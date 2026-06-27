"""Parametric contract tests — every registered LanguagePlugin against C1–C15.

These tests are language-agnostic: they never assert linguistic correctness,
only structural compliance with the invariants in backend.parsing.contract.

Enable pipeline-level contract warnings with:
    MNEMOSYNE_CONTRACT_CHECK=1 pytest

Run only contract tests:
    pytest backend/tests/test_plugin_contract.py -v
"""
from __future__ import annotations

import pytest

from backend.parsing.contract import (
    REQUIRED_LESSON_KEYS,
    VALID_RELATION_TYPES,
    ContractReport,
    ContractViolation,
    assert_contract,
    validate_result,
)
from backend.parsing.plugin_loader import load_plugins
from backend.schemas.parse import (
    CandidateObject,
    CandidateSentenceResult,
    RelationHint,
)

# ── Fixture setup ─────────────────────────────────────────────────────────────

_REGISTRY = load_plugins()
_ALL_PLUGINS = list(_REGISTRY.all().values())
_PLUGIN_IDS  = [p.language_code for p in _ALL_PLUGINS]

# Representative sentences per language, chosen to exercise each extraction path.
# Kept to ≤3 sentences; fall back to _FALLBACK when a code is not listed.
_SENTENCES: dict[str, list[str]] = {
    "en": [
        "The cat sleeps.",
        "She speaks English every day.",
        "All that glitters is not gold.",
    ],
    "es": [
        "El libro rojo.",
        "Ella habla español todos los días.",
        "Sin embargo, no quiero meter la pata.",
    ],
    "fr": [
        "Le chat dort.",
        "Elle parle français tous les jours.",
        "Il faut que tu sois là.",
    ],
    "de": [
        "Das rote Buch liegt auf dem Tisch.",
        "Sie spricht Deutsch jeden Tag.",
        "Er will anfangen.",
    ],
    "it": [
        "Il gatto dorme.",
        "Lei parla italiano ogni giorno.",
        "Bisogna che tu ci sia.",
    ],
    "pt": [
        "O gato dorme.",
        "Ela fala português todos os dias.",
        "É preciso que ele venha.",
    ],
    "ru": [
        "Кошка спит.",
        "Она говорит по-русски каждый день.",
        "Он шёл домой.",
    ],
    "zh": [
        "猫睡觉。",
        "她每天说中文。",
    ],
    "ja": [
        "猫が寝ている。",
        "彼女は毎日日本語を話す。",
    ],
    "ar": [
        "القطة نائمة.",
        "هي تتحدث العربية كل يوم.",
    ],
    "he": [
        "החתול ישן.",
        "היא מדברת עברית כל יום.",
    ],
    "ko": [
        "고양이가 잔다.",
        "그녀는 매일 한국어를 말한다.",
    ],
    "la": [
        "Feles dormit.",
        "Lingua Latina difficilis est.",
    ],
    "grc": [
        "ἡ αἴλουρος καθεύδει.",
        "αὕτη λέγει ἑκάστης ἡμέρας.",
    ],
    "fa": [
        "کتاب را خواندم.",
        "من می‌روم به خانه.",
    ],
}
_FALLBACK = ["Hello world.", "The cat sat on the mat."]


def _sents(lang: str) -> list[str]:
    return _SENTENCES.get(lang, _FALLBACK)


@pytest.fixture(scope="module", params=_ALL_PLUGINS, ids=_PLUGIN_IDS)
def plugin(request):
    return request.param


# ── C1: canonical_form non-empty, no surrounding whitespace ──────────────────

class TestC1CanonicalForm:
    def test_non_empty(self, plugin) -> None:
        for sent in _sents(plugin.language_code):
            result = plugin.analyze_sentence(sent)
            for obj in result.candidates:
                assert obj.canonical_form, (
                    f"[C1] Empty canonical_form from {plugin.language_code!r} "
                    f"on {sent!r}"
                )

    def test_no_surrounding_whitespace(self, plugin) -> None:
        for sent in _sents(plugin.language_code):
            result = plugin.analyze_sentence(sent)
            for obj in result.candidates:
                cf = obj.canonical_form
                assert cf == cf.strip(), (
                    f"[C1] Whitespace-padded canonical_form {cf!r} from "
                    f"{plugin.language_code!r} on {sent!r}"
                )

    def test_no_embedded_newlines(self, plugin) -> None:
        for sent in _sents(plugin.language_code):
            result = plugin.analyze_sentence(sent)
            for obj in result.candidates:
                assert "\n" not in obj.canonical_form and "\t" not in obj.canonical_form, (
                    f"[C1] Newline/tab in canonical_form {obj.canonical_form!r} from "
                    f"{plugin.language_code!r}"
                )


# ── C2: determinism ───────────────────────────────────────────────────────────

class TestC2Determinism:
    def test_same_output_on_repeated_call(self, plugin) -> None:
        for sent in _sents(plugin.language_code):
            r1 = plugin.analyze_sentence(sent)
            r2 = plugin.analyze_sentence(sent)
            cf1 = {o.canonical_form for o in r1.candidates}
            cf2 = {o.canonical_form for o in r2.candidates}
            assert cf1 == cf2, (
                f"[C2] Non-deterministic output from {plugin.language_code!r} "
                f"on {sent!r}:\n  run1={sorted(cf1)}\n  run2={sorted(cf2)}"
            )


# ── C3: no duplicate canonical_forms within one result ───────────────────────

class TestC3Deduplication:
    def test_no_duplicates(self, plugin) -> None:
        for sent in _sents(plugin.language_code):
            result = plugin.analyze_sentence(sent)
            forms = [o.canonical_form for o in result.candidates]
            dupes = [f for f in forms if forms.count(f) > 1]
            assert not dupes, (
                f"[C3] Duplicate canonical_forms {dupes} from "
                f"{plugin.language_code!r} on {sent!r}"
            )


# ── C4: no double-tagging ─────────────────────────────────────────────────────

class TestC4NoDoubleTagging:
    """phrase_family/idiom tokens must not also appear as vocabulary candidates.
    Conjugation, agreement, and other morphological types are EXEMPT — they
    are orthogonal learning goals and co-occurrence is intentional.
    """
    _CONSUMING = frozenset({"phrase_family", "idiom"})

    def test_no_surface_in_both_phrase_and_vocabulary(self, plugin) -> None:
        for sent in _sents(plugin.language_code):
            result = plugin.analyze_sentence(sent)
            consumed: set[str] = set()
            for obj in result.candidates:
                if obj.type in self._CONSUMING and obj.surface_form:
                    for word in obj.surface_form.lower().split():
                        consumed.add(word)
            for obj in result.candidates:
                if obj.type == "vocabulary" and obj.surface_form:
                    sf = obj.surface_form.lower()
                    assert sf not in consumed, (
                        f"[C4] {obj.surface_form!r} double-tagged (vocabulary + "
                        f"{obj.type!r}) in {plugin.language_code!r} on {sent!r}"
                    )


# ── C5: confidence in range ───────────────────────────────────────────────────

class TestC5Confidence:
    def test_confidence_in_half_open_range(self, plugin) -> None:
        for sent in _sents(plugin.language_code):
            result = plugin.analyze_sentence(sent)
            for obj in result.candidates:
                if obj.confidence is not None:
                    assert 0.0 < obj.confidence <= 1.0, (
                        f"[C5] confidence={obj.confidence} not in (0.0, 1.0] "
                        f"for {obj.canonical_form!r} in {plugin.language_code!r}"
                    )


# ── C6: low-confidence objects carry a note ───────────────────────────────────

class TestC6LowConfidenceNote:
    def test_note_present_when_low(self, plugin) -> None:
        for sent in _sents(plugin.language_code):
            result = plugin.analyze_sentence(sent)
            for obj in result.candidates:
                if obj.confidence is not None and obj.confidence < 0.70:
                    note = obj.lesson_data.get("confidence_note")
                    assert isinstance(note, str) and note.strip(), (
                        f"[C6] confidence={obj.confidence:.2f} < 0.70 but "
                        f"confidence_note absent for {obj.canonical_form!r} "
                        f"in {plugin.language_code!r}"
                    )


# ── C7/C8: relation hints ─────────────────────────────────────────────────────

class TestC7C8RelationHints:
    def test_relation_type_declared(self, plugin) -> None:
        for sent in _sents(plugin.language_code):
            result = plugin.analyze_sentence(sent)
            for obj in result.candidates:
                for hint in obj.relation_hints:
                    assert hint.relation_type in VALID_RELATION_TYPES, (
                        f"[C7] Undeclared relation_type {hint.relation_type!r} on "
                        f"{obj.canonical_form!r} in {plugin.language_code!r}. "
                        f"Valid types: {sorted(VALID_RELATION_TYPES)}"
                    )

    def test_target_canonical_form_non_empty(self, plugin) -> None:
        for sent in _sents(plugin.language_code):
            result = plugin.analyze_sentence(sent)
            for obj in result.candidates:
                for hint in obj.relation_hints:
                    assert hint.target_canonical_form and hint.target_canonical_form.strip(), (
                        f"[C8] Empty target_canonical_form on {obj.canonical_form!r} "
                        f"in {plugin.language_code!r}"
                    )


# ── C9: required lesson_data keys ────────────────────────────────────────────

class TestC9LessonDataKeys:
    def test_required_keys_present(self, plugin) -> None:
        for sent in _sents(plugin.language_code):
            result = plugin.analyze_sentence(sent)
            for obj in result.candidates:
                required = REQUIRED_LESSON_KEYS.get(obj.type, frozenset())
                missing  = required - obj.lesson_data.keys()
                assert not missing, (
                    f"[C9] type={obj.type!r} missing keys {sorted(missing)} "
                    f"for {obj.canonical_form!r} in {plugin.language_code!r} "
                    f"on {sent!r}"
                )


# ── C10: idiom_detection capability gate ─────────────────────────────────────

class TestC10IdiomCapability:
    def test_no_idiom_when_detection_false(self, plugin) -> None:
        if plugin.capabilities.idiom_detection:
            pytest.skip(f"{plugin.language_code}: idiom_detection=True")
        for sent in _sents(plugin.language_code):
            result = plugin.analyze_sentence(sent)
            idioms = [o for o in result.candidates if o.type == "idiom"]
            assert not idioms, (
                f"[C10] type='idiom' emitted but idiom_detection=False "
                f"in {plugin.language_code!r} on {sent!r}"
            )


# ── C11: morphology_depth capability gate ────────────────────────────────────

class TestC11MorphologyCapability:
    def test_no_morphology_when_depth_none(self, plugin) -> None:
        if plugin.capabilities.morphology_depth != "none":
            pytest.skip(f"{plugin.language_code}: morphology_depth != none")
        morph_types = {"conjugation", "agreement", "case_agreement"}
        for sent in _sents(plugin.language_code):
            result = plugin.analyze_sentence(sent)
            bad = [o for o in result.candidates if o.type in morph_types]
            assert not bad, (
                f"[C11] morphological type(s) emitted but morphology_depth='none' "
                f"in {plugin.language_code!r}: {[o.type for o in bad]}"
            )


# ── C12: phrase_families capability gate ─────────────────────────────────────

class TestC12PhraseFamiliesCapability:
    def test_no_phrase_family_when_capability_none(self, plugin) -> None:
        nc = plugin.capabilities.nuance_capabilities
        if nc is not None and nc.phrase_families != "none":
            pytest.skip(f"{plugin.language_code}: phrase_families={nc.phrase_families!r}")
        for sent in _sents(plugin.language_code):
            result = plugin.analyze_sentence(sent)
            pf = [o for o in result.candidates if o.type == "phrase_family"]
            assert not pf, (
                f"[C12] type='phrase_family' emitted but phrase_families='none' "
                f"in {plugin.language_code!r} on {sent!r}"
            )


# ── C13: text preservation ────────────────────────────────────────────────────

class TestC13TextPreservation:
    def test_result_text_equals_input(self, plugin) -> None:
        for sent in _sents(plugin.language_code):
            result = plugin.analyze_sentence(sent)
            assert result.text == sent, (
                f"[C13] result.text mutated in {plugin.language_code!r}: "
                f"expected {sent!r}, got {result.text!r}"
            )


# ── C14/C15: protocol attribute consistency ───────────────────────────────────

class TestC14C15ProtocolAttributes:
    def test_language_code_lowercase(self, plugin) -> None:
        assert plugin.language_code == plugin.language_code.lower(), (
            f"[C14] language_code {plugin.language_code!r} not lowercase"
        )

    def test_language_code_matches_capabilities_code(self, plugin) -> None:
        assert plugin.language_code == plugin.capabilities.code, (
            f"[C14] language_code {plugin.language_code!r} != "
            f"capabilities.code {plugin.capabilities.code!r}"
        )

    def test_direction_matches_capabilities(self, plugin) -> None:
        assert plugin.direction == plugin.capabilities.direction, (
            f"[C15] plugin.direction={plugin.direction!r} != "
            f"capabilities.direction={plugin.capabilities.direction!r}"
        )


# ── Full contract via validate_result() ──────────────────────────────────────

class TestFullContractValidator:
    """Run the entire validate_result() function, which covers all C1–C15 rules."""

    def test_no_violations(self, plugin) -> None:
        for sent in _sents(plugin.language_code):
            result = plugin.analyze_sentence(sent)
            report = validate_result(result, plugin, input_sentence=sent)
            assert report.ok, (
                f"Contract violations for {plugin.language_code!r} on {sent!r}:\n{report}"
            )


# ── ContractReport unit tests ─────────────────────────────────────────────────

class TestContractReport:
    def test_ok_when_no_violations(self) -> None:
        assert ContractReport().ok

    def test_not_ok_when_violation_present(self) -> None:
        r = ContractReport()
        r.violations.append(ContractViolation("C1", "test"))
        assert not r.ok

    def test_str_shows_rule_and_message(self) -> None:
        r = ContractReport()
        r.violations.append(ContractViolation("C3", "Duplicate", object_index=2, canonical_form="cat"))
        assert "C3" in str(r)
        assert "Duplicate" in str(r)

    def test_str_ok_when_clean(self) -> None:
        assert str(ContractReport()) == "OK"


# ── validate_result unit tests (compliant + failing examples) ─────────────────

class _GoodPlugin:
    """Minimal compliant plugin — satisfies every invariant."""
    language_code = "x-good"
    direction     = "ltr"

    class capabilities:
        code                 = "x-good"
        direction            = "ltr"
        idiom_detection      = False
        morphology_depth     = "none"
        nuance_capabilities  = None


class _BadPlugin:
    """Plugin that violates C1, C3, C5, C7, C8, C9, C10, C11, C13."""
    language_code = "x-bad"
    direction     = "ltr"

    class capabilities:
        code                 = "x-bad"
        direction            = "ltr"
        idiom_detection      = False    # C10: plugin still emits "idiom"
        morphology_depth     = "none"   # C11: plugin still emits "conjugation"
        nuance_capabilities  = None


def _good_result(sent: str) -> CandidateSentenceResult:
    return CandidateSentenceResult(
        text=sent,
        candidates=[
            CandidateObject(
                canonical_form="cat",
                type="vocabulary",
                label="cat",
                surface_form="cat",
                lesson_data={"lemma": "cat"},
                confidence=0.85,
            )
        ],
    )


def _bad_result(sent: str) -> CandidateSentenceResult:
    return CandidateSentenceResult(
        text=sent.upper(),   # C13: mutated
        candidates=[
            CandidateObject(
                canonical_form=" cat ",   # C1: surrounding whitespace
                type="idiom",             # C10: idiom_detection=False
                label="cat",
                lesson_data={},           # C9: idiom requires "meaning"
                confidence=0.0,           # C5: must be > 0.0 or None
                relation_hints=[
                    RelationHint(
                        relation_type="motion_pair",   # C7: undeclared
                        target_canonical_form="",      # C8: empty
                        target_type="vocabulary",
                    ),
                ],
            ),
            CandidateObject(
                canonical_form=" cat ",   # C3: duplicate canonical_form
                type="conjugation",       # C11: morphology_depth="none"
                label="cat",
                lesson_data={},           # C9: conjugation requires "tense", "mood"
                confidence=None,
            ),
        ],
    )


class TestCompliantPlugin:
    def test_good_plugin_no_violations(self) -> None:
        sent   = "The cat sleeps."
        result = _good_result(sent)
        report = validate_result(result, _GoodPlugin(), input_sentence=sent)
        assert report.ok, f"Unexpected violations:\n{report}"


class TestFailingPlugin:
    def setup_method(self) -> None:
        sent        = "The cat sleeps."
        result      = _bad_result(sent)
        self.report = validate_result(result, _BadPlugin(), input_sentence=sent)
        self.rules  = {v.rule for v in self.report.violations}

    def test_has_violations(self) -> None:
        assert not self.report.ok

    def test_catches_c1_whitespace(self) -> None:
        assert "C1" in self.rules, f"C1 not in {self.rules}"

    def test_catches_c3_duplicate(self) -> None:
        assert "C3" in self.rules, f"C3 not in {self.rules}"

    def test_catches_c5_zero_confidence(self) -> None:
        assert "C5" in self.rules, f"C5 not in {self.rules}"

    def test_catches_c7_undeclared_relation_type(self) -> None:
        assert "C7" in self.rules, f"C7 not in {self.rules}"

    def test_catches_c8_empty_target(self) -> None:
        assert "C8" in self.rules, f"C8 not in {self.rules}"

    def test_catches_c9_missing_lesson_keys(self) -> None:
        assert "C9" in self.rules, f"C9 not in {self.rules}"

    def test_catches_c10_idiom_when_detection_false(self) -> None:
        assert "C10" in self.rules, f"C10 not in {self.rules}"

    def test_catches_c11_conjugation_when_morphology_none(self) -> None:
        assert "C11" in self.rules, f"C11 not in {self.rules}"

    def test_catches_c13_text_mutated(self) -> None:
        assert "C13" in self.rules, f"C13 not in {self.rules}"
