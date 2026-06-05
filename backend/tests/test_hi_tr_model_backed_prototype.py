"""Regression tests for optional Hindi/Turkish model-backed morphology prototypes."""
from __future__ import annotations

from backend.morphology.tr_stanza_adapter import TrStanzaMorphToken
from backend.plugins import hindi as hindi_mod
from backend.plugins import turkish as turkish_mod
from backend.plugins.hindi import create_plugin as create_hindi
from backend.plugins.turkish import create_plugin as create_turkish


def _assert_unique_canonical_forms(result) -> None:
    forms = [c.canonical_form for c in result.candidates]
    assert forms == list(dict.fromkeys(forms))


class TestHindiOptionalModelFallback:
    def test_stanza_unavailable_falls_back_to_suffix_rules(self, monkeypatch):
        monkeypatch.setattr(hindi_mod._hi_adapter, "is_available", lambda: False)
        plugin = create_hindi()

        result = plugin.analyze_sentence("वह कल जाएगा।")
        jaayega = next(
            c for c in result.candidates
            if c.surface_form == "जाएगा" and c.type == "conjugation"
        )

        assert jaayega.lesson_data.get("tense") == "future"
        assert jaayega.lesson_data.get("gender") == "masculine"
        assert jaayega.lesson_data.get("confidence_note")
        _assert_unique_canonical_forms(result)

    def test_rule_known_habitual_remains_available_without_stanza(self, monkeypatch):
        monkeypatch.setattr(hindi_mod._hi_adapter, "is_available", lambda: False)
        plugin = create_hindi()

        result = plugin.analyze_sentence("वह रोज़ जाता है।")
        jaata = next(
            c for c in result.candidates
            if c.surface_form == "जाता" and c.type == "conjugation"
        )

        assert jaata.lesson_data.get("aspect") == "habitual"
        assert jaata.lesson_data.get("gender") == "masculine"
        assert jaata.confidence <= 0.45

    def test_opaque_hindi_rule_output_is_not_overconfident(self, monkeypatch):
        monkeypatch.setattr(hindi_mod._hi_adapter, "is_available", lambda: False)
        plugin = create_hindi()

        result = plugin.analyze_sentence("अज्ञात")

        assert result.candidates[0].confidence is None
        _assert_unique_canonical_forms(result)


class TestTurkishOptionalModelFallback:
    def test_models_unavailable_fall_back_to_suffix_rules(self, monkeypatch):
        monkeypatch.setattr(turkish_mod._tr_stanza, "is_available", lambda: False)
        monkeypatch.setattr(turkish_mod._tr_adapter, "is_available", lambda: False)
        plugin = create_turkish()

        result = plugin.analyze_sentence("Gidecek.")
        gidecek = next(
            c for c in result.candidates
            if c.surface_form.lower() == "gidecek" and c.type == "conjugation"
        )

        assert gidecek.lesson_data.get("tense") == "future"
        assert gidecek.lesson_data.get("confidence_note")
        assert gidecek.confidence <= 0.45
        _assert_unique_canonical_forms(result)

    def test_rule_known_locative_remains_available_without_models(self, monkeypatch):
        monkeypatch.setattr(turkish_mod._tr_stanza, "is_available", lambda: False)
        monkeypatch.setattr(turkish_mod._tr_adapter, "is_available", lambda: False)
        plugin = create_turkish()

        result = plugin.analyze_sentence("Evde.")
        evde = next(c for c in result.candidates if c.surface_form.lower() == "evde")

        assert evde.lesson_data.get("case") == "locative"
        assert evde.confidence <= 0.45

    def test_stanza_no_feature_output_is_not_overconfident(self):
        plugin = create_turkish()
        fake_tokens = [
            TrStanzaMorphToken(
                text="Belirsiz",
                lemma="belirsiz",
                upos="NOUN",
                case=None,
                number=None,
                person=None,
                poss_person=None,
                poss_number=None,
                tense=None,
                mood=None,
                polarity=None,
                verb_form=None,
                evidential=None,
                source="stanza",
                feats_raw=None,
            )
        ]

        result = plugin._analyze_with_stanza("Belirsiz", fake_tokens)

        assert result.candidates[0].confidence is None
        _assert_unique_canonical_forms(result)
