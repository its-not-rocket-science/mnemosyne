"""Generate and insert verbal government entries from JSON spec files.

Usage:
    python scripts/gen_verbal_government.py [--lang LANG [LANG ...]] [--dry-run] [--validate-only]

Each JSON spec file lives at scripts/data/{lang}_verbal_government.json and
contains a list of objects with this schema:

    {
      "lemma": "желать",
      "case": "genitive",
      "example": "«желать» governs the genitive: желать успеха (to wish success)"
    }

Per-language configuration (target file, dict name, valid cases, lemma char
class) lives in LANG_CONFIG below. Add a new language by appending an entry
there and ensuring backend/nuance/{lang}.py contains a `_VERBAL_GOV` dict
literal (or whatever dict_name the config specifies).

The script:
  1. Loads and validates the spec file for each requested language.
  2. Reads existing lemmas from the target dict via regex.
  3. Skips any lemma already present (idempotent).
  4. Inserts new entries before the closing '}' of the dict.
  5. Verifies the module imports cleanly after patching.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(__file__).resolve().parent / "data"


# Per-language config. To add a language:
#   1. Add an entry here.
#   2. Make sure backend/nuance/{lang}.py defines the dict (empty `{}` ok).
#   3. Drop a JSON spec at scripts/data/{lang}_verbal_government.json.
LANG_CONFIG: dict[str, dict] = {
    "ru": {
        "target": "backend/nuance/ru.py",
        "dict_name": "_VERBAL_GOV",
        "valid_cases": frozenset({
            "nominative", "genitive", "dative", "accusative",
            "instrumental", "prepositional",
            "accusative/genitive", "genitive/accusative",
            "dative/accusative", "accusative/dative",
            "accusative+dative", "prepositional+о",
            "genitive+dative",
        }),
        "lemma_chars": r"\wЀ-ӿ ",
    },
    "de": {
        "target": "backend/nuance/de.py",
        "dict_name": "_VERBAL_GOV",
        "valid_cases": frozenset({
            "nominative", "accusative", "dative", "genitive",
            "accusative/dative", "dative/accusative",
            "an+accusative", "an+dative",
            "auf+accusative", "auf+dative",
            "in+accusative", "in+dative",
            "über+accusative", "über+dative",
            "unter+accusative", "unter+dative",
            "vor+accusative", "vor+dative",
            "hinter+accusative", "hinter+dative",
            "neben+accusative", "neben+dative",
            "zwischen+accusative", "zwischen+dative",
            "mit+dative", "nach+dative", "von+dative",
            "zu+dative", "bei+dative", "aus+dative",
            "seit+dative", "gegenüber+dative",
            "für+accusative", "um+accusative",
            "gegen+accusative", "ohne+accusative", "durch+accusative",
            "wegen+genitive", "trotz+genitive",
            "während+genitive", "statt+genitive",
            "double+accusative",
        }),
        "lemma_chars": r"\wäöüÄÖÜß ",
    },
    "la": {
        "target": "backend/nuance/la.py",
        "dict_name": "_VERBAL_GOV",
        "valid_cases": frozenset({
            "nominative", "accusative", "dative", "genitive",
            "ablative", "vocative", "locative",
            "accusative+infinitive", "ablative+absolute",
            "double+accusative", "accusative+dative",
            "genitive/ablative",
        }),
        "lemma_chars": r"\w",
    },
    "grc": {
        "target": "backend/nuance/grc.py",
        "dict_name": "_VERBAL_GOV",
        "valid_cases": frozenset({
            "nominative", "accusative", "dative", "genitive",
            "vocative",
            "accusative+infinitive", "genitive+infinitive",
            "double+accusative", "accusative+dative",
            "genitive/dative",
        }),
        "lemma_chars": r"\wἀ-ῼΑ-Ωα-ω",
    },
    "ar": {
        "target": "backend/nuance/ar.py",
        "dict_name": "_VERBAL_GOV",
        "valid_cases": frozenset({
            "nominative", "accusative", "genitive",
            "bi+genitive", "li+genitive",
            "fi+genitive", "ila+genitive",
            "min+genitive", "an+genitive",
            "ala+genitive", "ma'a+genitive",
            "double+accusative",
        }),
        "lemma_chars": r"\w؀-ۿ ـ",
    },
    # ── Romance languages (no morphological case; "case" labels are prepositions) ──
    "es": {
        "target": "backend/nuance/es.py",
        "dict_name": "_VERBAL_GOV",
        "valid_cases": frozenset({
            "direct_object", "indirect_object",
            "a", "de", "en", "con", "por", "para",
            "sobre", "contra", "hacia", "hasta", "tras", "ante", "bajo",
            "a+infinitive", "de+infinitive", "en+infinitive",
            "con+infinitive", "por+infinitive", "para+infinitive",
            "que+subjunctive", "que+indicative",
        }),
        "lemma_chars": r"\wáéíóúñüÁÉÍÓÚÑÜ ",
    },
    "fr": {
        "target": "backend/nuance/fr.py",
        "dict_name": "_VERBAL_GOV",
        "valid_cases": frozenset({
            "direct_object", "indirect_object",
            "à", "de", "en", "avec", "par", "pour",
            "sur", "contre", "vers", "jusqu'à", "dans", "chez",
            "à+infinitive", "de+infinitive", "par+infinitive", "pour+infinitive",
            "que+subjunctive", "que+indicative",
        }),
        "lemma_chars": r"\wàâäéèêëïîôöùûüÿçÀÂÄÉÈÊËÏÎÔÖÙÛÜŸÇ '",
    },
    "it": {
        "target": "backend/nuance/it.py",
        "dict_name": "_VERBAL_GOV",
        "valid_cases": frozenset({
            "direct_object", "indirect_object",
            "a", "di", "in", "con", "per", "su",
            "tra", "fra", "da", "contro", "verso",
            "a+infinitive", "di+infinitive", "da+infinitive",
            "per+infinitive",
            "che+subjunctive", "che+indicative",
        }),
        "lemma_chars": r"\wàèéìíîòóùúÀÈÉÌÍÎÒÓÙÚ '",
    },
    "pt": {
        "target": "backend/nuance/pt.py",
        "dict_name": "_VERBAL_GOV",
        "valid_cases": frozenset({
            "direct_object", "indirect_object",
            "a", "de", "em", "com", "por", "para",
            "sobre", "contra", "até", "perante", "ante",
            "a+infinitive", "de+infinitive", "em+infinitive",
            "para+infinitive", "por+infinitive",
            "que+subjunctive", "que+indicative",
        }),
        "lemma_chars": r"\wáâãàçéêíóôõúüÁÂÃÀÇÉÊÍÓÔÕÚÜ \-",
    },
    # ── Hebrew (prep system; some pronominal/inflected preps) ──
    "he": {
        "target": "backend/nuance/he.py",
        "dict_name": "_VERBAL_GOV",
        "valid_cases": frozenset({
            "direct_object", "indirect_object",
            "et",                # accusative marker את
            "be", "le", "mi",    # ב, ל, מ — prefixed prepositions
            "al", "el", "im",    # על, אל, עם
            "min", "ad", "neged",
            "shel",              # של (genitive marker)
            "le+infinitive",
        }),
        "lemma_chars": r"\w֐-׿ ",
    },
    # ── East Asian languages (particle / coverb systems) ──
    "ja": {
        "target": "backend/nuance/ja.py",
        "dict_name": "_VERBAL_GOV",
        "valid_cases": frozenset({
            "ga", "wo", "ni", "de", "e", "to",
            "kara", "made", "yori", "no",
            "ni+wo", "wo+ni", "to+wo",
            "ni+naru", "to+naru",
        }),
        "lemma_chars": r"\w぀-ゟ゠-ヿ一-鿿 ",
    },
    "ko": {
        "target": "backend/nuance/ko.py",
        "dict_name": "_VERBAL_GOV",
        "valid_cases": frozenset({
            "i_ga", "eul_reul",        # 이/가 nominative; 을/를 accusative
            "e", "eseo",                # 에, 에서
            "ege", "eseo",              # 에게, 에서
            "wa_gwa",                   # 와/과
            "euro_ro",                  # 으로/로
            "buteo", "kkaji",           # 부터, 까지
            "ui",                       # 의
            "eun_neun",                 # 은/는 (topic)
            "do",                       # 도
        }),
        "lemma_chars": r"\w가-힯ᄀ-ᇿ ",
    },
    "zh": {
        "target": "backend/nuance/zh.py",
        "dict_name": "_VERBAL_GOV",
        "valid_cases": frozenset({
            "direct_object",
            "gei", "dui", "gen", "he",      # 给, 对, 跟, 和
            "zai", "cong", "dao",            # 在, 从, 到
            "ba", "bei",                     # 把, 被 (object-fronting / passive)
            "wei", "wèile",                  # 为, 为了
            "yu", "guanyu",                  # 于, 关于
            "xiang",                         # 向
        }),
        "lemma_chars": r"\w一-鿿 ",
    },
}


def _spec_path(lang: str) -> Path:
    return DATA_DIR / f"{lang}_verbal_government.json"


def _target_path(cfg: dict) -> Path:
    return ROOT / cfg["target"]


def _dict_body(src: str, dict_name: str, target: str = "") -> tuple[str, int, int]:
    """Return (body, open_brace_pos, close_brace_pos) of the named dict literal."""
    match = re.search(rf'({re.escape(dict_name)}[^{{]*\{{)', src)
    if not match:
        where = f" in {target}" if target else ""
        sys.exit(
            f"[error] cannot locate {dict_name}{where}. "
            f"Add a `{dict_name}: dict[str, tuple[str, str]] = {{}}` line to "
            "the target module first, then re-run."
        )
    open_pos = match.end() - 1
    depth = 1
    pos = match.end()
    while pos < len(src) and depth:
        if src[pos] == "{":
            depth += 1
        elif src[pos] == "}":
            depth -= 1
        pos += 1
    close_pos = pos - 1
    return src[match.end():close_pos], open_pos, close_pos


def _existing_lemmas(cfg: dict) -> set[str]:
    src = _target_path(cfg).read_text(encoding="utf-8")
    body, _, _ = _dict_body(src, cfg["dict_name"], cfg["target"])
    chars = cfg["lemma_chars"]
    # Match both "..." and '...' quote styles — repr() emits single quotes.
    pattern = rf'(?:"([{chars}]+)"|\'([{chars}]+)\')\s*:\s*\('
    return {a or b for a, b in re.findall(pattern, body)}


def _load_spec(lang: str) -> list[dict]:
    path = _spec_path(lang)
    if not path.exists():
        sys.exit(f"[error] spec file not found: {path}")
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _validate(
    specs: list[dict],
    cfg: dict,
    existing: set[str],
) -> tuple[list[dict], list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    seen: set[str] = set()
    valid: list[dict] = []
    valid_cases = cfg["valid_cases"]

    for entry in specs:
        lemma = entry.get("lemma", "").strip()
        case = entry.get("case", "").strip()
        example = entry.get("example", "").strip()

        if not lemma:
            errors.append("  entry missing 'lemma' field")
            continue
        if not case:
            errors.append(f"  [{lemma}] missing 'case' field")
        elif case not in valid_cases:
            errors.append(
                f"  [{lemma}] invalid case {case!r}; "
                f"must be one of {sorted(valid_cases)}"
            )
        if not example:
            errors.append(f"  [{lemma}] missing 'example' field")
        if lemma in existing:
            warnings.append(f"  [{lemma}] already in {cfg['dict_name']} — skipping")
            continue
        if lemma in seen:
            errors.append(f"  [{lemma}] duplicate lemma in spec file")
            continue
        seen.add(lemma)

        if not errors:
            valid.append(entry)

    return valid, errors, warnings


def _render_entry(entry: dict) -> str:
    lemma = entry["lemma"]
    case = entry["case"]
    example = entry["example"].replace('"', '\\"')
    return f'    {lemma!r}: ({case!r}, "{example}"),'


def _patch_file(new_entries: list[dict], cfg: dict, lang: str, dry_run: bool) -> int:
    target = _target_path(cfg)
    src = target.read_text(encoding="utf-8")

    _, _, close_pos = _dict_body(src, cfg["dict_name"], cfg["target"])

    code_lines = [f"\n    # ── {lang.upper()} additions (gen_verbal_government.py) ──"]
    for entry in new_entries:
        code_lines.append(_render_entry(entry))
    insertion = "\n".join(code_lines) + "\n"

    new_src = src[:close_pos] + insertion + src[close_pos:]

    if dry_run:
        print(f"[dry-run] {lang}: would insert:")
        print(insertion[:2000])
        if len(insertion) > 2000:
            print(f"  ... ({len(insertion) - 2000} more chars)")
        return len(new_entries)

    target.write_text(new_src, encoding="utf-8")
    return len(new_entries)


def _verify_import(cfg: dict, lang: str) -> None:
    import subprocess
    module = cfg["target"].replace("/", ".").replace("\\", ".").removesuffix(".py")
    dict_name = cfg["dict_name"]
    code = (
        f"from {module} import {dict_name} as d; "
        f"print(f'{lang} {dict_name} size: {{len(d)}}')"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    if result.returncode != 0:
        print(f"[ERROR] {lang}: import failed:")
        print(result.stderr)
        sys.exit(1)
    print(result.stdout.strip())


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate verbal government entries (polyglot)"
    )
    parser.add_argument(
        "--lang", nargs="+",
        help=f"Language code(s). Supported: {sorted(LANG_CONFIG)}. "
             "Default: all langs that have a spec file.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    if args.lang:
        for lang in args.lang:
            if lang not in LANG_CONFIG:
                sys.exit(
                    f"[error] unknown lang {lang!r}; "
                    f"add to LANG_CONFIG. Supported: {sorted(LANG_CONFIG)}"
                )
        langs = list(args.lang)
    else:
        langs = sorted(
            lang for lang in LANG_CONFIG
            if _spec_path(lang).exists()
        )

    if not langs:
        sys.exit(
            f"[error] no spec files found. "
            f"Drop a JSON at {DATA_DIR}/<lang>_verbal_government.json."
        )

    all_valid: dict[str, list[dict]] = {}
    all_errors: list[str] = []

    for lang in langs:
        cfg = LANG_CONFIG[lang]
        existing = _existing_lemmas(cfg)
        print(f"[{lang}] existing {cfg['dict_name']}: {len(existing)} lemmas")

        specs = _load_spec(lang)
        valid, errors, warnings = _validate(specs, cfg, existing)

        for w in warnings:
            print(f"[warn]  {lang}: {w}")
        if errors:
            print(f"[ERROR] {lang}: {len(errors)} validation error(s):")
            for e in errors:
                print(e)
            all_errors.extend(errors)
        else:
            print(f"[ok]    {lang}: {len(valid)} new entries validated")
            all_valid[lang] = valid

    if all_errors:
        sys.exit(f"\n{len(all_errors)} validation error(s). Aborting.")

    if args.validate_only:
        print("\nValidation passed. (--validate-only: no files written)")
        return

    total = 0
    for lang, entries in all_valid.items():
        if not entries:
            continue
        cfg = LANG_CONFIG[lang]
        n = _patch_file(entries, cfg, lang, dry_run=args.dry_run)
        total += n
        if not args.dry_run:
            print(f"[wrote] {lang}: {n} entries appended to {cfg['target']}")

    if args.dry_run:
        print(f"\n[dry-run] {total} entries would be added.")
        return

    for lang in all_valid:
        if not all_valid[lang]:
            continue
        _verify_import(LANG_CONFIG[lang], lang)

    print(f"\nDone. {total} new verbal government entries added.")


if __name__ == "__main__":
    main()
