"""mnemosyne-corpus — offline corpus acquisition and enrichment CLI.

Usage
-----
    poetry run mnemosyne-corpus list-languages
    poetry run mnemosyne-corpus list-sources
    poetry run mnemosyne-corpus validate
    poetry run mnemosyne-corpus acquire --language es
    poetry run mnemosyne-corpus acquire --all
    poetry run mnemosyne-corpus ingest --language ja
    poetry run mnemosyne-corpus ingest --all [--dry-run]
    poetry run mnemosyne-corpus build --language de
    poetry run mnemosyne-corpus build --all [--dry-run] [--force]
    poetry run mnemosyne-corpus report

All commands respect the manifest at ``corpora/manifest.yaml`` by default.
Override with ``--manifest <path>``.
"""
from __future__ import annotations

import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import typer
from rich.console import Console
from rich.table import Table
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.corpus.build import BuildResult, acquire_entry, build_entry
from backend.corpus.chunking import DEFAULT_MAX_CHUNK_CHARS
from backend.corpus.levels import difficulty_rank
from backend.corpus.manifest import CorpusManifest, CorpusEntry, load_manifest
from backend.corpus.quality import check_manifest
from backend.corpus.reports import generate_stats
from backend.core.config import get_settings
from backend.parsing.plugin_loader import load_plugins

logger = logging.getLogger(__name__)

# Force UTF-8 output on Windows consoles that default to CP1252.
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

console = Console(legacy_windows=False)

app = typer.Typer(
    name="mnemosyne-corpus",
    help="Offline corpus acquisition and enrichment for Mnemosyne.",
    add_completion=False,
)

DEFAULT_MANIFEST_PATH = Path("corpora/manifest.yaml")


# ── DB session context manager ────────────────────────────────────────────────

@asynccontextmanager
async def _db_session() -> AsyncGenerator[AsyncSession, None]:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            yield session
    finally:
        await engine.dispose()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_manifest_or_exit(path: Path) -> CorpusManifest:
    if not path.exists():
        console.print(f"[red]Manifest not found:[/red] {path}")
        raise typer.Exit(code=1)
    try:
        return load_manifest(path)
    except Exception as exc:
        console.print(f"[red]Manifest error:[/red] {exc}")
        raise typer.Exit(code=1)


def _resolve_entries(
    manifest: CorpusManifest,
    language: str | None,
    all_languages: bool,
) -> list[CorpusEntry]:
    if all_languages:
        entries = manifest.entries
    elif language:
        entries = manifest.for_language(language)
        if not entries:
            console.print(f"[yellow]No entries for language '{language}' in manifest.[/yellow]")
            raise typer.Exit(code=0)
    else:
        console.print("[red]Specify --language LANG or --all.[/red]")
        raise typer.Exit(code=1)
    return sorted(entries, key=lambda e: (difficulty_rank(e.framework.value, e.level), e.title))


# ── Commands ──────────────────────────────────────────────────────────────────

@app.command("list-languages")
def list_languages(
    manifest_path: Path = typer.Option(DEFAULT_MANIFEST_PATH, "--manifest", "-m", help="Path to manifest YAML"),
) -> None:
    """Show all languages in the manifest with entry counts."""
    manifest = _load_manifest_or_exit(manifest_path)
    table = Table(title="Languages in manifest", show_header=True)
    table.add_column("Code", style="cyan")
    table.add_column("Entries", justify="right")
    for lang in manifest.languages():
        count = len(manifest.for_language(lang))
        table.add_row(lang, str(count))
    console.print(table)


@app.command("list-sources")
def list_sources(
    manifest_path: Path = typer.Option(DEFAULT_MANIFEST_PATH, "--manifest", "-m"),
    language: str | None = typer.Option(None, "--language", "-l", help="Filter by language code"),
) -> None:
    """List all corpus sources in the manifest."""
    manifest = _load_manifest_or_exit(manifest_path)
    entries = manifest.for_language(language) if language else manifest.entries
    entries = sorted(entries, key=lambda e: (e.language, difficulty_rank(e.framework.value, e.level)))

    table = Table(title="Corpus sources", show_header=True)
    table.add_column("Lang", style="cyan", width=6)
    table.add_column("Level", width=6)
    table.add_column("Title")
    table.add_column("Author")
    table.add_column("License", width=14)

    for e in entries:
        cefr = e.cefr_equivalent or e.level
        table.add_row(e.language, cefr, e.title, e.author or "—", e.license)
    console.print(table)


@app.command("validate")
def validate(
    manifest_path: Path = typer.Option(DEFAULT_MANIFEST_PATH, "--manifest", "-m"),
    check_plugins: bool = typer.Option(False, "--check-plugins", help="Verify plugin availability"),
) -> None:
    """Validate the manifest structure and check for quality issues."""
    manifest = _load_manifest_or_exit(manifest_path)

    supported: set[str] | None = None
    if check_plugins:
        registry = load_plugins()
        supported = set(registry.supported_languages().keys())

    report = check_manifest(manifest, supported_languages=supported)

    if not report.issues:
        console.print(f"[green]OK[/green] Manifest OK - {len(manifest.entries)} entries, no issues.")
        return

    for issue in report.errors:
        console.print(f"[red]ERROR[/red] [{issue.language}] {issue.title}: {issue.message}")
    for issue in report.warnings:
        console.print(f"[yellow]WARN[/yellow]  [{issue.language}] {issue.title}: {issue.message}")

    console.print(
        f"\n{len(report.errors)} error(s), {len(report.warnings)} warning(s)."
    )
    if report.errors:
        raise typer.Exit(code=1)


@app.command("acquire")
def acquire(
    language: str | None = typer.Option(None, "--language", "-l"),
    all_languages: bool = typer.Option(False, "--all"),
    force: bool = typer.Option(False, "--force", help="Re-download even if cached"),
    manifest_path: Path = typer.Option(DEFAULT_MANIFEST_PATH, "--manifest", "-m"),
    cache_dir: Path = typer.Option(Path("data/corpus_cache"), "--cache-dir"),
) -> None:
    """Download and cache corpus texts (no parsing)."""
    manifest = _load_manifest_or_exit(manifest_path)
    entries = _resolve_entries(manifest, language, all_languages)

    async def _run() -> None:
        for entry in entries:
            try:
                text = await acquire_entry(entry, force=force, cache_dir=cache_dir)
                console.print(
                    f"[green]OK[/green] [{entry.language}] {entry.title} "
                    f"({len(text):,} chars)"
                )
            except Exception as exc:
                console.print(f"[red]FAIL[/red] [{entry.language}] {entry.title}: {exc}")

    asyncio.run(_run())


@app.command("ingest")
def ingest(
    language: str | None = typer.Option(None, "--language", "-l"),
    all_languages: bool = typer.Option(False, "--all"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    force: bool = typer.Option(False, "--force"),
    manifest_path: Path = typer.Option(DEFAULT_MANIFEST_PATH, "--manifest", "-m"),
    cache_dir: Path = typer.Option(Path("data/corpus_cache"), "--cache-dir"),
    max_chunk_chars: int = typer.Option(DEFAULT_MAX_CHUNK_CHARS, "--max-chunk-chars"),
) -> None:
    """Parse cached texts and persist to the database."""
    manifest = _load_manifest_or_exit(manifest_path)
    entries = _resolve_entries(manifest, language, all_languages)
    registry = load_plugins()

    async def _run() -> None:
        async with _db_session() as db:
            for entry in entries:
                result: BuildResult = await build_entry(
                    entry, registry, db,
                    dry_run=dry_run,
                    force=force,
                    cache_dir=cache_dir,
                    max_chunk_chars=max_chunk_chars,
                )
                _print_result(result)

    asyncio.run(_run())


@app.command("build")
def build(
    language: str | None = typer.Option(None, "--language", "-l"),
    all_languages: bool = typer.Option(False, "--all"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    force: bool = typer.Option(False, "--force"),
    manifest_path: Path = typer.Option(DEFAULT_MANIFEST_PATH, "--manifest", "-m"),
    cache_dir: Path = typer.Option(Path("data/corpus_cache"), "--cache-dir"),
    max_chunk_chars: int = typer.Option(DEFAULT_MAX_CHUNK_CHARS, "--max-chunk-chars"),
) -> None:
    """Acquire + parse + persist in one step (acquire then ingest)."""
    manifest = _load_manifest_or_exit(manifest_path)
    entries = _resolve_entries(manifest, language, all_languages)
    registry = load_plugins()

    async def _run() -> None:
        async with _db_session() as db:
            for entry in entries:
                result: BuildResult = await build_entry(
                    entry, registry, db,
                    dry_run=dry_run,
                    force=force,
                    cache_dir=cache_dir,
                    max_chunk_chars=max_chunk_chars,
                )
                _print_result(result)

    asyncio.run(_run())


@app.command("report")
def report(
    manifest_path: Path = typer.Option(DEFAULT_MANIFEST_PATH, "--manifest", "-m"),
) -> None:
    """Show corpus coverage statistics from the database."""
    manifest = _load_manifest_or_exit(manifest_path)
    registry = load_plugins()

    async def _run() -> None:
        async with _db_session() as db:
            stats = await generate_stats(
                db, registry, manifest_languages=manifest.languages()
            )
        table = Table(title="Corpus coverage", show_header=True)
        table.add_column("Language", style="cyan")
        table.add_column("Display name")
        table.add_column("Documents", justify="right")
        table.add_column("Sentences", justify="right")
        table.add_column("Objects", justify="right")
        for ls in stats.by_language:
            table.add_row(
                ls.language,
                ls.display_name,
                str(ls.documents),
                str(ls.sentences),
                str(ls.objects),
            )
        table.add_section()
        table.add_row(
            "TOTAL", "",
            str(stats.total_documents),
            str(stats.total_sentences),
            str(stats.total_objects),
            style="bold",
        )
        console.print(table)
        if stats.languages_in_manifest_but_not_db:
            console.print(
                "[yellow]Languages in manifest but not yet in DB:[/yellow] "
                + ", ".join(stats.languages_in_manifest_but_not_db)
            )

    asyncio.run(_run())


def _print_result(result: BuildResult) -> None:
    entry = result.entry
    prefix = f"[{entry.language}] {entry.title}"
    if result.status == "skipped":
        console.print(f"[dim]--[/dim] {prefix}: already ingested (skipped)")
    elif result.status == "dry_run":
        console.print(f"[blue]DRY[/blue] {prefix}: {'; '.join(result.warnings)}")
    elif result.status == "ingested":
        console.print(
            f"[green]OK[/green] {prefix}: "
            f"{result.chunks_processed} chunk(s), "
            f"{result.sentences_total} sentences, "
            f"{result.objects_total} objects"
        )
    elif result.status == "acquired":
        console.print(f"[cyan]DL[/cyan] {prefix}: acquired")
    elif result.status == "failed":
        console.print(f"[red]FAIL[/red] {prefix}: {result.error}")
    if result.warnings and result.status not in ("dry_run",):
        for w in result.warnings:
            console.print(f"  [yellow]WARN[/yellow] {w}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    app()
