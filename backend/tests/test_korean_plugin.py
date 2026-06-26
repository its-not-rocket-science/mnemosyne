"""Tests for the Korean plugin (backend/plugins/korean.py).

Coverage goals
──────────────
Always-run (no NLP dependency):
- Capability declarations match contract
- Protocol compliance (lesson_store, analyze_text, etc.)
- Heuristic fallback path: Hangul → word:{surface}, confidence=0.5,
  confidence_note present, no _raw_tag leak
- Sentence splitting
- Deduplication in both paths
- canonical_object_id UUID stability for Hangul forms
- Homograph namespace collision avoidance (noun:일 ≠ verb:일하다)
- Cross-language UUID distinctness (ko ≠ ja for same Hangul)
- Lesson engine integration (vocabulary + dictionary modes)

kiwipiepy-required (skipped when not installed):
- Verb lemma construction: surface stem → verb:{stem}다
- Noun/adj/adv extraction with correct canonical prefixes
- XSV compound detection: NNG + XSV → verb:{noun}하다
- PROPN confidence ≤ 0.65
- _raw_tag not present in final lesson_data
- Particle/suffix skip tags produce no candidates
"""
from __future__ import annotations

import uuid

import pytest

from backend.parsing.canonical import canonical_object_id
from backend.plugins.korean import KoreanPlugin, create_plugin
from backend.schemas.language import LanguageCapabilities
from backend.schemas.parse import CandidateObject, CandidateSentenceResult


# ── skip guard ────────────────────────────────────────────────────────────────

def _kiwi_available() -> bool:
    try:
        from kiwipiepy import Kiwi  # noqa: PLC0415
        Kiwi()
        return True
    except Exception:
        return False


_KIWI = _kiwi_available()
kiwi_required = pytest.mark.skipif(
    not _KIWI,
    reason="kiwipiepy not installed; run: pip install kiwipiepy",
)


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def plugin() -> KoreanPlugin:
    return create_plugin()


# ── helpers ───────────────────────────────────────────────────────────────────

def objects_of(result: CandidateSentenceResult, kind: str) -> list[CandidateObject]:
    return [o for o in result.candidates if o.type == kind]


def canonical_forms(result: CandidateSentenceResult) -> list[str]:
    return [o.canonical_form for o in result.candidates]


def has_no_raw_tag(result: CandidateSentenceResult) -> bool:
    return all("_raw_tag" not in o.lesson_data for o in result.candidates)


# ── capability declarations ───────────────────────────────────────────────────

class TestCapabilities:
    def test_language_code(self, plugin: KoreanPlugin) -> None:
        assert plugin.language_code == "ko"

    def test_display_name(self, plugin: KoreanPlugin) -> None:
        assert "Korean" in plugin.display_name

    def test_direction_ltr(self, plugin: KoreanPlugin) -> None:
        assert plugin.direction == "ltr"

    def test_script_family_other(self, plugin: KoreanPlugin) -> None:
        assert plugin.capabilities.script_family == "other"

    def test_tokenization_mode_whitespace(self, plugin: KoreanPlugin) -> None:
        assert plugin.capabilities.tokenization_mode == "whitespace"

    def test_morphology_depth_rich(self, plugin: KoreanPlugin) -> None:
        assert plugin.capabilities.morphology_depth == "rich"

    def test_lesson_modes_vocabulary(self, plugin: KoreanPlugin) -> None:
        assert "vocabulary" in plugin.capabilities.lesson_modes_supported

    def test_lesson_modes_dictionary(self, plugin: KoreanPlugin) -> None:
        assert "dictionary" in plugin.capabilities.lesson_modes_supported

    def test_lesson_modes_morphology(self, plugin: KoreanPlugin) -> None:
        assert "morphology" in plugin.capabilities.lesson_modes_supported

    def test_analysis_depth_full(self, plugin: KoreanPlugin) -> None:
        assert plugin.capabilities.analysis_depth == "full"

    def test_tts_lang_tag(self, plugin: KoreanPlugin) -> None:
        assert plugin.capabilities.tts_lang_tag == "ko"

    def test_no_transliteration_scheme(self, plugin: KoreanPlugin) -> None:
        assert plugin.capabilities.transliteration_scheme is None

    def test_syntax_support_false(self, plugin: KoreanPlugin) -> None:
        assert plugin.capabilities.syntax_support is False

    def test_idiom_detection_false(self, plugin: KoreanPlugin) -> None:
        assert plugin.capabilities.idiom_detection is False

    def test_capabilities_type(self, plugin: KoreanPlugin) -> None:
        assert isinstance(plugin.capabilities, LanguageCapabilities)

    def test_capabilities_code_matches_language_code(self, plugin: KoreanPlugin) -> None:
        assert plugin.capabilities.code == plugin.language_code


# ── protocol compliance ───────────────────────────────────────────────────────

class TestProtocol:
    def test_has_lesson_store(self, plugin: KoreanPlugin) -> None:
        assert isinstance(plugin.lesson_store, dict)

    def test_analyze_text_returns_list(self, plugin: KoreanPlugin) -> None:
        results = plugin.analyze_text("고양이가 잔다.")
        assert isinstance(results, list)

    def test_analyze_sentence_returns_result(self, plugin: KoreanPlugin) -> None:
        result = plugin.analyze_sentence("고양이가 잔다.")
        assert isinstance(result, CandidateSentenceResult)

    def test_split_sentences_returns_list(self, plugin: KoreanPlugin) -> None:
        sents = plugin.split_sentences("고양이가 잔다. 개가 짖는다.")
        assert isinstance(sents, list)

    def test_get_lesson_returns_none_for_unknown(self, plugin: KoreanPlugin) -> None:
        assert plugin.get_lesson("does-not-exist") is None

    def test_analyze_text_consistent_with_analyze_sentence(self, plugin: KoreanPlugin) -> None:
        text = "고양이가 잔다. 개가 짖는다."
        multi = plugin.analyze_text(text)
        sents = plugin.split_sentences(text)
        singles = [plugin.analyze_sentence(s) for s in sents]
        assert len(multi) == len(singles)
        for m, s in zip(multi, singles):
            assert m.text == s.text
            assert set(canonical_forms(m)) == set(canonical_forms(s))


# ── sentence splitting ────────────────────────────────────────────────────────

class TestSentenceSplitting:
    def test_splits_on_period(self, plugin: KoreanPlugin) -> None:
        sents = plugin.split_sentences("고양이가 잔다. 개가 짖는다.")
        assert len(sents) >= 2

    def test_splits_on_exclamation(self, plugin: KoreanPlugin) -> None:
        sents = plugin.split_sentences("안녕하세요! 잘 지내세요.")
        assert len(sents) >= 2

    def test_splits_on_question_mark(self, plugin: KoreanPlugin) -> None:
        sents = plugin.split_sentences("어떻게 지내세요? 잘 지내요.")
        assert len(sents) >= 2

    def test_empty_returns_empty(self, plugin: KoreanPlugin) -> None:
        assert plugin.split_sentences("") == []

    def test_sentences_are_non_empty_strings(self, plugin: KoreanPlugin) -> None:
        sents = plugin.split_sentences("고양이가 잔다. 개가 짖는다.")
        assert all(s.strip() for s in sents)

    def test_sentence_text_preserved_in_result(self, plugin: KoreanPlugin) -> None:
        sentence = "고양이가 잔다."
        result = plugin.analyze_sentence(sentence)
        assert result.text == sentence

    def test_single_sentence_analyzed(self, plugin: KoreanPlugin) -> None:
        results = plugin.analyze_text("고양이가 잔다.")
        assert len(results) >= 1


# ── heuristic fallback path (always runs) ────────────────────────────────────

class TestHeuristicFallback:
    """Force the heuristic path by patching _get_kiwi to return None."""

    @pytest.fixture()
    def heuristic_plugin(self, monkeypatch: pytest.MonkeyPatch) -> KoreanPlugin:
        import backend.plugins.korean as _ko_mod
        monkeypatch.setattr(_ko_mod, "_kiwi", None)
        p = KoreanPlugin()
        return p

    def test_hangul_extracted_as_word_prefix(
        self, heuristic_plugin: KoreanPlugin
    ) -> None:
        result = heuristic_plugin.analyze_sentence("학교에 갔어요")
        forms = [o.canonical_form for o in result.candidates if o.type == "vocabulary"]
        assert forms
        assert all(f.startswith("word:") for f in forms), (
            f"Heuristic vocabulary path must use word: prefix; got {forms}"
        )

    def test_hangul_runs_extracted(
        self, heuristic_plugin: KoreanPlugin
    ) -> None:
        result = heuristic_plugin.analyze_sentence("학교에 갔어요")
        assert len(result.candidates) >= 1

    def test_confidence_is_0_5(
        self, heuristic_plugin: KoreanPlugin
    ) -> None:
        result = heuristic_plugin.analyze_sentence("학교에 갔어요")
        for obj in objects_of(result, "vocabulary"):
            assert obj.confidence == 0.50

    def test_confidence_note_present(
        self, heuristic_plugin: KoreanPlugin
    ) -> None:
        result = heuristic_plugin.analyze_sentence("학교에 갔어요")
        for obj in objects_of(result, "vocabulary"):
            assert "confidence_note" in obj.lesson_data
            assert isinstance(obj.lesson_data["confidence_note"], str)
            assert len(obj.lesson_data["confidence_note"]) > 0

    def test_confidence_note_mentions_kiwipiepy(
        self, heuristic_plugin: KoreanPlugin
    ) -> None:
        result = heuristic_plugin.analyze_sentence("학교에 갔어요")
        for obj in objects_of(result, "vocabulary"):
            note = obj.lesson_data["confidence_note"]
            assert "kiwipiepy" in note.lower()

    def test_no_raw_tag_in_lesson_data(
        self, heuristic_plugin: KoreanPlugin
    ) -> None:
        result = heuristic_plugin.analyze_sentence("학교에 갔어요")
        assert has_no_raw_tag(result)

    def test_deduplication_same_token(
        self, heuristic_plugin: KoreanPlugin
    ) -> None:
        result = heuristic_plugin.analyze_sentence("학교 학교 학교")
        forms = canonical_forms(result)
        assert len(forms) == len(set(forms))
        assert forms.count("word:학교") == 1

    def test_latin_text_produces_no_candidates(
        self, heuristic_plugin: KoreanPlugin
    ) -> None:
        result = heuristic_plugin.analyze_sentence("Hello world")
        assert result.candidates == []

    def test_punctuation_only_produces_no_candidates(
        self, heuristic_plugin: KoreanPlugin
    ) -> None:
        result = heuristic_plugin.analyze_sentence(".,!?")
        assert result.candidates == []

    def test_all_types_are_vocabulary(
        self, heuristic_plugin: KoreanPlugin
    ) -> None:
        result = heuristic_plugin.analyze_sentence("고양이가 잔다")
        assert objects_of(result, "vocabulary")
        assert all(obj.type in {"vocabulary", "nuance"} for obj in result.candidates)

    def test_lemma_key_present(
        self, heuristic_plugin: KoreanPlugin
    ) -> None:
        result = heuristic_plugin.analyze_sentence("학교에 갔어요")
        for obj in objects_of(result, "vocabulary"):
            assert "lemma" in obj.lesson_data

    def test_idempotent_analysis(
        self, heuristic_plugin: KoreanPlugin
    ) -> None:
        sentence = "고양이가 잔다."
        r1 = heuristic_plugin.analyze_sentence(sentence)
        r2 = heuristic_plugin.analyze_sentence(sentence)
        assert canonical_forms(r1) == canonical_forms(r2)


# ── kiwipiepy path ────────────────────────────────────────────────────────────

class TestKiwiPath:
    @kiwi_required
    def test_verb_canonical_form_prefix(self, plugin: KoreanPlugin) -> None:
        result = plugin.analyze_sentence("고양이가 잔다.")
        forms = canonical_forms(result)
        assert any(f.startswith("verb:") for f in forms), (
            f"Expected a verb: form; got {forms}"
        )

    @kiwi_required
    def test_verb_lemma_ends_in_da(self, plugin: KoreanPlugin) -> None:
        result = plugin.analyze_sentence("고양이가 잔다.")
        verbs = [o for o in result.candidates if o.canonical_form.startswith("verb:")]
        for v in verbs:
            assert v.lesson_data.get("lemma", "").endswith("다"), (
                f"Verb lemma must end in 다; got {v.lesson_data.get('lemma')!r}"
            )

    @kiwi_required
    def test_noun_canonical_form_prefix(self, plugin: KoreanPlugin) -> None:
        result = plugin.analyze_sentence("학교에 갔습니다.")
        forms = canonical_forms(result)
        assert any(f.startswith("noun:") for f in forms), (
            f"Expected a noun: form; got {forms}"
        )

    @kiwi_required
    def test_adj_canonical_form_prefix(self, plugin: KoreanPlugin) -> None:
        result = plugin.analyze_sentence("날씨가 좋다.")
        forms = canonical_forms(result)
        assert any(f.startswith("adj:") or f.startswith("verb:") for f in forms), (
            f"Expected adj: or verb: form; got {forms}"
        )

    @kiwi_required
    def test_no_raw_tag_in_lesson_data(self, plugin: KoreanPlugin) -> None:
        for sentence in [
            "고양이가 잔다.",
            "학교에 갔습니다.",
            "날씨가 좋다.",
            "그는 공부합니다.",
        ]:
            result = plugin.analyze_sentence(sentence)
            assert has_no_raw_tag(result), (
                f"_raw_tag leaked into lesson_data for sentence {sentence!r}"
            )

    @kiwi_required
    def test_no_duplicates(self, plugin: KoreanPlugin) -> None:
        result = plugin.analyze_sentence("고양이 고양이 고양이")
        forms = canonical_forms(result)
        assert len(forms) == len(set(forms))

    @kiwi_required
    def test_all_types_are_vocabulary(self, plugin: KoreanPlugin) -> None:
        result = plugin.analyze_sentence("그녀는 매일 한국어를 말한다.")
        assert objects_of(result, "vocabulary")
        assert all(obj.type in {"vocabulary", "conjugation", "nuance"} for obj in result.candidates)

    @kiwi_required
    def test_pos_key_present(self, plugin: KoreanPlugin) -> None:
        result = plugin.analyze_sentence("고양이가 잔다.")
        for obj in objects_of(result, "vocabulary"):
            assert "pos" in obj.lesson_data

    @kiwi_required
    def test_lemma_key_present(self, plugin: KoreanPlugin) -> None:
        result = plugin.analyze_sentence("고양이가 잔다.")
        for obj in objects_of(result, "vocabulary"):
            assert "lemma" in obj.lesson_data

    @kiwi_required
    def test_confidence_in_valid_range(self, plugin: KoreanPlugin) -> None:
        result = plugin.analyze_sentence("그녀는 매일 한국어를 말한다.")
        for obj in result.candidates:
            if obj.confidence is not None:
                assert 0.0 < obj.confidence <= 1.0

    @kiwi_required
    def test_propn_confidence_at_most_0_65(self, plugin: KoreanPlugin) -> None:
        result = plugin.analyze_sentence("서울에 갔습니다.")
        propns = [o for o in result.candidates if o.lesson_data.get("pos") == "PROPN"]
        for p in propns:
            if p.confidence is not None:
                assert p.confidence <= 0.65, (
                    f"PROPN confidence must be ≤ 0.65; got {p.confidence}"
                )

    @kiwi_required
    def test_skip_tags_produce_no_candidate(self, plugin: KoreanPlugin) -> None:
        """Particles, endings, affixes must not appear as vocabulary objects."""
        result = plugin.analyze_sentence("그녀는 매일 한국어를 말한다.")
        pos_tags = {o.lesson_data.get("pos") for o in result.candidates}
        forbidden = {"ADP", "PART", "AFFIX"}
        assert not (pos_tags & forbidden), (
            f"Forbidden POS tags in vocabulary: {pos_tags & forbidden}"
        )

    @kiwi_required
    def test_kiwi_path_no_word_prefix(self, plugin: KoreanPlugin) -> None:
        """kiwipiepy path must not emit word: fallback forms."""
        result = plugin.analyze_sentence("고양이가 잔다.")
        forms = canonical_forms(result)
        assert not any(f.startswith("word:") for f in forms), (
            f"word: prefix must only appear in heuristic fallback; got {forms}"
        )


# ── XSV compound verb detection ───────────────────────────────────────────────

class TestXsvCompoundDetection:
    @kiwi_required
    def test_gongbu_hada_compound(self, plugin: KoreanPlugin) -> None:
        """공부(NNG) + 하(XSV) must produce verb:공부하다, not noun:공부."""
        result = plugin.analyze_sentence("나는 매일 공부합니다.")
        forms = canonical_forms(result)
        assert "verb:공부하다" in forms, (
            f"Expected verb:공부하다 from XSV compound; got {forms}"
        )

    @kiwi_required
    def test_compound_no_bare_noun_stem(self, plugin: KoreanPlugin) -> None:
        """When XSV compound is detected, the bare NNG stem must be absorbed."""
        result = plugin.analyze_sentence("나는 매일 공부합니다.")
        forms = canonical_forms(result)
        assert "noun:공부" not in forms, (
            f"Bare noun:공부 should be absorbed into compound verb; got {forms}"
        )

    @kiwi_required
    def test_compound_verb_has_verb_pos(self, plugin: KoreanPlugin) -> None:
        result = plugin.analyze_sentence("나는 매일 공부합니다.")
        compounds = [
            o for o in result.candidates if o.canonical_form == "verb:공부하다"
        ]
        assert compounds, "verb:공부하다 candidate not found"
        assert compounds[0].lesson_data.get("pos") == "VERB"

    @kiwi_required
    def test_compound_no_raw_tag_leaked(self, plugin: KoreanPlugin) -> None:
        result = plugin.analyze_sentence("나는 매일 공부합니다.")
        assert has_no_raw_tag(result)


# ── homograph namespace collision avoidance ───────────────────────────────────

class TestHomographAvoidance:
    def test_noun_il_differs_from_verb_ilhada(self) -> None:
        """noun:일 and verb:일하다 must produce distinct UUIDs."""
        noun_id = canonical_object_id("ko", "vocabulary", "noun:일")
        verb_id = canonical_object_id("ko", "vocabulary", "verb:일하다")
        assert noun_id != verb_id, (
            "Homograph collision: noun:일 and verb:일하다 share a UUID"
        )

    def test_noun_and_verb_prefixes_distinct_for_same_stem(self) -> None:
        """Any noun:{x} and verb:{x}다 that share a stem must not collide."""
        noun_id = canonical_object_id("ko", "vocabulary", "noun:사랑")
        verb_id = canonical_object_id("ko", "vocabulary", "verb:사랑하다")
        assert noun_id != verb_id

    def test_adj_prefix_distinct_from_noun(self) -> None:
        adj_id  = canonical_object_id("ko", "vocabulary", "adj:예쁘다")
        noun_id = canonical_object_id("ko", "vocabulary", "noun:예쁘다")
        assert adj_id != noun_id

    def test_adv_prefix_distinct_from_noun(self) -> None:
        adv_id  = canonical_object_id("ko", "vocabulary", "adv:빨리")
        noun_id = canonical_object_id("ko", "vocabulary", "noun:빨리")
        assert adv_id != noun_id


# ── UUID stability for Hangul canonical forms ─────────────────────────────────

class TestUuidStability:
    def test_hangul_uuid_is_deterministic(self) -> None:
        id1 = canonical_object_id("ko", "vocabulary", "noun:학교")
        id2 = canonical_object_id("ko", "vocabulary", "noun:학교")
        assert id1 == id2

    def test_hangul_uuid_is_v5(self) -> None:
        raw = canonical_object_id("ko", "vocabulary", "verb:먹다")
        assert uuid.UUID(raw).version == 5

    def test_different_forms_produce_different_uuids(self) -> None:
        ids = [
            canonical_object_id("ko", "vocabulary", f)
            for f in ["noun:학교", "verb:먹다", "adj:예쁘다", "adv:빨리", "word:갔어요"]
        ]
        assert len(ids) == len(set(ids)), "Collision among Korean canonical UUIDs"

    def test_korean_and_japanese_same_hangul_differ(self) -> None:
        ko_id = canonical_object_id("ko", "vocabulary", "noun:학교")
        ja_id = canonical_object_id("ja", "vocabulary", "noun:학교")
        assert ko_id != ja_id

    def test_korean_and_chinese_same_form_differ(self) -> None:
        ko_id = canonical_object_id("ko", "vocabulary", "noun:서울")
        zh_id = canonical_object_id("zh", "vocabulary", "noun:서울")
        assert ko_id != zh_id


# ── lesson store ──────────────────────────────────────────────────────────────

class TestLessonStore:
    def test_missing_id_returns_none(self, plugin: KoreanPlugin) -> None:
        assert plugin.get_lesson("no-such-uuid") is None

    def test_stored_object_is_retrievable(self, plugin: KoreanPlugin) -> None:
        obj = CandidateObject(
            canonical_form="noun:학교",
            surface_form="학교에",
            type="vocabulary",
            label="학교",
            lesson_data={"lemma": "학교", "pos": "NOUN"},
        )
        plugin.lesson_store["ko-test-001"] = obj
        assert plugin.get_lesson("ko-test-001") is obj

    def test_lesson_stores_independent_across_instances(self) -> None:
        p1 = create_plugin()
        p2 = create_plugin()
        obj = CandidateObject(
            canonical_form="verb:먹다",
            type="vocabulary",
            label="먹다",
            lesson_data={},
        )
        p1.lesson_store["ko-isolated"] = obj
        assert p2.get_lesson("ko-isolated") is None


# ── multilingual architecture ─────────────────────────────────────────────────

class TestMultilingualArchitecture:
    def test_korean_registered_in_plugin_loader(self) -> None:
        from backend.parsing.plugin_loader import load_plugins
        registry = load_plugins()
        assert "ko" in registry.all()

    def test_korean_capabilities_in_registry(self) -> None:
        from backend.parsing.plugin_loader import load_plugins
        registry = load_plugins()
        caps = registry.supported_languages()
        assert "ko" in caps
        assert caps["ko"].direction == "ltr"

    def test_korean_not_rtl(self) -> None:
        from backend.parsing.plugin_loader import load_plugins
        registry = load_plugins()
        caps = registry.supported_languages()
        assert caps["ko"].direction != "rtl"

    def test_korean_and_japanese_ids_differ(self) -> None:
        ko_id = canonical_object_id("ko", "vocabulary", "noun:사랑")
        ja_id = canonical_object_id("ja", "vocabulary", "noun:사랑")
        assert ko_id != ja_id


# ── lesson engine integration ─────────────────────────────────────────────────

class TestLessonEngineIntegration:
    def test_build_vocabulary_lesson(self) -> None:
        from backend.lesson.generators import build_lesson
        from backend.lesson.context import LessonContext

        ctx = LessonContext.from_capabilities(KoreanPlugin.capabilities)
        lesson = build_lesson(
            object_id=canonical_object_id("ko", "vocabulary", "noun:학교"),
            obj_type="vocabulary",
            canonical_form="noun:학교",
            display_label="학교",
            lesson_data={"lemma": "학교", "pos": "NOUN"},
            lesson_mode="vocabulary",
            context=ctx,
        )
        assert lesson.language_code == "ko"
        assert lesson.script_direction == "ltr"
        assert lesson.lesson_mode == "vocabulary"

    def test_build_dictionary_lesson(self) -> None:
        from backend.lesson.generators import build_lesson
        from backend.lesson.context import LessonContext

        ctx = LessonContext.from_capabilities(KoreanPlugin.capabilities)
        lesson = build_lesson(
            object_id=canonical_object_id("ko", "vocabulary", "verb:먹다"),
            obj_type="vocabulary",
            canonical_form="verb:먹다",
            display_label="먹다",
            lesson_data={"lemma": "먹다", "pos": "VERB"},
            lesson_mode="dictionary",
            context=ctx,
        )
        assert lesson.language_code == "ko"
        assert lesson.lesson_mode == "dictionary"

    def test_context_is_not_rtl(self) -> None:
        from backend.lesson.context import LessonContext
        ctx = LessonContext.from_capabilities(KoreanPlugin.capabilities)
        assert ctx.is_rtl is False

    def test_context_is_not_cjk(self) -> None:
        from backend.lesson.context import LessonContext
        ctx = LessonContext.from_capabilities(KoreanPlugin.capabilities)
        assert ctx.is_cjk is False

    def test_heuristic_roundtrip_to_lesson(self, plugin: KoreanPlugin) -> None:
        from backend.lesson.generators import build_lesson
        from backend.lesson.context import LessonContext

        with pytest.MonkeyPatch().context() as mp:
            import backend.plugins.korean as _ko_mod
            mp.setattr(_ko_mod, "_kiwi", None)
            heuristic = KoreanPlugin()
            result = heuristic.analyze_sentence("학교")
            assert result.candidates

        c = result.candidates[0]
        oid = canonical_object_id("ko", c.type, c.canonical_form)
        ctx = LessonContext.from_capabilities(KoreanPlugin.capabilities)
        lesson = build_lesson(
            object_id=oid,
            obj_type=c.type,
            canonical_form=c.canonical_form,
            display_label=c.label,
            lesson_data=c.lesson_data,
            lesson_mode="dictionary",
            context=ctx,
        )
        assert lesson.language_code == "ko"
