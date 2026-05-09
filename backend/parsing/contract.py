"""Plugin Output Contract — invariants all LanguagePlugin implementations must satisfy.

REQUIRED INVARIANTS (enforced by validate_result and test_plugin_contract.py)
─────────────────────────────────────────────────────────────────────────────

C1  canonical_form is a non-empty string with no leading/trailing whitespace.
    Rationale: canonical_form is hashed to a stable UUID by canonical_object_id();
    whitespace would silently produce different IDs for the same lemma.

C2  canonical_form is deterministic: identical input → identical canonical_form,
    across calls and across process restarts (no randomness, timestamps, or
    insertion-order dependence).
    Enforced by: test_plugin_contract.py::TestC2Determinism (call twice, compare sets).

C3  No two CandidateObjects in one CandidateSentenceResult share a canonical_form.
    Rationale: the pipeline writes one DB row per canonical_form; duplicates
    produce silent last-write-wins merges with unpredictable lesson_data.

C4  Surface tokens consumed by phrase_family or idiom candidates must not also
    appear as vocabulary candidates.  Conjugation, agreement, case_agreement,
    grammar, and nuance types are explicitly EXEMPT — those are orthogonal
    learning goals (inflection lesson ≠ vocabulary lesson) and co-occurrence is
    intentional.
    Rationale: an idiom/phrase_family lesson covers "all that glitters" as a
    unit; individual token vocabulary cards for "all", "that", etc. inside the
    phrase create redundant and conflicting lesson flows.  A conjugation lesson
    for "habla" (hablar:present:3sg) and a vocabulary lesson for "hablar" are
    distinct and should both be surfaced.

C5  confidence, when present, is in the half-open interval (0.0, 1.0].
    A confidence of exactly 0.0 is treated as "unknown" and must be omitted (None).
    Rationale: a zero-confidence object is not useful and confuses the SRS scheduler.

C6  confidence < 0.70 requires lesson_data["confidence_note"] to be a non-empty string
    explaining why the score is low (e.g. "OOV word", "ambiguous homograph").
    Rationale: exposes heuristic limits to the UI so users are not misled.

C7  Every RelationHint.relation_type must be one of VALID_RELATION_TYPES.
    Rationale: unrecognised relation types are silently ignored by the parse route;
    using them produces phantom edges that never appear in the DB.
    (Violation spotted in nuance/ru.py: "motion_pair" — not a declared type.)

C8  RelationHint.target_canonical_form must be a non-empty, non-whitespace string.
    Rationale: an empty target cannot be resolved to a UUID; the edge is silently
    dropped by the parse route.

C9  Type-specific lesson_data keys must be present (REQUIRED_LESSON_KEYS).
    These are the minimum keys that the lesson UI and SRS engine depend on.
    Language-specific extra keys are allowed and encouraged.

C10 If capabilities.idiom_detection is False, the plugin must not emit
    type="idiom" objects.
    Rationale: the frontend gates the idiom lesson card on this flag; mismatches
    produce visible UI breakage.

C11 If capabilities.morphology_depth == "none", the plugin must not emit
    type="conjugation", "agreement", or "case_agreement" objects.
    Rationale: morphology_depth="none" is a contract to the frontend that no
    morphological drills will be generated for this language.

C12 If nuance_capabilities.phrase_families == "none" (or nuance_capabilities is None),
    the plugin must not emit type="phrase_family" objects.

C13 CandidateSentenceResult.text must equal the input sentence exactly (no
    mutation, stripping, or normalisation by the plugin).
    Rationale: the pipeline joins results to the original text for display; any
    mutation produces misaligned sentence boundaries.

C14 language_code must be lowercase and must equal capabilities.code.
    Rationale: plugin_loader and canonical_object_id both lower-case the code
    before lookup; a mixed-case code would register but never be found.

C15 direction must equal capabilities.direction.
    Rationale: direction is exposed on both the plugin and its capabilities;
    divergence means one of the two is stale.

LANGUAGE-VARIABLE (NOT enforced here)
──────────────────────────────────────
• canonical_form format per type — e.g. German nouns preserve capitalisation;
  conjugation canonical form separates axes with ":" but axis labels are language-
  specific (tense pool, mood pool).
• Confidence caps and baselines per type — Spanish caps conjugation at 0.85;
  French and German cap at 0.80. These reflect model quality differences.
• lesson_data keys beyond REQUIRED_LESSON_KEYS — paradigm_class, register,
  etymology, etc. are encouraged but language-specific.
• Which types are emitted — a stub plugin that only emits "vocabulary" is valid.
• tense_pool, mood_pool content — language-specific.
• Capitalisation of canonical_form for German nouns is explicitly declared via
  capabilities (no canonical_form_lowercase flag yet; accept it as convention).

COMPLIANT PLUGIN SKETCH
──────────────────────────────────────────────────────────────────────────────
    class GoodPlugin:
        language_code = "xx"
        direction     = "ltr"
        capabilities  = LanguageCapabilities(
            code="xx", direction="ltr", idiom_detection=False, ...
            nuance_capabilities=NuanceCapabilities(phrase_families="none", ...)
        )
        def analyze_sentence(self, sent):
            return CandidateSentenceResult(
                text=sent,          # C13 — preserve input
                candidates=[
                    CandidateObject(
                        canonical_form="cat",   # C1 — no padding, non-empty
                        type="vocabulary",
                        label="cat",
                        lesson_data={"lemma": "cat"},   # C9 — required key
                        confidence=0.85,                # C5 — in (0, 1]
                        relation_hints=[],
                    )
                ],
            )

FAILING PLUGIN SKETCH
──────────────────────────────────────────────────────────────────────────────
    class BadPlugin:
        language_code = "xx"
        direction     = "ltr"
        capabilities  = LanguageCapabilities(
            code="xx", direction="ltr", idiom_detection=False,
            morphology_depth="none", ...
        )
        def analyze_sentence(self, sent):
            return CandidateSentenceResult(
                text=sent.strip(),   # C13 FAIL — stripped != input when input has no punct
                candidates=[
                    CandidateObject(
                        canonical_form=" cat ",  # C1 FAIL — leading/trailing whitespace
                        type="conjugation",      # C11 FAIL — morphology_depth="none"
                        label="cat",
                        lesson_data={},          # C9 FAIL — missing "tense", "mood"
                        confidence=0.0,          # C5 FAIL — must be None or > 0
                        relation_hints=[
                            RelationHint(
                                relation_type="motion_pair",  # C7 FAIL — undeclared type
                                target_canonical_form="",     # C8 FAIL — empty target
                                target_type="vocabulary",
                            )
                        ],
                    ),
                    CandidateObject(            # C3 FAIL — duplicate canonical_form
                        canonical_form=" cat ",
                        type="conjugation",
                        label="cat",
                        lesson_data={},
                        confidence=None,
                    ),
                ],
            )
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.schemas.parse import CandidateSentenceResult

# Set MNEMOSYNE_CONTRACT_CHECK=1 to enable pipeline contract warnings.
CONTRACT_CHECK: bool = os.getenv("MNEMOSYNE_CONTRACT_CHECK") == "1"

VALID_RELATION_TYPES: frozenset[str] = frozenset({
    "conjugation_of",
    "agreement_of",
    "instance_of",
    "nuance_of",
})

# Minimum lesson_data keys required per type.  Plugins may add more.
REQUIRED_LESSON_KEYS: dict[str, frozenset[str]] = {
    "vocabulary":      frozenset({"lemma"}),
    "conjugation":     frozenset({"tense", "mood"}),
    "agreement":       frozenset({"noun"}),
    "case_agreement":  frozenset({"noun"}),
    "idiom":           frozenset({"meaning"}),
    "phrase_family":   frozenset({"meaning"}),
    "nuance":          frozenset({"nuance_type"}),
    "grammar":         frozenset(),   # no universal keys; pattern-specific
    "script":          frozenset(),
    "transliteration": frozenset(),
}


@dataclass
class ContractViolation:
    rule: str                         # e.g. "C3"
    message: str
    object_index: int | None = None
    canonical_form: str | None = None


@dataclass
class ContractReport:
    language_code: str = ""
    violations: list[ContractViolation] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.violations

    def __str__(self) -> str:
        if self.ok:
            return "OK"
        lines = [
            f"  [{v.rule}] obj[{v.object_index}] {v.canonical_form!r}: {v.message}"
            if v.object_index is not None
            else f"  [{v.rule}] {v.message}"
            for v in self.violations
        ]
        return "\n".join(lines)


def validate_result(
    result: CandidateSentenceResult,
    plugin,
    *,
    input_sentence: str | None = None,
) -> ContractReport:
    """Validate one CandidateSentenceResult against the plugin output contract (C1–C15).

    Args:
        result:         Output of plugin.analyze_sentence(sentence).
        plugin:         The plugin that produced result (used for capability checks).
        input_sentence: Exact string passed to analyze_sentence (for C13).

    Returns:
        ContractReport; .ok is True when all invariants hold.
    """
    report = ContractReport(language_code=getattr(plugin, "language_code", "??"))
    caps = plugin.capabilities

    seen_canonical: dict[str, int] = {}
    non_vocab_surfaces: set[str] = set()
    _C4_CONSUMING = frozenset({"phrase_family", "idiom"})

    for i, obj in enumerate(result.candidates):
        cf = obj.canonical_form

        # C1
        if not cf or cf != cf.strip():
            report.violations.append(ContractViolation(
                "C1",
                f"canonical_form {cf!r} is empty or has surrounding whitespace",
                object_index=i, canonical_form=cf,
            ))

        # C3
        if cf in seen_canonical:
            report.violations.append(ContractViolation(
                "C3",
                f"Duplicate canonical_form (first at index {seen_canonical[cf]})",
                object_index=i, canonical_form=cf,
            ))
        else:
            seen_canonical[cf] = i

        # C4 — only phrase_family/idiom types consume vocabulary surface tokens
        if obj.type in _C4_CONSUMING and obj.surface_form:
            for word in obj.surface_form.lower().split():
                non_vocab_surfaces.add(word)

        # C5
        if obj.confidence is not None and not (0.0 < obj.confidence <= 1.0):
            report.violations.append(ContractViolation(
                "C5",
                f"confidence={obj.confidence} not in (0.0, 1.0]",
                object_index=i, canonical_form=cf,
            ))

        # C6
        if obj.confidence is not None and obj.confidence < 0.70:
            note = obj.lesson_data.get("confidence_note")
            if not isinstance(note, str) or not note.strip():
                report.violations.append(ContractViolation(
                    "C6",
                    f"confidence={obj.confidence:.2f} < 0.70 but confidence_note absent",
                    object_index=i, canonical_form=cf,
                ))

        # C7, C8
        for hint in obj.relation_hints:
            if hint.relation_type not in VALID_RELATION_TYPES:
                report.violations.append(ContractViolation(
                    "C7",
                    f"Undeclared relation_type {hint.relation_type!r} — "
                    f"must be one of {sorted(VALID_RELATION_TYPES)}",
                    object_index=i, canonical_form=cf,
                ))
            if not hint.target_canonical_form or not hint.target_canonical_form.strip():
                report.violations.append(ContractViolation(
                    "C8",
                    "target_canonical_form in RelationHint is empty",
                    object_index=i, canonical_form=cf,
                ))

        # C9
        required = REQUIRED_LESSON_KEYS.get(obj.type, frozenset())
        missing = required - obj.lesson_data.keys()
        if missing:
            report.violations.append(ContractViolation(
                "C9",
                f"type={obj.type!r} missing required lesson_data keys: {sorted(missing)}",
                object_index=i, canonical_form=cf,
            ))

        # C10
        if obj.type == "idiom" and not caps.idiom_detection:
            report.violations.append(ContractViolation(
                "C10",
                "type='idiom' emitted but capabilities.idiom_detection=False",
                object_index=i, canonical_form=cf,
            ))

        # C11
        if obj.type in ("conjugation", "agreement", "case_agreement"):
            if caps.morphology_depth == "none":
                report.violations.append(ContractViolation(
                    "C11",
                    f"type={obj.type!r} emitted but capabilities.morphology_depth='none'",
                    object_index=i, canonical_form=cf,
                ))

        # C12
        if obj.type == "phrase_family":
            nc = caps.nuance_capabilities
            if nc is None or nc.phrase_families == "none":
                report.violations.append(ContractViolation(
                    "C12",
                    "type='phrase_family' emitted but phrase_families='none' (or null)",
                    object_index=i, canonical_form=cf,
                ))

    # C4 — second pass: vocabulary objects vs non-vocab surfaces
    for i, obj in enumerate(result.candidates):
        if obj.type == "vocabulary" and obj.surface_form:
            if obj.surface_form.lower() in non_vocab_surfaces:
                report.violations.append(ContractViolation(
                    "C4",
                    f"surface_form {obj.surface_form!r} appears in both a structured "
                    "candidate and a vocabulary candidate (double-tagged)",
                    object_index=i, canonical_form=obj.canonical_form,
                ))

    # C13
    if input_sentence is not None and result.text != input_sentence:
        report.violations.append(ContractViolation(
            "C13",
            f"result.text mutated: expected {input_sentence!r}, got {result.text!r}",
        ))

    # C14
    lang = getattr(plugin, "language_code", "")
    if lang != lang.lower():
        report.violations.append(ContractViolation(
            "C14", f"language_code {lang!r} is not lowercase",
        ))
    if caps.code != lang:
        report.violations.append(ContractViolation(
            "C14", f"capabilities.code={caps.code!r} != language_code={lang!r}",
        ))

    # C15
    direction = getattr(plugin, "direction", None)
    if direction is not None and direction != caps.direction:
        report.violations.append(ContractViolation(
            "C15",
            f"plugin.direction={direction!r} != capabilities.direction={caps.direction!r}",
        ))

    return report


def assert_contract(
    result: CandidateSentenceResult,
    plugin,
    *,
    input_sentence: str | None = None,
) -> None:
    """Raise AssertionError listing all contract violations, if any."""
    report = validate_result(result, plugin, input_sentence=input_sentence)
    if not report.ok:
        raise AssertionError(
            f"Contract violation(s) for plugin {getattr(plugin, 'language_code', '??')!r}:\n{report}"
        )
