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

    # ── French — Arabic borrowings ───────────────────────────────────────────
    EtymologyEntry(
        language="fr", lemma="alcool",
        origin_summary=(
            "From Arabic al-kuhul 'antimony powder used as eye makeup.' "
            "Arab alchemists extended the term to any fine purified substance, then to "
            "distilled spirits. Medieval Latin alcohole → French alcool. "
            "English borrowed alcohol from the same Arabic root via French."
        ),
        roots=["Arabic al-kuhul (fine antimony powder)"],
        cognates=["English alcohol (same Arabic source)", "Spanish alcohol"],
        semantic_shift="'fine eye-makeup powder' → 'any pure distillate' → 'ethyl alcohol'",
    ),
    EtymologyEntry(
        language="fr", lemma="algèbre",
        origin_summary=(
            "From Arabic al-jabr 'the reunion of broken parts' — the operation of moving "
            "terms across an equation. The word comes from Muhammad al-Khwarizmi's 9th-century "
            "treatise title Kitāb al-mukhtaṣar fī ḥisāb al-jabr wa-l-muqābala. "
            "His name also gives English algorithm."
        ),
        roots=["Arabic al-jabr (reunion of broken parts)"],
        cognates=["English algebra (same Arabic source)", "Spanish álgebra"],
    ),
    EtymologyEntry(
        language="fr", lemma="hasard",
        origin_summary=(
            "From Arabic az-zahr 'the dice,' via Spanish azar 'chance, bad luck.' "
            "Dice games spread through the medieval Mediterranean; the Arabic word for "
            "the die entered French as the general word for chance or risk. "
            "English hazard is borrowed from Old French hasard."
        ),
        roots=["Arabic az-zahr (the dice)", "Spanish azar (chance, misfortune)"],
        cognates=["English hazard (from Old French hasard)"],
        semantic_shift="'dice (game piece)' → 'chance, luck' → 'risk, danger'",
    ),
    EtymologyEntry(
        language="fr", lemma="coton",
        origin_summary=(
            "From Arabic qutn (also spelled qutun), the standard Arabic term for the cotton plant. "
            "Spread through medieval Mediterranean trade via Italian cotone and Spanish algodón. "
            "English cotton derives from the same Arabic root via Old French coton."
        ),
        roots=["Arabic qutn (cotton plant)"],
        cognates=["English cotton (from Old French coton)", "Italian cotone", "Spanish algodón"],
    ),
    EtymologyEntry(
        language="fr", lemma="sofa",
        origin_summary=(
            "From Arabic suffah 'a low wooden platform or bench,' often raised and carpeted. "
            "Via Ottoman Turkish sofa (a furnished platform or sitting area). "
            "Entered European languages through contact with Ottoman culture in the 17th century. "
            "English sofa is borrowed from French."
        ),
        roots=["Arabic suffah (raised bench, platform)"],
        cognates=["English sofa (same Arabic origin via Turkish)", "Spanish sofá"],
    ),
    EtymologyEntry(
        language="fr", lemma="sirop",
        origin_summary=(
            "From Arabic sharab 'a drink, something drunk,' from shariba 'to drink.' "
            "Medieval contact gave French sirop and English syrup. "
            "The same root gives English sherbet (via Turkish/Persian şerbet) "
            "and shrub (the drink — via Arabic sharab)."
        ),
        roots=["Arabic sharab (a drink)", "Arabic shariba (to drink)"],
        cognates=["English syrup (same Arabic source)", "English sherbet", "Turkish şerbet"],
    ),
    EtymologyEntry(
        language="fr", lemma="jupe",
        origin_summary=(
            "From Arabic jubba, a long outer garment with wide sleeves, worn in the Near East. "
            "Via medieval Mediterranean trade: Arabic jubba → Italian giubba → Old French jupe. "
            "The original meaning 'long robe' narrowed in French to 'skirt.' "
            "English 'jumper' (the garment) may derive from the same Arabic source via French jupon."
        ),
        roots=["Arabic jubba (long outer garment with wide sleeves)"],
        cognates=["Italian giubba", "English jumper (possibly via French jupon — disputed)"],
        semantic_shift="'full-length robe' → 'undershirt or bodice' → 'skirt' (modern French)",
    ),
    EtymologyEntry(
        language="fr", lemma="café",
        origin_summary=(
            "From Arabic qahwa 'a kind of wine, coffee,' via Turkish kahve → French café. "
            "English coffee came independently via Turkish kahve or Dutch koffie. "
            "English café is borrowed directly from French, preserving the 'coffeehouse' sense "
            "that Arabic qahwa extended to when coffee replaced wine."
        ),
        roots=["Arabic qahwa (coffee, a brewed drink)"],
        cognates=["English coffee (same Arabic root via Turkish/Dutch)", "Italian caffè", "Turkish kahve"],
        semantic_shift="'wine-like drink' → 'coffee' → 'place where coffee is served'",
    ),
    EtymologyEntry(
        language="fr", lemma="chimie",
        origin_summary=(
            "From Arabic al-kīmiyāʾ 'the transmutation art,' itself from Greek khymeia "
            "'the art of alloying metals' or from Coptic/Egyptian kēme 'black earth' (Egypt). "
            "Arabic al-kīmiyāʾ → Medieval Latin alchimia → French alchimie/chimie. "
            "Gives English alchemy and chemistry — same word, different moment in the discipline's history."
        ),
        roots=["Arabic al-kīmiyāʾ (art of transmutation)", "possibly Coptic kēme (black earth — Egypt)"],
        cognates=["English alchemy (the mystical stage)", "English chemistry (the scientific stage)"],
        semantic_shift="'alchemical transmutation art' → 'experimental science of matter'",
    ),
    EtymologyEntry(
        language="fr", lemma="zéro",
        origin_summary=(
            "From Arabic sifr 'empty, nothing,' the Arabic word for the absence of quantity. "
            "Via Medieval Latin zephirum (early 13th c.) and Italian zero. "
            "Arabic sifr also gives English cipher — both 'zero' and 'secret code' "
            "stem from the revolutionary concept of representing nothing with a symbol."
        ),
        roots=["Arabic sifr (empty, nothing, zero)"],
        cognates=["English zero (same Arabic source)", "English cipher (from the same sifr)"],
    ),

    # ── French — Frankish/Germanic substratum ─────────────────────────────────
    EtymologyEntry(
        language="fr", lemma="guerre",
        origin_summary=(
            "From Old High German/Frankish werra 'strife, discord.' "
            "The conquering Franks displaced Latin bellum with their vernacular word for conflict. "
            "English war derives from the same Germanic root via Norman French guerre. "
            "The parallel Latin word bellum survives in English as bellicose, belligerent, rebel."
        ),
        roots=["Frankish/Old High German werra (strife, discord)"],
        cognates=["English war (same Germanic root via Norman French)", "Spanish guerra"],
        semantic_shift="'strife, discord between neighbors' → 'organised armed conflict'",
    ),
    EtymologyEntry(
        language="fr", lemma="garder",
        origin_summary=(
            "From Frankish *wardōn 'to watch over, guard,' from the same Germanic root "
            "as English ward, warden, and guard. "
            "Ward entered English directly from Old English; guard entered via French garder. "
            "Both paths lead to the same Frankish verb — a doubled borrowing."
        ),
        roots=["Frankish *wardōn (to watch, guard)"],
        cognates=["English guard (from French garder)", "English ward (direct from Old English, same root)"],
    ),
    EtymologyEntry(
        language="fr", lemma="blanc",
        origin_summary=(
            "From Proto-Germanic *blankaz 'shining, white.' "
            "The same root gives English blank (a white or unmarked surface) and "
            "blanch (to whiten). German blank means 'shiny, clean.' "
            "The French feminine blanche gave the name Blanche — 'the white one.'"
        ),
        roots=["Proto-Germanic *blankaz (shining, gleaming, white)"],
        cognates=["English blank (same root)", "English blanch (to whiten)", "German blank (shiny)"],
    ),
    EtymologyEntry(
        language="fr", lemma="riche",
        origin_summary=(
            "From Frankish *rīkī 'powerful, mighty,' related to Proto-Germanic *rīkijaz. "
            "In Frankish society, power and wealth were inseparable; the meaning shifted to 'wealthy.' "
            "Gives English rich (via Old English rīce, same root), realm (via Latin regnum — cognate), "
            "and German Reich 'empire.'"
        ),
        roots=["Frankish *rīkī (powerful, mighty)"],
        cognates=["English rich (same Germanic root via Old English)", "German Reich (empire)"],
        semantic_shift="'powerful, ruling' → 'wealthy, well-provisioned'",
    ),
    EtymologyEntry(
        language="fr", lemma="garçon",
        origin_summary=(
            "From Frankish *wrakjo 'vagabond, wanderer, exile.' "
            "The social trajectory: wanderer → menial servant → young male servant → boy. "
            "The meaning 'waiter' is a metonymy from 'boy (who serves).' "
            "English has no direct cognate; the German Recke 'warrior, hero' shares the root but "
            "went in the opposite social direction."
        ),
        roots=["Frankish *wrakjo (vagabond, wanderer, exile)"],
        semantic_shift="'vagrant, exile' → 'menial servant' → 'boy' → 'waiter'",
    ),

    # ── French — Latin with semantic shift ────────────────────────────────────
    EtymologyEntry(
        language="fr", lemma="tête",
        origin_summary=(
            "From Latin testa 'earthenware pot, shell, skull.' "
            "Classical Latin used caput for 'head' (giving English capital, captain, chapter). "
            "Testa began as colloquial slang — the hard skull likened to a clay pot. "
            "Over time testa displaced caput entirely in spoken Latin, giving French tête. "
            "English test (as in assay by crucible) comes from the same Latin testa."
        ),
        roots=["Latin testa (earthenware pot, tile, shell)"],
        cognates=["English test (assay crucible — same Latin root)", "Italian testa (head)"],
        semantic_shift="'clay pot, hard shell' → slang for 'skull' → 'head' (replacing caput)",
    ),
    EtymologyEntry(
        language="fr", lemma="fenêtre",
        origin_summary=(
            "From Latin fenestra 'window, opening for light.' "
            "Latin fenestra possibly borrowed from Etruscan. "
            "Gives English fenestration (the arrangement of windows in a building) and "
            "defenestration (the act of throwing someone out of a window — coined for the "
            "1618 Defenestration of Prague)."
        ),
        roots=["Latin fenestra (window, opening for light) — possibly Etruscan"],
        cognates=["English fenestration, defenestration (learned Latin borrowings)"],
    ),
    EtymologyEntry(
        language="fr", lemma="voix",
        origin_summary=(
            "From Latin vox, vocis 'voice, sound, word.' "
            "One of the most productive Latin roots in French and English: "
            "gives English voice (via Norman French voix), vocal, vocabulary, vowel "
            "(the voiced letters), invoke, revoke, advocate, vocation — all from vox."
        ),
        roots=["Latin vox / vocis (voice, sound)"],
        cognates=["English voice (from French voix)", "English vocal, vowel, invoke, vocation (all from vox)"],
    ),
    EtymologyEntry(
        language="fr", lemma="argent",
        origin_summary=(
            "From Latin argentum 'silver.' The chemical symbol Ag comes from argentum. "
            "Latin used argentum for both the metal and coined money (since early coins were silver). "
            "French inherited both senses; argent now primarily means 'money.' "
            "English keeps the metal sense in Argentina (Río de la Plata — 'silver river'), "
            "and argent in heraldry (the silver tincture)."
        ),
        roots=["PIE *h₂erǵ- (shining, silver)", "Latin argentum (silver)"],
        cognates=["English argent (heraldry — silver)", "Italian argento", "Argentina (the country)"],
        semantic_shift="'the metal silver' → 'silver coinage' → 'money in general'",
    ),
    EtymologyEntry(
        language="fr", lemma="travail",
        origin_summary=(
            "From Medieval Latin tripalium 'a three-staked instrument of torture,' "
            "used to restrain horses and oxen for shoeing. "
            "To work (travailler) was equated with being bound to the tripalium. "
            "English travel is the same word — to travel was to toil, to undergo hardship. "
            "Both English travail (labor, hardship) and travel descend from the same Latin root."
        ),
        roots=["Medieval Latin tripalium (three-stake restraint for animals)", "tri- (three) + palus (stake)"],
        cognates=["English travail (hard labor — same word)", "English travel (same word — toil of the road)"],
        semantic_shift="'torture device' → 'to toil, labor' → 'to journey (with hardship)'",
    ),
    EtymologyEntry(
        language="fr", lemma="rival",
        origin_summary=(
            "From Latin rivalis 'one who shares a stream,' from rivus 'stream, brook.' "
            "Neighbors drawing from the same irrigation stream were natural rivals for its water. "
            "The word river also comes from rivus — so rivals are literally river-sharers. "
            "English borrowed both rival (unchanged) and river (via Old French rivière)."
        ),
        roots=["Latin rivus (stream, brook)", "Latin rivalis (one who shares a stream)"],
        cognates=["English rival (from Latin rivalis)", "English river (from Old French rivière, same root)"],
        semantic_shift="'one who shares a stream (and competes for its water)' → 'competitor in any domain'",
    ),
    EtymologyEntry(
        language="fr", lemma="hôpital",
        origin_summary=(
            "From Latin hospitale 'guest quarters,' from hospes 'host, guest' — "
            "a word that means both at once, since host and guest are two roles in one relationship. "
            "Medieval hospitals were first and foremost pilgrim hostels. "
            "The same root gives English hospital, hotel (from hôtel), hostel, hospice, hospitable, host."
        ),
        roots=["Latin hospes (host and guest in one word)", "Latin hospitale (guest quarters)"],
        cognates=["English hospital, hotel, hostel, hospice, host (all from hospes)"],
        semantic_shift="'guest quarters, place of hospitality' → 'place for the sick and infirm'",
    ),
    EtymologyEntry(
        language="fr", lemma="joie",
        origin_summary=(
            "From Latin gaudia, the plural of gaudium 'joy, pleasure.' "
            "The plural form gaudia (joys) was used in Late Latin as a singular collective. "
            "English joy is borrowed from Old French joie. "
            "The root also gives English enjoy (en + joie) and rejoice."
        ),
        roots=["Latin gaudium (joy, delight)", "Latin gaudēre (to rejoice)"],
        cognates=["English joy, enjoy, rejoice (all from Old French joie/Latin gaudia)"],
    ),
    EtymologyEntry(
        language="fr", lemma="main",
        origin_summary=(
            "From Latin manus 'hand.' One of the most productive Latin roots: "
            "gives English manual, manipulate, manufacture (manu + facere = to make by hand), "
            "manage (via Italian maneggiare), maneuver (manu + operare = to work by hand), "
            "manicure, and maintain. "
            "The French derivative maintenir (to maintain) literally means 'to hold in hand.'"
        ),
        roots=["Latin manus (hand)"],
        cognates=["English manual, manipulate, manufacture, maneuver, maintain (all from manus)"],
    ),
    EtymologyEntry(
        language="fr", lemma="nuance",
        origin_summary=(
            "From Old French nuer 'to shade (colors),' from Latin nubes 'cloud.' "
            "A nuance is literally 'a cloudlike shading' — a subtle gradation of color, "
            "then meaning, then feeling. "
            "English borrowed nuance from French in the 18th century, retaining the sense "
            "of subtle distinction too fine for a single word."
        ),
        roots=["Latin nubes (cloud)", "Old French nuer (to shade, to cloud)"],
        cognates=["English nuance (borrowed from French)", "English nebula (from Latin nubes cognate)"],
        semantic_shift="'cloud' → 'gradation of shade in color' → 'subtle distinction in meaning'",
    ),
    EtymologyEntry(
        language="fr", lemma="bureau",
        origin_summary=(
            "From Old French burel, a coarse dark woolen cloth used to cover writing desks. "
            "The cloth → the desk it covered → the room containing the desk → the office → "
            "the government department. English bureaucracy (bureau + Greek kratos 'rule') "
            "was coined in the 18th century, satirising the desk-bound machinery of administration."
        ),
        roots=["Old French burel (coarse woolen cloth)", "Late Latin burra (shaggy cloth)"],
        cognates=["English bureau, bureaucracy (from French bureau)"],
        semantic_shift="'coarse desk-cloth' → 'writing desk' → 'office room' → 'government department'",
    ),
    EtymologyEntry(
        language="fr", lemma="voilà",
        origin_summary=(
            "Contraction of vois là 'see there' — imperative of voir (to see) + là (there). "
            "From Latin vide illac 'look there.' "
            "The parallel voici (see here) = vois + ici. "
            "English borrowed voilà as an exclamation of presentation; "
            "it is frequently misspelled viola (the instrument) in English."
        ),
        roots=["Latin vidēre (to see)", "Latin illac (there)"],
        cognates=["English voilà (borrowed)", "Italian eccolo (see it there — parallel structure)"],
    ),
    EtymologyEntry(
        language="fr", lemma="journée",
        origin_summary=(
            "From Latin diurnus 'of the day,' from dies 'day.' "
            "The Latin root gives French jour (day), journée (a day's length or events), "
            "journal (daily record), and journey — English borrowed journey as 'a day's travel.' "
            "The same Latin dies gives English diary, dial (sundial), and dismal (dies mali, 'evil days')."
        ),
        roots=["Latin dies (day)", "Latin diurnus (daily)"],
        cognates=["English journey (from French journée — a day's travel)", "English journal, diary (from dies)"],
        semantic_shift="'a day's duration' → 'a day's work or travel' → 'trip' (in English journey)",
    ),

    # ── French — faux amis (false cognates) ──────────────────────────────────
    EtymologyEntry(
        language="fr", lemma="librairie",
        origin_summary=(
            "From Latin librarium 'place for books,' from liber 'book' (originally 'inner bark'). "
            "A librairie is a bookshop — where books are sold. "
            "A bibliothèque is a library — where books are lent. "
            "English 'library' came from the same Latin root via Old French but shifted to mean "
            "the lending institution; French kept the commercial sense for librairie."
        ),
        roots=["Latin liber (book, inner bark of tree)", "Latin librarium (book-place)"],
        cognates=["English library (same Latin root — but means lending library, not bookshop)"],
        semantic_shift="Latin librarium → French: bookshop; Latin libraria → English: lending library",
    ),
    EtymologyEntry(
        language="fr", lemma="sensible",
        origin_summary=(
            "From Latin sensibilis 'able to perceive through the senses, sensitive.' "
            "In French, sensible = emotionally sensitive, perceptive, capable of feeling. "
            "In English, 'sensible' shifted to mean 'reasonable, practical, showing good sense.' "
            "This is a classic faux ami: a French sensible person feels deeply; "
            "an English sensible person acts practically — nearly opposite emphases."
        ),
        roots=["Latin sensibilis (able to feel, perceptible)", "Latin sensus (sense, feeling)"],
        cognates=["English sensible (false friend — now means 'reasonable' not 'sensitive')", "English sensitive (closer to French sensible)"],
        semantic_shift="'capable of feeling' → French: 'emotionally perceptive'; English: 'showing practical good sense'",
    ),
    EtymologyEntry(
        language="fr", lemma="actuellement",
        origin_summary=(
            "From French actuel 'current, present,' from Latin actualis 'active, practical.' "
            "Actuellement = currently, at this moment in time. "
            "English 'actually' shifted from 'in active reality' to 'in truth, as a matter of fact.' "
            "The faux ami trap: 'actuellement, je travaille' = 'I'm currently working,' "
            "not 'I'm actually working' (which implies correction or surprise)."
        ),
        roots=["Latin actualis (relating to acts, practical)", "Latin actus (action, deed)"],
        cognates=["English actually (false friend — means 'in truth/fact,' not 'currently')"],
        semantic_shift="'in the present moment' (French) vs. 'in reality, as a corrective' (English)",
    ),
    EtymologyEntry(
        language="fr", lemma="location",
        origin_summary=(
            "From Latin locatio 'a letting, renting,' from locare 'to let, to hire out' (from locus 'place'). "
            "In French, location = rental (voiture de location = rental car). "
            "English 'location' kept the spatial sense 'a place.' "
            "The faux ami trap: a French location is a financial arrangement; an English location is a place."
        ),
        roots=["Latin locus (place)", "Latin locare (to let, rent out)", "Latin locatio (rental)"],
        cognates=["English location (false friend — means 'a place,' not 'a rental')", "English local, locate (same root)"],
        semantic_shift="French: 'rental transaction'; English: 'the place where something is'",
    ),

    # ── French — cultural and historical etymology ────────────────────────────
    EtymologyEntry(
        language="fr", lemma="grève",
        origin_summary=(
            "From Old French grève 'gravel bank, sandy riverbank,' from Latin grava 'gravel.' "
            "The Place de Grève — a graveled riverside square beside the Seine in Paris — "
            "was where day-laborers gathered to be hired. 'Faire grève' (to go to the Grève) "
            "came to mean withholding one's labor. The square is now Place de l'Hôtel de Ville; "
            "the word grève lives on as the French word for 'strike.'"
        ),
        roots=["Latin grava (gravel, coarse sand)", "Old French grève (gravel bank)"],
        cognates=["English gravel (from Old French gravele, same root)"],
        semantic_shift="'gravel riverbank (the Place de Grève)' → 'labor market meeting point' → 'work stoppage'",
    ),
    EtymologyEntry(
        language="fr", lemma="silhouette",
        origin_summary=(
            "Eponym from Étienne de Silhouette (1709–1767), French finance minister under Louis XV. "
            "His severe austerity measures made him notorious; cheap black profile portraits "
            "— made quickly, without depth or detail — were mockingly named after him. "
            "A silhouette portrait was, like his policies, a mere outline, stripped to essentials. "
            "English borrowed both the word and its meaning unchanged."
        ),
        roots=["Étienne de Silhouette (1709–1767), French finance minister"],
        cognates=["English silhouette (borrowed from French)"],
        semantic_shift="Proper name → 'cheap black-profile portrait' → 'any dark outline against light'",
    ),
    EtymologyEntry(
        language="fr", lemma="cliché",
        origin_summary=(
            "From cliquer 'to click,' imitating the sound of a stereotype printing plate being cast. "
            "In 19th-century typography, a cliché (or stereotype) was a metal plate cast from a mold "
            "of set type, allowing unlimited reprinting of the same image or text. "
            "The plate's repetitive use extended metaphorically to any overused phrase or idea. "
            "English borrowed cliché in the sense of a hackneyed expression."
        ),
        roots=["Old French cliquer (to click — imitative of the casting sound)"],
        cognates=["English cliché (borrowed)", "English stereotype (same printing origin — stereos 'solid' + typos 'impression')"],
        semantic_shift="'cast printing plate (for reprinting)' → 'any formulaic, overused expression'",
    ),
    EtymologyEntry(
        language="fr", lemma="boulevard",
        origin_summary=(
            "From Middle Dutch bolwerk 'bulwark' (bol 'plank' + werk 'work, structure'). "
            "Paris's grand boulevards were built in the 17th century on the filled-in medieval "
            "city ramparts — literally atop the old defensive bulwarks. "
            "English borrowed boulevard from French and bulwark directly from Middle Dutch/Low German — "
            "both words trace to the same source."
        ),
        roots=["Middle Dutch bolwerk (bulwark, defensive rampart)", "bol (plank) + werk (structure)"],
        cognates=["English boulevard (from French)", "English bulwark (from the same Dutch source — same word, different path)"],
        semantic_shift="'defensive rampart' → 'promenade built atop the leveled ramparts' → 'wide urban avenue'",
    ),

    # ── French — Norman borrowings preserved in English ───────────────────────
    EtymologyEntry(
        language="fr", lemma="bœuf",
        origin_summary=(
            "From Latin bos, bovis 'ox, cattle.' "
            "After the Norman Conquest (1066), French-speaking lords ate the animals tended "
            "by Anglo-Saxon peasants: the peasant kept the cow (Old English cū); "
            "the lord ate the beef (Norman French bœuf). "
            "The same split applies: porc/pork, mouton/mutton, veau/veal, cerf/venison."
        ),
        roots=["Latin bos / bovis (ox, cattle)"],
        cognates=["English beef (from Norman French bœuf)", "English bovine (from the same Latin root)"],
    ),
    EtymologyEntry(
        language="fr", lemma="mouton",
        origin_summary=(
            "From Gaulish Celtic multo 'sheep,' possibly pre-Celtic. "
            "After 1066: Anglo-Saxon farmers kept sheep (Old English scēap); "
            "Norman lords ate mutton (Old French mouton). "
            "Mouton also gives English mutton-chop (the lamb cut, then the whisker style) "
            "and mouton (sheepskin processed as fake fur)."
        ),
        roots=["Gaulish multo (sheep — pre-Latin Gaulish word)"],
        cognates=["English mutton (from Norman French mouton)", "English mutton-chop (same)"],
    ),
    EtymologyEntry(
        language="fr", lemma="porc",
        origin_summary=(
            "From Latin porcus 'pig, hog.' "
            "The Norman layer: Saxon farmers kept pigs (Old English picga); "
            "Norman lords ate pork (Old French porc). "
            "The same Latin porcus gives English porcupine (literally 'spiny pig,' from porcus + spina) "
            "and porcelain (from Italian porcellana — the pig-cowrie shell whose shape it resembled)."
        ),
        roots=["Latin porcus (pig)"],
        cognates=["English pork (from Norman French porc)", "English porcupine, porcelain (from the same Latin root)"],
    ),

    # ── French — borrowings from Italian ─────────────────────────────────────
    EtymologyEntry(
        language="fr", lemma="ballet",
        origin_summary=(
            "From Italian balletto, diminutive of ballo 'dance,' from ballare 'to dance.' "
            "Italian court dance came to France through Catherine de' Medici (c. 1533–1589). "
            "French masters refined and codified the art form, then exported it to the world "
            "with French terminology (plié, arabesque, entrechat, pas de deux) — "
            "all French, despite the Italian origin of the word ballet."
        ),
        roots=["Italian ballare (to dance)", "Italian ballo (dance)", "Italian balletto (little dance)"],
        cognates=["English ballet (borrowed via French)", "English ball (formal dance — same Italian root)"],
    ),
    EtymologyEntry(
        language="fr", lemma="camarade",
        origin_summary=(
            "From Spanish camarada 'chamber-mate, room-sharer,' from cámara 'chamber, room,' "
            "from Latin camera 'vaulted room.' "
            "Soldiers billeted together in a camera (room) were camaradas. "
            "French adopted camarade; English comrade came via Dutch kameraad from the same Spanish source. "
            "Camera also gives English camera obscura (dark chamber) and, through that, the camera."
        ),
        roots=["Latin camera (vaulted room, chamber)", "Spanish camarada (room-sharer)"],
        cognates=["English comrade (via Dutch kameraad, same Spanish source)", "English camera (same Latin root)"],
    ),

    # ── French — borrowings from Greek ────────────────────────────────────────
    EtymologyEntry(
        language="fr", lemma="bibliothèque",
        origin_summary=(
            "From Greek bibliothēkē 'book-chest' (biblion 'book' + thēkē 'chest, container'). "
            "Biblion itself comes from byblos — the ancient Phoenician city of Byblos (modern Jbeil, Lebanon) "
            "was the major papyrus trade hub. "
            "Gives English Bible (the book), bibliography (list of books), bibliophile. "
            "Note the faux ami: French bibliothèque = library; librairie = bookshop."
        ),
        roots=["Greek byblos (papyrus, from city Byblos)", "Greek biblion (book)", "Greek thēkē (box, container)"],
        cognates=["English Bible, bibliography, bibliophile (all from Greek biblion)"],
    ),
    EtymologyEntry(
        language="fr", lemma="catastrophe",
        origin_summary=(
            "From Greek katastrophē 'overturning, sudden end,' from kata 'down' + strephein 'to turn.' "
            "Originally a theater term for the final reversal in a Greek play — the tragic turning point. "
            "Aristotle used it in Poetics. French and English both borrowed it in the 16th century "
            "for any sudden disastrous reversal, theatrical or real."
        ),
        roots=["Greek kata (down, against)", "Greek strephein (to turn)"],
        cognates=["English catastrophe, catastrophic (from Greek via French and Latin)"],
        semantic_shift="'final overturning scene in a play' → 'any sudden disastrous event'",
    ),
    EtymologyEntry(
        language="fr", lemma="enthousiasme",
        origin_summary=(
            "From Greek enthousiazein 'to be inspired by a god,' from entheos 'god-within' "
            "(en 'in' + theos 'god'). "
            "Being enthusiastic originally meant being divinely possessed — seized by a deity. "
            "Early English uses of enthusiasm (17th century) described religious frenzy, "
            "often as a term of mockery. Only later did it acquire its positive secular meaning."
        ),
        roots=["Greek en (in)", "Greek theos (god)", "Greek entheos (divinely inspired)"],
        cognates=["English enthusiasm, enthusiast (from Greek via French and Latin)"],
        semantic_shift="'seized by a god, divinely possessed' → 'religious fervor' → 'intense eagerness'",
    ),
    EtymologyEntry(
        language="fr", lemma="mystère",
        origin_summary=(
            "From Greek mysterion 'secret rite,' from myein 'to close the lips (or eyes).' "
            "Initiates of Greek mystery cults were sworn to silence about the rites they witnessed. "
            "The word entered Latin as mysterium, then Old French as mistere, "
            "also giving the medieval mystery play (a dramatization of scripture — from the same source). "
            "English borrowed both mystery and mystic."
        ),
        roots=["Greek myein (to close eyes or lips)", "Greek mysterion (secret rite)"],
        cognates=["English mystery, mystic, mysterious (from Greek mysterion via Latin)"],
        semantic_shift="'sworn-secret religious rite' → 'anything hidden or unexplained'",
    ),

    # ── French — miscellaneous high-value entries ─────────────────────────────
    EtymologyEntry(
        language="fr", lemma="bizarre",
        origin_summary=(
            "Disputed. Likely from Spanish bizarro 'brave, bold, extravagant,' itself possibly "
            "from Basque bizar 'beard' — bearded soldiers were seen as fierce and bold. "
            "The meaning shifted in French from 'bold, extravagant' to 'strange, odd.' "
            "English borrowed bizarre from French in the 17th century with the 'strange' sense already fixed."
        ),
        roots=["Spanish bizarro (brave, bold, extravagant)", "possibly Basque bizar (beard)"],
        cognates=["English bizarre (borrowed from French)"],
        semantic_shift="'brave, bold (beard-as-warrior marker)' → 'extravagant' → 'strange, odd'",
    ),
    EtymologyEntry(
        language="fr", lemma="genre",
        origin_summary=(
            "From Latin genus, generis 'kind, type, birth, origin,' from gignere 'to beget.' "
            "In French, genre covers both 'literary/artistic category' and 'grammatical gender' — "
            "the same word. English borrowed genre for the artistic category and kept gender "
            "(from the same Latin root) for the grammatical/biological sense. "
            "Also gives English genus, generic, generate, degenerate."
        ),
        roots=["Latin gignere (to beget, to give birth)", "Latin genus / generis (kind, type, birth)"],
        cognates=["English genre (artistic type)", "English gender (grammatical/biological — same Latin root)", "English genus, generate"],
    ),
    EtymologyEntry(
        language="fr", lemma="souvenir",
        origin_summary=(
            "From Latin subvenire 'to come to mind, to come to one's aid' (sub 'up from below' + venire 'to come'). "
            "A souvenir is literally something that 'comes up' into memory. "
            "In French, souvenir (verb) = to remember; (noun) = a memory or keepsake. "
            "English borrowed the noun in the 18th century, narrowing it to a purchased memento."
        ),
        roots=["Latin sub (up from below, toward)", "Latin venire (to come)", "Latin subvenire (to come to mind)"],
        cognates=["English souvenir (borrowed)", "English convene, venture, prevent (all from venire)"],
        semantic_shift="'to come up into the mind' → 'a memory' → 'a purchased keepsake'",
    ),
    EtymologyEntry(
        language="fr", lemma="fête",
        origin_summary=(
            "From Latin festa, plural of festum 'festival day, holiday.' "
            "The same root gives English feast (via Norman French feste), festival, festive, festivity. "
            "English has borrowed fête directly from French to describe outdoor public celebrations, "
            "preserving the French word alongside the English feast — "
            "another case of the same Latin word arriving by two different historical routes."
        ),
        roots=["Latin festum (festival, holiday)", "Latin festa (plural: festival days)"],
        cognates=["English feast (from Norman French feste — same Latin root)", "English festival, festive (from Latin festa)"],
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
    EtymologyEntry(
        language="it", lemma="strada",
        origin_summary=(
            "From Latin strata (via) 'paved road,' past participle of sternere 'to lay flat, to pave.' "
            "The same root gives English street (via Old English stræt) and the German Straße."
        ),
        roots=["Latin strata via (paved road)", "Latin sternere (to lay flat, spread out)"],
        cognates=["English street", "German Straße", "Spanish estrada", "French route (divergent)"],
        semantic_shift="'paved surface' → 'road, street'",
    ),
    EtymologyEntry(
        language="it", lemma="parola",
        origin_summary=(
            "From Late Latin parabola 'speech, saying,' itself from Greek parabolē 'comparison, parable.' "
            "The Greek original is para (beside) + bolē (throw) — a 'throwing beside' or comparison. "
            "French parole (word, speech) and Spanish palabra share this origin."
        ),
        roots=["Greek parabolē (comparison, parable)", "Latin parabola (speech)"],
        cognates=["French parole (word)", "Spanish palabra", "English parable, parabola (same Greek root)"],
        semantic_shift="'comparison, parable' → 'speech' → 'word'",
    ),
    EtymologyEntry(
        language="it", lemma="influenza",
        origin_summary=(
            "From Medieval Latin influentia 'flowing in,' from influere 'to flow into.' "
            "Medieval astrologers attributed disease epidemics to the 'influence' of stars. "
            "English borrowed the word during the 1743 epidemic; the abbreviation flu dates to 1839."
        ),
        roots=["Latin influere (to flow in)", "Latin fluere (to flow)"],
        cognates=["English influenza, flu, influence (all from same root)", "French grippe (different)"],
        semantic_shift="'flowing in (of celestial bodies)' → 'epidemic caused by stellar influence' → 'the disease itself'",
    ),
    EtymologyEntry(
        language="it", lemma="malaria",
        origin_summary=(
            "Compound of Italian mala 'bad' + aria 'air.' Before germ theory, "
            "the disease was believed to come from swamp vapors. "
            "The word entered English in the 18th century; the actual cause (Plasmodium parasite) "
            "was not identified until 1880."
        ),
        roots=["Latin mala (bad, evil)", "Latin aer/aria (air)"],
        cognates=["English malaria (borrowed directly)", "Italian aria (also means melody in music)"],
        semantic_shift="'bad air (miasma)' → the disease itself",
    ),
    EtymologyEntry(
        language="it", lemma="bravo",
        origin_summary=(
            "From Italian bravo 'brave, skilled, bold,' possibly from Latin barbarus 'foreign, barbarous.' "
            "Bravo is the masculine form; brava is used for female performers. "
            "In 16th-century Italian, bravo meant a hired assassin — the 'brave' one for hire."
        ),
        roots=["Possibly Latin barbarus (foreign, barbarous)"],
        cognates=["Spanish bravo (fierce, brave)", "French brave", "English brave"],
        semantic_shift="'barbarous, ferocious' → 'brave' → 'exclamation of praise'",
    ),
    EtymologyEntry(
        language="it", lemma="vendetta",
        origin_summary=(
            "From Italian vendetta 'revenge,' from Latin vindicta 'vengeance, protection.' "
            "Vindicta shares its root with vindicare 'to claim, avenge' — the source of "
            "English vindicate, vindictive, and avenge."
        ),
        roots=["Latin vindicta (vengeance, protection)", "Latin vindicare (to claim, avenge)"],
        cognates=["English vindictive, vindicate (same Latin root)", "Spanish venganza (different)"],
        semantic_shift="'legal vengeance' → 'blood feud between families'",
    ),
    EtymologyEntry(
        language="it", lemma="diva",
        origin_summary=(
            "From Latin diva 'goddess,' feminine of divus 'divine, god.' "
            "Applied to great opera singers in the 19th century as a term of reverence. "
            "Modern usage extended to any dominant female performer or demanding celebrity."
        ),
        roots=["Latin divus/diva (divine, god/goddess)"],
        cognates=["English divine, deity (related)", "Spanish diva", "French diva"],
        semantic_shift="'goddess' → 'celebrated opera soprano' → 'demanding celebrity'",
    ),
    EtymologyEntry(
        language="it", lemma="graffiti",
        origin_summary=(
            "Plural of graffito 'little scratch,' from graffio 'scratch,' from graffiare 'to scratch.' "
            "Ultimately from Greek graphein 'to write' — the same root as graph, biography, and paragraph. "
            "Archaeological graffiti survive from Pompeii."
        ),
        roots=["Greek graphein (to write, scratch)", "Italian graffio (scratch)"],
        cognates=["English graph, biography, paragraph (all from graphein)", "French graffiti (borrowed)"],
        semantic_shift="'scratched inscription' → 'unauthorized public drawing or writing'",
    ),
    EtymologyEntry(
        language="it", lemma="soprano",
        origin_summary=(
            "From Italian soprano 'above, uppermost,' from sopra 'above,' from Latin supra. "
            "Applied to the highest vocal register in the 16th century. "
            "Latin supra also gives supranational, suprarenal, and the French sur-."
        ),
        roots=["Latin supra (above, over)"],
        cognates=["English supreme, supranational (from Latin supra)", "French sur- (prefix)"],
        semantic_shift="'uppermost' → 'highest singing voice'",
    ),
    EtymologyEntry(
        language="it", lemma="imbroglio",
        origin_summary=(
            "From Italian imbrogliare 'to tangle, to confuse,' from in- + broglio 'tangle, muddle.' "
            "Entered English in the 18th century to mean a complicated misunderstanding or political tangle. "
            "Broglio itself may derive from Old French brouiller 'to mix up.'"
        ),
        roots=["Italian broglio (tangle, muddle)", "Old French brouiller (to mix up)"],
        cognates=["English embroil (from same Old French root)", "French embrouiller (to tangle)"],
        semantic_shift="'physical tangle' → 'confused situation, political scandal'",
    ),
    EtymologyEntry(
        language="it", lemma="casino",
        origin_summary=(
            "Diminutive of Italian casa 'house,' from Latin casa 'cottage, hut.' "
            "Originally a small country house or social club. In 18th-century Venice, "
            "casini were private clubs for gambling. English borrowed the gambling sense in the 19th century."
        ),
        roots=["Latin casa (cottage, hut)", "Italian casa (house)"],
        cognates=["Spanish casa (house)", "French maison (different origin)", "English casino (borrowed)"],
        semantic_shift="'little house' → 'private social club' → 'gambling establishment'",
    ),
    EtymologyEntry(
        language="it", lemma="balcone",
        origin_summary=(
            "From Italian balcone 'large window, scaffold,' from Langobardic *balko 'beam.' "
            "The same Germanic root gives English balk and German Balken (beam). "
            "English balcony was borrowed from Italian in the 17th century."
        ),
        roots=["Langobardic *balko (beam)", "Germanic root *balk-"],
        cognates=["English balcony (borrowed), balk", "German Balken (beam)"],
        semantic_shift="'beam (construction)' → 'elevated platform on a building'",
    ),
    EtymologyEntry(
        language="it", lemma="bello",
        origin_summary=(
            "From Latin bellus 'beautiful, fine, handsome,' a diminutive of bonus 'good.' "
            "In Vulgar Latin it replaced the classical pulcher/pulchra. "
            "The root gives Spanish bello/bella and French belle, as well as English belle and belladonna."
        ),
        roots=["Latin bellus (beautiful)", "Latin bonus (good)"],
        cognates=["Spanish bello/bella", "French belle", "English belle, belladonna (deadly nightshade = 'beautiful lady')"],
        semantic_shift="'good (diminutive)' → 'pretty, beautiful'",
    ),
    EtymologyEntry(
        language="it", lemma="chiesa",
        origin_summary=(
            "From Latin ecclesia, borrowed from Greek ekklēsia 'assembly of citizens,' "
            "from ek (out) + kalein (to call) — those 'called out' to assemble. "
            "Gives Spanish iglesia, French église, and the English prefix ecclesi- (ecclesiastical)."
        ),
        roots=["Greek ekklēsia (assembly)", "Greek ek + kalein (to call out)"],
        cognates=["Spanish iglesia", "French église", "English ecclesiastical"],
        semantic_shift="'civic assembly (called out)' → 'Christian congregation' → 'church building'",
    ),
    EtymologyEntry(
        language="it", lemma="soldato",
        origin_summary=(
            "From Late Latin solidatus 'one paid in solidi,' from solidus, the gold coin of the Roman Empire. "
            "A soldier was literally someone paid in solid gold coins. "
            "English soldier came via Old French soldat from the same Latin root."
        ),
        roots=["Latin solidus (gold coin)", "Late Latin solidatus (paid in solidi)"],
        cognates=["English soldier (via French)", "Spanish soldado", "French soldat"],
        semantic_shift="'one paid a solidus' → 'fighting man' → 'soldier'",
    ),
    EtymologyEntry(
        language="it", lemma="mascara",
        origin_summary=(
            "From Italian maschera 'mask,' from Medieval Latin masca or Arabic maskharah 'buffoon, mockery.' "
            "Mascara was originally theatrical face paint. "
            "Italian masquerade and English mask share this root."
        ),
        roots=["Arabic maskharah (buffoon, mockery)", "Medieval Latin masca (mask)"],
        cognates=["English mask, masquerade (same root)", "Spanish máscara", "French masque"],
        semantic_shift="'buffoon, mockery' → 'face mask' → 'eye cosmetic'",
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
    EtymologyEntry(
        language="pt", lemma="amor",
        origin_summary=(
            "From Latin amor 'love,' from amare 'to love.' "
            "One of the most productive Latin roots: gives English amorous, enamour, amateur "
            "(one who does something for love), and the name Amos. "
            "The Roman god Amor is the equivalent of Greek Eros."
        ),
        roots=["Latin amor (love)", "Latin amare (to love)"],
        cognates=["Spanish amor", "French amour", "Italian amore", "English amorous, amateur"],
        semantic_shift="'love (noun)' — extremely stable across 2000 years",
    ),
    EtymologyEntry(
        language="pt", lemma="pessoa",
        origin_summary=(
            "From Latin persona 'mask worn by an actor,' then 'character,' then 'person.' "
            "Greek prosopon meant the theatrical mask; persona was the Latin translation. "
            "Gives English person, personal, personnel, persona. "
            "Fernando Pessoa, Portugal's great modernist poet, bore this common noun as a surname."
        ),
        roots=["Latin persona (actor's mask, character)", "Possibly Etruscan phersu (mask)"],
        cognates=["English person, personal, personnel, persona", "Spanish persona", "French personne"],
        semantic_shift="'actor's mask' → 'role played' → 'individual human being'",
    ),
    EtymologyEntry(
        language="pt", lemma="falar",
        origin_summary=(
            "From Latin fabulare 'to tell stories, to converse,' from fabula 'story, tale.' "
            "Classical Latin loqui/dicere were replaced in Vulgar Latin by fabulare in Iberia. "
            "The same root gives English fable, fabulous, and confabulate."
        ),
        roots=["Latin fabulare (to tell stories)", "Latin fabula (story, tale)"],
        cognates=["English fable, fabulous (same Latin root)", "Spanish hablar (same root)"],
        semantic_shift="'to tell fables/stories' → 'to speak, to talk'",
    ),
    EtymologyEntry(
        language="pt", lemma="trabalho",
        origin_summary=(
            "From Latin tripalium, a torture instrument made of three stakes (tri + palus). "
            "To 'tripaliate' originally meant to suffer or torture; it shifted to 'to labor hard.' "
            "French travail shares this origin, as does English travel — medieval journeys were an ordeal."
        ),
        roots=["Latin tripalium (three-stake torture instrument)", "Latin tri (three) + palus (stake)"],
        cognates=["French travail (work)", "English travel (same root — journeys as ordeal)", "Spanish trabajo"],
        semantic_shift="'torture instrument' → 'to suffer' → 'to work hard'",
    ),
    EtymologyEntry(
        language="pt", lemma="guerra",
        origin_summary=(
            "From Frankish *werra 'strife, confusion,' from a Germanic root related to English war. "
            "Classical Latin had bellum for war; Germanic *werra displaced it in Vulgar Latin, "
            "giving rise to Spanish guerra, Italian guerra, and French guerre."
        ),
        roots=["Frankish *werra (strife, confusion)", "Germanic *werraz (to confuse)"],
        cognates=["English war (from same Germanic root)", "Spanish guerra", "Italian guerra", "French guerre"],
        semantic_shift="'strife, confusion' → 'armed conflict'",
    ),
    EtymologyEntry(
        language="pt", lemma="coração",
        origin_summary=(
            "From Latin cor, cordis 'heart.' The diminutive coratione entered Vulgar Latin. "
            "The root cor/cord- appears in English cordial (from the heart), courage (from cœur), "
            "accord, discord, and even record (to 'take to heart')."
        ),
        roots=["Latin cor, cordis (heart)", "Latin coratione (little heart)"],
        cognates=["English cordial, courage, accord, discord, record (all from cor/cœur)", "Spanish corazón", "Italian cuore"],
    ),
    EtymologyEntry(
        language="pt", lemma="mundo",
        origin_summary=(
            "From Latin mundus 'world, universe,' possibly borrowed from Etruscan. "
            "In classical Latin, mundus also meant 'clean, elegant' (mundus as adjective). "
            "The same root gives English mundane (worldly, ordinary)."
        ),
        roots=["Latin mundus (world, universe; also: clean, elegant)"],
        cognates=["English mundane (worldly)", "Spanish mundo", "Italian mondo", "French monde"],
        semantic_shift="'clean, ordered' → 'the ordered cosmos' → 'the world'",
    ),
    EtymologyEntry(
        language="pt", lemma="escola",
        origin_summary=(
            "From Latin schola, borrowed from Greek skholē 'leisure, free time.' "
            "For ancient Greeks, philosophical discussion was the proper use of leisure. "
            "Gives English school, scholar; the semantic journey from 'leisure' to 'learning' "
            "reflects the Greek ideal of intellectual freedom."
        ),
        roots=["Greek skholē (leisure, rest)", "Latin schola (school)"],
        cognates=["English school, scholar (same Greek root)", "Spanish escuela", "Italian scuola"],
        semantic_shift="'leisure, free time' → 'philosophical discussion' → 'place of learning'",
    ),
    EtymologyEntry(
        language="pt", lemma="livro",
        origin_summary=(
            "From Latin liber 'book,' originally meaning the inner bark of a tree — "
            "the surface on which Romans wrote before papyrus became widespread. "
            "The same root gives English library, libel, and the name Liber (a Roman god)."
        ),
        roots=["Latin liber (inner bark, book)"],
        cognates=["English library (from liber)", "Spanish libro", "Italian libro", "French livre"],
        semantic_shift="'inner bark (writing surface)' → 'written document' → 'book'",
    ),
    EtymologyEntry(
        language="pt", lemma="nome",
        origin_summary=(
            "From Latin nomen 'name, noun,' from Proto-Indo-European *h₃neh₃mn. "
            "One of the most ancient words in the language: the PIE root appears in "
            "Greek onoma (name), Sanskrit nāman, English name, and German Name."
        ),
        roots=["Latin nomen (name, noun)", "Proto-Indo-European *h₃neh₃mn (name)"],
        cognates=["English name, noun, nominal (same root)", "Spanish nombre", "French nom", "Italian nome"],
    ),
    EtymologyEntry(
        language="pt", lemma="mar",
        origin_summary=(
            "From Latin mare 'sea.' Portugal's identity as a seafaring nation makes this "
            "one of its most culturally weighted words. The root gives English marine, "
            "maritime, mermaid (literally 'sea-maid'), and the name Mary/Maria."
        ),
        roots=["Latin mare (sea)"],
        cognates=["English marine, maritime, mermaid (sea + maid)", "Spanish mar", "Italian mare", "French mer"],
    ),
    EtymologyEntry(
        language="pt", lemma="tempo",
        origin_summary=(
            "From Latin tempus 'time, season,' from Proto-Indo-European *temp- 'to stretch.' "
            "Like Spanish tiempo, Portuguese tempo covers both 'time' and 'weather.' "
            "The root gives English temporal, temporary, contemporary, and the musical term tempo."
        ),
        roots=["Latin tempus (time, season)", "Proto-Indo-European *temp- (to stretch)"],
        cognates=["English temporal, temporary, tempo (all from tempus)", "Spanish tiempo", "Italian tempo"],
        semantic_shift="'stretched span' → 'time' (and in Iberian languages, also 'weather')",
    ),
    EtymologyEntry(
        language="pt", lemma="mão",
        origin_summary=(
            "From Latin manus 'hand.' One of the most productive Latin roots: gives "
            "English manual, manufacture (hand-made), mandate, manuscript (hand-written), "
            "manipulate, maintain, and manage."
        ),
        roots=["Latin manus (hand)"],
        cognates=["English manual, manufacture, manuscript, manipulate (all from manus)", "Spanish mano", "Italian mano"],
    ),
    EtymologyEntry(
        language="pt", lemma="saber",
        origin_summary=(
            "From Latin sapere 'to taste, to have good taste, to be wise.' "
            "The same root gives English sapient (wise), sage (the wise person), "
            "and savor. The semantic link is tasting → judging → knowing."
        ),
        roots=["Latin sapere (to taste, to be wise)"],
        cognates=["English sapient, sage, savor (same root)", "Spanish saber", "Italian sapere"],
        semantic_shift="'to taste' → 'to discern flavors' → 'to know, to be wise'",
    ),
    EtymologyEntry(
        language="pt", lemma="noite",
        origin_summary=(
            "From Latin noctem (accusative of nox) 'night.' "
            "One of the oldest words: the PIE root *nókʷts appears in Greek nyx, "
            "English night, German Nacht, and Sanskrit nakti."
        ),
        roots=["Latin nox/noctem (night)", "Proto-Indo-European *nókʷts (night)"],
        cognates=["English night, nocturnal (from nox)", "Spanish noche", "Italian notte", "French nuit"],
    ),
    EtymologyEntry(
        language="pt", lemma="querer",
        origin_summary=(
            "From Latin quaerere 'to seek, to inquire, to ask.' "
            "The shift from 'to seek' to 'to want' is semantic narrowing. "
            "The same Latin root gives English query, quest, question, inquest, and acquire."
        ),
        roots=["Latin quaerere (to seek, inquire)"],
        cognates=["English query, quest, question, inquest, acquire (all from quaerere)", "Spanish querer"],
        semantic_shift="'to seek, to inquire' → 'to desire, to want'",
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
    EtymologyEntry(
        language="ru", lemma="душа",
        origin_summary=(
            "From Proto-Slavic *duša 'soul, breath,' related to *duxъ 'spirit, breath.' "
            "In Russian culture, душа carries far more weight than the English 'soul' — "
            "it denotes the innermost emotional self, the seat of authentic feeling. "
            "Russian широкая душа ('wide soul') means generosity and openness."
        ),
        roots=["Proto-Slavic *duša (soul, breath)", "Proto-Slavic *duxъ (spirit, breath)"],
        cognates=["Polish dusza", "Czech duše", "Serbian duša"],
        semantic_shift="'breath' → 'animating spirit' → 'inner emotional self'",
    ),
    EtymologyEntry(
        language="ru", lemma="слово",
        origin_summary=(
            "From Proto-Slavic *slovo 'word,' related to *slava 'glory, fame' and *slušati 'to listen.' "
            "The cluster *slav- is at the root of Slav and Slavic: the Slavs were 'those who speak [our language].' "
            "The related slava appears in names like Yaroslav, Vladislav, and Stanislav."
        ),
        roots=["Proto-Slavic *slovo (word)", "Proto-Slavic *slava (glory, fame)"],
        cognates=["Polish słowo", "Czech slovo", "Slavic names ending in -slav (glory in words)"],
    ),
    EtymologyEntry(
        language="ru", lemma="мир",
        origin_summary=(
            "A uniquely ambiguous word: before the 1918 spelling reform, мiръ meant 'world/commune' "
            "and миръ meant 'peace.' The reform merged both spellings into мир. "
            "Tolstoy's War and Peace (Война и мiръ) originally meant 'War and Society' — "
            "modern readers often read 'war and peace.' The ambiguity is irreducible."
        ),
        roots=["Proto-Slavic *mirъ (commune, agreement, peace)"],
        cognates=["Polish mir (peace)", "Czech mír (peace)", "Serbian мир"],
        semantic_shift="'commune, community agreement' → both 'peace' and 'the world/society'",
    ),
    EtymologyEntry(
        language="ru", lemma="хлеб",
        origin_summary=(
            "Borrowed from Proto-Germanic *hlaibaz 'loaf of bread' — the same root as "
            "English loaf and German Laib (loaf). The borrowing happened in early medieval contact "
            "between Slavic and Germanic peoples. In Russian culture, bread (хлеб) represents "
            "life itself; хлеб-соль (bread-and-salt) is the traditional welcoming gift."
        ),
        roots=["Proto-Germanic *hlaibaz (loaf of bread)"],
        cognates=["English loaf (same Germanic root)", "German Laib (loaf)", "Polish chleb", "Ukrainian хліб"],
        semantic_shift="Germanic 'loaf' → Slavic 'bread (general)'",
    ),
    EtymologyEntry(
        language="ru", lemma="самовар",
        origin_summary=(
            "Compound of Russian само (self) + варить (to boil): literally 'self-boiler.' "
            "The samovar heated water by an internal charcoal tube and kept tea hot for hours. "
            "It became a symbol of Russian domestic life and hospitality. "
            "The first Russian samovar workshops appeared in Tula in the 18th century."
        ),
        roots=["Russian само (self) + варить (to boil/cook)", "Cognate with English warm"],
        cognates=["English warm (from the same PIE root as варить)", "German wärmen"],
        semantic_shift="'self-boiling vessel' → symbol of Russian domestic hospitality",
    ),
    EtymologyEntry(
        language="ru", lemma="воля",
        origin_summary=(
            "From Proto-Slavic *volja 'will, freedom,' from *velěti 'to command, to wish.' "
            "Воля in Russian encompasses both 'will' (strength of determination) and 'freedom' "
            "(liberty) — a duality that reflects the historical tension between individual autonomy "
            "and collective authority in Russian culture."
        ),
        roots=["Proto-Slavic *volja (will, freedom)", "Proto-Slavic *velěti (to command, to wish)"],
        cognates=["Polish wola (will)", "Czech vůle (will)", "English well (as in 'to will')"],
        semantic_shift="'wish, command' → 'will (determination)' and 'freedom (liberation)'",
    ),
    EtymologyEntry(
        language="ru", lemma="судьба",
        origin_summary=(
            "From суд 'judgment, court,' from Proto-Slavic *sǫdъ 'judgment.' "
            "Судьба literally means 'that which has been judged (fated).' "
            "The root *sǫd- appears in суд (court), судья (judge), and осудить (to condemn)."
        ),
        roots=["Proto-Slavic *sǫdъ (judgment)", "Russian суд (court, judgment)"],
        cognates=["Polish sąd (court)", "Czech soud (court)", "Serbian суд"],
        semantic_shift="'judgment (legal verdict)' → 'fate, destiny'",
    ),
    EtymologyEntry(
        language="ru", lemma="путь",
        origin_summary=(
            "From Proto-Slavic *pǫtь 'path, way,' related to *pati 'to go.' "
            "In Russian, путь has both literal (road, route) and philosophical (life's path, "
            "spiritual journey) meanings. The Soviet-era Sputnik ('fellow traveler') contains "
            "the same root: s- (with) + put' (path)."
        ),
        roots=["Proto-Slavic *pǫtь (path, way)"],
        cognates=["Sputnik (s + put' = fellow traveler)", "Polish podróż (journey)", "Serbian пут"],
        semantic_shift="'physical path/road' → 'life journey, spiritual way'",
    ),
    EtymologyEntry(
        language="ru", lemma="земля",
        origin_summary=(
            "From Proto-Slavic *zemlja 'earth, ground, land,' from Proto-Indo-European *dʰéǵʰōm. "
            "The same ancient root gives Latin humus (soil), homo (human — 'earthling'), "
            "Greek khthōn (earth), English humble and human."
        ),
        roots=["Proto-Slavic *zemlja (earth, land)", "Proto-Indo-European *dʰéǵʰōm (earth)"],
        cognates=["Latin humus (soil), homo (human)", "English humble, human (same PIE root)", "Polish ziemia", "Czech země"],
    ),
    EtymologyEntry(
        language="ru", lemma="небо",
        origin_summary=(
            "From Proto-Slavic *nebo 'sky, heaven,' from Proto-Indo-European *nebʰos 'cloud, mist.' "
            "The same root gives Greek nephos (cloud), Latin nebula (mist, fog), "
            "and German Nebel (fog). In Russian, небо covers both the physical sky and heaven."
        ),
        roots=["Proto-Slavic *nebo (sky)", "Proto-Indo-European *nebʰos (cloud, mist)"],
        cognates=["Latin nebula (cloud, mist)", "Greek nephos (cloud)", "English nebula (borrowed from Latin)"],
        semantic_shift="'cloud, mist (sky)' → 'sky' and 'heaven'",
    ),
    EtymologyEntry(
        language="ru", lemma="дружба",
        origin_summary=(
            "From друг 'friend' + suffix -ба (forming abstract nouns), from Proto-Slavic *drugъ "
            "'companion, other person.' The Slavic root *drug- originally meant 'another' — "
            "a friend is quite literally 'another (person like oneself).' "
            "Related to Russian другой (another, different)."
        ),
        roots=["Proto-Slavic *drugъ (companion, another person)"],
        cognates=["Polish druh (friend, companion)", "Czech druh (companion)", "Russian другой (another, different)"],
        semantic_shift="'another (person)' → 'companion, friend' → abstract 'friendship'",
    ),
    EtymologyEntry(
        language="ru", lemma="ночь",
        origin_summary=(
            "From Proto-Slavic *noktь 'night,' from Proto-Indo-European *nókʷts. "
            "One of the oldest words in the language: appears virtually unchanged across "
            "all Indo-European branches: Greek nyx, Latin nox, English night, German Nacht."
        ),
        roots=["Proto-Slavic *noktь (night)", "Proto-Indo-European *nókʷts (night)"],
        cognates=["English night (same PIE root)", "Latin nox/nocturnal", "German Nacht", "Greek nyx"],
    ),
    EtymologyEntry(
        language="ru", lemma="степь",
        origin_summary=(
            "Of uncertain origin; often attributed to Turkic or early Iranian contact. "
            "The степь (steppe) is the vast Eurasian grassland that shaped Russian history — "
            "the route of nomadic invasions, the frontier of expansion, and the landscape "
            "of Cossack culture. English steppe was borrowed from Russian."
        ),
        roots=["Possibly Turkic or Iranian; exact origin disputed"],
        cognates=["English steppe (borrowed from Russian)", "German Steppe (borrowed)", "French steppe (borrowed)"],
    ),
    EtymologyEntry(
        language="ru", lemma="сила",
        origin_summary=(
            "From Proto-Slavic *sila 'strength, power,' from Proto-Indo-European *sel- 'to take.' "
            "In Russian, сила permeates proverbs and culture: 'не в силе Бог, а в правде' "
            "('God is not in power but in truth' — Alexander Nevsky). "
            "The same root appears in насилие (violence) and усилие (effort)."
        ),
        roots=["Proto-Slavic *sila (strength, force)"],
        cognates=["Polish siła (strength)", "Czech síla", "Serbian сила"],
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

    # ── Italian (new entries) ─────────────────────────────────────────────────
    EtymologyEntry(
        language="it", lemma="allegro",
        origin_summary=(
            "From Latin alacer/alacris (lively, cheerful, eager). Entered music as a tempo "
            "marking meaning 'fast and lively.' Italian musical terminology spread across "
            "Europe in the 17th–18th centuries, making allegro a universal term."
        ),
        roots=["Latin alacer (lively, eager)"],
        cognates=["English alacrity (same Latin root)"],
        semantic_shift="'lively, eager' → musical tempo marking for fast, bright passages",
    ),
    EtymologyEntry(
        language="it", lemma="amore",
        origin_summary=(
            "From Latin amor (love, affection), itself from amare (to love). "
            "A core Romance word shared across all the family. "
            "Italian amore entered English in opera, poetry, and music as a loanword."
        ),
        roots=["Latin amor (love)", "Latin amare (to love)"],
        cognates=["Spanish amor", "French amour", "Portuguese amor", "English amorous"],
    ),
    EtymologyEntry(
        language="it", lemma="bambino",
        origin_summary=(
            "Diminutive of bambo (stupid, simple — applied to small children). "
            "Bambo itself may derive from baby-talk reduplication. "
            "In English art history, bambino refers specifically to a depiction of the infant Jesus."
        ),
        roots=["Italian bambo (simple, baby-like)"],
        cognates=["English babe, baby (parallel baby-talk forms)"],
        semantic_shift="'simple/baby-like one' → infant → child generally",
    ),
    EtymologyEntry(
        language="it", lemma="cappuccino",
        origin_summary=(
            "Named for the Capuchin friars (Cappuccini), whose brown habits match "
            "the espresso-and-milk color of the drink. "
            "The friars took their name from cappuccio (hood), from cappa (cloak). "
            "The drink emerged in early 20th-century Vienna and Italy."
        ),
        roots=["Latin cappa (cloak, hood)", "Late Latin Caputium (hood)"],
        cognates=["English cape (garment)", "French capuche (hood)"],
        semantic_shift="'hooded friar' → the friar's brown color → coffee drink of that color",
    ),
    EtymologyEntry(
        language="it", lemma="concerto",
        origin_summary=(
            "From concertare (to contest, to debate, to agree), from Latin concertare "
            "(to contend). The musical form pits a soloist or small group against "
            "a full orchestra — a structured contest. "
            "Emerged as a genre in the late 17th century."
        ),
        roots=["Latin concertare (to contend, strive together)"],
        cognates=["English concert (agreeing together)", "French concert"],
        semantic_shift="'contest, debate' → soloist vs. ensemble musical form",
    ),
    EtymologyEntry(
        language="it", lemma="confetti",
        origin_summary=(
            "Plural of confetto, from Latin confectum (prepared, made up) — the same root "
            "as English confection. Originally sugar-coated almonds or sweets thrown at "
            "celebrations. Paper discs replaced real sweets in the 19th century, "
            "keeping the name."
        ),
        roots=["Latin conficere (to prepare, make up)", "Latin con- + facere (to make)"],
        cognates=["English confection", "French confiture (jam)"],
        semantic_shift="'prepared sweets' → sweets thrown at weddings → paper discs thrown at parties",
    ),
    EtymologyEntry(
        language="it", lemma="dilettante",
        origin_summary=(
            "From dilettare (to delight, to take pleasure in), from Latin delectare. "
            "Originally a positive term: a lover of the arts who pursues them for pleasure. "
            "By the 19th century it acquired the negative sense of 'amateur who lacks depth.'"
        ),
        roots=["Latin delectare (to delight)"],
        cognates=["English delight (same Latin root)", "French délectation"],
        semantic_shift="'one who takes delight in the arts' → superficial amateur",
    ),
    EtymologyEntry(
        language="it", lemma="espresso",
        origin_summary=(
            "Past participle of esprimere (to press out, to express), from Latin exprimere. "
            "The coffee is 'pressed out' by forcing hot water through compacted grounds "
            "under pressure. Also carries the sense of 'made expressly for you' — "
            "made to order."
        ),
        roots=["Latin exprimere (to press out, express)"],
        cognates=["English express, expression (same Latin root)"],
        semantic_shift="'pressed out' → coffee made by pressure extraction",
    ),
    EtymologyEntry(
        language="it", lemma="ghetto",
        origin_summary=(
            "Origin disputed. Most likely from Venetian gheto (foundry, casting), "
            "as the first Jewish ghetto in Venice (1516) was established near a copper "
            "foundry on an island. Possibly also from borghetto (small borough). "
            "The word spread to mean any segregated urban area."
        ),
        roots=["Venetian geto (foundry/casting)"],
        cognates=["English ghetto (borrowed)"],
        semantic_shift="'foundry island' → enclosed Jewish quarter → any marginalized urban area",
    ),
    EtymologyEntry(
        language="it", lemma="gondola",
        origin_summary=(
            "Etymology uncertain — possibly from Medieval Greek kontaros (pole) "
            "or Byzantine Greek kondoura (short boat). "
            "The flat-bottomed Venetian boat has been documented since the 11th century. "
            "English borrowed both the boat and the cable-car/airship-basket sense."
        ),
        roots=["Possibly Byzantine Greek kondoura (small boat)"],
        cognates=["English gondola (borrowed in multiple senses)"],
    ),
    EtymologyEntry(
        language="it", lemma="gusto",
        origin_summary=(
            "From Latin gustus (taste, the act of tasting), from gustare (to taste). "
            "In Italian it means both physical taste and enthusiastic enjoyment. "
            "English borrowed it in the sense of 'zest, keen relish' in the 17th century."
        ),
        roots=["Latin gustus (taste)", "Latin gustare (to taste)"],
        cognates=["English gusto (borrowed)", "English disgust (opposite: bad taste)", "French goût"],
        semantic_shift="'physical taste' → enthusiasm, relish, energetic enjoyment",
    ),
    EtymologyEntry(
        language="it", lemma="latte",
        origin_summary=(
            "Simply the Italian word for milk, from Latin lac/lactis (milk). "
            "In Italian cafés, ordering a latte means a glass of milk — "
            "the full term is caffè latte. The word is ancient, cognate with "
            "Greek gala/galaktos, giving English galaxy (Milky Way)."
        ),
        roots=["Latin lac/lactis (milk)"],
        cognates=["English lactose, lactate", "Greek gala (milk)", "French lait"],
        semantic_shift="'milk' → in English café usage: espresso-and-milk drink",
    ),
    EtymologyEntry(
        language="it", lemma="mafia",
        origin_summary=(
            "Origin contested. Likely from Sicilian dialect mafioso (bold, swaggering, "
            "self-assured). Possible connection to Arabic mahyaz (bragging) "
            "or Old French meffait (misdeed). The word entered Italian and world "
            "vocabulary through 19th-century Sicily."
        ),
        roots=["Sicilian mafiusu (swagger, bravado)"],
        cognates=["English mafia, mafioso (borrowed)"],
        semantic_shift="'swagger, bold self-assertion' → criminal brotherhood → any organized crime network",
    ),
    EtymologyEntry(
        language="it", lemma="manifesto",
        origin_summary=(
            "From Latin manifestus (evident, caught in the act, plain to see). "
            "In Italian and then English, a public declaration of principles or intentions — "
            "something made plainly visible to all. "
            "Marx and Engels' Manifest der Kommunistischen Partei (1848) popularized the genre."
        ),
        roots=["Latin manifestus (plain, evident)", "Latin manus (hand) + festus (struck)"],
        cognates=["English manifest (adjective/verb)", "Spanish manifiesto"],
        semantic_shift="'plain, evident' → public declaration that makes intentions evident",
    ),
    EtymologyEntry(
        language="it", lemma="motto",
        origin_summary=(
            "From Latin muttum (grunt, murmur, a brief sound), from muttire (to mutter). "
            "A motto is a short phrase — a 'word' or brief utterance — "
            "that encapsulates a group's or person's guiding principle. "
            "Heraldry adopted it for the phrase on a coat of arms."
        ),
        roots=["Latin muttum (grunt, word)", "Latin muttire (to mutter)"],
        cognates=["English mot (witty saying, from French)", "French mot (word)"],
        semantic_shift="'brief sound/grunt' → short saying → guiding slogan",
    ),
    EtymologyEntry(
        language="it", lemma="omertà",
        origin_summary=(
            "Sicilian dialect form of umiltà (humility), from Latin humilitas. "
            "The code of silence observed by criminal organizations requires "
            "'humility' before the group — not speaking to outsiders or authorities. "
            "The word encodes submission to the criminal hierarchy as a virtue."
        ),
        roots=["Latin humilitas (humility, lowness)", "Latin humilis (low, humble)"],
        cognates=["English humble, humility (same Latin root)"],
        semantic_shift="'humility before the group' → code of silence and non-cooperation with authorities",
    ),
    EtymologyEntry(
        language="it", lemma="opera",
        origin_summary=(
            "Latin opera (works, labor, plural of opus). An opera is a 'work' — "
            "a composite work of music, drama, and spectacle. "
            "The full original term was opera in musica (a work in music). "
            "The genre emerged in Florence c. 1600 from the Florentine Camerata."
        ),
        roots=["Latin opus/opera (work, labor)"],
        cognates=["English opus, operation, cooperate (same root)", "French œuvre"],
        semantic_shift="'works, labor' → dramatic musical work → the genre itself",
    ),
    EtymologyEntry(
        language="it", lemma="orchestra",
        origin_summary=(
            "From Greek orkhestra (the semicircular dancing space in front of the stage "
            "in a Greek theatre), from orkheisthai (to dance). "
            "The area was later used for musicians, then the musicians themselves. "
            "In Italian baroque theatre, the pit became the orchestra's home."
        ),
        roots=["Greek orkheisthai (to dance)"],
        cognates=["English orchestrate (to arrange, like an orchestra)", "French orchestre"],
        semantic_shift="'dancing place' → musician pit → ensemble of musicians",
    ),
    EtymologyEntry(
        language="it", lemma="palazzo",
        origin_summary=(
            "From Latin palatium (the Palatine Hill in Rome), where Augustus built "
            "his imperial residence. The hill's name gave its name to the building, "
            "which gave its name to grand buildings generally. "
            "English palace and French palais follow the same path."
        ),
        roots=["Latin Palatium (Palatine Hill)", "Latin Palatinus (of the Palatine)"],
        cognates=["English palace", "French palais", "Spanish palacio"],
        semantic_shift="'Palatine Hill' → emperor's residence there → any grand building",
    ),
    EtymologyEntry(
        language="it", lemma="pasta",
        origin_summary=(
            "From Latin pasta (dough, paste), from Greek paste (barley porridge), "
            "from passein (to sprinkle). The word names both the dough and the "
            "shaped, dried product. Italian regional varieties — from spaghetti "
            "to penne — are all grammatically pasta."
        ),
        roots=["Greek paste (barley porridge)", "Greek passein (to sprinkle, mix)"],
        cognates=["English paste, pastry, pastel (same root)", "French pâte"],
        semantic_shift="'barley porridge' → dough → shaped wheat-flour food product",
    ),
    EtymologyEntry(
        language="it", lemma="piazza",
        origin_summary=(
            "From Latin platea (broad street, open space), from Greek plateia "
            "(broad way), from platos (broad, flat). "
            "The Italian piazza, French place, Spanish plaza, and English place "
            "all descend from the same Latin root."
        ),
        roots=["Latin platea (broad street)", "Greek plateia hodos (broad road)"],
        cognates=["English place, plaza", "French place", "Spanish plaza"],
        semantic_shift="'broad road' → open public square in a town",
    ),
    EtymologyEntry(
        language="it", lemma="spaghetti",
        origin_summary=(
            "Diminutive plural of spago (string, cord, twine). "
            "The pasta strands were likened to thin strings. "
            "The word is first recorded in the early 19th century. "
            "In English, spaghetti became a catch-all for long thin pasta."
        ),
        roots=["Italian spago (string, cord, twine)"],
        cognates=["English spaghetti (borrowed)"],
        semantic_shift="'little strings' → thin rod pasta → Italian-American cuisine staple",
    ),
    EtymologyEntry(
        language="it", lemma="arpeggio",
        origin_summary=(
            "From arpeggiare (to play the harp), from arpa (harp), "
            "from Proto-Germanic *harpō. "
            "An arpeggio plays chord notes in succession upward or downward, "
            "mimicking how a harpist sweeps strings. "
            "The term was adopted into all European musical languages."
        ),
        roots=["Italian arpa (harp)", "Proto-Germanic *harpō"],
        cognates=["English harp (same Germanic root)", "French harpe"],
        semantic_shift="'harp-playing' → broken chord played note-by-note",
    ),
    EtymologyEntry(
        language="it", lemma="ballerina",
        origin_summary=(
            "Feminine agent noun from ballare (to dance), from Late Latin ballare, "
            "possibly from Greek ballizein (to dance, jump about). "
            "The feminine form ballerina (male: ballerino) refers specifically "
            "to a trained classical ballet dancer."
        ),
        roots=["Late Latin ballare (to dance)", "Greek ballizein (to dance)"],
        cognates=["English ball (formal dance event)", "French bal (dance)", "English ballet"],
        semantic_shift="'female dancer' → specifically a classical ballet dancer",
    ),
    EtymologyEntry(
        language="it", lemma="finale",
        origin_summary=(
            "From Latin finalis (of the end, final), from finis (end, boundary). "
            "In music, the finale is the concluding movement or section. "
            "Borrowed into English in both musical and general senses "
            "('the grand finale')."
        ),
        roots=["Latin finis (end, boundary)", "Latin finalis (final)"],
        cognates=["English final, finish, finance (same root)", "French final"],
        semantic_shift="'of the end' → concluding musical section → any dramatic conclusion",
    ),
    EtymologyEntry(
        language="it", lemma="pronto",
        origin_summary=(
            "From Latin promptus (brought forward, ready, at hand), past participle "
            "of promere (to bring forth). In Italian it means 'ready' and is used "
            "as a telephone greeting ('ready/hello'). "
            "English borrowed it colloquially as 'quickly, right away.'"
        ),
        roots=["Latin promptus (ready, at hand)", "Latin promere (to bring forth)"],
        cognates=["English prompt (same Latin root)", "Spanish pronto (soon)"],
        semantic_shift="'ready, at hand' → Italian phone greeting → English 'immediately'",
    ),
    EtymologyEntry(
        language="it", lemma="terra",
        origin_summary=(
            "From Latin terra (earth, land, soil, ground). "
            "Cognate with a vast family: terrarium, territory, terrace, Mediterranean "
            "(middle of the earth). In Italian it means both earth/soil and "
            "land/country. Terra firma (firm land) entered English directly."
        ),
        roots=["Latin terra (earth, land)", "Proto-Indo-European *ters- (to dry)"],
        cognates=["English territory, terrace, terrain, Mediterranean", "French terre", "Spanish tierra"],
        semantic_shift="'dry ground' → earth, soil, land, territory",
    ),
    EtymologyEntry(
        language="it", lemma="firma",
        origin_summary=(
            "From Latin firmus (firm, steady, strong). A firma (signature/company) "
            "was originally a 'firm sign' — a legally binding mark. "
            "This sense of firmness as legal certainty underlies 'signature' and "
            "the business sense of 'firm' (company)."
        ),
        roots=["Latin firmus (firm, steady, strong)"],
        cognates=["English firm (business)", "English affirm, confirm (same root)", "Spanish firma"],
        semantic_shift="'firm, steady' → binding signature → company name → business firm",
    ),
    EtymologyEntry(
        language="it", lemma="serenata",
        origin_summary=(
            "From Latin serenus (calm, clear sky, serene). "
            "A serenata is music performed in the open air on a calm evening — "
            "the serene sky provides the setting. "
            "Spanish serenata and English serenade follow the same derivation."
        ),
        roots=["Latin serenus (calm, clear, serene)"],
        cognates=["English serene, serenade", "Spanish serenata", "French sérénade"],
        semantic_shift="'calm clear evening sky' → evening open-air performance",
    ),
    EtymologyEntry(
        language="it", lemma="portico",
        origin_summary=(
            "From Latin porticus (porch, colonnade, covered walkway), from porta "
            "(gate, door, city gate). A portico is a roofed colonnade "
            "at a building's entrance — the monumental 'gateway' structure. "
            "The Stoics took their name from the Stoa (Greek equivalent)."
        ),
        roots=["Latin porta (gate, door)", "Latin porticus (colonnade)"],
        cognates=["English porch (same root)", "English port, portal (same root)", "Spanish pórtico"],
        semantic_shift="'gateway structure' → covered colonnade at a building entrance",
    ),
    EtymologyEntry(
        language="it", lemma="tempo",
        origin_summary=(
            "From Latin tempus (time, period, season). In Italian it means both "
            "'time' and 'weather' (like French temps). As a musical term "
            "it means the speed of a piece. "
            "The Latin root gives English temporal, temporary, tense (grammatical), and contemporary."
        ),
        roots=["Latin tempus (time, period, season)"],
        cognates=["English temporal, contemporary, tense", "French temps", "Spanish tiempo"],
        semantic_shift="'time' → musical speed → rate of rhythmic pulse",
    ),

    # ── Portuguese (new entries) ──────────────────────────────────────────────
    EtymologyEntry(
        language="pt", lemma="água",
        origin_summary=(
            "From Latin aqua (water). One of the most fundamental words in the language, "
            "inherited from Latin with minimal change. The Latin aqua gives English aquarium, "
            "aqueduct, and aquatic. Portuguese preserves the initial 'a-' that other "
            "Romance languages often dropped."
        ),
        roots=["Latin aqua (water)", "Proto-Indo-European *akʷā- (water)"],
        cognates=["Spanish agua", "Italian acqua", "English aquatic, aqueduct"],
    ),
    EtymologyEntry(
        language="pt", lemma="aldeia",
        origin_summary=(
            "From Arabic al-day'a (the estate, the village). Borrowed during the "
            "period of Islamic rule in the Iberian Peninsula (711–1492). "
            "One of hundreds of Arabic loanwords in Portuguese relating to settlement, "
            "agriculture, and daily life."
        ),
        roots=["Arabic al-day'a (the estate/village)"],
        cognates=["Spanish aldea (village, same Arabic source)"],
        semantic_shift="'the estate' → rural village, small settlement",
    ),
    EtymologyEntry(
        language="pt", lemma="azulejo",
        origin_summary=(
            "From Arabic az-zulayj (the polished stone, the glazed tile). "
            "The decorative glazed ceramic tile became central to Portuguese and "
            "Spanish architecture. The blue-and-white variety that defines Portuguese "
            "aesthetic came via Dutch and Chinese influences in the 17th century."
        ),
        roots=["Arabic az-zulayj (polished stone, glazed tile)"],
        cognates=["Spanish azulejo (glazed tile, same source)"],
        semantic_shift="'polished stone' → decorative glazed ceramic tile",
    ),
    EtymologyEntry(
        language="pt", lemma="banana",
        origin_summary=(
            "From West African languages — likely Wolof or Mandinka banaana. "
            "Portuguese traders encountered the fruit in West Africa and "
            "introduced both the plant and the word to Europe and the Americas "
            "in the 16th century. Now universal across most of the world's languages."
        ),
        roots=["Wolof or Mandinka banaana"],
        cognates=["English banana", "Spanish banana/plátano", "French banane"],
        semantic_shift="West African word for the fruit → adopted universally through Portuguese trade routes",
    ),
    EtymologyEntry(
        language="pt", lemma="branco",
        origin_summary=(
            "From Germanic blank (shining, white, bare). Introduced by Germanic tribes "
            "during the Migration Period. Replaced Latin albus (white) in Portuguese "
            "and Spanish, while French kept blanc from the same Germanic source. "
            "The connection to 'blank' (empty white space) is direct."
        ),
        roots=["Proto-Germanic *blankaz (shining, white)"],
        cognates=["English blank (same Germanic root)", "French blanc", "Spanish blanco"],
        semantic_shift="'shining, gleaming' → white color",
    ),
    EtymologyEntry(
        language="pt", lemma="café",
        origin_summary=(
            "From Arabic qahwa (a type of wine, then coffee), via Turkish kahve. "
            "The drink spread from Yemen through the Ottoman Empire to Europe. "
            "Portuguese traders in the Indian Ocean trade routes helped diffuse it. "
            "Café now means both the drink and the establishment serving it."
        ),
        roots=["Arabic qahwa (coffee, a wine-like beverage)", "Turkish kahve"],
        cognates=["English coffee (via Italian caffè)", "French café", "Spanish café"],
        semantic_shift="'wine-like drink' → coffee bean beverage → the establishment serving it",
    ),
    EtymologyEntry(
        language="pt", lemma="caju",
        origin_summary=(
            "From Tupi acajú or acaíuba (the cashew tree). "
            "The cashew tree is native to northeastern Brazil. "
            "Portuguese colonizers adopted the Tupi name. "
            "English cashew comes from a variant of the same Tupi word via French."
        ),
        roots=["Tupi acajú (cashew tree)"],
        cognates=["English cashew (same Tupi source via French acajou)"],
        semantic_shift="Tupi name for the cashew tree → the nut and juice of the fruit",
    ),
    EtymologyEntry(
        language="pt", lemma="capoeira",
        origin_summary=(
            "Origin disputed. Likely from Tupi caá-puéra (former forest, cleared "
            "land where capões/capons were kept) or Old Portuguese capoeira "
            "(a chicken coop). The Afro-Brazilian martial art developed among "
            "enslaved Africans in Brazil who disguised combat as dance."
        ),
        roots=["Tupi caá-puéra (former forest/cleared land)"],
        cognates=["English capoeira (borrowed)"],
        semantic_shift="'cleared forest/chicken yard' → Afro-Brazilian martial art disguised as dance",
    ),
    EtymologyEntry(
        language="pt", lemma="chá",
        origin_summary=(
            "From Cantonese chah (tea). Portuguese traders at Macau adopted the "
            "Cantonese pronunciation, giving Portuguese chá and English 'char' (British slang). "
            "English tea comes from Hokkien tê, adopted via Dutch traders in Taiwan. "
            "Two different Chinese pronunciations split into two English words."
        ),
        roots=["Cantonese chah (tea)"],
        cognates=["English char (British slang for tea)", "English tea (via Hokkien/Dutch route)"],
        semantic_shift="Cantonese word for tea → Portuguese and then general use",
    ),
    EtymologyEntry(
        language="pt", lemma="cobra",
        origin_summary=(
            "From Latin colubra (female snake). Portuguese cobra de capelo "
            "(hooded snake) was shortened in English to cobra. "
            "The Latin colubra gives English coulomb indirectly, and is cognate "
            "with Greek kolubros (a kind of snake)."
        ),
        roots=["Latin colubra (female serpent)"],
        cognates=["English cobra (borrowed from Portuguese)", "English coluber (zoological genus)"],
        semantic_shift="'female snake' → specifically the hooded venomous snake of Asia and Africa",
    ),
    EtymologyEntry(
        language="pt", lemma="dinheiro",
        origin_summary=(
            "From Latin denarius (a silver coin worth ten asses), from deni "
            "(ten each). The denarius was the standard Roman silver coin; "
            "its name survives in Italian denaro, Spanish dinero, and Portuguese "
            "dinheiro — and in the 'd' abbreviation for pre-decimal British pence."
        ),
        roots=["Latin denarius (silver coin)", "Latin deni (ten each)"],
        cognates=["Spanish dinero", "Italian denaro", "English penny (d for denarius)", "French denier"],
        semantic_shift="'ten-unit Roman coin' → money generally",
    ),
    EtymologyEntry(
        language="pt", lemma="estar",
        origin_summary=(
            "From Latin stare (to stand, to be stationary). Portuguese (and Spanish) "
            "split the Latin esse (to be) into two verbs: ser for permanent states "
            "and estar for temporary or locational states. "
            "This ser/estar distinction is one of the most studied features of Iberian languages."
        ),
        roots=["Latin stare (to stand, to remain)"],
        cognates=["Spanish estar (same distinction)", "English state, station, status (same root)"],
        semantic_shift="'to stand/remain' → to be temporarily, to be located somewhere",
    ),
    EtymologyEntry(
        language="pt", lemma="irmão",
        origin_summary=(
            "From Latin germanus (full-blooded brother, from the same parents), "
            "from germen (seed, offspring). The Latin germanus (genuine, full brother) "
            "replaced frater in Iberian Portuguese and Spanish. "
            "German (the nationality) shares the Latin root, though the connection is indirect."
        ),
        roots=["Latin germanus (full-blooded, genuine sibling)", "Latin germen (seed)"],
        cognates=["Spanish hermano (same derivation)", "English germane (relevant, genuine)"],
        semantic_shift="'full-blooded (sibling)' → brother",
    ),
    EtymologyEntry(
        language="pt", lemma="lua",
        origin_summary=(
            "From Latin luna (moon), from an older root related to lux (light). "
            "The moon as 'the light-giver of night.' "
            "Luna gives English lunar, lunatic (thought to be moon-caused madness), "
            "and lune. Portuguese lua is also a surname and poetic name."
        ),
        roots=["Latin luna (moon)", "Proto-Indo-European *lewk- (light)"],
        cognates=["English lunar, lunatic", "Spanish luna", "French lune", "Italian luna"],
        semantic_shift="'night light-giver' → the moon → romantic/poetic symbol",
    ),
    EtymologyEntry(
        language="pt", lemma="namorado",
        origin_summary=(
            "Past participle of namorar (to woo, to court), from namorar-se (to fall "
            "in love), derived from amor (love) via the verb form. "
            "A namorado is literally 'one who has been loved/courted' — "
            "a boyfriend. The word captures love as a completed action."
        ),
        roots=["Latin amor (love)", "Portuguese namorar (to court, woo)"],
        cognates=["Spanish enamorado (in love, same root)", "Italian innamorato"],
        semantic_shift="'one who has been wooed/loved' → boyfriend/girlfriend",
    ),
    EtymologyEntry(
        language="pt", lemma="obrigado",
        origin_summary=(
            "Past participle of obrigar (to oblige, to bind), from Latin obligare "
            "(to bind, to oblige), from ob- + ligare (to tie). "
            "Saying obrigado literally means '(I am) obliged (to you).' "
            "The same Latin root gives English obligate, oblige, and religion."
        ),
        roots=["Latin obligare (to bind, obligate)", "Latin ligare (to tie, bind)"],
        cognates=["English obliged, oblige", "Spanish obligado (obliged)", "English religion (to re-bind)"],
        semantic_shift="'(I am) bound/obliged' → thank you",
    ),
    EtymologyEntry(
        language="pt", lemma="peixe",
        origin_summary=(
            "From Latin piscis (fish). The Latin root gives English Pisces (zodiac sign), "
            "piscine (relating to fish), and piscatorial. "
            "Portuguese peixe and Spanish pez/pescado both come from Latin piscis, "
            "with different forms for the living fish and the caught/eaten fish."
        ),
        roots=["Latin piscis (fish)", "Proto-Indo-European *pisk- (fish)"],
        cognates=["English Pisces, piscine", "Spanish pez/pescado", "French poisson"],
        semantic_shift="'fish (as animal)' → also used for fish as food",
    ),
    EtymologyEntry(
        language="pt", lemma="português",
        origin_summary=(
            "From Portucale, the medieval kingdom name, itself from Portus Cale "
            "(the port at Cale). Cale was likely a pre-Roman Galician settlement "
            "near modern Porto. The country Portugal, the language português, "
            "and the port city Porto all share this ancient toponym."
        ),
        roots=["Latin portus (harbor, port)", "Celtic Cale (pre-Roman settlement name)"],
        cognates=["English Portugal, Portuguese (same toponym)", "Spanish portugués"],
        semantic_shift="'port at Cale' → kingdom name → people and language of that kingdom",
    ),
    EtymologyEntry(
        language="pt", lemma="praia",
        origin_summary=(
            "From Latin plagia (region, shore, side), from Greek plagios "
            "(oblique, sideways). The beach as the slanted meeting place of land "
            "and sea. Portuguese praia gave English the surname Praia (Cape Verde's "
            "capital) and influenced several Atlantic Creoles."
        ),
        roots=["Latin plagia (shore, region)", "Greek plagios (oblique, sideways)"],
        cognates=["Spanish playa (beach, same root)", "English plagiarism (oblique theft — different path)"],
        semantic_shift="'slanted shore' → beach, coastline",
    ),
    EtymologyEntry(
        language="pt", lemma="sino",
        origin_summary=(
            "From Latin signum (sign, signal, military standard). A church bell "
            "is a 'signal' — it marks time, calls to worship, and announces events. "
            "The Latin signum gives English sign, signal, and insignia. "
            "The Portuguese shift from signum to sino involved vowel reduction."
        ),
        roots=["Latin signum (sign, signal, standard)"],
        cognates=["English sign, signal, insignia", "Spanish signo (sign, but campanario for bell tower)"],
        semantic_shift="'signal, sign' → bell (the instrument that signals)",
    ),
    EtymologyEntry(
        language="pt", lemma="sol",
        origin_summary=(
            "From Latin sol (sun), from Proto-Indo-European *sóh₂wl̥. "
            "The Latin sol gives English solar, solstice, and parasol. "
            "In music, sol (or so) is the fifth note of the scale in solfège, "
            "named from the first syllable of 'Solve polluti' in a medieval hymn."
        ),
        roots=["Latin sol (sun)", "Proto-Indo-European *sóh₂wl̥"],
        cognates=["English solar, solstice, parasol", "Spanish sol", "French soleil"],
    ),
    EtymologyEntry(
        language="pt", lemma="também",
        origin_summary=(
            "From Latin tam bene (so well, likewise). The contraction tam+bene → "
            "Portuguese também (also, too). The same contraction produced Spanish "
            "también. It is the Iberian way of saying 'equally well' → 'also.'"
        ),
        roots=["Latin tam (so, so much)", "Latin bene (well)"],
        cognates=["Spanish también (also, same derivation)"],
        semantic_shift="'so well/equally well' → also, too",
    ),
    EtymologyEntry(
        language="pt", lemma="vinho",
        origin_summary=(
            "From Latin vinum (wine), from Proto-Indo-European *wóinom (wine, vine). "
            "Portugal produces some of the world's most distinctive wines: "
            "Port (vinho do Porto) and Vinho Verde. "
            "The Latin root gives English wine, vine, and vinegar."
        ),
        roots=["Latin vinum (wine)", "Proto-Indo-European *wóinom"],
        cognates=["English wine, vine, vineyard", "Spanish vino", "French vin", "Italian vino"],
    ),
    EtymologyEntry(
        language="pt", lemma="janela",
        origin_summary=(
            "From Latin ianuella (little gate, small door), diminutive of ianua (door, gate), "
            "from Ianus (the two-faced god of doorways and beginnings). "
            "A window as a 'little door.' January (Januarius) is named for the same Janus, "
            "the god who faces both past and future."
        ),
        roots=["Latin ianua (door, gate)", "Latin Ianus (god of doorways)"],
        cognates=["English January (same Janus)", "Spanish ventana (different etymology, from ventus/wind)"],
        semantic_shift="'little gate/door' → window (an opening in the wall)",
    ),
    EtymologyEntry(
        language="pt", lemma="cozinha",
        origin_summary=(
            "From Latin coquina (kitchen, cooking place), from coquere (to cook). "
            "The Latin coquere gives English cook, cuisine (via French), concoct, "
            "and biscuit (twice-cooked). Kitchen itself comes from the same Latin "
            "root via Old English cycene."
        ),
        roots=["Latin coquina (kitchen)", "Latin coquere (to cook)"],
        cognates=["English cook, cuisine", "Spanish cocina", "French cuisine", "English kitchen"],
        semantic_shift="'cooking place' → kitchen",
    ),
    EtymologyEntry(
        language="pt", lemma="língua",
        origin_summary=(
            "From Latin lingua (tongue, language). The physical organ of speech "
            "became the name for language itself — a metonymy so old it is invisible. "
            "The Latin lingua gives English lingual, bilingual, and linguist. "
            "The Romance languages were long called 'vulgar Latin tongues.'"
        ),
        roots=["Latin lingua (tongue, language)", "Proto-Indo-European *dn̥ǵʰwéh₂s (tongue)"],
        cognates=["English lingual, bilingual, linguist", "Spanish lengua", "French langue", "Italian lingua"],
        semantic_shift="'physical tongue' → language, speech system",
    ),
    EtymologyEntry(
        language="pt", lemma="rei",
        origin_summary=(
            "From Latin rex/regis (king), from regere (to rule, direct, guide). "
            "The Latin rex gives English regal, royal, reign, regent, and rector. "
            "The same Proto-Indo-European root *h₃reǵ- (to straighten, rule) "
            "gives Sanskrit rājan (king) and English right (straight)."
        ),
        roots=["Latin rex/regis (king)", "Latin regere (to rule, guide)", "PIE *h₃reǵ- (to straighten)"],
        cognates=["English regal, royal, reign, rector", "Spanish rey", "French roi", "Sanskrit rājan"],
        semantic_shift="'one who guides/straightens' → king",
    ),
    EtymologyEntry(
        language="pt", lemma="ilha",
        origin_summary=(
            "From Latin insula (island). The Latin root gives English insular, "
            "insulate, insulin (named for the islets of Langerhans in the pancreas), "
            "and peninsula (almost-island). Portuguese dropped the initial consonant "
            "cluster in- to produce ilha."
        ),
        roots=["Latin insula (island)"],
        cognates=["English insular, insulate, insulin, peninsula", "Spanish isla", "French île", "Italian isola"],
        semantic_shift="'isolated land mass' → island",
    ),
    EtymologyEntry(
        language="pt", lemma="ouro",
        origin_summary=(
            "From Latin aurum (gold), from Proto-Indo-European *h₂é-h₂us-o- (gold). "
            "The chemical symbol Au comes from aurum. "
            "Gold's chemical name and Portuguese name share this Latin root. "
            "The Brazilian state of Minas Gerais was named for its gold and mineral wealth."
        ),
        roots=["Latin aurum (gold)", "Proto-Indo-European *h₂é-h₂us-o-"],
        cognates=["English aureate, aurora (golden dawn)", "Spanish oro", "French or", "Italian oro"],
        semantic_shift="'the shining metal' → gold",
    ),
    EtymologyEntry(
        language="pt", lemma="filho",
        origin_summary=(
            "From Latin filius (son), from Proto-Indo-European *dʰeh₁y- (to suck, "
            "to nurse). The PIE root links son to the concept of nursing/suckling. "
            "Latin filius gives English affiliate (to adopt as a son) and filial. "
            "Portuguese filho can refer to both son and child generally."
        ),
        roots=["Latin filius (son)", "PIE *dʰeh₁y- (to suck, nurse)"],
        cognates=["English filial, affiliate", "Spanish hijo", "French fils", "Italian figlio"],
        semantic_shift="'nursling, son' → son/child",
    ),
    EtymologyEntry(
        language="pt", lemma="porta",
        origin_summary=(
            "From Latin porta (gate, door, city gate), from portare (to carry). "
            "A gate as the place through which things are carried. "
            "The same root gives English port (harbor — where cargo is carried), "
            "portal, portfolio, and transport."
        ),
        roots=["Latin porta (gate, door)", "Latin portare (to carry)"],
        cognates=["English port, portal, transport, import, export", "Spanish puerta", "French porte"],
        semantic_shift="'passage for carrying' → gate, door",
    ),
    EtymologyEntry(
        language="pt", lemma="leite",
        origin_summary=(
            "From Latin lac/lactis (milk) via Vulgar Latin lacte (ablative form). "
            "The Latin root gives English lactose, lactic, lactate, and galaxy "
            "(via Greek gala/galaktos — the Milky Way). "
            "Portuguese leite and Spanish leche both come from the Vulgar Latin lacte."
        ),
        roots=["Latin lac/lactis (milk)", "Vulgar Latin lacte"],
        cognates=["English lactose, lactic, galaxy", "Spanish leche", "French lait", "Italian latte"],
        semantic_shift="'milk' → the liquid dairy product",
    ),

    # ── Russian (new entries) ─────────────────────────────────────────────────
    EtymologyEntry(
        language="ru", lemma="берег",
        origin_summary=(
            "From Proto-Slavic *bergъ (bank, shore, slope). Cognate with Norwegian "
            "berg (mountain, cliff) and English borough/burg (a fortified height). "
            "The shared PIE root *bhergh- (high, hill) links river banks, "
            "mountains, and fortified hilltops across Germanic and Slavic."
        ),
        roots=["Proto-Slavic *bergъ (bank, shore)", "PIE *bhergh- (high, elevated)"],
        cognates=["German Berg (mountain)", "English borough/burg", "Norwegian berg"],
        semantic_shift="'elevated slope/height' → river bank, shoreline",
    ),
    EtymologyEntry(
        language="ru", lemma="богатый",
        origin_summary=(
            "From богатство (wealth), ultimately from бог (God). Originally meant "
            "'god-given, blessed by God' — wealth as divine gift. "
            "The connection of divine favor to material prosperity is ancient "
            "and cross-cultural. The opposite, убогий (poor), literally means 'without God.'"
        ),
        roots=["Proto-Slavic *bogъ (God, wealth-giver)", "PIE *bhag- (to allot, distribute)"],
        cognates=["Russian бог (God)", "Sanskrit bhaga (fortune, lord)", "Russian убогий (poor — 'without God')"],
        semantic_shift="'god-given, divinely blessed' → wealthy, rich",
    ),
    EtymologyEntry(
        language="ru", lemma="брат",
        origin_summary=(
            "From Proto-Slavic *bratrъ (brother), from PIE *bʰréh₂tēr. "
            "One of the most stable words in the Indo-European family — "
            "nearly identical across Latin frater, Greek phrāter, Sanskrit bhrātṛ, "
            "English brother, and Old Irish brathair. "
            "Russian also uses it colloquially to mean 'buddy, pal.'"
        ),
        roots=["Proto-Slavic *bratrъ", "PIE *bʰréh₂tēr (brother)"],
        cognates=["Latin frater", "English brother", "Sanskrit bhrātṛ", "Greek phrāter", "German Bruder"],
    ),
    EtymologyEntry(
        language="ru", lemma="вода",
        origin_summary=(
            "From Proto-Slavic *voda (water), from PIE *wódr̥. "
            "One of the most fundamental PIE words, present across nearly all branches: "
            "English water, German Wasser, Greek hydor (giving English hydrogen and hydro-), "
            "and Sanskrit udaka. "
            "Vodka is the diminutive: вода → водка (little water)."
        ),
        roots=["Proto-Slavic *voda", "PIE *wódr̥ (water)"],
        cognates=["English water", "German Wasser", "Greek hydor", "Sanskrit udaka", "Russian водка (diminutive)"],
        semantic_shift="'water' → also vodka (diminutive 'little water')",
    ),
    EtymologyEntry(
        language="ru", lemma="время",
        origin_summary=(
            "From Proto-Slavic *verme (time, season), from a root meaning 'to turn' "
            "(*ver- to turn/spin). Time as 'the turning' or 'that which revolves.' "
            "The same root appears in Latin vertere (to turn), giving English convert, "
            "version, and verse. Russian время encompasses both 'time' and 'weather' (like French temps)."
        ),
        roots=["Proto-Slavic *verme (time)", "PIE *wer- (to turn, bend)"],
        cognates=["Latin vertere (to turn)", "English verse, version, convert", "Old Church Slavonic врѣмѧ"],
        semantic_shift="'the turning/spinning (of seasons)' → time, weather",
    ),
    EtymologyEntry(
        language="ru", lemma="глаз",
        origin_summary=(
            "Originally meant 'smooth round stone, pebble, ball' — the eye was "
            "named for its round shape. This replaced the older Slavic oko (eye), "
            "which survives in compound words. "
            "The shift from the Old Slavic word for 'eye' to a metaphor from 'pebble' "
            "is a fascinating semantic innovation unique to Russian and related dialects."
        ),
        roots=["Proto-Slavic *glazъ (smooth stone, pebble, ball)"],
        cognates=["Russian окно (window — from oko, old word for eye)", "Czech oko (eye, preserved)"],
        semantic_shift="'smooth round pebble/ball' → eye (named for its round shape)",
    ),
    EtymologyEntry(
        language="ru", lemma="голос",
        origin_summary=(
            "From Proto-Slavic *golsъ (voice, sound), related to Old Church Slavonic "
            "глас (voice). The archaic/literary form голос coexists with the Church "
            "Slavonic глас in set phrases and religious contexts. "
            "Cognate with Lithuanian galas (end) and possibly with call."
        ),
        roots=["Proto-Slavic *golsъ (voice, sound)"],
        cognates=["Old Church Slavonic глас (voice)", "Lithuanian galas"],
        semantic_shift="'sound, voice' → voting voice (голосовать = to vote, 'to give voice')",
    ),
    EtymologyEntry(
        language="ru", lemma="город",
        origin_summary=(
            "From Proto-Slavic *gordъ (enclosed/fortified settlement), from PIE "
            "*gʰordʰo- (enclosure, yard). "
            "Cities began as fortified enclosures. The same root gives English "
            "garden and yard (enclosed space), German Garten, and the -grad/-gorod "
            "in city names: Novgorod (new city), Leningrad, Belgrade."
        ),
        roots=["Proto-Slavic *gordъ (enclosed settlement)", "PIE *gʰordʰo- (enclosure)"],
        cognates=["English garden, yard", "German Garten", "Serbian grad (city)", "Novgorod, Leningrad"],
        semantic_shift="'fortified enclosure' → settlement → city",
    ),
    EtymologyEntry(
        language="ru", lemma="гость",
        origin_summary=(
            "From Proto-Slavic *gostь (guest, stranger), from PIE *gʰóstis (stranger, "
            "guest, host). The same PIE root gives Latin hostis (enemy — a stranger "
            "who became hostile) and hospes (guest-friend, host). "
            "English host and guest are both from this root, preserving the ancient "
            "guest-friendship institution."
        ),
        roots=["Proto-Slavic *gostь (guest)", "PIE *gʰóstis (stranger, guest)"],
        cognates=["Latin hostis (enemy)", "Latin hospes (host, guest)", "English guest, host, hostile"],
        semantic_shift="'stranger under guest-friendship' → guest, visitor",
    ),
    EtymologyEntry(
        language="ru", lemma="дерево",
        origin_summary=(
            "From Proto-Slavic *dervo (tree, wood), from PIE *dóru (tree, wood). "
            "The same PIE root gives Greek dys (oak, Dryad — tree nymph), "
            "English tree (a metathesized form), and tar (wood distillate). "
            "The word serves for both 'tree' (the plant) and 'wood' (the material)."
        ),
        roots=["Proto-Slavic *dervo (tree, wood)", "PIE *dóru (tree, wood)"],
        cognates=["Greek drys (oak), dryad (tree-nymph)", "English tree, tar", "Sanskrit dāru (wood)"],
        semantic_shift="'the living tree' → also wood as material",
    ),
    EtymologyEntry(
        language="ru", lemma="деньги",
        origin_summary=(
            "Borrowed from Tatar teŋkä (silver coin, money) during the Mongol period "
            "(13th–15th centuries). One of many Tatar/Mongol loanwords in Russian "
            "relating to trade, administration, and horses. "
            "The plural form деньги replaced earlier native Slavic words for currency."
        ),
        roots=["Tatar teŋkä (silver coin)"],
        cognates=["Mongolian tögrög (currency)", "Turkish tenge (currency of Kazakhstan)"],
        semantic_shift="'silver coin (Tatar/Mongol)' → money generally",
    ),
    EtymologyEntry(
        language="ru", lemma="дорога",
        origin_summary=(
            "From Proto-Slavic *dorga (road, path). "
            "Intriguingly, the same root gives дорогой (dear, expensive) — "
            "roads were costly to maintain and travel was precious. "
            "The semantic link between 'road' and 'valuable' reflects the importance "
            "of roads in pre-modern economies."
        ),
        roots=["Proto-Slavic *dorga (road, path)"],
        cognates=["Russian дорогой (dear, expensive — same root)", "Polish droga (road)"],
        semantic_shift="'path, road' → shared root with 'dear/expensive' (roads as valued things)",
    ),
    EtymologyEntry(
        language="ru", lemma="друг",
        origin_summary=(
            "From Proto-Slavic *drugъ (another, the second, a companion). "
            "A friend as 'the other one' — the person alongside you. "
            "The same root gives другой (other, another). "
            "In Old Church Slavonic, другъ could mean both 'friend' and 'the other' — "
            "companionship as the experience of otherness."
        ),
        roots=["Proto-Slavic *drugъ (another, companion)"],
        cognates=["Russian другой (other, another — same root)", "Old Church Slavonic другъ (friend, other)"],
        semantic_shift="'another, the second one' → companion → friend",
    ),
    EtymologyEntry(
        language="ru", lemma="живой",
        origin_summary=(
            "From Proto-Slavic *živъ (alive, living), from PIE *gʷih₃wós (alive). "
            "The same PIE root gives Latin vivus (alive — vivid, survive), "
            "Greek bios (life — biology, biography), and English quick "
            "(originally 'living,' as in 'the quick and the dead')."
        ),
        roots=["Proto-Slavic *živъ (alive)", "PIE *gʷih₃wós (alive)"],
        cognates=["Latin vivus (alive)", "Greek bios (life)", "English quick (originally 'living')"],
        semantic_shift="'alive, living' → lively, vivid",
    ),
    EtymologyEntry(
        language="ru", lemma="зима",
        origin_summary=(
            "From Proto-Slavic *zima (winter, cold), from PIE *ǵʰeymon- (winter, snow). "
            "The same PIE root gives Greek cheimōn (winter storm), Himalaya "
            "(Sanskrit hima + alaya = 'abode of snow'), and Latin hiems (winter — "
            "giving English hibernate)."
        ),
        roots=["Proto-Slavic *zima (winter, cold)", "PIE *ǵʰeymon- (winter, snow)"],
        cognates=["Greek cheimōn (winter)", "Sanskrit hima (snow — as in Himalaya)", "Latin hiems (winter)"],
    ),
    EtymologyEntry(
        language="ru", lemma="книга",
        origin_summary=(
            "Possibly borrowed from Old Turkic kü:inig (book, document) or Uyghur "
            "küinig — a very early cultural loanword from the steppe contact zone. "
            "The word's ultimate source is debated; some propose a Chinese origin. "
            "It is one of the oldest non-Slavic loanwords in Russian."
        ),
        roots=["Old Turkic kü:inig (book, document)"],
        cognates=["Mongolian nom (book — from Greek nomos)", "Old Bulgarian кънига (book)"],
        semantic_shift="Turkic word for written document → book in all Slavic languages",
    ),
    EtymologyEntry(
        language="ru", lemma="конь",
        origin_summary=(
            "From Proto-Slavic *konjь (horse), possibly borrowed from Germanic *kuna "
            "or from an Iranian source. "
            "Russian distinguishes конь (noble horse, poetic) from лошадь (horse, colloquial). "
            "Конь appears in chess (the knight piece) and in heraldry and epic poetry."
        ),
        roots=["Proto-Slavic *konjь (horse)"],
        cognates=["Polish koń (horse)", "Czech kůň (horse)", "English conestoga (wagon horse — unrelated)"],
        semantic_shift="'horse' → noble/poetic horse vs. everyday лошадь",
    ),
    EtymologyEntry(
        language="ru", lemma="кровь",
        origin_summary=(
            "From Proto-Slavic *krъvь (blood), from PIE *krewh₂- (raw flesh, blood). "
            "The same PIE root gives Latin cruor (gore, raw blood — distinct from sanguis), "
            "and possibly Greek kreas (flesh — creating creosote). "
            "A very ancient word for blood as raw, vital substance."
        ),
        roots=["Proto-Slavic *krъvь (blood)", "PIE *krewh₂- (raw flesh, blood)"],
        cognates=["Latin cruor (gore, raw blood)", "Greek kreas (flesh)", "English raw (same PIE root)"],
        semantic_shift="'raw vital fluid' → blood",
    ),
    EtymologyEntry(
        language="ru", lemma="лес",
        origin_summary=(
            "From Proto-Slavic *lěsъ (forest, woodland). A core Slavic environmental "
            "word with no clear cognates outside the Slavic branch — suggesting it may "
            "have been borrowed from a non-IE substrate language of Eastern Europe. "
            "Russia's vast forest (taiga) makes this one of the most culturally important "
            "words in the language."
        ),
        roots=["Proto-Slavic *lěsъ (forest)"],
        cognates=["Polish las (forest)", "Czech les (forest)", "Bulgarian лес (forest)"],
        semantic_shift="'woodland' → the Russian forest, taiga — a cultural symbol",
    ),
    EtymologyEntry(
        language="ru", lemma="мать",
        origin_summary=(
            "From Proto-Slavic *mati (mother), from PIE *méh₂tēr. "
            "One of the most stable words in all Indo-European languages: "
            "Latin mater, Greek mētēr, Sanskrit mātṛ, Armenian mayr, English mother, "
            "German Mutter. All are cognates. "
            "The Russian colloquial form мама is also from this root."
        ),
        roots=["Proto-Slavic *mati (mother)", "PIE *méh₂tēr"],
        cognates=["Latin mater", "English mother", "Sanskrit mātṛ", "Greek mētēr", "German Mutter"],
    ),
    EtymologyEntry(
        language="ru", lemma="море",
        origin_summary=(
            "From Proto-Slavic *morje (sea), from PIE *móri (sea, large body of water). "
            "The same PIE root gives Latin mare (sea — maritime, submarine), "
            "French mer, and English mere (a lake in northern dialects). "
            "Морской (of the sea) and мор (plague, mass death) share this root "
            "— the sea as a place of death."
        ),
        roots=["Proto-Slavic *morje (sea)", "PIE *móri (sea, lake)"],
        cognates=["Latin mare (sea)", "French mer", "English mere (lake), maritime", "German Meer"],
        semantic_shift="'large body of water' → sea/ocean",
    ),
    EtymologyEntry(
        language="ru", lemma="народ",
        origin_summary=(
            "Compound of на- (on, upon) + род (birth, generation, clan). "
            "Literally 'those born together' or 'upon the same birth/generation.' "
            "Народ encompasses 'people,' 'folk,' and 'nation' without English's "
            "distinctions. It carries strong cultural weight in Russian thought "
            "and literature (Tolstoy's understanding of the народ)."
        ),
        roots=["Russian на- (upon) + род (birth, generation, clan)"],
        cognates=["Russian родина (homeland — same root)", "Russian родить (to give birth)", "Czech národ (nation)"],
        semantic_shift="'those born together' → the people, the nation, the folk",
    ),
    EtymologyEntry(
        language="ru", lemma="огонь",
        origin_summary=(
            "From Proto-Slavic *ognь (fire), from PIE *h₁ngʷnis (fire). "
            "One of the clearest IE etymologies: Latin ignis (fire — ignite, ignition), "
            "Sanskrit agni (fire — Agni, the Vedic fire god), Lithuanian ugnis. "
            "Fire as a sacred PIE element appears across ritual, language, and mythology."
        ),
        roots=["Proto-Slavic *ognь (fire)", "PIE *h₁ngʷnis (fire)"],
        cognates=["Latin ignis (fire — ignite)", "Sanskrit agni (fire, Agni)", "Lithuanian ugnis"],
    ),
    EtymologyEntry(
        language="ru", lemma="родина",
        origin_summary=(
            "From род (birth, clan, generation) + suffix -ина (place/collective suffix). "
            "Literally 'the place of one's birth and kin.' "
            "Родина is the emotionally charged word for 'homeland' — more intimate "
            "than отечество (fatherland, the official/political term). "
            "The WWII-era poster 'Родина-мать зовёт!' (The Motherland Calls!) made it iconic."
        ),
        roots=["Proto-Slavic *rodъ (birth, clan, generation)", "PIE *Herdh- (to grow)"],
        cognates=["Russian народ (people)", "Russian родить (to give birth)", "Russian род (clan)"],
        semantic_shift="'place of one's birth/kin' → beloved homeland, motherland",
    ),
    EtymologyEntry(
        language="ru", lemma="река",
        origin_summary=(
            "From Proto-Slavic *rěka (river), from PIE *h₃reǵ- or a separate water root. "
            "Russia is defined by its rivers — the Volga, the Ob, the Yenisei. "
            "Река is used for rivers generally; specific rivers often have non-Slavic "
            "names from earlier indigenous inhabitants."
        ),
        roots=["Proto-Slavic *rěka (river, stream)"],
        cognates=["Polish rzeka (river)", "Czech řeka (river)", "Bulgarian река (river)"],
        semantic_shift="'flowing water' → river",
    ),
    EtymologyEntry(
        language="ru", lemma="рука",
        origin_summary=(
            "From Proto-Slavic *rǫka (hand, arm), from PIE *h₃rengʷ- or related root. "
            "Russian (like German Arm but unlike English) uses one word for the entire "
            "limb from shoulder to fingertip. "
            "Рука appears in hundreds of idioms: рукопожатие (handshake), рукопись (manuscript — handwriting)."
        ),
        roots=["Proto-Slavic *rǫka (hand/arm)"],
        cognates=["Polish ręka (hand)", "Czech ruka (hand)", "Russian рукопись (manuscript — hand-writing)"],
        semantic_shift="'hand and arm (as one limb)' → hand in common usage",
    ),
    EtymologyEntry(
        language="ru", lemma="сердце",
        origin_summary=(
            "From Proto-Slavic *sьrdьce (heart), from PIE *ḱḗrd (heart). "
            "One of the most pan-IE words: Latin cor/cordis (heart — cordial, accord, "
            "concord), Greek kardia (heart — cardiac), English heart, Sanskrit hṛd. "
            "All are cognates — the heart as the physical and emotional center."
        ),
        roots=["Proto-Slavic *sьrdьce (heart)", "PIE *ḱḗrd (heart)"],
        cognates=["Latin cor/cordis (heart)", "Greek kardia (heart)", "English heart", "Sanskrit hṛd"],
        semantic_shift="'physical heart' → seat of emotion and courage",
    ),
    EtymologyEntry(
        language="ru", lemma="сын",
        origin_summary=(
            "From Proto-Slavic *synъ (son), from PIE *suHnús (son). "
            "The same PIE root gives English son, German Sohn, Sanskrit sūnu, "
            "and Gothic sunus. One of the core family terms preserved "
            "across the entire IE family."
        ),
        roots=["Proto-Slavic *synъ (son)", "PIE *suHnús (son)"],
        cognates=["English son", "German Sohn", "Sanskrit sūnu", "Gothic sunus"],
    ),
    EtymologyEntry(
        language="ru", lemma="человек",
        origin_summary=(
            "Compound of two archaic roots: чело (forehead, front; now poetic) "
            "+ век (age, era, lifetime). The full etymology is debated — "
            "possibly 'one at the forefront of an age' or 'a being of the human era.' "
            "The word is distinctively Slavic with no direct IE cognates for the compound."
        ),
        roots=["Old Slavic чело (forehead, front)", "Old Slavic вѣкъ (age, era, lifetime)"],
        cognates=["Polish człowiek (person)", "Czech člověk (person)", "Russian век (century, era)"],
        semantic_shift="'being of the forefront/era' → person, human being",
    ),
    EtymologyEntry(
        language="ru", lemma="имя",
        origin_summary=(
            "From Proto-Slavic *jьmę (name), from PIE *h₁nómn̥ (name). "
            "One of the clearest pan-IE etymologies: Latin nomen (name — nominal, "
            "noun, pronoun), Greek onoma (name — anonymous, pseudonym), "
            "English name, Sanskrit nāman. "
            "The Russian form is irregular due to the Proto-Slavic nasal vowel."
        ),
        roots=["Proto-Slavic *jьmę (name)", "PIE *h₁nómn̥ (name)"],
        cognates=["Latin nomen (name)", "Greek onoma (name)", "English name", "Sanskrit nāman"],
    ),
    EtymologyEntry(
        language="ru", lemma="любить",
        origin_summary=(
            "From Proto-Slavic *ljubiti (to love, to hold dear), from *ljubъ (dear, "
            "beloved). Related to PIE *lewbʰ- (to love, desire). "
            "Latin lubet/libet (it pleases) and English lief (willingly — as in 'I'd "
            "as lief') share the same PIE root. "
            "Russian distinguishes любить (enduring love) from влюбиться (to fall in love)."
        ),
        roots=["Proto-Slavic *ljubiti (to love)", "PIE *lewbʰ- (to love, desire)"],
        cognates=["Latin lubet/libet (it pleases)", "English lief (willingly)", "German lieb (dear)"],
        semantic_shift="'to hold dear, to desire' → to love (enduring affection)",
    ),
    EtymologyEntry(
        language="ru", lemma="старый",
        origin_summary=(
            "From Proto-Slavic *starъ (old), from PIE *steh₂- (to stand, be firm, be "
            "established). Old as 'that which has stood long.' "
            "Latin stare (to stand) and status share the root. "
            "Russian distinguishes старый (old of things/people) from древний (ancient, "
            "of civilizations)."
        ),
        roots=["Proto-Slavic *starъ (old)", "PIE *steh₂- (to stand, be firm)"],
        cognates=["Latin stare (to stand), status", "English stand, stable", "German alt (different root)"],
        semantic_shift="'that which has stood (for a long time)' → old, aged",
    ),
    EtymologyEntry(
        language="ru", lemma="новый",
        origin_summary=(
            "From Proto-Slavic *novъ (new), from PIE *néwos (new). "
            "One of the most pan-IE adjectives: Latin novus (new — novel, innovate, "
            "renovate), Greek neos (new — neoclassical, Neolithic), English new, "
            "Sanskrit nava. Novgorod means 'new city' (новый + город)."
        ),
        roots=["Proto-Slavic *novъ (new)", "PIE *néwos (new)"],
        cognates=["Latin novus (new)", "Greek neos (new)", "English new", "Sanskrit nava", "Novgorod (new city)"],
    ),

    # ── French (new entries) ──────────────────────────────────────────────────
    EtymologyEntry(
        language="fr", lemma="amour",
        origin_summary=(
            "From Latin amor (love, affection), from amare (to love). "
            "In French amour became the romantic ideal — courtly love (amour courtois) "
            "was a medieval French literary institution. "
            "The word entered English in amorous, enamored, and in philosophical 'amour propre' (self-love)."
        ),
        roots=["Latin amor (love)", "Latin amare (to love)"],
        cognates=["English amorous, enamored, amour propre", "Spanish amor", "Italian amore"],
    ),
    EtymologyEntry(
        language="fr", lemma="art",
        origin_summary=(
            "From Latin ars/artis (skill, craft, technique), from PIE *h₂er- (to fit together). "
            "Originally meant skill or craft in general — military art, the art of cooking. "
            "The narrowing to fine arts (beaux-arts) occurred gradually in French and English. "
            "Artisan, artisan, and article all share this root."
        ),
        roots=["Latin ars/artis (skill, craft)", "PIE *h₂er- (to fit together)"],
        cognates=["English art, artisan, article, arm (weapon — to fit)", "Spanish arte", "Italian arte"],
        semantic_shift="'skill, fitting things together' → fine arts",
    ),
    EtymologyEntry(
        language="fr", lemma="bagage",
        origin_summary=(
            "From Old French bague (bundle, pack), of Germanic origin (related to bag). "
            "The suffix -age forms a collective. "
            "English baggage is borrowed from the same French source. "
            "The phrase 'intellectual baggage' (ideas one carries) is a direct metaphorical extension."
        ),
        roots=["Old French bague (bundle)", "Germanic bag (pack, sack)"],
        cognates=["English baggage, bag (same root)", "Spanish bagaje"],
        semantic_shift="'bundle of packs' → luggage → figurative 'baggage' one carries",
    ),
    EtymologyEntry(
        language="fr", lemma="balcon",
        origin_summary=(
            "Borrowed from Italian balcone (large window, scaffold, balcony), "
            "from balco (beam, scaffold) of Proto-Germanic *balkô (beam). "
            "The architectural feature spread from Italy with Renaissance design. "
            "Shakespeare's balcony in Romeo and Juliet is an anachronism — "
            "the word didn't exist in English until 1618."
        ),
        roots=["Italian balco (beam, scaffold)", "Proto-Germanic *balkô (beam)"],
        cognates=["English balcony (from Italian via French)", "English balk (beam — same root)"],
        semantic_shift="'scaffold, beam structure' → projecting platform on a building's facade",
    ),
    EtymologyEntry(
        language="fr", lemma="banlieue",
        origin_summary=(
            "Compound of ban (legal jurisdiction, proclamation) + lieue (league, a unit "
            "of distance). The banlieue was the area within one league of a town "
            "subject to its ban (lord's authority). "
            "Now means suburb or outskirts — the zone just outside the city proper."
        ),
        roots=["Frankish ban (authority, jurisdiction)", "Latin leuca (league, distance)"],
        cognates=["English ban (same Frankish root)", "English league (same Latin root)"],
        semantic_shift="'area within the lord's legal reach' → suburb, city outskirts",
    ),
    EtymologyEntry(
        language="fr", lemma="bonjour",
        origin_summary=(
            "Compound of bon (good, from Latin bonus) + jour (day, from Latin diurnum). "
            "The greeting 'good day' — wishing the other person a good day. "
            "French uses bonjour in the morning and afternoon (unlike English's "
            "three-way good morning/afternoon/evening split) and bonsoir for evening."
        ),
        roots=["Latin bonus (good)", "Latin diurnum (of the day, daily)"],
        cognates=["English bonus (borrowed from Latin)", "English diurnal, journal (same Latin root)"],
        semantic_shift="'good day (wish)' → standard daytime greeting",
    ),
    EtymologyEntry(
        language="fr", lemma="courage",
        origin_summary=(
            "From Old French corage, from cuer (heart, from Latin cor/cordis) "
            "+ suffix -age. Courage is literally 'heartedness' — having heart. "
            "English borrowed it from French. "
            "The same Latin cor gives accord, record, and cordial."
        ),
        roots=["Latin cor/cordis (heart)", "Old French cuer (heart) + -age suffix"],
        cognates=["English encourage (give heart to)", "English cordial, accord (same root)", "Spanish coraje"],
        semantic_shift="'heartedness, having heart' → bravery, moral strength",
    ),
    EtymologyEntry(
        language="fr", lemma="croissant",
        origin_summary=(
            "Present participle of croître (to grow, to increase), from Latin crescere. "
            "The pastry is named for its crescent (growing/waxing moon) shape. "
            "The Viennese kipferl is the ancestor; the French croissant with flaky "
            "laminated dough was developed in Paris in the 19th century."
        ),
        roots=["Latin crescere (to grow, increase)", "PIE *ker- (to grow)"],
        cognates=["English crescent (waxing moon)", "English increase, concrete (same root)", "Italian crescendo"],
        semantic_shift="'growing (waxing moon shape)' → crescent-shaped flaky pastry",
    ),
    EtymologyEntry(
        language="fr", lemma="danger",
        origin_summary=(
            "From Old French dongier, from Vulgar Latin *dominiarium (the power/authority "
            "of a lord), from dominus (lord, master). Being in danger was originally "
            "being 'in the lord's power' — subject to someone else's authority. "
            "The shift from 'being in someone's power' to 'being at risk' "
            "is a remarkable semantic journey."
        ),
        roots=["Latin dominus (lord, master)", "Vulgar Latin *dominiarium (lordship)"],
        cognates=["English domain, dominate, dominion (same root)", "English danger (borrowed from French)"],
        semantic_shift="'being in a lord's power' → being in peril",
    ),
    EtymologyEntry(
        language="fr", lemma="droit",
        origin_summary=(
            "From Latin directum (straight, direct), from dirigere (to direct, guide). "
            "Law as 'that which is straight' — the straight line of justice. "
            "Le droit means both 'law' and 'a right (entitlement).' "
            "English direct, rector, and region all share the same Latin root."
        ),
        roots=["Latin directum (straight, direct)", "Latin dirigere (to direct, guide)"],
        cognates=["English direct, direction, rector", "Italian diritto (law/right)", "Spanish derecho (law/right)"],
        semantic_shift="'straight, directed' → law (the straight path), a legal right",
    ),
    EtymologyEntry(
        language="fr", lemma="eau",
        origin_summary=(
            "From Latin aqua (water) via Vulgar Latin *eawa. "
            "The evolution from aqua to eau shows the radical reduction French applied "
            "to Latin: aq- → e-, -ua → -au. "
            "Despite being only three letters, eau preserves the full Latin word's meaning. "
            "Eau de toilette and eau de vie (water of life = brandy) are compound borrowings."
        ),
        roots=["Latin aqua (water)", "PIE *akʷā- (water)"],
        cognates=["English aquatic, aqueduct (from Latin aqua)", "Spanish agua", "Italian acqua"],
        semantic_shift="'water' → used in many compound French words (eau de vie, eau de cologne)",
    ),
    EtymologyEntry(
        language="fr", lemma="église",
        origin_summary=(
            "From Latin ecclesia, from Greek ekklesia (assembly of citizens called out "
            "to meet), from ek- (out) + kalein (to call). "
            "Early Christians adopted the Greek word for civic assembly as their "
            "word for the congregation and then the building. "
            "English ecclesiastical and Anglican church both preserve this etymology."
        ),
        roots=["Greek ekklesia (assembly)", "Greek ek- (out) + kalein (to call)"],
        cognates=["English ecclesiastical (same Greek root)", "Spanish iglesia", "Italian chiesa"],
        semantic_shift="'civic assembly (called out)' → Christian congregation → the church building",
    ),
    EtymologyEntry(
        language="fr", lemma="enfant",
        origin_summary=(
            "From Latin infans (non-speaking, unable to speak), from in- (not) + "
            "fari (to speak). An infant as 'the one who cannot yet speak.' "
            "The Latin root fari gives English fate (what is spoken by the gods), "
            "fable (spoken story), and famous."
        ),
        roots=["Latin infans (non-speaking)", "Latin in- (not) + fari (to speak)"],
        cognates=["English infant (same source)", "English fate, fable, famous (Latin fari)"],
        semantic_shift="'non-speaking (one)' → infant → child generally",
    ),
    EtymologyEntry(
        language="fr", lemma="famille",
        origin_summary=(
            "From Latin familia (household, servants, family), from famulus (servant). "
            "The Latin familia originally meant the household including slaves and servants — "
            "not just the blood relatives. The sense narrowed to blood family over centuries. "
            "Familiar (of the household) shares this root."
        ),
        roots=["Latin familia (household)", "Latin famulus (servant, household member)"],
        cognates=["English familiar, family (same Latin root)", "Spanish familia", "Italian famiglia"],
        semantic_shift="'entire household (including servants)' → blood family",
    ),
    EtymologyEntry(
        language="fr", lemma="fleur",
        origin_summary=(
            "From Latin flos/floris (flower, blossom), from PIE *bʰleh₃- (to bloom). "
            "The fleur-de-lis (flower of the lily) is the heraldic symbol of France. "
            "English flour is borrowed from French fleur (the finest/flowering part "
            "of ground grain — the flower of wheat)."
        ),
        roots=["Latin flos/floris (flower)", "PIE *bʰleh₃- (to bloom, blossom)"],
        cognates=["English flower, flour, flourish, floral (same Latin root)", "Spanish flor", "Italian fiore"],
        semantic_shift="'bloom' → flower → English flour (the finest part, the 'flower' of grain)",
    ),
    EtymologyEntry(
        language="fr", lemma="forêt",
        origin_summary=(
            "From Medieval Latin forestis (outside, open woodland), from foris (outside, "
            "outdoors). A forest was royal hunting land kept 'outside' (unfarmed). "
            "The circumflex in forêt marks the lost 's' of Old French forest. "
            "English forest is borrowed from the same Latin source."
        ),
        roots=["Medieval Latin forestis (outside woodland)", "Latin foris (outside, outdoors)"],
        cognates=["English forest (same source)", "English foreign (from foris — outside)", "Spanish bosque (different etymology)"],
        semantic_shift="'royal hunting ground outside settled land' → woodland generally",
    ),
    EtymologyEntry(
        language="fr", lemma="glace",
        origin_summary=(
            "From Latin glacies (ice), from PIE *gel- (cold, to freeze). "
            "French glace covers ice, a mirror (polished like ice), and ice cream — "
            "three senses unified by reflective, cold smoothness. "
            "Glacier shares this root. English glass is from a Germanic cognate "
            "(*glasaz — shining substance)."
        ),
        roots=["Latin glacies (ice)", "PIE *gel- (cold, to freeze)"],
        cognates=["English glacier, glacial (same Latin root)", "English glass (Germanic cognate *glasaz)"],
        semantic_shift="'ice' → mirror (smooth, reflective like ice) → ice cream",
    ),
    EtymologyEntry(
        language="fr", lemma="honte",
        origin_summary=(
            "From Frankish *haunitha (contempt, shame), related to Gothic haunjan "
            "(to humiliate). A Germanic word at the core of French moral vocabulary, "
            "introduced by the Franks. "
            "English honest and honor entered French from Latin but honte itself "
            "is thoroughly Germanic."
        ),
        roots=["Frankish *haunitha (contempt, shame)", "Proto-Germanic *haunjaną (to humiliate)"],
        cognates=["English hone (to sharpen — different root)", "Dutch hoon (scorn — related)"],
        semantic_shift="'contempt, being held in contempt' → shame",
    ),
    EtymologyEntry(
        language="fr", lemma="humeur",
        origin_summary=(
            "From Latin humor (liquid, fluid, moisture). Medieval medicine held that "
            "four bodily fluids (humors) — blood, phlegm, yellow bile, black bile — "
            "determined personality and mood. "
            "A good humor meant the right fluid balance. "
            "English humor, humorous, and humid all share this Latin root."
        ),
        roots=["Latin humor (liquid, fluid, moisture)"],
        cognates=["English humor, humorous, humid (same root)", "Spanish humor"],
        semantic_shift="'bodily fluid' → temperament (fluid-based) → mood → wit and comedy",
    ),
    EtymologyEntry(
        language="fr", lemma="île",
        origin_summary=(
            "From Latin insula (island), via Old French isle. "
            "The circumflex in île marks the lost 's' (isle). "
            "The Latin insula gives English insular (island-minded), insulate "
            "(isolate like an island), and insulin (named for the islets of Langerhans "
            "in the pancreas)."
        ),
        roots=["Latin insula (island)"],
        cognates=["English isle, island (same root)", "English insular, insulate, insulin", "Spanish isla"],
        semantic_shift="'isolated land mass' → island",
    ),
    EtymologyEntry(
        language="fr", lemma="impasse",
        origin_summary=(
            "From im- (not, variant of in-) + passe (passage, from passer to pass). "
            "Literally 'no-passage' — a dead end. "
            "Borrowed into English and international diplomacy for a stalemate "
            "or deadlock where no progress is possible."
        ),
        roots=["French im- (not) + passe (passage, from passer — to pass)"],
        cognates=["English impassable (same components)", "Spanish callejón sin salida (different construction)"],
        semantic_shift="'no-through passage' → dead-end street → negotiation stalemate",
    ),
    EtymologyEntry(
        language="fr", lemma="jardin",
        origin_summary=(
            "From Frankish *gardo (enclosure, garden), from Proto-Germanic *gardaz. "
            "The same Germanic root gives English yard (enclosed space), garden "
            "(borrowed from Old North French), and German Garten. "
            "A garden as an enclosed, cultivated space contrasts with the wild forest."
        ),
        roots=["Frankish *gardo (enclosure)", "Proto-Germanic *gardaz (enclosure)"],
        cognates=["English garden, yard (same Germanic root)", "German Garten", "Italian giardino"],
        semantic_shift="'enclosed space' → cultivated planted enclosure",
    ),
    EtymologyEntry(
        language="fr", lemma="langue",
        origin_summary=(
            "From Latin lingua (tongue, language). The physical organ metonymically "
            "became the language system. "
            "The Romance languages were long called langues (tongues). "
            "Langue d'oc and langue d'oïl distinguished southern and northern medieval "
            "French by their word for 'yes' (oc vs. oïl → oui)."
        ),
        roots=["Latin lingua (tongue, language)", "PIE *dn̥ǵʰwéh₂s (tongue)"],
        cognates=["English lingual, bilingual, linguist", "Spanish lengua", "Italian lingua"],
        semantic_shift="'tongue (body part)' → language system → specific tongue (dialect/language)",
    ),
    EtymologyEntry(
        language="fr", lemma="liberté",
        origin_summary=(
            "From Latin libertas (freedom, independence), from liber (free). "
            "The French Revolution's rallying cry 'Liberté, Égalité, Fraternité' "
            "made this word the central emblem of republican values. "
            "The Statue of Liberty (La Liberté éclairant le monde) was France's gift to the US."
        ),
        roots=["Latin libertas (freedom)", "Latin liber (free)"],
        cognates=["English liberty, liberal, liberate (same root)", "Spanish libertad", "Italian libertà"],
        semantic_shift="'freedom from slavery' → political liberty → abstract freedom",
    ),
    EtymologyEntry(
        language="fr", lemma="livre",
        origin_summary=(
            "From Latin liber (book, the inner bark of trees on which Romans wrote), "
            "from an earlier meaning of the bark layer between wood and outer bark. "
            "The Romans adopted thin bark strips for writing before papyrus was widely available. "
            "Library (bibliothèque in French) comes from the same root via Latin librarium."
        ),
        roots=["Latin liber (book, tree bark)", "PIE root related to leaf/layer"],
        cognates=["English library (via Latin librarium)", "Spanish libro", "Italian libro"],
        semantic_shift="'tree bark (writing material)' → book",
    ),
    EtymologyEntry(
        language="fr", lemma="lumière",
        origin_summary=(
            "From Latin luminaria (lights, lamps, luminaries), plural of luminare "
            "(light source), from lumen/luminis (light). "
            "The Lumière brothers (Auguste and Louis) were named for 'light' — "
            "and invented cinema in 1895. "
            "Luminary, illuminate, and bioluminescence share this root."
        ),
        roots=["Latin lumen/luminis (light)", "Latin luminare (light source)"],
        cognates=["English luminary, illuminate, luminous (same root)", "Spanish luminaria"],
        semantic_shift="'light source' → light → the Lumières' cinema (light projected through film)",
    ),
    EtymologyEntry(
        language="fr", lemma="maison",
        origin_summary=(
            "From Latin mansio/mansionis (a stay, a stopping place, a dwelling), "
            "from manere (to remain, stay). A house as 'the place where one remains.' "
            "English mansion (a grand house) is borrowed from the same Latin word, "
            "while French maison covers ordinary houses too."
        ),
        roots=["Latin mansio (stay, dwelling)", "Latin manere (to remain)"],
        cognates=["English mansion, permanent, remain (same Latin root)", "Spanish mansión"],
        semantic_shift="'stopping/staying place' → house, dwelling",
    ),
    EtymologyEntry(
        language="fr", lemma="marché",
        origin_summary=(
            "From Latin mercatus (trade, market), from mercari (to trade), "
            "from merx/mercis (goods, merchandise). "
            "The same root gives English merchant, mercenary, mercy (originally "
            "'price paid'), and commerce. "
            "A market as the place of exchange of goods."
        ),
        roots=["Latin mercatus (trade, market)", "Latin merx/mercis (goods)"],
        cognates=["English market, merchant, commerce, mercy (same root)", "Spanish mercado", "Italian mercato"],
        semantic_shift="'trading, commercial exchange' → the marketplace itself",
    ),
    EtymologyEntry(
        language="fr", lemma="merci",
        origin_summary=(
            "From Latin merces (wages, pay, reward), from merx (goods). "
            "Originally merci meant 'favor, pity, mercy' — the gift given without "
            "expectation of payment. The shift from 'wages' to 'grace freely given' "
            "to 'thank you' is a remarkable semantic journey through Christian charity."
        ),
        roots=["Latin merces (wages, reward, price)", "Latin merx (goods)"],
        cognates=["English mercy (same source)", "English commerce, merchant (same root)", "Spanish merced"],
        semantic_shift="'wages, price' → favor/grace freely given → thank you",
    ),
    EtymologyEntry(
        language="fr", lemma="mère",
        origin_summary=(
            "From Latin mater/matris (mother), from PIE *méh₂tēr. "
            "One of the most stable IE words — essentially identical across "
            "Latin mater, Greek mētēr, Sanskrit mātṛ, English mother, German Mutter. "
            "French mère gives English maternal, maternity, and matrix (the mother-form)."
        ),
        roots=["Latin mater/matris (mother)", "PIE *méh₂tēr"],
        cognates=["English mother, maternal, matrix (same root)", "Spanish madre", "Italian madre"],
    ),
    EtymologyEntry(
        language="fr", lemma="montagne",
        origin_summary=(
            "From Latin montanea (mountainous places), from mons/montis (mountain). "
            "The same Latin root gives English mount, mountain, amount (to mount up), "
            "and paramount (above all mountains). "
            "The French Alps and Pyrenees gave montagne its cultural weight."
        ),
        roots=["Latin mons/montis (mountain)", "Latin montanea (mountainous places)"],
        cognates=["English mountain, mount, amount, paramount (same root)", "Spanish montaña", "Italian montagna"],
        semantic_shift="'mountainous terrain' → mountain",
    ),
    EtymologyEntry(
        language="fr", lemma="monde",
        origin_summary=(
            "From Latin mundus (world, universe, the clean/ordered cosmos), "
            "from mundare (to clean). The world as the 'ordered, clean' sphere "
            "contrasted with chaos. "
            "French monde also means 'people, society' (tout le monde = everyone). "
            "English mundane (worldly, ordinary) comes from the same root."
        ),
        roots=["Latin mundus (world, clean order)", "Latin mundare (to clean, make orderly)"],
        cognates=["English mundane (worldly, ordinary)", "Spanish mundo", "Italian mondo"],
        semantic_shift="'clean, ordered cosmos' → world → people/society",
    ),
    EtymologyEntry(
        language="fr", lemma="mort",
        origin_summary=(
            "From Latin mors/mortis (death), from PIE *mr̥tós (dead). "
            "The same PIE root gives English mortal, murder (to cause death), "
            "and mortgage (literally 'dead pledge' — the debt dies when paid off). "
            "French morte (dead, feminine) and mort (death, noun) both come from mors."
        ),
        roots=["Latin mors/mortis (death)", "PIE *mr̥tós (dead)"],
        cognates=["English mortal, murder, mortgage (dead pledge)", "Spanish muerte", "Italian morte"],
        semantic_shift="'dying' → death as noun → mortality as concept",
    ),
    EtymologyEntry(
        language="fr", lemma="nature",
        origin_summary=(
            "From Latin natura (birth, nature, the natural order), from nasci (to be born). "
            "Nature as 'that which is born' — the totality of the born/created world. "
            "French nature, English nature, Spanish naturaleza all derive from this. "
            "Natural philosophy was the predecessor to science."
        ),
        roots=["Latin natura (birth, the natural order)", "Latin nasci (to be born)"],
        cognates=["English nature, natural, native, nation (same Latin root)", "Spanish naturaleza"],
        semantic_shift="'the born/created order' → the physical world → natural character",
    ),
    EtymologyEntry(
        language="fr", lemma="nuit",
        origin_summary=(
            "From Latin nox/noctis (night), from PIE *nókʷts (night). "
            "One of the most pan-IE words: Greek nyx (night — the goddess Nyx), "
            "English night, German Nacht, Sanskrit nakta. "
            "Nocturnal, equinox (equal night), and nocturn all share this root."
        ),
        roots=["Latin nox/noctis (night)", "PIE *nókʷts (night)"],
        cognates=["English night, nocturnal, equinox (same root)", "Spanish noche", "German Nacht", "Greek nyx"],
    ),
    EtymologyEntry(
        language="fr", lemma="or",
        origin_summary=(
            "From Latin aurum (gold), from PIE *h₂é-h₂us-o- (the shining metal). "
            "The chemical symbol Au comes from aurum. "
            "French or (gold the metal) is distinct from the conjunction or (now/but), "
            "from Latin hora (hour — at that hour/now). "
            "Aurora (dawn — golden light) shares the gold root."
        ),
        roots=["Latin aurum (gold)", "PIE *h₂é-h₂us-o- (the shining metal)"],
        cognates=["English aureate, aurora", "Spanish oro", "Italian oro", "Chemical symbol Au"],
    ),
    EtymologyEntry(
        language="fr", lemma="ombre",
        origin_summary=(
            "From Latin umbra (shadow, shade, ghost), from PIE *n̥dʰro- (shadow). "
            "French ombre has entered English in hairdressing (gradient color) "
            "and watercolor technique. "
            "Latin umbra gives English umbrella (little shadow), adumbrate "
            "(to foreshadow), and the ombre card game."
        ),
        roots=["Latin umbra (shadow, shade)", "PIE *n̥dʰro- (shadow)"],
        cognates=["English umbrella, adumbrate (same root)", "Spanish sombra (shadow)", "Italian ombra"],
        semantic_shift="'shadow' → shade → ghostly presence → hair-coloring gradient technique",
    ),
    EtymologyEntry(
        language="fr", lemma="pain",
        origin_summary=(
            "From Latin panis (bread), from PIE *peh₂- (to protect, feed). "
            "Bread as the primary food, the thing that feeds. "
            "The same root gives English companion (com + panis — one who shares bread), "
            "pantry (bread store), and company (bread-sharers)."
        ),
        roots=["Latin panis (bread)", "PIE *peh₂- (to protect, feed)"],
        cognates=["English companion (bread-sharer)", "English pantry, company (same root)", "Spanish pan", "Italian pane"],
        semantic_shift="'bread (primary food)' → the French baguette culture's central word",
    ),
    EtymologyEntry(
        language="fr", lemma="pays",
        origin_summary=(
            "From Latin pagus (village, district, canton), from PIE *pag- (to fasten, "
            "fix — a settled, fixed place). "
            "A pays is the land/district one comes from — one's native region. "
            "English pagan (originally 'villager/rural person'), peasant, and page "
            "(territory) all share this Latin root."
        ),
        roots=["Latin pagus (village, rural district)", "PIE *pag- (to fix, fasten — settled place)"],
        cognates=["English pagan, peasant (same root)", "Spanish país", "Italian paese"],
        semantic_shift="'rural district/canton' → country, homeland",
    ),
    EtymologyEntry(
        language="fr", lemma="peuple",
        origin_summary=(
            "From Latin populus (people, nation, citizen body), from PIE root. "
            "The Latin populus gives English people, popular, public, republic "
            "(res publica — public thing), and populate. "
            "French le peuple carried revolutionary weight — the people vs. the aristocracy."
        ),
        roots=["Latin populus (people, citizen body)"],
        cognates=["English people, popular, republic (same root)", "Spanish pueblo", "Italian popolo"],
        semantic_shift="'citizen body' → the common people → the nation",
    ),
    EtymologyEntry(
        language="fr", lemma="plaisir",
        origin_summary=(
            "From Latin placere (to please, to be agreeable), infinitive used as a noun. "
            "The French turned the Latin infinitive directly into a noun — 'the pleasing.' "
            "English please and placid share the root. "
            "S'il vous plaît (if it pleases you) and à plaisir (with pleasure) "
            "show the word's politeness function."
        ),
        roots=["Latin placere (to please, to be agreeable)"],
        cognates=["English please, pleasant, placid, complacent (same root)", "Spanish placer"],
        semantic_shift="'the act of pleasing' → pleasure, enjoyment",
    ),
    EtymologyEntry(
        language="fr", lemma="pouvoir",
        origin_summary=(
            "From Latin potere (to be able), later Vulgar Latin *potēre, from potis "
            "(able, powerful). The French infinitive pouvoir (to be able) became "
            "a noun meaning 'power.' "
            "English potent, potential, and possible share the same Latin root."
        ),
        roots=["Latin potis (able, powerful)", "Latin potere (to be able)"],
        cognates=["English potent, potential, possible, impotent (same root)", "Spanish poder"],
        semantic_shift="'to be able' → power (the capacity to act)",
    ),
    EtymologyEntry(
        language="fr", lemma="raison",
        origin_summary=(
            "From Latin ratio/rationis (calculation, reckoning, reason, account), "
            "from reri (to think, reckon). Reason as 'calculation/reckoning.' "
            "English reason, rational, ratio, and ration all come from the same Latin root. "
            "The Enlightenment (le Siècle des Lumières) elevated la raison as supreme."
        ),
        roots=["Latin ratio/rationis (reckoning, reason)", "Latin reri (to think, reckon)"],
        cognates=["English reason, rational, ratio, ration (same root)", "Spanish razón", "Italian ragione"],
        semantic_shift="'calculation/reckoning' → reason, rational thought → cause/justification",
    ),
    EtymologyEntry(
        language="fr", lemma="rêve",
        origin_summary=(
            "From rêver (to dream, to wander), of uncertain origin — possibly from "
            "Old French desver (to wander, to be delirious) or from a Gaulish root. "
            "The connection to English 'rave' (to speak wildly) may be genuine. "
            "Rêve entered English in the phrase 'en rêve' and in the name of Debussy's Rêverie."
        ),
        roots=["Old French desver (to wander, be delirious)", "Possibly Gaulish substrate word"],
        cognates=["English rave (possibly related)", "French rêverie (daydream — borrowed into English)"],
        semantic_shift="'to wander/be delirious' → to dream → dream (noun)",
    ),
    EtymologyEntry(
        language="fr", lemma="reine",
        origin_summary=(
            "From Latin regina (queen, feminine of rex), from regere (to rule). "
            "The French reine, Spanish reina, and Italian regina all descend from the "
            "same Latin feminine form. English 'reign' and 'regina' are directly from Latin. "
            "Queen itself is from Germanic *kwenō (woman), an entirely different root."
        ),
        roots=["Latin regina (queen)", "Latin regere (to rule, direct)"],
        cognates=["English reign, regina (same Latin root)", "Spanish reina", "Italian regina"],
        semantic_shift="'female ruler' → queen",
    ),
    EtymologyEntry(
        language="fr", lemma="roi",
        origin_summary=(
            "From Latin rex/regis (king), from regere (to rule, to guide straight). "
            "The king as 'the one who rules/guides.' "
            "The same root gives English regal, royal, reign, and rector. "
            "Le Roi Soleil (The Sun King) was Louis XIV's self-chosen epithet."
        ),
        roots=["Latin rex/regis (king)", "Latin regere (to rule, guide)"],
        cognates=["English regal, royal, reign (same root)", "Spanish rey", "Italian re"],
        semantic_shift="'one who rules/guides' → king",
    ),
    EtymologyEntry(
        language="fr", lemma="temps",
        origin_summary=(
            "From Latin tempus/temporis (time, season, period), from PIE *tempos "
            "(stretch of time). French temps covers both 'time' and 'weather' — "
            "two meanings English splits between time and weather. "
            "Temporal, temporary, and contemporary all share this root. "
            "Quel temps fait-il? = What's the weather? Il n'a pas le temps = He has no time."
        ),
        roots=["Latin tempus/temporis (time, season)", "PIE *tempos (stretch of time)"],
        cognates=["English temporal, temporary, contemporary (same root)", "Spanish tiempo", "Italian tempo"],
        semantic_shift="'stretch of time' → time AND weather (two English words from one French word)",
    ),
    EtymologyEntry(
        language="fr", lemma="vrai",
        origin_summary=(
            "From Latin veracem (truthful, veracious), accusative of verax, "
            "from verus (true). The Vulgar Latin *veracus contracted to Old French "
            "verai → vrai. "
            "English very (truly, extremely) is borrowed from Old French verai — "
            "originally meaning 'truly' rather than 'extremely.'"
        ),
        roots=["Latin verus (true)", "Latin verax/veracem (truthful)"],
        cognates=["English very (originally 'truly'), verify, verdict (same root)", "Spanish verdadero"],
        semantic_shift="'truthful, genuine' → true, real (adjective)",
    ),

    # ── German (new entries) ──────────────────────────────────────────────────
    EtymologyEntry(
        language="de", lemma="Abenteuer",
        origin_summary=(
            "Borrowed from Old French aventure (adventure, chance event), from Latin "
            "adventura (things about to happen), from advenire (to arrive, befall). "
            "The word entered Middle High German as âventiure in the 12th century "
            "via courtly literature. German preserved the 'b' from the older French form."
        ),
        roots=["Latin advenire (to arrive, befall)", "Latin ad- + venire (to come)"],
        cognates=["English adventure (same source)", "French aventure", "Spanish aventura"],
        semantic_shift="'things about to arrive/befall' → exciting venture, adventure",
    ),
    EtymologyEntry(
        language="de", lemma="Abend",
        origin_summary=(
            "From Old High German âband (evening), from Proto-Germanic *ēbanþuz. "
            "Related to Old English æfen (evening — giving English even/evening). "
            "Abendland (Abend + Land) means 'the West' — the land of the evening "
            "sun, a poetic synonym for Western civilization."
        ),
        roots=["Proto-Germanic *ēbanþuz (evening)", "Old High German âband"],
        cognates=["English evening (same Proto-Germanic root)", "Dutch avond (evening)"],
        semantic_shift="'evening' → Abendland (the West, land of the setting sun)",
    ),
    EtymologyEntry(
        language="de", lemma="Anfang",
        origin_summary=(
            "Compound of an- (on, at) + Fang (catch, grasp), from fangen (to catch). "
            "The 'beginning' as the first moment of grasping/catching something. "
            "Anfänger (beginner) literally means 'one who is at the catch/beginning.' "
            "This concrete-to-abstract shift is typical of German word formation."
        ),
        roots=["Old High German ana- (on) + fāhan (to catch, seize)"],
        cognates=["English fang (same Proto-Germanic root)", "German fangen (to catch)"],
        semantic_shift="'the catching/grasping (at the start)' → beginning",
    ),
    EtymologyEntry(
        language="de", lemma="Arbeit",
        origin_summary=(
            "From Proto-Germanic *arbaidiz (toil, labor, hardship). "
            "The Proto-Slavic borrowing *orbota (giving Russian работа — work) "
            "confirms the early form. "
            "Originally meant hard, burdensome toil rather than neutral 'work.' "
            "The shift to neutral 'work' occurred over centuries."
        ),
        roots=["Proto-Germanic *arbaidiz (toil, hardship)", "PIE *orbh- (orphan, burden)"],
        cognates=["Russian работа (work — borrowed from Germanic)", "English orphan (distant PIE cognate)"],
        semantic_shift="'burdensome toil/hardship' → work (neutral sense)",
    ),
    EtymologyEntry(
        language="de", lemma="Berg",
        origin_summary=(
            "From Proto-Germanic *bergaz (mountain, hill, high place). "
            "The same root gives English borough and burg (fortified hilltop settlement), "
            "Norwegian berg, and the -berg in place names (Heidelberg, Pittsburgh). "
            "The PIE root *bhergh- (high) appears in Russian берег (bank/shore — a height)."
        ),
        roots=["Proto-Germanic *bergaz (mountain, hill)", "PIE *bhergh- (high, elevated)"],
        cognates=["English borough/burg (fortified height)", "Norwegian berg", "-berg in Heidelberg, Pittsburgh"],
        semantic_shift="'high place, mountain' → place names worldwide",
    ),
    EtymologyEntry(
        language="de", lemma="Blume",
        origin_summary=(
            "From Proto-Germanic *blōmô (flower, blossom), from PIE *bʰleh₃- "
            "(to bloom, blossom). The same root gives English bloom and blossom, "
            "Latin flos/floris (flower — flora, florist), and flour "
            "(the 'flower' of ground wheat, its finest part)."
        ),
        roots=["Proto-Germanic *blōmô (flower)", "PIE *bʰleh₃- (to bloom)"],
        cognates=["English bloom, blossom (same root)", "Latin flos (flower)", "English flour (the flower of grain)"],
    ),
    EtymologyEntry(
        language="de", lemma="Brot",
        origin_summary=(
            "From Proto-Germanic *braudą (bread, fermented bread), from *breuwan "
            "(to brew — to ferment). Bread as the fermented/leavened product. "
            "The same root gives English bread and brew. "
            "Pumpernickel (German dark bread) comes from a different origin — "
            "reputedly from pumpen (to fart) + Nickel (a devil), 'devil's fart.'"
        ),
        roots=["Proto-Germanic *braudą (fermented bread)", "Proto-Germanic *breuwan (to brew)"],
        cognates=["English bread, brew (same Proto-Germanic root)", "Dutch brood"],
        semantic_shift="'fermented/brewed product' → leavened bread",
    ),
    EtymologyEntry(
        language="de", lemma="Bruder",
        origin_summary=(
            "From Proto-Germanic *brōþēr (brother), from PIE *bʰréh₂tēr. "
            "One of the most universal IE cognate sets: Latin frater, Greek phrāter, "
            "Sanskrit bhrātṛ, English brother, Russian брат. "
            "Bruder is also used colloquially for 'guy, bro' in modern German slang."
        ),
        roots=["Proto-Germanic *brōþēr (brother)", "PIE *bʰréh₂tēr"],
        cognates=["English brother", "Latin frater", "Russian брат", "Sanskrit bhrātṛ"],
    ),
    EtymologyEntry(
        language="de", lemma="Dank",
        origin_summary=(
            "From Proto-Germanic *þankaz (thought, gratitude), from *þankjan (to think). "
            "Gratitude as 'a thought directed toward someone.' "
            "The same root gives English thank (to direct a thought of gratitude), "
            "and think (to form thoughts). "
            "Danke schön (thank you beautifully) pairs Dank with schön (beautiful)."
        ),
        roots=["Proto-Germanic *þankaz (thought, gratitude)", "PIE *tong- (to think)"],
        cognates=["English thank, think (same Proto-Germanic root)", "Dutch dank"],
        semantic_shift="'thought (directed at someone)' → gratitude, thanks",
    ),
    EtymologyEntry(
        language="de", lemma="Dorf",
        origin_summary=(
            "From Proto-Germanic *þurpą (village, hamlet), from PIE *trb- (settlement). "
            "The same root gives English thorp (an Old English village, surviving in "
            "place names like Scunthorpe, Mablethorpe), Dutch dorp, "
            "and the -trup/-drup in Scandinavian place names."
        ),
        roots=["Proto-Germanic *þurpą (village, hamlet)", "PIE *trb- (settlement)"],
        cognates=["English thorp (village — in place names like Scunthorpe)", "Dutch dorp", "Swedish torp"],
        semantic_shift="'hamlet, small settlement' → village",
    ),
    EtymologyEntry(
        language="de", lemma="Erde",
        origin_summary=(
            "From Proto-Germanic *erþō (earth, soil, ground), from PIE *h₁er- "
            "(earth). The same root gives English earth, Dutch aarde, "
            "and Swedish jord. Earth in all senses: soil, the planet, and "
            "the ground beneath one's feet."
        ),
        roots=["Proto-Germanic *erþō (earth, ground)", "PIE *h₁er- (earth)"],
        cognates=["English earth (same root)", "Dutch aarde", "Swedish jord"],
    ),
    EtymologyEntry(
        language="de", lemma="Erfahrung",
        origin_summary=(
            "Compound of er- (intensive prefix) + Fahrt (journey, ride), from "
            "fahren (to travel, drive, ride). Experience as 'traveling through' — "
            "living through events. The metaphor of experience as a journey "
            "is embedded in the etymology. Erfahren (to learn/find out) uses the same image."
        ),
        roots=["Old High German er- (through) + faran (to go, travel)"],
        cognates=["English fare (to travel, to do — same root)", "German fahren (to drive/travel)", "English wayfarer"],
        semantic_shift="'traveling through (something)' → experiencing → experience (noun)",
    ),
    EtymologyEntry(
        language="de", lemma="Fluss",
        origin_summary=(
            "From Proto-Germanic *flutuz (flow, stream), from *fleutan (to flow, float). "
            "The same root gives English fleet (a collection of floating vessels), "
            "float, and flow. "
            "Germany's major rivers (Rhine, Danube, Elbe) are all Flüsse. "
            "Flüssig (liquid, fluid) is the adjective form."
        ),
        roots=["Proto-Germanic *flutuz (flow)", "Proto-Germanic *fleutan (to flow, float)"],
        cognates=["English fleet, float, flow (same root)", "Dutch vloed (flood)", "English fluid (via Latin)"],
        semantic_shift="'flow, flowing' → river (the flowing body of water)",
    ),
    EtymologyEntry(
        language="de", lemma="Freude",
        origin_summary=(
            "From Proto-Germanic *frauðō (joy), related to froh (happy, glad) "
            "and ultimately to PIE *preh₁- (forward, beneficial). "
            "Beethoven's 'Ode an die Freude' (Ode to Joy) made this word iconic. "
            "Schadenfreude (damage-joy, pleasure at others' misfortune) is its darkest compound."
        ),
        roots=["Proto-Germanic *frauðō (joy)", "PIE *preh₁- (forward, favorable)"],
        cognates=["German froh (happy — same root)", "English free (same distant PIE root)", "Schadenfreude"],
        semantic_shift="'favorable feeling' → joy",
    ),
    EtymologyEntry(
        language="de", lemma="Frieden",
        origin_summary=(
            "From Proto-Germanic *friþuz (peace, friendship, freedom from hostility), "
            "from *frijaz (free, beloved). "
            "Peace as 'freedom from hostility' or 'the beloved state.' "
            "The same root gives English friend (one who is free/beloved), "
            "and the name Frederick (peaceful ruler)."
        ),
        roots=["Proto-Germanic *friþuz (peace)", "Proto-Germanic *frijaz (free, beloved)"],
        cognates=["English friend (same root)", "English free (same root)", "Frederick (peaceful ruler)"],
        semantic_shift="'freedom from hostility, beloved state' → peace",
    ),
    EtymologyEntry(
        language="de", lemma="Garten",
        origin_summary=(
            "From Proto-Germanic *gardaz (enclosure, yard), from PIE *gʰordʰo- "
            "(enclosure). The same root gives English yard (enclosed space), "
            "garden (borrowed from Old North French jardin of same Germanic source), "
            "and garth (an enclosed yard, in Northern English dialects)."
        ),
        roots=["Proto-Germanic *gardaz (enclosure)", "PIE *gʰordʰo- (enclosure)"],
        cognates=["English yard, garden (same Germanic root)", "Russian город (city — fortified enclosure)", "French jardin"],
        semantic_shift="'enclosed space' → cultivated garden",
    ),
    EtymologyEntry(
        language="de", lemma="Geld",
        origin_summary=(
            "From Old High German gelt (payment, tribute), from gelten (to be worth, "
            "to count as valid). Money as 'value, that which counts.' "
            "English guild shares this Germanic root (a guild collected geld — tribute). "
            "Danegeld (the tribute paid to the Vikings) is a famous historical compound."
        ),
        roots=["Proto-Germanic *geldą (payment, tribute)", "Proto-Germanic *geldan (to repay, be worth)"],
        cognates=["English guild, geld (tribute — historical)", "Dutch geld (money)", "English yield (same root)"],
        semantic_shift="'payment, that which counts as value' → money",
    ),
    EtymologyEntry(
        language="de", lemma="Geschichte",
        origin_summary=(
            "From geschehen (to happen, to occur), past participal noun: "
            "'what has happened.' History as 'the happened things.' "
            "The same formation appears in English history (from Greek historia — "
            "inquiry into what happened). "
            "Geschichtsbuch (history book) combines Geschichte with Buch (book)."
        ),
        roots=["Middle High German geschehen (to happen)", "Proto-Germanic *skehaną (to happen)"],
        cognates=["German geschehen (to happen)", "Dutch geschiedenis (history — same formation)"],
        semantic_shift="'what has happened' → history, story",
    ),
    EtymologyEntry(
        language="de", lemma="Glaube",
        origin_summary=(
            "From Proto-Germanic *galaubô (belief, trust), from *galaubjan "
            "(to believe, to hold dear). Belief as 'holding dear' — "
            "to believe is to value something as true. "
            "The same root gives English believe and love (both from *leubh- — to love, desire)."
        ),
        roots=["Proto-Germanic *galaubô (belief)", "Proto-Germanic *leubh- (to love, hold dear)"],
        cognates=["English believe, love (same distant root)", "Dutch geloof (belief)"],
        semantic_shift="'holding dear, valuing' → belief, faith",
    ),
    EtymologyEntry(
        language="de", lemma="Glück",
        origin_summary=(
            "From Middle High German gelücke (luck, fortune, fate), from Middle Low "
            "German. German Glück uniquely covers both 'luck' (Zufälligkeit) and "
            "'happiness' (Freude) — two concepts English keeps separate. "
            "The philosophical question 'Was ist Glück?' asks about both luck and happiness."
        ),
        roots=["Middle Low German gelücke (luck, fortune)"],
        cognates=["Dutch geluk (luck/happiness — same dual meaning)", "English luck (borrowed from Low German)"],
        semantic_shift="'fortune, fate' → both luck and happiness (two English concepts in one German word)",
    ),
    EtymologyEntry(
        language="de", lemma="Hand",
        origin_summary=(
            "From Proto-Germanic *handuz (hand), of uncertain ultimate PIE origin. "
            "The same root gives English hand, Dutch hand, Swedish hand. "
            "Handel (trading — handling goods) and Handwerk (handicraft — hand-work) "
            "show how central the hand was to commerce and craft. "
            "Händel the composer's name means 'trader.'"
        ),
        roots=["Proto-Germanic *handuz (hand)"],
        cognates=["English hand (same root)", "Dutch hand", "German Händel (trade), Handwerk (craft)"],
        semantic_shift="'hand' → handel (trade — handling), Handwerk (craft — hand-work)",
    ),
    EtymologyEntry(
        language="de", lemma="Heimat",
        origin_summary=(
            "From Old High German heima (home, dwelling place) + -ōt (abstract noun suffix). "
            "Heimat goes beyond 'home' — it is the deep emotional attachment to a specific "
            "place of origin. The concept of Heimatlosigkeit (homelessness) and "
            "Heimweh (homesickness) show the word's cultural weight in German thought."
        ),
        roots=["Old High German heima (home)", "Proto-Germanic *haimaz (home, village)"],
        cognates=["English home (same root)", "German Heim (home), Heimweh (homesickness)"],
        semantic_shift="'dwelling place' → deep emotional attachment to a place of origin",
    ),
    EtymologyEntry(
        language="de", lemma="Held",
        origin_summary=(
            "From Middle High German helt (hero), from Proto-Germanic *halþaz "
            "(one who holds, supports). A hero as 'one who holds firm.' "
            "The name Harold (Old English Hereweald) and similar names share "
            "the Germanic hero-root. Heldin is the feminine form."
        ),
        roots=["Middle High German helt (hero)", "Proto-Germanic *halþaz (one who holds)"],
        cognates=["English hero (from Greek, not related)", "German halten (to hold — same root)"],
        semantic_shift="'one who holds/stands firm' → hero",
    ),
    EtymologyEntry(
        language="de", lemma="Herz",
        origin_summary=(
            "From Proto-Germanic *hertô (heart), from PIE *ḱḗrd. "
            "One of the clearest pan-IE etymologies: Latin cor/cordis (heart — "
            "cordial, accord, courage), Greek kardia (cardiac), English heart, "
            "Sanskrit hṛd. The heart as both organ and emotional center. "
            "Herzlich (heartfelt) is a common German greeting."
        ),
        roots=["Proto-Germanic *hertô (heart)", "PIE *ḱḗrd (heart)"],
        cognates=["English heart, cordial (Latin cor)", "Greek cardiac (kardia)", "Sanskrit hṛd"],
    ),
    EtymologyEntry(
        language="de", lemma="Himmel",
        origin_summary=(
            "From Proto-Germanic *himinaz (sky, heaven), of uncertain PIE origin. "
            "German Himmel covers both the physical sky and the theological heaven — "
            "two concepts English distinguishes with separate words. "
            "Himmelfahrt (Ascension) literally means 'heaven-journey.' "
            "Um Himmels willen! (for heaven's sake!) uses the theological sense."
        ),
        roots=["Proto-Germanic *himinaz (sky/heaven)"],
        cognates=["English heaven (same Proto-Germanic root)", "Dutch hemel (sky/heaven — same dual meaning)"],
        semantic_shift="'sky/heavenly vault' → physical sky AND theological heaven in one word",
    ),
    EtymologyEntry(
        language="de", lemma="Jahr",
        origin_summary=(
            "From Proto-Germanic *jēram (year), from PIE *yeh₁-ro- (year, season). "
            "The same root gives English year, Gothic jer, and possibly Greek hora "
            "(season, hour — a division of the year). "
            "Jahrhundert (century) is literally 'year-hundred.' Jahrmarkt (annual fair) "
            "is 'year-market.'"
        ),
        roots=["Proto-Germanic *jēram (year)", "PIE *yeh₁-ro- (year, going)"],
        cognates=["English year (same root)", "Greek hora (season/hour — possible cognate)"],
        semantic_shift="'the going/turning (of seasons)' → year",
    ),
    EtymologyEntry(
        language="de", lemma="Kind",
        origin_summary=(
            "From Proto-Germanic *kindą (birth, offspring, kin), from *kunjam "
            "(family, generation, kind). A child as 'the born one' or 'the kin.' "
            "English kind (type, sort) and kin are from the same root. "
            "Kindheit (childhood) combines Kind with -heit (abstract noun suffix)."
        ),
        roots=["Proto-Germanic *kindą (offspring)", "Proto-Germanic *kunjam (family, generation)"],
        cognates=["English kin, kind (type/sort — same root)", "English kindergarten (borrowed from German)"],
        semantic_shift="'offspring, born one' → child",
    ),
    EtymologyEntry(
        language="de", lemma="Kirche",
        origin_summary=(
            "From Old High German kirihha, from Byzantine Greek kyrikon (of the Lord, "
            "the Lord's house), from kyrios (Lord). "
            "The same Greek source gives English church and Scottish kirk. "
            "The word spread via early Christian missionaries who brought both the "
            "faith and the Greek terminology northward."
        ),
        roots=["Byzantine Greek kyrikon (of the Lord)", "Greek kyrios (Lord, master)"],
        cognates=["English church (same Greek source)", "Scottish kirk (same source)", "Dutch kerk"],
        semantic_shift="'the Lord's (house)' → the church building → the institution",
    ),
    EtymologyEntry(
        language="de", lemma="Kraft",
        origin_summary=(
            "From Proto-Germanic *kraftuz (strength, power, capacity). "
            "The same root gives Dutch kracht and Swedish kraft. "
            "Kraftfahrzeug (motor vehicle) literally means 'power-drive-thing' — "
            "the German compound for car. Kraftwerk (power plant) is 'strength-work.'"
        ),
        roots=["Proto-Germanic *kraftuz (strength, power)"],
        cognates=["Dutch kracht (strength)", "Swedish kraft (strength)", "German Kraftfahrzeug (motor vehicle)"],
        semantic_shift="'strength, capacity' → power (physical and figurative)",
    ),
    EtymologyEntry(
        language="de", lemma="Krieg",
        origin_summary=(
            "From Middle High German kriec (quarrel, fight, effort, war), "
            "from Old High German chreg (stubbornness, persistence). "
            "War as sustained, persistent struggle. "
            "The word replaced the older Fehde (feud) for large-scale armed conflict. "
            "Kriegspiel (war game) entered English as a board/wargame term."
        ),
        roots=["Old High German chreg (stubbornness, persistence)", "Proto-Germanic *kregaz"],
        cognates=["English kriegspiel (borrowed for wargame)", "Dutch krijg (war — same root)"],
        semantic_shift="'stubborn persistence, quarrel' → war",
    ),
    EtymologyEntry(
        language="de", lemma="Land",
        origin_summary=(
            "From Proto-Germanic *landą (land, territory, country). "
            "The same root gives English land, Dutch land, and the -land in "
            "country names (England, Ireland, Iceland, Deutschland). "
            "Deutschland itself means 'land of the people' (Deutsch + Land)."
        ),
        roots=["Proto-Germanic *landą (land, territory)"],
        cognates=["English land (same root)", "England (Angle-land), Ireland, Iceland", "Dutch land"],
    ),
    EtymologyEntry(
        language="de", lemma="Leben",
        origin_summary=(
            "From Proto-Germanic *libāną (to live, to remain, to be left). "
            "The same root gives English live/life and leave (to remain behind — "
            "the living remain). "
            "Lebensraum (living space) was the geopolitical concept of Nazi Germany. "
            "Lebenslauf (CV/résumé) is literally 'life-run.'"
        ),
        roots=["Proto-Germanic *libāną (to live, remain)"],
        cognates=["English live, life, leave (remain — same root)", "Dutch leven (life)", "Lebensraum"],
        semantic_shift="'to remain, to be left alive' → to live → life (noun)",
    ),
    EtymologyEntry(
        language="de", lemma="Licht",
        origin_summary=(
            "From Proto-Germanic *leuhtą (light, brightness), from PIE *lewk- (light, "
            "brightness). The same root gives Latin lux (light — luxury was originally "
            "associated with light), English light, and Greek leukos (white — leukemia). "
            "Lichtblick (a gleam of light) means a ray of hope."
        ),
        roots=["Proto-Germanic *leuhtą (light)", "PIE *lewk- (light, brightness)"],
        cognates=["English light, luminous", "Latin lux (light)", "Greek leukos (white — leukemia)"],
    ),
    EtymologyEntry(
        language="de", lemma="Liebe",
        origin_summary=(
            "From Proto-Germanic *liubō (love, what is dear), from *leubh- "
            "(to love, desire, be pleased with). The same root gives English "
            "love, believe (hold dear), and Latin lubet/libet (it pleases). "
            "Liebesbrief (love letter) and Liebling (darling — the beloved one) "
            "show the word's productive derivatives."
        ),
        roots=["Proto-Germanic *liubō (love)", "PIE *lewbʰ- (to love, desire)"],
        cognates=["English love, believe (same root)", "Latin lubet (it pleases)", "Russian любить"],
        semantic_shift="'what is dear/desired' → love",
    ),
    EtymologyEntry(
        language="de", lemma="Mann",
        origin_summary=(
            "From Proto-Germanic *mannaz (human being, person), from PIE *mon-. "
            "Originally gender-neutral (a human), it narrowed to mean adult male. "
            "The English man underwent the same narrowing. "
            "Mankind (Menschheit in German) and German Mensch (person — retained "
            "the neutral sense) preserve the older meaning."
        ),
        roots=["Proto-Germanic *mannaz (human being)", "PIE *mon- (person)"],
        cognates=["English man (same narrowing from 'person' to 'male')", "Dutch man", "Gothic manna"],
        semantic_shift="'human being (gender-neutral)' → adult male",
    ),
    EtymologyEntry(
        language="de", lemma="Meer",
        origin_summary=(
            "From Proto-Germanic *mari- (sea, lake, body of water), from PIE *móri. "
            "The same root gives English mere (a lake — in Northern dialects), "
            "Latin mare (sea — maritime, submarine, Mediterranean), "
            "and French mer. The German Nordsee and Ostsee use See (lake/sea) — "
            "Meer is for the open ocean."
        ),
        roots=["Proto-Germanic *mari- (sea, lake)", "PIE *móri (body of water)"],
        cognates=["English mere (lake)", "Latin mare (sea — maritime)", "French mer", "Russian море"],
        semantic_shift="'body of water' → the open sea/ocean",
    ),
    EtymologyEntry(
        language="de", lemma="Mensch",
        origin_summary=(
            "From Middle High German mennisch/mennisch (human, human-like), "
            "from Mann (human being) + -isch (adjectival suffix) → nominalized. "
            "While Mann narrowed to 'adult male,' Mensch retained the gender-neutral "
            "sense of 'human being.' In Yiddish (mensch), it means a good, decent person."
        ),
        roots=["Middle High German mennisch (human)", "Old High German mannisco (human being)"],
        cognates=["English man (same root, but narrowed)", "Yiddish mensch (a decent person)", "Dutch mens"],
        semantic_shift="'human-like, of mankind' → person, human being (retained neutral sense)",
    ),
    EtymologyEntry(
        language="de", lemma="Mutter",
        origin_summary=(
            "From Proto-Germanic *mōþēr (mother), from PIE *méh₂tēr. "
            "One of the most stable and universal IE words: Latin mater, "
            "Greek mētēr, English mother, Russian мать, Sanskrit mātṛ. "
            "Muttersprache (mother tongue) is the German word for native language."
        ),
        roots=["Proto-Germanic *mōþēr (mother)", "PIE *méh₂tēr"],
        cognates=["English mother", "Latin mater", "Russian мать", "Greek mētēr", "Muttersprache (mother tongue)"],
    ),
    EtymologyEntry(
        language="de", lemma="Nacht",
        origin_summary=(
            "From Proto-Germanic *nahtō (night), from PIE *nókʷts. "
            "One of the clearest pan-IE words: Latin nox/noctis (night — nocturnal), "
            "Greek nyx, English night, French nuit, Russian ночь. "
            "Nachtigall (nightingale) literally means 'night singer.'"
        ),
        roots=["Proto-Germanic *nahtō (night)", "PIE *nókʷts (night)"],
        cognates=["English night (same root)", "Latin nox (nocturnal)", "French nuit", "Russian ночь"],
        semantic_shift="'night' → Nachtigall (nightingale — night-singer)",
    ),
    EtymologyEntry(
        language="de", lemma="Name",
        origin_summary=(
            "From Proto-Germanic *namô (name), from PIE *h₁nómn̥. "
            "One of the clearest pan-IE word families: Latin nomen (nominal, noun), "
            "Greek onoma (anonymous, pseudonym), English name, Russian имя, "
            "Sanskrit nāman. All are cognates — naming as a universal human act."
        ),
        roots=["Proto-Germanic *namô (name)", "PIE *h₁nómn̥ (name)"],
        cognates=["English name (same root)", "Latin nomen (nominal)", "Greek onoma (anonymous)", "Russian имя"],
    ),
    EtymologyEntry(
        language="de", lemma="Natur",
        origin_summary=(
            "From Latin natura (birth, the natural order), borrowed early into German. "
            "One of many Latin abstractions that entered German through church, "
            "scholarship, and law. "
            "Naturwissenschaft (natural science) contrasts with Geisteswissenschaft "
            "(humanities — science of the spirit)."
        ),
        roots=["Latin natura (nature, birth)", "Latin nasci (to be born)"],
        cognates=["English nature, natural (same source)", "Spanish naturaleza", "French nature"],
        semantic_shift="'the born order of things' → nature → natural science",
    ),
    EtymologyEntry(
        language="de", lemma="Recht",
        origin_summary=(
            "From Proto-Germanic *rehtaz (straight, direct, right), from PIE *h₃reǵ- "
            "(to straighten, rule). Law as 'the straight line' of justice. "
            "The same root gives English right, Latin rectus (straight — rector, "
            "correct), and Sanskrit rāja (king — one who straightens/rules). "
            "Rechtsanwalt (lawyer) literally means 'legal power-of-attorney.'"
        ),
        roots=["Proto-Germanic *rehtaz (straight, right)", "PIE *h₃reǵ- (to straighten)"],
        cognates=["English right (same root)", "Latin rectus (straight)", "Sanskrit rāja (king — ruler/straightener)"],
        semantic_shift="'straight, direct' → correct → law/right (the straight path of justice)",
    ),
    EtymologyEntry(
        language="de", lemma="Reise",
        origin_summary=(
            "From Old Saxon rēsa (rising, departure, journey), from *rīsan "
            "(to rise, set out). A journey as 'a rising up and setting out.' "
            "The same root gives English rise and raise. "
            "Reisepass (passport) literally means 'journey-pass.' "
            "Reisefieber (travel excitement) is 'journey-fever.'"
        ),
        roots=["Old Saxon rēsa (rising, departure)", "Proto-Germanic *rīsan (to rise)"],
        cognates=["English rise, raise (same root)", "German aufstehen (to rise — related concept)"],
        semantic_shift="'rising up, departure' → journey, trip",
    ),
    EtymologyEntry(
        language="de", lemma="Seele",
        origin_summary=(
            "From Proto-Germanic *saiwalō (soul), possibly from *saiwa- (sea, lake). "
            "One theory: souls were believed to come from and return to the sea. "
            "Another: the soul as 'the belonging to the sea of the dead.' "
            "Seelsorge (pastoral care) literally means 'soul-care.' "
            "Seelenruhe (peace of mind) is 'soul-calm.'"
        ),
        roots=["Proto-Germanic *saiwalō (soul)", "Possibly *saiwa- (sea — abode of souls)"],
        cognates=["English soul (same Proto-Germanic root)", "Dutch ziel (soul)"],
        semantic_shift="'that which belongs to the (sea of the) dead' → soul, psyche",
    ),
    EtymologyEntry(
        language="de", lemma="Sinn",
        origin_summary=(
            "From Proto-Germanic *sinnaz (journey, direction, sense, mind). "
            "Sinn originally meant 'the direction one's mind travels.' "
            "It now covers 'sense' (direction of thought), 'meaning,' and 'mind.' "
            "Sinnlos (senseless/meaningless) and Unsinn (nonsense) are key derivatives. "
            "Lebenssinn (meaning of life) shows its philosophical weight."
        ),
        roots=["Proto-Germanic *sinnaz (journey, direction, sense)"],
        cognates=["English sin (to miss the mark — different root)", "German sinnen (to ponder, reflect)"],
        semantic_shift="'direction of travel/thought' → sense, meaning, mind",
    ),
    EtymologyEntry(
        language="de", lemma="Sprache",
        origin_summary=(
            "From sprechen (to speak), from Proto-Germanic *sprekanan (to speak). "
            "The nominalized infinitive/verbal noun: 'the speaking.' "
            "The same root gives English speak and speech. "
            "Sprachgefühl (language instinct/feeling) and Sprachgrenze (language boundary) "
            "show its cultural importance."
        ),
        roots=["Proto-Germanic *sprekanan (to speak)"],
        cognates=["English speak, speech (same root)", "Dutch spreken (to speak)", "Sprachgefühl (borrowed)"],
        semantic_shift="'the speaking' → language system",
    ),
    EtymologyEntry(
        language="de", lemma="Stadt",
        origin_summary=(
            "From Proto-Germanic *stadiz (place, standing point, site), from *standan "
            "(to stand). A city as 'a place where things stand/settle.' "
            "The same root gives Englishstead (place — in homestead, instead) "
            "and German stehen (to stand). "
            "Stadtrat (city council) and Stadtplan (city map) are productive compounds."
        ),
        roots=["Proto-Germanic *stadiz (place, standing point)", "Proto-Germanic *standan (to stand)"],
        cognates=["English stead (place — homestead, instead)", "English stand (same root)", "Dutch stad"],
        semantic_shift="'standing place, settled site' → town, city",
    ),
    EtymologyEntry(
        language="de", lemma="Stern",
        origin_summary=(
            "From Proto-Germanic *sternō (star), from PIE *h₂stḗr (star). "
            "The pan-IE star word: Latin stella (star — stellar, constellation), "
            "Greek astēr (star — astronomy, asterisk), English star, "
            "Sanskrit star, Armenian astɫ. "
            "Sternstunde (shining hour) is German for a 'golden moment.'"
        ),
        roots=["Proto-Germanic *sternō (star)", "PIE *h₂stḗr (star)"],
        cognates=["English star (same root)", "Latin stella (stellar)", "Greek astēr (astronomy)", "Sanskrit tāra"],
    ),
    EtymologyEntry(
        language="de", lemma="Stille",
        origin_summary=(
            "From still (quiet, motionless), from Proto-Germanic *stillaz "
            "(standing still, motionless). Silence as a state of stillness. "
            "The same root gives English still (motionless, yet, a distillery). "
            "Stille Nacht (Silent Night) is the Christmas carol. "
            "Die Stille vor dem Sturm (the calm before the storm) is a key idiom."
        ),
        roots=["Proto-Germanic *stillaz (standing still, motionless)"],
        cognates=["English still (same root — all senses)", "Dutch stil (quiet)", "Stille Nacht (Silent Night)"],
        semantic_shift="'standing motionless' → quiet, still → silence (noun)",
    ),
    EtymologyEntry(
        language="de", lemma="Straße",
        origin_summary=(
            "From Latin strata (via) (paved/layered road), from sternere (to spread, "
            "lay flat). A Roman road as a 'spread-out, layered surface.' "
            "The same Latin root gives English street, stratum, and prostrate. "
            "Straßenbahnhof (tram station) combines Straße, Bahn (track), and Hof (yard)."
        ),
        roots=["Latin strata (via) (paved road)", "Latin sternere (to spread, lay flat)"],
        cognates=["English street (same Latin root)", "English stratum (layer — same root)", "Dutch straat"],
        semantic_shift="'paved/layered Roman road surface' → street, road",
    ),
    EtymologyEntry(
        language="de", lemma="Tag",
        origin_summary=(
            "From Proto-Germanic *dagaz (day), from PIE *dʰegʷʰ- (to burn) — "
            "the day as 'the burning time.' The same root gives English day and "
            "Gothic dags. Tageslicht (daylight) and Tageszeitung (daily newspaper) "
            "show its productiveness. Guten Tag is the standard German daytime greeting."
        ),
        roots=["Proto-Germanic *dagaz (day)", "PIE *dʰegʷʰ- (to burn — the burning daylight)"],
        cognates=["English day (same root)", "Gothic dags", "Dutch dag"],
        semantic_shift="'the burning/bright time' → day",
    ),
    EtymologyEntry(
        language="de", lemma="Tod",
        origin_summary=(
            "From Proto-Germanic *dauþuz (death), from *dauþijaz (dead, dying). "
            "The same root gives English death and dead. "
            "Todesstrafe (death penalty) and Todesangst (mortal fear) are key compounds. "
            "Tod und Teufel (death and devil) is a common intensifying pair."
        ),
        roots=["Proto-Germanic *dauþuz (death)", "PIE *dhewbh- (to be stunned/overwhelmed)"],
        cognates=["English death, dead (same root)", "Dutch dood", "Norse dauði"],
        semantic_shift="'the dying, the overwhelming' → death",
    ),
    EtymologyEntry(
        language="de", lemma="Traum",
        origin_summary=(
            "From Proto-Germanic *draugmaz (phantom, illusion, dream), from *draugaz "
            "(a ghost, deceptive appearance). A dream as a 'phantom of the night.' "
            "The same root gives English dream (via Old English drēam — joy, music first, "
            "then dream). "
            "Traumhaft (dreamlike) and Traumfrau (dream woman) show its positive use."
        ),
        roots=["Proto-Germanic *draugmaz (phantom, illusion)", "Proto-Germanic *draugaz (ghost, deceptive appearance)"],
        cognates=["English dream (same root — originally meant 'joy/music')", "Dutch droom"],
        semantic_shift="'nighttime phantom/illusion' → dream → ideal (Traumfrau = dream woman)",
    ),
    EtymologyEntry(
        language="de", lemma="Tür",
        origin_summary=(
            "From Proto-Germanic *durz (door, gate), from PIE *dʰwer- (door, doorway). "
            "One of the pan-IE architectural words: Latin foris (door — foreign, "
            "the one outside), Greek thyra (door — thyroid — door-shaped), "
            "English door, Sanskrit dvāra. "
            "Türhüter (doorkeeper) and Türklinke (door handle) are common compounds."
        ),
        roots=["Proto-Germanic *durz (door)", "PIE *dʰwer- (door, doorway)"],
        cognates=["English door (same root)", "Latin foris (outside — foreign)", "Greek thyra (thyroid)"],
        semantic_shift="'doorway' → door",
    ),
    EtymologyEntry(
        language="de", lemma="Volk",
        origin_summary=(
            "From Proto-Germanic *fulką (people, host, multitude), from PIE *plk-. "
            "The same root gives English folk (people — folklore, folk music) "
            "and Swedish folk. "
            "Volkswagen (people's car) and Volkslied (folk song) show its compounds. "
            "The political use of Volk (das deutsche Volk) gave it complex historical associations."
        ),
        roots=["Proto-Germanic *fulką (people, host)", "PIE *plk- (multitude)"],
        cognates=["English folk (same root)", "Swedish folk", "Volkswagen (people's car)"],
        semantic_shift="'multitude, host of people' → the people, the folk, the nation",
    ),
    EtymologyEntry(
        language="de", lemma="Wasser",
        origin_summary=(
            "From Proto-Germanic *watōr (water), from PIE *wódr̥. "
            "The pan-IE water word: English water, Greek hydor (hydrogen, hydro-), "
            "Russian вода. "
            "Wasserfall (waterfall), Wasserwerk (waterworks), and Wasserspiegel "
            "(water level/surface) show its productivity. "
            "Wasser predates the German language itself."
        ),
        roots=["Proto-Germanic *watōr (water)", "PIE *wódr̥ (water)"],
        cognates=["English water (same root)", "Greek hydor (hydrogen)", "Russian вода (water)"],
    ),
    EtymologyEntry(
        language="de", lemma="Weg",
        origin_summary=(
            "From Proto-Germanic *wegaz (way, path, road), from PIE *weǵʰ- "
            "(to go, carry, transport). The same root gives English way, "
            "Latin via (road — viable, deviate), and wagon. "
            "Wegweiser (signpost) is literally 'way-pointer.' "
            "Unterwegs (underway, on the road) is a key adverb."
        ),
        roots=["Proto-Germanic *wegaz (way, path)", "PIE *weǵʰ- (to go, transport)"],
        cognates=["English way, wagon (same root)", "Latin via (road)", "Dutch weg (way/road)"],
        semantic_shift="'path of transport/going' → way, road, path",
    ),
    EtymologyEntry(
        language="de", lemma="Welt",
        origin_summary=(
            "From Proto-Germanic *wer-ald (age of man), from *wer (man) + *aldaz "
            "(age, era). The world as 'the era/age of mankind.' "
            "The same compound gives English world. "
            "Weltanschauung, Weltschmerz, and Weltreise show German's preference "
            "for Welt- compounds when discussing global or cosmic matters."
        ),
        roots=["Proto-Germanic *wer (man) + *aldaz (age, era)"],
        cognates=["English world (same compound)", "Weltanschauung, Weltschmerz (borrowed into English)"],
        semantic_shift="'age of man' → the inhabited world → the universe/cosmos",
    ),
    EtymologyEntry(
        language="de", lemma="Wind",
        origin_summary=(
            "From Proto-Germanic *windaz (wind), from PIE *h₂wéh₁nts (blowing). "
            "The same root gives English wind, Latin ventus (wind — ventilate, vent), "
            "and Sanskrit vāta. "
            "Windmühle (windmill) and Windjammer (windjammer ship) are productive compounds. "
            "Wind is one of the oldest weather words in IE."
        ),
        roots=["Proto-Germanic *windaz (wind)", "PIE *h₂wéh₁nts (blowing)"],
        cognates=["English wind (same root)", "Latin ventus (wind — ventilate)", "Sanskrit vāta"],
    ),
    EtymologyEntry(
        language="de", lemma="Wort",
        origin_summary=(
            "From Proto-Germanic *wurdą (word, spoken thing), from PIE *werd- "
            "(to speak). The same root gives English word, Latin verbum "
            "(word — verbal, verb), and Gothic waurd. "
            "Wortspiel (word game, pun) and Wörterbuch (dictionary — word-book) "
            "show its productivity."
        ),
        roots=["Proto-Germanic *wurdą (word)", "PIE *werd- (to speak)"],
        cognates=["English word (same root)", "Latin verbum (verbal, verb)", "Wörterbuch (dictionary — word-book)"],
    ),
    EtymologyEntry(
        language="de", lemma="Zuhause",
        origin_summary=(
            "Compound of zu (at, to) + Hause (dative of Haus, house). "
            "Literally 'at the house' — but used for the warm concept of home. "
            "Zuhause as a noun captures 'home' as a place of belonging, "
            "distinct from the mere building (Haus). "
            "Kein Zuhause haben (to have no home) expresses homelessness."
        ),
        roots=["Old High German zu (at, toward) + Haus (house — from Proto-Germanic *hūsą)"],
        cognates=["English at home (same conceptual compound)", "English house (same root as Haus)"],
        semantic_shift="'at the house' → the concept of home as belonging",
    ),
    EtymologyEntry(
        language="de", lemma="Bürger",
        origin_summary=(
            "From Burg (fortified town, castle), from Proto-Germanic *burgz. "
            "A Bürger is a 'town-dweller' — a citizen of a Burg. "
            "English borough and burg share the same root. "
            "Bürger became the German equivalent of French bourgeois "
            "(also from 'burg/bourg'). Bürgertum (bourgeoisie/middle class) derives from it."
        ),
        roots=["Proto-Germanic *burgz (fortified settlement)", "Old High German burg (fortress)"],
        cognates=["English borough, burg (same root)", "French bourgeois (same concept)", "Dutch burger"],
        semantic_shift="'inhabitant of a fortified town' → citizen → bourgeois/middle class",
    ),
    EtymologyEntry(
        language="de", lemma="Gemütlichkeit",
        origin_summary=(
            "From Gemüt (disposition, mind, soul, heart) + -lich (adjectival suffix) "
            "+ -keit (abstract noun suffix). Gemüt itself combines ge- (collective) "
            "+ Mut (courage, mood). "
            "Gemütlichkeit is the quality of warm, cozy, relaxed sociability — "
            "the feeling of a comfortable gathering. Untranslatable into a single English word."
        ),
        roots=["Old High German gi-muot (mind, disposition)", "Proto-Germanic *mōdaz (mind, courage, mood)"],
        cognates=["English mood, mood (same Proto-Germanic root)", "German Mut (courage — same root)"],
        semantic_shift="'disposition of the soul' → comfortable, warm sociability and coziness",
    ),
    EtymologyEntry(
        language="de", lemma="Gesellschaft",
        origin_summary=(
            "From Geselle (companion, journeyman — one who shares a Saal/hall) "
            "+ -schaft (fellowship suffix, from Proto-Germanic *-skapją). "
            "A Gesellschaft is literally 'fellowship of companions.' "
            "In sociology (Tönnies 1887), Gesellschaft (society, contractual) "
            "contrasts with Gemeinschaft (community, organic)."
        ),
        roots=["Middle High German geselle (companion, hall-sharer)", "Proto-Germanic *-skapją (state, condition)"],
        cognates=["English fellowship, friendship (-ship same root)", "German Gemeinschaft (community — contrast)"],
        semantic_shift="'hall-fellowship, companions' → society, company, association",
    ),
    EtymologyEntry(
        language="de", lemma="Gesundheit",
        origin_summary=(
            "From gesund (healthy) + -heit (abstract noun suffix). "
            "Gesund comes from Old High German gisunt (unharmed, healthy). "
            "Gesundheit is said after someone sneezes — wishing them health. "
            "In English-speaking contexts, Gesundheit is used as a borrowing "
            "alongside 'bless you.'"
        ),
        roots=["Old High German gisunt (unharmed, whole, healthy)", "Proto-Germanic *swnþaz (healthy)"],
        cognates=["English sound (healthy — 'sound body'), sanity (Latin cognate)"],
        semantic_shift="'unharmed, whole' → healthy → health (noun) → bless you (after sneezing)",
    ),
    EtymologyEntry(
        language="de", lemma="Kaputt",
        origin_summary=(
            "From French capot (having won no tricks at cards — completely defeated), "
            "from Dutch kapotas or Italian cappotto (overcoat — 'capped'). "
            "A losing player at the card game piquet was 'capot' (cloaked, defeated). "
            "German borrowed it as kaputt (broken, done for) in the 17th century, "
            "and English uses it as a loanword from German."
        ),
        roots=["French capot (losing all card tricks)", "Italian cappotto (overcoat, defeat in cards)"],
        cognates=["English kaput (borrowed from German)", "French capot (card defeat)"],
        semantic_shift="'defeated at cards (winning no tricks)' → broken, done for, exhausted",
    ),
    EtymologyEntry(
        language="de", lemma="Kitsch",
        origin_summary=(
            "Possibly from dialect kitschen (to scrape street mud) or from "
            "verkitschen (to sell cheaply, palm off). "
            "The term emerged in the Munich art market c. 1870 for cheap, "
            "sentimental art made for quick sale. "
            "Hermann Broch's essay 'Notes on the Problem of Kitsch' (1950) "
            "made it an international aesthetic concept."
        ),
        roots=["Possibly German dialect kitschen (to scrape mud) or verkitschen (to sell cheap)"],
        cognates=["English kitsch (borrowed)", "French kitsch (borrowed)"],
        semantic_shift="'cheap street art/mud-scraping' → sentimentally bad taste in art → aesthetic category",
    ),
    EtymologyEntry(
        language="de", lemma="Lied",
        origin_summary=(
            "From Proto-Germanic *liuþam (song, poem, lyric), from PIE *lewdʰ- "
            "(to sing). German Lied specifically refers to art song for voice and piano — "
            "especially the Romantic era (Schubert, Schumann, Brahms, Wolf). "
            "Volkslied (folk song) and Kunstlied (art song) are the key types."
        ),
        roots=["Proto-Germanic *liuþam (song, lyric)", "PIE *lewdʰ- (to sing)"],
        cognates=["English laud (to praise — same PIE root via Latin)", "Dutch lied (song)"],
        semantic_shift="'lyric/song' → specifically the German Romantic art song genre",
    ),
    EtymologyEntry(
        language="de", lemma="Mitleid",
        origin_summary=(
            "Compound of mit (with) + Leid (suffering, grief). "
            "Literally 'co-suffering' — experiencing another's pain alongside them. "
            "This is the German word for compassion/pity, etymologically identical "
            "to the Greek com-passio (suffering with). "
            "Nietzsche criticized Mitleid as a weakness; Schopenhauer praised it as the basis of morality."
        ),
        roots=["Old High German mit (with) + Proto-Germanic *laiþaz (suffering, harm)"],
        cognates=["English loath, loathe (same root as Leid)", "English compassion (Latin: com + passio = with + suffering)"],
        semantic_shift="'co-suffering' → compassion, pity",
    ),
    EtymologyEntry(
        language="de", lemma="Ordnung",
        origin_summary=(
            "From ordnen (to arrange, order), from Latin ordinare (to put in order). "
            "One of the Latin loanwords that entered German through church and administration. "
            "Ordnung muss sein (there must be order) is a stereotypically German sentiment. "
            "Ordnungsamt (public order office) enforces local ordinances."
        ),
        roots=["Latin ordinare (to put in order)", "Latin ordo/ordinis (order, rank)"],
        cognates=["English order, orderly, ordinary (same Latin root)", "German ordentlich (orderly, proper)"],
        semantic_shift="'putting in a rank/order' → orderliness, regulatory order",
    ),
    EtymologyEntry(
        language="de", lemma="Pflicht",
        origin_summary=(
            "From Proto-Germanic *plugtiz (obligation, pledge, duty), from *plugjan "
            "(to pledge). The same root gives English plight (a sworn obligation, "
            "as in 'I plight thee my troth'). "
            "Pflicht und Neigung (duty and inclination) is Kant's famous moral opposition. "
            "Pflichtgefühl (sense of duty) is a key cultural value."
        ),
        roots=["Proto-Germanic *plugtiz (obligation, pledge)", "PIE *pleǵ- (to pledge)"],
        cognates=["English plight (obligation — archaic, 'plight one's troth')", "Dutch plicht (duty)"],
        semantic_shift="'pledge, sworn obligation' → duty",
    ),
    EtymologyEntry(
        language="de", lemma="Sehnsucht",
        origin_summary=(
            "Compound of Sehnen (longing, yearning — from sinew/tendon: the pull of longing) "
            "+ Sucht (craving, compulsion — from siechen, to be sick). "
            "Sehnsucht is an addictive, painful longing for something unattainable — "
            "more than nostalgia, less than obsession. "
            "C.S. Lewis called it 'the secret signature of each soul' and used it in theology."
        ),
        roots=["Old High German sēnen (to long for — connected to sinew/tension)", "Proto-Germanic *suhtiz (sickness, craving)"],
        cognates=["English sinew (tense longing — same root as Sehnen)", "English sick (same root as Sucht)"],
        semantic_shift="'sinew-pull + sick-craving' → intense, addictive longing for the unattainable",
    ),
    EtymologyEntry(
        language="de", lemma="Schatten",
        origin_summary=(
            "From Proto-Germanic *skadwaz (shadow, shade), from PIE *skot- "
            "(darkness). The same root gives English shadow (via Old English sceadwe) "
            "and shade, Greek skotos (darkness — scotoma, a dark blind spot). "
            "Schattendasein (shadow existence) means a marginal, unrecognized life."
        ),
        roots=["Proto-Germanic *skadwaz (shadow)", "PIE *skot- (darkness)"],
        cognates=["English shadow, shade (same root)", "Greek skotos (darkness — scotoma)"],
        semantic_shift="'darkness, shade' → shadow → figurative shadow (marginal existence)",
    ),
    EtymologyEntry(
        language="de", lemma="Schmerz",
        origin_summary=(
            "From Middle High German smerze (pain, ache), from Proto-Germanic *smertaz "
            "(smarting pain), from *smertan (to smart, to pain). "
            "The same root gives English smart (to feel a stinging pain, and then "
            "'sharp, clever' — the smart of the whip sharpening the mind). "
            "Schmerzlos (painless) and Schmerzensmann (Man of Sorrows) are key forms."
        ),
        roots=["Proto-Germanic *smertaz (smarting pain)", "PIE *smer- (to rub, pain)"],
        cognates=["English smart (to sting — same root, then shifted to 'sharp/clever')", "Dutch smart (pain)"],
        semantic_shift="'stinging pain' → pain, ache",
    ),
    EtymologyEntry(
        language="de", lemma="Übermensch",
        origin_summary=(
            "Compound of über (over, beyond, above) + Mensch (person, human being). "
            "Friedrich Nietzsche coined the concept in Also sprach Zarathustra (1883) "
            "for the ideal human who transcends conventional morality. "
            "George Bernard Shaw translated it as 'Superman'; the concept influenced "
            "Superman comics. Nietzsche's intent was misappropriated by later ideologies."
        ),
        roots=["Proto-Germanic *uberi (over, above) + *mannaz (human being)"],
        cognates=["English superman (translation of Übermensch)", "German über (prefix — borrowed into English)"],
        semantic_shift="Nietzsche's 'one who transcends' → popular culture's superhero concept",
    ),
    EtymologyEntry(
        language="de", lemma="Urlaub",
        origin_summary=(
            "From Middle High German urloup (permission to leave, dismissal), from "
            "ur- (out, primal) + loup (leave, permission). "
            "A vacation as 'having been given leave to go.' "
            "The modern sense of leisure vacation emerged in the 19th century "
            "when paid leave became a workers' right."
        ),
        roots=["Middle High German ur- (out, original) + loup (leave, permission)"],
        cognates=["English leave (as in 'take leave' — same concept)", "Dutch verlof (leave of absence)"],
        semantic_shift="'official permission to go/leave' → vacation, holiday",
    ),
    EtymologyEntry(
        language="de", lemma="Weltreise",
        origin_summary=(
            "Compound of Welt (world) + Reise (journey). A circumnavigation or "
            "grand tour of the world. "
            "The concept captures the Romantic ideal of experiencing the entire world — "
            "from Humboldt's scientific expeditions to modern gap-year travel. "
            "Weltreisender (world traveler) is the agent noun."
        ),
        roots=["Proto-Germanic *wer-ald (world — age of man) + Old Saxon rēsa (journey/rising)"],
        cognates=["English world journey (translation)", "German Weltenbummler (globe-trotter)"],
        semantic_shift="'journey of/through the world' → a grand tour or circumnavigation",
    ),
    EtymologyEntry(
        language="de", lemma="Anfänger",
        origin_summary=(
            "Agent noun from Anfang (beginning) + -er (agent suffix). "
            "Literally 'one who is at the beginning' — a beginner. "
            "Anfänger contrasts with Fortgeschrittener (advanced learner) and Experte. "
            "The suffix -er forms agent nouns across German: Lehrer (teacher — one who teaches), "
            "Fahrer (driver), Spieler (player)."
        ),
        roots=["German Anfang (beginning) + -er (agent suffix)", "Old High German ana- + fāhan (to begin by catching)"],
        cognates=["English beginner (same conceptual formation)", "German Anfang (beginning — same root)"],
        semantic_shift="'one at the catching/beginning' → beginner, novice",
    ),
    EtymologyEntry(
        language="de", lemma="Geburtstag",
        origin_summary=(
            "Compound of Geburt (birth) + Tag (day). 'Birth-day' — the day of birth. "
            "Geburt comes from gebären (to bear/give birth), from Proto-Germanic *baraną. "
            "The same root gives English bear (to carry/birth), barn (place where "
            "born things are kept), and barrow. "
            "Herzlichen Glückwunsch zum Geburtstag is the standard birthday greeting."
        ),
        roots=["Proto-Germanic *baraną (to bear, carry, give birth) + *dagaz (day)"],
        cognates=["English birthday (same compound structure)", "English bear (to carry/birth — same root)"],
        semantic_shift="'birth day' → birthday (annual celebration of the day of birth)",
    ),
    EtymologyEntry(
        language="de", lemma="Widerstand",
        origin_summary=(
            "Compound of wider (against, contrary to) + Stand (standing, stand). "
            "Resistance as 'standing against.' "
            "Der Widerstand refers specifically to the German resistance against "
            "National Socialism — the moral weight of standing firm. "
            "Widerstandsfähigkeit (resilience) is 'capacity to stand against.'"
        ),
        roots=["Proto-Germanic *wiþra (against, contrary) + *standaną (to stand)"],
        cognates=["English withstand (same compound — to stand against)", "English resistance (Latin: re + sistere = to stand again)"],
        semantic_shift="'standing against (something)' → resistance, opposition",
    ),

    # ── Spanish (new entries) ─────────────────────────────────────────────────
    EtymologyEntry(
        language="es", lemma="trabajo",
        origin_summary=(
            "From Latin trepalium (a three-pronged instrument of torture), from "
            "tres (three) + palus (stake). To work was 'to suffer the trepalium.' "
            "The semantic shift from torture to labor reflects the experience of "
            "forced agricultural work. The same root gives English travail (painful toil)."
        ),
        roots=["Latin trepalium (three-stake torture device)", "Latin tres (three) + palus (stake)"],
        cognates=["English travail (hard labor, toil — same source)", "French travail (work — same source)", "Portuguese trabalho"],
        semantic_shift="'torture device' → toil, hard labor → work generally",
    ),
    EtymologyEntry(
        language="es", lemma="dinero",
        origin_summary=(
            "From Latin denarius (a silver Roman coin worth ten asses), from deni "
            "(ten each). The denarius was Rome's standard silver coin. "
            "Its name lives in Spanish dinero, Italian denaro, French denier, "
            "and the 'd' abbreviation for pre-decimal British pence (d = denarius)."
        ),
        roots=["Latin denarius (silver coin)", "Latin deni (ten each)"],
        cognates=["Italian denaro", "French denier (small coin)", "English penny (d for denarius)"],
        semantic_shift="'ten-unit Roman silver coin' → money generally",
    ),
    EtymologyEntry(
        language="es", lemma="casa",
        origin_summary=(
            "From Latin casa (cottage, hut, simple dwelling), not from the grander "
            "Latin domus. Casa replaced domus in popular Latin and then all Romance "
            "languages for 'house.' The shift reflects the social reality: most people "
            "lived in casae, not domus. English casino (little house) comes from Italian casa."
        ),
        roots=["Latin casa (cottage, simple dwelling)"],
        cognates=["Italian casa (house)", "French chez (at the house of — same root via Provençal)", "English casino (little house)"],
        semantic_shift="'simple cottage/hut' → house (any dwelling)",
    ),
    EtymologyEntry(
        language="es", lemma="comer",
        origin_summary=(
            "From Latin comedere (to eat up, consume), from com- (completely) + "
            "edere (to eat). The intensive prefix com- emphasizes eating completely. "
            "The same Latin edere gives English edible and comestible. "
            "Spanish uses comer where Latin used simply edere — the compound became the default."
        ),
        roots=["Latin comedere (to eat up)", "Latin com- (completely) + edere (to eat)"],
        cognates=["English edible, comestible (same root)", "French manger (from manducare — to chew)", "Italian mangiare"],
        semantic_shift="'to eat up completely' → to eat (general sense)",
    ),
    EtymologyEntry(
        language="es", lemma="gente",
        origin_summary=(
            "From Latin gens/gentis (clan, tribe, people, nation), from gignere "
            "(to beget). A gens was originally a group sharing common ancestry. "
            "English gentile (non-Jewish people), gentle (well-born), and gender "
            "all come from the same root. "
            "Spanish gente can be singular ('people') unlike English 'people.'"
        ),
        roots=["Latin gens/gentis (clan, people)", "Latin gignere (to beget)"],
        cognates=["English gentile, gentle, gender, generate (same root)", "French gens (people)", "Italian gente"],
        semantic_shift="'those born of the same clan' → people (general term)",
    ),
    EtymologyEntry(
        language="es", lemma="calor",
        origin_summary=(
            "From Latin calor (warmth, heat, passion), from calere (to be warm). "
            "The same root gives English calorie (unit of heat energy), "
            "and the Caloric theory of heat (now replaced by thermodynamics). "
            "In Spanish, calor is used for both physical and emotional warmth "
            "(calor humano = human warmth)."
        ),
        roots=["Latin calor (heat, warmth)", "Latin calere (to be warm)"],
        cognates=["English calorie, caloric (same root)", "Italian calore (heat)", "French chaleur"],
        semantic_shift="'physical heat' → emotional warmth",
    ),
    EtymologyEntry(
        language="es", lemma="cielo",
        origin_summary=(
            "From Latin caelum (sky, heavens, vault of heaven), of uncertain PIE origin. "
            "Spanish cielo covers both the physical sky and the theological heaven — "
            "a single word for two English concepts. "
            "¡Cielos! (heavens!) is a common exclamation. "
            "Celestial (from caelestis) and ceiling (via Norman French) share this root."
        ),
        roots=["Latin caelum (sky, heavens)"],
        cognates=["English celestial, ceiling (same root)", "French ciel (sky/heaven)", "Italian cielo"],
        semantic_shift="'the vault of the sky' → sky AND heaven in one word",
    ),
    EtymologyEntry(
        language="es", lemma="luna",
        origin_summary=(
            "From Latin luna (moon), from an older root related to lux (light) — "
            "the moon as the night's light-giver. "
            "Lunar, lunatic (moon-caused madness), and lunation all derive from luna. "
            "The Spanish luna is also the name of Earth's moon in the scientific sense, "
            "and appears in lunes (Monday — day of the moon)."
        ),
        roots=["Latin luna (moon)", "PIE *lewk- (light)"],
        cognates=["English lunar, lunatic (same root)", "French lune", "Italian luna", "lunes (Monday — moon's day)"],
    ),
    EtymologyEntry(
        language="es", lemma="mar",
        origin_summary=(
            "From Latin mare (sea), from PIE *móri (sea, large body of water). "
            "Spanish mar is unusual in that it can be both masculine (el mar) and "
            "feminine (la mar) — traditionally feminine in poetry and among fishermen. "
            "Maritime, submarine, and Mediterranean (middle-of-the-sea) share this root."
        ),
        roots=["Latin mare (sea)", "PIE *móri (sea, large body of water)"],
        cognates=["English maritime, submarine, Mediterranean (same root)", "French mer", "Italian mare"],
        semantic_shift="'sea' → el mar (masculine, standard) / la mar (feminine, poetic/maritime)",
    ),
    EtymologyEntry(
        language="es", lemma="año",
        origin_summary=(
            "From Latin annus (year), from PIE *h₂et-no- (going — the year as a going/circuit). "
            "The Latin 'nn' was palatalized to 'ñ' in Spanish. "
            "Annual, anniversary, and annals all share this root. "
            "Año nuevo (New Year) and años luz (light years) show its range."
        ),
        roots=["Latin annus (year)", "PIE *h₂et-no- (going, circuit)"],
        cognates=["English annual, anniversary, annals (same root)", "French an/année (year)", "Italian anno"],
        semantic_shift="'the circuit/going (of the sun)' → year",
    ),
    EtymologyEntry(
        language="es", lemma="mano",
        origin_summary=(
            "From Latin manus (hand), from PIE *meh₂- (hand). "
            "Unusual in Spanish: despite ending in -o, mano is feminine (la mano). "
            "The Latin manus gives English manual, manage (to handle), manufacture, "
            "and manuscript (written by hand). "
            "Mano a mano (hand to hand) entered English as a sporting metaphor."
        ),
        roots=["Latin manus (hand)", "PIE *meh₂- (hand)"],
        cognates=["English manual, manage, manuscript, manufacture (same root)", "French main", "Italian mano"],
        semantic_shift="'hand' → mano a mano (hand-to-hand combat/competition)",
    ),
    EtymologyEntry(
        language="es", lemma="niño",
        origin_summary=(
            "Possibly from Latin ninnus (infant, baby — baby-talk word) or from "
            "a reduplication form of *ninus. "
            "El Niño (the child/boy) entered climate science as the name for the "
            "Pacific warm current that arrives around Christmas — the Christ Child's arrival. "
            "Niñez (childhood) and niñero/a (babysitter) derive from it."
        ),
        roots=["Possibly Latin ninnus (baby — nursery word)"],
        cognates=["El Niño (climate phenomenon — Christmas child metaphor)", "Spanish niña, niñez"],
        semantic_shift="'baby/infant' → child, boy/girl",
    ),
    EtymologyEntry(
        language="es", lemma="nombre",
        origin_summary=(
            "From Latin nomen/nominis (name), from PIE *h₁nómn̥. "
            "The pan-IE name word: Greek onoma (anonymous), English name, "
            "German Name, Russian имя. "
            "Nominal, noun (the naming word), and denominate all share this root. "
            "En nombre de (in the name of) is a common legal/formal phrase."
        ),
        roots=["Latin nomen/nominis (name)", "PIE *h₁nómn̥ (name)"],
        cognates=["English name, noun, nominal (same root)", "French nom", "Italian nome", "German Name"],
    ),
    EtymologyEntry(
        language="es", lemma="venir",
        origin_summary=(
            "From Latin venire (to come), from PIE *gʷem- (to go, come). "
            "The same root gives English come and welcome (well-come). "
            "Adventure (that which comes to you), event (that which comes out), "
            "and convention (coming together) share the Latin root. "
            "¡Bienvenido! (welcome!) is literally 'come well!'"
        ),
        roots=["Latin venire (to come)", "PIE *gʷem- (to go, come)"],
        cognates=["English come, welcome, adventure, event (same root)", "French venir", "Italian venire"],
        semantic_shift="'to come' → ¡Bienvenido! (well-come → welcome!)",
    ),
    EtymologyEntry(
        language="es", lemma="vida",
        origin_summary=(
            "From Latin vita (life), from PIE *gʷih₃wó- (alive). "
            "Vita gives English vital, vitamin (life substance), viable (able to live), "
            "and vivid. "
            "¡Viva! (long live!) and ¡Olé! (bravo!) both celebrate life. "
            "Vida cotidiana (daily life) and modo de vida (way of life) are key phrases."
        ),
        roots=["Latin vita (life)", "PIE *gʷih₃wó- (alive)"],
        cognates=["English vital, vitamin, viable, vivid (same root)", "French vie", "Italian vita"],
    ),
    EtymologyEntry(
        language="es", lemma="viaje",
        origin_summary=(
            "From Arabic wajh (direction, face, course), via Mozarabic Spanish. "
            "The Arabic root gives 'the direction/course of travel.' "
            "Alternatively traced to Latin via (road) + -aje. "
            "A viaje is any journey or trip. "
            "Viajero (traveler) and viaje de ida y vuelta (round trip) are common forms."
        ),
        roots=["Arabic wajh (direction, face, course)", "Possible influence of Latin via (road)"],
        cognates=["English voyage (from French voiage from Latin via — related concept)", "Portuguese viagem"],
        semantic_shift="'direction of travel' → journey, trip",
    ),
    EtymologyEntry(
        language="es", lemma="calle",
        origin_summary=(
            "From Latin callis (narrow path, footpath — especially for cattle "
            "going to pasture). A calle was originally a narrow lane, not a broad road. "
            "In Spanish cities, calle refers to any street. "
            "The medieval calleja (alleyway) and callejón (dead-end alley) preserve "
            "the narrow sense."
        ),
        roots=["Latin callis (narrow path, cattle track)"],
        cognates=["Spanish callejón (alleyway — narrow street)", "Portuguese calçada (paved path)"],
        semantic_shift="'narrow cattle path' → any street",
    ),
    EtymologyEntry(
        language="es", lemma="alcohol",
        origin_summary=(
            "From Arabic al-kuhl (antimony powder, used as eye cosmetic), from kuhala "
            "(to apply antimony). The word was applied to any refined, purified substance — "
            "then to distilled spirits (the refined essence of wine). "
            "The shift from powdered eye paint to drinkable spirits is one of etymology's "
            "most surprising paths."
        ),
        roots=["Arabic al-kuhl (antimony powder)", "Arabic kuhala (to apply eye cosmetic)"],
        cognates=["English alcohol (same source)", "French alcool", "German Alkohol"],
        semantic_shift="'refined antimony powder (eye paint)' → any refined substance → distilled spirits",
    ),
    EtymologyEntry(
        language="es", lemma="algodón",
        origin_summary=(
            "From Arabic al-qutun (the cotton), from Greek kóttōn or possibly "
            "an Egyptian source. Cotton cultivation spread westward via Islamic trade routes. "
            "Spanish algodón preserves the Arabic article al-, as do many Spanish "
            "words borrowed during the Moorish period."
        ),
        roots=["Arabic al-qutun (the cotton)"],
        cognates=["English cotton (same Arabic source, via Italian cotone)", "French coton", "Italian cotone"],
        semantic_shift="Arabic word for cotton plant/fiber → cotton",
    ),
    EtymologyEntry(
        language="es", lemma="azúcar",
        origin_summary=(
            "From Arabic as-sukkar (the sugar), from Persian shakar, from Sanskrit "
            "sharkara (grit, ground sugar). Sugar moved westward from India via "
            "Persia to the Arab world and then to Spain and Europe. "
            "The Arabic article as- (the) is preserved in the Spanish word."
        ),
        roots=["Arabic as-sukkar (the sugar)", "Persian shakar (sugar)", "Sanskrit sharkara (grit)"],
        cognates=["English sugar (same chain via Italian zucchero)", "French sucre", "German Zucker"],
        semantic_shift="'grit/ground substance' → cane sugar → sweetener generally",
    ),
    EtymologyEntry(
        language="es", lemma="ojalá",
        origin_summary=(
            "From Arabic in sha' Allah (if God wills it/God willing). "
            "The Arabic phrase was phonologically adapted through Mozarabic to "
            "oxalá → ojalá. It expresses hope or wish (¡Ojalá que venga! = I hope he comes!). "
            "One of the most direct Arabic grammatical expressions preserved in any "
            "European language."
        ),
        roots=["Arabic in sha' Allah (if God wills it)"],
        cognates=["Portuguese oxalá (same source)", "English inshallah (direct Arabic borrowing)"],
        semantic_shift="'if God wills it' → I hope, hopefully (expressing wish/desire)",
    ),
    EtymologyEntry(
        language="es", lemma="naranja",
        origin_summary=(
            "From Sanskrit nāranga (orange tree), via Persian nārang and Arabic "
            "nāranj. The fruit traveled west from India with its name. "
            "Spanish naranja, Portuguese laranja, and Italian arancia all come "
            "from the same Sanskrit source. English orange (losing the 'n') came "
            "via Old French orenge."
        ),
        roots=["Sanskrit nāranga (orange tree)", "Persian nārang", "Arabic nāranj"],
        cognates=["English orange (same source — 'an orange' from 'a naranja')", "Italian arancia", "Portuguese laranja"],
        semantic_shift="Sanskrit name for the fruit → the fruit itself → the color (English orange)",
    ),
    EtymologyEntry(
        language="es", lemma="tomate",
        origin_summary=(
            "From Nahuatl tomatl (the swelling round fruit), from tōmātl. "
            "Spanish brought the tomato from Mexico to Europe in the 16th century. "
            "The Nahuatl suffix -tl was dropped to form tomate. "
            "English tomato comes from Spanish. The fruit was initially viewed with "
            "suspicion in Europe — called 'love apple' in French (pomme d'amour)."
        ),
        roots=["Nahuatl tōmātl (the swelling round fruit)"],
        cognates=["English tomato (from Spanish)", "French tomate (same source)", "Italian pomodoro (apple of gold — different metaphor)"],
        semantic_shift="Nahuatl word for the plant → the fruit → a global staple",
    ),
    EtymologyEntry(
        language="es", lemma="chocolate",
        origin_summary=(
            "From Nahuatl xocolātl (bitter water) or chocolātl (foam water). "
            "The Aztec drink was unsweetened cacao mixed with water and spices. "
            "Spanish brought it to Europe in the 16th century; the addition of "
            "sugar transformed it. The word spread through all European languages "
            "from Spanish."
        ),
        roots=["Nahuatl xocolātl (bitter water) or chocolātl (foamy liquid)"],
        cognates=["English chocolate (via Spanish)", "French chocolat", "German Schokolade"],
        semantic_shift="'bitter cacao drink' → sweetened solid and beverage → global confection",
    ),
    EtymologyEntry(
        language="es", lemma="cacao",
        origin_summary=(
            "From Nahuatl cacahuatl (cacao seeds, cacao tree). "
            "The Aztecs used cacao beans as currency and to make xocolātl. "
            "Spanish cacao gives English cocoa (a corruption of cacao). "
            "The scientific name Theobroma cacao means 'food of the gods' — "
            "combining Greek and Nahuatl."
        ),
        roots=["Nahuatl cacahuatl (cacao seeds/tree)"],
        cognates=["English cocoa (corruption of cacao)", "English chocolate (from cacao — via Nahuatl)"],
        semantic_shift="Nahuatl name for the tree and seeds → cacao, the basis of chocolate",
    ),
    EtymologyEntry(
        language="es", lemma="canoa",
        origin_summary=(
            "From Taino canaoua (dugout canoe), one of the first Amerindian words "
            "recorded in writing by Columbus in 1492. "
            "The word spread immediately through all European languages. "
            "English canoe comes from Spanish canoa. "
            "It remains one of the clearest examples of direct Taino-to-European transmission."
        ),
        roots=["Taino canaoua (dugout canoe)"],
        cognates=["English canoe (same Taino source via Spanish)", "French canoë", "German Kanu"],
        semantic_shift="Taino word for dugout boat → canoe in all European languages",
    ),
    EtymologyEntry(
        language="es", lemma="tabaco",
        origin_summary=(
            "From Taino tobago (the pipe or the plant itself) or Carib tabago. "
            "Columbus's crew encountered tobacco use in the Caribbean in 1492. "
            "The Spanish adoption of the word and the plant created a global word — "
            "tobacco entered every European language through Spanish. "
            "Now one of the world's most widely borrowed words."
        ),
        roots=["Taino tobago or Carib tabago (pipe or herb)"],
        cognates=["English tobacco (same source via Spanish)", "French tabac", "German Tabak"],
        semantic_shift="Taino/Carib word for the plant or pipe → tobacco, the plant and product",
    ),
    EtymologyEntry(
        language="es", lemma="maíz",
        origin_summary=(
            "From Taino mahis (the life-giving plant), recorded by Columbus in 1493. "
            "The Taino word was adopted into Spanish and spread across Europe. "
            "English maize comes directly from Spanish maíz. "
            "American English corn (from Germanic korn, meaning any grain) displaced "
            "maize in common usage."
        ),
        roots=["Taino mahis (corn/maize plant)"],
        cognates=["English maize (same source via Spanish)", "French maïs", "German Mais"],
        semantic_shift="Taino name for the plant → corn/maize in all European languages",
    ),
    EtymologyEntry(
        language="es", lemma="hamaca",
        origin_summary=(
            "From Taino hamaka (the woven sleeping net). Introduced to Europe by "
            "Columbus's crew who observed its use by Caribbean indigenous people. "
            "Spanish sailors adopted it for shipboard use. "
            "English hammock comes from Spanish hamaca. "
            "A uniquely Caribbean contribution to global material culture and vocabulary."
        ),
        roots=["Taino hamaka (woven sleeping net)"],
        cognates=["English hammock (same Taino source via Spanish)", "French hamac", "German Hängematte (translated)"],
        semantic_shift="Taino word for woven sleeping net → hammock worldwide",
    ),
    EtymologyEntry(
        language="es", lemma="huracán",
        origin_summary=(
            "From Taino Hurakán (the storm god, god of winds and chaos). "
            "The supreme deity of the Taino mythology was the creator of storms. "
            "Spanish adopted the name for the meteorological phenomenon. "
            "English hurricane comes via Spanish. "
            "The Central American deity's name now describes one of Earth's most powerful storms."
        ),
        roots=["Taino Hurakán (storm god, god of chaos and winds)"],
        cognates=["English hurricane (same Taino source via Spanish)", "French ouragan", "German Hurrikan"],
        semantic_shift="'storm god (Taino deity)' → the tropical storm the god embodied → hurricane",
    ),
    EtymologyEntry(
        language="es", lemma="canción",
        origin_summary=(
            "From Latin cantio/cantionis (singing, a song), from canere (to sing). "
            "The same root gives English chant, enchant (to sing a spell over), "
            "incantation, and cantata. "
            "La canción is also the title of Federico García Lorca's famous "
            "poem collection Canciones (1921-1924)."
        ),
        roots=["Latin cantio (song)", "Latin canere (to sing)"],
        cognates=["English chant, enchant, incantation (same root)", "French chanson (song)", "Italian canzone"],
        semantic_shift="'the singing' → song",
    ),
    EtymologyEntry(
        language="es", lemma="corazón",
        origin_summary=(
            "From Latin cor/cordis (heart) + augmentative suffix -azón. "
            "Literally 'big heart' — the augmentative suffix magnifies the organ "
            "and, by extension, its emotional significance. "
            "Cordial (from the heart), accord (heart-to-heart agreement), "
            "and courage (heartedness) all share the Latin root."
        ),
        roots=["Latin cor/cordis (heart)", "Spanish augmentative suffix -azón"],
        cognates=["English cordial, accord, courage (same root)", "French cœur (heart)", "Italian cuore"],
        semantic_shift="'big heart' → heart (literal and emotional)",
    ),
    EtymologyEntry(
        language="es", lemma="verdad",
        origin_summary=(
            "From Latin veritas/veritatis (truth), from verus (true). "
            "The same root gives English verify, verdict (true saying), veracious, "
            "and aver (to state as true). "
            "La verdad os hará libres (The truth shall set you free) is a Biblical phrase "
            "in Spanish, showing the word's moral weight."
        ),
        roots=["Latin veritas (truth)", "Latin verus (true)"],
        cognates=["English verify, verdict, veracious, very (same root — originally 'truly')", "French vérité"],
        semantic_shift="'the true thing' → truth, reality",
    ),
    EtymologyEntry(
        language="es", lemma="tierra",
        origin_summary=(
            "From Latin terra (earth, land, soil, ground), from PIE *ters- (to dry — "
            "dry land). The same root gives English territory, terrain, terrace, "
            "and Mediterranean (middle-earth/land). "
            "Tierra firma (firm land), tierra natal (native land), and "
            "el tercer mundo (Third World — tercer/terra) show its range."
        ),
        roots=["Latin terra (earth, land)", "PIE *ters- (to dry — dry ground)"],
        cognates=["English territory, terrain, terrace, Mediterranean (same root)", "French terre", "Italian terra"],
    ),
    EtymologyEntry(
        language="es", lemma="pueblo",
        origin_summary=(
            "From Latin populus (people, the citizen body). Pueblo covers both "
            "'people' (la gente del pueblo = the people of the town) and "
            "'town/village' — the community and the place it inhabits. "
            "In the American Southwest, pueblo refers to the communal Adobe architecture "
            "of indigenous peoples — a Spanish borrowing that became an English one."
        ),
        roots=["Latin populus (people, citizen body)"],
        cognates=["English people, popular, public (same root)", "French peuple", "English pueblo (borrowed for architecture)"],
        semantic_shift="'citizen body/the people' → town, village (the people AND the place)",
    ),
    EtymologyEntry(
        language="es", lemma="rojo",
        origin_summary=(
            "From Latin russeus (reddish, rust-colored) or rubeus (red, as in ruby). "
            "The expected Latin ruber gave Spanish rubro (formal/poetic) but the "
            "everyday word became rojo. "
            "Russo/roux (red-haired) shares this root, as does rouge (French for red). "
            "La bandera roja (the red flag) and Caperucita Roja (Little Red Riding Hood) "
            "are iconic uses."
        ),
        roots=["Latin russeus (reddish)", "Latin rubeus (red — from ruber)"],
        cognates=["English ruby, rouge (same root)", "French rouge (red)", "Italian rosso"],
        semantic_shift="'reddish/rust-colored' → red",
    ),
    EtymologyEntry(
        language="es", lemma="negro",
        origin_summary=(
            "From Latin niger/nigri (black). The same Latin root gives English "
            "denigrate (to blacken a reputation) and nigrescence. "
            "In Spanish and Portuguese, negro was the standard word for the color black. "
            "Its use as a racial term and the complex history around that use "
            "evolved differently across Spanish and English."
        ),
        roots=["Latin niger/nigri (black)"],
        cognates=["English denigrate (to blacken — same root)", "French noir (black)", "Italian nero"],
        semantic_shift="'black (color)' → also became a racial designation with complex history",
    ),
    EtymologyEntry(
        language="es", lemma="blanco",
        origin_summary=(
            "From Frankish/Gothic blank (shining, white, bare). The Germanic word "
            "replaced Latin albus (white) in Iberian and Gallo-Romance. "
            "The same Germanic root gives French blanc, Italian bianco, and English "
            "blank (empty, white space) and blanch (to whiten). "
            "In chess, las blancas (the whites) are the pieces that move first."
        ),
        roots=["Proto-Germanic *blankaz (shining, gleaming, white)", "Frankish blank"],
        cognates=["English blank, blanch (same root)", "French blanc", "Italian bianco"],
        semantic_shift="'shining, gleaming' → white → blank (empty/white space)",
    ),
    EtymologyEntry(
        language="es", lemma="llevar",
        origin_summary=(
            "From Latin levare (to lift, raise), from levis (light in weight). "
            "To lift → to carry → to take somewhere. "
            "Spanish llevar covers 'to carry,' 'to take (a person),' and 'to wear' "
            "(llevar ropa = to wear clothes — carry clothes on one's body). "
            "The semantic broadening from 'lift' to 'carry/wear' is thorough."
        ),
        roots=["Latin levare (to lift, lighten)", "Latin levis (light in weight)"],
        cognates=["English levitate, lever, relieve (same root)", "French lever (to raise)"],
        semantic_shift="'to lift/lighten' → to carry → to take (a person somewhere) → to wear",
    ),
    EtymologyEntry(
        language="es", lemma="poner",
        origin_summary=(
            "From Latin ponere (to put, place, set down), from *po- + sinere "
            "(to let, allow). The same Latin root gives English position, postpone, "
            "component, compose, and deposit. "
            "Spanish poner is one of the most irregular verbs (pongo, puse, puesto) "
            "due to its high frequency and ancient usage."
        ),
        roots=["Latin ponere (to put, place)", "Latin *po- + sinere (to let/place)"],
        cognates=["English position, postpone, component, deposit (same root)", "French poser", "Italian porre"],
        semantic_shift="'to place/set down' → to put (general placement verb)",
    ),
    EtymologyEntry(
        language="es", lemma="entender",
        origin_summary=(
            "From Latin intendere (to stretch toward, to direct attention to), from "
            "in- + tendere (to stretch). Understanding as 'stretching one's mind toward.' "
            "The same root gives English intend, intent, and tender (to stretch out). "
            "Spanish distinguishes entender (to understand) from comprender (to comprehend/grasp)."
        ),
        roots=["Latin intendere (to stretch toward, attend to)", "Latin in- + tendere (to stretch)"],
        cognates=["English intend, intent, tend, tender (same root)", "French entendre (to hear/understand)", "Italian intendere"],
        semantic_shift="'to stretch one's attention toward' → to understand",
    ),
    EtymologyEntry(
        language="es", lemma="conocer",
        origin_summary=(
            "From Latin cognoscere (to come to know, recognize), from com- + gnoscere "
            "(to know). Knowing a person or place — recognitional knowledge. "
            "Distinguishes from saber (factual knowledge). "
            "The same root gives English recognize, cognizant, and connoisseur "
            "(French: one who knows wine/art)."
        ),
        roots=["Latin cognoscere (to come to know)", "Latin com- + gnoscere (to know)"],
        cognates=["English recognize, cognizant, connoisseur (same root)", "French connaître (to know a person)"],
        semantic_shift="'to come to know (someone)' → to know (a person, place — acquaintance knowledge)",
    ),
    EtymologyEntry(
        language="es", lemma="saber",
        origin_summary=(
            "From Latin sapere (to taste, to have flavor, to be wise). "
            "Knowledge as flavor — wisdom as 'having good taste.' "
            "The same root gives English sapient (wise), savant (learned person — via French), "
            "and insipid (without taste/flavor). "
            "Saber (factual knowledge) contrasts with conocer (personal acquaintance)."
        ),
        roots=["Latin sapere (to taste, be wise)", "PIE *sep- (to taste, to perceive)"],
        cognates=["English sapient, savant, insipid (same root)", "French savoir (to know factually)"],
        semantic_shift="'to taste, to perceive flavor' → to be wise → to know (facts/skills)",
    ),
    EtymologyEntry(
        language="es", lemma="poder",
        origin_summary=(
            "From Latin potere (to be able), from potis (able, powerful). "
            "The Spanish infinitive poder became a noun meaning 'power.' "
            "The same root gives English potent, potential, possible, and impotent. "
            "¿Puede ser? (can it be?) and No puedo más (I can't take it anymore) "
            "show its range from possibility to endurance."
        ),
        roots=["Latin potis (able, powerful)", "Latin potere (to be able)"],
        cognates=["English potent, potential, possible (same root)", "French pouvoir (to be able/power)"],
        semantic_shift="'to be able' → power (the capacity to act or command)",
    ),
    EtymologyEntry(
        language="es", lemma="querer",
        origin_summary=(
            "From Latin quaerere (to seek, to ask, to inquire). "
            "Seeking → wanting → loving. The shift from 'to seek' to 'to want' to "
            "'to love' reflects the relationship between desire and love. "
            "The same Latin root gives English query, question, inquest, and require. "
            "Te quiero (I love you — literally 'I seek/want you') is the common expression of love."
        ),
        roots=["Latin quaerere (to seek, ask, inquire)"],
        cognates=["English query, question, require, inquest (same root)", "French quérir (to seek — archaic)"],
        semantic_shift="'to seek, to ask for' → to want → to love",
    ),
    EtymologyEntry(
        language="es", lemma="esperar",
        origin_summary=(
            "From Latin sperare (to hope), from spes (hope). "
            "Esperar means both 'to wait' and 'to hope' — two meanings English "
            "keeps separate. Waiting and hoping collapse: to wait IS to hope. "
            "¡Espera! (Wait!) and Espero que sí (I hope so) use the same verb. "
            "Despair (English) comes from the same root: de + sperare = to lose hope."
        ),
        roots=["Latin sperare (to hope)", "Latin spes (hope)"],
        cognates=["English despair (loss of hope — same root)", "French espérer (to hope)", "Italian sperare"],
        semantic_shift="'to hope' → both to hope AND to wait (waiting as active hoping)",
    ),
    EtymologyEntry(
        language="es", lemma="pensar",
        origin_summary=(
            "From Latin pensare (to weigh carefully, to ponder), from pendere "
            "(to hang, to weigh). Thinking as 'weighing carefully in the mind.' "
            "The same root gives English pensive (thoughtful), ponder (to weigh), "
            "and pound (weight). Compensate and expend also share the root."
        ),
        roots=["Latin pensare (to weigh carefully)", "Latin pendere (to hang, weigh)"],
        cognates=["English pensive, ponder, pound (weight), compensate (same root)", "French penser", "Italian pensare"],
        semantic_shift="'to weigh (in the mind)' → to think, to consider",
    ),
    EtymologyEntry(
        language="es", lemma="morir",
        origin_summary=(
            "From Latin mori (to die), from PIE *mr̥tós (dead). "
            "The same PIE root gives Latin mors/mortis (death — mortal, murder, "
            "mortgage), English murder, and Russian мор (plague). "
            "García Lorca's duende (dark creative force) is deeply connected to "
            "morir — Spanish art's intimate relationship with death."
        ),
        roots=["Latin mori (to die)", "PIE *mr̥tós (dead)"],
        cognates=["English mortal, murder, mortgage (dead pledge — same root)", "French mourir", "Italian morire"],
    ),
    EtymologyEntry(
        language="es", lemma="nacer",
        origin_summary=(
            "From Latin nasci (to be born), from gnasci, from PIE *ǵenh₁- "
            "(to give birth, produce). The same root gives English native, nation "
            "(those born together), nature (the born order), and Renaissance "
            "(re-birth). "
            "De donde naces (where you are born from) defines one's nationality."
        ),
        roots=["Latin nasci (to be born)", "PIE *ǵenh₁- (to give birth)"],
        cognates=["English native, nation, nature, Renaissance (same root)", "French naître", "Italian nascere"],
        semantic_shift="'to be born' → also applied to sunrise (nacer el sol) and emergence",
    ),
    EtymologyEntry(
        language="es", lemma="crecer",
        origin_summary=(
            "From Latin crescere (to grow, increase, wax), from PIE *ker- (to grow). "
            "The same root gives English crescent (waxing moon — the growing moon), "
            "increase, concrete (grown/hardened together), and accrue. "
            "Crecer means to grow physically, emotionally, and in importance."
        ),
        roots=["Latin crescere (to grow)", "PIE *ker- (to grow, wax)"],
        cognates=["English crescent, increase, concrete, accrue (same root)", "French croître", "Italian crescere"],
        semantic_shift="'to grow, wax (like the moon)' → to grow (in all senses)",
    ),
    EtymologyEntry(
        language="es", lemma="salud",
        origin_summary=(
            "From Latin salus/salutis (safety, health, well-being, salvation), from "
            "salvus (safe, whole, healthy). The same root gives English safe, salvation, "
            "salute (a health-wish), and salary (salt money — Roman soldiers' pay). "
            "¡Salud! is the standard toast (health!) and the response to a sneeze."
        ),
        roots=["Latin salus/salutis (safety, health)", "Latin salvus (safe, whole)"],
        cognates=["English safe, salvation, salute, salary (same root)", "French santé (health — different root)", "Italian salute"],
        semantic_shift="'safety, being whole/sound' → health → toast (wishing health)",
    ),
    EtymologyEntry(
        language="es", lemma="gracia",
        origin_summary=(
            "From Latin gratia (favor, grace, gratitude, charm), from gratus "
            "(pleasing, thankful). The word covers grace (divine favor), thanks "
            "(gracias — plural), and charm/wit. "
            "The same root gives English gracious, gratitude, gratify, and "
            "gratis (free, as a favor). The Christian concept of grace (gracia divina) "
            "expanded its meaning enormously."
        ),
        roots=["Latin gratia (favor, grace)", "Latin gratus (pleasing, grateful)"],
        cognates=["English grace, gratitude, gratify, gratis (same root)", "French grâce", "Italian grazia"],
        semantic_shift="'favor, pleasing quality' → divine grace → thanks (gracias) → charm/wit",
    ),
    EtymologyEntry(
        language="es", lemma="lengua",
        origin_summary=(
            "From Latin lingua (tongue, language). The physical organ became "
            "the name for the language system — a universal metonymy. "
            "Lengua materna (mother tongue) and lengua extranjera (foreign language) "
            "are key compounds. Lingüística (linguistics) shows the learned Latin form. "
            "Lenguaje (language/speech) is derived from lengua."
        ),
        roots=["Latin lingua (tongue, language)", "PIE *dn̥ǵʰwéh₂s (tongue)"],
        cognates=["English lingual, bilingual, linguist (same root)", "French langue", "Italian lingua"],
        semantic_shift="'physical tongue' → language system",
    ),
    EtymologyEntry(
        language="es", lemma="mundo",
        origin_summary=(
            "From Latin mundus (the world, the ordered cosmos), from mundare "
            "(to clean, purify). The world as the 'clean/ordered' realm, "
            "contrasted with chaos. Todo el mundo (everyone — all the world) "
            "and primer mundo (First World) show its range. "
            "English mundane (worldly, boring) comes from the same root."
        ),
        roots=["Latin mundus (world, clean order)", "Latin mundare (to clean, make orderly)"],
        cognates=["English mundane (worldly — same root)", "French monde", "Italian mondo"],
        semantic_shift="'clean, ordered cosmos' → the world → everyone (todo el mundo)",
    ),
    EtymologyEntry(
        language="es", lemma="leche",
        origin_summary=(
            "From Latin lac/lactis (milk) via Vulgar Latin lacte. "
            "The Latin root gives English lactose, lactic, lactate, and galaxy "
            "(the Milky Way — via Greek gala/galaktos). "
            "Café con leche (coffee with milk) is one of Spanish's most recognizable "
            "compound words worldwide."
        ),
        roots=["Latin lac/lactis (milk)", "Vulgar Latin lacte"],
        cognates=["English lactose, lactic, galaxy (same root)", "French lait", "Italian latte", "Portuguese leite"],
    ),
    EtymologyEntry(
        language="es", lemma="paella",
        origin_summary=(
            "From Old Valencian/Catalan paella (pan), from Old French paele (pan), "
            "from Latin patella (small pan, dish), diminutive of patina. "
            "The dish is named for the wide, shallow pan in which it is cooked. "
            "Paella valenciana (the original with rabbit and beans) gave its name "
            "to all variations of the saffron rice dish."
        ),
        roots=["Latin patella (small pan)", "Latin patina (shallow dish)"],
        cognates=["English paten (communion plate — same root)", "French poêle (frying pan)", "Italian padella"],
        semantic_shift="'shallow pan' → the Valencian rice dish cooked in that pan",
    ),
    EtymologyEntry(
        language="es", lemma="embargo",
        origin_summary=(
            "From embargar (to restrain, block, impede), from Vulgar Latin "
            "*imbarricare (to bar in), from barra (bar, barrier). "
            "Sin embargo (nevertheless) literally means 'without restraint/embargo' — "
            "despite the barrier. "
            "English borrowed embargo in the legal/trade sense (blockade of trade)."
        ),
        roots=["Vulgar Latin *imbarricare (to bar in)", "Latin barra (bar, barrier)"],
        cognates=["English embargo (trade blockade — borrowed)", "English bar, barrier (same Latin root)", "Portuguese embargo"],
        semantic_shift="'to block/bar' → trade blockade → sin embargo (without blockage = nevertheless)",
    ),
    EtymologyEntry(
        language="es", lemma="rodeo",
        origin_summary=(
            "From rodear (to go around, surround), from rueda (wheel), from Latin "
            "rota (wheel). A rodeo was a circular gathering of cattle — rounding them up "
            "by going around them. "
            "English borrowed rodeo for the equestrian competition. "
            "Rotary, rotate, and routine (circular path) share the Latin rota root."
        ),
        roots=["Latin rota (wheel)", "Spanish rodear (to go around)"],
        cognates=["English rotate, rotary, routine (same root)", "English rodeo (borrowed from Spanish)"],
        semantic_shift="'going in a circle/wheel' → cattle roundup → the rodeo competition",
    ),
    EtymologyEntry(
        language="es", lemma="sombrero",
        origin_summary=(
            "From sombra (shadow, shade) + -ero (agent/maker suffix). "
            "Literally 'the shade-maker' — a hat that casts shade. "
            "Sombra itself comes from Latin sub- + umbra (under-shadow). "
            "The wide-brimmed sombrero was perfectly designed for the intense "
            "sun of Iberian and Latin American summers."
        ),
        roots=["Latin sub- (under) + umbra (shadow)", "Spanish -ero (agent/maker suffix)"],
        cognates=["English umbrella (little shadow — same umbra)", "English somber (shaded/dark — same root)"],
        semantic_shift="'shade-maker' → wide-brimmed hat designed for sun protection",
    ),
    EtymologyEntry(
        language="es", lemma="patio",
        origin_summary=(
            "From Vulgar Latin patere (to be open, spread out), or possibly from "
            "Old Spanish pado (pasture). An open inner courtyard, typical of "
            "Andalusian and Moorish architectural tradition. "
            "English borrowed patio in the 20th century for any outdoor living area. "
            "The patios of Córdoba are UNESCO heritage sites."
        ),
        roots=["Vulgar Latin patere (to be open, extend)", "Latin patere (to lie open)"],
        cognates=["English patio (borrowed)", "English patent (lying open — same Latin root)"],
        semantic_shift="'open space' → inner courtyard of a house → any outdoor paved area",
    ),
    EtymologyEntry(
        language="es", lemma="tornado",
        origin_summary=(
            "From tornar (to turn, return), from Latin tornare (to turn on a lathe), "
            "from tornus (lathe, turning tool). Past participle tornada → tornado. "
            "The storm as 'the turned/turning thing.' "
            "Spanish sailors in the Atlantic used it for rotating squalls; "
            "English adopted it for the American Great Plains storms."
        ),
        roots=["Latin tornare (to turn on a lathe)", "Latin tornus (lathe, turning tool)"],
        cognates=["English turn, tournament (turning — same root)", "English tornado (borrowed from Spanish)", "Italian tornare"],
        semantic_shift="'the turned/rotating (storm)' → tornado",
    ),
    EtymologyEntry(
        language="es", lemma="bonanza",
        origin_summary=(
            "From Latin bonacia (calm sea, dead calm), from bonus (good) + Greek "
            "malakia (softness — calm sea). 'Good calm' originally referred to fair "
            "weather at sea. Miners applied it to a rich vein of ore — the 'good calm' "
            "of luck. English borrowed it from Spanish miners' slang. "
            "The TV show Bonanza (1959) popularized the American Western sense."
        ),
        roots=["Latin bonus (good) + Greek malakia (softness, calm sea)"],
        cognates=["English bonanza (borrowed from Spanish)", "English bonus (same Latin root)"],
        semantic_shift="'calm, fair sea' → good luck at mining → prosperity, windfall",
    ),
    EtymologyEntry(
        language="es", lemma="corral",
        origin_summary=(
            "From corro (circle, ring) or from Latin currere (to run). "
            "A corral is an enclosure where animals run in a circle — "
            "a circular pen. English borrowed it from Spanish in the American Southwest. "
            "Course, corridor, and current all share the Latin currere root."
        ),
        roots=["Spanish corro (circle) from Latin currere (to run)", "Or Latin corrale (circular enclosure)"],
        cognates=["English corral (borrowed from Spanish)", "English course, corridor, current (same root)"],
        semantic_shift="'circular running space' → enclosure for livestock",
    ),
    EtymologyEntry(
        language="es", lemma="mesa",
        origin_summary=(
            "From Latin mensa (table), of uncertain ultimate origin. "
            "Spanish mesa also describes the flat-topped geological landform "
            "where the table metaphor is applied to geography. "
            "The American Southwest has many mesas named by Spanish explorers. "
            "Mensa (the high-IQ society) uses the Latin word for table."
        ),
        roots=["Latin mensa (table)"],
        cognates=["English mesa (geological — borrowed from Spanish)", "Mensa (table — intelligence society)", "Italian mensa (cafeteria)"],
        semantic_shift="'table' → flat-topped plateau (geological table)",
    ),
    EtymologyEntry(
        language="es", lemma="vainilla",
        origin_summary=(
            "Diminutive of vaina (pod, sheath, scabbard), from Latin vagina "
            "(sheath, scabbard). Vanilla as 'little pod' — named for its seed pod. "
            "Latin vagina meant the sword's scabbard; the anatomical sense developed later. "
            "The flavor comes from the Totonac people of Mexico, who cultivated vanilla "
            "before European contact."
        ),
        roots=["Latin vagina (sheath, scabbard)", "Spanish diminutive suffix -illa"],
        cognates=["English vanilla (same source via Spanish)", "English vagina (same Latin word — different sense)"],
        semantic_shift="'little pod/sheath' → the vanilla orchid's seed pod → the flavor/spice",
    ),
    EtymologyEntry(
        language="es", lemma="aguacate",
        origin_summary=(
            "From Nahuatl ahuacatl (testicle), due to the shape and paired hanging "
            "of the avocado fruit. The Aztecs also used ahuacatl for avocado sauce "
            "(guacamole = ahuacatl + molli). "
            "English avocado comes via Spanish aguacate. "
            "The Nahuatl anatomical name is one of etymology's most striking examples."
        ),
        roots=["Nahuatl ahuacatl (testicle — named for shape of the fruit)"],
        cognates=["English avocado (same Nahuatl source via Spanish)", "Guacamole (aguacate + molli = avocado sauce)"],
        semantic_shift="Nahuatl anatomical metaphor for fruit shape → avocado the fruit and food",
    ),
    EtymologyEntry(
        language="es", lemma="patata",
        origin_summary=(
            "Blend of Taino batata (sweet potato) and Nahuatl papa (potato). "
            "Early Spanish explorers encountered both plants and conflated their names. "
            "English potato comes from Spanish patata/batata. "
            "Spanish now distinguishes patata (Spain) from papa (Latin America) "
            "for the common potato."
        ),
        roots=["Taino batata (sweet potato)", "Nahuatl papa (potato)"],
        cognates=["English potato (via Spanish patata/batata)", "French pomme de terre (earth apple — different metaphor)"],
        semantic_shift="Blend of two Amerindian words for different tubers → potato",
    ),
    EtymologyEntry(
        language="es", lemma="hermano",
        origin_summary=(
            "From Latin germanus (full-blooded, born of the same parents), from "
            "germen (seed, offspring). A hermano was originally specifically a "
            "'genuine/full' brother (both parents shared), as opposed to a half-sibling. "
            "The sense generalized to any brother. Hermandad (brotherhood) is the "
            "collective noun, used for religious and civic fraternities."
        ),
        roots=["Latin germanus (full-blooded, of same parents)", "Latin germen (seed, offspring)"],
        cognates=["English germane (relevant, genuine — same root)", "Portuguese irmão (brother — same root)"],
        semantic_shift="'full-blooded (sibling)' → brother (generalized)",
    ),
    EtymologyEntry(
        language="es", lemma="padre",
        origin_summary=(
            "From Latin pater/patris (father), from PIE *ph₂tḗr. "
            "One of the pan-IE father words: Greek patēr, Sanskrit pitṛ, English "
            "father (via Germanic). The same root gives English paternal, patron, "
            "patronymic, and patrimony. "
            "El Padre Nuestro (Our Father) is the Lord's Prayer in Spanish."
        ),
        roots=["Latin pater/patris (father)", "PIE *ph₂tḗr (father)"],
        cognates=["English paternal, patron, patrimony (same root)", "French père", "Italian padre", "Sanskrit pitṛ"],
    ),
    EtymologyEntry(
        language="es", lemma="madre",
        origin_summary=(
            "From Latin mater/matris (mother), from PIE *méh₂tēr. "
            "The pan-IE mother word: Greek mētēr, Sanskrit mātṛ, English mother. "
            "Madre patria (motherland), madre natura (Mother Nature), and "
            "madrina (godmother — little mother) show its derivatives. "
            "In Mexican Spanish, ¡Madre mía! is a common exclamation."
        ),
        roots=["Latin mater/matris (mother)", "PIE *méh₂tēr"],
        cognates=["English mother, maternal, matrix (same root)", "French mère", "Italian madre"],
    ),
    EtymologyEntry(
        language="es", lemma="guerra",
        origin_summary=(
            "From Visigothic/Frankish werra (strife, confusion, quarrel), from "
            "Proto-Germanic *werzō. The Germanic word replaced Latin bellum "
            "in all Romance languages — a remarkable linguistic conquest. "
            "English war comes from the same Germanic source. "
            "The Latin bellum survives in English belligerent and bellicose."
        ),
        roots=["Proto-Germanic *werzō (strife, confusion)", "Visigothic werra (strife)"],
        cognates=["English war (same Germanic root)", "French guerre", "Italian guerra", "English belligerent (Latin bellum — the word guerra replaced)"],
        semantic_shift="'strife, quarrel' → war (large-scale armed conflict)",
    ),
    EtymologyEntry(
        language="es", lemma="rey",
        origin_summary=(
            "From Latin rex/regis (king), from regere (to rule, guide straight), "
            "from PIE *h₃reǵ- (to straighten). A king as 'one who guides/rules.' "
            "The same root gives English regal, royal, regiment, and rector. "
            "The Reyes Magos (Three Kings/Magi) bring gifts on January 6 in Spanish "
            "tradition — more important than Christmas in many Spanish-speaking cultures."
        ),
        roots=["Latin rex/regis (king)", "PIE *h₃reǵ- (to rule, straighten)"],
        cognates=["English regal, royal, reign (same root)", "French roi", "Italian re"],
        semantic_shift="'one who guides/straightens' → king",
    ),
    EtymologyEntry(
        language="es", lemma="reina",
        origin_summary=(
            "From Latin regina (queen), feminine of rex (king). "
            "All the Romance languages preserved the Latin feminine form for queen. "
            "English queen (from Germanic *kwenō, meaning woman) is entirely different. "
            "La Reina (the Queen) was the title of Isabella I, who sponsored Columbus's "
            "1492 voyage."
        ),
        roots=["Latin regina (queen)", "Latin regere (to rule) + feminine suffix -ina"],
        cognates=["English reign, regal (same root)", "French reine", "Italian regina", "Portuguese rainha"],
        semantic_shift="'female ruler' → queen",
    ),
    EtymologyEntry(
        language="es", lemma="iglesia",
        origin_summary=(
            "From Greek ekklesia (assembly of citizens called out to meet), via "
            "Latin ecclesia. The Greek word (ek- out + kalein to call) described "
            "the civic assembly of ancient Athens. Early Christians adopted it "
            "for their congregation and then their gathering place. "
            "Ecclesiastical (church-related) preserves the Greek form."
        ),
        roots=["Greek ekklesia (assembly)", "Greek ek- (out) + kalein (to call)"],
        cognates=["English ecclesiastical (same Greek root)", "French église", "Italian chiesa"],
        semantic_shift="'civic assembly of called-out citizens' → Christian congregation → church building",
    ),
    EtymologyEntry(
        language="es", lemma="amor",
        origin_summary=(
            "From Latin amor (love, affection), from amare (to love). "
            "Amor rules the Romance tradition of poetry and song — "
            "the troubadours' amour, Dante's amor, and Pablo Neruda's veinte "
            "poemas de amor. The same root gives English amorous, enamored, "
            "and amour propre."
        ),
        roots=["Latin amor (love)", "Latin amare (to love)"],
        cognates=["English amorous, enamored (same root)", "French amour", "Italian amore", "Portuguese amor"],
    ),
    EtymologyEntry(
        language="es", lemma="espada",
        origin_summary=(
            "From Latin spatha (broad flat sword, spatula), from Greek spathē "
            "(broad blade, paddle). The long Roman broadsword gave its name to "
            "the suit of swords in Spanish playing cards (espadas). "
            "The same root gives English spatula (flat blade) and épée (fencing sword). "
            "Don Quijote's obsession with his espada defines his knightly identity."
        ),
        roots=["Latin spatha (broad sword, blade)", "Greek spathē (broad blade)"],
        cognates=["English spatula, spade (card suit — same root)", "French épée (fencing sword)", "Italian spada"],
        semantic_shift="'broad flat blade' → sword → the sword suit in Spanish playing cards",
    ),
    EtymologyEntry(
        language="es", lemma="cuerpo",
        origin_summary=(
            "From Latin corpus/corporis (body, substance), from PIE *krp- (body, "
            "shape). The same root gives English corpse (dead body), corporation "
            "(a legal body), corporal (of the body), and incorporate "
            "(to embody). "
            "A corps (military body of people) and corpus (body of text) "
            "also come from Latin corpus."
        ),
        roots=["Latin corpus/corporis (body)", "PIE *krp- (body, shape)"],
        cognates=["English corpse, corporation, corporal, corpus (same root)", "French corps", "Italian corpo"],
        semantic_shift="'body, substance' → the human body → body of soldiers, text, etc.",
    ),
    EtymologyEntry(
        language="es", lemma="vino",
        origin_summary=(
            "From Latin vinum (wine, grapevine), from PIE *wóinom (wine). "
            "Wine's PIE origin suggests it spread with grapevine cultivation from "
            "the Near East. The same root gives English wine and vine. "
            "Spain is one of the world's largest wine producers. "
            "¡Salud! is the toast; Rioja, Ribera del Duero, and Albariño are key wines."
        ),
        roots=["Latin vinum (wine)", "PIE *wóinom (wine/grapevine)"],
        cognates=["English wine, vine, vineyard (same root)", "French vin", "Italian vino", "Portuguese vinho"],
    ),
    EtymologyEntry(
        language="es", lemma="pan",
        origin_summary=(
            "From Latin panis (bread), from PIE *peh₂- (to protect, feed). "
            "Bread as the primary food — 'the thing that feeds.' "
            "The same root gives English companion (com + panis = bread-sharer), "
            "pantry (bread storage), and company. "
            "El pan nuestro de cada día (our daily bread) is from the Lord's Prayer."
        ),
        roots=["Latin panis (bread)", "PIE *peh₂- (to protect, feed)"],
        cognates=["English companion (bread-sharer), pantry (same root)", "French pain", "Italian pane", "Portuguese pão"],
        semantic_shift="'the thing that feeds/protects' → bread → the staple food",
    ),
    EtymologyEntry(
        language="es", lemma="río",
        origin_summary=(
            "From Latin rivus (stream, brook, small watercourse), from PIE *h₃reiH- "
            "(to flow). A river as 'the flowing thing.' "
            "Rival comes from the same root — rivals were those who shared a rivus "
            "(water rights disputes made neighbors into rivals). "
            "The great rivers: Río Amazonas, Río de la Plata, Río Ebro, Río Tajo."
        ),
        roots=["Latin rivus (stream, brook)", "PIE *h₃reiH- (to flow)"],
        cognates=["English rival (same root — those sharing a river)", "English rivulet (small stream — same root)", "French rivière"],
        semantic_shift="'small stream, watercourse' → river → rival (those who share/compete for a river)",
    ),
]


#: Default store — import and call .get() directly in most code paths.
DEFAULT_STORE: EtymologyStore = EtymologyStore(_CURATED)
