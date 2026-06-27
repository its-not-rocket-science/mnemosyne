from backend.lesson_extraction import enrich
from backend.schemas.parse import CandidateObject, CandidateSentenceResult


def test_enrich_is_non_destructive_for_unknown_language():
    sent = CandidateSentenceResult(
        text="hello world",
        candidates=[
            CandidateObject(
                canonical_form="hello",
                type="vocabulary",
                label="hello",
                lesson_data={"lemma": "hello", "pos": "WORD"},
                confidence=0.8,
            )
        ],
    )

    out = enrich("xx", [sent], capabilities=None)

    assert len(out) == 1
    assert len(out[0].candidates) == 1
    assert out[0].candidates[0].canonical_form == "hello"
    assert "pedagogy" in out[0].candidates[0].lesson_data


def test_chinese_derives_particle_grammar():
    sent = CandidateSentenceResult(
        text="我吃了饭。",
        candidates=[
            CandidateObject(
                canonical_form="吃",
                type="vocabulary",
                label="吃",
                surface_form="吃",
                lesson_data={"lemma": "吃", "pos": "VERB", "hsk_level": 1},
                confidence=0.8,
            )
        ],
    )

    out = enrich("zh", [sent], capabilities=None)
    types = {(c.type, c.lesson_data.get("grammar_type")) for c in out[0].candidates}

    assert ("grammar", "aspect_particle_le") in types


def test_arabic_derives_root_pattern_when_form_present():
    sent = CandidateSentenceResult(
        text="كَتَّبَ",
        candidates=[
            CandidateObject(
                canonical_form="كتب",
                type="vocabulary",
                label="كَتَّبَ",
                surface_form="كَتَّبَ",
                lesson_data={"lemma": "كتب", "root": "كتب", "verb_form": "form-ii"},
                confidence=0.8,
            )
        ],
    )

    out = enrich("ar", [sent], capabilities=None)

    assert any(c.type == "grammar" and c.lesson_data.get("grammar_type") == "root_pattern" for c in out[0].candidates)


def test_japanese_derives_particle_grammar():
    sent = CandidateSentenceResult(
        text="私は本を読む。",
        candidates=[
            CandidateObject(
                canonical_form="読む",
                type="vocabulary",
                label="読む",
                surface_form="読む",
                lesson_data={"lemma": "読む", "pos": "VERB"},
                confidence=0.8,
            )
        ],
    )

    out = enrich("ja", [sent], capabilities=None)
    skills = {c.lesson_data.get("grammar_type") for c in out[0].candidates if c.type == "grammar"}

    assert "topic_particle_wa" in skills
    assert "object_particle_o" in skills
