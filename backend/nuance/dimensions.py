"""Cross-language nuance abstraction layer.

Defines shared dimension types and per-language nuance inventories.
An inventory lists every major nuance system a language exercises — not
just what the extractor currently covers, but what a learner *needs*
to understand to sound natural.

Usage::

    from backend.nuance.dimensions import get_inventory
    inv = get_inventory("ja")
    for system in inv:
        print(system.name, system.cefr_range)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

# ── Dimension taxonomy ────────────────────────────────────────────────────────

NuanceDimension = Literal[
    # Temporal / aspectual
    "aspect",           # perfective/imperfective, bounded/unbounded
    "tense",            # absolute tense, relative tense, tense-aspect fusion
    "aktionsart",       # lexical aspect (telicity, duration, punctuality)
    # Mood / modality
    "mood",             # indicative/subjunctive/conditional/optative
    "evidentiality",    # source-of-information encoding
    "modality",         # necessity, possibility, permission
    # Register / pragmatics
    "formality",        # formal/informal/colloquial/archaic
    "politeness",       # honorific levels, speech styles
    "register",         # literary/spoken/written/specialist
    # Information structure
    "topic_focus",      # topic markers, focus particles
    "information_structure",  # given/new, contrastive focus
    # Argument structure
    "case",             # nominal case distinctions
    "valency",          # transitive/intransitive, causative
    "diathesis",        # active/passive/middle/reflexive/anticausative
    "argument_marking", # particle/preposition/case government
    # Nominal
    "definiteness",     # definite/indefinite/generic
    "number",           # singular/dual/plural/paucal
    "gender",           # grammatical gender assignment
    "classifier",       # measure words, numeral classifiers
    # Negation
    "negation",         # negation strategies (short/long, indicative/subjunctive)
    # Lexical / semantic
    "semantic_field",   # semantic contrasts within a lexical field
    "idiom",            # fixed expressions with non-compositional meaning
    "discourse_particle",  # pragmatic particles (German Modalpartikeln, etc.)
    "implicature",      # scalar implicature, conventional implicature
]


# ── Nuance system descriptor ──────────────────────────────────────────────────

@dataclass
class NuanceSystem:
    """Describes one nuance system for a language.

    Each system has a name, a primary dimension, a CEFR range, and
    a brief description of what the learner needs to understand.
    ``native_term`` is the language's own name for the system when one
    exists (e.g. 「敬語」 for Japanese honorifics).
    ``contrast_concept`` links to the canonical concept ID used in
    ``data/nuance/{lang}.json`` contrast datasets.
    """
    name: str
    """Short English name, e.g. "Perfective aspect"."""
    dimension: NuanceDimension
    cefr_range: tuple[str, str]
    """(min_cefr, max_cefr) — when this system becomes relevant/mastered."""
    description: str
    """One sentence from the learner's perspective."""
    native_term: str | None = None
    contrast_concept: str | None = None
    """Maps to a concept ID in the JSON data file if a contrast set exists."""
    discourse_effects: list[str] = field(default_factory=list)
    """What changes in meaning/register/implication when learner gets this wrong."""
    advanced_notes: str | None = None
    """C1/C2 stylistic, literary, or pragmatic notes."""


# ── Per-language inventory catalogs ──────────────────────────────────────────

_INVENTORIES: dict[str, list[NuanceSystem]] = {

    # ── Spanish ──────────────────────────────────────────────────────────────
    "es": [
        NuanceSystem(
            name="Ser vs Estar",
            dimension="mood",
            cefr_range=("A2", "B1"),
            description="Two verbs meaning 'to be': ser for inherent identity, estar for transient state or location.",
            native_term="ser/estar",
            contrast_concept="ser_vs_estar",
            discourse_effects=[
                "Using ser instead of estar with emotional states sounds clinical or insulting (es triste = he's a sad person; está triste = he's sad right now).",
                "With adjectives like 'aburrido', copula choice reverses the meaning: boring vs bored.",
            ],
        ),
        NuanceSystem(
            name="Preterite vs Imperfect",
            dimension="aspect",
            cefr_range=("B1", "B2"),
            description="Both encode past, but preterite presents a bounded event while imperfect frames ongoing state or habit.",
            contrast_concept="preterite_vs_imperfect",
            discourse_effects=[
                "Imperfect for a punctual event sounds stylistically marked (stage-setting or literary).",
                "Preterite mid-narrative interrupts background description and advances the plot.",
            ],
            advanced_notes="In literary Spanish, the historic present (presente histórico) can replace preterite for vividness.",
        ),
        NuanceSystem(
            name="Subjunctive vs Indicative",
            dimension="mood",
            cefr_range=("B2", "C1"),
            description="Indicative asserts facts; subjunctive encodes doubt, desire, hypothetical, or emotional contexts.",
            contrast_concept="subjunctive_vs_indicative",
            discourse_effects=[
                "Indicative in a doubt-clause (creo que viene) asserts higher confidence than subjunctive (creo que venga).",
                "Subjunctive after 'aunque' marks purely hypothetical concession vs. indicative for factual concession.",
            ],
            advanced_notes="The imperfect subjunctive (-ra/-se forms) has stylistic variation: -ra is more universal, -se is more literary/Castilian.",
        ),
        NuanceSystem(
            name="Por vs Para",
            dimension="argument_marking",
            cefr_range=("B1", "B2"),
            description="Both translate loosely as 'for': por looks backward (cause, exchange, duration) while para looks forward (purpose, recipient, deadline).",
            contrast_concept="por_vs_para",
        ),
        NuanceSystem(
            name="Diminutives",
            dimension="register",
            cefr_range=("B1", "C1"),
            description="-ito/-ito suffixes encode smallness, affection, or informality — pervasive in conversational Latin American Spanish.",
            discourse_effects=["Omitting diminutives in casual speech can sound cold or bureaucratic in many Latin American dialects."],
        ),
    ],

    # ── French ───────────────────────────────────────────────────────────────
    "fr": [
        NuanceSystem(
            name="Passé composé vs Imparfait",
            dimension="aspect",
            cefr_range=("B1", "B2"),
            description="Passé composé for completed events; imparfait for ongoing background states, habits, or interrupted actions.",
            contrast_concept="passe_compose_vs_imparfait",
            discourse_effects=[
                "Imparfait used for a sharply punctual event reads as literary or stylised.",
                "Mixing them signals competence: je lisais quand le téléphone a sonné (I was reading when the phone rang).",
            ],
        ),
        NuanceSystem(
            name="Tu vs Vous",
            dimension="politeness",
            cefr_range=("A1", "B1"),
            description="Tu (informal) vs. vous (formal/plural): wrong choice signals social register mismatch.",
            contrast_concept="tu_vs_vous",
            native_term="tutoiement/vouvoiement",
            discourse_effects=[
                "Tutoyer a stranger in a formal context (job interview, older person) is rude.",
                "Vouvoyer a close friend or family member sounds cold or sarcastic.",
            ],
        ),
        NuanceSystem(
            name="Subjonctif vs Indicatif",
            dimension="mood",
            cefr_range=("B2", "C1"),
            description="Subjonctif after triggers of doubt, will, emotion, or impersonal expressions; indicatif for factual assertions.",
            contrast_concept="subjonctif_vs_indicatif",
            discourse_effects=["Using indicatif after espérer que is an acceptable colloquial shortcut, but subjonctif is the standard."],
        ),
        NuanceSystem(
            name="Discourse particles (donc, alors, quand même, etc.)",
            dimension="discourse_particle",
            cefr_range=("B2", "C2"),
            description="High-frequency particles modulate certainty, inference, concession, and social positioning.",
            advanced_notes="Quand même alone on a turn expresses concession ('fair enough'); with a verb it adds insistence ('he did it anyway, surprisingly').",
        ),
    ],

    # ── German ───────────────────────────────────────────────────────────────
    "de": [
        NuanceSystem(
            name="Modal particles (Modalpartikeln)",
            dimension="discourse_particle",
            cefr_range=("B2", "C2"),
            description="Particles like ja, doch, mal, halt, wohl shift epistemic stance, social tone, and implicature without propositional content.",
            native_term="Modalpartikeln",
            contrast_concept="modal_particles",
            discourse_effects=[
                "«doch» contradicts an assumption — omitting it in a rebuttal sounds blunt.",
                "«ja» marks shared knowledge — using it with truly new information sounds condescending.",
                "«mal» softens a command — without it, requests can sound rude.",
            ],
            advanced_notes="Stacking particles (doch mal, eigentlich doch) is normal but order is constrained; wrong order sounds foreign.",
        ),
        NuanceSystem(
            name="Wechselpräpositionen (case-selecting prepositions)",
            dimension="case",
            cefr_range=("A2", "B2"),
            description="Two-way prepositions (in, an, auf, über, …) take accusative for directed motion and dative for static location.",
            contrast_concept="wechselpraepositionen",
            discourse_effects=[
                "Accusative where dative is expected (Ich bin in den Laden = I walked into the store) suggests motion, not presence.",
                "Dative for a movement verb (Ich lege das Buch auf dem Tisch) is a classic learner error marking non-native proficiency.",
            ],
        ),
        NuanceSystem(
            name="Konjunktiv II (subjunctive II)",
            dimension="mood",
            cefr_range=("B2", "C1"),
            description="Expresses counterfactual conditionals, polite requests, and reported speech.",
            native_term="Konjunktiv II",
            contrast_concept="konjunktiv_ii",
            discourse_effects=[
                "Könnte ich bitte…? (Konjunktiv II) is significantly more polite than Kann ich…? (indicative).",
                "Wenn ich reich wäre, … marks irreality; wenn ich reich bin, … marks realistic condition.",
            ],
        ),
        NuanceSystem(
            name="Separable verb particles",
            dimension="valency",
            cefr_range=("A2", "C1"),
            description="Particle position and choice fundamentally changes verb meaning: anrufen (call) ≠ aufrufen (summon).",
        ),
        NuanceSystem(
            name="Dative case government",
            dimension="argument_marking",
            cefr_range=("A2", "B2"),
            description="Many German verbs govern dative where English speakers expect accusative (helfen, danken, gefallen).",
        ),
    ],

    # ── Russian ───────────────────────────────────────────────────────────────
    "ru": [
        NuanceSystem(
            name="Perfective vs Imperfective aspect",
            dimension="aspect",
            cefr_range=("A2", "C1"),
            description="Every Russian verb has aspect. Perfective delivers a result; imperfective describes process, habit, or ongoing state.",
            native_term="вид глагола",
            contrast_concept="perfective_vs_imperfective",
            discourse_effects=[
                "Perfective in a series of clauses chains events sequentially; imperfective allows background or simultaneous reading.",
                "Imperfective imperative (Пиши!) sounds gentler than perfective (Напиши!), which demands completion.",
                "Negated perfectives are odd (rarely grammatical); negated imperfectives are standard for habitual negation.",
            ],
            advanced_notes="Some verbs change meaning entirely by aspect pair: слышать/услышать (hear/catch the sound), видеть/увидеть (see/notice).",
        ),
        NuanceSystem(
            name="Unidirectional vs Multidirectional motion verbs",
            dimension="aspect",
            cefr_range=("B1", "C1"),
            description="идти (one-way trip right now) vs. ходить (habitual/multidirectional); each direction has 14 such pairs.",
            contrast_concept="motion_verb_pairs",
            discourse_effects=["Using идти for a habitual action (Я иду в школу каждый день) sounds odd; ходить is required."],
        ),
        NuanceSystem(
            name="Case system",
            dimension="case",
            cefr_range=("A2", "C1"),
            description="Six cases encode grammatical function: nominative, accusative, dative, genitive, instrumental, prepositional.",
            native_term="падежи",
        ),
        NuanceSystem(
            name="Genitive of negation",
            dimension="case",
            cefr_range=("B1", "B2"),
            description="Negated existential clauses take genitive (Нет книги) not nominative (Есть книга).",
            contrast_concept="genitive_negation",
        ),
    ],

    # ── Arabic ───────────────────────────────────────────────────────────────
    "ar": [
        NuanceSystem(
            name="Definiteness — article vs null",
            dimension="definiteness",
            cefr_range=("A1", "B1"),
            description="ال (al-) marks definite nouns; its absence marks indefinite. Definiteness agreement cascades through adjectival phrases.",
            native_term="التعريف والتنكير",
            contrast_concept="definiteness",
            discourse_effects=[
                "الكتاب الكبير (the big book) vs. كتاب كبير (a big book) — the article must match on both noun and adjective.",
                "Predicate nouns in equational sentences are typically indefinite: أحمد طالب (Ahmad is a student).",
            ],
        ),
        NuanceSystem(
            name="Verb-final vs verb-initial aspect",
            dimension="aspect",
            cefr_range=("A2", "B2"),
            description="Perfect (الماضي) describes completed actions; imperfect (المضارع) describes ongoing, habitual, or future actions.",
            contrast_concept="perfect_vs_imperfect",
            native_term="الماضي والمضارع",
        ),
        NuanceSystem(
            name="Tense negation particles",
            dimension="negation",
            cefr_range=("A2", "B1"),
            description="لا (present/future), لم + jussive (past), لن + subjunctive (emphatic future): negation particle selects verb mood.",
            contrast_concept="negation_particles",
            discourse_effects=[
                "لم أذهب negates a past action with jussive mood; ما ذهبتُ is an equivalent classical/literary form.",
                "لن + subjunctive is emphatic future negation — much stronger than لا + present.",
            ],
        ),
        NuanceSystem(
            name="Broken plural vs sound plural",
            dimension="number",
            cefr_range=("A2", "B2"),
            description="Most Arabic nouns have irregular 'broken' plurals (أقلام ← قلم) that must be memorized; sound plurals follow regular suffixes.",
            native_term="جمع التكسير",
            contrast_concept="broken_plural",
        ),
        NuanceSystem(
            name="Dual number",
            dimension="number",
            cefr_range=("A2", "B1"),
            description="Arabic has a productive dual suffix (-ان/-ين) for exactly two of anything — distinct from both singular and plural.",
            contrast_concept="dual_number",
            discourse_effects=["Using plural for 'two of something' is grammatically incorrect in formal Arabic."],
        ),
        NuanceSystem(
            name="Root-pattern morphology",
            dimension="semantic_field",
            cefr_range=("B1", "C1"),
            description="Most Arabic words derive from a 3- or 4-letter root via patterns (أوزان) that reliably signal part of speech and semantic field.",
            native_term="الجذر والوزن",
            advanced_notes="Recognising that كَتَبَ, كِتَاب, كَاتِب, مَكْتَب, مَكْتُوب all share root ك-ت-ب reveals the whole semantic cluster.",
        ),
    ],

    # ── Japanese ─────────────────────────────────────────────────────────────
    "ja": [
        NuanceSystem(
            name="Keigo — honorific speech levels",
            dimension="politeness",
            cefr_range=("A2", "C1"),
            description="Three tiers: teineigo (polite baseline, ます/です), sonkeigo (elevates others), kenjōgo (humbles oneself).",
            native_term="敬語",
            contrast_concept="keigo_levels",
            discourse_effects=[
                "Using plain form with a boss or customer is rude; using sonkeigo for one's own actions is an error.",
                "Kenjōgo is essential in business (伺う vs 行く, いただく vs もらう).",
            ],
            advanced_notes="Bikago (美化語) is an aesthetic register that adds politeness without strict hierarchical marking (お料理, ご飯).",
        ),
        NuanceSystem(
            name="は vs が topic/subject contrast",
            dimension="topic_focus",
            cefr_range=("A2", "C1"),
            description="は marks the topic (known/given information, often with contrast); が marks the neutral grammatical subject or new information focus.",
            native_term="は/が",
            contrast_concept="wa_ga_contrast",
            discourse_effects=[
                "猫はいる implies 'as for cats, there are some' (known topic); 猫がいる announces existence as new information.",
                "誰が来ましたか? asks 'who came?' (open question); 誰は来ましたか? implies exclusion ('who among them came?').",
            ],
            advanced_notes="は can mark objects (魚は食べる), creating a contrastive 'as for fish, I eat [it]'.",
        ),
        NuanceSystem(
            name="Aspect markers ている / てある",
            dimension="aspect",
            cefr_range=("A2", "B2"),
            description="〜ている encodes ongoing action or resultant state; 〜てある encodes a resultant state caused by a deliberate prior action.",
            contrast_concept="te_iru_te_aru",
            discourse_effects=[
                "ドアが開いている (the door is open — state) vs. ドアを開けてある (the door has been opened deliberately).",
            ],
        ),
        NuanceSystem(
            name="Evidential and modal endings (-らしい, -ようだ, -そうだ)",
            dimension="evidentiality",
            cefr_range=("B1", "C1"),
            description="Different endings signal the evidence source: hearsay (-そうだ), inference from observation (-ようだ), general reputation (-らしい).",
            native_term="様態・推量・伝聞",
            contrast_concept="evidential_endings",
        ),
        NuanceSystem(
            name="Particles は/が/を/に/で/へ",
            dimension="argument_marking",
            cefr_range=("A1", "B2"),
            description="Postpositional case particles mark grammatical role; particle choice changes meaning (に for endpoint vs で for location of action).",
        ),
    ],

    # ── Chinese (Mandarin) ────────────────────────────────────────────────────
    "zh": [
        NuanceSystem(
            name="Aspect particles 了/着/过",
            dimension="aspect",
            cefr_range=("A2", "B2"),
            description="了 (completion/change of state), 着 (ongoing/durative state), 过 (experiential — occurred at some point in life).",
            native_term="动态助词",
            contrast_concept="aspect_particles",
            discourse_effects=[
                "我吃了 (I ate / I'm done eating) vs 我吃着 (I'm eating) vs 我吃过 (I have eaten before).",
                "Omitting 了 after a clear completion verb can sound abrupt or leave ambiguity.",
            ],
        ),
        NuanceSystem(
            name="把 construction (disposal)",
            dimension="diathesis",
            cefr_range=("B1", "B2"),
            description="把 fronts the affected object before the verb to emphasize disposal or transformation of that object.",
            native_term="把字句",
            contrast_concept="ba_construction",
            discourse_effects=[
                "把书放在桌子上 (put the book on the table) — 把 requires a resultative or directional complement.",
                "Without 把: 书放在桌子上 (the book is placed on the table) — less agent-focused.",
            ],
        ),
        NuanceSystem(
            name="被 passive (adversative nuance)",
            dimension="diathesis",
            cefr_range=("B1", "B2"),
            description="被 marks passive voice and typically carries an adversative (unfortunate) connotation.",
            native_term="被字句",
            contrast_concept="bei_passive",
            discourse_effects=["被 + positive event sounds unusual or ironic; normally used for undesirable outcomes."],
        ),
        NuanceSystem(
            name="Topic prominence",
            dimension="topic_focus",
            cefr_range=("B1", "C1"),
            description="Chinese is a topic-prominent language — the sentence topic need not be the subject: 那本书我看了 (That book, I read it).",
            contrast_concept="topic_prominence",
            advanced_notes="Topic + comment structure allows long topic chains that have no direct English equivalent.",
        ),
        NuanceSystem(
            name="Measure words (量词)",
            dimension="classifier",
            cefr_range=("A1", "B1"),
            description="Every countable noun requires a classifier between a numeral and the noun: 三本书, 两条鱼, 一辆车.",
            native_term="量词",
            contrast_concept="measure_words",
        ),
        NuanceSystem(
            name="Degree adverbs (很/太/非常/挺/有点)",
            dimension="semantic_field",
            cefr_range=("A1", "B1"),
            description="Different degree adverbs encode evaluation: 挺 (pleasantly), 有点 (slightly negative), 太 (excessive), 非常 (neutral emphasis).",
            contrast_concept="degree_adverbs",
        ),
    ],

    # ── Korean ────────────────────────────────────────────────────────────────
    "ko": [
        NuanceSystem(
            name="Speech level system",
            dimension="politeness",
            cefr_range=("A1", "B2"),
            description="Six speech levels encode social relationship; 합쇼체 (formal), 해요체 (polite), 해체 (intimate), 해라체 (written).",
            native_term="경어법",
            contrast_concept="speech_levels",
            discourse_effects=[
                "해체 with a superior is rude; 합쇼체 with a close friend sounds cold or sarcastic.",
                "Context-switching between levels signals social distance shifts.",
            ],
        ),
        NuanceSystem(
            name="은/는 vs 이/가 topic/subject contrast",
            dimension="topic_focus",
            cefr_range=("A2", "C1"),
            description="은/는 marks topic or contrast; 이/가 marks the neutral subject or new information. Same as Japanese は/が.",
            native_term="주제/주어",
            contrast_concept="topic_subject_contrast",
            discourse_effects=[
                "저는 학생이에요 (I [topic] am a student) vs 제가 했어요 (I [subject] did it — specifically me).",
                "은/는 in negative sentences marks contrastive scope: 밥은 먹었어 (I ate rice [at least]).",
            ],
        ),
        NuanceSystem(
            name="Negation strategies",
            dimension="negation",
            cefr_range=("A2", "B1"),
            description="Short negation (안/못) vs long negation (-지 않다/-지 못하다); 안 = volitional, 못 = inability.",
            contrast_concept="negation_forms",
        ),
        NuanceSystem(
            name="Object marker choice (을/를 vs 이/가)",
            dimension="argument_marking",
            cefr_range=("A2", "B2"),
            description="좋아하다 takes 을/를 (object) while 좋다 takes 이/가 (subject) — the same English verb 'like' has two Korean structures.",
            contrast_concept="object_subject_verbs",
        ),
    ],

    # ── Italian ───────────────────────────────────────────────────────────────
    "it": [
        NuanceSystem(
            name="Congiuntivo vs Indicativo",
            dimension="mood",
            cefr_range=("B2", "C1"),
            description="Congiuntivo after triggers of doubt, will, emotion, impersonal verbs; indicativo for factual statements.",
            contrast_concept="congiuntivo_vs_indicativo",
            discourse_effects=[
                "Penso che abbia ragione (congiuntivo, B2) vs. colloquially Penso che ha ragione (indicativo, informal).",
                "Congiuntivo in independent clauses expresses wish or mild command: Che venga! (Let him come!).",
            ],
        ),
        NuanceSystem(
            name="Passato prossimo vs Passato remoto",
            dimension="tense",
            cefr_range=("B1", "B2"),
            description="Both translate as simple past; prossimo for recent/relevant-to-present events (especially northern Italy), remoto for historical/distant events (especially southern Italy).",
            contrast_concept="passato_prossimo_vs_remoto",
            discourse_effects=[
                "In northern Italy, passato remoto for a recent event sounds literary; in southern Italy the reverse holds.",
                "Passato remoto is always preferred for historical narrative (Dante nacque nel 1265).",
            ],
        ),
        NuanceSystem(
            name="Lei (formal) vs Tu (informal)",
            dimension="politeness",
            cefr_range=("A2", "B1"),
            description="Third-person singular Lei is the formal address; second-person tu is informal. Register mismatch is socially marked.",
            native_term="Lei/tu",
            contrast_concept="lei_vs_tu",
        ),
        NuanceSystem(
            name="Si passivante / impersonale",
            dimension="diathesis",
            cefr_range=("B1", "C1"),
            description="The pronoun si can mark passive (si vende — is for sale) or impersonal (si fa — one does). Context disambiguates.",
            contrast_concept="si_constructions",
        ),
        NuanceSystem(
            name="Essere vs Avere as auxiliary",
            dimension="valency",
            cefr_range=("A2", "B1"),
            description="Intransitive motion/change-of-state verbs take essere; most transitive verbs take avere in compound tenses.",
            contrast_concept="essere_vs_avere",
        ),
    ],

    # ── Portuguese ────────────────────────────────────────────────────────────
    "pt": [
        NuanceSystem(
            name="Ser vs Estar vs Ficar",
            dimension="mood",
            cefr_range=("A2", "B1"),
            description="Ser = inherent/permanent, estar = temporary state, ficar = become/remain (Brazilian), with overlap that learners must master.",
            contrast_concept="ser_estar_ficar",
            discourse_effects=[
                "Ficar in Brazil often replaces estar for many states: fiquei com medo (I got scared).",
                "Ficar also means 'to stay' (location): fiquei em casa.",
            ],
        ),
        NuanceSystem(
            name="Personal infinitive",
            dimension="valency",
            cefr_range=("B2", "C1"),
            description="Portuguese uniquely inflects infinitives by person/number in certain contexts: para eles fazerem (for them to do).",
            native_term="infinitivo pessoal",
            contrast_concept="personal_infinitive",
            discourse_effects=["Using uninflected infinitive where personal is required sounds unnatural in EP; BP accepts both more freely."],
            advanced_notes="Especially required after prepositions in complex clauses; triggers when infinitive subjects differ from main clause subject.",
        ),
        NuanceSystem(
            name="Future subjunctive",
            dimension="mood",
            cefr_range=("B2", "C1"),
            description="Portuguese maintains an active future subjunctive for conditional/hypothetical future clauses that Spanish has abandoned.",
            native_term="futuro do subjuntivo",
            contrast_concept="future_subjunctive",
            discourse_effects=["Se eu for (future subjunctive) vs Se eu fosse (imperfect subjunctive): real vs. hypothetical future condition."],
        ),
        NuanceSystem(
            name="Pretérito perfeito vs imperfeito",
            dimension="aspect",
            cefr_range=("B1", "B2"),
            description="Same aspectual distinction as Spanish: perfeito (completed event) vs imperfeito (ongoing, habitual, background).",
            contrast_concept="preterito_perfeito_vs_imperfeito",
        ),
    ],

    # ── Latin ─────────────────────────────────────────────────────────────────
    "la": [
        NuanceSystem(
            name="Indicative vs Subjunctive mood",
            dimension="mood",
            cefr_range=("A2", "C1"),
            description="Indicative for facts; subjunctive for purpose clauses, result clauses, indirect command, cum-clauses, indirect statement in certain verbs.",
            contrast_concept="indicative_vs_subjunctive",
            discourse_effects=[
                "Purpose clauses require subjunctive (ut + subj); result clauses also require it (ita … ut + subj).",
                "Historical cum-clauses (cum diceret) take subjunctive; temporal cum (cum dicit) takes indicative.",
            ],
        ),
        NuanceSystem(
            name="Ablative case uses",
            dimension="case",
            cefr_range=("A2", "B2"),
            description="The ablative encodes means, manner, accompaniment, separation, time, comparison, and agent (with passive) — all without prepositions.",
            contrast_concept="ablative_uses",
            native_term="casus ablativus",
            discourse_effects=["Ablative absolute is a highly compressed construction that expert readers use to date events and set scene."],
        ),
        NuanceSystem(
            name="Indirect statement (accusative + infinitive)",
            dimension="valency",
            cefr_range=("B1", "C1"),
            description="Latin indirect statement uses accusative subject + infinitive (not a conjunction clause): dicit eum venire (he says he is coming).",
            contrast_concept="indirect_statement",
            native_term="accusativus cum infinitivo",
        ),
        NuanceSystem(
            name="Gerund vs Gerundive",
            dimension="valency",
            cefr_range=("B2", "C1"),
            description="Gerund (verbal noun: amandi = of loving) vs gerundive (verbal adjective implying obligation: liber legendus = a book to be read).",
            contrast_concept="gerund_vs_gerundive",
        ),
        NuanceSystem(
            name="Aspect in past tenses (perfect vs imperfect)",
            dimension="aspect",
            cefr_range=("A2", "B2"),
            description="Perfect (dixi) = completed action or present result; imperfect (dicebam) = ongoing or repeated past action.",
            contrast_concept="latin_aspect",
        ),
    ],

    # ── Koine Greek ──────────────────────────────────────────────────────────
    "grc": [
        NuanceSystem(
            name="Verbal aspect (aorist vs imperfect vs perfect)",
            dimension="aspect",
            cefr_range=("A2", "C1"),
            description="Greek aspect is primary: aorist = summary/punctiliar view, imperfect = ongoing/incomplete view, perfect = present relevance of past event.",
            native_term="ποιόν ἐνεργείας",
            contrast_concept="greek_aspect",
            discourse_effects=[
                "Aorist imperative (ποίησον) commands a discrete act; present imperative (ποίει) commands ongoing action or sustains a habit.",
                "Perfect states persist into the present: γέγραπται (it stands written) — not just 'it was written'.",
            ],
            advanced_notes="Greek aspect is more fundamental than tense in the non-indicative moods; aspect drives meaning, tense situates it in time.",
        ),
        NuanceSystem(
            name="οὐ vs μή negation",
            dimension="negation",
            cefr_range=("A2", "B1"),
            description="οὐ negates indicative assertions; μή negates non-indicative moods, infinitives, and participles — the most systematic distinction in Greek negation.",
            contrast_concept="ou_vs_me",
            discourse_effects=["Using μή with an indicative main clause is ungrammatical in Classical Greek; in Koine some relaxation occurs."],
        ),
        NuanceSystem(
            name="Conditional types",
            dimension="mood",
            cefr_range=("B1", "C1"),
            description="Four condition types encode probability: simple (εἰ + indicative), future-more-vivid (ἐὰν + subjunctive), future-less-vivid (εἰ + optative), contrary-to-fact (εἰ + indicative + ἄν).",
            contrast_concept="conditional_types",
        ),
        NuanceSystem(
            name="Article as definite marker and pronoun",
            dimension="definiteness",
            cefr_range=("A1", "B1"),
            description="The Greek article (ὁ/ἡ/τό) marks definiteness and can function as demonstrative pronoun, relative clause introducer, or even weak conjunction (ὁ μέν… ὁ δέ).",
            contrast_concept="article_functions",
        ),
        NuanceSystem(
            name="Optative mood",
            dimension="mood",
            cefr_range=("C1", "C2"),
            description="The optative expresses possibility, wish, or polite condition — mainly in Classical Greek; less common in Koine.",
            native_term="εὐκτική ἔγκλισις",
            contrast_concept="optative_mood",
        ),
    ],

    # ── Hebrew ────────────────────────────────────────────────────────────────
    "he": [
        NuanceSystem(
            name="Definite article ה + agreement",
            dimension="definiteness",
            cefr_range=("A1", "B1"),
            description="Article ה- prefixes the noun and must be repeated on each attributive adjective: הספר הגדול (the big book).",
            contrast_concept="hebrew_definiteness",
        ),
        NuanceSystem(
            name="Binyanim (verb patterns)",
            dimension="diathesis",
            cefr_range=("A2", "C1"),
            description="Seven verb patterns (Pa'al, Nif'al, Pi'el, Pu'al, Hitpa'el, Hif'il, Huf'al) encode active, passive, reflexive, causative, and intensive meanings.",
            native_term="בניינים",
            contrast_concept="binyanim",
        ),
        NuanceSystem(
            name="Construct state (Semikut)",
            dimension="case",
            cefr_range=("B1", "B2"),
            description="Noun modification via construct chain: ספר הילד (the book of the child) — the first noun takes a special construct form.",
            native_term="סמיכות",
            contrast_concept="construct_state",
        ),
    ],

    # ── English ───────────────────────────────────────────────────────────────
    "en": [
        NuanceSystem(
            name="Simple vs Progressive aspect",
            dimension="aspect",
            cefr_range=("A1", "B1"),
            description="Simple tenses (I work) encode habitual/generic; progressive (I am working) encodes ongoing action at reference time.",
            contrast_concept="simple_vs_progressive",
        ),
        NuanceSystem(
            name="Present perfect vs Simple past",
            dimension="tense",
            cefr_range=("B1", "B2"),
            description="Present perfect (I have eaten) marks relevance to now; simple past (I ate) anchors the event in finished time.",
            contrast_concept="present_perfect_vs_past",
        ),
    ],
}


# ── Public API ────────────────────────────────────────────────────────────────

def get_inventory(language: str) -> list[NuanceSystem]:
    """Return the nuance inventory for *language*.

    Returns an empty list for unsupported languages rather than raising,
    so callers degrade gracefully.
    """
    return _INVENTORIES.get(language, [])


def get_system(language: str, concept: str) -> NuanceSystem | None:
    """Return the NuanceSystem whose ``contrast_concept`` matches *concept*."""
    for system in _INVENTORIES.get(language, []):
        if system.contrast_concept == concept:
            return system
    return None


def all_languages() -> list[str]:
    """Return all language codes that have an inventory."""
    return list(_INVENTORIES.keys())
