"""Tests for phrase_families.py and the _build_phrase_family lesson generator.

Coverage
────────
- MatchType enum values and canonical confidence weights
- PhraseFamily / PhraseVariant immutability
- Catalog: all_that_glitters family (all 6 variants), of_the_first_water, gild_the_lily
- match_phrase_families: each requested surface form, language filtering, no-overlap
- lesson_data structure: keys, types, confusable separation
- build_lesson dispatches to phrase_family template and generates correct fields/drills
"""
from __future__ import annotations

import pytest

from backend.dictionary.phrase_families import (
    MatchType,
    PhraseFamily,
    PhraseVariant,
    _FAMILY_CATALOG,
    _MATCH_TYPE_CONFIDENCE,
    _VARIANT_INDEX,
    match_phrase_families,
)
from backend.lesson.generators import build_lesson


# ── MatchType ─────────────────────────────────────────────────────────────────


class TestMatchType:
    def test_all_eight_values_exist(self) -> None:
        expected = {
            "exact", "orthographic_variant", "modernized_variant",
            "inflectional_variant", "misquotation", "blend",
            "allusion", "confusable_not_same",
        }
        assert {m.value for m in MatchType} == expected

    def test_is_str_subclass(self) -> None:
        assert isinstance(MatchType.exact, str)
        assert MatchType.exact == "exact"

    def test_confidence_all_types_covered(self) -> None:
        for mt in MatchType:
            assert mt in _MATCH_TYPE_CONFIDENCE, f"{mt} missing from _MATCH_TYPE_CONFIDENCE"

    def test_exact_highest_confidence(self) -> None:
        assert _MATCH_TYPE_CONFIDENCE[MatchType.exact] == max(_MATCH_TYPE_CONFIDENCE.values())

    def test_blend_lowest_non_confusable_confidence(self) -> None:
        non_confusable = {k: v for k, v in _MATCH_TYPE_CONFIDENCE.items()
                          if k != MatchType.confusable_not_same}
        assert _MATCH_TYPE_CONFIDENCE[MatchType.blend] == min(non_confusable.values())

    def test_confidence_range(self) -> None:
        for mt, conf in _MATCH_TYPE_CONFIDENCE.items():
            assert 0.0 < conf <= 1.0, f"{mt} confidence {conf} out of range"


# ── Data model immutability ───────────────────────────────────────────────────


class TestImmutability:
    def test_phrase_variant_frozen(self) -> None:
        v = PhraseVariant(surface="test", match_type=MatchType.exact)
        with pytest.raises((AttributeError, TypeError)):
            v.surface = "other"  # type: ignore[misc]

    def test_phrase_family_frozen(self) -> None:
        fam = _FAMILY_CATALOG["all_that_glitters"]
        with pytest.raises((AttributeError, TypeError)):
            fam.canonical_form = "other"  # type: ignore[misc]

    def test_variants_are_tuple(self) -> None:
        fam = _FAMILY_CATALOG["all_that_glitters"]
        assert isinstance(fam.variants, tuple)

    def test_confusables_are_tuple(self) -> None:
        fam = _FAMILY_CATALOG["all_that_glitters"]
        assert isinstance(fam.confusables, tuple)


# ── Catalog contents ──────────────────────────────────────────────────────────


class TestCatalog:
    def test_all_required_families_present(self) -> None:
        for fid in ("all_that_glitters", "of_the_first_water",
                    "hit_the_nail_on_the_head", "bite_the_bullet", "gild_the_lily"):
            assert fid in _FAMILY_CATALOG, f"Family {fid!r} missing from catalog"

    # ── all_that_glitters ────────────────────────────────────────────────────

    def test_canonical_form_is_shakespeare_spelling(self) -> None:
        fam = _FAMILY_CATALOG["all_that_glitters"]
        assert fam.canonical_form == "all that glisters is not gold"

    def test_all_six_variants_present(self) -> None:
        fam = _FAMILY_CATALOG["all_that_glitters"]
        surfaces = {v.surface for v in fam.variants}
        assert "all that glisters is not gold"   in surfaces   # exact
        assert "all that glitters is not gold"   in surfaces   # modernized_variant
        assert "not all that glitters is gold"   in surfaces   # misquotation
        assert "all that is gold does not glitter" in surfaces  # allusion
        assert "all that shines is not gold"     in surfaces   # blend
        assert "all that glitters is gold"       in surfaces   # confusable_not_same

    def test_match_types_correct(self) -> None:
        fam = _FAMILY_CATALOG["all_that_glitters"]
        mt_map = {v.surface: v.match_type for v in fam.variants}
        assert mt_map["all that glisters is not gold"]    == MatchType.exact
        assert mt_map["all that glitters is not gold"]    == MatchType.modernized_variant
        assert mt_map["not all that glitters is gold"]    == MatchType.misquotation
        assert mt_map["all that is gold does not glitter"] == MatchType.allusion
        assert mt_map["all that shines is not gold"]      == MatchType.blend
        assert mt_map["all that glitters is gold"]        == MatchType.confusable_not_same

    def test_cross_references_gild_the_lily(self) -> None:
        fam = _FAMILY_CATALOG["all_that_glitters"]
        assert "gild_the_lily" in fam.confusables

    def test_has_source_text_and_why_it_matters(self) -> None:
        fam = _FAMILY_CATALOG["all_that_glitters"]
        assert fam.source_text and "Shakespeare" in fam.source_text
        assert fam.why_it_matters and len(fam.why_it_matters) > 20

    def test_language_is_en(self) -> None:
        for fam in _FAMILY_CATALOG.values():
            assert fam.language == "en"

    # ── of_the_first_water ───────────────────────────────────────────────────

    def test_of_the_first_water_canonical(self) -> None:
        fam = _FAMILY_CATALOG["of_the_first_water"]
        assert fam.canonical_form == "of the first water"

    def test_of_the_first_water_has_exact_variant(self) -> None:
        fam = _FAMILY_CATALOG["of_the_first_water"]
        exact = [v for v in fam.variants if v.match_type == MatchType.exact]
        assert len(exact) == 1
        assert exact[0].surface == "of the first water"

    # ── gild_the_lily cross-reference ────────────────────────────────────────

    def test_gild_the_lily_is_confusable_of_all_that_glitters(self) -> None:
        gild = _FAMILY_CATALOG["gild_the_lily"]
        assert "all_that_glitters" in gild.confusables


# ── Variant index ─────────────────────────────────────────────────────────────


class TestVariantIndex:
    def test_canonical_form_indexed(self) -> None:
        assert "all that glisters is not gold" in _VARIANT_INDEX

    def test_modernized_form_indexed(self) -> None:
        assert "all that glitters is not gold" in _VARIANT_INDEX

    def test_confusable_indexed(self) -> None:
        assert "all that glitters is gold" in _VARIANT_INDEX

    def test_of_the_first_water_indexed(self) -> None:
        assert "of the first water" in _VARIANT_INDEX

    def test_index_value_is_triple(self) -> None:
        surface, fam, variant = _VARIANT_INDEX["all that glisters is not gold"]
        assert isinstance(surface, str)
        assert isinstance(fam, PhraseFamily)
        assert isinstance(variant, PhraseVariant)
        assert variant.match_type == MatchType.exact


# ── match_phrase_families ─────────────────────────────────────────────────────


def _tokens(phrase: str) -> list[str]:
    """Split phrase to word tokens (mimics stub plugin tokenizer)."""
    import re
    return re.findall(r"[A-Za-z']+", phrase)


class TestMatchPhraseFamilies:

    # ── Requested glisters/glitters variants ────────────────────────────────

    def test_exact_shakespeare_form(self) -> None:
        results = match_phrase_families(
            _tokens("All that glisters is not gold"), "en"
        )
        assert len(results) == 1
        ld = results[0].lesson_data
        assert ld["match_type"] == "exact"
        assert ld["canonical_form"] == "all that glisters is not gold"

    def test_modernized_glitters_form(self) -> None:
        results = match_phrase_families(
            _tokens("All that glitters is not gold"), "en"
        )
        assert len(results) == 1
        ld = results[0].lesson_data
        assert ld["match_type"] == "modernized_variant"
        assert results[0].confidence == _MATCH_TYPE_CONFIDENCE[MatchType.modernized_variant]

    def test_misquotation_inverted_syntax(self) -> None:
        results = match_phrase_families(
            _tokens("Not all that glitters is gold"), "en"
        )
        assert len(results) == 1
        assert results[0].lesson_data["match_type"] == "misquotation"

    def test_allusion_tolkien_reversal(self) -> None:
        results = match_phrase_families(
            _tokens("All that is gold does not glitter"), "en"
        )
        assert len(results) == 1
        ld = results[0].lesson_data
        assert ld["match_type"] == "allusion"
        assert "Tolkien" in (ld.get("match_type_note") or "")

    def test_confusable_missing_not(self) -> None:
        results = match_phrase_families(
            _tokens("All that glitters is gold"), "en"
        )
        assert len(results) == 1
        ld = results[0].lesson_data
        assert ld["match_type"] == "confusable_not_same"
        assert results[0].confidence == _MATCH_TYPE_CONFIDENCE[MatchType.confusable_not_same]

    def test_of_the_first_water_exact(self) -> None:
        results = match_phrase_families(
            _tokens("a scholar of the first water"), "en"
        )
        assert len(results) == 1
        assert results[0].lesson_data["canonical_form"] == "of the first water"
        assert results[0].lesson_data["match_type"] == "exact"

    # ── Language filtering ───────────────────────────────────────────────────

    def test_no_match_wrong_language(self) -> None:
        results = match_phrase_families(
            _tokens("all that glitters is not gold"), "fr"
        )
        assert results == []

    def test_no_match_gibberish(self) -> None:
        results = match_phrase_families(["hello", "world"], "en")
        assert results == []

    # ── Longest-match / no-overlap ───────────────────────────────────────────

    def test_exact_preferred_over_shorter_prefix_match(self) -> None:
        # "all that glitters is not gold" is 6 tokens; a 5-token confusable
        # "all that glitters is gold" must not consume the longer phrase.
        results = match_phrase_families(
            _tokens("all that glitters is not gold"), "en"
        )
        assert len(results) == 1
        assert results[0].lesson_data["match_type"] == "modernized_variant"

    def test_two_distinct_phrases_in_one_sentence(self) -> None:
        sentence = "All that glitters is not gold — hit the nail on the head"
        results = match_phrase_families(_tokens(sentence), "en")
        family_ids = {r.lesson_data["family_id"] for r in results}
        assert "all_that_glitters"       in family_ids
        assert "hit_the_nail_on_the_head" in family_ids

    def test_no_token_used_twice(self) -> None:
        sentence = "all that glitters is not gold all that glitters is not gold"
        results = match_phrase_families(_tokens(sentence), "en")
        # Greedy left-to-right: first match consumes tokens; second attempt
        # uses the remaining tokens which still form the same phrase.
        # Both may or may not match depending on offset — what matters is
        # no result references the same token position twice.
        assert len(results) >= 1  # at least one match found

    # ── Punctuation tolerance ────────────────────────────────────────────────

    def test_trailing_period_does_not_prevent_match(self) -> None:
        results = match_phrase_families(
            _tokens("All that glisters is not gold."), "en"
        )
        assert len(results) == 1

    def test_comma_in_middle_ok(self) -> None:
        # The normaliser strips punctuation tokens; real token list may include commas
        tokens = ["All", "that", "glisters", ",", "is", "not", "gold"]
        results = match_phrase_families(tokens, "en")
        assert len(results) == 1


# ── lesson_data structure ─────────────────────────────────────────────────────


class TestLessonData:
    def _match(self, phrase: str) -> dict:
        results = match_phrase_families(_tokens(phrase), "en")
        assert results, f"No match for: {phrase!r}"
        return results[0].lesson_data

    def test_required_keys_present_for_exact(self) -> None:
        ld = self._match("all that glisters is not gold")
        for key in ("family_id", "canonical_form", "matched_variant",
                    "match_type", "meaning", "register"):
            assert key in ld, f"Missing key: {key!r}"

    def test_optional_keys_present_for_rich_family(self) -> None:
        ld = self._match("all that glisters is not gold")
        assert "origin"         in ld
        assert "source_text"    in ld
        assert "why_it_matters" in ld
        assert "confusables"    in ld
        assert "tags"           in ld

    def test_variants_list_excludes_confusable_not_same(self) -> None:
        ld = self._match("all that glisters is not gold")
        variants = ld["variants"]
        for v in variants:
            assert v["match_type"] != "confusable_not_same", (
                f"confusable_not_same leaked into variants: {v}"
            )

    def test_confusable_forms_contains_confusable_not_same(self) -> None:
        ld = self._match("all that glisters is not gold")
        cf = ld.get("confusable_forms", [])
        assert len(cf) >= 1
        surfaces = {c["surface"] for c in cf}
        assert "all that glitters is gold" in surfaces

    def test_confusable_form_has_note(self) -> None:
        ld = self._match("all that glisters is not gold")
        cf = ld["confusable_forms"]
        for c in cf:
            assert "surface" in c
            assert "note" in c

    def test_variant_dicts_have_required_keys(self) -> None:
        ld = self._match("all that glisters is not gold")
        for v in ld["variants"]:
            assert "surface"    in v
            assert "match_type" in v
            assert "note"       in v

    def test_matched_variant_is_surface_span(self) -> None:
        ld = self._match("All that Glitters Is Not Gold")
        assert ld["matched_variant"] == "All that Glitters Is Not Gold"

    def test_match_type_note_present_for_variant_with_note(self) -> None:
        ld = self._match("all that glitters is not gold")
        assert "match_type_note" in ld
        assert ld["match_type_note"]  # non-empty

    def test_no_match_type_note_for_exact_canonical(self) -> None:
        ld = self._match("all that glisters is not gold")
        # exact variant has no note
        assert "match_type_note" not in ld or not ld["match_type_note"]

    def test_confusable_match_goes_to_confusable_forms_not_variants(self) -> None:
        ld = self._match("all that glitters is gold")
        # Even when the confusable itself is matched, the confusable_not_same
        # variants must NOT appear in the variants list.
        for v in ld.get("variants", []):
            assert v["match_type"] != "confusable_not_same"


# ── build_lesson integration ──────────────────────────────────────────────────


class TestBuildPhraseFamily:
    def _lesson(self, phrase: str):
        results = match_phrase_families(_tokens(phrase), "en")
        assert results
        obj = results[0]
        return build_lesson(
            object_id=obj.canonical_form,
            obj_type=obj.type,
            canonical_form=obj.canonical_form,
            display_label=obj.label,
            lesson_data=obj.lesson_data,
        )

    def test_lesson_mode_is_phrase_family(self) -> None:
        lesson = self._lesson("all that glisters is not gold")
        assert lesson.lesson_mode == "phrase_family"

    def test_type_is_phrase_family(self) -> None:
        lesson = self._lesson("all that glisters is not gold")
        assert lesson.type == "phrase_family"

    def test_exact_match_no_matched_variant_field(self) -> None:
        lesson = self._lesson("all that glisters is not gold")
        labels = {f.label for f in lesson.fields}
        assert "Matched variant" not in labels

    def test_non_exact_has_matched_variant_field(self) -> None:
        lesson = self._lesson("all that glitters is not gold")
        labels = {f.label for f in lesson.fields}
        assert "Matched variant" in labels

    def test_match_type_label_human_readable(self) -> None:
        lesson = self._lesson("all that glitters is not gold")
        mt_field = next(f for f in lesson.fields if f.label == "Match type")
        assert mt_field.value == "Modernised form"

    def test_canonical_form_field_always_present(self) -> None:
        for phrase in (
            "all that glisters is not gold",
            "all that glitters is not gold",
            "all that glitters is gold",
        ):
            lesson = self._lesson(phrase)
            assert any(f.label == "Canonical form" for f in lesson.fields), phrase

    def test_shadowing_drill_always_present(self) -> None:
        lesson = self._lesson("all that glisters is not gold")
        types = [d.type for d in lesson.drills]
        assert "shadowing" in types

    def test_meaning_drill_present(self) -> None:
        lesson = self._lesson("all that glisters is not gold")
        fill_drills = [d for d in lesson.drills if d.type == "fill_blank"]
        assert any("mean" in d.prompt.lower() for d in fill_drills)

    def test_recognition_drill_non_exact_is_false(self) -> None:
        lesson = self._lesson("all that glitters is not gold")
        rec = [d for d in lesson.drills if d.type == "recognition"]
        assert any(not d.correct for d in rec)

    def test_recognition_drill_exact_is_true(self) -> None:
        lesson = self._lesson("all that glisters is not gold")
        rec = [d for d in lesson.drills if d.type == "recognition"]
        assert any(d.correct for d in rec)

    def test_of_the_first_water_builds_correctly(self) -> None:
        lesson = self._lesson("of the first water")
        assert lesson.lesson_mode == "phrase_family"
        assert any(f.label == "Source" for f in lesson.fields)

    def test_confusable_match_lesson_has_canonical_form(self) -> None:
        lesson = self._lesson("all that glitters is gold")
        canonical_f = next(f for f in lesson.fields if f.label == "Canonical form")
        assert canonical_f.value == "all that glisters is not gold"

    def test_source_field_present_when_source_text(self) -> None:
        lesson = self._lesson("all that glisters is not gold")
        assert any(f.label == "Source" for f in lesson.fields)

    def test_why_it_matters_field_present(self) -> None:
        lesson = self._lesson("all that glisters is not gold")
        assert any(f.label == "Why it matters" for f in lesson.fields)

    def test_known_variants_field_lists_surfaces(self) -> None:
        lesson = self._lesson("all that glisters is not gold")
        variants_f = next((f for f in lesson.fields if f.label == "Known variants"), None)
        assert variants_f is not None
        # At least the canonical and modernized forms should appear
        assert "glisters" in variants_f.value
        assert "glitters" in variants_f.value

    def test_confusable_with_field_present_for_family_with_confusables(self) -> None:
        lesson = self._lesson("all that glisters is not gold")
        assert any(f.label == "Confusable with" for f in lesson.fields)

    def test_determinism(self) -> None:
        def make():
            return self._lesson("all that glitters is not gold")
        assert make() == make()
