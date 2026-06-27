"""Unit tests for backend/srs/sentence_miner.py.

All tests are pure — no I/O, no DB.  The miner is tested against hand-crafted
object dicts that match the shape produced by parse persistence.
"""
from __future__ import annotations

import pytest

from backend.srs.sentence_miner import (
    SentenceReviewItemSpec,
    _MAX_PER_SENTENCE,
    _MIN_CONFIDENCE,
    _MIN_SENTENCE_CHARS,
    _MAX_SENTENCE_CHARS,
    mine_sentence,
)

# ── Helpers ───────────────────────────────────────────────────────────────────

SID = "sentence-uuid-001"
LANG = "es"


def _vocab(surface: str, *, confidence: float = 0.85, lemma: str | None = None, cefr: str | None = None) -> dict:
    return {
        "id": f"obj-{surface}",
        "type": "vocabulary",
        "display_label": surface,
        "surface_forms": [surface],
        "lesson_data": {**({"lemma": lemma} if lemma else {}), **({"cefr_level": cefr} if cefr else {})},
        "confidence": confidence,
    }


def _conj(surface: str, *, lemma: str, tense: str, mood: str = "indicative", confidence: float = 0.85) -> dict:
    return {
        "id": f"obj-{surface}",
        "type": "conjugation",
        "display_label": surface,
        "surface_forms": [surface],
        "lesson_data": {"lemma": lemma, "tense": tense, "mood": mood},
        "confidence": confidence,
    }


def _idiom(label: str, *, confidence: float = 0.80) -> dict:
    return {
        "id": f"obj-{label.replace(' ', '_')}",
        "type": "idiom",
        "display_label": label,
        "surface_forms": [label],
        "lesson_data": {},
        "confidence": confidence,
    }


def _conj_with_contrast(surface: str, *, lemma: str, tense: str, form_b: str, note: str) -> dict:
    return {
        "id": f"obj-{surface}",
        "type": "conjugation",
        "display_label": surface,
        "surface_forms": [surface],
        "lesson_data": {
            "lemma": lemma,
            "tense": tense,
            "mood": "indicative",
            "contrasts": [{"form_a": surface, "form_b": form_b, "note": note}],
        },
        "confidence": 0.80,
    }


# ── Sentence eligibility ──────────────────────────────────────────────────────

class TestSentenceEligibility:
    def test_too_short_rejected(self):
        short = "Hola."
        assert mine_sentence(SID, short, LANG, [_vocab("Hola")]) == []

    def test_too_long_rejected(self):
        long_sent = "a " * 200  # > 280 chars
        assert mine_sentence(SID, long_sent, LANG, [_vocab("a")]) == []

    def test_empty_sentence_rejected(self):
        assert mine_sentence(SID, "", LANG, [_vocab("casa")]) == []

    def test_boundary_length_accepted(self):
        sent = "El niño juega en el jardín con su perro."
        items = mine_sentence(SID, sent, LANG, [_vocab("niño")])
        assert len(items) >= 1


# ── Cloze generation ──────────────────────────────────────────────────────────

class TestCloze:
    def test_basic_cloze(self):
        sent = "La casa es muy grande."
        items = mine_sentence(SID, sent, LANG, [_vocab("casa")])
        assert len(items) == 1
        item = items[0]
        assert item.item_type == "cloze"
        assert "___" in item.prompt
        assert item.answer.lower() == "casa"
        assert item.target_span.lower() == "casa"

    def test_cloze_uses_surface_form(self):
        sent = "Ella comió una manzana."
        obj = _vocab("manzana")
        items = mine_sentence(SID, sent, LANG, [obj])
        assert items[0].answer.lower() == "manzana"

    def test_cloze_blank_is_first_occurrence(self):
        sent = "El gato vio al gato en el jardín."
        obj = _vocab("gato")
        items = mine_sentence(SID, sent, LANG, [obj])
        # First "gato" should be blanked
        assert items[0].prompt.index("___") < items[0].prompt.find("gato") or \
               "gato" not in items[0].prompt.replace("___", "")

    def test_lemma_hint_when_different(self):
        sent = "Los perros corren rápido."
        obj = _vocab("perros", lemma="perro")
        items = mine_sentence(SID, sent, LANG, [obj])
        assert items[0].hint is not None
        assert "perro" in items[0].hint

    def test_no_hint_when_lemma_equals_surface(self):
        sent = "El gato duerme mucho."
        obj = _vocab("gato", lemma="gato")
        items = mine_sentence(SID, sent, LANG, [obj])
        assert items[0].hint is None

    def test_span_not_in_sentence_returns_nothing(self):
        sent = "Hace mucho frío aquí."
        obj = _vocab("calor")
        items = mine_sentence(SID, sent, LANG, [obj])
        assert items == []

    def test_cefr_propagated(self):
        sent = "Tengo mucho trabajo que hacer."
        obj = _vocab("trabajo", cefr="A2")
        items = mine_sentence(SID, sent, LANG, [obj])
        assert items[0].cefr_level == "A2"

    def test_object_id_in_target_ids(self):
        sent = "La ciudad es hermosa."
        obj = _vocab("ciudad")
        items = mine_sentence(SID, sent, LANG, [obj])
        assert obj["id"] in items[0].target_object_ids


# ── Chunk recall ──────────────────────────────────────────────────────────────

class TestChunkRecall:
    def test_basic_chunk_recall(self):
        sent = "Me estás tomando el pelo con eso."
        obj = _idiom("tomando el pelo")
        items = mine_sentence(SID, sent, LANG, [obj])
        assert len(items) >= 1
        item = items[0]
        assert item.item_type == "chunk_recall"
        assert "___" in item.prompt
        # Stem should be present; answer is the tail
        assert item.answer  # not empty

    def test_single_word_idiom_falls_back_to_cloze(self):
        sent = "Llegamos al fin."
        obj = _idiom("fin")
        items = mine_sentence(SID, sent, LANG, [obj])
        # Should fall back to cloze since no space in label
        assert len(items) == 1
        assert items[0].item_type == "cloze"

    def test_chunk_not_in_sentence_yields_cloze(self):
        sent = "El tiempo pasa volando sin parar."
        obj = _idiom("no estar ni de broma")
        items = mine_sentence(SID, sent, LANG, [obj])
        # idiom not found → falls through to cloze if nothing found
        assert all(i.item_type != "chunk_recall" for i in items)


# ── Grammar transform ─────────────────────────────────────────────────────────

class TestGrammarTransform:
    def test_present_to_preterite(self):
        sent = "Ella habla español todos los días."
        obj = _conj("habla", lemma="hablar", tense="present")
        items = mine_sentence(SID, sent, LANG, [obj])
        assert len(items) >= 1
        item = items[0]
        assert item.item_type == "grammar_transform"
        assert item.grammar_concept == "present_to_preterite"
        assert "preterite" in item.hint or "preterite" in item.answer

    def test_preterite_imperfect_gets_special_concept(self):
        sent = "Ayer comió mucho en la fiesta."
        obj = _conj("comió", lemma="comer", tense="preterite")
        items = mine_sentence(SID, sent, LANG, [obj])
        assert items[0].grammar_concept == "preterite_imperfect"

    def test_untransformable_tense_falls_to_cloze(self):
        sent = "Quería que lo hicieras tú."
        obj = _conj("hicieras", lemma="hacer", tense="subjunctive")
        items = mine_sentence(SID, sent, LANG, [obj])
        # subjunctive not in transform map → cloze
        assert items[0].item_type == "cloze"

    def test_transform_has_higher_difficulty(self):
        sent = "Ella cantó muy bien en el concierto."
        cloze_obj = _vocab("cantó", confidence=0.85)
        transform_obj = _conj("cantó", lemma="cantar", tense="preterite", confidence=0.85)
        cloze_items = mine_sentence(SID, sent, LANG, [cloze_obj])
        transform_items = mine_sentence(SID, sent, LANG, [transform_obj])
        assert transform_items[0].difficulty_score > cloze_items[0].difficulty_score


# ── Meaning discrimination ────────────────────────────────────────────────────

class TestMeaningDiscrimination:
    def test_basic_discrimination(self):
        sent = "Ayer comió en casa de sus padres."
        obj = _conj_with_contrast(
            "comió", lemma="comer", tense="preterite",
            form_b="comía",
            note="Use preterite for completed past actions, imperfect for ongoing/habitual."
        )
        items = mine_sentence(SID, sent, LANG, [obj])
        disc = next((i for i in items if i.item_type == "meaning_discrimination"), None)
        assert disc is not None
        assert disc.answer == "comió"
        assert "comía" in disc.distractors
        assert disc.hint is not None

    def test_discrimination_without_contrast_falls_to_transform(self):
        sent = "Ellos vivían en Madrid cuando era niño."
        obj = _conj("vivían", lemma="vivir", tense="imperfect")
        items = mine_sentence(SID, sent, LANG, [obj])
        # No contrasts → should fall to grammar_transform
        assert items[0].item_type in ("grammar_transform", "cloze")


# ── Cap + priority ────────────────────────────────────────────────────────────

class TestCapAndPriority:
    def test_max_items_per_sentence(self):
        sent = "El gato come peces en el río tranquilo hoy."
        objects = [
            _vocab("gato"),
            _vocab("come"),
            _vocab("peces"),
            _vocab("río"),
            _vocab("tranquilo"),
        ]
        items = mine_sentence(SID, sent, LANG, objects)
        assert len(items) <= _MAX_PER_SENTENCE

    def test_custom_max_items(self):
        sent = "El gato come peces en el río tranquilo hoy."
        objects = [_vocab(w) for w in ["gato", "come", "peces", "río"]]
        items = mine_sentence(SID, sent, LANG, objects, max_items=2)
        assert len(items) <= 2

    def test_low_confidence_objects_skipped(self):
        sent = "Había una vez un dragón poderoso."
        obj = _vocab("dragón", confidence=0.3)  # below threshold
        items = mine_sentence(SID, sent, LANG, [obj])
        assert items == []

    def test_confidence_at_threshold_accepted(self):
        sent = "Había una vez un dragón poderoso."
        obj = _vocab("dragón", confidence=_MIN_CONFIDENCE)
        items = mine_sentence(SID, sent, LANG, [obj])
        assert len(items) == 1

    def test_higher_confidence_preferred(self):
        sent = "La bella princesa dormía en el castillo encantado."
        high = _vocab("princesa", confidence=0.95)
        low = _vocab("castillo", confidence=0.55)
        items = mine_sentence(SID, sent, LANG, [high, low], max_items=1)
        assert items[0].target_span.lower() == "princesa"

    def test_no_duplicate_span_type(self):
        sent = "El gato negro caza ratones."
        # Two objects with same surface form — only one item should be produced.
        obj1 = _vocab("gato")
        obj2 = {**_vocab("gato"), "id": "obj-gato-2"}
        items = mine_sentence(SID, sent, LANG, [obj1, obj2])
        spans = [(i.item_type, i.target_span.lower()) for i in items]
        assert len(spans) == len(set(spans))


# ── Empty / degenerate inputs ─────────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_objects_list(self):
        sent = "El niño juega en el parque todos los días."
        assert mine_sentence(SID, sent, LANG, []) == []

    def test_non_eligible_types_skipped(self):
        sent = "Ella llegó tarde a la reunión importante."
        obj = {"id": "x", "type": "agreement", "display_label": "la",
               "surface_forms": ["la"], "lesson_data": {}, "confidence": 0.9}
        assert mine_sentence(SID, sent, LANG, [obj]) == []

    def test_sentence_without_any_matching_form(self):
        sent = "Mañana saldremos de viaje muy temprano."
        obj = _vocab("casa")  # "casa" not in sentence
        assert mine_sentence(SID, sent, LANG, [obj]) == []

    def test_returns_list(self):
        sent = "Ella trabaja mucho todos los días de la semana."
        result = mine_sentence(SID, sent, LANG, [_vocab("trabaja")])
        assert isinstance(result, list)

    def test_spec_fields_populated(self):
        sent = "Los estudiantes estudian en la biblioteca."
        obj = _vocab("estudiantes", lemma="estudiante", cefr="A1")
        items = mine_sentence(SID, sent, LANG, [obj])
        spec = items[0]
        assert spec.sentence_id == SID
        assert spec.language == LANG
        assert spec.item_type
        assert spec.prompt
        assert spec.target_span
        assert spec.answer
        assert spec.difficulty_score is not None
        assert spec.cefr_level == "A1"
