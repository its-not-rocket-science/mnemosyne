"""Etymology enrichment layer — learner-facing word-origin notes.

Architecture
────────────
EtymologyStore holds curated entries keyed by (language, normalised_lemma).
apply_etymology() writes lesson_data["etymology"] for vocabulary objects.
EtymologyProvider is a Protocol for future network-backed providers
(Wiktionary, GPT, etc.) that callers can wire in independently.

Fields written
──────────────
``lesson_data["etymology"]``
    Dict with origin_summary, optional roots/cognates/semantic_shift,
    confidence, and source_type.

``lesson_data["etymology_attempted"]``
    Sentinel set after any lookup attempt (hit or miss), matching the
    gloss_attempted / translation_attempted pattern used elsewhere.
"""
from __future__ import annotations

import logging
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import CanonicalObjectRow

logger = logging.getLogger(__name__)


# ── Data model ────────────────────────────────────────────────────────────────

class EtymologyEntry(BaseModel):
    language: str
    lemma: str
    origin_summary: str
    roots: list[str] = Field(default_factory=list)
    cognates: list[str] = Field(default_factory=list)
    semantic_shift: str | None = None
    confidence: float = 1.0
    source_type: Literal["curated", "wiktionary", "model"] = "curated"

    def to_lesson_data(self) -> dict[str, Any]:
        """JSON-safe dict for storage in lesson_data["etymology"]."""
        d: dict[str, Any] = {"origin_summary": self.origin_summary}
        if self.roots:
            d["roots"] = self.roots
        if self.cognates:
            d["cognates"] = self.cognates
        if self.semantic_shift:
            d["semantic_shift"] = self.semantic_shift
        d["confidence"] = self.confidence
        d["source_type"] = self.source_type
        return d


# ── Provider interface ────────────────────────────────────────────────────────

class EtymologyProvider(Protocol):
    """Interface for network-backed etymology providers (Wiktionary, model, etc.)."""

    async def fetch(self, lemma: str, language: str) -> EtymologyEntry | None:
        """Return an EtymologyEntry, or None on miss."""
        ...


# ── In-memory store ───────────────────────────────────────────────────────────

class EtymologyStore:
    """In-memory store; keys are (language, lemma.lower())."""

    def __init__(self, entries: list[EtymologyEntry] | None = None) -> None:
        self._data: dict[tuple[str, str], EtymologyEntry] = {}
        for entry in (entries or []):
            self.add(entry)

    def add(self, entry: EtymologyEntry) -> None:
        self._data[(entry.language, entry.lemma.lower())] = entry

    def get(self, language: str, lemma: str) -> EtymologyEntry | None:
        return self._data.get((language, lemma.lower()))

    def __len__(self) -> int:
        return len(self._data)


# ── Enrichment function ───────────────────────────────────────────────────────

async def apply_etymology(
    db: AsyncSession,
    object_ids: list[str],
    store: EtymologyStore | None = None,
) -> None:
    """Write etymology data to lesson_data for vocabulary objects in object_ids.

    Silently skips objects that are not vocabulary type, already have etymology,
    have no lemma in lesson_data, or have no entry in the store.
    """
    if not object_ids:
        return

    effective_store = store if store is not None else DEFAULT_STORE

    result = await db.execute(
        select(CanonicalObjectRow).where(
            CanonicalObjectRow.id.in_(object_ids),
            CanonicalObjectRow.type == "vocabulary",
        )
    )
    rows = result.scalars().all()

    pending = [
        row for row in rows
        if not (row.lesson_data or {}).get("etymology")
        and not (row.lesson_data or {}).get("etymology_attempted")
    ]
    if not pending:
        return

    dirty: list[CanonicalObjectRow] = []
    for row in pending:
        ld = dict(row.lesson_data or {})
        lemma = ld.get("lemma") or row.canonical_form
        entry = effective_store.get(row.language or "", lemma)
        ld["etymology_attempted"] = True
        if entry:
            ld["etymology"] = entry.to_lesson_data()
        row.lesson_data = ld
        dirty.append(row)

    if dirty:
        try:
            await db.commit()
            hits = sum(1 for r in dirty if (r.lesson_data or {}).get("etymology"))
            logger.info(
                "etymology: %d objects updated, %d hits/%d pending",
                len(dirty), hits, len(pending),
            )
        except Exception:
            logger.warning("etymology DB commit failed", exc_info=True)


# ── Curated seed data ─────────────────────────────────────────────────────────
# Selected for learner insight: polysemy, cultural weight, semantic shift,
# cross-language spread, untranslatability.

_CURATED: list[EtymologyEntry] = [

    # ── Spanish ──────────────────────────────────────────────────────────────
    EtymologyEntry(
        language="es", lemma="tiempo",
        origin_summary=(
            "From Latin tempus 'time, period, season, weather.' Latin used one word "
            "for all these senses; Spanish inherited the ambiguity, so tiempo still "
            "means both 'time' and 'weather.'"
        ),
        roots=["Latin tempus (time, season)"],
        cognates=["French temps", "Italian tempo", "Portuguese tempo"],
        semantic_shift="Latin tempus → season/weather sense merged with abstract 'time'",
    ),
    EtymologyEntry(
        language="es", lemma="amigo",
        origin_summary=(
            "From Latin amicus 'friend,' derived from amare 'to love.' "
            "Shares its root with amour, amiable, and English amicable."
        ),
        roots=["Latin amare (to love)", "Latin amicus (friend)"],
        cognates=["French ami", "Italian amico", "Portuguese amigo", "English amicable"],
    ),
    EtymologyEntry(
        language="es", lemma="decir",
        origin_summary=(
            "From Latin dicere 'to say, declare.' "
            "The same root gives English diction, dictate, and predict."
        ),
        roots=["Latin dicere (to say)"],
        cognates=["French dire", "Italian dire", "English diction"],
    ),
    EtymologyEntry(
        language="es", lemma="guerrilla",
        origin_summary=(
            "Diminutive of guerra 'war,' from Old High German werra 'strife, discord.' "
            "Borrowed into English in the early 19th century during the Peninsular War "
            "to describe Spanish irregular fighters resisting Napoleon's army."
        ),
        roots=["Old High German werra (strife, discord)", "Spanish guerra (war)"],
        cognates=["English war (same Germanic root)", "French guerre"],
        semantic_shift="'small war' → partisan irregular warfare → any guerrilla force",
    ),
    EtymologyEntry(
        language="es", lemma="mosquito",
        origin_summary=(
            "Diminutive of mosca 'fly,' from Latin musca. "
            "Spanish explorers brought the term to English in the 16th century. "
            "In Spanish, mosca is the housefly; mosquito is its small biting relative."
        ),
        roots=["Latin musca (fly)"],
        cognates=["French mouche (fly)", "Italian mosca", "English mosquito (borrowed)"],
        semantic_shift="'little fly' → the biting gnat specifically",
    ),
    EtymologyEntry(
        language="es", lemma="siesta",
        origin_summary=(
            "From Latin hora sexta 'the sixth hour,' counting from 6 a.m. — "
            "meaning noon. Romans rested at midday; the practice became culturally "
            "associated with the word. English borrowed siesta unchanged."
        ),
        roots=["Latin sexta (sixth)", "Latin hora (hour)"],
        cognates=["Italian sesta", "English siesta (borrowed)"],
        semantic_shift="'sixth hour of the day' → midday → the afternoon rest taken then",
    ),
    EtymologyEntry(
        language="es", lemma="plaza",
        origin_summary=(
            "From Latin plattea 'broad street, open space,' from Greek plateia (hodos) "
            "'broad (street).' The same Greek root gives English plate, place, and plaza, "
            "and French place. Spanish plaza spread globally in names like Plaza Mayor."
        ),
        roots=["Greek plateia (broad)", "Latin plattea (broad street)"],
        cognates=["English place, plaza (from same Latin root)", "French place", "Italian piazza"],
    ),
    EtymologyEntry(
        language="es", lemma="fiesta",
        origin_summary=(
            "From Latin festa (plural of festum) 'festival, feast days.' "
            "The Latin root also gives English feast, festival, and festive. "
            "Borrowed into English as fiesta with the sense of a lively celebration."
        ),
        roots=["Latin festum (festival, holiday)"],
        cognates=["English feast, festival (from same Latin)", "French fête", "Italian festa"],
    ),
    EtymologyEntry(
        language="es", lemma="camino",
        origin_summary=(
            "From Late Latin camminus 'path, road,' likely from Celtic "
            "(compare Breton ken-min, Welsh cam 'step'). "
            "The Camino de Santiago pilgrimage route preserves the word in English."
        ),
        roots=["Celtic *camman or camminus (path, step)"],
        cognates=["French chemin", "Italian cammino", "English Camino (borrowed)"],
    ),
    EtymologyEntry(
        language="es", lemma="loco",
        origin_summary=(
            "Etymology disputed; possibly from Arabic lauqa 'female fool' "
            "(feminine of alwaq), or from a pre-Roman Iberian substrate. "
            "English loco (crazy) is borrowed from Spanish. "
            "Locomotive shares no root — its loco comes from Latin locus 'place.'"
        ),
        roots=["Possibly Arabic lauqa (female fool) or pre-Roman Iberian"],
        cognates=["English loco (borrowed from Spanish)"],
    ),

    # ── French ───────────────────────────────────────────────────────────────
    EtymologyEntry(
        language="fr", lemma="naïf",
        origin_summary=(
            "From Old French naïf, Latin nativus 'born in the country, natural, inborn.' "
            "Originally meant 'native' or 'natural'; shifted to 'ingenuous, unsophisticated' "
            "as urban sophistication became the norm."
        ),
        roots=["Latin nativus (native, inborn)"],
        cognates=["English naive", "Spanish nativo"],
        semantic_shift="'natural-born' → 'unsophisticated, credulous'",
    ),
    EtymologyEntry(
        language="fr", lemma="château",
        origin_summary=(
            "From Old French chastel, Latin castellum 'fort, small camp,' "
            "diminutive of castrum 'military camp.' "
            "English castle comes from the same Latin source via Norman French."
        ),
        roots=["Latin castellum (fort)", "Latin castrum (camp)"],
        cognates=["English castle", "Spanish castillo", "Italian castello"],
    ),
    EtymologyEntry(
        language="fr", lemma="déjà",
        origin_summary=(
            "Contraction of Old French des-ja, from des- (from) + ja (already, now), "
            "from Latin jam 'now, already.' "
            "Déjà vu—'already seen'—was coined by psychologist Émile Boirac in 1876."
        ),
        roots=["Latin jam (now, already)"],
        cognates=["Spanish ya", "Italian già"],
    ),

    # ── German ───────────────────────────────────────────────────────────────
    EtymologyEntry(
        language="de", lemma="Schadenfreude",
        origin_summary=(
            "Compound of Schaden 'harm, damage' + Freude 'joy, pleasure.' "
            "Describes pleasure from another's misfortune. "
            "Borrowed into English unchanged in the 20th century as it filled a lexical gap."
        ),
        roots=["Old High German scado (harm)", "Old High German frewida (joy)"],
        cognates=["English Schadenfreude (borrowed)"],
    ),
    EtymologyEntry(
        language="de", lemma="Kindergarten",
        origin_summary=(
            "Coined by educator Friedrich Fröbel in 1837 from Kinder 'children' + Garten 'garden.' "
            "He conceived of children as plants needing nurturing. "
            "Adopted into English, French, Japanese, and many other languages unchanged."
        ),
        roots=["Old High German kind (child)", "Proto-Germanic *gardaz (enclosure, yard)"],
        cognates=["English kindergarten (borrowed)", "French jardin d'enfants (calque)"],
    ),
    EtymologyEntry(
        language="de", lemma="Weltanschauung",
        origin_summary=(
            "Compound of Welt 'world' + Anschauung 'view, contemplation' "
            "(from anschauen 'to look at'). Coined in German philosophy to mean "
            "a comprehensive worldview or philosophy of life."
        ),
        roots=["Proto-Germanic *weraldiz (world)", "Old High German scouwôn (to look)"],
        cognates=["English worldview (calque)"],
    ),
    EtymologyEntry(
        language="de", lemma="Zeitgeist",
        origin_summary=(
            "Compound of Zeit 'time' + Geist 'spirit, mind.' "
            "Coined in 18th-century German philosophy to describe the intellectual "
            "and moral spirit of an era. Borrowed into English in the 19th century; "
            "used freely in journalism and criticism without translation."
        ),
        roots=["Proto-Germanic *tīdaz (time)", "Proto-Germanic *gaistaz (spirit, ghost)"],
        cognates=["English time, tide (related to Zeit)", "English zeitgeist (borrowed)"],
    ),
    EtymologyEntry(
        language="de", lemma="Doppelgänger",
        origin_summary=(
            "Compound of Doppel 'double' + Gänger 'walker, goer' (from gehen 'to go'). "
            "Literally 'double-walker' — a ghostly duplicate of a living person. "
            "Popularised by Jean Paul's novel Siebenkäs (1796). "
            "Borrowed into English as a word for any lookalike."
        ),
        roots=["Latin duplus → Middle High German doppel (double)", "Old High German gān (to go)"],
        cognates=["English double (same Latin root)", "English doppelganger (borrowed)"],
        semantic_shift="'ghostly double' → any lookalike or impersonating double",
    ),
    EtymologyEntry(
        language="de", lemma="Wanderlust",
        origin_summary=(
            "Compound of wandern 'to hike, wander' + Lust 'desire, pleasure.' "
            "Wandern derives from Proto-Germanic *wandrōną. "
            "Entered English through 20th-century usage; describes a strong "
            "impulse to travel and explore."
        ),
        roots=["Proto-Germanic *wandrōną (to wander)", "Proto-Germanic *lustuz (desire)"],
        cognates=["English wander (from the same root)", "English lust (from Lust)", "English wanderlust (borrowed)"],
    ),
    EtymologyEntry(
        language="de", lemma="Angst",
        origin_summary=(
            "From Proto-Germanic *angustaz 'narrowness, tightness,' related to Latin "
            "angustus 'narrow.' The chest-tightening feeling of dread gave the word "
            "its meaning. Borrowed into English via Freudian psychology to describe "
            "existential anxiety."
        ),
        roots=["Proto-Germanic *angustaz (tightness)", "PIE *h₂enǵʰ- (tight, narrow)"],
        cognates=["English anguish (from Latin angustus)", "French angoisse", "English angst (borrowed)"],
    ),
    EtymologyEntry(
        language="de", lemma="Leitmotiv",
        origin_summary=(
            "Compound of leiten 'to lead, guide' + Motiv 'motif, theme.' "
            "Coined in music criticism — not by Wagner himself — to describe "
            "recurring themes in his operas. Now used broadly for any recurrent "
            "symbol or theme in art or discourse."
        ),
        roots=["Old High German leitan (to lead)", "Latin motivus (moving)"],
        cognates=["English lead (related Germanic root)", "English leitmotif/leitmotiv (borrowed)"],
    ),
    EtymologyEntry(
        language="de", lemma="Poltergeist",
        origin_summary=(
            "Compound of poltern 'to make a racket, clatter' + Geist 'ghost, spirit.' "
            "Literally 'noisy ghost.' Entered English through German folklore accounts "
            "and was widely popularised by the 1982 film Poltergeist."
        ),
        roots=["Middle High German boldern/poldern (to rumble)", "Proto-Germanic *gaistaz (spirit)"],
        cognates=["English ghost (from Geist's cognate)", "English poltergeist (borrowed)"],
    ),
    EtymologyEntry(
        language="de", lemma="Rucksack",
        origin_summary=(
            "Compound of Rücken 'back' + Sack 'bag, sack.' "
            "Literally 'back-bag.' Borrowed into English and used interchangeably "
            "with backpack in many varieties of English, particularly British English."
        ),
        roots=["Proto-Germanic *hrugaz (back)", "Proto-Germanic *sakkaz (bag, sack)"],
        cognates=["English rucksack (borrowed)", "English sack (from the same root as Sack)"],
    ),

    # ── Italian ──────────────────────────────────────────────────────────────
    EtymologyEntry(
        language="it", lemma="ciao",
        origin_summary=(
            "From Venetian s'ciao vostro 'I am your slave,' shortened to ciau, then ciao. "
            "Sciau derives from Medieval Latin sclavus 'slave.' "
            "Originally a respectful greeting; now the most casual Italian hello and goodbye."
        ),
        roots=["Medieval Latin sclavus (slave, Slav)"],
        cognates=["English slave (same Latin root)"],
        semantic_shift="'(I am your) slave' → informal greeting/farewell",
    ),
    EtymologyEntry(
        language="it", lemma="piano",
        origin_summary=(
            "Short for pianoforte, coined c. 1700 from piano 'soft' + forte 'loud.' "
            "Piano itself comes from Latin planus 'flat, even, smooth.' "
            "The instrument was named for its dynamic range, unlike the harpsichord."
        ),
        roots=["Latin planus (flat, smooth)"],
        cognates=["Spanish llano", "French plan", "English plane, plain"],
        semantic_shift="'flat, soft' → musical dynamic marking → the instrument itself",
    ),
    EtymologyEntry(
        language="it", lemma="fiasco",
        origin_summary=(
            "From Italian fiasco 'bottle, flask,' from Medieval Latin flasco. "
            "Theater slang far fiasco ('to make a bottle') meant to fail on stage."
        ),
        roots=["Medieval Latin flasco (bottle)"],
        cognates=["French fiasco", "English fiasco (borrowed)", "German Flasche (bottle)"],
        semantic_shift="'glass bottle' → 'complete failure or disaster'",
    ),

    # ── Portuguese ───────────────────────────────────────────────────────────
    EtymologyEntry(
        language="pt", lemma="saudade",
        origin_summary=(
            "Disputed etymology: possibly from Latin solitas 'solitude' or salus 'health/welfare.' "
            "Describes a melancholic longing for something loved and lost—"
            "a defining concept of Portuguese and Brazilian culture."
        ),
        roots=["Possibly Latin solitas (solitude) or salus (health, welfare)"],
        cognates=["Spanish soledad (solitude, partial semantic overlap)"],
        semantic_shift="physical solitude → profound emotional longing for the absent",
    ),
    EtymologyEntry(
        language="pt", lemma="fado",
        origin_summary=(
            "From Latin fatum 'fate, destiny,' past participle of fari 'to speak.' "
            "Fado is a genre of melancholic song expressing longing and fate. "
            "The same Latin root gives English fate, fatal, and fairy."
        ),
        roots=["Latin fatum (fate)", "Latin fari (to speak)"],
        cognates=["Spanish hado", "French fée (fairy)", "English fate, fatal"],
    ),

    # ── Spanish — extended ───────────────────────────────────────────────────
    EtymologyEntry(
        language="es", lemma="agua",
        origin_summary=(
            "From Latin aqua 'water.' One of the most productive Latin roots: "
            "gives English aquatic, aqueduct, aquarium, and aquifer. "
            "In Spanish, agua uniquely triggers masculine articles in the singular "
            "(el agua, un agua) to avoid the double-a clash — yet it remains "
            "grammatically feminine (las aguas frías)."
        ),
        roots=["Latin aqua (water)"],
        cognates=["English aquatic, aqueduct, aquarium (all from aqua)", "Italian acqua", "Portuguese água"],
    ),
    EtymologyEntry(
        language="es", lemma="escuela",
        origin_summary=(
            "From Latin schola, borrowed from Greek skholē 'leisure, rest, free time.' "
            "For ancient Greeks, learning was the proper use of leisure. "
            "The semantic chain: leisure → philosophical discussion → place for teaching. "
            "Gives English school, scholar, and scholarship."
        ),
        roots=["Greek skholē (leisure, rest)", "Latin schola (school)"],
        cognates=["English school, scholar (from same Greek root)", "French école", "Italian scuola"],
        semantic_shift="'leisure, free time' → 'philosophical discussion in leisure' → 'place of learning'",
    ),
    EtymologyEntry(
        language="es", lemma="libro",
        origin_summary=(
            "From Latin liber, originally meaning the inner bark of a tree — "
            "the surface on which Romans wrote before papyrus became common. "
            "The same word gave English library, libel, and the name Liber (a Roman deity). "
        ),
        roots=["Latin liber (inner bark of tree, book)"],
        cognates=["English library, libel (from same Latin root)", "French livre", "Italian libro"],
        semantic_shift="'inner bark (writing surface)' → 'written document' → 'book'",
    ),
    EtymologyEntry(
        language="es", lemma="hablar",
        origin_summary=(
            "From Latin fabulare 'to tell stories, to converse,' from fabula 'story, tale.' "
            "The same root gives English fable, fabulous, and confabulate. "
            "In Spanish, fabulare became hablar (speech); fabular survives as a literary verb "
            "for 'to tell fables.'"
        ),
        roots=["Latin fabula (story, tale)", "Latin fabulare (to tell stories)"],
        cognates=["English fable, fabulous (from fabula)", "Italian favellare (archaic 'to speak')"],
        semantic_shift="'to tell fables/stories' → 'to speak, converse'",
    ),
    EtymologyEntry(
        language="es", lemma="flor",
        origin_summary=(
            "From Latin flos, floris 'flower.' One of the most productive Latin roots: "
            "gives English flower, flour (fine-ground grain — once called 'the flower of wheat'), "
            "flora, floral, flourish, and Florence (Florentia 'the flourishing one')."
        ),
        roots=["Latin flos / floris (flower)"],
        cognates=["English flower, flour, flora, flourish (all from flos)", "French fleur", "Italian fiore"],
        semantic_shift="English flour: 'the flower (finest part) of the grain'",
    ),
    EtymologyEntry(
        language="es", lemma="ciudad",
        origin_summary=(
            "From Latin civitas 'citizenship, community of citizens, city-state,' "
            "derived from civis 'citizen.' "
            "The same root gives English city, citizen, civic, civil, and civilization. "
            "Spanish ciudad preserves the abstract sense of a human community, not merely a place."
        ),
        roots=["Latin civis (citizen)", "Latin civitas (citizenship, city-state)"],
        cognates=["English city, civic, civil, civilization (all from civis)", "French cité", "Italian città"],
    ),
    EtymologyEntry(
        language="es", lemma="palabra",
        origin_summary=(
            "From Latin parabola 'comparison, parable,' itself from Greek parabolē "
            "'comparison, analogy' (para- 'beside' + ballein 'to throw'). "
            "In Late Latin, parabola shifted from 'comparison' to 'word, speech.' "
            "English borrowed the same word as parable (religious story) and parabola "
            "(the mathematical curve). Spanish kept the 'speech' sense."
        ),
        roots=["Greek parabolē (comparison, analogy)", "Latin parabola (comparison → word, speech)"],
        cognates=["English parable, parabola (from same Greek source)", "French parole (word)", "Italian parola"],
        semantic_shift="'thrown alongside (comparison)' → 'parable' → 'word, speech'",
    ),
    EtymologyEntry(
        language="es", lemma="caballo",
        origin_summary=(
            "From Latin caballus 'a workhorse, nag' — a pre-Latin word, probably Gaulish or Iberian. "
            "While equus was the classical word for horse, caballus was the working horse of soldiers "
            "and farmers; it displaced equus in all Romance languages. "
            "Gives English cavalier, cavalry, cavalcade, and chivalry (via French chevalier)."
        ),
        roots=["Latin caballus (workhorse, nag) — pre-Latin origin"],
        cognates=["English cavalry, cavalier, chivalry (via French chevalier)", "French cheval", "Italian cavallo"],
        semantic_shift="'working horse, nag' → general 'horse' as equus fell out of vernacular use",
    ),
    EtymologyEntry(
        language="es", lemma="sol",
        origin_summary=(
            "From Latin sol 'sun,' from Proto-Indo-European *sóh₂wl̥. "
            "One of the most ancient words in the Indo-European family: "
            "gives English solar, solstice, parasol, and underlies Sunday "
            "(Old English Sunnandæg 'Sun's day'). "
            "The Peruvian monetary unit sol is named after the sun."
        ),
        roots=["PIE *sóh₂wl̥ (sun)", "Latin sol (sun)"],
        cognates=["English solar, solstice, Sunday (all from the same root)", "French soleil", "Italian sole"],
    ),
    EtymologyEntry(
        language="es", lemma="noche",
        origin_summary=(
            "From Latin nox, noctis 'night,' from Proto-Indo-European *nókʷts. "
            "Gives English nocturnal, equinox (nox + aequus 'equal night'), and nocturn. "
            "The same PIE root gives English night, German Nacht, and Greek nyx — "
            "demonstrating remarkable stability across 5,000 years of language change."
        ),
        roots=["PIE *nókʷts (night)", "Latin nox / noctis (night)"],
        cognates=["English night, nocturnal, equinox (from nox)", "French nuit", "Italian notte", "German Nacht"],
    ),

    # ── German — extended ─────────────────────────────────────────────────────
    EtymologyEntry(
        language="de", lemma="Fernweh",
        origin_summary=(
            "Compound of fern 'far, distant' + Weh 'ache, pain.' "
            "Literally 'far-ache' — a longing to travel to distant places. "
            "The opposite of Heimweh (homesickness). "
            "Both words exploit the same German pain-metaphor for emotional longing. "
            "English has no direct equivalent; wanderlust is related but emphasises restlessness "
            "rather than longing for a specific distant place."
        ),
        roots=["Proto-Germanic *ferrana (far, distant)", "Proto-Germanic *wai- (pain, woe) — Old High German wē"],
        cognates=["English woe (from the same Weh root)", "German Heimweh (homesickness — opposite)"],
    ),
    EtymologyEntry(
        language="de", lemma="Heimweh",
        origin_summary=(
            "Compound of Heim 'home' + Weh 'ache, pain.' "
            "Coined in Swiss German (Heimwehe) around 1650 by Johannes Hofer "
            "as the medical diagnosis for what soldiers and students suffered when far from home. "
            "English 'homesick' is a calque of Heimweh. "
            "The Weh suffix (pain, woe) is the same root as English woe."
        ),
        roots=["Proto-Germanic *haimaz (home, village)", "Proto-Germanic *wai- (pain, woe)"],
        cognates=["English homesick (calque of Heimweh)", "English woe (from Weh)", "English home (from Heim)"],
        semantic_shift="Medical diagnosis for soldiers' nostalgia → general word for homesickness",
    ),
    EtymologyEntry(
        language="de", lemma="Weltschmerz",
        origin_summary=(
            "Compound of Welt 'world' + Schmerz 'pain, ache.' "
            "Coined by the German Romantic writer Jean Paul (1763–1825) in his novel Selina (1827) "
            "to describe the pain caused by the world failing to match one's ideals. "
            "Borrowed into English as a loanword in the 19th century. "
            "Related: Weltanschauung (worldview), Weltgeist (world spirit)."
        ),
        roots=["Proto-Germanic *weraldiz (world)", "Proto-Germanic *smertaz (pain)"],
        cognates=["English smart (pain sense — same root as Schmerz)", "English weltschmerz (borrowed)"],
    ),
    EtymologyEntry(
        language="de", lemma="Fingerspitzengefühl",
        origin_summary=(
            "Compound of Fingerspitze 'fingertip' (Finger + Spitze 'tip, point') + "
            "Gefühl 'feeling, sense.' "
            "Literally 'fingertip feeling': intuitive sensitivity and delicate handling — "
            "the ability to gauge a situation with a surgeon's precision. "
            "Used in German for political, social, and artistic finesse. "
            "No clean English single-word equivalent exists."
        ),
        roots=["Proto-Germanic *fingraz (finger)", "Proto-Germanic *fōlijaną (to feel)"],
        cognates=["English finger, feel (same Germanic roots)"],
    ),
    EtymologyEntry(
        language="de", lemma="Bildung",
        origin_summary=(
            "From bilden 'to form, shape, educate,' from Bild 'image, form' (Proto-Germanic *bilþam). "
            "In German philosophical tradition (Hegel, Schiller, Goethe) Bildung describes "
            "the process of self-cultivation: not merely acquiring knowledge but forming one's "
            "character and humanity through culture. "
            "Gives English Bildungsroman (novel of formation) as a borrowed compound."
        ),
        roots=["Proto-Germanic *bilþam (image, form)", "Old High German bilōn (to form)"],
        cognates=["English build (from the same Germanic root *bilþam)", "English Bildungsroman (borrowed)"],
        semantic_shift="'to give form/shape' → 'to educate' → 'cultivation of the complete human being'",
    ),
    EtymologyEntry(
        language="de", lemma="Buch",
        origin_summary=(
            "From Proto-Germanic *bōkō, originally meaning 'beech tree.' "
            "Ancient Germanic peoples carved runes into beech boards for writing; "
            "the beech tree became the writing surface, and the writing surface became the book. "
            "English book and beech are cognates from the same root — both derive from *bōkō."
        ),
        roots=["Proto-Germanic *bōkō (beech tree → writing tablet → book)"],
        cognates=["English book (same root)", "English beech tree (same root — both from beech-as-writing-surface)"],
        semantic_shift="'beech tree' → 'beech-bark writing tablet' → 'book'",
    ),
    EtymologyEntry(
        language="de", lemma="Zeit",
        origin_summary=(
            "From Proto-Germanic *tīdaz 'time, period,' related to Old English tīd. "
            "English tide originally meant 'time, season, period' (Yuletide, Christmastide, eventide) "
            "before narrowing to the rise and fall of the sea. "
            "The compound Zeitgeist (Zeit + Geist) 'spirit of the time' was borrowed into English intact."
        ),
        roots=["Proto-Germanic *tīdaz (time, period)"],
        cognates=["English tide (originally 'time' — same root)", "English Yuletide, Christmastide"],
        semantic_shift="English tide: 'time, season' → specifically 'tidal movement of the sea'",
    ),
    EtymologyEntry(
        language="de", lemma="Geist",
        origin_summary=(
            "From Proto-Germanic *gaistaz 'spirit, ghost.' "
            "The word appears in Zeitgeist, Weltgeist, Poltergeist, and Heiliger Geist (Holy Spirit). "
            "English ghost is the direct cognate — Old English gāst meant both 'spirit' and 'ghost.' "
            "The h in ghost was added during early printing through Dutch spelling influence (geest)."
        ),
        roots=["Proto-Germanic *gaistaz (spirit, ghost)"],
        cognates=["English ghost (direct cognate)", "English aghast (frightened by a spirit — same root)"],
    ),
    EtymologyEntry(
        language="de", lemma="Mut",
        origin_summary=(
            "From Proto-Germanic *mōdaz 'spirit, courage, mood, mind.' "
            "In Old High German muot meant the mind or spirit broadly; "
            "the meaning narrowed to 'courage' in modern German. "
            "English mood is the direct cognate, preserving the broader emotional sense. "
            "Related compounds: Übermut (overconfidence), Wehmut (melancholy), Hochmut (arrogance)."
        ),
        roots=["Proto-Germanic *mōdaz (mind, spirit, mood)"],
        cognates=["English mood (direct cognate — same Germanic root)", "English moody (from the same)"],
        semantic_shift="'mind, spirit, emotional state' → 'courage' in German; 'emotional disposition' in English",
    ),
    EtymologyEntry(
        language="de", lemma="Verschlimmbessern",
        origin_summary=(
            "A 19th-century blend of verschlimmern 'to make worse' and verbessern 'to improve.' "
            "Describes making something worse in the process of trying to improve it. "
            "German's capacity for compound words allows this precise concept: "
            "the schlimm (bad) element from verschlimmern hijacks the bessern (improve) "
            "structure of verbessern. No single English equivalent exists."
        ),
        roots=["verschlimmern (to worsen) + verbessern (to improve)", "schlimm (bad) + besser (better)"],
        cognates=["English 'making things worse by fixing them' — no single-word equivalent"],
        semantic_shift="Playful blend; the 'improvement' root is ironically dominated by the 'worsening' element",
    ),

    # ── Russian ──────────────────────────────────────────────────────────────
    EtymologyEntry(
        language="ru", lemma="тоска",
        origin_summary=(
            "From Proto-Slavic *tъska 'anguish, grief.' "
            "Nabokov described тоска as: 'a longing with nothing to long for, "
            "a sick pining, a vague restlessness.' No single English equivalent exists."
        ),
        roots=["Proto-Slavic *tъska (anguish)"],
        cognates=["Polish tęsknota (longing)", "Czech touha (longing)"],
    ),
    EtymologyEntry(
        language="ru", lemma="правда",
        origin_summary=(
            "From Proto-Slavic *pravda 'truth, justice, right,' related to pravyi 'straight, right.' "
            "Pravda was the title of the Soviet newspaper. "
            "The root *prav- also gives ispravit' 'to correct' and upravlyat' 'to govern.'"
        ),
        roots=["Proto-Slavic *pravda (truth, justice)", "Proto-Slavic *pravyi (straight, right)"],
        cognates=["Polish prawda", "Czech pravda", "Serbian pravda"],
    ),
    EtymologyEntry(
        language="ru", lemma="товарищ",
        origin_summary=(
            "From Turkic tavar-ysh 'companion in trade,' from tavar 'goods, wares.' "
            "Originally meant a merchant's travel companion; adopted into Russian as 'comrade.' "
            "Soviet usage politicised it into a revolutionary form of address."
        ),
        roots=["Turkic tavar (goods, wares)"],
        semantic_shift="'merchant's travel companion' → 'political comrade'",
    ),

    # ── Arabic ───────────────────────────────────────────────────────────────
    EtymologyEntry(
        language="ar", lemma="قلم",
        origin_summary=(
            "Borrowed from Greek kalamos 'reed pen,' itself from an older Mediterranean root. "
            "Entered Arabic via early contact between Greek and Arab scholars. "
            "The same Greek root gives English calamus and calligraphy."
        ),
        roots=["Greek kalamos (reed, pen)"],
        cognates=["Hebrew קולמוס qolmus", "Persian قلم qalam", "Turkish kalem"],
    ),
    EtymologyEntry(
        language="ar", lemma="كتاب",
        origin_summary=(
            "From the Arabic root ك-ت-ب (k-t-b) meaning 'to write.' "
            "The trilateral root: kataba (he wrote), kitāb (book), maktaba (library), "
            "kātib (writer). One of the most productive roots in Arabic."
        ),
        roots=["Semitic root k-t-b (to write)"],
        cognates=["Hebrew כתב ktv (to write)", "Aramaic כְּתָב ktāb"],
    ),
    EtymologyEntry(
        language="ar", lemma="علم",
        origin_summary=(
            "From the Semitic root ع-ل-م (ʿ-l-m) meaning 'to know, to mark.' "
            "ʿIlm (knowledge/science) is central to Islamic intellectual tradition. "
            "Related: ʿālim (scholar), taʿallama (to learn), maʿlūm (known)."
        ),
        roots=["Semitic root ʿ-l-m (to know, to mark)"],
        cognates=["Hebrew עלם ʿolam (world — related sense of 'what is known')"],
    ),

    # ── Chinese (Mandarin) ────────────────────────────────────────────────────
    EtymologyEntry(
        language="zh", lemma="茶",
        origin_summary=(
            "From Old Chinese *draa. The word spread along two routes: "
            "the Hokkien pronunciation tê spread by sea, giving English tea and French thé; "
            "Mandarin chá spread overland, giving Russian чай, Persian چای, and Arabic شاي."
        ),
        roots=["Old Chinese *draa (tea plant)"],
        cognates=["English tea (from Hokkien tê)", "Russian чай (from Mandarin chá)", "Arabic شاي"],
    ),
    EtymologyEntry(
        language="zh", lemma="书",
        origin_summary=(
            "Oracle bone script depicted a hand holding a writing brush over a surface. "
            "The character unified 'to write' and 'book/document.' "
            "Simplified 书 descends from traditional 書."
        ),
        roots=["Oracle bone: hand + brush + writing surface"],
        cognates=["Japanese 書 (sho) in compounds: 書道 shodō 'calligraphy'"],
    ),
    EtymologyEntry(
        language="zh", lemma="道",
        origin_summary=(
            "From Old Chinese *lˤuʔ, the character shows a head (首 shǒu) and movement (辶). "
            "Dào means 'way, path, principle, method.' "
            "As the core concept of Taoism it denotes the fundamental nature of the universe."
        ),
        roots=["Old Chinese: 首 (head) + 辶 (movement/road)"],
        cognates=["Japanese 道 (dō/michi) in 柔道 jūdō, 剣道 kendō, 茶道 chadō"],
    ),

    # ── Hebrew ───────────────────────────────────────────────────────────────
    EtymologyEntry(
        language="he", lemma="שלום",
        origin_summary=(
            "From the Semitic root ש-ל-מ (sh-l-m) meaning 'wholeness, completeness, peace.' "
            "Shalom serves as hello, goodbye, and peace. "
            "The root also gives shalem (complete), shillem (to pay), and Solomon (Shlomo). "
            "Arabic salaam shares the same Semitic root."
        ),
        roots=["Semitic root sh-l-m (wholeness, completeness)"],
        cognates=["Arabic سلام salām", "Aramaic שְׁלָמָא šlāmā"],
    ),
    EtymologyEntry(
        language="he", lemma="אמן",
        origin_summary=(
            "From the root א-מ-נ (ʾ-m-n) meaning 'faithfulness, truth, support.' "
            "Used as a liturgical affirmation across Jewish, Christian, and Muslim worship. "
            "Related: emunah (faith), omen (trustworthy sign)."
        ),
        roots=["Semitic root ʾ-m-n (faithfulness, truth)"],
        cognates=["Arabic آمين āmīn", "Greek ἀμήν amēn", "English amen (borrowed)"],
    ),

    # ── Japanese ─────────────────────────────────────────────────────────────
    EtymologyEntry(
        language="ja", lemma="木漏れ日",
        origin_summary=(
            "Compound of 木 (ko/ki, tree) + 漏れ (more, leak/filter through) + 日 (hi, sun/day). "
            "Describes sunlight filtering through tree leaves—a concept and aesthetic sensibility "
            "for which English has no single word."
        ),
        roots=["木 (ki/ko, tree)", "漏れ (more, to leak through)", "日 (hi, sun)"],
    ),
    EtymologyEntry(
        language="ja", lemma="勉強",
        origin_summary=(
            "From Chinese 勉強 (miǎnqiǎng) meaning 'to force, to compel, to make an effort.' "
            "In modern Japanese, benkyō means 'to study.' "
            "The shift reflects the cultural association between diligent effort and learning."
        ),
        roots=["勉 (ben, effort, diligence)", "強 (kyō, strong, force)"],
        cognates=["Chinese 勉强 miǎnqiǎng (reluctantly, barely)"],
        semantic_shift="'forced effort' → 'studying, learning'",
    ),
    EtymologyEntry(
        language="ja", lemma="物の哀れ",
        origin_summary=(
            "Classical concept: 物 (mono, things) + の (no, possessive) + 哀れ (aware, pathos). "
            "Coined by scholar Motoori Norinaga (1730–1801) to describe the aesthetic sensibility "
            "in Japanese literature—a poignant awareness of impermanence."
        ),
        roots=["物 (mono, things, matter)", "哀れ (aware, pathos, bittersweet feeling)"],
    ),

    # ── Greek Koine ───────────────────────────────────────────────────────────
    EtymologyEntry(
        language="grc", lemma="λόγος",
        origin_summary=(
            "From Proto-Indo-European *leg- 'to collect, gather, speak.' "
            "Logos means word, reason, discourse, and cosmic principle. "
            "Used in John 1:1 ('In the beginning was the Word'). "
            "Gives English logic, dialogue, theology, and countless -logy compounds."
        ),
        roots=["PIE *leg- (to gather, speak)", "λέγω legō (to say, to gather)"],
        cognates=["English logic, dialogue, theology (all from logos)"],
    ),
    EtymologyEntry(
        language="grc", lemma="ἀγάπη",
        origin_summary=(
            "Uncertain ultimate origin; used in the Septuagint and New Testament to denote "
            "selfless, unconditional love—distinct from ἔρως (romantic) and φιλία (friendship). "
            "Early Christians chose this word to describe divine love."
        ),
        roots=["ἀγαπάω agapaō (to love, to be content with)"],
        cognates=["Latin caritas (used to translate agapē)", "English agape (borrowed)"],
    ),
    EtymologyEntry(
        language="grc", lemma="εὐαγγέλιον",
        origin_summary=(
            "Compound of εὖ (eu, good) + ἄγγελος (angelos, messenger). "
            "Originally 'reward for good news.' Adopted by early Christians to mean the gospel. "
            "Gives English evangelist, evangelical, and angel."
        ),
        roots=["εὖ eu (good, well)", "ἄγγελος angelos (messenger)"],
        cognates=["English gospel (Old English gōdspel, calque)", "English angel"],
    ),

    # ── Latin ─────────────────────────────────────────────────────────────────
    EtymologyEntry(
        language="la", lemma="persona",
        origin_summary=(
            "Borrowed from Etruscan phersu, meaning a masked character in theater. "
            "Latin persona came to mean 'character in a play,' then 'legal person,' then 'individual.' "
            "Gives English person, personal, personnel, persona."
        ),
        roots=["Etruscan phersu (theatrical mask)"],
        cognates=["English person, personal, persona (all borrowed)", "French personne"],
        semantic_shift="'theatrical mask' → 'role/character' → 'individual person'",
    ),
    EtymologyEntry(
        language="la", lemma="calculus",
        origin_summary=(
            "Diminutive of calx 'limestone, pebble.' Romans counted with small stones. "
            "The mathematical sense was coined by Leibniz (17th c.) from the general meaning "
            "'system of calculation.' Gives English calculate, calculus, calcium, chalk."
        ),
        roots=["calx (limestone, pebble)"],
        cognates=["English calculate, calcium, chalk (related Latin roots)"],
        semantic_shift="'small pebble (for counting)' → 'calculation' → 'branch of mathematics'",
    ),
    EtymologyEntry(
        language="la", lemma="sinister",
        origin_summary=(
            "Originally simply 'left (hand side).' In Roman augury, omens on the left were "
            "unfavorable. This superstition caused the word to drift to mean 'unlucky, bad.' "
            "English sinister was borrowed in the sense 'evil, threatening.'"
        ),
        roots=["Proto-Indo-European *seni- (aside, away from)"],
        cognates=["French sinistre", "Italian sinistro", "Spanish siniestro"],
        semantic_shift="'left (hand)' → 'unlucky (left-side omen)' → 'evil, threatening'",
    ),
]


#: Default store — import and call .get() directly in most code paths.
DEFAULT_STORE: EtymologyStore = EtymologyStore(_CURATED)
