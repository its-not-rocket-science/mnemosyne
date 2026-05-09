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
]


#: Default store — import and call .get() directly in most code paths.
DEFAULT_STORE: EtymologyStore = EtymologyStore(_CURATED)
