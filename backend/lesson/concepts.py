"""Deterministic grammar concept explanation catalogue.

All entries are authored here — no LLM call at runtime.  Each concept has
a base record plus optional language-specific and L1-comparison notes.

Usage::

    from backend.lesson.concepts import resolve_concept

    c = resolve_concept("axis.tense")
    c = resolve_concept("tense.imperfect", language_code="es", l1_language="en")
    c = resolve_concept("unknown.xyz")   # → None
"""
from __future__ import annotations

from copy import deepcopy

from backend.schemas.lesson import GrammarConceptExplanation

# ── Base catalogue ────────────────────────────────────────────────────────────
# Maps concept_id → dict of constructor kwargs (without target_language_note
# and l1_comparison — those are injected by resolve_concept).

_BASE: dict[str, dict] = {

    # ── Axis concepts ─────────────────────────────────────────────────────────

    "axis.lemma": dict(
        concept_id="axis.lemma",
        axis="lemma",
        title="Lemma",
        short_definition="The dictionary citation form of a word.",
        learner_explanation=(
            "The lemma is the base form you look up in a dictionary — for verbs "
            "it is the infinitive; for nouns the singular nominative. Surface forms "
            "in real text are inflected versions of the lemma."
        ),
        examples=["hablar", "casa", "laufen", "быть"],
        related_concepts=["axis.surface_form"],
        practice_tags=["lemma_recall"],
    ),

    "axis.surface_form": dict(
        concept_id="axis.surface_form",
        axis="surface_form",
        title="Surface form",
        short_definition="The word exactly as it appears in the text.",
        learner_explanation=(
            "The surface form is the inflected word as written. It may differ "
            "from the lemma because of tense, number, case, or agreement changes."
        ),
        examples=["hablo", "casas", "lief", "были"],
        related_concepts=["axis.lemma"],
        practice_tags=["form_recall"],
    ),

    "axis.part_of_speech": dict(
        concept_id="axis.part_of_speech",
        axis="part_of_speech",
        title="Part of speech",
        short_definition="The grammatical category of a word (noun, verb, adjective, …).",
        learner_explanation=(
            "Part of speech tells you what role a word plays: nouns name things, "
            "verbs describe actions or states, adjectives modify nouns, adverbs "
            "modify verbs or adjectives."
        ),
        examples=["NOUN: casa", "VERB: correr", "ADJ: rápido", "ADV: rápidamente"],
        related_concepts=["pos.noun", "pos.verb", "pos.adjective"],
        practice_tags=["pos_recognition"],
    ),

    "axis.tense": dict(
        concept_id="axis.tense",
        axis="tense",
        title="Tense",
        short_definition="When an action or state occurs relative to the moment of speaking.",
        learner_explanation=(
            "Tense locates an event in time. Most languages mark at least past, "
            "present, and future, though many languages express time through "
            "context rather than verb endings."
        ),
        examples=["present: I speak", "past: I spoke", "future: I will speak"],
        related_concepts=["axis.aspect", "axis.mood",
                          "tense.present", "tense.preterite", "tense.imperfect"],
        practice_tags=["tense_recognition", "tense_production"],
    ),

    "axis.mood": dict(
        concept_id="axis.mood",
        axis="mood",
        title="Mood",
        short_definition="Whether the verb expresses fact, doubt, command, or conditionality.",
        learner_explanation=(
            "Mood signals the speaker's attitude toward the action. The indicative "
            "states facts; the subjunctive expresses doubt, wishes, or hypotheticals; "
            "the imperative gives commands."
        ),
        examples=["indicative: she comes", "subjunctive: I hope she comes",
                  "imperative: Come here!"],
        related_concepts=["mood.indicative", "mood.subjunctive", "mood.imperative",
                          "axis.tense"],
        practice_tags=["mood_recognition"],
    ),

    "axis.person": dict(
        concept_id="axis.person",
        axis="person",
        title="Person",
        short_definition="Whether the verb refers to the speaker (1st), addressee (2nd), or other (3rd).",
        learner_explanation=(
            "Person marks the grammatical subject. First person is I/we, second "
            "person is you, third person is he/she/they. Many languages encode "
            "person in the verb ending, so a pronoun is optional."
        ),
        examples=["1st: (yo) hablo", "2nd: (tú) hablas", "3rd: (él) habla"],
        related_concepts=["person.first", "person.second", "person.third",
                          "axis.number"],
        practice_tags=["person_recognition"],
    ),

    "axis.number": dict(
        concept_id="axis.number",
        axis="number",
        title="Number",
        short_definition="Whether a word refers to one thing (singular) or more than one (plural).",
        learner_explanation=(
            "Grammatical number affects nouns, pronouns, and often verbs and "
            "adjectives. Languages vary in how strictly they mark number — "
            "some (like Chinese) do not inflect at all."
        ),
        examples=["singular: cat / gato", "plural: cats / gatos"],
        related_concepts=["number.singular", "number.plural", "axis.gender"],
        practice_tags=["number_recognition"],
    ),

    "axis.gender": dict(
        concept_id="axis.gender",
        axis="gender",
        title="Grammatical gender",
        short_definition="A noun-class system that affects agreement with articles, adjectives, and pronouns.",
        learner_explanation=(
            "Grammatical gender is a classification system for nouns. It is not "
            "about biological sex — it is a property that forces other words in "
            "the sentence to change their form to match."
        ),
        examples=["masc: el libro", "fem: la casa", "neut: das Kind"],
        related_concepts=["gender.masculine", "gender.feminine", "gender.neuter",
                          "axis.number"],
        practice_tags=["gender_recognition"],
    ),

    "axis.case": dict(
        concept_id="axis.case",
        axis="case",
        title="Case",
        short_definition="A grammatical marker showing the role a noun plays in its clause.",
        learner_explanation=(
            "Case is marked on nouns and pronouns to show whether they are "
            "subjects, objects, possessors, or recipients. Latin, Russian, German, "
            "and Greek use case endings; English mainly uses word order."
        ),
        examples=["nominative (subject)", "accusative (direct object)",
                  "dative (indirect object)", "genitive (possessor)"],
        related_concepts=["axis.number", "axis.gender"],
        practice_tags=["case_recognition"],
    ),

    "axis.aspect": dict(
        concept_id="axis.aspect",
        axis="aspect",
        title="Aspect",
        short_definition="Whether an action is seen as complete (perfective) or ongoing/habitual (imperfective).",
        learner_explanation=(
            "Aspect describes how the speaker views an action's internal structure. "
            "The perfective sees the action as a bounded whole; the imperfective "
            "sees it as ongoing, repeated, or in progress. Aspect is distinct "
            "from tense: both are often expressed together."
        ),
        examples=["perfective: she wrote (finished)", "imperfective: she was writing (in progress)"],
        related_concepts=["aspect.perfective", "aspect.imperfective", "axis.tense"],
        practice_tags=["aspect_recognition"],
    ),

    "axis.voice": dict(
        concept_id="axis.voice",
        axis="voice",
        title="Voice",
        short_definition="Whether the subject performs (active) or receives (passive) the action.",
        learner_explanation=(
            "In the active voice the subject does the action. In the passive voice "
            "the subject receives it. Some languages also have a middle voice "
            "where the subject acts on itself or for its own benefit."
        ),
        examples=["active: the cat caught the mouse",
                  "passive: the mouse was caught by the cat"],
        related_concepts=["axis.mood"],
        practice_tags=[],
    ),

    "axis.romanized": dict(
        concept_id="axis.romanized",
        axis="romanized",
        title="Romanization",
        short_definition="A phonetic spelling of a word using the Latin alphabet.",
        learner_explanation=(
            "Romanization converts a non-Latin script into Latin letters to help "
            "with pronunciation. It is a learning aid — communication in the "
            "target language should use the original script."
        ),
        examples=["pinyin for Chinese: 学习 → xué xí",
                  "romaji for Japanese: 学校 → gakkō",
                  "transliteration for Russian: привет → privet"],
        related_concepts=[],
        practice_tags=[],
    ),

    "axis.construction": dict(
        concept_id="axis.construction",
        axis="construction",
        title="Construction",
        short_definition="A multi-word grammatical pattern that functions as a unit.",
        learner_explanation=(
            "A construction is a fixed or semi-fixed pattern with a grammatical "
            "function — like a periphrastic tense (estar + gerund) or a modal "
            "verb phrase. Constructions should be learned as wholes."
        ),
        examples=["estar + gerund (Spanish progressive)",
                  "sein + Partizip II (German perfect)"],
        related_concepts=["axis.tense", "axis.mood"],
        practice_tags=[],
    ),

    # ── Tense values ──────────────────────────────────────────────────────────

    "tense.present": dict(
        concept_id="tense.present",
        axis="tense", value="present",
        title="Present tense",
        short_definition="Expresses current actions, states, or general truths.",
        learner_explanation=(
            "The present tense describes what is happening now, habitual actions, "
            "or permanent truths. In many languages it is also used for scheduled "
            "future events."
        ),
        examples=["I speak / hablo", "the sun rises every day"],
        related_concepts=["tense.preterite", "tense.imperfect", "axis.tense"],
        practice_tags=["tense_recognition"],
    ),

    "tense.preterite": dict(
        concept_id="tense.preterite",
        axis="tense", value="preterite",
        title="Preterite",
        short_definition="A past tense marking a completed, bounded event.",
        learner_explanation=(
            "The preterite (simple past) reports an action that started and ended "
            "in the past. It answers 'what happened?'. It contrasts with the "
            "imperfect, which describes ongoing or habitual past states."
        ),
        examples=["She arrived yesterday.", "Ayer llegó."],
        related_concepts=["tense.imperfect", "axis.aspect", "axis.tense"],
        practice_tags=["tense_recognition", "preterite_vs_imperfect"],
    ),

    "tense.imperfect": dict(
        concept_id="tense.imperfect",
        axis="tense", value="imperfect",
        title="Imperfect",
        short_definition="A past tense for ongoing, habitual, or background states.",
        learner_explanation=(
            "The imperfect describes a past action that was in progress, repeated, "
            "or habitual — it does not mark a clear start or end. It is the "
            "storytelling background tense, setting the scene for completed events."
        ),
        examples=["She was running when I called.", "Cuando era niño, comía mucho."],
        related_concepts=["tense.preterite", "axis.aspect", "axis.tense"],
        practice_tags=["tense_recognition", "preterite_vs_imperfect"],
    ),

    "tense.future": dict(
        concept_id="tense.future",
        axis="tense", value="future",
        title="Future tense",
        short_definition="Expresses actions or states that will happen after the present moment.",
        learner_explanation=(
            "The future tense describes what will happen. Some languages use a "
            "dedicated inflection; others use auxiliary verbs or present tense "
            "with a future time adverb."
        ),
        examples=["I will speak / hablaré / je parlerai"],
        related_concepts=["tense.present", "tense.conditional", "axis.tense"],
        practice_tags=["tense_recognition"],
    ),

    "tense.conditional": dict(
        concept_id="tense.conditional",
        axis="tense", value="conditional",
        title="Conditional",
        short_definition="Expresses what would happen under certain conditions.",
        learner_explanation=(
            "The conditional describes hypothetical outcomes ('I would speak'). "
            "It often appears in if-clauses alongside the subjunctive."
        ),
        examples=["I would speak / hablaría / je parlerais"],
        related_concepts=["tense.future", "mood.subjunctive", "axis.mood"],
        practice_tags=["tense_recognition"],
    ),

    # ── Mood values ───────────────────────────────────────────────────────────

    "mood.indicative": dict(
        concept_id="mood.indicative",
        axis="mood", value="indicative",
        title="Indicative mood",
        short_definition="The default mood for stating facts and real-world events.",
        learner_explanation=(
            "Use the indicative when you are asserting something as fact or "
            "reporting a real event. It is the most common mood."
        ),
        examples=["She speaks Spanish.", "El tren llegó a las diez."],
        related_concepts=["mood.subjunctive", "mood.imperative", "axis.mood"],
        practice_tags=["mood_recognition"],
    ),

    "mood.subjunctive": dict(
        concept_id="mood.subjunctive",
        axis="mood", value="subjunctive",
        title="Subjunctive mood",
        short_definition="Expresses doubt, wishes, hypotheticals, or subordinate clauses of emotion.",
        learner_explanation=(
            "The subjunctive appears in subordinate clauses that express "
            "uncertainty, desire, emotion, or condition. It is triggered by "
            "verbs and expressions like 'I want that…', 'it is important that…', "
            "or 'although…'."
        ),
        examples=["Quiero que hables.", "Il faut que tu viennes."],
        related_concepts=["mood.indicative", "tense.imperfect", "axis.mood"],
        practice_tags=["mood_recognition", "subjunctive_triggers"],
    ),

    "mood.imperative": dict(
        concept_id="mood.imperative",
        axis="mood", value="imperative",
        title="Imperative mood",
        short_definition="Used to give commands, instructions, or requests.",
        learner_explanation=(
            "The imperative tells someone to do something. It typically uses "
            "a special verb form. Negated imperatives (prohibitions) may use "
            "a different form from affirmative ones."
        ),
        examples=["Habla más despacio.", "Parle plus lentement.", "Sprich langsamer."],
        related_concepts=["mood.indicative", "axis.mood"],
        practice_tags=["mood_recognition"],
    ),

    # ── Person values ─────────────────────────────────────────────────────────

    "person.first": dict(
        concept_id="person.first",
        axis="person", value="first",
        title="First person",
        short_definition="The speaker (I / we).",
        learner_explanation="First person refers to the person speaking: I (singular) or we (plural).",
        examples=["I speak / yo hablo / je parle", "We speak / nosotros hablamos"],
        related_concepts=["person.second", "person.third", "axis.number"],
        practice_tags=["person_recognition"],
    ),

    "person.second": dict(
        concept_id="person.second",
        axis="person", value="second",
        title="Second person",
        short_definition="The addressee (you).",
        learner_explanation=(
            "Second person refers to the person being spoken to. Many languages "
            "have formal and informal second-person forms."
        ),
        examples=["you speak / tú hablas / vous parlez"],
        related_concepts=["person.first", "person.third"],
        practice_tags=["person_recognition"],
    ),

    "person.third": dict(
        concept_id="person.third",
        axis="person", value="third",
        title="Third person",
        short_definition="Someone or something other than the speaker or addressee (he/she/it/they).",
        learner_explanation=(
            "Third person refers to anyone or anything that is neither the speaker "
            "nor the direct addressee."
        ),
        examples=["she speaks / ella habla / elle parle"],
        related_concepts=["person.first", "person.second"],
        practice_tags=["person_recognition"],
    ),

    # ── Number values ─────────────────────────────────────────────────────────

    "number.singular": dict(
        concept_id="number.singular",
        axis="number", value="singular",
        title="Singular",
        short_definition="Referring to exactly one entity.",
        learner_explanation="Singular forms refer to one person, thing, or concept.",
        examples=["cat / gato / chat", "I speak / yo hablo"],
        related_concepts=["number.plural", "axis.number"],
        practice_tags=["number_recognition"],
    ),

    "number.plural": dict(
        concept_id="number.plural",
        axis="number", value="plural",
        title="Plural",
        short_definition="Referring to more than one entity.",
        learner_explanation=(
            "Plural forms refer to more than one person, thing, or concept. "
            "They often require agreement changes on verbs, adjectives, and articles."
        ),
        examples=["cats / gatos / chats", "we speak / nosotros hablamos"],
        related_concepts=["number.singular", "axis.number"],
        practice_tags=["number_recognition"],
    ),

    # ── Gender values ─────────────────────────────────────────────────────────

    "gender.masculine": dict(
        concept_id="gender.masculine",
        axis="gender", value="masculine",
        title="Masculine",
        short_definition="The masculine grammatical gender class.",
        learner_explanation=(
            "Masculine is one of the grammatical gender classes. It is not "
            "necessarily related to biological sex — many inanimate nouns are "
            "masculine. Articles, adjectives, and pronouns must agree."
        ),
        examples=["el libro (the book)", "le livre", "der Mann"],
        related_concepts=["gender.feminine", "gender.neuter", "axis.gender"],
        practice_tags=["gender_recognition"],
    ),

    "gender.feminine": dict(
        concept_id="gender.feminine",
        axis="gender", value="feminine",
        title="Feminine",
        short_definition="The feminine grammatical gender class.",
        learner_explanation=(
            "Feminine is one of the grammatical gender classes. Like masculine, "
            "it is a grammatical convention — many inanimate nouns are feminine."
        ),
        examples=["la casa (the house)", "la maison", "die Frau"],
        related_concepts=["gender.masculine", "gender.neuter", "axis.gender"],
        practice_tags=["gender_recognition"],
    ),

    "gender.neuter": dict(
        concept_id="gender.neuter",
        axis="gender", value="neuter",
        title="Neuter",
        short_definition="The neuter grammatical gender class (used in German, Russian, Greek, and others).",
        learner_explanation=(
            "Neuter is a third gender class found in languages like German, "
            "Russian, and Greek. It does not imply neutrality about biological "
            "sex — it is simply a noun class."
        ),
        examples=["das Kind (the child)", "окно (window) in Russian"],
        related_concepts=["gender.masculine", "gender.feminine", "axis.gender"],
        practice_tags=["gender_recognition"],
    ),

    # ── Aspect values ─────────────────────────────────────────────────────────

    "aspect.perfective": dict(
        concept_id="aspect.perfective",
        axis="aspect", value="perfective",
        title="Perfective aspect",
        short_definition="Views the action as a completed, bounded whole.",
        learner_explanation=(
            "Perfective verbs present the action as finished, achieved, or "
            "instantaneous. In Slavic languages, choosing perfective vs "
            "imperfective changes meaning significantly."
        ),
        examples=["написать (to write — perfective, finished)",
                  "she wrote the letter (and finished)"],
        related_concepts=["aspect.imperfective", "axis.aspect"],
        practice_tags=["aspect_recognition"],
    ),

    "aspect.imperfective": dict(
        concept_id="aspect.imperfective",
        axis="aspect", value="imperfective",
        title="Imperfective aspect",
        short_definition="Views the action as ongoing, habitual, or without a defined boundary.",
        learner_explanation=(
            "Imperfective verbs present the action as ongoing, repeated, or not "
            "yet completed. In Slavic languages they are the default/unmarked form."
        ),
        examples=["писать (to write — imperfective, ongoing)",
                  "she was writing (in progress)"],
        related_concepts=["aspect.perfective", "axis.aspect"],
        practice_tags=["aspect_recognition"],
    ),

    # ── POS values ────────────────────────────────────────────────────────────

    "pos.noun": dict(
        concept_id="pos.noun",
        axis="part_of_speech", value="noun",
        title="Noun",
        short_definition="A word that names a person, place, thing, or concept.",
        learner_explanation=(
            "Nouns are the main naming words in a sentence. They can be subjects, "
            "objects, or complements. In many languages, nouns carry gender and "
            "change form depending on number and case."
        ),
        examples=["casa (house)", "Hund (dog)", "liberté (freedom)"],
        related_concepts=["axis.gender", "axis.number", "axis.case",
                          "axis.part_of_speech"],
        practice_tags=["pos_recognition"],
    ),

    "pos.verb": dict(
        concept_id="pos.verb",
        axis="part_of_speech", value="verb",
        title="Verb",
        short_definition="A word that describes an action, occurrence, or state of being.",
        learner_explanation=(
            "Verbs are the core of a clause. They conjugate to agree with their "
            "subject and carry tense, mood, aspect, and voice information."
        ),
        examples=["hablar (to speak)", "sein (to be)", "courir (to run)"],
        related_concepts=["axis.tense", "axis.mood", "axis.person", "axis.aspect",
                          "axis.part_of_speech"],
        practice_tags=["pos_recognition"],
    ),

    "pos.adjective": dict(
        concept_id="pos.adjective",
        axis="part_of_speech", value="adjective",
        title="Adjective",
        short_definition="A word that modifies a noun by describing a quality or attribute.",
        learner_explanation=(
            "Adjectives modify nouns. In languages with grammatical gender and "
            "case they often agree with the noun they modify."
        ),
        examples=["rojo (red)", "groß (big)", "beau (beautiful)"],
        related_concepts=["axis.gender", "axis.number", "pos.noun",
                          "axis.part_of_speech"],
        practice_tags=["pos_recognition"],
    ),

    "pos.adverb": dict(
        concept_id="pos.adverb",
        axis="part_of_speech", value="adverb",
        title="Adverb",
        short_definition="A word that modifies a verb, adjective, or other adverb.",
        learner_explanation=(
            "Adverbs answer questions like how, when, where, or to what degree. "
            "Unlike adjectives, they typically do not inflect for gender or case."
        ),
        examples=["rápidamente (quickly)", "sehr (very)", "hier (here)"],
        related_concepts=["pos.adjective", "axis.part_of_speech"],
        practice_tags=["pos_recognition"],
    ),

    "pos.auxiliary_verb": dict(
        concept_id="pos.auxiliary_verb",
        axis="part_of_speech", value="auxiliary verb",
        title="Auxiliary verb",
        short_definition="A helping verb used to form compound tenses, moods, or voices.",
        learner_explanation=(
            "Auxiliary verbs combine with main verbs to express tense, mood, or "
            "voice. Common auxiliaries include 'have', 'be', 'will', and their "
            "equivalents in other languages."
        ),
        examples=["haber + participio (Spanish perfect)",
                  "avoir + participe passé (French perfect)",
                  "haben/sein + Partizip (German Perfekt)"],
        related_concepts=["pos.verb", "axis.tense", "axis.voice"],
        practice_tags=["pos_recognition"],
    ),

    "pos.proper_noun": dict(
        concept_id="pos.proper_noun",
        axis="part_of_speech", value="proper noun",
        title="Proper noun",
        short_definition="A noun that names a specific individual, place, or organization.",
        learner_explanation=(
            "Proper nouns name unique entities. They are typically capitalised "
            "and do not take an article in many languages, though exceptions exist."
        ),
        examples=["Madrid", "Beethoven", "Mnemosyne"],
        related_concepts=["pos.noun", "axis.part_of_speech"],
        practice_tags=[],
    ),

    # ── Chinese-specific concepts ─────────────────────────────────────────────

    "zh.word_segmentation": dict(
        concept_id="zh.word_segmentation",
        title="Word segmentation",
        short_definition="Splitting a Chinese text into individual words, which are not separated by spaces.",
        learner_explanation=(
            "Written Chinese uses no spaces between words. Segmentation is the "
            "process of identifying where one word ends and another begins. "
            "This is non-trivial because the same characters can combine in "
            "different ways depending on context."
        ),
        examples=["他也来了 → 他 / 也 / 来了"],
        related_concepts=["zh.pinyin"],
        practice_tags=[],
    ),

    "zh.pinyin": dict(
        concept_id="zh.pinyin",
        title="Pinyin",
        short_definition="The standard romanization system for Mandarin Chinese.",
        learner_explanation=(
            "Pinyin writes Chinese sounds using the Latin alphabet with tone "
            "marks (ā á ǎ à). It is the primary learning aid for pronunciation "
            "but is not used in ordinary writing."
        ),
        examples=["学习 → xué xí", "你好 → nǐ hǎo"],
        related_concepts=["axis.romanized", "zh.word_segmentation"],
        practice_tags=[],
    ),

    "zh.aspect_particle.le": dict(
        concept_id="zh.aspect_particle.le",
        title="了 (le) — completion particle",
        short_definition="Marks a completed action or a changed state.",
        learner_explanation=(
            "了 (le) appears after a verb to show the action has been completed, "
            "or at the end of a sentence to signal a change in situation. "
            "It does not correspond directly to past tense — the time must be "
            "inferred from context."
        ),
        examples=["我吃了。(I have eaten.)", "天黑了。(It has gotten dark.)"],
        related_concepts=["zh.aspect_particle.guo", "zh.aspect_particle.zhe"],
        practice_tags=["zh_particle"],
    ),

    "zh.aspect_particle.guo": dict(
        concept_id="zh.aspect_particle.guo",
        title="过 (guò) — experiential particle",
        short_definition="Marks an action that has been experienced at some point in the past.",
        learner_explanation=(
            "过 indicates that the speaker (or subject) has the life experience "
            "of doing something. It focuses on the experience, not the result."
        ),
        examples=["我去过北京。(I have been to Beijing — I have that experience.)"],
        related_concepts=["zh.aspect_particle.le", "zh.aspect_particle.zhe"],
        practice_tags=["zh_particle"],
    ),

    "zh.aspect_particle.zhe": dict(
        concept_id="zh.aspect_particle.zhe",
        title="着 (zhe) — continuous/durative particle",
        short_definition="Marks an ongoing state or action used as a background.",
        learner_explanation=(
            "着 indicates that an action or state is continuing. It often appears "
            "in subordinate clauses describing simultaneous background activity."
        ),
        examples=["他坐着看书。(He sat reading — while sitting he read.)"],
        related_concepts=["zh.aspect_particle.le", "zh.aspect_particle.guo"],
        practice_tags=["zh_particle"],
    ),

    "zh.structural_particle.de": dict(
        concept_id="zh.structural_particle.de",
        title="的/地/得 (de) — structural particles",
        short_definition="Three homophones that link modifiers to nouns, adverbs to verbs, or indicate manner/degree.",
        learner_explanation=(
            "的 links an attribute to a noun (noun/adjective + 的 + noun). "
            "地 links an adverb to a verb. 得 links a verb to a degree complement. "
            "They are all pronounced the same but written differently."
        ),
        examples=["漂亮的书 (beautiful book — 的)",
                  "快乐地跑 (happily ran — 地)",
                  "跑得很快 (ran very fast — 得)"],
        related_concepts=["zh.classifier"],
        practice_tags=["zh_particle"],
    ),

    "zh.classifier": dict(
        concept_id="zh.classifier",
        title="Classifier / measure word",
        short_definition="A word that must appear between a numeral and a noun in Chinese.",
        learner_explanation=(
            "Chinese requires a classifier between a number and the noun it "
            "counts. Different classifiers apply to different categories of "
            "noun (flat objects, long thin objects, abstract items, etc.). "
            "The most common general classifier is 个 (gè)."
        ),
        examples=["一个人 (one person — 个)", "两本书 (two books — 本)",
                  "三条鱼 (three fish — 条)"],
        related_concepts=["zh.structural_particle.de"],
        practice_tags=["zh_classifier"],
    ),
}

# ── Language-specific note injections ────────────────────────────────────────
# Maps (concept_id, language_code) → target_language_note string.
# Maps (concept_id, l1_language)  → l1_comparison string.

_LANG_NOTES: dict[tuple[str, str], str] = {
    ("tense.imperfect", "es"): (
        "In Spanish the imperfect (imperfecto) has regular -AR/-ER/-IR endings "
        "with very few irregulars (ser, ir, ver). Use it for background description, "
        "habitual actions, ongoing states, and polite requests."
    ),
    ("tense.imperfect", "fr"): (
        "In French the imparfait has regular endings (-ais, -ais, -ait, -ions, -iez, -aient) "
        "for nearly all verbs. It describes ongoing or habitual past actions."
    ),
    ("mood.subjunctive", "es"): (
        "Spanish subjunctive is triggered by WEIRDO verbs: Wishes, Emotions, Impersonal expressions, "
        "Recommendations/Requests, Doubts/Denial, and Ojalá/Ojala. "
        "Present subjunctive uses present indicative first-person minus -o plus opposite vowel endings."
    ),
    ("mood.subjunctive", "fr"): (
        "French subjunctive is required after expressions of doubt, emotion, necessity "
        "and in some subordinate clauses. Formation: third-person plural present stem + "
        "-e, -es, -e, -ions, -iez, -ent."
    ),
    ("axis.gender", "es"): (
        "In Spanish most nouns ending in -o are masculine (el libro) and most ending "
        "in -a are feminine (la casa), but many common exceptions exist (el día, la mano). "
        "Adjectives add -a for feminine: blanco → blanca."
    ),
    ("axis.gender", "de"): (
        "German has three genders (der/die/das). Gender must be memorised with each noun "
        "as there are few reliable rules. Endings -ung, -heit, -keit are always feminine; "
        "-chen, -lein are always neuter."
    ),
    ("axis.romanized", "zh"): (
        "For Chinese this shows Hanyu Pinyin — the official romanization of Mandarin. "
        "Tones are marked: ā (1st), á (2nd), ǎ (3rd), à (4th), a (neutral). "
        "Pinyin is used in dictionaries, language learning, and input methods."
    ),
    ("zh.word_segmentation", "zh"): (
        "Mnemosyne uses jieba for word segmentation when available. "
        "The quality is reliable for standard modern prose but may struggle "
        "with literary or highly formal text."
    ),
}

_L1_COMPARISONS: dict[tuple[str, str], str] = {
    ("tense.imperfect", "en"): (
        "English has no direct equivalent. The imperfect typically translates to "
        "'was/were doing' (past continuous), 'used to do', or simply 'did' depending on context."
    ),
    ("mood.subjunctive", "en"): (
        "English has a vestigial subjunctive ('If I were you…', 'I suggest he leave'), "
        "but it is rarely marked. In Spanish and French it is obligatory in many clauses "
        "that English handles with different constructions."
    ),
    ("axis.gender", "en"): (
        "English lost grammatical gender centuries ago. English speakers learning a "
        "gendered language must memorise noun gender as part of vocabulary — it does "
        "not map to meaning."
    ),
    ("axis.case", "en"): (
        "English retains case only in pronouns (I/me/my, he/him/his). "
        "In languages like German or Russian, case endings appear on nouns, "
        "articles, and adjectives throughout the sentence."
    ),
    ("axis.aspect", "en"): (
        "English expresses aspect through auxiliary constructions ('was doing' vs 'did', "
        "'has done' vs 'did'). In Russian and other Slavic languages, aspect is a "
        "core grammatical category built into the verb stem."
    ),
    ("axis.romanized", "en"): (
        "For English learners, romanization is a bridge to reading the target script. "
        "Aim to transition to the native script as early as possible."
    ),
    ("zh.word_segmentation", "en"): (
        "Unlike English, Chinese text has no spaces between words. "
        "Understanding segmentation helps you identify word boundaries and "
        "look up words in a dictionary."
    ),
}


# ── Public API ────────────────────────────────────────────────────────────────

def resolve_concept(
    concept_id: str,
    language_code: str | None = None,
    l1_language: str = "en",
    lesson_data: dict | None = None,
) -> GrammarConceptExplanation | None:
    """Return a ``GrammarConceptExplanation`` for *concept_id*, or ``None``.

    Parameters
    ──────────
    concept_id
        A dotted concept identifier such as ``"axis.tense"`` or ``"tense.imperfect"``.
    language_code
        BCP-47 code of the target language (e.g. ``"es"``).  Used to inject
        language-specific notes where they exist.
    l1_language
        BCP-47 code of the learner's first language (default ``"en"``).  Used
        to inject L1-comparison notes.
    lesson_data
        Optional raw ``lesson_data`` dict for the current lesson object.
        Reserved for future use (e.g. dynamic examples from the lesson).
    """
    base = _BASE.get(concept_id)
    if base is None:
        return None

    data = deepcopy(base)

    if language_code:
        note = _LANG_NOTES.get((concept_id, language_code))
        if note:
            data["target_language_note"] = note

    l1_cmp = _L1_COMPARISONS.get((concept_id, l1_language))
    if l1_cmp:
        data["l1_comparison"] = l1_cmp

    return GrammarConceptExplanation(**data)


def all_concept_ids() -> list[str]:
    """Return a sorted list of all registered concept IDs."""
    return sorted(_BASE.keys())
