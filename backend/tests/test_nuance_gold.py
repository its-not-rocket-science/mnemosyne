"""Multilingual nuance gold-test suite.

Parametrized over all fixtures in backend/tests/fixtures/nuance_gold/.
Each case runs the configured pipeline (plugin / extractor / both) and
asserts on candidate types, nuance_types, confidence, lesson_data keys,
and absence of raw UUIDs in lesson_data.

Capability tests verify that each plugin's declared nuance_capabilities
field for a dimension falls within the allowed set listed in the fixture.

Fixture schema (per language JSON file):
    language                  BCP-47 tag
    plugin_module             dotted import path for the plugin
    plugin_class              class name inside that module
    nuance_extractor_module   dotted import path for the extractor (or null)
    nuance_extractor_class    class name inside that module (or null)
    tokenizer                 "spacy" | "words" | "characters"
    capability_assertions     {dimension: [allowed_levels]}
    capability_gaps           {dimension: human-readable note}
    cases                     list of case dicts (see _assert_case for schema)
"""
from __future__ import annotations

import importlib
import json
import re
from pathlib import Path
from typing import Any

import pytest

from backend.schemas.parse import CandidateObject

# ── Paths and constants ───────────────────────────────────────────────────────

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "nuance_gold"
_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I
)


# ── Token stub ────────────────────────────────────────────────────────────────

class _Tok:
    """Minimal token stub — only attributes our extractors ever read."""

    def __init__(
        self,
        text: str,
        pos: str = "NOUN",
        lemma: str = "",
        dep: str = "dep",
    ) -> None:
        self.text      = text
        self.pos_      = pos
        self.lemma_    = lemma or text.lower()
        self.dep_      = dep
        self.is_punct  = text in ".,:;!?\"'()[]{}—–-"
        self.is_space  = text.isspace()

    def __repr__(self) -> str:
        return f"<Tok {self.text!r}>"


# ── Plugin / extractor loading ────────────────────────────────────────────────

def _try_import(module_path: str | None, class_name: str | None) -> Any | None:
    if not module_path or not class_name:
        return None
    try:
        mod = importlib.import_module(module_path)
        cls = getattr(mod, class_name)
        return cls()
    except (ImportError, OSError, AttributeError, Exception):
        return None


# ── Tokenization ──────────────────────────────────────────────────────────────

def _tokenize(text: str, tokenizer: str, plugin: Any | None) -> list[_Tok]:
    if tokenizer == "words":
        return [_Tok(w) for w in text.split()]
    if tokenizer == "characters":
        return [_Tok(c) for c in text]
    if tokenizer == "jieba":
        try:
            import jieba  # type: ignore[import-untyped]
            return [_Tok(w) for w in jieba.cut(text)]
        except ImportError:
            return [_Tok(c) for c in text]
    # "spacy" — use the plugin's NLP pipeline when available
    if plugin is not None and hasattr(plugin, "_nlp"):
        try:
            return list(plugin._nlp(text))
        except Exception:
            pass
    # fallback: word-split (avoids hard crash in spaCy-absent environments)
    return [_Tok(w) for w in text.split()]


# ── Pipeline execution ────────────────────────────────────────────────────────

def _run_case(
    plugin: Any | None,
    extractor: Any | None,
    case: dict,
    fixture: dict,
) -> list[CandidateObject]:
    text      = case["text"]
    pipeline  = case["pipeline"]
    lang      = fixture["language"]
    # Per-case tokenizer_override beats fixture-level tokenizer
    tokenizer = case.get("tokenizer_override") or fixture["tokenizer"]

    plugin_candidates: list[CandidateObject] = []
    if pipeline in ("plugin", "both") and plugin is not None:
        plugin_candidates = list(plugin.analyze_sentence(text).candidates)

    extractor_candidates: list[CandidateObject] = []
    if pipeline in ("extractor", "both") and extractor is not None:
        tokens = _tokenize(text, tokenizer, plugin)
        extractor_candidates = list(
            extractor.extract_nuance(text, tokens, plugin_candidates, lang)
        )

    return plugin_candidates + extractor_candidates


# ── Assertion helpers ─────────────────────────────────────────────────────────

def _str_values(d: dict) -> list[str]:
    """Collect all leaf string values from a lesson_data dict (recursive)."""
    out: list[str] = []
    for v in d.values():
        if isinstance(v, str):
            out.append(v)
        elif isinstance(v, dict):
            out.extend(_str_values(v))
        elif isinstance(v, list):
            out.extend(x for x in v if isinstance(x, str))
    return out


def _assert_case(candidates: list[CandidateObject], case: dict) -> None:
    cid         = case["id"]
    types_seen  = {c.type for c in candidates}
    nuance_types_seen: set[str] = {
        c.lesson_data.get("nuance_type", "")
        for c in candidates
        if c.type == "nuance" and c.lesson_data.get("nuance_type")
    }

    # types_present
    for t in (case.get("assert_types_present") or []):
        assert t in types_seen, (
            f"[{cid}] expected type {t!r}; got {sorted(types_seen)}"
        )

    # types_absent
    for t in (case.get("assert_types_absent") or []):
        assert t not in types_seen, (
            f"[{cid}] type {t!r} should be absent; found in {sorted(types_seen)}"
        )

    # nuance_type present
    want_nt = case.get("assert_nuance_type")
    if want_nt:
        assert want_nt in nuance_types_seen, (
            f"[{cid}] expected nuance_type {want_nt!r}; got {nuance_types_seen}"
        )

    # nuance_types absent
    for nt in (case.get("assert_nuance_types_absent") or []):
        assert nt not in nuance_types_seen, (
            f"[{cid}] nuance_type {nt!r} should be absent; found"
        )

    # canonical_form substring
    want_cf = case.get("assert_canonical_contains")
    if want_cf:
        matched = any(want_cf in (c.canonical_form or "") for c in candidates)
        assert matched, (
            f"[{cid}] no canonical_form contains {want_cf!r}; "
            f"got {[c.canonical_form for c in candidates]}"
        )

    # confidence threshold (at least one candidate must meet it)
    conf_ge = case.get("confidence_ge")
    if conf_ge is not None:
        any_meets = any((c.confidence or 0) >= conf_ge for c in candidates)
        assert any_meets, (
            f"[{cid}] no candidate has confidence >= {conf_ge}; "
            f"got {[(c.canonical_form, c.confidence) for c in candidates]}"
        )

    # lesson_data required keys (per type)
    for type_name, required_keys in (case.get("lesson_data_required_keys") or {}).items():
        typed = [c for c in candidates if c.type == type_name]
        assert typed, (
            f"[{cid}] no candidates of type {type_name!r} found for key check"
        )
        for c in typed:
            ld = c.lesson_data or {}
            for key in required_keys:
                assert key in ld, (
                    f"[{cid}] {type_name} candidate {c.canonical_form!r} "
                    f"missing lesson_data key {key!r}; got {list(ld)}"
                )

    # no raw UUIDs in any lesson_data string value
    if case.get("no_raw_uuids"):
        for c in candidates:
            for val in _str_values(c.lesson_data or {}):
                assert not _UUID_RE.search(val), (
                    f"[{cid}] raw UUID in lesson_data of {c.canonical_form!r}: {val!r}"
                )

    # minimum vocabulary candidate count
    min_vocab = case.get("assert_min_vocabulary_count")
    if min_vocab is not None:
        vocab_count = sum(1 for c in candidates if c.type == "vocabulary")
        assert vocab_count >= min_vocab, (
            f"[{cid}] expected at least {min_vocab} vocabulary candidates; "
            f"got {vocab_count}"
        )

    # no candidate confidence exceeds threshold (morphology-light cap)
    conf_max = case.get("assert_no_confidence_above")
    if conf_max is not None:
        over = [
            (c.canonical_form, c.confidence)
            for c in candidates
            if c.confidence is not None and c.confidence > conf_max
        ]
        assert not over, (
            f"[{cid}] candidates have confidence > {conf_max}: {over}"
        )


# ── Fixture collection ────────────────────────────────────────────────────────

def _load_fixtures() -> list[dict]:
    return [
        json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(_FIXTURE_DIR.glob("*.json"))
    ]


def _collect_cases() -> list[tuple[str, dict, dict]]:
    """Return (case_id, fixture, case) for every case across all fixtures."""
    out: list[tuple[str, dict, dict]] = []
    for fixture in _load_fixtures():
        for case in fixture["cases"]:
            out.append((case["id"], fixture, case))
    return out


def _collect_capability_cases() -> list[tuple[str, str, list[str], dict]]:
    """Return (lang, dimension, allowed_levels, fixture) for each capability assertion."""
    out: list[tuple[str, str, list[str], dict]] = []
    for fixture in _load_fixtures():
        lang = fixture["language"]
        for dimension, allowed in (fixture.get("capability_assertions") or {}).items():
            out.append((lang, dimension, allowed, fixture))
    return out


_ALL_CASES = _collect_cases()
_CAP_CASES = _collect_capability_cases()


# ── Gold-case tests ───────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "case_id, fixture, case",
    _ALL_CASES,
    ids=[cid for cid, _, _ in _ALL_CASES],
)
def test_nuance_gold_case(case_id: str, fixture: dict, case: dict) -> None:
    pipeline = case["pipeline"]
    tokenizer = fixture["tokenizer"]

    need_plugin = (
        pipeline in ("plugin", "both")
        or tokenizer == "spacy"
    )

    plugin = _try_import(fixture["plugin_module"], fixture["plugin_class"])
    if need_plugin and plugin is None:
        pytest.skip(
            f"Plugin {fixture['plugin_class']} unavailable "
            f"(module: {fixture['plugin_module']})"
        )

    extractor = _try_import(
        fixture.get("nuance_extractor_module"),
        fixture.get("nuance_extractor_class"),
    )
    if pipeline in ("extractor", "both") and extractor is None:
        if fixture.get("nuance_extractor_module"):
            pytest.skip(
                f"Extractor {fixture.get('nuance_extractor_class')} unavailable"
            )

    candidates = _run_case(plugin, extractor, case, fixture)
    _assert_case(candidates, case)


# ── Capability assertion tests ────────────────────────────────────────────────

@pytest.mark.parametrize(
    "lang, dimension, allowed_levels, fixture",
    _CAP_CASES,
    ids=[f"{lang}_{dim}" for lang, dim, _, _ in _CAP_CASES],
)
def test_capability_declared(
    lang: str,
    dimension: str,
    allowed_levels: list[str],
    fixture: dict,
) -> None:
    plugin = _try_import(fixture["plugin_module"], fixture["plugin_class"])
    if plugin is None:
        pytest.skip(f"Plugin {fixture['plugin_class']} unavailable")

    nuance_caps = getattr(plugin.capabilities, "nuance_capabilities", None)
    if nuance_caps is None:
        pytest.skip(f"{lang} plugin has no nuance_capabilities declared")

    actual = getattr(nuance_caps, dimension, None)
    assert actual is not None, (
        f"NuanceCapabilities has no field {dimension!r}"
    )
    assert actual in allowed_levels, (
        f"{lang}.{dimension}: expected one of {allowed_levels}, got {actual!r}"
    )
