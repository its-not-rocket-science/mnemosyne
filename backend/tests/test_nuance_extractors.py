"""Golden-sentence tests for all per-language NuanceExtractors.

Each test class:
  - builds stub tokens that mimic the plugin output (no spaCy loaded)
  - optionally builds stub CandidateObjects
  - calls extract_nuance() and asserts expected nuance_type(s)

Token stub deliberately minimal — only the attributes our extractors read.
"""
from __future__ import annotations

import pytest

from backend.schemas.parse import CandidateObject, RelationHint
from backend.nuance.en import EnglishNuanceExtractor
from backend.nuance.es import SpanishNuanceExtractor
from backend.nuance.fr import FrenchNuanceExtractor
from backend.nuance.de import GermanNuanceExtractor
from backend.nuance.ru import RussianNuanceExtractor
from backend.nuance.zh import ChineseNuanceExtractor
from backend.nuance.ja import JapaneseNuanceExtractor
from backend.nuance.ar import ArabicNuanceExtractor
from backend.nuance.he import HebrewNuanceExtractor
from backend.nuance.la import LatinNuanceExtractor
from backend.nuance.grc import AncientGreekNuanceExtractor
from backend.nuance.registry import get_extractor
from backend.nuance.interface import NuanceExtractor


# ── Token stub ────────────────────────────────────────────────────────────────

class _Tok:
    def __init__(
        self,
        text: str,
        pos: str = "NOUN",
        lemma: str = "",
        dep: str = "dep",
    ):
        self.text    = text
        self.pos_    = pos
        self.lemma_  = lemma or text.lower()
        self.dep_    = dep
        self.is_punct = False
        self.is_space = False

    def __repr__(self) -> str:
        return f"<Tok {self.text!r}>"


def _tok(text: str, pos: str = "NOUN", lemma: str = "", dep: str = "dep") -> _Tok:
    return _Tok(text, pos=pos, lemma=lemma, dep=dep)


def _conj(lemma: str, surface: str, mood: str = "indicative") -> CandidateObject:
    return CandidateObject(
        canonical_form=f"conj:{lemma}:{mood}",
        surface_form=surface,
        type="conjugation",
        label=surface,
        lesson_data={"lemma": lemma, "surface": surface, "mood": mood},
        confidence=0.85,
    )


def _vocab(lemma: str, surface: str = "") -> CandidateObject:
    return CandidateObject(
        canonical_form=lemma,
        surface_form=surface or lemma,
        type="vocabulary",
        label=surface or lemma,
        lesson_data={"lemma": lemma},
        confidence=0.80,
    )


def _nuance_types(results: list[CandidateObject]) -> set[str]:
    return {c.lesson_data.get("nuance_type", "") for c in results if c.type == "nuance"}




# ── English ───────────────────────────────────────────────────────────────────

class TestEnglishNuance:
    @pytest.fixture()
    def ext(self):
        return EnglishNuanceExtractor()

    def test_register_formal_detected(self, ext):
        results = ext.extract_nuance("Therefore we proceed.", [_tok("Therefore")], [], "en")
        assert "register" in _nuance_types(results)

    def test_politeness_detected(self, ext):
        results = ext.extract_nuance("Could you help, please?", [_tok("Could"), _tok("please")], [], "en")
        assert "politeness" in _nuance_types(results)

    def test_ambiguity_detected(self, ext):
        results = ext.extract_nuance("Since he left, we waited.", [_tok("Since")], [], "en")
        assert "ambiguity" in _nuance_types(results)

    def test_collocation_detected(self, ext):
        toks = [_tok("make"), _tok("a"), _tok("decision")]
        results = ext.extract_nuance("make a decision", toks, [], "en")
        assert "collocation" in _nuance_types(results)

    def test_regional_variation_detected(self, ext):
        results = ext.extract_nuance("The apartment is small.", [_tok("apartment")], [], "en")
        assert "regional_variation" in _nuance_types(results)

    def test_required_keys_present(self, ext):
        results = ext.extract_nuance("please", [_tok("please")], [], "en")
        n = next(c for c in results if c.lesson_data.get("nuance_type") == "politeness")
        for key in ("nuance_type", "explanation", "register", "learner_level", "source"):
            assert key in n.lesson_data

# ── Spanish ───────────────────────────────────────────────────────────────────

class TestSpanishNuance:
    @pytest.fixture()
    def ext(self):
        return SpanishNuanceExtractor()

    def test_ser_detected(self, ext):
        # "Juan es médico."
        candidates = [_conj("ser", "es")]
        results = ext.extract_nuance("Juan es médico.", [], candidates, "es")
        assert "ser_estar" in _nuance_types(results)

    def test_estar_detected(self, ext):
        # "Ella está cansada."
        candidates = [_conj("estar", "está")]
        results = ext.extract_nuance("Ella está cansada.", [], candidates, "es")
        assert "ser_estar" in _nuance_types(results)

    def test_ser_and_estar_both_in_sentence(self, ext):
        # "Ella está cansada pero es médica."
        candidates = [_conj("estar", "está"), _conj("ser", "es")]
        results = ext.extract_nuance("Ella está cansada pero es médica.", [], candidates, "es")
        ser_estar = [c for c in results if c.lesson_data.get("nuance_type") == "ser_estar"]
        assert len(ser_estar) == 2

    def test_por_detected(self, ext):
        tokens = [_tok("Estudia"), _tok("por"), _tok("amor")]
        results = ext.extract_nuance("Estudia por amor.", tokens, [], "es")
        assert "por_para" in _nuance_types(results)

    def test_para_detected(self, ext):
        tokens = [_tok("Trabaja"), _tok("para"), _tok("vivir")]
        results = ext.extract_nuance("Trabaja para vivir.", tokens, [], "es")
        assert "por_para" in _nuance_types(results)

    def test_por_para_no_duplicate(self, ext):
        tokens = [_tok("por"), _tok("para")]
        results = ext.extract_nuance("por para", tokens, [], "es")
        por_para = [c for c in results if c.lesson_data.get("nuance_type") == "por_para"]
        assert len(por_para) == 2  # one per preposition

    def test_subjunctive_detected(self, ext):
        # mood contains "sub"
        candidates = [_conj("venir", "vengas", mood="subjunctive")]
        results = ext.extract_nuance("Quiero que vengas.", [], candidates, "es")
        assert "subjunctive_trigger" in _nuance_types(results)

    def test_diminutive_detected(self, ext):
        tokens = [_tok("El"), _tok("gatito"), _tok("duerme")]
        results = ext.extract_nuance("El gatito duerme.", tokens, [], "es")
        assert "diminutive" in _nuance_types(results)

    def test_diminutive_too_short_not_flagged(self, ext):
        tokens = [_tok("hito")]  # 4 chars, below min 6
        results = ext.extract_nuance("hito", tokens, [], "es")
        assert "diminutive" not in _nuance_types(results)

    def test_ser_estar_relation_hint(self, ext):
        candidates = [_conj("ser", "es")]
        results = ext.extract_nuance("Es tarde.", [], candidates, "es")
        nuances = [c for c in results if c.lesson_data.get("nuance_type") == "ser_estar"]
        assert any(h.relation_type == "nuance_of" for h in nuances[0].relation_hints)

    def test_type_is_nuance(self, ext):
        candidates = [_conj("ser", "es")]
        results = ext.extract_nuance("Es tarde.", [], candidates, "es")
        assert all(c.type == "nuance" for c in results)


# ── French ────────────────────────────────────────────────────────────────────

class TestFrenchNuance:
    @pytest.fixture()
    def ext(self):
        return FrenchNuanceExtractor()

    def test_tu_informal(self, ext):
        tokens = [_tok("tu"), _tok("aimes"), _tok("la"), _tok("musique")]
        results = ext.extract_nuance("tu aimes la musique", tokens, [], "fr")
        assert "tu_vous_register" in _nuance_types(results)
        reg = next(c for c in results if c.lesson_data.get("nuance_type") == "tu_vous_register")
        assert reg.lesson_data["register"] == "informal"

    def test_vous_formal(self, ext):
        tokens = [_tok("vous"), _tok("aimez"), _tok("la"), _tok("musique")]
        results = ext.extract_nuance("vous aimez la musique", tokens, [], "fr")
        assert "tu_vous_register" in _nuance_types(results)
        reg = next(c for c in results if c.lesson_data.get("nuance_type") == "tu_vous_register")
        assert reg.lesson_data["register"] == "formal"

    def test_tu_and_vous_both_flagged(self, ext):
        tokens = [_tok("tu"), _tok("et"), _tok("vous")]
        results = ext.extract_nuance("tu et vous", tokens, [], "fr")
        tu_vous = [c for c in results if c.lesson_data.get("nuance_type") == "tu_vous_register"]
        assert len(tu_vous) == 2

    def test_ne_expletif_no_pas(self, ext):
        # "Il faut que tu ne viennes" — no pas after ne
        tokens = [_tok("Il"), _tok("faut"), _tok("que"), _tok("tu"),
                  _tok("ne"), _tok("viennes")]
        results = ext.extract_nuance("Il faut que tu ne viennes", tokens, [], "fr")
        assert "ne_expletif" in _nuance_types(results)

    def test_ne_pas_not_flagged_as_expletif(self, ext):
        tokens = [_tok("Il"), _tok("ne"), _tok("vient"), _tok("pas")]
        results = ext.extract_nuance("Il ne vient pas.", tokens, [], "fr")
        assert "ne_expletif" not in _nuance_types(results)

    def test_subjunctive_detected(self, ext):
        candidates = [_conj("venir", "vienne", mood="subjunctive")]
        results = ext.extract_nuance("Il faut qu'il vienne.", [], candidates, "fr")
        assert "subjunctive_trigger" in _nuance_types(results)

    def test_liaison_vous_avant_voyelle(self, ext):
        # "vous avez" → liaison
        tokens = [_tok("vous"), _tok("avez")]
        results = ext.extract_nuance("vous avez", tokens, [], "fr")
        assert "liaison" in _nuance_types(results)

    def test_liaison_no_fire_before_consonant(self, ext):
        tokens = [_tok("vous"), _tok("parlez")]  # p is consonant
        results = ext.extract_nuance("vous parlez", tokens, [], "fr")
        assert "liaison" not in _nuance_types(results)

    def test_confidence_tu_vous(self, ext):
        tokens = [_tok("tu")]
        results = ext.extract_nuance("tu", tokens, [], "fr")
        nuance = next(c for c in results if c.lesson_data.get("nuance_type") == "tu_vous_register")
        assert nuance.confidence == pytest.approx(0.90)

    # ── Phrase families ───────────────────────────────────────────────────────

    def test_phrase_family_casser_les_pieds(self, ext):
        tokens = [_tok("tu"), _tok("me"), _tok("casses"), _tok("les"), _tok("pieds")]
        results = ext.extract_nuance("tu me casses les pieds", tokens, [], "fr")
        pf = [c for c in results if c.type == "phrase_family"]
        assert any(c.lesson_data["family_id"] == "fr_casser_les_pieds" for c in pf)

    def test_phrase_family_poser_un_lapin(self, ext):
        # m'a must be a single token so it normalises to "ma" and matches the variant
        tokens = [_tok("il"), _tok("m'a"), _tok("posé"), _tok("un"), _tok("lapin")]
        results = ext.extract_nuance("il m'a posé un lapin", tokens, [], "fr")
        pf = [c for c in results if c.type == "phrase_family"]
        assert any(c.lesson_data["family_id"] == "fr_poser_un_lapin" for c in pf)

    def test_phrase_family_avoir_le_cafard(self, ext):
        # use canonical infinitive form to avoid j'/ai split issue
        tokens = [_tok("avoir"), _tok("le"), _tok("cafard")]
        results = ext.extract_nuance("avoir le cafard", tokens, [], "fr")
        pf = [c for c in results if c.type == "phrase_family"]
        assert any(c.lesson_data["family_id"] == "fr_avoir_le_cafard" for c in pf)

    def test_phrase_family_tomber_dans_les_pommes(self, ext):
        tokens = [_tok("elle"), _tok("est"), _tok("tombée"), _tok("dans"),
                  _tok("les"), _tok("pommes")]
        results = ext.extract_nuance(
            "elle est tombée dans les pommes", tokens, [], "fr"
        )
        pf = [c for c in results if c.type == "phrase_family"]
        assert any(c.lesson_data["family_id"] == "fr_tomber_dans_les_pommes" for c in pf)

    def test_phrase_family_revenons_a_nos_moutons(self, ext):
        tokens = [_tok("revenons"), _tok("à"), _tok("nos"), _tok("moutons")]
        results = ext.extract_nuance("revenons à nos moutons", tokens, [], "fr")
        pf = [c for c in results if c.type == "phrase_family"]
        assert any(c.lesson_data["family_id"] == "fr_revenons_a_nos_moutons" for c in pf)

    def test_phrase_family_noyer_le_poisson(self, ext):
        tokens = [_tok("il"), _tok("noie"), _tok("le"), _tok("poisson")]
        results = ext.extract_nuance("il noie le poisson", tokens, [], "fr")
        pf = [c for c in results if c.type == "phrase_family"]
        assert any(c.lesson_data["family_id"] == "fr_noyer_le_poisson" for c in pf)

    def test_phrase_family_pain_sur_la_planche(self, ext):
        tokens = [_tok("on"), _tok("a"), _tok("du"), _tok("pain"),
                  _tok("sur"), _tok("la"), _tok("planche")]
        results = ext.extract_nuance(
            "on a du pain sur la planche", tokens, [], "fr"
        )
        pf = [c for c in results if c.type == "phrase_family"]
        assert any(
            c.lesson_data["family_id"] == "fr_avoir_du_pain_sur_la_planche"
            for c in pf
        )

    def test_phrase_family_carottes_cuites(self, ext):
        tokens = [_tok("les"), _tok("carottes"), _tok("sont"), _tok("cuites")]
        results = ext.extract_nuance("les carottes sont cuites", tokens, [], "fr")
        pf = [c for c in results if c.type == "phrase_family"]
        assert any(
            c.lesson_data["family_id"] == "fr_les_carottes_sont_cuites" for c in pf
        )

    def test_phrase_family_pieds_dans_le_plat(self, ext):
        tokens = [_tok("il"), _tok("a"), _tok("mis"), _tok("les"), _tok("pieds"),
                  _tok("dans"), _tok("le"), _tok("plat")]
        results = ext.extract_nuance(
            "il a mis les pieds dans le plat", tokens, [], "fr"
        )
        pf = [c for c in results if c.type == "phrase_family"]
        assert any(
            c.lesson_data["family_id"] == "fr_mettre_les_pieds_dans_le_plat"
            for c in pf
        )

    def test_phrase_family_autres_chats(self, ext):
        # j'ai and d'autres must be single tokens so apostrophes normalise correctly
        tokens = [_tok("j'ai"), _tok("d'autres"), _tok("chats"), _tok("à"), _tok("fouetter")]
        results = ext.extract_nuance(
            "j'ai d'autres chats à fouetter", tokens, [], "fr"
        )
        pf = [c for c in results if c.type == "phrase_family"]
        assert any(
            c.lesson_data["family_id"] == "fr_avoir_dautres_chats" for c in pf
        )

    def test_phrase_family_croix_et_banniere(self, ext):
        # c'est as single token normalises to "cest" matching the variant key
        tokens = [_tok("c'est"), _tok("la"), _tok("croix"),
                  _tok("et"), _tok("la"), _tok("bannière")]
        results = ext.extract_nuance(
            "c'est la croix et la bannière", tokens, [], "fr"
        )
        pf = [c for c in results if c.type == "phrase_family"]
        assert any(
            c.lesson_data["family_id"] == "fr_cest_la_croix_et_la_banniere"
            for c in pf
        )

    def test_phrase_family_peau_de_lours(self, ext):
        # l'ours as single token normalises to "lours" matching the variant key
        tokens = [_tok("vendre"), _tok("la"), _tok("peau"), _tok("de"), _tok("l'ours")]
        results = ext.extract_nuance(
            "vendre la peau de l'ours", tokens, [], "fr"
        )
        pf = [c for c in results if c.type == "phrase_family"]
        assert any(
            c.lesson_data["family_id"] == "fr_ne_pas_vendre_la_peau" for c in pf
        )

    def test_phrase_family_tenir_la_chandelle(self, ext):
        tokens = [_tok("je"), _tok("tiens"), _tok("la"), _tok("chandelle")]
        results = ext.extract_nuance("je tiens la chandelle", tokens, [], "fr")
        pf = [c for c in results if c.type == "phrase_family"]
        assert any(
            c.lesson_data["family_id"] == "fr_tenir_la_chandelle" for c in pf
        )

    def test_phrase_family_vent_en_poupe(self, ext):
        tokens = [_tok("il"), _tok("a"), _tok("le"), _tok("vent"),
                  _tok("en"), _tok("poupe")]
        results = ext.extract_nuance("il a le vent en poupe", tokens, [], "fr")
        pf = [c for c in results if c.type == "phrase_family"]
        assert any(
            c.lesson_data["family_id"] == "fr_avoir_le_vent_en_poupe" for c in pf
        )

    def test_phrase_family_jambes_a_son_cou(self, ext):
        tokens = [_tok("il"), _tok("a"), _tok("pris"), _tok("ses"),
                  _tok("jambes"), _tok("à"), _tok("son"), _tok("cou")]
        results = ext.extract_nuance(
            "il a pris ses jambes à son cou", tokens, [], "fr"
        )
        pf = [c for c in results if c.type == "phrase_family"]
        assert any(
            c.lesson_data["family_id"] == "fr_prendre_ses_jambes_a_son_cou"
            for c in pf
        )

    def test_phrase_family_pleut_des_cordes(self, ext):
        tokens = [_tok("il"), _tok("pleut"), _tok("des"), _tok("cordes")]
        results = ext.extract_nuance("il pleut des cordes", tokens, [], "fr")
        pf = [c for c in results if c.type == "phrase_family"]
        assert any(
            c.lesson_data["family_id"] == "fr_il_pleut_des_cordes" for c in pf
        )

    def test_phrase_family_fine_bouche(self, ext):
        tokens = [_tok("il"), _tok("fait"), _tok("la"), _tok("fine"), _tok("bouche")]
        results = ext.extract_nuance("il fait la fine bouche", tokens, [], "fr")
        pf = [c for c in results if c.type == "phrase_family"]
        assert any(
            c.lesson_data["family_id"] == "fr_faire_la_fine_bouche" for c in pf
        )

    def test_phrase_family_coeur_sur_main(self, ext):
        tokens = [_tok("il"), _tok("a"), _tok("le"), _tok("cœur"),
                  _tok("sur"), _tok("la"), _tok("main")]
        results = ext.extract_nuance(
            "il a le cœur sur la main", tokens, [], "fr"
        )
        pf = [c for c in results if c.type == "phrase_family"]
        assert any(
            c.lesson_data["family_id"] == "fr_avoir_coeur_sur_main" for c in pf
        )

    def test_phrase_family_poser_les_jalons(self, ext):
        tokens = [_tok("il"), _tok("a"), _tok("posé"), _tok("les"), _tok("jalons")]
        results = ext.extract_nuance("il a posé les jalons", tokens, [], "fr")
        pf = [c for c in results if c.type == "phrase_family"]
        assert any(
            c.lesson_data["family_id"] == "fr_poser_les_jalons" for c in pf
        )

    def test_phrase_family_cross_confusable_registered(self, ext):
        # fr_avoir_coeur_sur_main declares de_hand_aufs_herz as confusable
        from backend.dictionary.phrase_families import lookup_family_by_id
        fam = lookup_family_by_id("fr_avoir_coeur_sur_main")
        assert fam is not None
        assert "de_hand_aufs_herz" in fam.lesson_data.get("confusables", [])


# ── German ────────────────────────────────────────────────────────────────────

class TestGermanNuance:
    @pytest.fixture()
    def ext(self):
        return GermanNuanceExtractor()

    def test_modal_particle_ja(self, ext):
        tokens = [_tok("Das"), _tok("ist"), _tok("ja"), _tok("toll")]
        results = ext.extract_nuance("Das ist ja toll.", tokens, [], "de")
        assert "modal_particle" in _nuance_types(results)

    def test_modal_particle_doch(self, ext):
        tokens = [_tok("Komm"), _tok("doch"), _tok("rein")]
        results = ext.extract_nuance("Komm doch rein.", tokens, [], "de")
        assert "modal_particle" in _nuance_types(results)

    def test_multiple_modal_particles(self, ext):
        tokens = [_tok("Das"), _tok("ist"), _tok("ja"), _tok("doch"), _tok("klar")]
        results = ext.extract_nuance("Das ist ja doch klar.", tokens, [], "de")
        modal = [c for c in results if c.lesson_data.get("nuance_type") == "modal_particle"]
        particles = {c.lesson_data.get("particle") for c in modal}
        assert "ja" in particles
        assert "doch" in particles

    def test_separable_verb_svp(self, ext):
        tokens = [_tok("Ich"), _tok("rufe"), _tok("an", dep="svp")]
        results = ext.extract_nuance("Ich rufe an.", tokens, [], "de")
        assert "separable_verb" in _nuance_types(results)

    def test_separable_verb_no_svp_not_flagged(self, ext):
        tokens = [_tok("an"), _tok("der"), _tok("Schule")]  # "an" as preposition
        results = ext.extract_nuance("an der Schule", tokens, [], "de")
        assert "separable_verb" not in _nuance_types(results)

    def test_wechselpraep_in(self, ext):
        tokens = [_tok("Das"), _tok("Buch"), _tok("liegt"), _tok("in"), _tok("der"), _tok("Tasche")]
        results = ext.extract_nuance("Das Buch liegt in der Tasche.", tokens, [], "de")
        assert "two_way_preposition" in _nuance_types(results)

    def test_wechselpraep_auf(self, ext):
        tokens = [_tok("auf"), _tok("dem"), _tok("Tisch")]
        results = ext.extract_nuance("auf dem Tisch", tokens, [], "de")
        assert "two_way_preposition" in _nuance_types(results)

    def test_particle_lesson_data(self, ext):
        tokens = [_tok("ja")]
        results = ext.extract_nuance("ja", tokens, [], "de")
        nuance = next(c for c in results if c.lesson_data.get("nuance_type") == "modal_particle")
        assert nuance.lesson_data["particle"] == "ja"
        assert "explanation" in nuance.lesson_data


# ── Russian ───────────────────────────────────────────────────────────────────

class TestRussianNuance:
    @pytest.fixture()
    def ext(self):
        return RussianNuanceExtractor()

    def test_motion_verb_unidirectional(self, ext):
        # "Иван идёт в магазин."
        candidates = [_vocab("идти", "идёт")]
        results = ext.extract_nuance("Иван идёт в магазин.", [], candidates, "ru")
        assert "motion_verb" in _nuance_types(results)
        mv = next(c for c in results if c.lesson_data.get("nuance_type") == "motion_verb")
        assert mv.lesson_data["direction_type"] == "unidirectional"

    def test_motion_verb_multidirectional(self, ext):
        candidates = [_vocab("ходить", "ходит")]
        results = ext.extract_nuance("Он ходит каждый день.", [], candidates, "ru")
        assert "motion_verb" in _nuance_types(results)
        mv = next(c for c in results if c.lesson_data.get("nuance_type") == "motion_verb")
        assert mv.lesson_data["direction_type"] == "multidirectional"

    def test_motion_verb_partner_lemma(self, ext):
        candidates = [_vocab("идти", "идёт")]
        results = ext.extract_nuance("Он идёт.", [], candidates, "ru")
        mv = next(c for c in results if c.lesson_data.get("nuance_type") == "motion_verb")
        assert mv.lesson_data["partner_lemma"] == "ходить"

    def test_motion_verb_pair_relation_hint(self, ext):
        candidates = [_vocab("идти", "идёт")]
        results = ext.extract_nuance("Он идёт.", [], candidates, "ru")
        mv = next(c for c in results if c.lesson_data.get("nuance_type") == "motion_verb")
        relation_types = {h.relation_type for h in mv.relation_hints}
        assert "motion_pair" in relation_types

    def test_verbal_government_boidat(self, ext):
        candidates = [_vocab("бояться", "боится")]
        results = ext.extract_nuance("Он боится темноты.", [], candidates, "ru")
        assert "verbal_government" in _nuance_types(results)
        vg = next(c for c in results if c.lesson_data.get("nuance_type") == "verbal_government")
        assert vg.lesson_data["required_case"] == "genitive"

    def test_verbal_government_pomogat(self, ext):
        candidates = [_vocab("помогать", "помогает")]
        results = ext.extract_nuance("Он помогает другу.", [], candidates, "ru")
        vg = next(c for c in results if c.lesson_data.get("nuance_type") == "verbal_government")
        assert vg.lesson_data["required_case"] == "dative"

    def test_no_false_positive_on_unknown_verb(self, ext):
        candidates = [_vocab("думать", "думает")]
        results = ext.extract_nuance("Он думает.", [], candidates, "ru")
        assert "verbal_government" not in _nuance_types(results)
        assert "motion_verb" not in _nuance_types(results)

    def test_deduplication(self, ext):
        candidates = [_vocab("идти", "иду"), _vocab("идти", "идёшь")]
        results = ext.extract_nuance("", [], candidates, "ru")
        motion = [c for c in results if c.lesson_data.get("nuance_type") == "motion_verb"]
        assert len(motion) == 1


# ── Chinese ───────────────────────────────────────────────────────────────────

class TestChineseNuance:
    @pytest.fixture()
    def ext(self):
        return ChineseNuanceExtractor()

    def test_aspect_le(self, ext):
        # "他吃了三碗饭。"
        tokens = [_tok("他"), _tok("吃"), _tok("了"), _tok("三"), _tok("碗"), _tok("饭")]
        results = ext.extract_nuance("他吃了三碗饭。", tokens, [], "zh")
        assert "aspect_le" in _nuance_types(results)

    def test_aspect_guo(self, ext):
        tokens = [_tok("我"), _tok("去"), _tok("过"), _tok("北京")]
        results = ext.extract_nuance("我去过北京。", tokens, [], "zh")
        assert "aspect_guo" in _nuance_types(results)

    def test_aspect_zhe(self, ext):
        tokens = [_tok("他"), _tok("笑"), _tok("着"), _tok("说")]
        results = ext.extract_nuance("他笑着说。", tokens, [], "zh")
        assert "aspect_zhe" in _nuance_types(results)

    def test_measure_word_wan(self, ext):
        tokens = [_tok("三"), _tok("碗"), _tok("饭")]
        results = ext.extract_nuance("三碗饭", tokens, [], "zh")
        assert "measure_word" in _nuance_types(results)
        mw = next(c for c in results if c.lesson_data.get("nuance_type") == "measure_word")
        assert mw.lesson_data["measure_word"] == "碗"

    def test_measure_word_ge(self, ext):
        tokens = [_tok("两"), _tok("个"), _tok("人")]
        results = ext.extract_nuance("两个人", tokens, [], "zh")
        assert "measure_word" in _nuance_types(results)

    def test_chengyu_four_chars(self, ext):
        tokens = [_tok("他"), _tok("一石二鸟"), _tok("。")]
        results = ext.extract_nuance("他一石二鸟。", tokens, [], "zh")
        assert "chengyu" in _nuance_types(results)

    def test_chengyu_wrong_length_not_flagged(self, ext):
        tokens = [_tok("一石二"), _tok("鸟")]  # split into two tokens
        results = ext.extract_nuance("一石二鸟", tokens, [], "zh")
        assert "chengyu" not in _nuance_types(results)

    def test_deduplication(self, ext):
        tokens = [_tok("了"), _tok("了"), _tok("了")]
        results = ext.extract_nuance("了了了", tokens, [], "zh")
        le_nuances = [c for c in results if c.lesson_data.get("nuance_type") == "aspect_le"]
        assert len(le_nuances) == 1


# ── Japanese ─────────────────────────────────────────────────────────────────

class TestJapaneseNuance:
    @pytest.fixture()
    def ext(self):
        return JapaneseNuanceExtractor()

    def test_teineigo_masu(self, ext):
        tokens = [_tok("先生"), _tok("が"), _tok("おっしゃいます", lemma="おっしゃる")]
        results = ext.extract_nuance("先生がおっしゃいます。", tokens, [], "ja")
        assert "keigo" in _nuance_types(results)

    def test_sonkeigo_lemma(self, ext):
        tokens = [_tok("先生", lemma="先生"), _tok("が"), _tok("おっしゃった", lemma="おっしゃる")]
        results = ext.extract_nuance("先生がおっしゃった。", tokens, [], "ja")
        keigo = [c for c in results if c.lesson_data.get("nuance_type") == "keigo"]
        assert any(k.lesson_data.get("keigo_type") == "sonkeigo" for k in keigo)

    def test_kenjogo_lemma(self, ext):
        tokens = [_tok("私"), _tok("が"), _tok("いたします", lemma="いたす")]
        results = ext.extract_nuance("私がいたします。", tokens, [], "ja")
        keigo = [c for c in results if c.lesson_data.get("nuance_type") == "keigo"]
        assert any(k.lesson_data.get("keigo_type") == "kenjogo" for k in keigo)

    def test_particle_wa(self, ext):
        tokens = [_tok("私"), _tok("は"), _tok("学生")]
        results = ext.extract_nuance("私は学生です。", tokens, [], "ja")
        assert "particle" in _nuance_types(results)

    def test_particle_ga(self, ext):
        tokens = [_tok("猫"), _tok("が"), _tok("いる")]
        results = ext.extract_nuance("猫がいる。", tokens, [], "ja")
        assert "particle" in _nuance_types(results)

    def test_particle_wo(self, ext):
        tokens = [_tok("本"), _tok("を"), _tok("読む")]
        results = ext.extract_nuance("本を読む。", tokens, [], "ja")
        particles = [c for c in results if c.lesson_data.get("nuance_type") == "particle"]
        assert any(p.lesson_data.get("particle") == "を" for p in particles)

    def test_yojijukugo(self, ext):
        tokens = [_tok("彼は"), _tok("一期一会"), _tok("を"), _tok("大切にする")]
        results = ext.extract_nuance("彼は一期一会を大切にする。", tokens, [], "ja")
        assert "yojijukugo" in _nuance_types(results)

    def test_yojijukugo_not_in_list_not_flagged(self, ext):
        tokens = [_tok("ランダム")]  # random 5-char word not in list
        results = ext.extract_nuance("ランダム", tokens, [], "ja")
        assert "yojijukugo" not in _nuance_types(results)


# ── Arabic ────────────────────────────────────────────────────────────────────

class TestArabicNuance:
    @pytest.fixture()
    def ext(self):
        return ArabicNuanceExtractor()

    def test_definite_article_al(self, ext):
        # "الكتاب" starts with ال
        tokens = [_tok("الكتاب"), _tok("كبير")]
        results = ext.extract_nuance("الكتاب كبير", tokens, [], "ar")
        assert "definite_article" in _nuance_types(results)

    def test_definite_article_not_on_bare_word(self, ext):
        tokens = [_tok("كتاب")]  # no ال prefix
        results = ext.extract_nuance("كتاب", tokens, [], "ar")
        assert "definite_article" not in _nuance_types(results)

    def test_negation_lam(self, ext):
        # "لم يذهب"
        tokens = [_tok("لم"), _tok("يذهب")]
        results = ext.extract_nuance("لم يذهب", tokens, [], "ar")
        assert "negation_lam" in _nuance_types(results)

    def test_negation_la(self, ext):
        tokens = [_tok("لا"), _tok("أعرف")]
        results = ext.extract_nuance("لا أعرف", tokens, [], "ar")
        assert "negation_la" in _nuance_types(results)

    def test_negation_lan(self, ext):
        tokens = [_tok("لن"), _tok("يأتي")]
        results = ext.extract_nuance("لن يأتي", tokens, [], "ar")
        assert "negation_lan" in _nuance_types(results)

    def test_negation_laysa(self, ext):
        tokens = [_tok("ليس"), _tok("هذا"), _tok("صحيحاً")]
        results = ext.extract_nuance("ليس هذا صحيحاً", tokens, [], "ar")
        assert "negation_laysa" in _nuance_types(results)

    def test_root_pattern_from_candidate(self, ext):
        candidate = CandidateObject(
            canonical_form="كتب",
            type="vocabulary",
            label="كتب",
            lesson_data={"root": "ك-ت-ب", "form": "فَعَلَ"},
            confidence=0.80,
        )
        results = ext.extract_nuance("كَتَبَ", [], [candidate], "ar")
        assert "root_pattern" in _nuance_types(results)

    def test_root_pattern_no_root_no_fire(self, ext):
        candidate = CandidateObject(
            canonical_form="كتاب",
            type="vocabulary",
            label="كتاب",
            lesson_data={},
            confidence=0.80,
        )
        results = ext.extract_nuance("كتاب", [], [candidate], "ar")
        assert "root_pattern" not in _nuance_types(results)


# ── Hebrew ────────────────────────────────────────────────────────────────────

class TestHebrewNuance:
    @pytest.fixture()
    def ext(self):
        return HebrewNuanceExtractor()

    def test_definite_prefix_hakelev(self, ext):
        tokens = [_tok("הכלב"), _tok("גדול")]
        results = ext.extract_nuance("הכלב גדול", tokens, [], "he")
        assert "definite_prefix" in _nuance_types(results)

    def test_definite_prefix_no_he_no_fire(self, ext):
        tokens = [_tok("כלב")]  # no ה prefix
        results = ext.extract_nuance("כלב", tokens, [], "he")
        assert "definite_prefix" not in _nuance_types(results)

    def test_waw_conjunction(self, ext):
        tokens = [_tok("הוא"), _tok("והיא"), _tok("באו")]
        results = ext.extract_nuance("הוא והיא באו", tokens, [], "he")
        assert "waw_conjunction" in _nuance_types(results)

    def test_waw_too_short_not_flagged(self, ext):
        tokens = [_tok("ו")]  # single-char token
        results = ext.extract_nuance("ו", tokens, [], "he")
        assert "waw_conjunction" not in _nuance_types(results)

    def test_binyan_from_candidate(self, ext):
        candidate = CandidateObject(
            canonical_form="כתב",
            type="vocabulary",
            label="כתב",
            lesson_data={"binyan": "pa'al"},
            confidence=0.80,
        )
        results = ext.extract_nuance("כתב", [], [candidate], "he")
        assert "binyan" in _nuance_types(results)

    def test_binyan_no_binyan_no_fire(self, ext):
        candidate = CandidateObject(
            canonical_form="כתב",
            type="vocabulary",
            label="כתב",
            lesson_data={},
            confidence=0.80,
        )
        results = ext.extract_nuance("כתב", [], [candidate], "he")
        assert "binyan" not in _nuance_types(results)

    def test_biblical_register_cantillation(self, ext):
        # Sentence with cantillation (U+05C1 is within range)
        sentence = "בְּרֵאשִׁ֖ית"  # contains cantillation
        results = ext.extract_nuance(sentence, [], [], "he")
        assert "biblical_register" in _nuance_types(results)

    def test_no_biblical_without_cantillation(self, ext):
        sentence = "הוא הלך"  # no cantillation
        results = ext.extract_nuance(sentence, [], [], "he")
        assert "biblical_register" not in _nuance_types(results)


# ── Latin ─────────────────────────────────────────────────────────────────────

class TestLatinNuance:
    @pytest.fixture()
    def ext(self):
        return LatinNuanceExtractor()

    def test_discourse_particle_autem(self, ext):
        # "Caesar autem fortis erat."
        tokens = [_tok("Caesar"), _tok("autem"), _tok("fortis"), _tok("erat")]
        results = ext.extract_nuance("Caesar autem fortis erat.", tokens, [], "la")
        assert "discourse_particle" in _nuance_types(results)

    def test_discourse_particle_enim(self, ext):
        tokens = [_tok("enim"), _tok("fortis"), _tok("erat")]
        results = ext.extract_nuance("enim fortis erat", tokens, [], "la")
        assert "discourse_particle" in _nuance_types(results)

    def test_discourse_particle_tamen(self, ext):
        tokens = [_tok("tamen"), _tok("vincere"), _tok("potuit")]
        results = ext.extract_nuance("tamen vincere potuit", tokens, [], "la")
        assert "discourse_particle" in _nuance_types(results)

    def test_enclitic_que(self, ext):
        # "Senatus populusque Romanus"
        tokens = [_tok("Senatus"), _tok("populusque"), _tok("Romanus")]
        results = ext.extract_nuance("Senatus populusque Romanus", tokens, [], "la")
        assert "enclitic_que" in _nuance_types(results)

    def test_enclitic_que_host_word(self, ext):
        tokens = [_tok("armavirumque")]  # arma + virum + que
        results = ext.extract_nuance("armavirumque", tokens, [], "la")
        que = next(c for c in results if c.lesson_data.get("nuance_type") == "enclitic_que")
        assert que.lesson_data["host_word"] == "armavirum"

    def test_que_alone_not_enclitic(self, ext):
        tokens = [_tok("que")]
        results = ext.extract_nuance("que", tokens, [], "la")
        assert "enclitic_que" not in _nuance_types(results)

    def test_classical_register_macrons(self, ext):
        sentence = "Arma virumque canō, Trōiae quī prīmus ab ōrīs"
        results = ext.extract_nuance(sentence, [], [], "la")
        assert "classical_register" in _nuance_types(results)

    def test_no_classical_without_macrons(self, ext):
        sentence = "Arma virumque cano Troiae qui primus ab oris"
        results = ext.extract_nuance(sentence, [], [], "la")
        assert "classical_register" not in _nuance_types(results)

    def test_particle_confidence(self, ext):
        tokens = [_tok("autem")]
        results = ext.extract_nuance("autem", tokens, [], "la")
        p = next(c for c in results if c.lesson_data.get("nuance_type") == "discourse_particle")
        assert p.confidence == pytest.approx(0.85)


# ── Ancient Greek ─────────────────────────────────────────────────────────────

class TestAncientGreekNuance:
    @pytest.fixture()
    def ext(self):
        return AncientGreekNuanceExtractor()

    def test_particle_de(self, ext):
        # "ὁ δὲ λόγος" — δὲ normalizes to δε
        tokens = [_tok("ὁ"), _tok("δὲ"), _tok("λόγος")]
        results = ext.extract_nuance("ὁ δὲ λόγος", tokens, [], "grc")
        assert "discourse_particle" in _nuance_types(results)

    def test_particle_gar(self, ext):
        tokens = [_tok("γάρ")]
        results = ext.extract_nuance("γάρ", tokens, [], "grc")
        assert "discourse_particle" in _nuance_types(results)

    def test_particle_oun(self, ext):
        tokens = [_tok("οὖν")]
        results = ext.extract_nuance("οὖν", tokens, [], "grc")
        assert "discourse_particle" in _nuance_types(results)

    def test_negation_ou(self, ext):
        tokens = [_tok("οὐκ"), _tok("οἶδα")]
        results = ext.extract_nuance("οὐκ οἶδα", tokens, [], "grc")
        assert "negation_ou" in _nuance_types(results)

    def test_negation_me(self, ext):
        tokens = [_tok("μὴ"), _tok("ποιεῖτε")]
        results = ext.extract_nuance("μὴ ποιεῖτε τοῦτο", tokens, [], "grc")
        assert "negation_me" in _nuance_types(results)

    def test_article_ho(self, ext):
        # "ὁ" normalizes to "ο"
        tokens = [_tok("ὁ"), _tok("λόγος")]
        results = ext.extract_nuance("ὁ λόγος", tokens, [], "grc")
        assert "definite_article" in _nuance_types(results)

    def test_article_deduplication(self, ext):
        tokens = [_tok("ὁ"), _tok("καὶ"), _tok("ἡ"), _tok("καὶ"), _tok("τό")]
        results = ext.extract_nuance("ὁ καὶ ἡ καὶ τό", tokens, [], "grc")
        articles = [c for c in results if c.lesson_data.get("nuance_type") == "definite_article"]
        assert len(articles) == 1

    def test_particle_kai(self, ext):
        tokens = [_tok("καὶ"), _tok("αὐτὸς")]
        results = ext.extract_nuance("καὶ αὐτὸς", tokens, [], "grc")
        assert "discourse_particle" in _nuance_types(results)

    def test_type_is_nuance(self, ext):
        tokens = [_tok("δὲ")]
        results = ext.extract_nuance("δὲ", tokens, [], "grc")
        assert all(c.type == "nuance" for c in results)


# ── Registry ──────────────────────────────────────────────────────────────────

class TestRegistry:
    @pytest.mark.parametrize("lang", [
        "en", "es", "fr", "de", "ru", "zh", "ja", "ar", "he", "la", "grc",
    ])
    def test_get_extractor_returns_extractor(self, lang):
        ext = get_extractor(lang)
        assert ext is not None
        assert isinstance(ext, NuanceExtractor)

    def test_unknown_language_returns_none(self):
        assert get_extractor("xx") is None

    def test_extractor_language_attribute(self):
        ext = get_extractor("es")
        assert ext.language == "es"

    def test_registry_is_cached(self):
        a = get_extractor("de")
        b = get_extractor("de")
        assert a is b
