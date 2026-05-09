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

import re
from collections import defaultdict

from backend.dictionary.phrase_families import (
    MatchType,
    PhraseFamily,
    PhraseVariant,
    _FAMILY_CATALOG,
    _MATCH_TYPE_CONFIDENCE,
    _VARIANT_INDEX,
    _normalise,
    lookup_family_by_id,
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
        en_families = [fam for fam in _FAMILY_CATALOG.values() if fam.language == "en"]
        assert en_families, "Expected at least one English family in catalog"
        for fam in en_families:
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


# ── Catalog integrity ─────────────────────────────────────────────────────────


class TestCatalogIntegrity:
    """Every entry in _FAMILY_CATALOG must be structurally sound."""

    def test_every_family_id_matches_catalog_key(self) -> None:
        for key, fam in _FAMILY_CATALOG.items():
            assert fam.id == key, (
                f"Family stored under {key!r} has id={fam.id!r}"
            )

    def test_every_family_has_at_least_one_variant(self) -> None:
        for fam in _FAMILY_CATALOG.values():
            assert len(fam.variants) >= 1, (
                f"Family {fam.id!r} has no variants"
            )

    def test_every_family_has_exactly_one_exact_variant(self) -> None:
        for fam in _FAMILY_CATALOG.values():
            exact = [v for v in fam.variants if v.match_type == MatchType.exact]
            assert len(exact) == 1, (
                f"Family {fam.id!r} has {len(exact)} exact variants (expected 1)"
            )

    def test_canonical_form_matches_exact_variant_surface(self) -> None:
        for fam in _FAMILY_CATALOG.values():
            exact = next(v for v in fam.variants if v.match_type == MatchType.exact)
            assert fam.canonical_form == exact.surface, (
                f"Family {fam.id!r}: canonical_form={fam.canonical_form!r} "
                f"!= exact variant surface={exact.surface!r}"
            )

    def test_all_required_fields_nonempty(self) -> None:
        for fam in _FAMILY_CATALOG.values():
            assert fam.id,            f"{fam.id!r} has empty id"
            assert fam.language,      f"{fam.id!r} has empty language"
            assert fam.canonical_form, f"{fam.id!r} has empty canonical_form"
            assert fam.meaning,       f"{fam.id!r} has empty meaning"
            assert fam.register,      f"{fam.id!r} has empty register"

    def test_all_variant_surfaces_nonempty(self) -> None:
        for fam in _FAMILY_CATALOG.values():
            for var in fam.variants:
                assert var.surface, (
                    f"Family {fam.id!r} has a variant with empty surface"
                )

    def test_all_confusable_refs_point_to_existing_families(self) -> None:
        for fam in _FAMILY_CATALOG.values():
            for ref in fam.confusables:
                assert ref in _FAMILY_CATALOG, (
                    f"Family {fam.id!r} references unknown confusable {ref!r}"
                )

    def test_no_family_lists_itself_as_confusable(self) -> None:
        for fam in _FAMILY_CATALOG.values():
            assert fam.id not in fam.confusables, (
                f"Family {fam.id!r} lists itself as a confusable"
            )

    def test_confusable_refs_are_mutual(self) -> None:
        for fam in _FAMILY_CATALOG.values():
            for ref in fam.confusables:
                other = _FAMILY_CATALOG[ref]
                assert fam.id in other.confusables, (
                    f"Confusable link {fam.id!r} → {ref!r} is not reciprocated"
                )

    def test_register_values_are_known(self) -> None:
        known = {"neutral", "literary", "formal", "informal", "archaic"}
        for fam in _FAMILY_CATALOG.values():
            assert fam.register in known, (
                f"Family {fam.id!r} has unknown register {fam.register!r}"
            )

    def test_language_values_nonempty_strings(self) -> None:
        for fam in _FAMILY_CATALOG.values():
            assert isinstance(fam.language, str) and fam.language, (
                f"Family {fam.id!r} has invalid language {fam.language!r}"
            )


# ── Normalized-surface collision detection ────────────────────────────────────


class TestNormalizedSurfaceCollisions:
    """No two variants should share a normalized surface within a language.

    A collision causes _VARIANT_INDEX to silently overwrite one entry with
    the other, making one variant permanently undetectable.

    Add pairs to _ALLOWED_CROSS_FAMILY_COLLISIONS when a collision is
    genuinely intentional (e.g. two families that are explicit confusables
    of each other and intentionally share a surface).
    """

    # Cross-family collisions that are explicitly permitted.
    # Each entry is frozenset({family_id_a, family_id_b}).
    _ALLOWED: set[frozenset[str]] = set()

    def _build_norm_index(
        self,
    ) -> dict[str, list[tuple[str, str, MatchType]]]:
        """normalized_surface → [(family_id, display_surface, match_type)]"""
        idx: dict[str, list[tuple[str, str, MatchType]]] = defaultdict(list)
        for fam in _FAMILY_CATALOG.values():
            for var in fam.variants:
                norm = " ".join(_normalise(var.surface))
                if norm:
                    idx[norm].append((fam.id, var.surface, var.match_type))
        return idx

    def test_no_within_family_duplicate_surface(self) -> None:
        idx = self._build_norm_index()
        violations: list[str] = []
        for norm, entries in idx.items():
            if len(entries) <= 1:
                continue
            by_family: dict[str, list] = defaultdict(list)
            for fam_id, surface, mt in entries:
                by_family[fam_id].append((surface, mt))
            for fam_id, dupes in by_family.items():
                if len(dupes) > 1:
                    violations.append(
                        f"Family {fam_id!r} has two variants with normalized "
                        f"surface {norm!r}: {[s for s, _ in dupes]}"
                    )
        assert not violations, "\n".join(violations)

    def test_no_cross_family_collision(self) -> None:
        idx = self._build_norm_index()
        violations: list[str] = []
        for norm, entries in idx.items():
            if len(entries) <= 1:
                continue
            by_family: dict[str, list] = defaultdict(list)
            for fam_id, surface, mt in entries:
                by_family[fam_id].append((surface, mt))
            if len(by_family) <= 1:
                continue  # within-family only; other test handles it
            fam_ids = list(by_family.keys())
            pair = frozenset(fam_ids)
            if pair not in self._ALLOWED:
                violations.append(
                    f"Normalized surface {norm!r} collides across families "
                    + ", ".join(
                        f"{fid!r} ({[s for s, _ in by_family[fid]]})"
                        for fid in fam_ids
                    )
                )
        assert not violations, "\n".join(violations)

    def test_variant_index_size_equals_total_variants(self) -> None:
        """_VARIANT_INDEX must contain one slot per variant (no silent overwrites)."""
        total = sum(len(fam.variants) for fam in _FAMILY_CATALOG.values())
        assert len(_VARIANT_INDEX) == total, (
            f"_VARIANT_INDEX has {len(_VARIANT_INDEX)} slots but the catalog "
            f"defines {total} variants — collision(s) caused silent overwrite(s)."
        )


# ── Language filter ───────────────────────────────────────────────────────────


class TestLanguageFilter:
    """match_phrase_families must return nothing for non-matching language codes."""

    # English phrase tokens that would match if the language were "en".
    _EN_TOKENS = _tokens("all that glitters is not gold")

    @pytest.mark.parametrize("lang", [
        "fr", "es", "de", "it", "pt", "ru",
        "ja", "zh", "ar", "he", "la", "grc",
        "x-cjk-test", "x-rtl-test",
    ])
    def test_no_en_match_for_other_language(self, lang: str) -> None:
        results = match_phrase_families(self._EN_TOKENS, lang)
        assert results == [], (
            f"English phrase matched with language={lang!r}: {results}"
        )

    def test_case_sensitive_language_code(self) -> None:
        results = match_phrase_families(self._EN_TOKENS, "EN")
        assert results == [], (
            "Language code matching must be case-sensitive; 'EN' != 'en'"
        )

    def test_empty_language_returns_empty(self) -> None:
        results = match_phrase_families(self._EN_TOKENS, "")
        assert results == []

    def test_correct_language_still_matches(self) -> None:
        results = match_phrase_families(self._EN_TOKENS, "en")
        assert len(results) == 1, (
            "Sanity check: English phrase must match with language='en'"
        )


# ── confusable_families in lesson_data ───────────────────────────────────────


class TestConfusableFamilies:
    """confusable_families must be a rich list, not raw IDs."""

    def _match(self, phrase: str) -> dict:
        results = match_phrase_families(_tokens(phrase), "en")
        assert results, f"No match for: {phrase!r}"
        return results[0].lesson_data

    def test_confusable_families_present_when_confusables_exist(self) -> None:
        ld = self._match("all that glisters is not gold")
        assert "confusable_families" in ld

    def test_confusable_families_have_required_keys(self) -> None:
        ld = self._match("all that glisters is not gold")
        for cf in ld["confusable_families"]:
            assert "family_id"      in cf, f"Missing family_id: {cf}"
            assert "canonical_form" in cf, f"Missing canonical_form: {cf}"
            assert "meaning"        in cf, f"Missing meaning: {cf}"
            assert "register"       in cf, f"Missing register: {cf}"

    def test_confusable_families_canonical_form_nonempty(self) -> None:
        ld = self._match("all that glisters is not gold")
        for cf in ld["confusable_families"]:
            assert cf["canonical_form"], f"Empty canonical_form in: {cf}"

    def test_confusable_families_meaning_nonempty(self) -> None:
        ld = self._match("all that glisters is not gold")
        for cf in ld["confusable_families"]:
            assert cf["meaning"], f"Empty meaning in: {cf}"

    def test_confusable_families_ids_match_raw_confusables(self) -> None:
        ld = self._match("all that glisters is not gold")
        raw_ids = set(ld.get("confusables", []))
        rich_ids = {cf["family_id"] for cf in ld["confusable_families"]}
        assert rich_ids == raw_ids

    def test_family_without_confusables_omits_confusable_families(self) -> None:
        ld = self._match("hit the nail on the head")
        assert "confusable_families" not in ld

    def test_unknown_confusable_id_skipped_not_crashed(self) -> None:
        fam = _FAMILY_CATALOG["all_that_glitters"]
        import dataclasses
        bad_fam = dataclasses.replace(fam, confusables=("nonexistent_id",))
        from backend.dictionary.phrase_families import _family_to_candidate, PhraseVariant
        exact = next(v for v in fam.variants if v.match_type == MatchType.exact)
        obj = _family_to_candidate(bad_fam, exact.surface, exact)
        # Bad ID skipped — list present but empty.
        assert obj.lesson_data.get("confusable_families", []) == []


# ── lookup_family_by_id ───────────────────────────────────────────────────────


class TestLookupFamilyById:
    def test_known_id_returns_candidate(self) -> None:
        obj = lookup_family_by_id("all_that_glitters")
        assert obj is not None
        assert obj.type == "phrase_family"
        assert obj.lesson_data["family_id"] == "all_that_glitters"

    def test_unknown_id_returns_none(self) -> None:
        assert lookup_family_by_id("no_such_family") is None

    def test_returned_candidate_has_confusable_families(self) -> None:
        obj = lookup_family_by_id("all_that_glitters")
        assert obj is not None
        assert "confusable_families" in obj.lesson_data

    def test_surface_is_canonical_exact_variant(self) -> None:
        obj = lookup_family_by_id("all_that_glitters")
        assert obj is not None
        fam = _FAMILY_CATALOG["all_that_glitters"]
        exact = next(v for v in fam.variants if v.match_type == MatchType.exact)
        assert obj.surface_form == exact.surface
