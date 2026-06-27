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

    # ── PT additions (generated by gen_etymology.py) ──
    EtymologyEntry(
        language="pt", lemma="solidão",
        origin_summary=(
            "From Latin solitudo/solitudinis (loneliness, wilderness, "
            "solitude), from solus (alone). Solidão (loneliness, solitude) "
            "contrasts culturally with the Portuguese saudade — both describe "
            "forms of absence, but solidão is the absence of company, while "
            "saudade is the longing for what was once present. The word "
            "passed through Old Portuguese unchanged in meaning."
        ),
        roots=[
            "Latin solitudo (loneliness, desert, solitude)",
            "Latin solus (alone, only)",
        ],
        cognates=[
            "English 'solitude' (from the same Latin root)",
            "English 'sole' (from Latin solus)",
            "Spanish 'soledad' (loneliness, cognate)",
        ],
        semantic_shift=(
            "'state of being alone' → philosophical and poetic concept of "
            "solitude"
        ),
    ),
    EtymologyEntry(
        language="pt", lemma="boato",
        origin_summary=(
            "From Latin boatus (a roaring, a bellowing), from boare (to "
            "shout, to roar). A boato is a rumor, a piece of gossip — "
            "etymologically, a loud shout that spreads through a crowd. The "
            "journey from 'roar' to 'rumor' captures how news travels through "
            "a community noisily."
        ),
        roots=[
            "Latin boare (to shout, to roar, to bellow)",
            "Latin boatus (a roaring sound)",
        ],
        cognates=[
            "English 'boisterous' (possibly from the same root via Old French)",
            "Portuguese 'brado' (a shout, related)",
        ],
        semantic_shift=(
            "'a roar, a shout' → a rumor that spreads loudly through a "
            "community"
        ),
    ),
    EtymologyEntry(
        language="pt", lemma="cobiça",
        origin_summary=(
            "From Latin cupiditas (desire, greed), from cupere (to desire), "
            "the same root as Cupid (the god of desire). Portuguese cobiça "
            "means greed, covetousness, or strong desire for material things. "
            "The word entered Old Portuguese from Vulgar Latin and preserved "
            "the meaning of consuming desire."
        ),
        roots=[
            "Latin cupiditas (desire, greed, lust)",
            "Latin cupere (to desire, to long for)",
        ],
        cognates=[
            "English 'covet' (from Old French coveitier, same Latin root)",
            "English 'cupidity' (greed, from Latin cupiditas)",
            "Spanish 'codicia' (greed, same root)",
        ],
        semantic_shift=(
            "'strong desire, longing' → covetousness, greed for material "
            "things"
        ),
    ),
    EtymologyEntry(
        language="pt", lemma="madrugada",
        origin_summary=(
            "From Spanish madrugada (the early hours before dawn), from "
            "madrugar (to rise early), from Latin matutinus (of the morning), "
            "from Matuta (the Roman goddess of dawn). Madrugada denotes the "
            "hours between midnight and dawn — a word that exists in both "
            "Portuguese and Spanish with no equivalent single word in English "
            "('the small hours' comes close)."
        ),
        roots=[
            "Latin matutinus (of the morning)",
            "Roman deity Matuta (goddess of dawn and early morning light)",
        ],
        cognates=[
            "English 'matins' (morning prayers, from the same Latin root)",
            "Spanish 'madrugada' (early morning hours)",
            "English 'mature' (from a related sense of Latin maturus — timely)",
        ],
        semantic_shift=(
            "'morning goddess/morning time' → the specific period between "
            "midnight and dawn"
        ),
    ),
    EtymologyEntry(
        language="pt", lemma="sombra",
        origin_summary=(
            "From Latin subumbra (under the shade) or from Vulgar Latin "
            "*sumbra, from umbra (shadow, shade). Sombra is shadow, shade, or "
            "dark — a fundamental word in Portuguese and Spanish visual "
            "vocabulary. The metaphorical uses (estar na sombra = to be in "
            "the shade/background) extend from the physical shadow."
        ),
        roots=["Latin umbra (shadow, shade, ghost)"],
        cognates=[
            "English 'umbrella' (via Italian ombrella — from the same Latin umbra)",
            "English 'umbrage' (offense, shade)",
            "Spanish 'sombra' (shadow, same word)",
        ],
        semantic_shift=(
            "'shade, shadow' → background, obscurity; also shade for "
            "protection from sun"
        ),
    ),
    EtymologyEntry(
        language="pt", lemma="aldrabão",
        origin_summary=(
            "From aldrava (a door knocker, a latch), from Arabic ad-darrāba "
            "(a door knocker), from daraba (to knock, to strike). Originally "
            "a person who played with the door latch — one who loiters; "
            "evolved to mean a trickster, a deceiver, a charlatan. The Arabic "
            "import path through the Moorish period left numerous Portuguese "
            "words in everyday domestic vocabulary."
        ),
        roots=[
            "Arabic ad-darrāba (a door knocker)",
            "Arabic daraba (to knock, to strike, to hit)",
        ],
        cognates=["Portuguese 'aldrava' (a door latch, door knocker)"],
        semantic_shift=(
            "'door latch/knocker' → someone who fiddles with the latch "
            "(loiterer) → a trickster or charlatan"
        ),
    ),
    EtymologyEntry(
        language="pt", lemma="garfo",
        origin_summary=(
            "From Arabic ghārfūn or from Latin graphium (a stylus for "
            "writing), from Greek grapheion (a writing tool). Some "
            "derivations trace it to a Germanic root *garba (a bundle, "
            "tines). A garfo (fork) entered common use in Portugal earlier "
            "than in other European countries — Portugal's table culture was "
            "influenced by contact with the Arab world and the Renaissance."
        ),
        roots=[
            "possibly from Arabic gárfu or from Latin graphium (stylus, pointed tool)",
        ],
        cognates=[
            "Spanish 'garfio' (a hook, a grappling iron)",
            "English 'graph' (from Greek graphein, the same root if Latin graphium is the source)",
        ],
        semantic_shift="'pointed writing tool or hook' → a table utensil with tines",
    ),
    EtymologyEntry(
        language="pt", lemma="coragem",
        origin_summary=(
            "From Old French corage (heart, spirit, courage), from Latin cor "
            "(heart). The Old French form corage entered Portuguese and "
            "Spanish — the heart as the seat of bravery and moral strength. "
            "The metaphor 'heart = courage' is ancient and cross-cultural: "
            "Latin cor, Greek kardia, Sanskrit hṛd all mean both heart and "
            "the core of courage."
        ),
        roots=[
            "Latin cor/cordis (heart)",
            "Old French corage (heart, spirit, courage)",
        ],
        cognates=[
            "English 'courage' (from Old French corage, same origin)",
            "English 'cordial' (from the heart — from cor)",
            "Spanish 'coraje' (courage, anger — same root)",
        ],
        semantic_shift="'heart' → the quality of heart (spirit, bravery) → courage",
    ),
    EtymologyEntry(
        language="pt", lemma="berço",
        origin_summary=(
            "From Medieval Latin *bertium or from a Germanic root *bēra- (a "
            "bed frame, a bier). A berço is a cradle — the first bed of an "
            "infant. Metaphorically, o berço da civilização (the cradle of "
            "civilization) follows the same path as English 'cradle.' The "
            "word entered Portuguese in the early medieval period."
        ),
        roots=[
            "possibly from Germanic *bēra- (a bier, a carrying frame)",
            "Medieval Latin *bertium (uncertain)",
        ],
        cognates=[
            "English 'bier' (a frame for carrying a coffin, from the same Germanic root)",
            "German 'Bahre' (a stretcher, bier)",
        ],
        semantic_shift=(
            "'a carrying frame, a bed frame' → a baby's cradle → the "
            "birthplace of something"
        ),
    ),
    EtymologyEntry(
        language="pt", lemma="alfaiate",
        origin_summary=(
            "From Arabic al-khayyāṭ (the tailor), from khāṭa (to sew). The "
            "Arabic definite article al- fused with the noun khāyyāt to give "
            "Portuguese alfaiate (tailor). This is one of hundreds of Arabic "
            "loanwords that entered Portuguese during the Moorish period "
            "(711–1249 AD) and remain in everyday use."
        ),
        roots=[
            "Arabic al-khayyāṭ (the tailor)",
            "Arabic khāṭa (to sew, to stitch)",
        ],
        cognates=[
            "Spanish 'sastre' (tailor — different origin)",
            "Portuguese 'alfândega' (customs house — another Arabic loanword with al-)",
        ],
        semantic_shift="Arabic 'the tailor' → Portuguese word for a professional tailor",
    ),
    EtymologyEntry(
        language="pt", lemma="algodão",
        origin_summary=(
            "From Arabic al-quṭn (the cotton), from a Semitic root quṭn "
            "(cotton, fine fiber). Cotton cultivation and trade spread from "
            "the Arab world into Iberia during the Moorish period. The Arabic "
            "article al- fused with quṭn to give Portuguese algodão. Compare "
            "Spanish algodón (same origin)."
        ),
        roots=[
            "Arabic al-quṭn (the cotton)",
            "Semitic root for cotton fiber",
        ],
        cognates=[
            "Spanish 'algodón' (cotton, same Arabic root)",
            "English 'cotton' (via Old Italian cotone, from Arabic quṭn without the article)",
        ],
        semantic_shift=(
            "Arabic name for the cotton plant → Portuguese word for cotton "
            "fiber and fabric"
        ),
    ),
    EtymologyEntry(
        language="pt", lemma="laranja",
        origin_summary=(
            "From Arabic nāranj (an orange), from Persian nārang, from "
            "Sanskrit nāraṅga (orange tree), possibly from a Dravidian root. "
            "The Arabic nāranj lost its initial n- in Portuguese because the "
            "n was reanalyzed as part of the article uma n'aranja → uma "
            "laranja. The orange fruit traveled westward along trade routes "
            "from Southeast Asia through Persia, Arabia, and into Europe."
        ),
        roots=[
            "Sanskrit nāraṅga (orange tree)",
            "Persian nārang (orange)",
            "Arabic nāranj (orange)",
        ],
        cognates=[
            "English 'orange' (same Sanskrit root, via Arabic, then Old French orenge with the n- lost differently)",
            "Spanish 'naranja' (orange — retained the initial n)",
            "Italian 'arancia' (orange, also from Arabic)",
        ],
        semantic_shift=(
            "Sanskrit plant name → Persian → Arabic → Portuguese, with loss "
            "of initial n- through misdivision"
        ),
    ),
    EtymologyEntry(
        language="pt", lemma="açúcar",
        origin_summary=(
            "From Arabic as-sukkar (the sugar), from Sanskrit śarkarā (grit, "
            "gravel, sugar crystals). The Arabic article as- fused with "
            "sukkar to give Old Portuguese açúcar. Sugar reached Europe "
            "through Arab traders who cultivated it in Iberia and Sicily. "
            "Portuguese sailors established the Atlantic sugar trade via the "
            "Azores, Madeira, and eventually Brazil."
        ),
        roots=[
            "Sanskrit śarkarā (grit, gravel, crystalline sugar)",
            "Arabic as-sukkar (the sugar)",
        ],
        cognates=[
            "English 'sugar' (via Old French sucre, from Arabic without the article)",
            "Spanish 'azúcar' (sugar, same Arabic root)",
            "English 'saccharine' (from Greek sakkharon, same ultimate root)",
        ],
        semantic_shift=(
            "Sanskrit word for grit/gravel crystals → sugar crystals → the "
            "commodity"
        ),
    ),
    EtymologyEntry(
        language="pt", lemma="azinheira",
        origin_summary=(
            "From Portuguese azinha (the holm oak acorn) + suffix -eira "
            "(tree). Azinha derives from Latin acina (a grape berry, a small "
            "fruit), misapplied to the acorn. The holm oak (Quercus ilex) and "
            "the cork oak (Quercus suber) define the montado/dehesa landscape "
            "of the Iberian Peninsula — one of Europe's most biodiverse "
            "habitats."
        ),
        roots=[
            "Latin acina (a berry, small fruit)",
            "Portuguese -eira (feminine suffix for trees)",
        ],
        cognates=[
            "Spanish 'encina' (holm oak, same Latin root via Vulgar Latin *ilicina)",
        ],
        semantic_shift="'berry-tree' (fruit-bearing tree) → the holm oak specifically",
    ),
    EtymologyEntry(
        language="pt", lemma="bandeira",
        origin_summary=(
            "From Old Provençal bandiera or from a Germanic root *band- (a "
            "band, a stripe, a sign), from Proto-Germanic *bandwō (a sign, a "
            "banner). A bandeira (flag, banner) shares its root with 'banner' "
            "and 'band.' In Brazilian history, the bandeiras were colonial "
            "expeditions that explored the interior — the explorers were "
            "called bandeirantes."
        ),
        roots=["Germanic *bandwō (a sign, a banner, a signal)"],
        cognates=[
            "English 'banner' (from Old French baniere, same Germanic root)",
            "English 'band' (a stripe, a group — related)",
            "Spanish 'bandera' (flag, same root)",
        ],
        semantic_shift=(
            "'a band, a stripe (as a signal)' → a flag; in Brazil, also a "
            "colonial exploring expedition"
        ),
    ),
    EtymologyEntry(
        language="pt", lemma="cachoeira",
        origin_summary=(
            "Origin disputed: possibly from Tupi caguera (waterfall, from ca "
            "= water + guera = fall), or from Portuguese cachão (a violent "
            "flow of water, rapids), related to cascar (to cascade). "
            "Cachoeira designates a waterfall or rapids — a fundamental "
            "geographic feature in Brazil, where the word is extremely common "
            "in place names."
        ),
        roots=[
            "possibly Tupi caguera (waterfall)",
            "alternatively Portuguese cachão (rushing water)",
        ],
        cognates=[
            "Portuguese 'cascata' (waterfall — from Italian cascata)",
            "English 'cascade' (via French, from Italian)",
        ],
        semantic_shift=(
            "either Tupi or Portuguese word for rushing water → any waterfall "
            "or rapids"
        ),
    ),
    EtymologyEntry(
        language="pt", lemma="capanga",
        origin_summary=(
            "From Tupi ka'apãg (a forest thicket, dense undergrowth) or from "
            "African languages (possibly Kimbundu or Yoruba). In Brazilian "
            "Portuguese, a capanga is a hired thug, a bodyguard, or a "
            "strongman working for a local boss. The word traveled through "
            "the social history of rural Brazil — the fazenda (plantation) "
            "culture of private armed retinues."
        ),
        roots=[
            "possibly Tupi ka'apãg (forest undergrowth)",
            "or of African linguistic origin",
        ],
        semantic_shift=(
            "uncertain origin → in Brazilian Portuguese: a hired thug, rural "
            "strong-arm man"
        ),
    ),
    EtymologyEntry(
        language="pt", lemma="mandinga",
        origin_summary=(
            "From the Mandingo/Mande people of West Africa, brought to Brazil "
            "through the slave trade. In Brazilian Portuguese, mandinga means "
            "a spell, a charm, or black magic — reflecting the religious and "
            "magical practices that enslaved West Africans brought to Brazil, "
            "which were both feared and absorbed into popular culture."
        ),
        roots=["Mandingo/Mande ethnonym (West African people)"],
        cognates=[
            "Brazilian 'mandingueiro' (a sorcerer, someone who practices mandinga)",
        ],
        semantic_shift=(
            "name of a West African people → magical practices associated "
            "with them → any spell or charm"
        ),
    ),
    EtymologyEntry(
        language="pt", lemma="saúde",
        origin_summary=(
            "From Latin salus/salutis (safety, health, salvation, greeting), "
            "from salvus (safe, whole, unharmed). Saúde means health, and is "
            "used as a toast (the equivalent of 'cheers' — wishing health). "
            "The Roman greeting salve (be well) and the Portuguese saúde as a "
            "toast share the same PIE root *sol- (whole, healthy)."
        ),
        roots=[
            "Latin salus (health, safety, greeting)",
            "Latin salvus (safe, whole)",
        ],
        cognates=[
            "English 'salute' (a greeting, from Latin salutare)",
            "English 'salvation' (spiritual health/wholeness)",
            "Spanish '¡Salud!' (cheers — the same toast)",
        ],
        semantic_shift=(
            "'wholeness, safety, health' → a wish of good health (toast); "
            "also the state of health"
        ),
    ),
    EtymologyEntry(
        language="pt", lemma="esperança",
        origin_summary=(
            "From Latin sperare (to hope, to expect), via the present "
            "participle sperantem, substantivized as esperança. Sperare comes "
            "from the same root as Greek elpis (hope). Esperança is one of "
            "the three theological virtues alongside fé (faith) and caridade "
            "(charity) — hope as an active expectation of good."
        ),
        roots=["Latin sperare (to hope, to expect)", "Latin spes (hope)"],
        cognates=[
            "English 'Esperanto' (the invented language named 'hopeful' by its creator)",
            "Spanish 'esperanza' (hope)",
            "French 'espérer' (to hope)",
        ],
        semantic_shift=(
            "'to hope, to expect (something good)' → hope as a virtue and "
            "lived attitude"
        ),
    ),
    EtymologyEntry(
        language="pt", lemma="destino",
        origin_summary=(
            "From Latin destinare (to make fast, to determine, to aim at), "
            "from de- (thoroughly) + stanare (related to stare, to stand). "
            "Destino means fate, destination, or destiny — the place or "
            "outcome toward which something is aimed and fixed. Both "
            "'destination' (a place aimed at) and 'destiny' (a fixed outcome) "
            "come from the same Latin source."
        ),
        roots=[
            "Latin destinare (to determine, to aim at, to fix firmly)",
            "Latin stare (to stand, to be fixed)",
        ],
        cognates=[
            "English 'destination' (from the same Latin root)",
            "English 'destiny' (fixed outcome, same root)",
            "Spanish 'destino' (fate, destination)",
        ],
        semantic_shift=(
            "'firmly aimed at, fixed' → a predetermined fate; also a place "
            "one is heading toward"
        ),
    ),
    EtymologyEntry(
        language="pt", lemma="riqueza",
        origin_summary=(
            "From Old French richece (riches), from riche (rich), from "
            "Frankish *rīki (powerful, rich), from a Germanic root related to "
            "'realm' and 'rich.' The wealth vocabulary of early medieval "
            "Europe was largely Germanic — rulers (riks = king) defined "
            "wealth. Riqueza entered Old Portuguese through French influence."
        ),
        roots=[
            "Frankish *rīki (powerful, ruling, wealthy)",
            "Proto-Germanic *rīkijaz (powerful)",
        ],
        cognates=[
            "English 'rich' (from Old English rīce, same Germanic root)",
            "English 'realm' (from Old French reaume, from the same base as riche)",
            "Spanish 'riqueza' (wealth, same root)",
        ],
        semantic_shift=(
            "'powerful, ruling' (the king's quality) → possessing great "
            "resources → wealth as abundance"
        ),
    ),
    EtymologyEntry(
        language="pt", lemma="greve",
        origin_summary=(
            "From French grève (a bank of sand or gravel, a riverside beach). "
            "La Grève was the name of the Place de Grève in Paris, where "
            "workers gathered to be hired and where public executions took "
            "place. When workers gathered there to refuse work, 'faire la "
            "grève' (to do the Grève) became the term for a labor strike. The "
            "word entered Portuguese from French socialist labor vocabulary."
        ),
        roots=[
            "Old French grève (a sandy riverside bank)",
            "Place de Grève, Paris (the historic square by the Seine)",
        ],
        cognates=[
            "French 'grève' (strike)",
            "Spanish 'huelga' (strike — different origin)",
            "English 'strike' (a work stoppage — different metaphor)",
        ],
        semantic_shift=(
            "a Parisian square where workers gathered → 'to go on strike' → "
            "labor strike generally"
        ),
    ),
    EtymologyEntry(
        language="pt", lemma="chafariz",
        origin_summary=(
            "From Arabic as-sāqiya (the water channel, the irrigation "
            "channel), or alternatively from Arabic shadharwān (a cascading "
            "fountain). Chafariz is a public fountain or water basin — "
            "essential infrastructure in Portuguese cities before modern "
            "plumbing. Arabic hydraulic engineering vocabulary permeates "
            "Iberian Portuguese."
        ),
        roots=[
            "Arabic as-sāqiya (water channel, irrigation system) or Arabic shadharwān (a fountain spillway)",
        ],
        cognates=[
            "Portuguese 'aljube' (a cistern — another Arabic hydraulic term)",
            "Spanish 'acequia' (an irrigation canal — from Arabic as-sāqiya)",
        ],
        semantic_shift=(
            "Arabic water-management term → a public ornamental fountain in "
            "Portuguese cities"
        ),
    ),
    EtymologyEntry(
        language="pt", lemma="feitiço",
        origin_summary=(
            "From Latin facticius (made by art, artificial), from facere (to "
            "make, to do). A feitiço is a spell, a charm, or a fetish — "
            "literally 'something made (by art).' Portuguese sailors brought "
            "the word to West Africa in the 15th–16th centuries, where it was "
            "applied to ritual objects; English and French borrowed 'fetish' "
            "from the Portuguese, making feitiço one of the most globally "
            "traveled words in the language."
        ),
        roots=[
            "Latin facticius (artificial, made by craft)",
            "Latin facere (to make, to do)",
        ],
        cognates=[
            "English 'fetish' (from Portuguese feitiço, via French fétiche)",
            "English 'factitious' (artificially made)",
            "English 'fact' (from the same Latin facere)",
        ],
        semantic_shift=(
            "'made by craft/art' → a crafted magical object or spell → "
            "religious ritual object (in West African context) → obsessive "
            "fixation"
        ),
    ),
    EtymologyEntry(
        language="pt", lemma="mocidade",
        origin_summary=(
            "From Portuguese moço (a young person, a servant), possibly from "
            "Latin *musteus (fresh, young — from mustum = must, new wine) or "
            "from an uncertain Late Latin root. Mocidade means youth, the "
            "period of being young. Moço and moça (young man, young woman) "
            "are everyday words in both Portugal and Brazil."
        ),
        roots=[
            "possibly Latin *musteus (fresh, new — from mustum, new wine)",
            "or a Late Latin root of uncertain origin",
        ],
        cognates=[
            "Spanish 'mozo/moza' (a young person, a waiter)",
            "Portuguese 'moçada' (a group of young people)",
        ],
        semantic_shift=(
            "'fresh, new' (like new wine) → a young person → the state of "
            "being young (youth)"
        ),
    ),
    EtymologyEntry(
        language="pt", lemma="toalha",
        origin_summary=(
            "From Frankish *thwahlja (a cloth for washing), from *thwahan (to "
            "wash). A toalha is a towel — the functional cloth for drying. "
            "The same Frankish root gives French serviette via a different "
            "derivation. The word entered Iberian Romance through contact "
            "with Germanic peoples in the early medieval period."
        ),
        roots=[
            "Frankish *thwahlja (a washing cloth)",
            "Frankish *thwahan (to wash)",
        ],
        cognates=[
            "German 'Zwehle' (a towel, archaic)",
            "English 'towel' (via Old French toaille, same Frankish root)",
            "Spanish 'toalla' (towel, same root)",
        ],
        semantic_shift="'a cloth for washing' → a towel for drying",
    ),
    EtymologyEntry(
        language="pt", lemma="xadrez",
        origin_summary=(
            "From Arabic ash-shaṭranj, from Persian chatrang/chaturanga, from "
            "Sanskrit chaturanga (four-limbed, four divisions) — catur (four) "
            "+ anga (limb/body). The game of chess was invented in India, "
            "moved to Persia as chatrang, then to the Arab world as shaṭranj, "
            "and then to Europe via the Iberian Peninsula. Portuguese xadrez "
            "is one of the closest to the Arabic form."
        ),
        roots=[
            "Sanskrit chaturanga (four-limbed — the four divisions of an army: infantry, cavalry, elephants, chariots)",
            "Persian chatrang (chess)",
            "Arabic shaṭranj (chess)",
        ],
        cognates=[
            "English 'chess' (via Old French esches — from the same Persian/Arabic root, differently clipped)",
            "Spanish 'ajedrez' (chess, from Arabic ash-shaṭranj)",
        ],
        semantic_shift=(
            "'four-limbed (four army divisions)' → the Indian battle- "
            "simulation game → chess"
        ),
    ),
    EtymologyEntry(
        language="pt", lemma="gaveta",
        origin_summary=(
            "From Old French gaveite or from a Germanic root related to "
            "'give' or 'container.' A gaveta is a drawer (in furniture) — a "
            "sliding storage compartment. The word is used across Portugal "
            "and Brazil in the same sense. The functional furniture "
            "vocabulary of Romance languages often comes from Germanic "
            "craftsmen's terms."
        ),
        roots=[
            "possibly Old French gaveite (a small compartment)",
            "or Germanic root related to storage containers",
        ],
        cognates=[
            "Spanish 'gaveta' (a small drawer)",
            "French 'gavette' (a small coffer, archaic)",
        ],
        semantic_shift=(
            "'a small container or compartment' → a sliding drawer in "
            "furniture"
        ),
    ),
    EtymologyEntry(
        language="pt", lemma="quilombo",
        origin_summary=(
            "From Kimbundu kilombo (a settlement of warriors, a military "
            "camp), from Mbundu kilumbu (a camp, an enclosure). Quilombo "
            "entered Brazilian Portuguese as the word for settlements founded "
            "by escaped enslaved Africans — the most famous being Quilombo "
            "dos Palmares. The word carries immense historical weight as a "
            "symbol of Black Brazilian resistance."
        ),
        roots=[
            "Kimbundu kilombo (military encampment)",
            "Mbundu kilumbu (an enclosed settlement)",
        ],
        cognates=["Brazilian 'quilombola' (a person of quilombo heritage)"],
        semantic_shift=(
            "Kimbundu word for a warrior settlement → Brazilian word for "
            "communities of escaped slaves; symbol of Black resistance"
        ),
    ),
    EtymologyEntry(
        language="pt", lemma="caipira",
        origin_summary=(
            "From Tupi caa-pira (one who cuts or clears the forest) or from a "
            "Tupi root meaning 'forest dweller.' In Brazilian Portuguese, "
            "caipira describes a rural person from the interior — roughly "
            "equivalent to 'country bumpkin.' The caipirinha cocktail (lime, "
            "cachaça, sugar) is named after this word, suggesting something "
            "rural and down-to-earth."
        ),
        roots=[
            "Tupi caa (forest, the mato) + pira (a cutting or clearing)",
        ],
        cognates=[
            "Brazilian 'caipirinha' (the cocktail — a 'little caipira' thing)",
        ],
        semantic_shift=(
            "Tupi 'forest-clearer' → a rural dweller from the Brazilian "
            "interior → a rustic person"
        ),
    ),
    EtymologyEntry(
        language="pt", lemma="lusofonia",
        origin_summary=(
            "From Lusus (a son of Bacchus, legendary ancestor of the "
            "Lusitanians/Portuguese, from Latin Lusitania — the Roman "
            "province comprising modern Portugal) + Greek phonē (voice, "
            "language). Lusofonia denotes the community of Portuguese- "
            "speaking nations — Portugal, Brazil, Angola, Mozambique, Cape "
            "Verde, and others. A modern coinage modeling itself on "
            "'Francophonie.'"
        ),
        roots=[
            "Latin Lusitania (Roman province, ancestor of Portugal)",
            "Greek phonē (voice, sound, language)",
        ],
        cognates=[
            "French 'Francophonie' (the French-speaking world — same structural model)",
            "English 'phone/phonics' (from Greek phonē)",
        ],
        semantic_shift=(
            "Roman provincial name + Greek 'voice' → the global community of "
            "Portuguese speakers"
        ),
    ),
    EtymologyEntry(
        language="pt", lemma="pelourinho",
        origin_summary=(
            "From Latin pilarium (a pillar), from pila (a pillar, a pier). A "
            "pelourinho was a stone pillar or post in a town square where "
            "criminals were publicly punished — stocks, flogging, and "
            "humiliation. In Brazil, the Pelourinho district of Salvador da "
            "Bahia is named for the pillory that stood there during the slave "
            "trade. Now it is a UNESCO World Heritage site of colonial "
            "architecture."
        ),
        roots=["Latin pila (pillar, pier)", "Latin pilarium (a column)"],
        cognates=[
            "Spanish 'picota' (a pillory — different word, same object)",
            "English 'pillar' (from the same Latin pila)",
        ],
        semantic_shift=(
            "'pillar' → a punishment pillar/pillory → by extension, a town "
            "square with such a pillar; now a historic district name"
        ),
    ),
    EtymologyEntry(
        language="pt", lemma="cachaça",
        origin_summary=(
            "From Portuguese cachace (the dregs of pressed grape wine) or "
            "from cachazar (to crush, to press), ultimately uncertain. "
            "Cachaça is a distilled spirit made from fermented sugarcane "
            "juice — Brazil's national spirit and the base of the caipirinha. "
            "The word is distinctively Brazilian and Afro-Brazilian in "
            "origin, associated with the sugar plantation economy."
        ),
        roots=[
            "origin uncertain; possibly from Portuguese cachace (dregs, the waste of wine pressing)",
        ],
        cognates=[
            "Brazilian 'cana' (sugarcane — the raw material)",
            "Brazilian 'pinga' (an informal name for cachaça)",
        ],
        semantic_shift=(
            "uncertain origin → sugarcane spirit; the national distilled "
            "drink of Brazil"
        ),
    ),
    EtymologyEntry(
        language="pt", lemma="amendoim",
        origin_summary=(
            "From Tupi manduí (peanut), via Old Portuguese manduim with "
            "prefixed a- (through influence of Arabic a- words or Portuguese "
            "phonological change). The peanut is native to South America and "
            "was named in Tupi. Portuguese colonizers spread the peanut "
            "globally — it is now a major crop in West Africa, Asia, and "
            "North America — and the Tupi name traveled with it."
        ),
        roots=["Tupi manduí (peanut, groundnut)"],
        cognates=[
            "Spanish 'maní' (peanut, from the same Tupi root via a different path)",
            "English 'peanut' (different naming — based on the pod/nut appearance)",
        ],
        semantic_shift=(
            "Tupi name for the groundnut → Portuguese, then spread globally "
            "with the crop"
        ),
    ),
    EtymologyEntry(
        language="pt", lemma="lambada",
        origin_summary=(
            "From Portuguese lambar (to lash, to whip), from a root related "
            "to Spanish lamber/lamer (to lick). Lambada (a lash, a slap) "
            "became the name of a sensual Brazilian dance in the 1980s, known "
            "for its close-contact hip movements — the dance is 'a lash' or "
            "'a slap' of energy and contact. It briefly dominated "
            "international pop music in 1989."
        ),
        roots=["Portuguese lambar (to lash, to strike with a strap)"],
        cognates=[
            "Portuguese 'açoite' (a whip — related concept)",
            "Spanish 'lamer' (to lick — possible shared root)",
        ],
        semantic_shift=(
            "'a lashing, a whipping' → a vigorous dance characterized by "
            "close hip contact"
        ),
    ),
    EtymologyEntry(
        language="pt", lemma="butim",
        origin_summary=(
            "From French butin (booty, plunder), from Old Low German bute (an "
            "exchange, a share), related to English 'booty.' Butim entered "
            "Portuguese through military/naval vocabulary during the Age of "
            "Discoveries — the spoils of conquest. The Portuguese word for "
            "plunder captures the economic logic of maritime expansion."
        ),
        roots=[
            "Old Low German bute (an exchange, a share)",
            "French butin (plunder, spoils)",
        ],
        cognates=[
            "English 'booty' (spoils — from the same Germanic root via French)",
            "English 'bootleg' (originally goods sold illegally, same root family)",
        ],
        semantic_shift=(
            "'an exchange, a share taken' → spoils of war, plunder; in "
            "Portuguese particularly associated with maritime conquest"
        ),
    ),
    EtymologyEntry(
        language="pt", lemma="patavina",
        origin_summary=(
            "From Latin Patavina, the feminine adjective of Patavium (Padua, "
            "a city in Northern Italy). The phrase não perceber (entender) "
            "patavina (to not understand a single thing) may derive from "
            "Paduans' reputation in Lisbon for speaking Italian-influenced "
            "Portuguese that no one could understand — or from Italian "
            "commedia dell'arte characters from Padua. The exact etymology is "
            "disputed but geographically grounded."
        ),
        roots=["Latin Patavium (the Roman name for Padua, Italy)"],
        cognates=[
            "Italian 'padovano' (Paduan — the adjective from the same city name)",
        ],
        semantic_shift=(
            "'of Padua' → in Portuguese idiom: não perceber patavina = to not "
            "understand a single thing"
        ),
    ),
    EtymologyEntry(
        language="pt", lemma="cangaço",
        origin_summary=(
            "From cangalha (a wooden frame for carrying loads on donkeys), "
            "from Latin canalis (a channel, pipe) or from a pre-Latin Iberian "
            "root. Cangaço was the term for the violent banditry culture of "
            "the northeastern Brazilian sertão (backlands) in the 19th–early "
            "20th centuries. The cangaceiros (bandits) carried heavy loads of "
            "weapons — the frame for bearing arms gave the movement its name."
        ),
        roots=[
            "cangalha (a donkey's pack-frame, a wooden yoke)",
            "Latin canalis (a channel, tube — possibly cognate)",
        ],
        cognates=[
            "Brazilian 'cangaceiro' (a bandit of the sertão, a member of the cangaço movement)",
        ],
        semantic_shift=(
            "'a load-bearing wooden frame' → the culture of armed banditry in "
            "the Brazilian backlands"
        ),
    ),
    EtymologyEntry(
        language="pt", lemma="picareta",
        origin_summary=(
            "Diminutive of pica (a pickaxe, a pike), from picar (to prick, to "
            "pierce), from a Gallo-Romance root *piccare (to pierce), related "
            "to Italian piccare and French piquer. A picareta is a pickaxe. "
            "In colloquial Brazilian Portuguese, picareta also means a "
            "swindler or charlatan — the connotation of someone who 'picks "
            "away' dishonestly."
        ),
        roots=[
            "Gallo-Romance *piccare (to pierce, to prick)",
            "Latin *piccus (a woodpecker — related image of pecking)",
        ],
        cognates=[
            "English 'pike' (a long spear — from piquer/piccare)",
            "English 'picket' (from the same root)",
            "English 'pick/pickaxe' (related)",
        ],
        semantic_shift=(
            "'a pickaxe' → in Brazilian slang: a swindler, someone who "
            "extracts dishonestly"
        ),
    ),
    EtymologyEntry(
        language="pt", lemma="vaidade",
        origin_summary=(
            "From Latin vanitas/vanitatis (emptiness, worthlessness, vanity), "
            "from vanus (empty, hollow, vain). A vaidade is vanity — "
            "excessive pride in appearance or achievements, but also "
            "theological emptiness (vanitas vanitatum, 'vanity of vanities' "
            "from Ecclesiastes). The moral/aesthetic word and the biblical "
            "philosophical term share the same Latin emptiness."
        ),
        roots=[
            "Latin vanus (empty, hollow, without substance)",
            "Latin vanitas (emptiness, futility)",
        ],
        cognates=[
            "English 'vain' (from Latin vanus)",
            "English 'vanity' (from Latin vanitas)",
            "English 'evanescent' (fading away — from evanescere, related to vanere)",
        ],
        semantic_shift=(
            "'emptiness, hollowness' → moral emptiness (pride that is hollow) "
            "→ excessive vanity about appearance"
        ),
    ),
    EtymologyEntry(
        language="pt", lemma="azar",
        origin_summary=(
            "From Arabic az-zahr (the dice, the flower), from zahr (a die, a "
            "flower blossom). Arabic az-zahr referred to dice used in games "
            "of chance; the uncertainty of dice rolls gave the word its sense "
            "of chance and luck. In Portuguese, azar specifically means bad "
            "luck or misfortune — the unlucky throw of the dice. Spanish azar "
            "preserves the neutral meaning of chance; Portuguese narrowed it "
            "to ill fortune."
        ),
        roots=[
            "Arabic az-zahr (the dice, the flower)",
            "Arabic zahr (a die; also a flower or blossom)",
        ],
        cognates=[
            "Spanish 'azar' (chance, fate — broader in meaning)",
            "French 'hasard' (chance, risk — from the same Arabic root via Spanish)",
            "English 'hazard' (a danger, a risk — from Old French hasard, same source)",
        ],
        semantic_shift=(
            "Arabic 'dice (instrument of chance)' → the result of a bad throw "
            "→ bad luck, misfortune"
        ),
    ),
    EtymologyEntry(
        language="pt", lemma="almofada",
        origin_summary=(
            "From Arabic al-mukhadda (the pillow, the cushion), from khādd (a "
            "cheek — the body part one rests on a pillow). Almofada (a "
            "cushion, a pillow) entered Portuguese during the Moorish period. "
            "The Arabic term for a pillow is literally 'the cheek-rest.' Many "
            "Portuguese domestic comfort words — bedding, cushions, furniture "
            "— entered the language from Arabic."
        ),
        roots=[
            "Arabic al-mukhadda (the pillow)",
            "Arabic khādd (cheek — the anatomical root)",
        ],
        cognates=[
            "Spanish 'almohada' (pillow — same Arabic root)",
            "Portuguese 'almofadinha' (a small cushion, an affectionate term)",
        ],
        semantic_shift="Arabic 'cheek-rest' → a pillow or cushion for any surface",
    ),
    EtymologyEntry(
        language="pt", lemma="tabaco",
        origin_summary=(
            "From Taíno tabaco (a tube or pipe used for inhaling smoke), the "
            "name given by the indigenous people of the Caribbean to both the "
            "plant and the Y-shaped pipe used to smoke it. Christopher "
            "Columbus encountered tobacco in 1492; Portuguese sailors spread "
            "the plant globally through their trade networks. By the 16th "
            "century, tabaco had entered all major European languages from "
            "the Taíno word."
        ),
        roots=["Taíno tabaco (a smoking pipe; the tobacco plant)"],
        cognates=[
            "English 'tobacco' (from the same Taíno word via Spanish)",
            "French 'tabac' (tobacco)",
            "German 'Tabak' (tobacco)",
        ],
        semantic_shift=(
            "Taíno name for a smoking pipe → the plant itself → the processed "
            "leaf commodity"
        ),
    ),
    EtymologyEntry(
        language="pt", lemma="milho",
        origin_summary=(
            "From Latin milium (millet, a small-grained cereal), from Proto- "
            "Indo-European *mel- (to crush, to grind). When Portuguese "
            "explorers encountered maize/corn in the Americas, they applied "
            "the familiar word milho (which had meant millet) to the new "
            "crop. European milho (millet) and American milho (maize) are "
            "etymologically identical words for two different grains — a "
            "classic case of semantic transfer upon contact."
        ),
        roots=[
            "Latin milium (millet)",
            "Proto-Indo-European *mel- (to grind, to crush)",
        ],
        cognates=[
            "English 'millet' (from Old French millet, from Latin milium)",
            "English 'mill' (from the same PIE root *mel- via Latin mola)",
            "Spanish 'mijo' (millet — the old crop, whereas 'maíz' is used for corn)",
        ],
        semantic_shift=(
            "'millet (the Old World grain)' → in Portuguese, transferred to "
            "mean maize/corn upon contact with the Americas"
        ),
    ),
    EtymologyEntry(
        language="pt", lemma="naufrágio",
        origin_summary=(
            "From Latin naufragium (a shipwreck), from navis (a ship) + "
            "frangere (to break). A naufrágio is a shipwreck — literally "
            "'ship-breaking.' The Latin compound navis + frangere captures "
            "the catastrophe in its parts. Portugal's maritime empire was "
            "built on ships that navigated the most dangerous seas in the "
            "world; naufrágio was not a hypothetical word but a constant "
            "reality of the Age of Discovery."
        ),
        roots=[
            "Latin navis (a ship)",
            "Latin frangere (to break, to shatter)",
        ],
        cognates=[
            "English 'nave' (the central hall of a church — shaped like an inverted ship)",
            "English 'navigate' (from navis + agere)",
            "English 'fracture' (from frangere)",
            "Spanish 'naufragio' (shipwreck, same Latin compound)",
        ],
        semantic_shift=(
            "'ship-breaking event' → a shipwreck; by extension, any "
            "catastrophic failure or ruin"
        ),
    ),
    EtymologyEntry(
        language="pt", lemma="esquerda",
        origin_summary=(
            "From Basque ezker (left hand, the left side), borrowed into "
            "Ibero-Romance languages during the medieval period. The Latin "
            "sinister (left) was displaced in Iberian Portuguese and Spanish "
            "by the Basque loanword — perhaps because sinister had "
            "accumulated too many ominous connotations. Esquerda (left, the "
            "political left) entered Portuguese from a pre-Indo-European "
            "Basque substrate."
        ),
        roots=["Basque ezker (the left hand, the left side)"],
        cognates=[
            "Spanish 'izquierda' (left — from the same Basque ezker)",
            "Portuguese 'direita' (right — from Latin directa, by contrast)",
        ],
        semantic_shift="Basque 'left hand' → left direction → the political left",
    ),
    EtymologyEntry(
        language="pt", lemma="marmelada",
        origin_summary=(
            "From Portuguese marmelo (quince) + -ada (a preparation made "
            "from), from Latin melimelum (honey-apple), from Greek melímēlon "
            "(a sweet apple grafted onto quince), from méli (honey) + mēlon "
            "(apple). The English word 'marmalade' was borrowed directly from "
            "Portuguese marmelada — originally a quince paste. When the "
            "British began making it with oranges, they kept the Portuguese "
            "word but changed the fruit."
        ),
        roots=[
            "Greek melímēlon (honey-apple — a quince grafted with an apple)",
            "Greek méli (honey) + mēlon (an apple)",
            "Latin melimelum (honey-apple, sweet apple)",
        ],
        cognates=[
            "English 'marmalade' (borrowed directly from Portuguese marmelada, now made with citrus)",
            "English 'melon' (from the same Greek mēlon)",
        ],
        semantic_shift=(
            "'honey-apple (a grafted quince)' → quince paste (marmelada) → "
            "English borrowed it for any citrus preserve"
        ),
    ),
    EtymologyEntry(
        language="pt", lemma="calçada",
        origin_summary=(
            "From Latin calciata (paved with limestone), from calx/calcis "
            "(limestone, chalk). Calçada is a paved road, a cobbled pavement, "
            "or a sidewalk. The famous Calçada Portuguesa — hand-laid black "
            "and white limestone cobblestone patterns — is one of Portugal's "
            "most distinctive art forms, found on Lisbon's streets, "
            "Copacabana beach in Rio, and Portuguese communities worldwide."
        ),
        roots=[
            "Latin calx/calcis (limestone, chalk)",
            "Latin calciata (paved with lime-stone)",
        ],
        cognates=[
            "English 'calcium' (from Latin calx, the same limestone)",
            "English 'chalk' (from Latin calx, via Germanic)",
            "Portuguese 'cal' (lime — directly from Latin calx)",
        ],
        semantic_shift=(
            "'paved with limestone' → a paved road or cobbled surface; "
            "specifically the Portuguese decorative stone pavement art"
        ),
    ),

    # ── RU additions (generated by gen_etymology.py) ──
    EtymologyEntry(
        language="ru", lemma="медведь",
        origin_summary=(
            "From Proto-Slavic *medvědь, a compound of *medъ (honey) + "
            "*věděti (to know). The Russian word for 'bear' literally means "
            "'the honey-knower' — an ancient Slavic taboo replacement for the "
            "real name of the bear (*orktos, cognate with Greek arktos), "
            "which was considered too dangerous to speak aloud. This "
            "euphemistic replacement is one of the oldest recorded examples "
            "of linguistic taboo in European languages."
        ),
        roots=[
            "Proto-Slavic *medъ (honey)",
            "Proto-Slavic *věděti (to know, to be aware of)",
        ],
        cognates=[
            "Russian 'мёд' (honey — the first root)",
            "English 'mead' (the honey drink, from PIE *médʰu)",
            "Greek 'arktos' (bear — the suppressed original word)",
        ],
        semantic_shift=(
            "'honey-knower' → euphemistic replacement for the taboo word for "
            "bear → the standard word for bear in Slavic languages"
        ),
    ),
    EtymologyEntry(
        language="ru", lemma="белка",
        origin_summary=(
            "From Proto-Slavic *bělъ (white), related to *běliti (to whiten). "
            "The squirrel was 'the white one' — likely referring to the white "
            "winter coat of the squirrel or the valuable white underbelly of "
            "the squirrel pelt. Squirrel pelts were used as currency in "
            "medieval Rus'; the word for squirrel overlapped conceptually "
            "with the word for a small unit of value."
        ),
        roots=[
            "Proto-Slavic *bělъ (white)",
            "PIE *bʰelH- (to shine, to flash, white)",
        ],
        cognates=[
            "Russian 'белый' (white — the same root)",
            "Russian 'Белоруссия' (Belarus — the 'White Russia')",
            "English 'beluga' (the white whale/sturgeon — from Russian белуга, same *bělъ root)",
        ],
        semantic_shift=(
            "'the white one' (referring to white pelt) → the squirrel → in "
            "medieval Rus', also a unit of currency (a squirrel skin)"
        ),
    ),
    EtymologyEntry(
        language="ru", lemma="берёза",
        origin_summary=(
            "From Proto-Slavic *berza, from PIE *bʰerHĝ- (to shine, to glow "
            "white). The birch tree is the 'shining' or 'bright white' tree — "
            "named for the distinctive white bark that made it instantly "
            "recognizable across the northern forests. The birch is one of "
            "the most culturally central trees in Slavic cultures, associated "
            "with spring, youth, and female beauty."
        ),
        roots=[
            "Proto-Slavic *berza (birch)",
            "PIE *bʰerHĝ- (to shine, to be white, to gleam)",
        ],
        cognates=[
            "English 'birch' (from Proto-Germanic *birkijō, same PIE root)",
            "German 'Birke' (birch)",
            "Sanskrit 'bhūrja' (a type of birch, same PIE root)",
        ],
        semantic_shift=(
            "PIE 'shining/white' → the white-barked birch tree; culturally "
            "central to Russian and Slavic identity"
        ),
    ),
    EtymologyEntry(
        language="ru", lemma="волк",
        origin_summary=(
            "From Proto-Slavic *vьlkъ, from PIE *wĺ̥kʷos (wolf). The wolf was "
            "one of the most feared and respected animals in the Eurasian "
            "steppe — it figures prominently in Slavic folklore as a liminal "
            "creature between the human village and the wild forest. PIE "
            "*wĺ̥kʷos is one of the most widely attested PIE animal words, "
            "surviving in nearly every branch of the family."
        ),
        roots=["Proto-Slavic *vьlkъ (wolf)", "PIE *wĺ̥kʷos (wolf)"],
        cognates=[
            "English 'wolf' (from Proto-Germanic *wulfaz, same PIE root)",
            "Latin 'lupus' (wolf — *lúkʷos, same root with initial shift)",
            "Greek 'lykos' (wolf — Lycaon, the wolf-king myth)",
        ],
        semantic_shift=(
            "PIE word for the wolf → unchanged in Russian (волк) through "
            "6,000 years"
        ),
    ),
    EtymologyEntry(
        language="ru", lemma="буря",
        origin_summary=(
            "From Proto-Slavic *burja (storm, tempest), related to *bьrati "
            "(to bubble, to boil), from PIE *bʰrewh₁- (to boil, to bubble, to "
            "be in violent motion). A буря is a storm or gale — the boiling, "
            "seething motion of air. The same PIE root gives English 'brew,' "
            "'broth,' and 'burn' — all words for turbulent, heated motion."
        ),
        roots=[
            "Proto-Slavic *burja (storm)",
            "PIE *bʰrewh₁- (to boil, to bubble, to seethe)",
        ],
        cognates=[
            "English 'brew' (from Proto-Germanic *breuwaną, same PIE root)",
            "English 'broth' (boiled liquid, same root)",
            "German 'Brause' (a fizzy drink, a shower — related)",
        ],
        semantic_shift=(
            "'boiling, seething motion' → a violent storm or gale; "
            "figuratively, turbulent emotion"
        ),
    ),
    EtymologyEntry(
        language="ru", lemma="изба",
        origin_summary=(
            "From Old Slavic *jьstъba or *jьzba, borrowed from a Germanic "
            "source related to Old High German stuba (a warm room, a heated "
            "chamber), from the same root as English 'stove.' An изба is the "
            "traditional Russian peasant log hut, centered on a large stove. "
            "The borrowed word traveled eastward from Germanic tribes and "
            "came to define the archetypal dwelling of rural Russia."
        ),
        roots=[
            "Old High German stuba (a warm room, a bathhouse)",
            "Proto-Germanic *stubō (a heated room)",
        ],
        cognates=[
            "English 'stove' (a heated enclosure — from the same Germanic root)",
            "German 'Stube' (a room, a parlor — the same word)",
            "Dutch 'stoof' (a foot-warmer, same family)",
        ],
        semantic_shift=(
            "Germanic 'heated room' → borrowed into Slavic → the Russian "
            "peasant log house, defined by its central stove"
        ),
    ),
    EtymologyEntry(
        language="ru", lemma="кремль",
        origin_summary=(
            "From Old Russian кремль or кром (the inner fortified citadel of "
            "a Russian city). The origin is debated: possibly from a Turkic "
            "root (compare Crimean Tatar qirim = a cliff, a fortification) or "
            "from Old Russian кремъ (a strong wood used in fortification). "
            "Every major Russian medieval city had a kremlin — its inner "
            "citadel. The Moscow Kremlin became synonymous with Russian state "
            "power."
        ),
        roots=[
            "Old Russian кром/кремль (inner citadel, fortified core of a city)",
            "possibly Turkic qirim (a fortification, a cliff)",
        ],
        cognates=[
            "Russian 'Кремль' (specifically the Moscow Kremlin)",
            "Russian 'кромка' (an edge, a border — possibly related)",
        ],
        semantic_shift=(
            "a fortified inner citadel (any Russian city) → specifically the "
            "Moscow Kremlin → the Russian government itself"
        ),
    ),
    EtymologyEntry(
        language="ru", lemma="мёд",
        origin_summary=(
            "From Proto-Slavic *medъ (honey), from PIE *médʰu (honey, mead — "
            "the honey drink). One of the oldest inherited words in Russian, "
            "mead and honey were central to ancient Slavic economy, religion, "
            "and feasting culture. The PIE root *médʰu is among the best- "
            "attested PIE words — found from Sanskrit madhu to Greek methy to "
            "English mead."
        ),
        roots=[
            "Proto-Slavic *medъ (honey)",
            "PIE *médʰu (honey, the honey drink)",
        ],
        cognates=[
            "English 'mead' (the fermented honey drink, from Proto-Germanic *meduz)",
            "Sanskrit 'madhu' (honey, sweet)",
            "Greek 'methy' (wine, from the same root — methyl alcohol)",
        ],
        semantic_shift=(
            "PIE 'honey / honey-drink' → Russian мёд = honey (the substance); "
            "медовуха = the drink"
        ),
    ),
    EtymologyEntry(
        language="ru", lemma="молния",
        origin_summary=(
            "From Proto-Slavic *mъldьni or *moldьni (lightning), from *mьlti "
            "(to grind, to crush), related to the root *mel- (to grind). "
            "Lightning was conceptualized as a grinding or crushing force — "
            "the grinding of the sky. The suffix -ния is a verbal noun "
            "ending. Perun, the Slavic thunder god, wielded lightning as his "
            "weapon; молния retains something of the mythological power of "
            "sky-grinding."
        ),
        roots=[
            "Proto-Slavic *mьlti (to grind, to crush)",
            "PIE *melh₂- (to grind, to crush — the same root as mill)",
        ],
        cognates=[
            "Russian 'молоть' (to grind — the same root)",
            "English 'mill' (from PIE *melh₂- via Latin)",
            "Latin 'mola' (a millstone — related)",
        ],
        semantic_shift=(
            "'the grinding/crushing (of the sky)' → lightning; the instrument "
            "of the Slavic thunder god"
        ),
    ),
    EtymologyEntry(
        language="ru", lemma="муж",
        origin_summary=(
            "From Proto-Slavic *mǫžь (a man, a husband), from PIE *manus (a "
            "human being, a man). Муж means both 'husband' and, in "
            "elevated/archaic usage, 'a man of distinction.' The PIE root "
            "*manus gave Sanskrit मनु (Manu — the first man), Latin mas/maris "
            "(male), and Gothic manna. The narrowing from 'human' to "
            "'husband' is a common pattern across Indo-European languages."
        ),
        roots=[
            "Proto-Slavic *mǫžь (a man, a husband)",
            "PIE *manus (a human being, a man)",
        ],
        cognates=[
            "Sanskrit 'Manu' (the first man, humanity)",
            "English 'man' (from Proto-Germanic *mann-, same PIE root)",
            "German 'Mann' (man, husband)",
        ],
        semantic_shift=(
            "PIE 'a human being, a man' → Proto-Slavic 'a man; a husband' → "
            "Russian муж = husband (and literary 'a man of stature')"
        ),
    ),
    EtymologyEntry(
        language="ru", lemma="орёл",
        origin_summary=(
            "From Proto-Slavic *orьlъ (eagle), from PIE *h₃ér-o- (a large "
            "bird, possibly from *h₃er- = to stir into motion, to rise). The "
            "eagle was the bird of power and sovereignty across Indo-European "
            "cultures. In Russian heraldry, the double-headed eagle "
            "(двуглавый орёл) has been the symbol of Russia since the 15th "
            "century, adopted from the Byzantine Empire."
        ),
        roots=[
            "Proto-Slavic *orьlъ (eagle)",
            "PIE *h₃er- (to stir, to put into motion — possibly)",
        ],
        cognates=[
            "German 'Adler' (eagle — from Old High German adal-aro = noble-eagle)",
            "Latin 'aquila' (eagle — the Roman legionary standard)",
        ],
        semantic_shift=(
            "PIE 'a great bird in motion' → the eagle → symbol of imperial "
            "Russia"
        ),
    ),
    EtymologyEntry(
        language="ru", lemma="поле",
        origin_summary=(
            "From Proto-Slavic *polje (a flat open field), from PIE *pelH- "
            "(flat, to spread flat). Поле is an open field — culturally "
            "essential to the agricultural Russian landscape. The great open "
            "fields of the Russian steppe define the geography and the soul "
            "of Russian culture. The word appears in countless Russian place "
            "names (Ставрополь = 'city of the cross/field') and in set "
            "expressions (поле боя = battlefield, поле деятельности = field "
            "of activity)."
        ),
        roots=[
            "Proto-Slavic *polje (open field)",
            "PIE *pelH- (flat, to spread out flat)",
        ],
        cognates=[
            "Polish 'pole' (field — Poland takes its name from this word: land of fields)",
            "English 'fallow' (from Proto-Germanic *falwaz = pale flat land, related PIE root)",
            "Latin 'palma' (the flat of the hand — same root)",
        ],
        semantic_shift=(
            "PIE 'flat surface' → an open field; in Polish, a national name "
            "(Poland = land of fields)"
        ),
    ),
    EtymologyEntry(
        language="ru", lemma="пчела",
        origin_summary=(
            "From Proto-Slavic *bьčela (a bee), from PIE *bʰey- (to strike, "
            "to sting — the bee as the stinging insect). An older Slavic form "
            "бъчела is attested; the initial б- simplified. The bee was "
            "sacred in early Slavic culture — honey (мёд) was the primary "
            "sweetener and the basis of mead. Beekeeping (пчеловодство) was "
            "one of the oldest Slavic livelihoods."
        ),
        roots=[
            "Proto-Slavic *bьčela (bee)",
            "PIE *bʰey- (to strike, to sting)",
        ],
        cognates=[
            "English 'bee' (from Proto-Germanic *bijō, same PIE root)",
            "Latin 'apis' (bee — from a different PIE root, giving 'apiary')",
            "German 'Biene' (bee, same PIE root as English 'bee')",
        ],
        semantic_shift=(
            "PIE 'the stinging one' → the honeybee; central to Slavic "
            "agriculture and ritual"
        ),
    ),
    EtymologyEntry(
        language="ru", lemma="работа",
        origin_summary=(
            "From Proto-Slavic *orbota (labor, servitude), from *orbъ (a "
            "serf, a slave, an orphan — one stripped of kin-protection), from "
            "PIE *h₃órbʰos (a child who has lost a father, an orphan). The "
            "root of 'work' in Slavic languages is etymologically connected "
            "to slavery and orphanhood — those without the protection of kin "
            "were compelled to labor for others. The same root gives 'robot' "
            "(Czech for 'forced labor') and 'orphan.'"
        ),
        roots=[
            "Proto-Slavic *orbъ (serf, slave, orphan)",
            "PIE *h₃órbʰos (one deprived of father/kin — an orphan)",
        ],
        cognates=[
            "Czech 'robot' (forced labor → mechanical labor-doer, coined by Karel Čapek in 1920)",
            "German 'Arbeit' (work — from the same Proto-Germanic root)",
            "English 'orphan' (from Greek orphanos, same PIE root)",
        ],
        semantic_shift=(
            "PIE 'an orphan (one compelled to labor)' → forced labor, "
            "servitude → work in general"
        ),
    ),
    EtymologyEntry(
        language="ru", lemma="рыба",
        origin_summary=(
            "From Proto-Slavic *ryba (fish), of uncertain ultimate origin — "
            "possibly from an Indo-European root *reubh- (to tear), "
            "describing the slippery, tearing motion of a fish, or possibly a "
            "Baltic-Slavic substrate word. Рыба is culturally central to "
            "Russian life — the great river systems (Volga, Ob, Yenisei) and "
            "their fish defined Russian settlement patterns. Рыба appears in "
            "dozens of Russian idioms (ни рыба ни мясо = neither fish nor "
            "flesh = a nonentity)."
        ),
        roots=[
            "Proto-Slavic *ryba (fish)",
            "possibly PIE *reubh- (to tear, to scratch — uncertain)",
        ],
        cognates=[
            "Lithuanian 'rỹbas' (fish — from Baltic, confirming the Baltic-Slavic root)",
            "Latvian 'zivs' (fish — a different word, showing the root was not universal)",
        ],
        semantic_shift=(
            "Slavic word for fish → any fish; metaphorically, a cold or "
            "expressionless person (холодная рыба)"
        ),
    ),
    EtymologyEntry(
        language="ru", lemma="снег",
        origin_summary=(
            "From Proto-Slavic *sněgъ (snow), from PIE *sneygʷʰ- (to snow, "
            "snow). Snow is central to Russian identity, climate, and culture "
            "— Russia has some of the longest and harshest winters of any "
            "major civilization. The PIE root *sneygʷʰ- is remarkably well "
            "preserved across Indo-European: English snow, German Schnee, "
            "Latin nix/nivis, Greek nipha all descend from the same ancestor."
        ),
        roots=[
            "Proto-Slavic *sněgъ (snow)",
            "PIE *sneygʷʰ- (snow, to snow)",
        ],
        cognates=[
            "English 'snow' (from Proto-Germanic *snaiwaz, same PIE root)",
            "German 'Schnee' (snow)",
            "Latin 'nix/nivis' (snow — giving 'Nevada', the snowy range)",
        ],
        semantic_shift=(
            "PIE 'snow' → unchanged in Russian; culturally central to Russian "
            "experience"
        ),
    ),
    EtymologyEntry(
        language="ru", lemma="собака",
        origin_summary=(
            "Origin disputed and unusual — most likely borrowed from an "
            "Iranian or Scythian source (compare Median *spaka = dog, "
            "attested in Herodotus' account of Cyrus the Great's foster- "
            "mother Spako). The native Slavic word for dog was *pьsъ "
            "(surviving in Russian 'пёс'). Собака displaced the native word "
            "and is now the standard term — one of the few cases where a "
            "loanword completely replaced a PIE-inherited animal name."
        ),
        roots=[
            "possibly Iranian/Scythian *spaka (a dog — attested in Herodotus)",
        ],
        cognates=[
            "Russian 'пёс' (a dog — the older native Slavic word, now more informal or poetic)",
            "Median 'Spako' (the name of Cyrus's foster-mother, meaning 'bitch/dog')",
        ],
        semantic_shift=(
            "Iranian/Scythian word for dog → borrowed into Slavic → displaced "
            "the native PIE word пёс as the standard term"
        ),
    ),
    EtymologyEntry(
        language="ru", lemma="соль",
        origin_summary=(
            "From Proto-Slavic *solь (salt), from PIE *séh₂ls (salt). Salt "
            "was one of the most economically and culturally vital "
            "commodities in pre-modern Russia — it preserved food through "
            "long winters, and entire trade routes were built around salt "
            "supply. The Slavic word for salt is one of the oldest continuous "
            "PIE roots, essentially unchanged for 6,000 years: Latin sal, "
            "Greek halas, English salt, Russian соль all descend from the "
            "same ancestor."
        ),
        roots=["Proto-Slavic *solь (salt)", "PIE *séh₂ls (salt)"],
        cognates=[
            "English 'salt' (from Proto-Germanic *saltą, same PIE root)",
            "Latin 'sal' (salt — giving 'salary', originally salt payment)",
            "English 'salary' (from Latin salarium — salt money paid to soldiers)",
        ],
        semantic_shift=(
            "PIE 'salt' → Russian соль; idiomatically 'the essential thing' "
            "(суть соли = the crux)"
        ),
    ),
    EtymologyEntry(
        language="ru", lemma="стол",
        origin_summary=(
            "From Proto-Slavic *stolъ (a seat of power, a throne, a raised "
            "surface), from *stojati (to stand), from PIE *steh₂- (to stand). "
            "The original meaning was a raised seat — a throne or high seat. "
            "The meaning shifted from 'throne' to 'table' (a raised flat "
            "surface). In old texts, стол means a princely seat: Киевский "
            "стол = the Kievan throne. The dual memory of throne and table "
            "persists in Russian expressions."
        ),
        roots=[
            "Proto-Slavic *stolъ (a seat of power, a high seat)",
            "PIE *steh₂- (to stand, to be placed)",
        ],
        cognates=[
            "English 'stall' (a standing place — from the same root via Germanic)",
            "German 'Stuhl' (a chair — from the same Germanic family)",
            "English 'install' (to place in a seat — from the same PIE root)",
        ],
        semantic_shift=(
            "'a raised seat of power (a throne)' → 'a raised flat surface (a "
            "table)' — the democratization of the noble seat"
        ),
    ),
    EtymologyEntry(
        language="ru", lemma="тайга",
        origin_summary=(
            "From Turkic or Mongolian tayga (a dense coniferous forest on "
            "marshy ground), possibly from Yakut or Buryat. Тайга entered "
            "Russian through contact with Siberian peoples as Russian "
            "expansion moved eastward across Siberia in the 17th century. The "
            "word then entered all European languages from Russian — "
            "scientists and geographers adopted the Russian term for the vast "
            "boreal forest biome that stretches from Norway to the Pacific."
        ),
        roots=[
            "Turkic/Mongolian tayga (a dense northern coniferous forest)",
        ],
        cognates=[
            "English 'taiga' (borrowed from Russian tayga)",
            "French 'taïga' (from Russian)",
            "German 'Taiga' (from Russian)",
        ],
        semantic_shift=(
            "Siberian Turkic/Mongolian term for marshy dense forest → Russian "
            "word for the boreal forest zone → international scientific term "
            "adopted from Russian"
        ),
    ),
    EtymologyEntry(
        language="ru", lemma="тундра",
        origin_summary=(
            "From Sámi or Finnish tundar/tundra (a treeless upland plateau), "
            "possibly from Proto-Sámi *tūntēr (a high treeless fell). Like "
            "тайга, тундра was adopted by Russians expanding into Siberia and "
            "the Arctic north — the vast treeless plains between the Arctic "
            "Ocean and the taiga. The word then passed from Russian into all "
            "scientific European languages as the standard term for this "
            "biome."
        ),
        roots=[
            "Sámi tundar or Finnish tuntura (a treeless hill, a high fell)",
        ],
        cognates=[
            "English 'tundra' (from Russian тундра)",
            "German 'Tundra' (from Russian)",
        ],
        semantic_shift=(
            "Finno-Ugric/Sámi word for a treeless highland → Russian borrowed "
            "it for the Arctic flatlands → international scientific term"
        ),
    ),
    EtymologyEntry(
        language="ru", lemma="царь",
        origin_summary=(
            "From Old Church Slavonic цѣсарь, from a Gothic *kaisar, which "
            "was borrowed from Latin Caesar (the family name of Julius "
            "Caesar, later a title for Roman emperors). Caesar → Gothic "
            "kaisar → Old Slavic цѣсарь → Russian царь (with regular sound "
            "changes). The title passed from Rome to Byzantium, from "
            "Byzantium to Bulgarian and Serbian kingdoms, and finally to "
            "Moscow — Ivan IV (Ivan the Terrible) declared himself Tsar of "
            "all Rus in 1547."
        ),
        roots=[
            "Latin Caesar (the proper name of Gaius Julius Caesar, used as a title)",
            "Gothic *kaisar (emperor — borrowed from Latin)",
        ],
        cognates=[
            "German 'Kaiser' (emperor — from the same Gothic/Latin source)",
            "English 'Caesar' (the original name → title → Russian tsar)",
            "Arabic 'qaysar' (emperor — from the same Latin Caesar via Byzantine)",
        ],
        semantic_shift=(
            "Roman family name → imperial title → Gothic Kaiser → Slavic "
            "цѣсарь → Russian царь = the Russian emperor"
        ),
    ),
    EtymologyEntry(
        language="ru", lemma="чудо",
        origin_summary=(
            "From Proto-Slavic *čudo (a wonder, a miracle, a strange sight), "
            "of uncertain PIE origin — possibly from *ḱewdʰ- (to notice, to "
            "perceive acutely). A чудо is a miracle or wonder. The word "
            "permeates Russian religious vocabulary (чудотворец = miracle- "
            "worker, чудесный = miraculous/wonderful) and folk tales (Чудо- "
            "Юдо = the Wonder-Beast, a monster in Slavic folklore). The line "
            "between marvel and monster is thin."
        ),
        roots=["Proto-Slavic *čudo (a marvel, a wonder)"],
        cognates=[
            "Old English 'cyþan' (to make known, to announce — possibly related via PIE *ḱewdʰ-)",
            "Russian 'чудовище' (a monster — literally 'a terrible wonder')",
        ],
        semantic_shift=(
            "'a marvel, a supernatural wonder' → a miracle; also a monstrous "
            "creature (чудовище = monster)"
        ),
    ),
    EtymologyEntry(
        language="ru", lemma="яблоко",
        origin_summary=(
            "From Proto-Slavic *ablъko (apple), from PIE *h₂ébōl or *h₂ébl- "
            "(apple). Apple is one of the most widely attested PIE words — "
            "the fruit was cultivated across the Eurasian continent and named "
            "with a word that survives in nearly every Indo-European branch: "
            "English apple, German Apfel, Welsh afall, Russian яблоко all "
            "from the same ancestor. In Slavic folklore, the gold яблоко is a "
            "magical object — a golden apple — in countless fairy tales."
        ),
        roots=[
            "Proto-Slavic *ablъko (apple)",
            "PIE *h₂ébōl (apple — one of the most widespread PIE cultural words)",
        ],
        cognates=[
            "English 'apple' (from Proto-Germanic *aplaz, same PIE root)",
            "German 'Apfel' (apple)",
            "Welsh 'afall' (apple tree — from the same Celtic root that gives 'Avalon')",
        ],
        semantic_shift=(
            "PIE 'apple' → Russian яблоко; in Slavic folklore, the golden "
            "apple (золотое яблоко) is a magical object"
        ),
    ),
    EtymologyEntry(
        language="ru", lemma="язык",
        origin_summary=(
            "From Proto-Slavic *językъ (tongue, language), from PIE "
            "*dn̥ĝʰwéh₂s (tongue). The same word means both the physical "
            "tongue and language itself — one of the most conceptually "
            "fundamental synecdoches in Indo-European languages. In Old "
            "Russian, the word also meant 'people' or 'nation' (a foreign "
            "nation = чужой язык). The semantic range tongue → language → "
            "people reflects how language defines ethnic identity."
        ),
        roots=[
            "Proto-Slavic *językъ (tongue, language)",
            "PIE *dn̥ĝʰwéh₂s (the tongue as an organ)",
        ],
        cognates=[
            "Latin 'lingua' (tongue, language — from a different form of the same PIE root)",
            "English 'tongue' (from Proto-Germanic *tungōn, same PIE root)",
            "English 'language' (ultimately from Latin lingua)",
        ],
        semantic_shift=(
            "PIE 'the tongue (organ)' → language in general; in Old Russian "
            "also 'a people, a nation' (those who speak a tongue)"
        ),
    ),
    EtymologyEntry(
        language="ru", lemma="урок",
        origin_summary=(
            "From Old Russian урокъ (a fixed term, an appointed time, a "
            "doom), from у- (prefix indicating completion or setting) + рокъ "
            "(fate, doom, a fixed date), from рещи (to pronounce, to decree). "
            "The рок in урок is the same рок as судьбы рок (the doom of "
            "fate). A урок (lesson) was originally a fixed appointment — an "
            "assigned task with a deadline. The transformation from 'a doom' "
            "to 'a school lesson' is a remarkable semantic journey through "
            "bureaucratic Russian."
        ),
        roots=[
            "Old Russian рокъ (fate, doom, a fixed time)",
            "Proto-Slavic *rekti (to speak, to pronounce, to decree)",
        ],
        cognates=[
            "Russian 'рок' (fate, doom — the same root, as in 'рок-музыка' meaning fate-music/rock)",
            "Russian 'нарок' (intention, deliberately)",
            "Czech 'rok' (a year — a fixed period)",
        ],
        semantic_shift=(
            "'a decreed appointment, a fixed term' → a task assigned with a "
            "deadline → a school lesson"
        ),
    ),
    EtymologyEntry(
        language="ru", lemma="дух",
        origin_summary=(
            "From Proto-Slavic *duxъ (breath, spirit, soul), from PIE *dʰewH- "
            "(to blow, to breathe). Дух means spirit, breath, or ghost — the "
            "animating breath. The concept of breath as the soul or life- "
            "force is ancient and cross-cultural. In Russian, дух covers a "
            "wide range: courage (падать духом = to lose heart/spirit), smell "
            "(чем-то пахнет, в воздухе витает дух), and the supernatural "
            "(злой дух = an evil spirit)."
        ),
        roots=[
            "Proto-Slavic *duxъ (breath, spirit)",
            "PIE *dʰewH- (to blow, to breathe, to create a draft)",
        ],
        cognates=[
            "Latin 'animus' (spirit, breath — different root but same concept)",
            "Greek 'thymos' (spirit, soul — from the same PIE root *dʰewH-)",
            "English 'dust' (from Proto-Germanic *dustaz — related to the blowing/drifting root)",
        ],
        semantic_shift=(
            "'breath, air in motion' → the animating life-force (spirit, "
            "soul) → courage; also: a smell or atmosphere"
        ),
    ),
    EtymologyEntry(
        language="ru", lemma="заря",
        origin_summary=(
            "From Proto-Slavic *zorja (the dawn glow, the aurora), from "
            "*zorěti (to glow, to shine), from PIE *ǵʰer- or *ǵʰelH- (to "
            "shine, to glow). Заря is the dawn — both the morning glow and "
            "the evening twilight. In Russian folk and literary tradition, "
            "the зари personified as maidens — the Slavic dawn goddess Zarya. "
            "The word also gives Аврора, though that is from Latin Aurora."
        ),
        roots=[
            "Proto-Slavic *zorja (the glow of dawn)",
            "PIE *ǵʰelH- or *ǵʰer- (to glow, to shine yellow)",
        ],
        cognates=[
            "Russian 'зарево' (a glow on the horizon, a lurid light)",
            "Greek 'khrysos' (gold — from the same PIE shining root)",
            "English 'yellow' (from PIE *ǵʰelH- via Germanic)",
        ],
        semantic_shift=(
            "PIE 'glow, shine' → the glow of dawn and dusk → in folklore, the "
            "personified dawn maiden"
        ),
    ),
    EtymologyEntry(
        language="ru", lemma="звезда",
        origin_summary=(
            "From Proto-Slavic *gvězda (a star), from PIE *h₂wes-tereh₂ (a "
            "star, the evening star). The PIE root *h₂wes- meant to shine, to "
            "glitter — the star as the glittering thing. Звезда is culturally "
            "central: the five-pointed red star (пятиконечная звезда) was the "
            "symbol of the Soviet Union. In Russian folklore, stars (звёзды) "
            "are souls or fate-markers — 'родился под счастливой звездой' "
            "(born under a lucky star)."
        ),
        roots=[
            "Proto-Slavic *gvězda (star)",
            "PIE *h₂wes-tereh₂ (the evening star, a star — from *h₂wes- = to gleam)",
        ],
        cognates=[
            "Latin 'stella' (star — from *sterH₂-, a parallel PIE root)",
            "Greek 'aster' (star — giving 'asterisk', 'asteroid', 'astronomy')",
            "English 'star' (from Proto-Germanic *sternō, same PIE root)",
        ],
        semantic_shift=(
            "PIE 'the shining/glittering one' → a star; Soviet five-pointed "
            "red star → symbol of communist ideology"
        ),
    ),
    EtymologyEntry(
        language="ru", lemma="лебедь",
        origin_summary=(
            "From Proto-Slavic *lebedь (swan), from PIE *elbʰo- (white). The "
            "swan is 'the white bird' — the same root gives Latin albus "
            "(white) and Welsh elfyn (white). In Russian folklore, the swan "
            "(лебедь) is a symbol of feminine beauty, grace, and "
            "faithfulness: Царевна-Лебедь (the Swan-Princess) is one of the "
            "most beloved Slavic fairy-tale figures, immortalized in "
            "Tchaikovsky's Swan Lake."
        ),
        roots=[
            "Proto-Slavic *lebedь (swan)",
            "PIE *elbʰo- (white, shining)",
        ],
        cognates=[
            "Latin 'albus' (white — same PIE root)",
            "Welsh 'alarch' (swan — from the same Celtic form)",
            "English 'elf' (possibly from the same *elbʰo- root — elves as the shining ones)",
        ],
        semantic_shift=(
            "PIE 'the white one' → the white swan → in Russian folklore, the "
            "epitome of graceful female beauty"
        ),
    ),
    EtymologyEntry(
        language="ru", lemma="луна",
        origin_summary=(
            "From Proto-Slavic *luna (the moon), from PIE *lewk- (light, to "
            "shine). Луна is the moon — the shining night light. The PIE root "
            "*lewk- gives a vast family of light-words: Latin lux (light), "
            "lucere (to shine), luna (moon), English 'light,' 'lucid,' "
            "'illuminate' — all from the same shining ancestor. In Russian, "
            "луна is the celestial body while месяц (month) is also used for "
            "the moon in its lunar-month aspect."
        ),
        roots=["Proto-Slavic *luna (moon)", "PIE *lewk- (light, to shine)"],
        cognates=[
            "Latin 'luna' (moon — same word, same PIE root)",
            "Latin 'lux' (light)",
            "English 'light' (from Proto-Germanic *leuhtą, same PIE root)",
            "English 'lunatic' (from luna — the moon as the cause of madness)",
        ],
        semantic_shift="PIE 'the shining one' → the moon as the night-shining body",
    ),
    EtymologyEntry(
        language="ru", lemma="метель",
        origin_summary=(
            "From Proto-Slavic *metati (to sweep, to throw, to hurl), from "
            "PIE *met- (to sweep, to mow). A метель is a blizzard or "
            "snowstorm — the wind sweeping and hurling snow across the "
            "landscape. The image of the Russian blizzard as a sweeping force "
            "is deeply literary: Pushkin's 'Метель' (The Blizzard) and "
            "Pasternak's blizzard poetry both channel the метель as an "
            "overwhelming, disorienting force of nature."
        ),
        roots=[
            "Proto-Slavic *metati (to sweep, to throw)",
            "PIE *met- (to sweep, to mow, to cut down)",
        ],
        cognates=[
            "Russian 'мести' (to sweep — the immediate root)",
            "English 'mow' (from Proto-Germanic *mēaną, same PIE root)",
            "Russian 'подметать' (to sweep up — same family)",
        ],
        semantic_shift=(
            "'to sweep, to hurl' → a sweeping snowstorm; in Russian "
            "literature, an emblem of overwhelming natural and historical "
            "force"
        ),
    ),
    EtymologyEntry(
        language="ru", lemma="меч",
        origin_summary=(
            "From Proto-Slavic *mečь (a sword), of uncertain origin — "
            "possibly from a Germanic source (compare Old High German mezzi- "
            "rahs = a table knife, a cutting blade) or from an unknown "
            "Scythian or Sarmatian root. The sword was the central weapon and "
            "symbol of Slavic warrior culture. In Russian Orthodox "
            "Christianity, the sword of St. Michael and the Archangel's меч "
            "are iconic. Мечтать (to dream, to fantasize) may be unrelated "
            "despite the similar spelling."
        ),
        roots=[
            "Proto-Slavic *mečь (sword)",
            "possibly Germanic mezzi-rahs (a cutting blade) or Iranian/Scythian origin",
        ],
        cognates=[
            "Polish 'miecz' (sword)",
            "Serbian 'мач' (sword)",
            "possibly Old High German 'mezzi' (a knife, a blade)",
        ],
        semantic_shift=(
            "a cutting sword → the archetypal warrior's weapon in Slavic "
            "culture; symbol of justice and divine power"
        ),
    ),
    EtymologyEntry(
        language="ru", lemma="мороз",
        origin_summary=(
            "From Proto-Slavic *morzъ (frost, freezing), from *mьrznǫti (to "
            "freeze), from PIE *mer- (to flicker, to die — cold as a deadly "
            "force). Мороз is the sharp, penetrating Russian frost — not just "
            "cold but the life-threatening freeze of a Russian winter. Дед "
            "Мороз (Grandfather Frost) is the Russian equivalent of Father "
            "Christmas — the personified winter cold who brings gifts, a "
            "figure of great power and seasonal awe."
        ),
        roots=[
            "Proto-Slavic *morzъ (frost)",
            "PIE *mer- (to die, to fade — the deadly cold)",
        ],
        cognates=[
            "Russian 'умереть' (to die — from the same PIE *mer- root)",
            "Latin 'mors/mortis' (death — same PIE root)",
            "English 'murder' (from PIE *mr̥dhro- = a killing, same root)",
        ],
        semantic_shift=(
            "PIE 'death-cold, deadly frost' → Russian winter frost; Дед Мороз "
            "= the benevolent but powerful personification of winter"
        ),
    ),
    EtymologyEntry(
        language="ru", lemma="мост",
        origin_summary=(
            "From Proto-Slavic *mostъ (a bridge, a plank walkway over wet "
            "ground), from PIE *mod-to- or *mond- (a bridge, a causeway). A "
            "мост is a bridge. The word is ancient — bridges over rivers and "
            "marshes were among the most important infrastructure of early "
            "Slavic life. Novgorod ('new city') and its bridges over the "
            "Volkhov were central to its political life; the famous Novgorod "
            "Bridge was a site of judicial combat."
        ),
        roots=[
            "Proto-Slavic *mostъ (bridge, causeway)",
            "PIE *mod- or *mond- (a raised walkway, a causeway)",
        ],
        cognates=[
            "Lithuanian 'mãstas' (a ford, a crossing)",
            "possibly Latin 'moles' (a massive structure, a breakwater — debated)",
        ],
        semantic_shift=(
            "PIE 'a raised crossing over wet ground' → a bridge; "
            "strategically and symbolically central to Russian geography"
        ),
    ),
    EtymologyEntry(
        language="ru", lemma="мышь",
        origin_summary=(
            "From Proto-Slavic *myšь (a mouse), from PIE *mūs (mouse). One of "
            "the most stable PIE words — mouse has barely changed in 6,000 "
            "years. Latin mus, Greek mys, Sanskrit mūṣ, English mouse, "
            "Russian мышь all descend from the same PIE *mūs. In computer "
            "terminology, компьютерная мышь (computer mouse) translates the "
            "English term directly — keeping the same animal metaphor."
        ),
        roots=["Proto-Slavic *myšь (mouse)", "PIE *mūs (mouse)"],
        cognates=[
            "English 'mouse' (from Proto-Germanic *mūs, same PIE root)",
            "Latin 'mus' (mouse)",
            "English 'muscle' (from Latin musculus = a little mouse, from the shape of a flexed muscle under skin)",
        ],
        semantic_shift=(
            "PIE 'mouse' → Russian мышь; extended to 'computer mouse' by "
            "direct calque"
        ),
    ),
    EtymologyEntry(
        language="ru", lemma="облако",
        origin_summary=(
            "From Proto-Slavic *oblakъ (a cloud), from *ob-volkti (to drag "
            "over, to cover), from *volčь (to drag, to pull), from PIE *welk- "
            "(to drag, to be wet and dragging). A cloud is literally 'that "
            "which is dragged over' the sky. The same root *volčь gives "
            "Russian волочь (to drag) and влечь (to pull). The image of "
            "clouds as a dragging veil across the sky is ancient and vivid."
        ),
        roots=[
            "Proto-Slavic *ob-volkti (to drag over, to envelop)",
            "PIE *welk- (to drag, wet and heavy)",
        ],
        cognates=[
            "Russian 'волочь' (to drag — the direct root)",
            "Russian 'облачение' (vestments — what is draped over a priest, same root)",
            "possibly English 'welkin' (the sky/clouds in poetic English, from Old English)",
        ],
        semantic_shift="'that which is dragged/draped over (the sky)' → a cloud",
    ),
    EtymologyEntry(
        language="ru", lemma="окно",
        origin_summary=(
            "From Proto-Slavic *okъno (a window), from *oko (an eye), from "
            "PIE *h₃ekʷ- (to see, the eye). A window is literally 'an eye (of "
            "the building)' — the metaphor of windows as a building's eyes is "
            "ancient and cross-cultural. The same root gives Greek ops (eye), "
            "Latin oculus (eye), and English 'eye.' In Russian folklore, the "
            "window is a liminal space — spirits enter through windows, "
            "brides are traditionally associated with the window as a "
            "threshold."
        ),
        roots=["Proto-Slavic *oko (eye)", "PIE *h₃ekʷ- (to see, the eye)"],
        cognates=[
            "Greek 'ops/ophis' (eye, the visual faculty)",
            "Latin 'oculus' (eye — giving 'ocular', 'binoculars')",
            "English 'eye' (from Proto-Germanic *augō, same PIE root)",
        ],
        semantic_shift=(
            "'the eye (of the building)' → a window opening; in folklore, a "
            "liminal threshold between inside and outside"
        ),
    ),
    EtymologyEntry(
        language="ru", lemma="отец",
        origin_summary=(
            "From Proto-Slavic *otьcь (father), a diminutive/affectionate "
            "form of *otъ (a father, a patriarch), from PIE *ph₂tér (father). "
            "The PIE word for father is one of the most stable and widely "
            "attested roots in the language family: Sanskrit pitár, Greek "
            "patēr, Latin pater, English father, Russian отец all from the "
            "same source. The Russian form went through a diminutive suffix, "
            "giving it a more intimate quality than the formal Latin pater."
        ),
        roots=[
            "Proto-Slavic *otьcь (father, a diminutive-affectionate form)",
            "PIE *ph₂tér (father — one of the most stable PIE kinship terms)",
        ],
        cognates=[
            "English 'father' (from Proto-Germanic *fader, same PIE root)",
            "Latin 'pater' (father)",
            "Greek 'patēr' (father — giving 'patriarch', 'patron', 'patriot')",
        ],
        semantic_shift=(
            "PIE 'father' → Russian отец; also used as a respectful address "
            "to priests (отец Николай)"
        ),
    ),
    EtymologyEntry(
        language="ru", lemma="перо",
        origin_summary=(
            "From Proto-Slavic *pero (a feather, a quill), from PIE *peth₂- "
            "(to fly, to spread out like wings). Перо means both a feather "
            "and a pen (quill pen). The same PIE root *peth₂- gives Greek "
            "pteron (wing, feather), Sanskrit pátati (it flies), Latin penna "
            "(feather, quill — giving 'pen'). The trajectory from flying to "
            "writing is shared across European languages — the quill feather "
            "was the universal writing instrument."
        ),
        roots=[
            "Proto-Slavic *pero (feather, quill)",
            "PIE *peth₂- (to fly, to spread like wings)",
        ],
        cognates=[
            "Greek 'pteron' (wing, feather — giving 'pterodactyl', 'helicopter')",
            "Latin 'penna' (feather, quill — giving English 'pen')",
            "English 'feather' (from Proto-Germanic *feþrō, same PIE root)",
        ],
        semantic_shift=(
            "PIE 'flying/wing' → feather → quill pen → any pen; in modern "
            "Russian, also a nib or tip of a pen"
        ),
    ),
    EtymologyEntry(
        language="ru", lemma="погода",
        origin_summary=(
            "From Proto-Slavic *pogoda (favorable weather, a convenient "
            "time), from *po- (a completive prefix) + *goda (a suitable time, "
            "a season), from *godъ (a year, a proper time), from PIE *gʰedʰ- "
            "(to unite, to be fitting). Originally, погода meant good weather "
            "— fair and suitable conditions. The meaning shifted to 'weather "
            "in general' (any weather) in Russian, while related words like "
            "'never mind' (не гоже = not fitting) preserve the original sense "
            "of suitability."
        ),
        roots=[
            "Proto-Slavic *godъ (a year, a proper time, a season)",
            "PIE *gʰedʰ- (to fit together, to be suitable)",
        ],
        cognates=[
            "Russian 'год' (year — from the same *godъ root)",
            "Russian 'подходит' (it suits — from the same root family)",
            "English 'good' (from Proto-Germanic *gōdaz — debated connection to the same PIE root)",
        ],
        semantic_shift=(
            "'fitting/favorable conditions' → weather in general (any "
            "atmospheric conditions)"
        ),
    ),
    EtymologyEntry(
        language="ru", lemma="право",
        origin_summary=(
            "From Proto-Slavic *pravo (right, straightness, justice), from "
            "*pravъ (straight, correct, right), from PIE *pro- (forward, "
            "before) + *H₁- (straight). Право means law, right (legal or "
            "moral), and also 'right' as opposed to 'left.' The root *pravъ "
            "(straight) connects physical direction (right direction = "
            "correct direction) with legal correctness. Правда (truth) is "
            "from the same root — truth as that which is straight/correct."
        ),
        roots=[
            "Proto-Slavic *pravъ (straight, correct, right)",
            "PIE *preh₂- (straight, forward, true)",
        ],
        cognates=[
            "Russian 'правда' (truth — from the same root, already in store)",
            "Russian 'правительство' (government — from править, to rule/govern, same family)",
            "Latin 'probus' (upright, honest — from the same PIE root)",
        ],
        semantic_shift=(
            "'straight, correct' → the right direction; legal right; law and "
            "justice (the body of что правильно = what is correct)"
        ),
    ),
    EtymologyEntry(
        language="ru", lemma="птица",
        origin_summary=(
            "From Proto-Slavic *pьtica (a bird), from *pьtъ (a bird), from "
            "PIE *peth₂- (to fly). Птица (bird) shares the root *peth₂- with "
            "перо (feather) — both the bird and its feather come from the "
            "same flying root. The alternation between пт- and пер- in "
            "Russian traces back to different suffixation of the same PIE "
            "flying-root. Russian идиoms treat birds as symbols of freedom "
            "(вольная птица = a free person)."
        ),
        roots=[
            "Proto-Slavic *pьtica (bird)",
            "PIE *peth₂- (to fly, to spread as wings)",
        ],
        cognates=[
            "Russian 'перо' (feather — the same PIE root, differently suffixed)",
            "Greek 'pteron' (wing — same PIE root)",
            "Latin 'penna' (feather — same root)",
        ],
        semantic_shift=(
            "PIE 'flying' → a bird (the flying creature); idiomatically, a "
            "free or unconstrained person"
        ),
    ),
    EtymologyEntry(
        language="ru", lemma="рай",
        origin_summary=(
            "From Old Iranian *rāy- (wealth, prosperity, abundance) or from "
            "Avestan rayi (riches, paradise). Alternatively derived through "
            "Old Church Slavonic from Greek paradise (παράδεισος), which "
            "itself came from Old Iranian pairidaēza (a walled garden, an "
            "enclosed paradise). Рай is paradise — the Christian heaven but "
            "also the Garden of Eden. The Iranian concept of paradise as an "
            "enclosed, abundant garden profoundly shaped Semitic and then "
            "Christian imagery."
        ),
        roots=[
            "Old Iranian *rāy- or Avestan rayi (riches, prosperity, paradise-like abundance)",
            "or through Greek from Iranian pairidaēza (an enclosed garden)",
        ],
        cognates=[
            "English 'paradise' (via Greek paradeisos, from Iranian pairidaēza)",
            "Persian 'bihisht' (paradise — a different Iranian word for the same concept)",
        ],
        semantic_shift=(
            "Iranian 'abundant garden, prosperity' → the Garden of Eden; the "
            "Christian/Islamic heaven; any idyllic place"
        ),
    ),
    EtymologyEntry(
        language="ru", lemma="род",
        origin_summary=(
            "From Proto-Slavic *rodъ (birth, kin, family, generation, clan), "
            "from *roditi (to give birth), from PIE *Hrod- or *ǵenh₁- (to "
            "give birth, to engender). Род is one of the deepest and most "
            "productive roots in Russian — it generates an enormous word "
            "family: родина (homeland), народ (people/nation), природа "
            "(nature, literally 'that which is born alongside'), урожай "
            "(harvest). Род was also an ancient Slavic deity of fate and "
            "generation."
        ),
        roots=[
            "Proto-Slavic *rodъ (birth, kin, clan)",
            "PIE *Hrod- (birth, generation)",
        ],
        cognates=[
            "Russian 'родина' (homeland — 'the place of birth')",
            "Russian 'природа' (nature — 'that which is born alongside')",
            "Russian 'народ' (people/nation — born together)",
            "Latin 'natio' (birth, nation — the same concept from Latin nasci = to be born)",
        ],
        semantic_shift=(
            "'birth, the act of being born' → kin, clan; → people as those "
            "born together; → nature as what is born organically"
        ),
    ),
    EtymologyEntry(
        language="ru", lemma="рубль",
        origin_summary=(
            "From Russian рубить (to chop, to cut), from Proto-Slavic *rǫbiti "
            "(to cut, to hack). A рубль (ruble) was originally a chopped-off "
            "piece of a silver гривна (a silver ingot or neck ring) — the "
            "medieval Russian monetary system involved literally hacking "
            "silver bars into pieces of known weight. The ruble is "
            "etymologically a 'chopped piece.' The word has been the name of "
            "Russian currency since the 13th century."
        ),
        roots=[
            "Proto-Slavic *rǫbiti (to chop, to cut)",
            "Russian 'рубить' (to chop, to hack — the direct root)",
        ],
        cognates=[
            "Russian 'рубить' (to chop — the verb)",
            "Russian 'сруб' (a log cabin — logs chopped to build)",
            "Russian 'рубец' (a scar — where flesh has been cut)",
        ],
        semantic_shift=(
            "'a chopped piece' (of a silver ingot) → the name of the Russian "
            "monetary unit → Russia's currency from the 13th century to today"
        ),
    ),
    EtymologyEntry(
        language="ru", lemma="свет",
        origin_summary=(
            "From Proto-Slavic *světъ (light, the world), from PIE *ḱweyto- "
            "(bright, shining). Свет means both light (the illumination) and "
            "the world (весь свет = the whole world). The semantic connection "
            "between light and the world is ancient — the world is the "
            "illuminated space, the sphere of light. Russian говорит на свет "
            "= to give birth (to bring into the light). На белом свете = in "
            "the wide world (in the white light)."
        ),
        roots=[
            "Proto-Slavic *světъ (light; the world, the illuminated space)",
            "PIE *ḱweyto- (bright, shining white)",
        ],
        cognates=[
            "Russian 'священный' (sacred — from the same root: the shining/holy)",
            "English 'white' (from Proto-Germanic *hwītaz, same PIE root *ḱweyto-)",
            "Sanskrit 'śveta' (white — same PIE root)",
        ],
        semantic_shift=(
            "PIE 'shining white' → light → 'the world' (the illuminated "
            "sphere of existence)"
        ),
    ),
    EtymologyEntry(
        language="ru", lemma="слава",
        origin_summary=(
            "From Proto-Slavic *slava (glory, fame, renown), from *slovo "
            "(word, speech), from PIE *ḱlew- (to hear, to be heard — fame as "
            "what is heard about someone). Слава is glory or fame — "
            "etymologically, that which is spoken and heard about a person. "
            "The Slavic name-root *slav- appears in countless Slavic personal "
            "names: Vladislav (ruling-fame), Yaroslav (fierce-fame), "
            "Sviatoslav (holy-fame) — the Slavic nobility was literally named "
            "for glory."
        ),
        roots=[
            "Proto-Slavic *slava (glory, fame)",
            "PIE *ḱlew- (to hear, to be renowned — fame as what is widely heard)",
        ],
        cognates=[
            "Russian 'слово' (word — the root), already in store",
            "Greek 'kleos' (glory, fame — from the same PIE *ḱlew-)",
            "English 'loud' (from Proto-Germanic *hludaz = heard, renowned, same PIE root)",
        ],
        semantic_shift=(
            "PIE 'to be heard widely' → fame, renown → glory; embedded in "
            "Slavic personal names as a marker of noble status"
        ),
    ),
    EtymologyEntry(
        language="ru", lemma="страна",
        origin_summary=(
            "From Proto-Slavic *strana (a side, a region, a country), from "
            "*stornъ (turned to one side), from PIE *ster- (to extend, to "
            "spread out, to stretch). A страна is a country or land — "
            "literally a 'side' or expanse. The word captures the spatial "
            "concept of a country as an extended region facing a particular "
            "direction. Иностранец (a foreigner) = 'one from another "
            "side/страна.' На стороне = on one's side; на той стороне = on "
            "the other side."
        ),
        roots=[
            "Proto-Slavic *strana (a side, a region)",
            "PIE *ster- (to extend, to spread)",
        ],
        cognates=[
            "Russian 'сторона' (a side — the immediate root word)",
            "German 'Strand' (a beach, a shore — from the same spreading root)",
            "English 'strand' (a shore, a beach — same PIE *ster-)",
        ],
        semantic_shift=(
            "'a side, an extended region' → a country, a land; in compounds: "
            "иностранец (a foreigner = one from another страна)"
        ),
    ),
    EtymologyEntry(
        language="ru", lemma="жена",
        origin_summary=(
            "From Proto-Slavic *žena (a woman, a wife), from PIE *gʷén-eh₂ (a "
            "woman). Жена means wife in modern Russian, but the older meaning "
            "is simply 'a woman.' The PIE root *gʷén- is one of the most "
            "widespread Indo-European words for woman: Greek gynē (woman), "
            "English queen (from Proto-Germanic *kwenō = woman), Persian zan "
            "(woman), Sanskrit jáni (woman) — all from the same ancestor."
        ),
        roots=[
            "Proto-Slavic *žena (woman, wife)",
            "PIE *gʷén-eh₂ (a woman)",
        ],
        cognates=[
            "Greek 'gynē' (woman — giving 'gynecology')",
            "English 'queen' (from Proto-Germanic *kwenō = a woman, a queen)",
            "Persian 'zan' (woman)",
            "English 'banshee' (from Irish bean sí = fairy woman, bean = woman, same PIE root)",
        ],
        semantic_shift=(
            "PIE 'a woman' → in Russian: a wife (the primary modern meaning), "
            "though 'женщина' (a woman in general) retains the broader sense"
        ),
    ),
    EtymologyEntry(
        language="ru", lemma="зеркало",
        origin_summary=(
            "From Old Russian зерцало, from *zьrěti (to look, to gaze), from "
            "PIE *ǵerh₂- (to call out, to perceive). A зеркало is a mirror — "
            "literally 'the gazing thing.' The formation from 'to look' to "
            "'the thing you look in' is transparent. In Russian literature "
            "and folklore, зеркало is a quintessential magical object — the "
            "mirror that speaks truth (Пушкин's 'Сказка о мёртвой царевне' "
            "has the iconic magic mirror)."
        ),
        roots=[
            "Old Russian *zьrěti (to look, to see, to gaze)",
            "PIE *ǵerh₂- or *dhers- (perception, vision)",
        ],
        cognates=[
            "Russian 'взор' (a gaze, a look — from the same root)",
            "Russian 'зрение' (sight, vision — the same root)",
            "Russian 'обозревать' (to survey — from the same family)",
        ],
        semantic_shift=(
            "'the gazing instrument' → a mirror; in Russian folklore, the "
            "archetype of truth-telling magical objects"
        ),
    ),
    EtymologyEntry(
        language="ru", lemma="нога",
        origin_summary=(
            "From Proto-Slavic *noga (a leg, a foot), from PIE *nōgʷ- or "
            "*nōg- (a hoof, a nail, a claw — the hard tip of a limb). The "
            "same PIE root gives nail (as in fingernail/toenail) and hoof "
            "across Indo-European — the hard keratinous end of a limb. "
            "Russian нога covers both leg and foot (the entire lower limb), "
            "while нога as a word is related to ноготь (a nail/claw)."
        ),
        roots=[
            "Proto-Slavic *noga (leg, foot)",
            "PIE *nōgʷ- (hoof, nail, claw — the hard end of a limb)",
        ],
        cognates=[
            "English 'nail' (fingernail/toenail — from Proto-Germanic *naglaz, same PIE root)",
            "Latin 'unguis' (a nail, a claw — same PIE root)",
            "Russian 'ноготь' (a fingernail — directly from the same root)",
        ],
        semantic_shift=(
            "PIE 'the hard-tipped limb/hoof' → the leg/foot (the entire lower "
            "limb in Russian)"
        ),
    ),
    EtymologyEntry(
        language="ru", lemma="остров",
        origin_summary=(
            "From Proto-Slavic *ostrovъ (an island), from *ostrъ (sharp, "
            "pointed) — an island as the sharp point of land emerging from "
            "water, or from *ob-strovъ (that which is surrounded by a "
            "current). The etymology links острый (sharp) with острог (a "
            "palisaded fort — sharp pointed stakes) and остров (island). "
            "Russian river geography — islands in major rivers like the Volga "
            "— made острова (islands) important navigational landmarks."
        ),
        roots=[
            "Proto-Slavic *ostrъ (sharp, pointed)",
            "Proto-Slavic *ob-strovъ (that which is surrounded by a current — alternative)",
        ],
        cognates=[
            "Russian 'острый' (sharp — the same root)",
            "Russian 'острог' (a palisade fort — sharp pointed stakes, same root)",
            "possibly related to Proto-Germanic *austr- (east — the direction of the rising sun, a sharpening dawn)",
        ],
        semantic_shift="'sharp point (of land)' or 'surrounded by current' → an island",
    ),
    EtymologyEntry(
        language="ru", lemma="порог",
        origin_summary=(
            "From Proto-Slavic *porgъ (a threshold, a step, a rapid in a "
            "river), from *per- (through, across) + *ag- (to drive, to move). "
            "A порог is a doorstep or threshold (the step you cross), and "
            "also a rapid in a river (an obstacle you must navigate through). "
            "The Dnieper rapids (Днепровские пороги) were a famous obstacle "
            "on the trade route from Varangians to Greeks — the Viking name "
            "for each rapid was recorded in Byzantine sources."
        ),
        roots=[
            "Proto-Slavic *porgъ (a threshold, river rapids)",
            "Proto-Slavic *per- (through, across)",
        ],
        cognates=[
            "Russian 'перейти порог' (to cross the threshold)",
            "Greek records of the Dnieper rapids names (Βαρούφορος, etc. — the rapids as пороги)",
            "possibly related to English 'ford' (a crossing — a similar concept)",
        ],
        semantic_shift=(
            "'the crossing point' → a doorstep/threshold; also a river rapid "
            "(an obstacle one must cross); figuratively, a critical point"
        ),
    ),
    EtymologyEntry(
        language="ru", lemma="луч",
        origin_summary=(
            "From Proto-Slavic *lučь (a ray of light, a beam), from *lučiti "
            "(to send out, to shoot), possibly related to PIE *lewk- (light) "
            "or to *leuk- (to throw, to direct). A луч is a ray of light, a "
            "beam. The word is used scientifically (рентгеновский луч = "
            "X-ray), poetically (луч надежды = a ray of hope), and "
            "practically. The image of a ray as something sent or shot "
            "through space connects light and motion."
        ),
        roots=[
            "Proto-Slavic *lučь (a ray, a beam)",
            "possibly PIE *lewk- (light) or *leuk- (to shoot, to direct)",
        ],
        cognates=[
            "Russian 'лучший' (better, best — from *lučь in the sense of 'more directed/optimal')",
            "Russian 'случай' (a chance, an occurrence — from the same root family)",
            "Russian 'получить' (to receive — to 'obtain a directed thing')",
        ],
        semantic_shift=(
            "'a beam sent/directed' → a ray of light; also figuratively: a "
            "ray of hope, an X-ray"
        ),
    ),
    EtymologyEntry(
        language="ru", lemma="берлога",
        origin_summary=(
            "From Proto-Slavic *berlogъ (a bear's den), a compound of *berъ "
            "(bear — an older taboo form related to *medvědь) + *logъ (a "
            "lair, a lying-down place), from *lěgati (to lie down). A берлога "
            "is specifically a bear's hibernation den — where the bear lies "
            "through winter. The word preserves the archaic root *berъ for "
            "bear (which was itself a euphemism, later replaced by the more "
            "famous honey-knower euphemism медведь)."
        ),
        roots=[
            "Proto-Slavic *berъ (an old word for bear — a taboo form)",
            "Proto-Slavic *logъ (a lair, a place to lie down)",
        ],
        cognates=[
            "German 'Bär' (bear — from the same Proto-Germanic root *beron, cognate with *berъ)",
            "English 'bear' (from Proto-Germanic *beron — the same ancient bear-root)",
            "Russian 'логово' (a lair, a den — from the same *logъ)",
        ],
        semantic_shift=(
            "'a bear's lying-down place' → a bear's hibernation den; "
            "informally, a messy room or a hermit's retreat"
        ),
    ),
    EtymologyEntry(
        language="ru", lemma="оружие",
        origin_summary=(
            "From Proto-Slavic *orǫžьje (a weapon, arms), from *orǫdьje (a "
            "tool, an implement), from *rǫka (hand) — weapons as the "
            "instruments of the hand. Оружие (weapons, arms) is "
            "etymologically connected to Russian рука (hand) — weapons are "
            "the 'hand-things,' the instruments wielded by hand. The semantic "
            "field of hands and tools overlaps: оружие (weapon), орудие "
            "(tool), рукоять (handle) all from the same root."
        ),
        roots=[
            "Proto-Slavic *orǫdьje (a tool, a hand-instrument)",
            "Proto-Slavic *rǫka (hand — the grasping limb)",
        ],
        cognates=[
            "Russian 'рука' (hand — the immediate root, already in store)",
            "Russian 'орудие' (a tool, an instrument — same root)",
            "Russian 'рукоять' (a handle — hand-thing)",
        ],
        semantic_shift=(
            "'a hand-instrument, a tool' → specifically a weapon (the "
            "fighting hand-tool)"
        ),
    ),
    EtymologyEntry(
        language="ru", lemma="ужас",
        origin_summary=(
            "From Proto-Slavic *užasъ (horror, terror, a shuddering fright), "
            "from *užasnǫti (to be seized by horror), from *uz- (an "
            "intensifying prefix) + *gasiti (to extinguish) or from *žasъ (a "
            "fright). A ужас is a horror or terror — it describes extreme, "
            "sudden fear. In Russian, ужас! is also used as an exclamation of "
            "distress ('how awful!'). The ужас in Russian Romantic and Gothic "
            "literature — ночной ужас (the night terror) — is a specific "
            "aesthetic and emotional register."
        ),
        roots=[
            "Proto-Slavic *žasъ (a fright, a terror)",
            "Proto-Slavic *uz- (an intensifying/completive prefix)",
        ],
        cognates=[
            "Russian 'ужасный' (horrible, terrible — from the same root)",
            "Russian 'ужаснуться' (to be horrified — the reflexive verb)",
        ],
        semantic_shift=(
            "'a sudden overwhelming fright' → horror, terror; colloquially, "
            "any strongly unpleasant thing"
        ),
    ),
    EtymologyEntry(
        language="ru", lemma="ухо",
        origin_summary=(
            "From Proto-Slavic *ucho (ear), from PIE *h₂ewis (the faculty of "
            "hearing, the ear). The PIE root *h₂ewis is ancient and stable — "
            "preserved as Latin auris (ear), English ear, Greek ous/otos "
            "(ear), Russian ухо. The ear as a listening instrument is "
            "culturally coded in Russian: держать ухо востро (to keep one's "
            "ear sharp) = to be on guard; за ушко да на солнышко (by the "
            "little ear into the sun) = to expose someone."
        ),
        roots=[
            "Proto-Slavic *ucho (ear)",
            "PIE *h₂ewis (the ear, the hearing faculty)",
        ],
        cognates=[
            "Latin 'auris' (ear — giving 'aural', 'auricle')",
            "English 'ear' (from Proto-Germanic *ausō, same PIE root)",
            "Greek 'ous/otos' (ear — giving 'otology', ear medicine)",
        ],
        semantic_shift=(
            "PIE 'the hearing organ' → the ear; figuratively, attention and "
            "awareness (держать ухо востро = stay alert)"
        ),
    ),

    # ── IT additions (generated by gen_etymology.py) ──
    EtymologyEntry(
        language="it", lemma="crescendo",
        origin_summary=(
            "From Latin crescere (to grow, to increase). The present "
            "participle crescendo entered musical vocabulary to indicate a "
            "gradual increase in volume or intensity. Italian musicians' "
            "dominance of European concert life in the 17th–18th centuries "
            "made Italian tempo and dynamic markings the international "
            "standard."
        ),
        roots=["Latin crescere (to grow, to increase, to arise)"],
        cognates=[
            "English 'increase' (from Latin increscere)",
            "English 'decrease' (decrescere)",
            "English 'concrete' (past participle of concrescere = to grow together)",
        ],
        semantic_shift="'growing' → musical instruction for gradually increasing volume",
    ),
    EtymologyEntry(
        language="it", lemma="adagio",
        origin_summary=(
            "From Italian a (at) + agio (ease, leisure), itself from Old "
            "French aise (ease) or possibly from Gothic roots. The phrase a "
            "proprio agio (at one's own ease) contracted to adagio. In music, "
            "designates a slow, stately tempo. Also used as a standalone noun "
            "for a slow movement."
        ),
        roots=[
            "Italian a (at, to)",
            "Italian agio (ease, convenience, leisure)",
        ],
        cognates=[
            "French 'aise' (ease, comfort)",
            "English 'adagio' (borrowed directly)",
        ],
        semantic_shift="'at ease, at leisure' → musical direction for slow tempo",
    ),
    EtymologyEntry(
        language="it", lemma="andante",
        origin_summary=(
            "From the present participle of andare (to go, to walk). Andante "
            "literally means 'going' or 'walking.' As a musical term it "
            "indicates a moderately slow, walking pace — slower than "
            "moderato, faster than adagio. The motion metaphor is central to "
            "musical tempo language."
        ),
        roots=[
            "Italian andare (to go, to walk), of uncertain ultimate origin — possibly from Latin ambulare or Gaulish andare",
        ],
        cognates=[
            "Spanish 'andar' (to walk)",
            "Portuguese 'andar' (to walk, also a floor/storey)",
        ],
        semantic_shift=(
            "'walking, going' → musical instruction for a moderate walking "
            "pace"
        ),
    ),
    EtymologyEntry(
        language="it", lemma="staccato",
        origin_summary=(
            "Past participle of staccare (to detach, to separate), from Old "
            "French destachier (to unfasten) — prefix dis- + attachier. In "
            "music, staccato indicates that notes should be played in a "
            "clipped, detached manner, each shortened and separated from the "
            "next."
        ),
        roots=[
            "Italian staccare (to detach)",
            "Old French destachier (to unfasten)",
        ],
        cognates=[
            "English 'detach' (from Old French destachier)",
            "Italian 'attaccare' (to attach, also to attack musically)",
        ],
        semantic_shift=(
            "'detached, separated' → musical articulation of short, clipped "
            "notes"
        ),
    ),
    EtymologyEntry(
        language="it", lemma="legato",
        origin_summary=(
            "Past participle of legare (to tie, to bind), from Latin ligare "
            "(to bind). Legato in music indicates that notes should be played "
            "smoothly connected, without breaks between them — the opposite "
            "of staccato. The binding metaphor captures the seamless melodic "
            "flow."
        ),
        roots=["Latin ligare (to bind, to tie)"],
        cognates=[
            "English 'ligament' (a binding tissue)",
            "English 'league' (an alliance — those 'bound' together)",
            "Spanish 'ligar' (to bind)",
        ],
        semantic_shift="'tied, bound' → musical articulation of smooth, connected notes",
    ),
    EtymologyEntry(
        language="it", lemma="sonata",
        origin_summary=(
            "From the past participle of sonare (to sound, to play), from "
            "Latin sonare (to make a sound). A sonata is literally 'something "
            "sounded' — a purely instrumental piece, contrasted with cantata "
            "('something sung'). The distinction between sounded and sung "
            "became a fundamental form-based category in Western music."
        ),
        roots=["Latin sonare (to sound, to make noise)"],
        cognates=[
            "English 'sound' (from Old English sund/Latin sonus)",
            "English 'sonorous' (full of sound)",
            "Italian 'risuonare' (to resound)",
        ],
        semantic_shift="'sounded' → a multi-movement instrumental composition",
    ),
    EtymologyEntry(
        language="it", lemma="aria",
        origin_summary=(
            "From Latin aer (air, atmosphere), via Italian aria (air, tune, "
            "melody). In opera, an aria is a self-contained vocal piece for a "
            "single singer with orchestral accompaniment. The 'air' metaphor "
            "for melody appears in Italian, French (air), and English (air = "
            "tune) — breath as the vehicle of song."
        ),
        roots=["Latin aer (air, atmosphere)", "Greek aēr (mist, air)"],
        cognates=[
            "French 'air' (air, tune, melody)",
            "English 'aria' (borrowed from Italian)",
            "English 'airy' (light, melodious)",
        ],
        semantic_shift="'air, breath' → operatic solo song",
    ),
    EtymologyEntry(
        language="it", lemma="mezzo",
        origin_summary=(
            "From Latin medius (middle, half). In music, mezzo means 'half' "
            "or 'medium' — as in mezzo-soprano (half-soprano, a middle-range "
            "female voice), mezzo-forte (medium-loud), mezzo-piano (medium- "
            "soft). The prefix enters English musical vocabulary directly "
            "from Italian."
        ),
        roots=["Latin medius (middle, central, half)"],
        cognates=[
            "English 'medium' (from Latin medius)",
            "French 'mi-' (half, as in mi-chemin = halfway)",
            "Spanish 'medio' (half, middle)",
        ],
        semantic_shift=(
            "'middle, half' → musical prefix indicating moderation of an "
            "instruction"
        ),
    ),
    EtymologyEntry(
        language="it", lemma="toccata",
        origin_summary=(
            "From the past participle of toccare (to touch), from a Vulgar "
            "Latin *toccare (to knock, to touch), possibly from a Germanic "
            "root. A toccata is a keyboard composition that 'touches' the "
            "keys — originally a piece designed to demonstrate the player's "
            "technique with rapid, freely structured passages."
        ),
        roots=[
            "Vulgar Latin *toccare (to touch, to knock)",
            "possibly from Germanic *tukkōn (to tug)",
        ],
        cognates=[
            "English 'touch' (from Old French touchier, same Germanic base)",
            "French 'touche' (key, touch)",
            "Spanish 'tocar' (to play an instrument, to touch)",
        ],
        semantic_shift=(
            "'touched, played' → a virtuosic keyboard piece with free "
            "structure"
        ),
    ),
    EtymologyEntry(
        language="it", lemma="campanile",
        origin_summary=(
            "From Italian campana (bell), from Late Latin campana, probably "
            "from Campania, the region of Italy where bell-founding was "
            "prominent. A campanile is a freestanding bell tower, often "
            "architecturally independent from the church it serves — the "
            "Leaning Tower of Pisa being the most famous example."
        ),
        roots=[
            "Late Latin campana (bell)",
            "toponym Campania (Italian region known for bell manufacture)",
        ],
        cognates=[
            "English 'campanology' (the study of bells)",
            "Spanish 'campana' (bell)",
            "French 'campane' (bell, archaic)",
        ],
        semantic_shift="'bell' → freestanding tower housing bells",
    ),
    EtymologyEntry(
        language="it", lemma="cupola",
        origin_summary=(
            "From Latin cupula (a small tub, cask), diminutive of cupa (tub, "
            "barrel). The rounded shape of a barrel upturned became the "
            "architectural metaphor for a dome. Italian cupola was borrowed "
            "into English both as 'cupola' (a small dome or turret) and "
            "indirectly influenced 'couple' via different paths."
        ),
        roots=["Latin cupa (tub, barrel, cask)"],
        cognates=[
            "English 'cupola' (a small dome)",
            "English 'cooper' (barrel-maker, from the same Latin root)",
            "Spanish 'cúpula' (dome)",
        ],
        semantic_shift="'small tub or barrel' → a rounded dome or domed structure",
    ),
    EtymologyEntry(
        language="it", lemma="fresco",
        origin_summary=(
            "From Italian fresco (fresh, cool), from a Germanic root *friskaz "
            "(fresh). The painting technique buon fresco (true fresco) "
            "involves painting onto wet plaster while it is still fresh — the "
            "pigments bond chemically with the drying plaster, making the "
            "image permanent. The modifier 'fresh' refers to the plaster "
            "state."
        ),
        roots=["Germanic *friskaz (fresh, vigorous)"],
        cognates=[
            "English 'fresh' (from Old French freis, same Germanic root)",
            "German 'frisch' (fresh)",
            "English 'alfresco' (in the fresh air, outdoors — from Italian al fresco)",
        ],
        semantic_shift="'fresh' → a wall-painting technique using wet plaster",
    ),
    EtymologyEntry(
        language="it", lemma="chiaroscuro",
        origin_summary=(
            "From Italian chiaro (light, clear) + oscuro (dark, obscure). "
            "Chiaroscuro is the artistic technique of using strong contrasts "
            "between light and shadow to model three-dimensional forms. "
            "Mastered by Leonardo da Vinci and Caravaggio, it revolutionized "
            "European painting and became a foundational concept of art "
            "criticism."
        ),
        roots=[
            "Latin clarus (clear, bright)",
            "Latin obscurus (dark, hidden)",
        ],
        cognates=[
            "English 'clear' (from Latin clarus)",
            "English 'obscure' (from Latin obscurus)",
            "English 'chiaroscuro' (borrowed directly)",
        ],
        semantic_shift=(
            "'light-dark' → the artistic modelling of form through contrast "
            "of light and shadow"
        ),
    ),
    EtymologyEntry(
        language="it", lemma="sfumato",
        origin_summary=(
            "Past participle of sfumare (to evaporate, to shade off), from "
            "fumo (smoke), from Latin fumus (smoke). Sfumato is Leonardo da "
            "Vinci's technique of blurring outlines and allowing tones to "
            "shade into each other softly — like smoke dissolving into air. "
            "The Mona Lisa's enigmatic expression is largely achieved through "
            "sfumato."
        ),
        roots=["Latin fumus (smoke, vapor)"],
        cognates=[
            "English 'fume' (from Latin fumus)",
            "Italian 'fumo' (smoke)",
            "Spanish 'humo' (smoke, same Latin root)",
        ],
        semantic_shift=(
            "'smoked, evaporated' → Leonardo's painting technique of blurred, "
            "smoke-like outlines"
        ),
    ),
    EtymologyEntry(
        language="it", lemma="bruschetta",
        origin_summary=(
            "From the Roman dialect bruscare (to roast over coals), from "
            "brace (embers), which may share a root with French braise "
            "(embers). The dish of toasted bread rubbed with garlic and "
            "drizzled with olive oil is named for the toasting technique, not "
            "the toppings."
        ),
        roots=[
            "Roman bruscare (to toast over embers)",
            "brace (embers, hot coals)",
        ],
        cognates=[
            "French 'braise' (embers, from which 'braise' → 'braise' → 'braise' in cooking)",
            "English 'braise/braise' (to braise — cook over embers)",
        ],
        semantic_shift="'toasted over coals' → a dish of toasted bread with toppings",
    ),
    EtymologyEntry(
        language="it", lemma="gelato",
        origin_summary=(
            "Past participle of gelare (to freeze), from Latin gelare (to "
            "freeze, to congeal). Gelato is literally 'frozen' — Italian for "
            "the dense, slow-churned ice cream with less air than American- "
            "style ice cream. The word's direct Latin root distinguishes it "
            "from 'ice cream' etymologically."
        ),
        roots=["Latin gelare (to freeze, to congeal)"],
        cognates=[
            "English 'gel' (from the same root, via gelatin)",
            "English 'gelatin' (from Latin gelare)",
            "English 'jelly' (via Old French gelee, frozen thing)",
        ],
        semantic_shift="'frozen' → dense Italian-style frozen dessert",
    ),
    EtymologyEntry(
        language="it", lemma="prosciutto",
        origin_summary=(
            "From Latin perexsuctus (thoroughly dried out) — per (thoroughly) "
            "+ exsuctus (past participle of exsugere, to suck out, to dry "
            "out). Prosciutto is dry-cured ham aged by drawing out moisture "
            "over months, which the etymology captures precisely. The word "
            "entered Italian cuisine from the production region of Parma and "
            "San Daniele."
        ),
        roots=[
            "Latin perexsuctus (thoroughly dried)",
            "Latin per (thoroughly, through)",
            "Latin exsugere (to suck out, to drain)",
        ],
        semantic_shift="'thoroughly dried out' → dry-cured aged ham",
    ),
    EtymologyEntry(
        language="it", lemma="risotto",
        origin_summary=(
            "From riso (rice) + diminutive suffix -otto. Riso derives from "
            "Old French ris, from Italian riso, from Greek oryza, from a word "
            "of Eastern origin (Sanskrit, Persian). Risotto — 'little rice' — "
            "is the characteristic Northern Italian technique of slowly "
            "adding stock to arborio rice to develop starch and creaminess."
        ),
        roots=[
            "Greek oryza (rice)",
            "of ultimately Eastern origin (possibly Dravidian or Iranian)",
        ],
        cognates=[
            "English 'rice' (from the same Greek root via French)",
            "Spanish 'arroz' (rice, from Arabic ar-ruzz, same origin)",
        ],
        semantic_shift="Eastern grain name → Italian creamy rice dish",
    ),
    EtymologyEntry(
        language="it", lemma="tiramisu",
        origin_summary=(
            "From Italian tirami sù (pick me up, lift me up) — tira "
            "(imperative of tirare, to pull/lift) + mi (me) + sù (up). The "
            "dessert — espresso-soaked ladyfingers layered with mascarpone "
            "cream — gets its name from the stimulating combination of "
            "caffeine (espresso) and sugar. Invented in the Veneto region in "
            "the 1960s–70s."
        ),
        roots=[
            "Italian tirare (to pull, to lift, ultimately from Latin tirare)",
            "Italian su (up, from Latin sursum)",
        ],
        cognates=[
            "English 'tire' (possibly related via Old French tirer)",
            "Italian 'su' = English 'up' (both from PIE *upo)",
        ],
        semantic_shift="'pick me up' → a layered coffee-mascarpone dessert",
    ),
    EtymologyEntry(
        language="it", lemma="mozzarella",
        origin_summary=(
            "Diminutive of mozza (a slice cut off), from mozzare (to cut off, "
            "to chop), from an Old Italian root related to Latin mutilare (to "
            "mutilate, to shorten). The cheese is named for the way fresh "
            "curd is cut off (mozzata) by hand from the main block — a "
            "traditional technique in Campanian dairy production."
        ),
        roots=[
            "Italian mozzare (to cut off, to chop)",
            "possibly from Latin mutilare (to lop off)",
        ],
        cognates=[
            "English 'mutilate' (from the same Latin root)",
            "Italian 'mozzare' (to cut off, related to 'mutilare')",
        ],
        semantic_shift="'cut off' → a fresh pulled-curd cheese separated by hand-cutting",
    ),
    EtymologyEntry(
        language="it", lemma="gnocchi",
        origin_summary=(
            "From Italian nocchio (a knot in wood, a lump), probably from a "
            "Germanic root *knokk- (a knot, lump). The word describes the "
            "small lumps of potato-based dough. The Southern Italian and "
            "Northern Italian traditions produce different gnocchi — potato- "
            "based (Northern) or semolina-based (Roman) — but the lumpy shape "
            "is the constant."
        ),
        roots=[
            "Italian nocchio (a knot in wood, a lump)",
            "Germanic *knokk- (a knot, protuberance)",
        ],
        cognates=[
            "English 'knuckle' (from a similar Germanic root)",
            "English 'knot' (from Old English cnotta, same family)",
        ],
        semantic_shift=(
            "'lump, knot in wood' → small dumplings of potato or semolina "
            "dough"
        ),
    ),
    EtymologyEntry(
        language="it", lemma="parmigiano",
        origin_summary=(
            "An adjective meaning 'of Parma' — from the city of Parma in "
            "Emilia-Romagna, Italy, where this aged hard cheese originated. "
            "The full name Parmigiano-Reggiano (Parmesan) indicates joint "
            "production from Parma and Reggio Emilia. The geographic "
            "adjective-as-product-name pattern is common in Italian food "
            "naming."
        ),
        roots=[
            "Parma (Roman city Parma, of pre-Latin origin)",
            "Italian adjective suffix -igiano (of, from)",
        ],
        cognates=[
            "English 'Parmesan' (borrowed via French 'parmesan')",
            "French 'parmesan' (from Italian parmigiano)",
        ],
        semantic_shift=(
            "'of Parma' → a protected-designation aged hard cheese from "
            "Emilia-Romagna"
        ),
    ),
    EtymologyEntry(
        language="it", lemma="antipasto",
        origin_summary=(
            "From Italian anti (before) + pasto (meal, food), from Latin "
            "pastus (food, feeding), from pascere (to feed, to pasture). "
            "Antipasto is literally 'before the meal' — the Italian term for "
            "the first course of appetizers served before the main meal "
            "(primo, secondo). The word entered English directly."
        ),
        roots=[
            "Latin ante (before)",
            "Latin pastus (food, feeding)",
            "Latin pascere (to feed)",
        ],
        cognates=[
            "English 'past' (Latin pastus in a different sense)",
            "Italian 'pascere' = English 'pasture' (same Latin root)",
            "English 'antipasto' (borrowed directly)",
        ],
        semantic_shift="'before the meal' → first course of appetizers",
    ),
    EtymologyEntry(
        language="it", lemma="focaccia",
        origin_summary=(
            "From Latin focus (hearth, fireplace). Focaccia is flatbread "
            "baked on the hearth — the original domestic oven was the open "
            "fire (focus). Latin focus became Italian fuoco (fire) but the "
            "culinary term was preserved as focaccia, the 'hearth bread.' The "
            "same Latin root gives English 'focus' via a different "
            "metaphorical path."
        ),
        roots=[
            "Latin focus (hearth, fireplace, also used for the place where fire is kept)",
        ],
        cognates=[
            "English 'focus' (from Latin focus — the focal point of a lens, like a hearth)",
            "Italian 'fuoco' (fire)",
            "French 'feu' (fire, from the same Latin root)",
        ],
        semantic_shift=(
            "'hearth, fireplace' → flatbread traditionally baked on the "
            "hearth"
        ),
    ),
    EtymologyEntry(
        language="it", lemma="virtuoso",
        origin_summary=(
            "From Italian virtuoso (skilled, virtuous), from virtù (virtue, "
            "skill, excellence), from Latin virtus (excellence, worth, "
            "manliness), from vir (man). In Renaissance and later usage, "
            "virtù designated artistic and technical excellence. A virtuoso "
            "is one who possesses supreme technical mastery of an art or "
            "craft."
        ),
        roots=[
            "Latin virtus (excellence, worth, manliness)",
            "Latin vir (man)",
        ],
        cognates=[
            "English 'virtue' (moral excellence, from the same root)",
            "English 'virile' (manly, from vir)",
            "English 'virtuoso' (borrowed directly from Italian)",
        ],
        semantic_shift=(
            "'excellent, virtuous' → a performer of outstanding technical "
            "mastery"
        ),
    ),
    EtymologyEntry(
        language="it", lemma="maestro",
        origin_summary=(
            "From Italian maestro (master, teacher), from Latin magister "
            "(master, teacher, director), from magnus (great). In music, "
            "maestro is a title of respect for a conductor or acclaimed "
            "composer. The same Latin root gives English 'master,' "
            "'magistrate,' and 'majestic.'"
        ),
        roots=[
            "Latin magister (master, teacher, director)",
            "Latin magnus (great, large)",
        ],
        cognates=[
            "English 'master' (from Latin magister)",
            "English 'magistrate' (from magister)",
            "Spanish 'maestro' (teacher)",
            "French 'maître' (master)",
        ],
        semantic_shift=(
            "'master, teacher' → a distinguished conductor or eminent "
            "musician"
        ),
    ),
    EtymologyEntry(
        language="it", lemma="scenario",
        origin_summary=(
            "From Italian scenario (a scene, a stage setting), from scena "
            "(scene, stage), from Latin scaena, from Greek skēnē (a tent, "
            "booth, or stage backdrop — originally where actors changed "
            "costume). Scenario entered English via theater terminology and "
            "broadened to mean any hypothetical sequence of events."
        ),
        roots=["Greek skēnē (tent, stage building, backdrop)"],
        cognates=[
            "English 'scene' (same Greek root via Latin)",
            "English 'scenery' (stage settings)",
            "English 'scenario' (borrowed from Italian)",
        ],
        semantic_shift=(
            "'stage setting' → a sequence of events in a plan or script, then "
            "any hypothetical situation"
        ),
    ),
    EtymologyEntry(
        language="it", lemma="libretto",
        origin_summary=(
            "Diminutive of libro (book), from Latin liber (book, originally "
            "the inner bark of a tree on which writing was done). A libretto "
            "— literally 'little book' — is the text of an opera or oratorio: "
            "the verbal script that underlies the musical composition. "
            "Plural: libretti."
        ),
        roots=["Latin liber (book, inner tree bark used for writing)"],
        cognates=[
            "English 'library' (from Latin librarium, a bookcase)",
            "English 'libel' (originally a little book or pamphlet)",
            "Italian 'libro' (book)",
        ],
        semantic_shift="'little book' → the text/words of an opera or musical drama",
    ),
    EtymologyEntry(
        language="it", lemma="studio",
        origin_summary=(
            "From Italian studio (a study, a workplace for an artist), from "
            "Latin studium (eagerness, study, pursuit), from studere (to be "
            "eager, to study). A studio is literally a place of study or "
            "dedicated work. The word entered English in the 18th century for "
            "artists' workrooms, then extended to photography, recording, and "
            "film production."
        ),
        roots=[
            "Latin studium (eagerness, devotion, study)",
            "Latin studere (to be eager, to apply oneself)",
        ],
        cognates=[
            "English 'study' (from the same Latin root)",
            "English 'student' (from Latin studere)",
            "English 'studio' (borrowed from Italian)",
        ],
        semantic_shift=(
            "'study, eager pursuit' → a dedicated workspace for an artist, "
            "photographer, or broadcaster"
        ),
    ),
    EtymologyEntry(
        language="it", lemma="umbrella",
        origin_summary=(
            "From Italian ombrella (a little shade, a parasol), diminutive of "
            "ombra (shadow, shade), from Latin umbra (shade, shadow). The "
            "device was originally a parasol protecting from sun, not rain — "
            "a little shadow-maker. The meaning narrowed to rain-protection "
            "in English, while Italian and other Romance languages kept the "
            "sun-shade sense alongside."
        ),
        roots=["Latin umbra (shade, shadow)"],
        cognates=[
            "English 'umbrage' (shade, then offense — from umbra)",
            "English 'somber' (shaded, dark — from Spanish sombra = shade, same root)",
            "Italian 'ombra' (shadow)",
        ],
        semantic_shift=(
            "'little shade' (a sun-parasol) → rain umbrella in English; both "
            "senses retained in Italian"
        ),
    ),
    EtymologyEntry(
        language="it", lemma="volcano",
        origin_summary=(
            "From Italian vulcano, from Latin Volcanus/Vulcanus, the Roman "
            "god of fire and metalworking, also identified with the volcanic "
            "island of Vulcano in the Aeolian Islands. The island was thought "
            "to be the chimney of Vulcan's forge beneath the sea. The common "
            "noun 'volcano' spread from the island's name through Italian to "
            "all European languages."
        ),
        roots=[
            "Latin Volcanus (Roman god of fire and smithcraft)",
            "Aeolian island Vulcano (named for the deity)",
        ],
        cognates=[
            "English 'volcano' (via Italian vulcano)",
            "English 'vulcanize' (to treat rubber with heat — from Vulcan's fire)",
        ],
        semantic_shift="name of a deity and an island → any erupting geological vent",
    ),
    EtymologyEntry(
        language="it", lemma="lotteria",
        origin_summary=(
            "From Italian lotteria (a lottery), from lotto (lot, share, "
            "parcel), from Old French lot, from Frankish *hlot (a lot, a "
            "share allotted by chance). The sense of distributing prizes by "
            "drawing lots (casting hlot) is ancient; the organized Italian "
            "state lottery originated in Genoa in the 16th century. English "
            "'lottery' is borrowed from the Italian via Dutch loterij."
        ),
        roots=[
            "Frankish *hlot (a lot, a portion drawn by chance)",
            "Old Norse hlautr (sacrificial blood drawn by lot)",
        ],
        cognates=[
            "English 'lot' (portion, chance — from the same Germanic root)",
            "English 'lottery' (from Italian lotteria via Dutch)",
            "English 'allot' (to distribute by lot)",
        ],
        semantic_shift=(
            "'a portion by lot' → a game of chance with prizes distributed by "
            "random drawing"
        ),
    ),
    EtymologyEntry(
        language="it", lemma="gazzetta",
        origin_summary=(
            "Possibly from Venetian gazeta (a small coin, the price of the "
            "newspaper), or from gazza (magpie — a chattering bird associated "
            "with gossip and news). The first printed periodical news-sheets "
            "in Venice (1563 onward) were called gazzette. English 'gazette,' "
            "French 'gazette,' and German 'Gazette' all derive from Italian."
        ),
        roots=[
            "Venetian gazeta (small coin)",
            "alternatively gazza (magpie)",
        ],
        cognates=[
            "English 'gazette' (a newspaper or official journal)",
            "English 'gazetteer' (a geographical dictionary, originally published in gazette form)",
        ],
        semantic_shift=(
            "either 'small coin' (the price of news) or 'chattering bird' → a "
            "news periodical, then an official journal"
        ),
    ),
    EtymologyEntry(
        language="it", lemma="infanteria",
        origin_summary=(
            "From Italian infanteria (infantry), from infante (a young "
            "person, a foot soldier), from Latin infans/infantis (a young "
            "child, literally 'not speaking' — in + fans from fari, to "
            "speak). Young men who could not afford horses served on foot; "
            "the 'infant' foot soldiers gave infantry its name across "
            "European languages."
        ),
        roots=[
            "Latin infans (a young child, speechless person)",
            "Latin in- (not) + fari (to speak)",
        ],
        cognates=[
            "English 'infant' (a baby, from the same Latin root)",
            "English 'infantry' (via Italian infanteria and French infanterie)",
            "Spanish 'infante' (a prince, also a foot soldier)",
        ],
        semantic_shift=(
            "'young person, non-speaking child' → a young foot soldier → "
            "infantry as a branch of the military"
        ),
    ),
    EtymologyEntry(
        language="it", lemma="squadra",
        origin_summary=(
            "From Italian squadra (a square, a squad, a team), from Vulgar "
            "Latin *exquadra (a square), from ex- + quadra (a square), from "
            "Latin quadrus (square, fourfold), from quattuor (four). A "
            "military squad was originally formed in a square formation. "
            "English 'squadron,' 'squad,' and 'square' share this root."
        ),
        roots=["Latin quadrus (square)", "Latin quattuor (four)"],
        cognates=[
            "English 'squad' (via Italian squadra)",
            "English 'squadron' (via Italian squadrone)",
            "English 'square' (via Old French esquarre, same root)",
        ],
        semantic_shift="'a square, a square formation' → a military unit → a sports team",
    ),
    EtymologyEntry(
        language="it", lemma="carnevale",
        origin_summary=(
            "Disputed: either from Latin carnem levare (to put away meat — "
            "carne + levare) or from Latin carne vale (farewell to meat — "
            "carne + vale, imperative of valere, to be well). Both "
            "interpretations reference the abandonment of meat before Lent. "
            "Carnival marks the festive period before the Lenten fast — the "
            "last days of meat-eating."
        ),
        roots=[
            "Latin caro/carnis (flesh, meat)",
            "Latin levare (to lift, remove) or vale (farewell, be well)",
        ],
        cognates=[
            "English 'carnival' (from Italian)",
            "English 'carnivore' (meat-eater, from the same Latin root)",
            "Spanish 'carnaval' (from the same source)",
        ],
        semantic_shift=(
            "'farewell to meat' → a festive season of celebration immediately "
            "before Lent"
        ),
    ),
    EtymologyEntry(
        language="it", lemma="contrabbando",
        origin_summary=(
            "From Italian contrabbando (contraband, smuggled goods), from "
            "contra (against) + bando (a ban, a proclamation), from Lombardic "
            "*bann (a command, prohibition), from the same Germanic root as "
            "English 'ban.' Contraband is literally 'against the ban' — goods "
            "prohibited by official proclamation."
        ),
        roots=[
            "Latin contra (against, opposite)",
            "Lombardic/Germanic *bann (command, prohibition, edict)",
        ],
        cognates=[
            "English 'ban' (from the same Germanic root)",
            "English 'banns' (of marriage — a public proclamation)",
            "English 'contraband' (borrowed from Italian)",
        ],
        semantic_shift=(
            "'against the ban (proclamation)' → prohibited goods; smuggled "
            "merchandise"
        ),
    ),
    EtymologyEntry(
        language="it", lemma="citadella",
        origin_summary=(
            "Diminutive of città (city), from Latin civitas (citizenship, "
            "community, city), from civis (citizen). A citadella — literally "
            "'little city' — is the fortified inner core of a city that can "
            "hold out even when the city itself falls. The diminutive suffix "
            "implies it is the essential defended core of the larger urban "
            "form."
        ),
        roots=[
            "Latin civitas (citizenship, community, city-state)",
            "Latin civis (citizen)",
        ],
        cognates=[
            "English 'city' (from Latin civitas)",
            "English 'citizen' (from Latin civis)",
            "English 'citadel' (from Italian citadella)",
        ],
        semantic_shift="'little city' → the heavily fortified inner stronghold of a city",
    ),
    EtymologyEntry(
        language="it", lemma="portafoglio",
        origin_summary=(
            "From Italian portafoglio (portfolio, wallet), from porta (carry "
            "— from portare, to carry) + foglio (a leaf, a sheet of paper), "
            "from Latin folium (a leaf). A portfolio is literally 'a carrier "
            "of leaves/sheets' — originally a folder for carrying drawings or "
            "documents. Extended to mean a financial portfolio (a collection "
            "of investments) and a minister's portfolio (area of "
            "responsibility)."
        ),
        roots=["Latin portare (to carry)", "Latin folium (leaf, sheet)"],
        cognates=[
            "English 'portfolio' (from Italian portafoglio)",
            "English 'folio' (a sheet of paper, from Latin folium)",
            "English 'foliage' (from Latin folium)",
        ],
        semantic_shift=(
            "'a carrier of leaves/sheets' → a case for documents → a "
            "collection of investments or responsibilities"
        ),
    ),
    EtymologyEntry(
        language="it", lemma="belladonna",
        origin_summary=(
            "From Italian bella donna (beautiful woman), from bella "
            "(beautiful, feminine of bello) + donna (woman, lady), from Latin "
            "domina (mistress, lady). The plant Atropa belladonna was used by "
            "Renaissance Italian women to dilate their pupils — the dilated "
            "pupils were considered beautiful and seductive, giving the plant "
            "its common name."
        ),
        roots=[
            "Latin bellus (beautiful, fine)",
            "Latin domina (mistress, lady of the house)",
        ],
        cognates=[
            "English 'belladonna' (borrowed directly)",
            "Italian 'donna' = English 'dame/madam' (from Latin domina)",
            "English 'domino' (originally a master's hood, from dominus — related to domina)",
        ],
        semantic_shift=(
            "'beautiful lady' → a deadly nightshade plant used cosmetically "
            "to dilate pupils"
        ),
    ),
    EtymologyEntry(
        language="it", lemma="stravaganza",
        origin_summary=(
            "From Italian stravaganza (extravagance, eccentricity), from "
            "stravagante (straying, wandering), from Medieval Latin "
            "*extravagare (to wander outside), from Latin extra (outside) + "
            "vagare (to wander). In music, a stravaganza is a showy, "
            "fantastical composition. Vivaldi named a violin concerto "
            "collection 'La stravaganza' (1712). English borrowed the word as "
            "'extravaganza.'"
        ),
        roots=[
            "Latin extra (outside, beyond)",
            "Latin vagare (to wander, to roam)",
        ],
        cognates=[
            "English 'extravagance' (from the same Latin roots, via French)",
            "English 'vagabond' (one who wanders, from vagare)",
            "English 'vague' (wandering, unclear — from vagus, same root)",
        ],
        semantic_shift=(
            "'wandering outside (the norm)' → eccentricity, then an elaborate "
            "showy entertainment"
        ),
    ),
    EtymologyEntry(
        language="it", lemma="sequenza",
        origin_summary=(
            "From Italian sequenza (a sequence, a succession), from Medieval "
            "Latin sequentia (a series of notes), from Latin sequi (to "
            "follow). In medieval music, a sequentia was a liturgical chant "
            "following the Alleluia. The word entered music theory and "
            "broader usage. The minimalist composer Luciano Berio titled a "
            "famous series of solo works 'Sequenza.'"
        ),
        roots=["Latin sequi (to follow, to come after)"],
        cognates=[
            "English 'sequence' (from the same Latin root)",
            "English 'sequel' (that which follows)",
            "English 'subsequent' (following, from subsequi)",
        ],
        semantic_shift=(
            "'a following, a series' → a liturgical musical chant, then any "
            "ordered series"
        ),
    ),
    EtymologyEntry(
        language="it", lemma="cello",
        origin_summary=(
            "Short for Italian violoncello, a diminutive of violone (a large "
            "viol), itself an augmentative of viola (a viol). The naming "
            "chain is: viola → violone (big viola) → violoncello (small "
            "violone). So 'cello' is etymologically 'a little big viola' — "
            "the diminutive of the augmentative, ending up as a mid-sized "
            "string instrument."
        ),
        roots=[
            "Italian viola (a string instrument, possibly from Medieval Latin vitula = fiddle)",
            "Italian augmentative suffix -one",
            "Italian diminutive suffix -cello",
        ],
        cognates=[
            "English 'cello' (clipped from violoncello)",
            "English 'violin' (via French violon, diminutive of viole/viola)",
        ],
        semantic_shift="'small big-viola' → the bass member of the violin family",
    ),
    EtymologyEntry(
        language="it", lemma="contrapposto",
        origin_summary=(
            "From Italian contrapposto (counterposed, set against), past "
            "participle of contrapporre (to set against, to counterpose), "
            "from Latin contra (against) + ponere (to place). In sculpture "
            "and painting, contrapposto is the technique of setting the upper "
            "and lower body in opposite directions — one hip raised while the "
            "opposite shoulder drops — creating natural human movement. "
            "Pioneered in ancient Greek sculpture and revived in the "
            "Renaissance."
        ),
        roots=[
            "Latin contra (against, opposite)",
            "Latin ponere (to place, to put)",
        ],
        cognates=[
            "English 'counterpose' (direct translation)",
            "English 'contrapose' (to set against)",
            "English 'opposite' (from Latin oppositus, same ponere root)",
        ],
        semantic_shift=(
            "'counterposed, set against' → the sculptural technique of "
            "opposing upper/lower body axes"
        ),
    ),
    EtymologyEntry(
        language="it", lemma="canzone",
        origin_summary=(
            "From Latin cantio/cantionis (a song, a singing), from canere (to "
            "sing). A canzone is an Italian lyric poem or song form, "
            "important in Italian and Provençal poetry. Petrarch's Canzoniere "
            "(Songbook) is the most influential collection of Italian lyric "
            "poetry. The form influenced Elizabethan poetry and the "
            "development of the sonnet."
        ),
        roots=[
            "Latin cantio (a singing, a song)",
            "Latin canere (to sing, to play an instrument)",
        ],
        cognates=[
            "English 'chant' (from Latin cantare, a frequentative of canere)",
            "English 'incantation' (a magical singing)",
            "Italian 'cantare' (to sing)",
        ],
        semantic_shift="'a singing, a song' → a specific lyric poetic/musical form",
    ),
    EtymologyEntry(
        language="it", lemma="contratto",
        origin_summary=(
            "From Latin contractus (a drawing together, an agreement), past "
            "participle of contrahere (to draw together, to conclude a "
            "bargain), from con- (together) + trahere (to draw, to pull). A "
            "contract is what is 'drawn together' between parties. The "
            "legal/commercial sense was already present in Latin."
        ),
        roots=[
            "Latin contrahere (to draw together, to agree)",
            "Latin trahere (to draw, to pull)",
        ],
        cognates=[
            "English 'contract' (from the same Latin root)",
            "English 'abstract' (drawn away — abs + trahere)",
            "English 'tractor' (that which draws — from trahere)",
        ],
        semantic_shift="'drawn together' → a legally binding agreement between parties",
    ),
    EtymologyEntry(
        language="it", lemma="furore",
        origin_summary=(
            "From Latin furor (rage, frenzy), from furere (to be mad, to "
            "rage). In Italian and English, furore (Italian spelling) or "
            "furor (English) means an outbreak of public excitement or "
            "outrage. The sense shifted from violent madness to intense "
            "collective enthusiasm or controversy."
        ),
        roots=[
            "Latin furere (to be mad, to rage)",
            "Latin furor (madness, frenzy)",
        ],
        cognates=[
            "English 'fury' (from Latin furia)",
            "English 'furor/furore' (passionate outburst)",
            "English 'infuriated' (made furious)",
        ],
        semantic_shift=(
            "'madness, violent frenzy' → a public uproar of excitement or "
            "indignation"
        ),
    ),
    EtymologyEntry(
        language="it", lemma="intonazione",
        origin_summary=(
            "From Italian intonare (to intone, to pitch correctly), from in- "
            "+ tono (tone), from Latin tonus (tension, tone), from Greek "
            "tonos (a stretching, a tone), from teinein (to stretch). "
            "Intonation in music refers to the accuracy of pitch; in "
            "linguistics, to the melodic pattern of speech. Both senses "
            "derive from the physical tension of a vibrating string."
        ),
        roots=[
            "Greek tonos (tension, tone, a stretched string)",
            "Greek teinein (to stretch)",
        ],
        cognates=[
            "English 'tone' (from Greek tonos via Latin)",
            "English 'intonation' (from Italian)",
            "English 'tension' (from the same PIE root as teinein)",
        ],
        semantic_shift=(
            "'stretching into tone' → the accuracy of musical pitch; the "
            "melodic pattern of speech"
        ),
    ),
    EtymologyEntry(
        language="it", lemma="passione",
        origin_summary=(
            "From Latin passio/passionis (suffering, enduring), from pati (to "
            "suffer, to undergo). The primary Christian meaning is the "
            "Passion of Christ — the suffering and crucifixion. In medieval "
            "and Renaissance Italian, passione extended to any intense "
            "feeling one 'undergoes' or is 'subjected to,' as opposed to "
            "active choice. Modern Italian uses it for any deep enthusiasm."
        ),
        roots=[
            "Latin pati (to suffer, to endure, to undergo)",
            "Latin passio (suffering, the Passion of Christ)",
        ],
        cognates=[
            "English 'passion' (via the same Latin root)",
            "English 'patient' (one who suffers/endures)",
            "English 'passive' (subjected to, acted upon)",
        ],
        semantic_shift=(
            "'suffering, enduring' → the Passion of Christ → any intense "
            "feeling one undergoes → deep enthusiasm"
        ),
    ),
    EtymologyEntry(
        language="it", lemma="leggenda",
        origin_summary=(
            "From Medieval Latin legenda (things to be read), gerundive of "
            "legere (to read, to choose, to gather). Originally a leggenda "
            "was a collection of saints' lives — texts appointed to be read "
            "in church. The Legenda Aurea (Golden Legend, 13th century) was "
            "the most influential such collection. The meaning shifted from "
            "'required reading' to 'a traditional story.'"
        ),
        roots=[
            "Latin legere (to read, to gather, to choose)",
            "Latin -enda (gerundive suffix: 'to be done/read')",
        ],
        cognates=[
            "English 'legend' (from the same Medieval Latin root)",
            "English 'legible' (from Latin legere)",
            "English 'lecture' (a reading, from legere)",
        ],
        semantic_shift=(
            "'things to be read' (liturgical saints' lives) → a traditional "
            "story or myth; map legend (to be read)"
        ),
    ),
    EtymologyEntry(
        language="it", lemma="melancolia",
        origin_summary=(
            "From Greek melankholia (black bile, sadness), from melas (black) "
            "+ kholē (bile). In ancient humoral theory, an excess of black "
            "bile (melaina kholē) produced a disposition toward sadness, "
            "pensiveness, and creative genius. The Renaissance rehabilitated "
            "melancholy as the mark of the intellectual and artistic "
            "temperament — Dürer's 'Melencolia I' is the iconic image."
        ),
        roots=["Greek melas (black)", "Greek kholē (bile, gall)"],
        cognates=[
            "English 'melancholy' (from the same Greek roots)",
            "English 'cholera' (bile-related disease)",
            "English 'choleric' (bilious, quick-tempered — from kholē)",
        ],
        semantic_shift=(
            "'black bile' (a bodily humor) → a temperament of sadness and "
            "pensiveness → creative melancholy"
        ),
    ),

    # ── AR additions (generated by gen_etymology.py) ──
    EtymologyEntry(
        language="ar", lemma="صبر",
        origin_summary=(
            "From the triliteral root ص-ب-ر (ṣ-b-r) meaning 'to bind tightly, "
            "to endure, to be patient.' Ṣabr is one of the most important "
            "Quranic concepts — patient endurance under hardship. The same "
            "root yields ṣābūn (soap, originally a binding agent) and ṣabr "
            "meaning aloe (the bitter plant requiring patience). The semantic "
            "core is 'binding the self.'"
        ),
        roots=["Proto-Semitic *ṣ-b-r (to bind, to endure)"],
        cognates=[
            "Hebrew סבל (sabal, to bear/suffer — different root family)",
            "Aramaic sabar (to wait, to hope)",
        ],
        semantic_shift=(
            "'to bind tightly' → to endure with self-control → patience as "
            "religious virtue"
        ),
    ),
    EtymologyEntry(
        language="ar", lemma="حق",
        origin_summary=(
            "From root ح-ق-ق (ḥ-q-q) meaning 'to be true, to be right, to be "
            "due.' Ḥaqq is one of the 99 names of God (al-Ḥaqq, The Truth). "
            "The single word covers truth, right, justice, and reality — a "
            "key concept in Islamic legal and theological vocabulary."
        ),
        roots=["Proto-Semitic *ḥ-q-q (to engrave, to be fixed/true)"],
        cognates=[
            "Hebrew חקק (ḥaqaq, to engrave/decree)",
            "Aramaic ḥaqqā (truth)",
        ],
        semantic_shift=(
            "'engraved/fixed' → that which is fixed and true → truth, right, "
            "justice, divine reality"
        ),
    ),
    EtymologyEntry(
        language="ar", lemma="كرم",
        origin_summary=(
            "From root ك-ر-م (k-r-m) meaning 'to be noble, to be generous.' "
            "Karam is generosity raised to a moral and aesthetic ideal — a "
            "defining virtue of pre-Islamic Arabic poetry and bedouin "
            "culture, retained centrally in Islamic ethics. The same root "
            "gives karīm (noble/generous, also a name of God)."
        ),
        roots=["Proto-Semitic *k-r-m (to be noble, to honor)"],
        cognates=[
            "Hebrew כרם (kerem, vineyard — possibly from 'precious thing')",
            "Aramaic kerem (vineyard)",
        ],
        semantic_shift=(
            "'to be noble' → generosity as the practice of nobility → "
            "hospitality"
        ),
    ),
    EtymologyEntry(
        language="ar", lemma="نور",
        origin_summary=(
            "From root ن-و-ر (n-w-r) meaning 'to give light, to illuminate.' "
            "Nūr is light — the divine light, the light of guidance, "
            "illumination. An-Nūr is one of the names of God and a chapter of "
            "the Quran. The word is profoundly important in Islamic mystical "
            "(Sufi) vocabulary, where light is the metaphor for divine "
            "knowledge."
        ),
        roots=["Proto-Semitic *n-w-r (light, fire)"],
        cognates=[
            "Hebrew נר (ner, lamp/candle), אור (or, light) — same root family",
            "Aramaic nūrā (fire)",
        ],
        semantic_shift=(
            "'to give light' → light as physical phenomenon and divine "
            "metaphor"
        ),
    ),
    EtymologyEntry(
        language="ar", lemma="روح",
        origin_summary=(
            "From root ر-و-ح (r-w-ḥ) meaning 'to breathe, to be at rest, to "
            "refresh.' Rūḥ is spirit, soul, breath — etymologically the "
            "breath of life. The Quran speaks of God breathing rūḥ into Adam. "
            "Cognate with Hebrew rūaḥ (spirit/wind/breath) — a Pan-Semitic "
            "concept linking breath, wind, and soul."
        ),
        roots=["Proto-Semitic *r-w-ḥ (to breathe, wind, spirit)"],
        cognates=[
            "Hebrew רוח (rūaḥ, spirit/wind/breath)",
            "Aramaic rūḥā (spirit)",
            "English 'spirit' from Latin spiritus = breath, parallel concept",
        ],
        semantic_shift="'breath/wind' → animating breath → soul, spirit",
    ),
    EtymologyEntry(
        language="ar", lemma="عدل",
        origin_summary=(
            "From root ع-د-ل ('-d-l) meaning 'to be just, to balance, to make "
            "equal.' 'Adl is justice — one of the cardinal virtues in Islamic "
            "political and ethical thought. The same root gives mu'tadil "
            "(moderate, balanced) and ta'dīl (adjustment, balancing). Justice "
            "as balance is the etymological core."
        ),
        roots=["Proto-Semitic *'-d-l (to be straight, balanced)"],
        cognates=[
            "Hebrew עָדִיף (adīf — different sense, from related root)",
            "Aramaic 'edalā (justice)",
        ],
        semantic_shift="'to balance, to equalize' → justice as proper balance and equity",
    ),
    EtymologyEntry(
        language="ar", lemma="حضارة",
        origin_summary=(
            "From root ح-ض-ر (ḥ-ḍ-r) meaning 'to be present, to settle, to be "
            "sedentary' (as opposed to bedouin/nomadic). Ḥaḍāra is "
            "civilization — etymologically 'the settled state.' The "
            "opposition between ḥaḍar (settled people, town-dwellers) and "
            "badw (bedouin) structures Ibn Khaldūn's foundational sociology "
            "of civilization in the Muqaddimah."
        ),
        roots=["Proto-Semitic *ḥ-ḍ-r (to be present)"],
        cognates=[
            "Hebrew חצר (ḥatzer, courtyard/enclosure)",
            "Aramaic ḥuṣrā (yard)",
        ],
        semantic_shift=(
            "'sedentary settlement' → urban civilization → "
            "cultural/civilizational achievement"
        ),
    ),
    EtymologyEntry(
        language="ar", lemma="أمة",
        origin_summary=(
            "From root أ-م-م ('-m-m) related to umm (mother) — the "
            "foundational sense of 'group/nation' as 'descended from a common "
            "mother.' Umma is community/nation/people — the global Muslim "
            "community, but also any people group. The word appears in early "
            "treaties (Constitution of Medina, 622 CE) defining the political "
            "structure of early Islam."
        ),
        roots=["Proto-Semitic *'-m-m (mother, source, community)"],
        cognates=[
            "Hebrew אומה (umma, nation — same root)",
            "Aramaic ummā (people)",
        ],
        semantic_shift=(
            "'mother/source' → community sharing a common origin → nation, "
            "people; in Islam, the global Muslim community"
        ),
    ),
    EtymologyEntry(
        language="ar", lemma="جهاد",
        origin_summary=(
            "From root ج-ه-د (j-h-d) meaning 'to strive, to exert effort.' "
            "Jihād is struggle/exertion — broadly 'striving in the path of "
            "God.' The classical Islamic distinction between greater jihād "
            "(jihād akbar — internal struggle for moral betterment) and "
            "lesser jihād (jihād aṣghar — physical struggle/warfare) is "
            "theologically significant. The English connotation has narrowed "
            "to combat through media usage."
        ),
        roots=["Proto-Semitic *j-h-d (to strive, to be exhausted)"],
        cognates=["Hebrew יגד (yagad, related root for striving)"],
        semantic_shift=(
            "'exertion, striving' → moral and spiritual struggle (greater "
            "jihād) → also physical struggle (lesser jihād)"
        ),
    ),
    EtymologyEntry(
        language="ar", lemma="إيمان",
        origin_summary=(
            "From root أ-م-ن ('-m-n) meaning 'to be safe, to trust.' Īmān is "
            "faith — etymologically related to 'amn (security, peace) and "
            "amīn (trustworthy, the messenger's title). The same root gives "
            "the universal Hebrew/Christian/Islamic 'amen' (truly, "
            "faithfully). Faith as trust-grounded-in-truth."
        ),
        roots=["Proto-Semitic *'-m-n (to be firm, trusted)"],
        cognates=[
            "Hebrew אמונה (emūnā, faith — same root)",
            "Hebrew/Aramaic אמן (amen, certainly/truly — same root)",
            "English 'amen' (via Greek/Latin from Hebrew)",
        ],
        semantic_shift=(
            "'firmness, trust' → faith as trust → also gives amen, security, "
            "fidelity"
        ),
    ),
    EtymologyEntry(
        language="ar", lemma="جنة",
        origin_summary=(
            "From root ج-ن-ن (j-n-n) meaning 'to cover, to conceal, to "
            "enclose.' Janna is paradise/garden — etymologically 'the "
            "enclosed/protected place,' the walled garden. Same root gives "
            "jinn (concealed beings/spirits), janīn (fetus, the concealed "
            "one), and majnūn (mad, possessed by jinn). The Quranic paradise "
            "is described as a garden with rivers — preserving the original "
            "'enclosed garden' image."
        ),
        roots=["Proto-Semitic *j-n-n (to cover, to enclose)"],
        cognates=[
            "Hebrew גן (gan, garden — same root, as in Gan Eden)",
            "Aramaic gan (garden)",
            "English 'genie' (from Arabic jinn, via French)",
        ],
        semantic_shift=(
            "'enclosure, hidden place' → garden → paradise; also: spirit "
            "beings (jinn), fetus (janīn), madness (majnūn)"
        ),
    ),
    EtymologyEntry(
        language="ar", lemma="فقير",
        origin_summary=(
            "From root ف-ق-ر (f-q-r) meaning 'to be in need, to be poor.' "
            "Faqīr is poor person — but in Sufi vocabulary, the faqīr is the "
            "spiritual poor: one who recognizes total dependence on God. "
            "English 'fakir' enters via Persian-Indian Sufi orders. The "
            "semantic field connects material poverty to spiritual humility."
        ),
        roots=["Proto-Semitic *f-q-r (to break, to be deficient)"],
        cognates=[
            "English 'fakir' (mendicant ascetic — Arabic loanword via Persian/Hindustani)",
            "Hebrew פקר (paqar, related root meaning to be deficient)",
        ],
        semantic_shift=(
            "'to be in need' → poor person → in Sufism: spiritual mendicant "
            "who recognizes utter dependence on God"
        ),
    ),
    EtymologyEntry(
        language="ar", lemma="ملك",
        origin_summary=(
            "From root م-ل-ك (m-l-k) meaning 'to possess, to own, to rule.' "
            "Malik is king — the same root gives mulk (kingdom), mālik "
            "(owner), malak (angel — God's possessor/messenger). One of the "
            "names of God: al-Malik (the King). Cognate with Hebrew melekh "
            "(king) — Pan-Semitic."
        ),
        roots=["Proto-Semitic *m-l-k (to rule, to own)"],
        cognates=[
            "Hebrew מלך (melekh, king — same root)",
            "Aramaic mlk (to advise/rule)",
            "Phoenician/Punic mlk (king — name of the god Moloch)",
        ],
        semantic_shift=(
            "'to possess, to rule' → king; also: angel (one with delegated "
            "authority); mamluk (one possessed = slave-soldier)"
        ),
    ),
    EtymologyEntry(
        language="ar", lemma="عقل",
        origin_summary=(
            "From root ع-ق-ل ('-q-l) meaning 'to bind, to tie, to restrain.' "
            "'Aql is intellect/reason — etymologically 'that which binds' "
            "(constrains the passions). The same root gives 'iqāl, the rope "
            "used to hobble a camel — and the cord worn over the keffiyeh, "
            "named for that camel-binding tool. Reason as the rope that binds "
            "the wild horse of impulse."
        ),
        roots=["Proto-Semitic *'-q-l (to bind, to tie)"],
        cognates=[
            "Hebrew עקל (aqal, twisted/curved)",
            "Aramaic 'qal (to bend)",
        ],
        semantic_shift=(
            "'to bind, to restrain' → the binding faculty → reason, "
            "intellect; also: camel-hobble rope and the keffiyeh-cord"
        ),
    ),
    EtymologyEntry(
        language="ar", lemma="حلال",
        origin_summary=(
            "From root ح-ل-ل (ḥ-l-l) meaning 'to untie, to dissolve, to "
            "permit.' Ḥalāl is permitted/lawful — etymologically 'that which "
            "has been untied,' i.e., released from prohibition. The "
            "opposition ḥalāl/ḥarām (permitted/forbidden) structures Islamic "
            "legal thought across all domains — food, finance, sexual "
            "conduct, contracts."
        ),
        roots=["Proto-Semitic *ḥ-l-l (to untie, to release)"],
        cognates=[
            "Hebrew חלל (ḥalal, to profane — opposite semantic development)",
            "Aramaic ḥll (to untie)",
        ],
        semantic_shift=(
            "'to untie, to release' → released from prohibition → lawful, "
            "permitted"
        ),
    ),
    EtymologyEntry(
        language="ar", lemma="حرام",
        origin_summary=(
            "From root ح-ر-م (ḥ-r-m) meaning 'to forbid, to make sacred-and- "
            "untouchable.' Ḥarām is forbidden/sacred — the same word covers "
            "what is taboo because forbidden AND what is taboo because holy "
            "(e.g., al-ḥaram, the sacred precinct of Mecca). Same root gives "
            "ḥarīm (the women's quarters — protected/forbidden space) and "
            "ihrām (the pilgrim's sacred state)."
        ),
        roots=["Proto-Semitic *ḥ-r-m (to set apart, to consecrate/forbid)"],
        cognates=[
            "Hebrew חרם (ḥerem, ban/excommunication — same root)",
            "English 'harem' (from Arabic ḥarīm)",
        ],
        semantic_shift=(
            "'set apart' → both 'sacred (off-limits)' and 'forbidden'; also: "
            "harem (protected female space)"
        ),
    ),
    EtymologyEntry(
        language="ar", lemma="صدق",
        origin_summary=(
            "From root ص-د-ق (ṣ-d-q) meaning 'to be true, to be sincere.' "
            "Ṣidq is truthfulness/veracity — paired with īmān (faith) as twin "
            "virtues. The same root gives ṣadaqa (charity — true giving, not "
            "from obligation) and ṣiddīq (the honorific for Abu Bakr, 'the "
            "truthful one'). Truth and giving share an etymological identity."
        ),
        roots=["Proto-Semitic *ṣ-d-q (to be just, true)"],
        cognates=[
            "Hebrew צדק (tsedek, righteousness — same root)",
            "Hebrew צדקה (tzedakah, charity — same etymological connection)",
            "Aramaic ṣdq (to be just)",
        ],
        semantic_shift=(
            "'to be true' → truthfulness as virtue → also: charity given "
            "truly (ṣadaqa)"
        ),
    ),
    EtymologyEntry(
        language="ar", lemma="حكمة",
        origin_summary=(
            "From root ح-ك-م (ḥ-k-m) meaning 'to judge, to be wise, to "
            "govern.' Ḥikma is wisdom — the same root gives ḥākim (judge, "
            "governor), ḥukm (judgment, ruling), and muḥkam (firmly "
            "established). Wisdom and judgment share an etymological "
            "identity. Al-Ḥakīm (the Wise) is one of the names of God."
        ),
        roots=["Proto-Semitic *ḥ-k-m (to be wise/judge)"],
        cognates=[
            "Hebrew חכמה (ḥokhmā, wisdom — same root)",
            "Aramaic ḥekmā (wisdom)",
        ],
        semantic_shift=(
            "'to judge wisely' → wisdom (ḥikma); also: ruler (ḥākim), "
            "judgment (ḥukm)"
        ),
    ),
    EtymologyEntry(
        language="ar", lemma="نية",
        origin_summary=(
            "From root ن-و-ي (n-w-y) meaning 'to intend, to aim at.' Niyya is "
            "intention — central to Islamic ritual law: every act of worship "
            "requires niyya. The famous hadith 'innamā al-a'māl bi-l-niyyāt' "
            "(deeds are by intentions) makes intention the determinant of an "
            "action's moral value. The same root gives nawā (date pit — the "
            "inner core/intention)."
        ),
        roots=["Proto-Semitic *n-w-y (to aim, to intend)"],
        cognates=[
            "Hebrew נוי (noy, beauty — different sense from same root family)",
        ],
        semantic_shift=(
            "'to aim at, to intend' → the inner intention behind an action → "
            "ritual prerequisite for valid worship"
        ),
    ),
    EtymologyEntry(
        language="ar", lemma="رحمة",
        origin_summary=(
            "From root ر-ح-م (r-ḥ-m) meaning 'womb, mercy, compassion.' Raḥma "
            "is mercy/compassion — etymologically 'womb-feeling,' the "
            "protective love a mother has for the child in her womb. Both "
            "names of God in the Quran's opening — al-Raḥmān (the "
            "Compassionate), al-Raḥīm (the Merciful) — derive from this root. "
            "Mercy as womb-love is one of Islam's most evocative theological "
            "metaphors."
        ),
        roots=["Proto-Semitic *r-ḥ-m (womb, compassion)"],
        cognates=[
            "Hebrew רחם (reḥem, womb), רחמים (raḥamīm, mercy/compassion — same etymological connection)",
            "Aramaic raḥmīn (mercy)",
        ],
        semantic_shift=(
            "'womb' → womb-feeling/mother-love → mercy; the divine attribute "
            "par excellence"
        ),
    ),
    EtymologyEntry(
        language="ar", lemma="إنسان",
        origin_summary=(
            "From root أ-ن-س ('-n-s) meaning 'to be friendly, to be sociable, "
            "to be familiar.' Insān is human being — etymologically 'the "
            "social/companionable creature.' Distinguished from bashar (human "
            "as biological being) by emphasizing social relationship as "
            "definitional. Some etymologists link to nasiya (to forget), "
            "implying 'the forgetful one' — a complementary etymology used in "
            "religious discourse."
        ),
        roots=["Proto-Semitic *'-n-s (to be sociable)"],
        cognates=[
            "Hebrew אנש (enosh, mortal/man — related root)",
            "Aramaic 'enaš (human)",
        ],
        semantic_shift=(
            "'to be friendly/social' → human as the social being (insān); "
            "also folk-etymology: 'one who forgets' (nasiya)"
        ),
    ),
    EtymologyEntry(
        language="ar", lemma="صلاة",
        origin_summary=(
            "From root ص-ل-و/ي (ṣ-l-w/y) meaning 'to pray, to bless.' Ṣalāt "
            "is the ritual prayer — the second pillar of Islam, performed "
            "five times daily. The Hebrew cognate is questionable; some link "
            "it to the meaning 'to bow, to incline.' The Christian Aramaic "
            "ṣlōthā (prayer) is the same root. The act of bowing in prayer is "
            "etymologically present in the word."
        ),
        roots=["Proto-Semitic *ṣ-l-w (to incline, to pray)"],
        cognates=[
            "Aramaic ṣlōthā (prayer — same root)",
            "Syriac ṣlīb (cross — possibly related, the bowing-place)",
        ],
        semantic_shift=(
            "'to bow, to incline' → ritual prayer involving bowing → the five "
            "daily prayers of Islam"
        ),
    ),
    EtymologyEntry(
        language="ar", lemma="زكاة",
        origin_summary=(
            "From root ز-ك-و/ي (z-k-w/y) meaning 'to be pure, to grow.' Zakāt "
            "is the obligatory alms-tax — the third pillar of Islam. "
            "Etymologically 'purification through giving': giving a portion "
            "of wealth purifies the rest and causes growth. The dual meaning "
            "(purify AND grow) captures the spiritual logic of charitable "
            "obligation."
        ),
        roots=["Proto-Semitic *z-k-w (to be pure, clean, to grow)"],
        cognates=[
            "Hebrew זכה (zakhah, to be pure/innocent)",
            "Aramaic dakkēh (pure)",
        ],
        semantic_shift=(
            "'to purify, to grow' → giving that purifies and grows wealth → "
            "the obligatory Islamic alms-tax"
        ),
    ),
    EtymologyEntry(
        language="ar", lemma="صوم",
        origin_summary=(
            "From root ص-و-م (ṣ-w-m) meaning 'to abstain, to refrain.' Ṣawm "
            "is fasting — the fourth pillar of Islam, observed during "
            "Ramaḍān. The original sense of abstention (from food, drink, "
            "sexual relations from dawn to sunset) preserves the etymology. "
            "Same root gives ṣā'im (one who fasts)."
        ),
        roots=["Proto-Semitic *ṣ-w-m (to abstain)"],
        cognates=[
            "Hebrew צום (tzom, fast — same root)",
            "Aramaic ṣawmā (fast)",
        ],
        semantic_shift=(
            "'to abstain, to restrain' → fasting → the obligatory month-long "
            "Ramaḍān fast"
        ),
    ),
    EtymologyEntry(
        language="ar", lemma="حج",
        origin_summary=(
            "From root ح-ج-ج (ḥ-j-j) meaning 'to argue, to make pilgrimage.' "
            "Ḥajj is the pilgrimage to Mecca — the fifth pillar of Islam. The "
            "dual meaning (argue/dispute AND pilgrimage) reflects the ancient "
            "sense of 'going to a sanctuary to argue one's case before the "
            "deity.' Same root gives ḥujja (proof, argument) — pilgrimage and "
            "proof share an etymological core."
        ),
        roots=["Proto-Semitic *ḥ-g-g (to circle, to go in procession)"],
        cognates=[
            "Hebrew חג (ḥag, festival/pilgrimage — same root, as in the three pilgrimage festivals of Israel)",
            "Aramaic ḥaggā (festival)",
        ],
        semantic_shift=(
            "'to circle/process' → pilgrimage → the obligatory Islamic "
            "pilgrimage to Mecca"
        ),
    ),
    EtymologyEntry(
        language="ar", lemma="شهيد",
        origin_summary=(
            "From root ش-ه-د (sh-h-d) meaning 'to witness, to bear "
            "testimony.' Shahīd is martyr — etymologically 'one who bears "
            "witness' (with their life). The shahāda (witnessing/testimony) "
            "is the Islamic creed. Martyrdom as the ultimate witnessing: the "
            "martyr testifies to the truth by dying for it. Greek martys "
            "('witness' → 'martyr') develops the same metaphor independently."
        ),
        roots=["Proto-Semitic *sh-h-d (to witness)"],
        cognates=[
            "Hebrew עד (ed, witness — different root)",
            "Greek 'martys' (witness → martyr — parallel semantic development)",
        ],
        semantic_shift=(
            "'to witness, to testify' → martyr (one who bears witness with "
            "their life)"
        ),
    ),
    EtymologyEntry(
        language="ar", lemma="تقوى",
        origin_summary=(
            "From root و-ق-ي (w-q-y) meaning 'to guard, to protect, to fear.' "
            "Taqwā is God-consciousness/piety — etymologically 'self- "
            "guarding,' the inner state of being mindful and protective of "
            "one's relationship to God. A central Quranic virtue. Often "
            "translated 'fear of God,' but more precisely 'God-consciousness' "
            "— protective awareness, not terror."
        ),
        roots=["Proto-Semitic *w-q-y (to guard, to protect)"],
        cognates=[
            "Aramaic wqy (to guard)",
            "Possibly Hebrew יקה (yaqah — root family)",
        ],
        semantic_shift=(
            "'to guard, to protect' → self-guarding awareness of God → piety, "
            "God-consciousness"
        ),
    ),
    EtymologyEntry(
        language="ar", lemma="تأمل",
        origin_summary=(
            "From root أ-م-ل ('-m-l) meaning 'to hope, to wait expectantly.' "
            "Ta'ammul (Form V verbal noun) is contemplation, reflection, deep "
            "consideration — the reflexive sense of 'placing oneself in a "
            "state of expectant attention.' Common in Sufi vocabulary for "
            "mystical reflection. The same root gives amal (hope)."
        ),
        roots=["Proto-Semitic *'-m-l (to hope)"],
        cognates=["Hebrew אמל (amal, weak/wretched — different sense)"],
        semantic_shift=(
            "'to hope, to expect' → contemplation as expectant attention; "
            "mystical reflection in Sufism"
        ),
    ),
    EtymologyEntry(
        language="ar", lemma="ضيافة",
        origin_summary=(
            "From root ض-ي-ف (ḍ-y-f) meaning 'to be a guest, to incline "
            "toward.' Ḍiyāfa is hospitality — a defining cultural value in "
            "Arab society, with extensive customary law (the right of three "
            "days' hospitality even to enemies). Same root gives ḍayf (guest) "
            "and aḍāfa (to add — to add a person as a guest is to extend "
            "hospitality)."
        ),
        roots=["Proto-Semitic *ḍ-y-f (to incline, to host)"],
        semantic_shift=(
            "'to incline toward / take in' → hosting a guest → hospitality as "
            "cardinal cultural virtue"
        ),
    ),
    EtymologyEntry(
        language="ar", lemma="غضب",
        origin_summary=(
            "From root غ-ض-ب (gh-ḍ-b) meaning 'to be angry.' Ghaḍab is anger "
            "— discussed extensively in Islamic ethics as one of the passions "
            "to be controlled by reason ('aql) and patience (ṣabr). "
            "Distinguished from ḥilm (forbearance, restraint of anger), which "
            "is the cardinal virtue of nobility."
        ),
        roots=["Proto-Semitic *gh-ḍ-b (to be angry)"],
        cognates=[
            "Hebrew קצף (qatzaf, to be angry — different root, similar concept)",
        ],
        semantic_shift=(
            "Pan-Semitic 'anger' → moral discussion of how anger is to be "
            "channeled or restrained"
        ),
    ),
    EtymologyEntry(
        language="ar", lemma="حب",
        origin_summary=(
            "From root ح-ب-ب (ḥ-b-b) meaning 'to love, to desire.' Ḥubb is "
            "love — distinguished from passion ('ishq) and tenderness "
            "(mawadda). Sufi tradition develops a refined vocabulary of love- "
            "relationship to God. Same root gives ḥabīb (beloved — title of "
            "the Prophet) and ḥabba (a single grain — the seed of love that "
            "grows)."
        ),
        roots=["Proto-Semitic *ḥ-b-b (to love)"],
        cognates=[
            "Hebrew חב (ḥabh — root family, related)",
            "Aramaic ḥbb (to love)",
        ],
        semantic_shift=(
            "'to love' → love as a moral and spiritual reality; a single "
            "grain (ḥabba) shares the root — love as the seed of the heart"
        ),
    ),
    EtymologyEntry(
        language="ar", lemma="بركة",
        origin_summary=(
            "From root ب-ر-ك (b-r-k) meaning 'to bless, to kneel (as a "
            "camel).' Baraka is blessing — divine grace inhering in places, "
            "persons, objects. Etymologically related to 'kneeling': the "
            "camel kneels to be loaded; humans kneel to receive blessing. "
            "Same root gives birka (pool — where blessing/water collects) and "
            "tabarruk (seeking blessing). English 'baraka' has entered "
            "counterculture vocabulary."
        ),
        roots=["Proto-Semitic *b-r-k (to kneel, to bless)"],
        cognates=[
            "Hebrew ברך (barakh, to bless — same root, as in Baruch)",
            "Aramaic brk (to bless/kneel)",
        ],
        semantic_shift=(
            "'to kneel' → to receive blessing while kneeling → divine "
            "blessing inhering in things; also: pool (where blessing "
            "collects)"
        ),
    ),
    EtymologyEntry(
        language="ar", lemma="حياة",
        origin_summary=(
            "From root ح-ي-ي/و (ḥ-y-y/w) meaning 'to live.' Ḥayāt is life — "
            "also the root of ḥayyā (to greet, lit. 'to wish life'), as in "
            "the Islamic greeting taḥiyyāt and the call to prayer 'ḥayyā 'alā "
            "ṣ-ṣalāt' (come to prayer, lit. 'rouse-to-life toward prayer'). "
            "Cognate with Hebrew ḥai (alive) — the toast 'l'chaim'."
        ),
        roots=["Proto-Semitic *ḥ-y-y (to live)"],
        cognates=[
            "Hebrew חיים (ḥayyim, life — same root, as in 'l'chaim' toast)",
            "Aramaic ḥayyīn (life)",
        ],
        semantic_shift="'to live' → life; also: greeting (wishing life), call to prayer",
    ),
    EtymologyEntry(
        language="ar", lemma="موت",
        origin_summary=(
            "From root م-و-ت (m-w-t) meaning 'to die.' Mawt is death — "
            "discussed extensively in Islamic eschatology and Sufi "
            "spirituality (the 'death before death' = mystical annihilation "
            "of self). Cognate with Hebrew māwet (death) — Pan-Semitic. The "
            "Greek god Mot of death (Ugaritic mythology) preserves the same "
            "Proto-Semitic root."
        ),
        roots=["Proto-Semitic *m-w-t (to die)"],
        cognates=[
            "Hebrew מות (māwet, death — same root)",
            "Ugaritic Mot (the god of death)",
            "Aramaic mawtā (death)",
        ],
        semantic_shift=(
            "Pan-Semitic 'death'; in Sufism, also: ego-death (the spiritual "
            "annihilation that precedes union with God)"
        ),
    ),
    EtymologyEntry(
        language="ar", lemma="بدوي",
        origin_summary=(
            "From bādiya (desert, open plain), from root ب-د-و (b-d-w) "
            "meaning 'to appear, to be open/visible.' Badawī (English "
            "'bedouin') is a desert-dweller — etymologically 'one of the open "
            "spaces.' Distinguished from ḥaḍar (settled people). Ibn "
            "Khaldūn's 14th-c. sociology treats this opposition as "
            "foundational to civilizational dynamics."
        ),
        roots=["Proto-Semitic *b-d-w (to appear, open ground)"],
        cognates=["English 'bedouin' (from Arabic via French)"],
        semantic_shift=(
            "'open desert' → desert-dweller → the cultural/sociological "
            "category of nomadic Arabs"
        ),
    ),
    EtymologyEntry(
        language="ar", lemma="قدر",
        origin_summary=(
            "From root ق-د-ر (q-d-r) meaning 'to measure, to determine, to be "
            "capable.' Qadar is divine decree/destiny — the predetermined "
            "measure of all things. Foundational concept in Islamic theology "
            "(the qadariyya/jabariyya debate over free will vs. "
            "predestination). Same root gives qudra (power) — fate as God's "
            "measuring power. The Night of Power (laylat al-qadr) is named "
            "for this."
        ),
        roots=["Proto-Semitic *q-d-r (to measure, to be able)"],
        cognates=[
            "Hebrew קדר (qadar — different sense, 'to be dark')",
            "Aramaic qdr (to be able)",
        ],
        semantic_shift=(
            "'to measure, to determine' → divine decree → predetermined fate; "
            "also: power (qudra)"
        ),
    ),
    EtymologyEntry(
        language="ar", lemma="أمل",
        origin_summary=(
            "From root أ-م-ل ('-m-l) meaning 'to hope.' Amal is hope — paired "
            "with khawf (fear) as the twin emotions oriented toward the "
            "future. Sufi vocabulary develops a nuanced theory of hope "
            "(rajā') and fear (khawf) as complementary dispositions of the "
            "heart. Modern Arabic political vocabulary uses amal extensively "
            "(e.g., the Lebanese Amal Movement)."
        ),
        roots=["Proto-Semitic *'-m-l (to hope)"],
        cognates=["Hebrew אמל (amal — different sense)"],
        semantic_shift=(
            "'to hope' → hope as one of the twin disposition-emotions toward "
            "the future; foundational in Sufi psychology"
        ),
    ),
    EtymologyEntry(
        language="ar", lemma="حنين",
        origin_summary=(
            "From root ح-ن-ن (ḥ-n-n) meaning 'to yearn, to long, to be "
            "tender.' Ḥanīn is yearning/nostalgia — closely paralleled by "
            "Portuguese saudade and Welsh hiraeth. Often a longing for a lost "
            "place or person, with strong emotional weight in Arab poetic "
            "tradition. Same root gives ḥanān (tenderness, affection — "
            "usually maternal)."
        ),
        roots=["Proto-Semitic *ḥ-n-n (to be tender, gracious)"],
        cognates=[
            "Hebrew חן (ḥen, grace, favor — same root)",
            "Hebrew חנן (ḥanan, to be gracious — as in the name Hannah)",
        ],
        semantic_shift=(
            "'to be tender, gracious' → yearning → nostalgia, longing for "
            "what is absent"
        ),
    ),
    EtymologyEntry(
        language="ar", lemma="كتب",
        origin_summary=(
            "Imperative or perfect form of root ك-ت-ب (k-t-b) — 'he wrote.' "
            "The phrase kutiba 'alaykum (it has been written upon you) "
            "introduces obligation in the Quran (e.g., kutiba 'alaykum al- "
            "ṣiyām = fasting has been prescribed for you). The metaphor of "
            "obligation as inscription is central to Islamic legal language."
        ),
        roots=["Proto-Semitic *k-t-b (to write)"],
        cognates=["Hebrew כתב (katav, to write)"],
        semantic_shift=(
            "'he wrote' → 'it has been written/decreed' → divine "
            "prescription, religious obligation"
        ),
    ),
    EtymologyEntry(
        language="ar", lemma="حرف",
        origin_summary=(
            "From root ح-ر-ف (ḥ-r-f) meaning 'edge, side, letter.' Ḥarf is "
            "letter/character — the smallest unit of writing; same word means "
            "'edge' (e.g., of a road, of a knife). The Quran's recitation "
            "tradition speaks of 'aḥruf' (the seven readings/edges/aspects). "
            "Tools and inscription overlap etymologically."
        ),
        roots=["Proto-Semitic *ḥ-r-p/f (edge, sharp side)"],
        cognates=["Hebrew חרף (ḥaraf — related root family)"],
        semantic_shift=(
            "'edge, side' → the marks at the edge of meaning → letters, "
            "characters of writing"
        ),
    ),
    EtymologyEntry(
        language="ar", lemma="نسب",
        origin_summary=(
            "From root ن-س-ب (n-s-b) meaning 'to be related, to attribute.' "
            "Nasab is lineage/genealogy — one of the pillars of pre-Islamic "
            "and early Islamic Arab social organization. The hadith "
            "literature is structured around isnād (chain of transmission), "
            "which uses the same etymological logic — every saying must have "
            "its lineage of transmitters."
        ),
        roots=["Proto-Semitic *n-s-b (to lift up, attribute)"],
        cognates=[
            "Hebrew נצב (natzav — related)",
            "Aramaic nsb (to take, lift)",
        ],
        semantic_shift=(
            "'to attribute, to relate' → lineage/genealogy → also: hadith "
            "chain of transmitters (isnād)"
        ),
    ),
    EtymologyEntry(
        language="ar", lemma="صحراء",
        origin_summary=(
            "From root ص-ح-ر (ṣ-ḥ-r) meaning 'to be tawny, brownish-yellow' — "
            "the color of desert sand. Ṣaḥrā' is desert — the proper name al- "
            "Ṣaḥrā' (the Sahara) entered all European languages from Arabic. "
            "Color and landscape merge: the Sahara is etymologically 'the "
            "tawny one.'"
        ),
        roots=["Proto-Semitic *ṣ-ḥ-r (tawny color)"],
        cognates=["English 'Sahara' (from Arabic al-Ṣaḥrā')"],
        semantic_shift=(
            "'tawny color' → the tawny landscape → the desert; specifically "
            "the Sahara"
        ),
    ),
    EtymologyEntry(
        language="ar", lemma="ساعة",
        origin_summary=(
            "From root س-و-ع (s-w-') meaning 'to extend, to walk, time.' Sā'a "
            "is hour/clock/the Hour (eschatological). Multilayered word: a "
            "temporal hour, a wristwatch, AND the Last Hour (qiyāma — the "
            "apocalypse). Quranic eschatology speaks of 'when the Hour comes' "
            "(idhā jā'at al-sā'a). Time-keeping and the End of Time share "
            "this word."
        ),
        roots=["Proto-Semitic *s-w-' (to walk, to pass time)"],
        cognates=[
            "Hebrew שעה (sha'ah, hour — same root)",
            "Aramaic sha'ā (hour)",
        ],
        semantic_shift=(
            "'to extend/pass' → hour, unit of time → also: the Last Hour (the "
            "end-time)"
        ),
    ),
    EtymologyEntry(
        language="ar", lemma="بيت",
        origin_summary=(
            "From root ب-ي-ت (b-y-t) meaning 'to spend the night, to dwell.' "
            "Bayt is house/home — but also a verse of poetry (a poetic "
            "'house' of meaning). The Bayt Allāh (House of God) is the Kaaba "
            "in Mecca. The same root gives bāta (to spend the night) and "
            "bayāt (overnight stay)."
        ),
        roots=["Proto-Semitic *b-y-t (house)"],
        cognates=[
            "Hebrew בית (bayit, house — same root, as in Bethlehem = beit leḥem, house of bread)",
            "Aramaic bētā (house)",
            "Greek 'beta' (the Hebrew/Phoenician letter, originally a pictogram of a house)",
        ],
        semantic_shift="'house, dwelling' → also: a verse of poetry (poetic house)",
    ),
    EtymologyEntry(
        language="ar", lemma="كرسي",
        origin_summary=(
            "From a root meaning 'to be firm, to set up.' Kursī is "
            "chair/throne — but in Quranic vocabulary, the kursī of God is "
            "the divine throne/footstool ('His Kursī extends over heaven and "
            "earth' — Ayat al-Kursī, 2:255). Distinct from 'arsh (the higher "
            "throne). Hebrew kissē' (throne) is the cognate, used for kingly "
            "thrones."
        ),
        roots=["Proto-Semitic *k-r-s (to be firm, throne)"],
        cognates=[
            "Hebrew כסא (kissē', throne, chair — same root)",
            "Aramaic kursē (throne)",
        ],
        semantic_shift=(
            "'firm seat' → chair, throne → in Quranic theology: the divine "
            "footstool"
        ),
    ),
    EtymologyEntry(
        language="ar", lemma="خبر",
        origin_summary=(
            "From root خ-ب-ر (kh-b-r) meaning 'to know by experience, to "
            "inform.' Khabar is news/information — but in classical Islamic "
            "learning, khabar is also a technical term for 'transmitted "
            "report' (especially of hadith). The same root gives khabīr "
            "(expert — one who knows by experience) and ikhtibār (test, "
            "examination)."
        ),
        roots=["Proto-Semitic *kh-b-r (to know, to be expert)"],
        cognates=[
            "Hebrew חבר (ḥaver, friend/companion — different sense from related root)",
        ],
        semantic_shift=(
            "'to know by experience' → news, report → in Islamic scholarship: "
            "traditional report transmitted from earlier generations"
        ),
    ),
    EtymologyEntry(
        language="ar", lemma="قهوة",
        origin_summary=(
            "Originally meaning 'wine' or 'a strong drink,' qahwa was "
            "reapplied to coffee (qahwa al-bunn = 'wine of the bean') by Sufi "
            "orders in 15th-c. Yemen who used it to stay awake during dhikr. "
            "The Arabic word entered Turkish (kahve), then Italian (caffè), "
            "and from there into all European languages — making 'coffee' an "
            "Arabic loanword in nearly every world language."
        ),
        roots=["Arabic qahwa (originally a wine/strong drink)"],
        cognates=[
            "English 'coffee' (via Italian caffè, Turkish kahve, Arabic qahwa)",
            "French 'café'",
            "Italian 'caffè'",
            "German 'Kaffee'",
        ],
        semantic_shift=(
            "'wine, strong drink' → coffee (the new strong drink) → spread "
            "globally with the commodity"
        ),
    ),

    # ── HE additions (generated by gen_etymology.py) ──
    EtymologyEntry(
        language="he", lemma="תורה",
        origin_summary=(
            "From root י-ר-ה (y-r-h) meaning 'to throw, to point, to "
            "instruct.' Torah is teaching/instruction — the divinely revealed "
            "law and narrative; specifically the Pentateuch (five books of "
            "Moses). The semantic core is 'pointing the way' rather than "
            "'law' — Torah is direction/guidance more than legalistic code. "
            "The same root gives moreh (teacher) and horā'ah (instruction)."
        ),
        roots=[
            "Proto-Semitic *y-r-h (to point, to throw)",
            "Hebrew yarah (to teach, to point out)",
        ],
        cognates=[
            "Arabic ورى (warā — related root)",
            "Aramaic 'orāyetā (teaching)",
        ],
        semantic_shift=(
            "'to point/throw straight' → instruction → divine teaching → the "
            "Pentateuch"
        ),
    ),
    EtymologyEntry(
        language="he", lemma="צדק",
        origin_summary=(
            "From root צ-ד-ק (ts-d-q) meaning 'to be straight, just, "
            "righteous.' Tzedek is justice/righteousness — paired centrally "
            "with mishpat (judgment) in prophetic ethics. The same root gives "
            "tzaddik (righteous person), tzedakah (charity — etymologically "
            "'doing justice'), and Yehoshua/Joshua's longer name and "
            "Melchizedek (king of righteousness). Cognate with Arabic ṣidq "
            "(truth/sincerity)."
        ),
        roots=["Proto-Semitic *ṣ-d-q (just, true)"],
        cognates=["Arabic صدق (ṣidq, truth)", "Aramaic ṣiddeq"],
        semantic_shift=(
            "'to be straight, just' → righteousness; charity (tzedakah) is "
            "etymologically 'justice-giving'"
        ),
    ),
    EtymologyEntry(
        language="he", lemma="חסד",
        origin_summary=(
            "From root ח-ס-ד (ḥ-s-d) — meaning 'loyal love, covenant "
            "kindness.' Ḥesed is one of the most theologically important "
            "Hebrew words: covenant loyalty, faithful love, mercy that goes "
            "beyond duty. Often translated 'lovingkindness' (Coverdale) or "
            "'steadfast love.' Pivotal in the Psalms ('His ḥesed endures "
            "forever'). The plural ḥasidim (the pious) gave the name to the "
            "Hasidic Jewish movement."
        ),
        roots=["Proto-Semitic *ḥ-s-d (loyal love)"],
        cognates=["Aramaic ḥsd (devoted)"],
        semantic_shift=(
            "'covenantal loyal love' → mercy, kindness; gives the name "
            "'Hasidim' (the loyally devoted)"
        ),
    ),
    EtymologyEntry(
        language="he", lemma="רוח",
        origin_summary=(
            "From root ר-ו-ח (r-w-ḥ) meaning 'to breathe, wind, spirit.' Rūaḥ "
            "is spirit/wind/breath — like Greek pneuma and Latin spiritus, "
            "the same word covers the physical wind, the breath of life, and "
            "the spiritual reality. The Spirit of God hovers over the waters "
            "(Genesis 1:2) using this word. Cognate with Arabic rūḥ."
        ),
        roots=["Proto-Semitic *r-w-ḥ (to breathe, wind)"],
        cognates=["Arabic روح (rūḥ, spirit)", "Aramaic rūḥā (spirit)"],
        semantic_shift=(
            "'breath, wind' → spirit (animating breath) → also the divine "
            "creative Spirit"
        ),
    ),
    EtymologyEntry(
        language="he", lemma="כבוד",
        origin_summary=(
            "From root כ-ב-ד (k-b-d) meaning 'to be heavy, weighty.' Kavod is "
            "honor/glory — etymologically 'the weight' of someone's presence "
            "or importance. The Kavod YHWH (Glory of the Lord) is the visible "
            "weight of divine presence (e.g., the cloud filling the "
            "Tabernacle). The fifth commandment 'honor your father and "
            "mother' (kibbed et avikha) derives from this root."
        ),
        roots=["Proto-Semitic *k-b-d (to be heavy)"],
        cognates=["Arabic كبير (kabīr, great)", "Aramaic kebad (heavy)"],
        semantic_shift=(
            "'to be heavy' → the weight of presence → honor, glory; the Glory "
            "of the Lord"
        ),
    ),
    EtymologyEntry(
        language="he", lemma="כושר",
        origin_summary=(
            "From root כ-ש-ר (k-sh-r) meaning 'to be fit, proper, valid.' "
            "Kosher (kashrut = the laws thereof) is the system of Jewish "
            "dietary and ritual law — etymologically 'fitness/properness' in "
            "the broadest sense. Kasher means valid, proper, ritually fit. "
            "The English 'kosher' was borrowed from Yiddish, ultimately from "
            "this Hebrew root. Modern Hebrew kosher = 'physically fit' "
            "(athletic)."
        ),
        roots=["Proto-Semitic *k-sh-r (to be fit, ready)"],
        cognates=["Arabic كثر (kathara, to be many — possibly related)"],
        semantic_shift=(
            "'to be fit, proper' → ritually proper food → 'kosher' (English "
            "loan); also modern: physical fitness"
        ),
    ),
    EtymologyEntry(
        language="he", lemma="שכינה",
        origin_summary=(
            "From root ש-כ-נ (sh-k-n) meaning 'to dwell, to settle.' "
            "Shekhinah is the indwelling presence of God — the divine "
            "presence that dwells with Israel, in the Tabernacle, in the "
            "Temple. A Rabbinic (post-biblical) term, central to Jewish "
            "mystical and Hasidic theology. The same root gives mishkan "
            "(Tabernacle, lit. 'dwelling-place') and shakhen (neighbor)."
        ),
        roots=["Proto-Semitic *sh-k-n (to dwell)"],
        cognates=[
            "Arabic سكن (sakana, to dwell — same root)",
            "Arabic مسكن (maskan, dwelling-place)",
        ],
        semantic_shift="'to dwell' → divine indwelling presence (Shekhinah)",
    ),
    EtymologyEntry(
        language="he", lemma="תיקון",
        origin_summary=(
            "From root ת-ק-נ (t-q-n) meaning 'to set right, to repair.' "
            "Tikkun is repair/restoration — central to Lurianic Kabbalah's "
            "tikkun olam (repair of the world): humans help repair the cosmic "
            "brokenness through ethical and ritual action. In modern Jewish "
            "vocabulary, tikkun olam has become a slogan of social justice "
            "activism, secularizing the Kabbalistic concept."
        ),
        roots=["Proto-Semitic *t-q-n (to make right)"],
        cognates=["Aramaic taqqen (to set up, restore)"],
        semantic_shift=(
            "'to repair, set right' → cosmic restoration (Lurianic Kabbalah) "
            "→ modern social justice (tikkun olam)"
        ),
    ),
    EtymologyEntry(
        language="he", lemma="חכמה",
        origin_summary=(
            "From root ח-כ-מ (ḥ-k-m) meaning 'to be wise.' Ḥokhmah is wisdom "
            "— both practical wisdom and the personified divine Wisdom of "
            "Proverbs (Lady Ḥokhmah crying out in the streets). In Kabbalah, "
            "Ḥokhmah is the second sefirah, divine wisdom. The Greek Sophia "
            "(wisdom) translates ḥokhmah in the Septuagint. Cognate with "
            "Arabic ḥikma."
        ),
        roots=["Proto-Semitic *ḥ-k-m (to be wise)"],
        cognates=["Arabic حكمة (ḥikma, wisdom)", "Aramaic ḥekmā (wisdom)"],
        semantic_shift=(
            "'to be wise' → wisdom as virtue → personified divine Wisdom "
            "(Hebrew/Greek tradition)"
        ),
    ),
    EtymologyEntry(
        language="he", lemma="צבא",
        origin_summary=(
            "From root צ-ב-א (ts-b-') meaning 'army, host, to wage war.' "
            "Tzava is army — also 'host of heaven' (the stars, the angels). "
            "The divine title YHWH Tzevaot ('Lord of Hosts') is among the "
            "most common in the Hebrew Bible. Modern Israeli Tzahal (IDF) "
            "preserves the same root. The Sabbatical/Sabbath/Sabaoth "
            "confusion in Christian liturgy ('Lord God of Sabaoth') derives "
            "from this Hebrew word."
        ),
        roots=["Proto-Semitic *ṣ-b-' (army, host)"],
        cognates=["Arabic سبأ (Sheba — geographic name, possibly related)"],
        semantic_shift=(
            "'army, host' → host of heaven (stars/angels) → divine title "
            "'Lord of Hosts'; modern: Israeli army"
        ),
    ),
    EtymologyEntry(
        language="he", lemma="קודש",
        origin_summary=(
            "From root ק-ד-ש (q-d-sh) meaning 'to be set apart, holy.' Qodesh "
            "is holiness — etymologically 'separation/setting-apart.' The "
            "Holy of Holies (qodesh ha-qodashim) is the innermost sanctuary. "
            "Same root gives qiddush (sanctification — e.g., the Sabbath "
            "blessing over wine), qaddish (the prayer 'May His great name be "
            "sanctified'), and qedoshim (holy ones, martyrs)."
        ),
        roots=["Proto-Semitic *q-d-sh (to be holy)"],
        cognates=[
            "Arabic قدس (quds, sanctity — al-Quds = Jerusalem)",
            "Aramaic qaddiš (holy)",
        ],
        semantic_shift=(
            "'to set apart' → holy/sacred; gives qaddish prayer, qiddush "
            "blessing, Holy of Holies"
        ),
    ),
    EtymologyEntry(
        language="he", lemma="ברכה",
        origin_summary=(
            "From root ב-ר-כ (b-r-k) meaning 'to bless, to kneel.' Berakhah "
            "is blessing — etymologically 'kneeling' (one kneels to bless or "
            "be blessed). Birkhot ha-shaḥar (morning blessings) and the "
            "structure of Jewish liturgy revolve around this concept. Same "
            "root as Arabic baraka. The name Baruch ('blessed') and the "
            "formula 'Barukh attah Adonai' (Blessed are You, O Lord) open "
            "every Jewish blessing."
        ),
        roots=["Proto-Semitic *b-r-k (to kneel, bless)"],
        cognates=["Arabic بركة (baraka, blessing)", "Aramaic brk (to bless)"],
        semantic_shift="'to kneel' → kneeling to bless → blessing as ritual speech-act",
    ),
    EtymologyEntry(
        language="he", lemma="תשובה",
        origin_summary=(
            "From root ש-ו-ב (sh-w-b) meaning 'to return.' Teshuvah is "
            "repentance — etymologically 'return/turning-back.' The High Holy "
            "Days of Rosh Hashanah and Yom Kippur are the season of teshuvah. "
            "Maimonides' Hilkhot Teshuvah (Laws of Repentance) is one of the "
            "Mishneh Torah's most important sections. Repentance as return- "
            "to-God preserves the spatial metaphor of the original verb."
        ),
        roots=["Proto-Semitic *sh-w-b (to return)"],
        cognates=["Aramaic tūb (to return)"],
        semantic_shift=(
            "'to return' → returning to God → repentance as moral and "
            "spiritual return"
        ),
    ),
    EtymologyEntry(
        language="he", lemma="נשמה",
        origin_summary=(
            "From root נ-ש-מ (n-sh-m) meaning 'to breathe.' Neshamah is soul "
            "— etymologically 'breath.' Hebrew has multiple soul-words: "
            "nefesh (animating life force), rūaḥ (spirit/wind), neshamah (the "
            "higher rational soul). Kabbalah develops a five-fold soul "
            "typology layering these. Cognate with Arabic nasama (breath)."
        ),
        roots=["Proto-Semitic *n-sh-m (to breathe)"],
        cognates=[
            "Arabic نسمة (nasama, breath/soul)",
            "Aramaic nešmā (breath)",
        ],
        semantic_shift=(
            "'to breathe' → breath as soul → in Kabbalah, the higher rational "
            "soul"
        ),
    ),
    EtymologyEntry(
        language="he", lemma="מצווה",
        origin_summary=(
            "From root צ-ו-ה (ts-w-h) meaning 'to command.' Mitzvah is "
            "commandment — but also 'good deed' in popular usage ('it's a "
            "mitzvah to help'). The 613 mitzvot are the count of commandments "
            "in the Torah. The same root gives bar/bat mitzvah (son/daughter "
            "of the commandment — coming-of-age ritual at age 13/12)."
        ),
        roots=["Proto-Semitic *ṣ-w-h (to command)"],
        cognates=[
            "Arabic وصى (waṣṣā, to enjoin)",
            "Aramaic ṣawwī (to command)",
        ],
        semantic_shift=(
            "'to command' → divine commandment → good deed; also: bar/bat "
            "mitzvah coming-of-age"
        ),
    ),
    EtymologyEntry(
        language="he", lemma="כתובה",
        origin_summary=(
            "From root כ-ת-ב (k-t-b) meaning 'to write.' Ketubah is the "
            "Jewish marriage contract — etymologically 'a written document.' "
            "Ancient and elaborate document specifying the husband's "
            "financial obligations to the wife, including provision in case "
            "of death or divorce. Often artistically illuminated. Same root "
            "as Arabic kitāb."
        ),
        roots=["Proto-Semitic *k-t-b (to write)"],
        cognates=["Arabic كتاب (kitāb, book)", "Aramaic ktab (to write)"],
        semantic_shift="'written thing' → the Jewish marriage contract",
    ),
    EtymologyEntry(
        language="he", lemma="אהבה",
        origin_summary=(
            "From root א-ה-ב ('-h-b) meaning 'to love.' Ahavah is love — "
            "central to Deuteronomic theology ('You shall love the Lord your "
            "God with all your heart, soul, and might'). The Shema's "
            "commanded love (ve-ahavtah) shaped Jewish, Christian, and "
            "Islamic theological vocabulary. Distinguished from ḥesed (loyal "
            "love) and dodi (beloved, as in Song of Songs)."
        ),
        roots=["Proto-Semitic *'-h-b (to love)"],
        semantic_shift=(
            "'to love' → love as commanded religious obligation; also: love- "
            "poetry as in Song of Songs"
        ),
    ),
    EtymologyEntry(
        language="he", lemma="ברית",
        origin_summary=(
            "From a root meaning 'to cut, to bind by cutting.' Brit is "
            "covenant — etymologically 'a cutting' (because covenants were "
            "sealed by cutting animals in two and walking between them; cf. "
            "Genesis 15). The Brit Milah (covenant of circumcision) preserves "
            "the etymology — covenant established by cutting. The Hebrew "
            "Bible's central organizing concept; the New Covenant ('berit "
            "ḥadashah') of Jeremiah 31 became foundational for Christian "
            "theology."
        ),
        roots=[
            "Possibly Proto-Semitic *b-r-t (to cut) or related to Akkadian birītu (clasp/fetter)",
        ],
        cognates=["Akkadian birītu (clasp, bond)"],
        semantic_shift=(
            "'cutting' → covenant sealed by cutting → covenant as religious- "
            "legal bond"
        ),
    ),
    EtymologyEntry(
        language="he", lemma="כיפור",
        origin_summary=(
            "From root כ-פ-ר (k-p-r) meaning 'to cover, to atone.' Kippur is "
            "atonement — etymologically 'covering' (sin is 'covered' by "
            "atoning ritual). Yom Kippur (Day of Atonement) is the holiest "
            "day of the Jewish year. The same root gives kapporet (the cover "
            "of the Ark of the Covenant — translated 'mercy seat' in "
            "Christian Bibles). Cognate with Arabic kaffara (to atone, "
            "expiate)."
        ),
        roots=["Proto-Semitic *k-p-r (to cover, to wipe)"],
        cognates=[
            "Arabic كفر (kaffara, to atone)",
            "Aramaic kappēr (to atone)",
        ],
        semantic_shift="'to cover, wipe' → atonement (sin covered) → Yom Kippur",
    ),
    EtymologyEntry(
        language="he", lemma="משיח",
        origin_summary=(
            "From root מ-ש-ח (m-sh-ḥ) meaning 'to anoint.' Mashiaḥ is the "
            "anointed one — Messiah. Originally any anointed king or priest; "
            "over time, the eschatological figure expected to redeem Israel. "
            "Christian terminology preserves the Greek calque: Christos = "
            "Greek for mashiaḥ. The Hebrew/Greek/English chain gives English "
            "'Christ' the same etymology as 'Messiah.'"
        ),
        roots=["Proto-Semitic *m-sh-ḥ (to anoint)"],
        cognates=[
            "Aramaic məšīḥā (Messiah)",
            "Greek Christos (anointed — direct calque of mashiaḥ)",
            "English 'Christ' (via Greek)",
            "Arabic مسيح (Masīḥ, Christ)",
        ],
        semantic_shift=(
            "'to anoint' → anointed king/priest → eschatological redeemer; "
            "Greek calque gives 'Christ'"
        ),
    ),
    EtymologyEntry(
        language="he", lemma="גלות",
        origin_summary=(
            "From root ג-ל-ה (g-l-h) meaning 'to uncover, to exile.' Galut is "
            "exile — etymologically 'being uncovered/displaced.' The "
            "Babylonian Exile (Galut Bavel) and the long Diaspora that "
            "followed are central to Jewish historical and theological "
            "consciousness. Same root gives galui (revealed, in the open) and "
            "megilat (scroll — what is unrolled/revealed)."
        ),
        roots=["Proto-Semitic *g-l-y/h (to uncover)"],
        cognates=["Aramaic galī (to reveal)"],
        semantic_shift=(
            "'to uncover, displace' → exile, Diaspora; central concept in "
            "Jewish historical thought"
        ),
    ),
    EtymologyEntry(
        language="he", lemma="פסח",
        origin_summary=(
            "From root פ-ס-ח (p-s-ḥ) meaning 'to pass over, to skip.' Pesaḥ "
            "is Passover — the festival commemorating the Exodus, when the "
            "angel of death 'passed over' the Israelite houses marked with "
            "lamb's blood. The English 'Passover' is a direct calque. "
            "Christian Easter (Greek Pascha) takes its name from the same "
            "Hebrew root through Aramaic."
        ),
        roots=["Proto-Semitic *p-s-ḥ (to skip, pass over, limp)"],
        cognates=[
            "Aramaic pesḥā (Passover, Easter)",
            "Greek Pascha (Easter)",
            "English 'Easter'/'paschal' (related forms)",
        ],
        semantic_shift="'to skip/pass over' → the Passover festival",
    ),
    EtymologyEntry(
        language="he", lemma="סוכה",
        origin_summary=(
            "From root ס-כ-כ (s-k-k) meaning 'to cover with branches, to make "
            "a booth.' Sukkah is the booth/hut of the Festival of Sukkot "
            "(Tabernacles), commemorating the wilderness wandering. Built "
            "each year for the seven-day festival, with a roof of branches "
            "through which one must see the stars. Same root family gives "
            "sekhakh (the branch-roof) and Sukkot (the festival)."
        ),
        roots=["Proto-Semitic *s-k-k (to cover, to weave a covering)"],
        cognates=["Aramaic sukkā (booth)"],
        semantic_shift=(
            "'to cover with branches' → the temporary booth → festival of "
            "Sukkot/Tabernacles"
        ),
    ),
    EtymologyEntry(
        language="he", lemma="מנורה",
        origin_summary=(
            "From root נ-ו-ר (n-w-r) meaning 'to give light' (same root as "
            "Arabic nūr). Menorah is lampstand/candelabrum — specifically the "
            "seven-branched lampstand of the Tabernacle/Temple, described in "
            "Exodus 25. The eight-branched Hanukkiah (Hanukkah candelabrum) "
            "is named for it. The Menorah is one of Israel's national "
            "emblems."
        ),
        roots=["Proto-Semitic *n-w-r (light)"],
        cognates=[
            "Arabic منارة (manāra, lighthouse → English 'minaret')",
            "Aramaic mənārā (lamp)",
        ],
        semantic_shift=(
            "'lamp/lampstand' → the Temple seven-branched menorah → Israeli "
            "national emblem"
        ),
    ),
    EtymologyEntry(
        language="he", lemma="שמיים",
        origin_summary=(
            "From a root possibly meaning 'high, heights' or related to mayim "
            "(water) — heaven traditionally seen as containing 'waters above "
            "the firmament.' Shamayim is dual form: heavens. Cognate with "
            "Akkadian šamû, Arabic samā', Aramaic shemayyā — Pan-Semitic word "
            "for sky/heavens."
        ),
        roots=["Proto-Semitic *šamayu (sky, heaven)"],
        cognates=[
            "Arabic سماء (samā', sky)",
            "Akkadian šamû (sky)",
            "Aramaic shemayyā (heavens)",
        ],
        semantic_shift="'heights/heavens' → sky → divine heavenly realm",
    ),
    EtymologyEntry(
        language="he", lemma="ארץ",
        origin_summary=(
            "From a Pan-Semitic root for 'earth, land.' Eretz is earth/land — "
            "Eretz Yisrael (Land of Israel) is the foundational political- "
            "religious concept. Cognate with Arabic arḍ, Aramaic ar'a, "
            "Akkadian erṣetu. One of the oldest words in Semitic vocabulary, "
            "attested unchanged across millennia."
        ),
        roots=["Proto-Semitic *'arṣ (earth, land)"],
        cognates=[
            "Arabic أرض (arḍ, land)",
            "Aramaic ar'ā (land)",
            "Akkadian erṣetu (earth)",
        ],
        semantic_shift=(
            "Pan-Semitic 'earth, land' → unchanged across millennia; "
            "foundational word"
        ),
    ),
    EtymologyEntry(
        language="he", lemma="מים",
        origin_summary=(
            "Pan-Semitic word for water; dual form 'maim' suggests an ancient "
            "association of water with paired waters (above/below the "
            "firmament, fresh/salt, etc.). Cognate with Arabic mā', Aramaic "
            "mayyā. The Mediterranean Sea is yam ha-tikhon (the middle sea) "
            "in Hebrew. Water-vocabulary in the Hebrew Bible is rich and "
            "cosmologically significant."
        ),
        roots=["Proto-Semitic *may-/maw- (water)"],
        cognates=["Arabic ماء (mā', water)", "Aramaic mayyā (water)"],
        semantic_shift=(
            "Pan-Semitic 'water'; the dual form 'maim' may reflect ancient "
            "cosmological pairings"
        ),
    ),
    EtymologyEntry(
        language="he", lemma="אש",
        origin_summary=(
            "From a Proto-Semitic root for 'fire.' Esh is fire — central in "
            "biblical theophany (the burning bush, the pillar of fire, fire "
            "from heaven). Cognate with Arabic 'iyāsh (related), Akkadian "
            "išātu. Religious sacrifice was burned by fire (qorban olah, the "
            "burnt offering); fire as the medium of divine consumption."
        ),
        roots=["Proto-Semitic *'iš- (fire)"],
        cognates=["Akkadian išātu (fire)", "Aramaic eššā (fire)"],
        semantic_shift="Pan-Semitic 'fire'; central in biblical theophany",
    ),
    EtymologyEntry(
        language="he", lemma="לב",
        origin_summary=(
            "From a Proto-Semitic root for 'heart.' Lev is heart — but in "
            "biblical psychology, the heart is the seat of thought and will, "
            "not just emotion (modern English 'mind' is closer). 'Love the "
            "Lord with all your heart, soul, and might' (Deut 6:5) commands "
            "cognitive-volitional commitment. Cognate with Arabic lubb "
            "(heart, kernel), Aramaic libbā."
        ),
        roots=["Proto-Semitic *libb- (heart)"],
        cognates=["Arabic لب (lubb, heart, kernel)", "Aramaic libbā (heart)"],
        semantic_shift=(
            "Pan-Semitic 'heart' as seat of cognition and volition (not just "
            "emotion as in modern English)"
        ),
    ),
    EtymologyEntry(
        language="he", lemma="דבר",
        origin_summary=(
            "From root ד-ב-ר (d-b-r) meaning 'to speak, word, thing.' Davar "
            "is word/thing — the same word covers speech AND the substantial "
            "reality named by speech (a 'thing'). 'Aseret ha-Dibrot' is 'the "
            "Ten Words/Things' = the Decalogue. The semantic identity of word "
            "and thing is profoundly important for biblical and Jewish "
            "theology of language and creation."
        ),
        roots=["Proto-Semitic *d-b-r (to speak)"],
        cognates=[
            "Aramaic dbr (to speak)",
            "Arabic دبر (dabbara, to manage/arrange — different sense from related root)",
        ],
        semantic_shift=(
            "'speech' = 'thing'; word and reality share a single noun in "
            "Hebrew"
        ),
    ),
    EtymologyEntry(
        language="he", lemma="תפילה",
        origin_summary=(
            "From root פ-ל-ל (p-l-l) — meaning unclear; possibly 'to judge, "
            "to mediate, to intervene.' Tefillah is prayer — the act of "
            "bringing one's case before God. The Tefillah par excellence is "
            "the Amidah (the standing prayer), the central liturgical prayer "
            "of Jewish daily worship. Same root gives palel (to plead, "
            "judge)."
        ),
        roots=["Proto-Semitic *p-l-l (to judge, mediate)"],
        semantic_shift="'to plead, mediate' → prayer as bringing one's case before God",
    ),
    EtymologyEntry(
        language="he", lemma="אמת",
        origin_summary=(
            "From root א-מ-נ ('-m-n) meaning 'to be firm, true' (same root as "
            "amen). Emet is truth — etymologically 'firmness, fidelity.' "
            "Hebrew truth-vocabulary emphasizes firmness/reliability, not "
            "propositional correspondence (which is more Greek). The seal of "
            "God in Rabbinic tradition is emet. The Golem of Prague was "
            "animated by inscribing emet on its forehead; deactivated by "
            "erasing the alef (leaving met = death)."
        ),
        roots=["Proto-Semitic *'-m-n (firm)"],
        cognates=["Arabic إيمان (īmān, faith)", "Hebrew/Aramaic amen"],
        semantic_shift=(
            "'firmness' → truth as reliable/firm; the seal of God; the word "
            "of life vs. death (emet/met) in Golem legend"
        ),
    ),
    EtymologyEntry(
        language="he", lemma="חיים",
        origin_summary=(
            "From root ח-י-י/ה (ḥ-y-y/h) meaning 'to live.' Ḥayyim is life "
            "(always in plural form — life as multiple, abundant). The toast "
            "'l'chaim!' (to life!) and the name Ḥayyim are this word. Cognate "
            "with Arabic ḥayāt. The Tree of Life (Etz Ḥayyim) and the "
            "personal name Ḥayyim ben Yosef Vital (Lurianic Kabbalah) "
            "preserve this central vocabulary."
        ),
        roots=["Proto-Semitic *ḥ-y-y (to live)"],
        cognates=["Arabic حياة (ḥayāt, life)", "Aramaic ḥayyīn (life)"],
        semantic_shift=(
            "Pan-Semitic 'to live'; Hebrew uses plural form ḥayyim for 'life' "
            "(life as inherently abundant)"
        ),
    ),
    EtymologyEntry(
        language="he", lemma="בן",
        origin_summary=(
            "From a Proto-Semitic root for 'son.' Ben is son — appears in "
            "countless Hebrew personal names (Ben-Gurion = son of the lion- "
            "cub) and the Bar/Ben mitzvah ceremonies. Cognate with Arabic "
            "ibn, Aramaic bar (the Aramaic form survives in 'Bar Mitzvah'). "
            "The patronymic structure of ancient Semitic names ('X son of Y') "
            "is foundational."
        ),
        roots=["Proto-Semitic *bin- (son)"],
        cognates=["Arabic ابن (ibn, son)", "Aramaic bar (son)"],
        semantic_shift=(
            "Pan-Semitic 'son'; foundational in patronymics and naming "
            "conventions"
        ),
    ),
    EtymologyEntry(
        language="he", lemma="אב",
        origin_summary=(
            "From a Proto-Semitic root for 'father.' Av is father — also the "
            "name of the fifth Hebrew month (the month of mourning, including "
            "Tisha b'Av). Cognate with Arabic ab/abu, Aramaic abba. The "
            "Aramaic abba (papa, daddy) entered the Greek New Testament via "
            "Jesus' Aramaic prayer, then Latin and English Christian liturgy. "
            "Avraham (Abraham) is etymologically 'father of many.'"
        ),
        roots=["Proto-Semitic *'ab- (father)"],
        cognates=[
            "Arabic أب (ab, father)",
            "Aramaic abba (father, papa)",
            "English 'abbot' (via Latin abbas, from Aramaic abba)",
        ],
        semantic_shift=(
            "Pan-Semitic 'father'; preserved across millennia in personal "
            "names"
        ),
    ),
    EtymologyEntry(
        language="he", lemma="אם",
        origin_summary=(
            "From a Proto-Semitic root for 'mother.' Em is mother — and "
            "metaphorically 'origin/source' (em ha-derekh = 'mother of the "
            "road' = crossroads). Cognate with Arabic umm, Aramaic emma. Pan- "
            "Semitic 'mother' words tend toward universal /m/ sounds (cf. "
            "English mom, Russian mama)."
        ),
        roots=["Proto-Semitic *'imm- (mother)"],
        cognates=[
            "Arabic أم (umm, mother — and umma = community/nation, see entry)",
            "Aramaic emma (mother)",
        ],
        semantic_shift="Pan-Semitic 'mother'; metaphorical 'source/origin' in idioms",
    ),
    EtymologyEntry(
        language="he", lemma="מלאך",
        origin_summary=(
            "From root ל-א-כ (l-'-k) meaning 'to send.' Mal'akh is "
            "angel/messenger — etymologically 'one sent.' The Greek angelos "
            "(Septuagint translation) preserves the same metaphor: angel = "
            "messenger. Same root gives mela'khah (work — what one is sent to "
            "do; the Sabbath prohibits mela'khah). Cognate with Arabic malak "
            "(angel) and the same etymology."
        ),
        roots=["Proto-Semitic *l-'-k (to send)"],
        cognates=[
            "Arabic ملك (malak, angel)",
            "Greek 'angelos' (messenger → angel — same semantic logic)",
        ],
        semantic_shift=(
            "'to send' → messenger → angel; also: work (what one is sent to "
            "do)"
        ),
    ),
    EtymologyEntry(
        language="he", lemma="תפילין",
        origin_summary=(
            "From root פ-ל-ל (p-l-l), same root as tefillah (prayer). "
            "Tefillin is phylacteries — small leather boxes containing "
            "scriptural verses, worn during weekday morning prayers. The "
            "Greek 'phylactery' (φυλακτήριον = guardrail/amulet) was applied "
            "by the Septuagint; English follows. Modern Hebrew preserves the "
            "original Hebrew name. Worn daily by religious Jewish men."
        ),
        roots=["Proto-Semitic *p-l-l (to plead, judge — see tefillah)"],
        cognates=["Greek φυλακτήριον (phylactery — Septuagint translation)"],
        semantic_shift=(
            "Hebrew name for the daily-prayer leather boxes; Greek phylactery "
            "is a translation, not a cognate"
        ),
    ),
    EtymologyEntry(
        language="he", lemma="מקום",
        origin_summary=(
            "From root ק-ו-מ (q-w-m) meaning 'to stand up, to arise.' Maqom "
            "is place — etymologically 'standing-place.' In Rabbinic "
            "theology, ha-Maqom (the Place) is one of the names of God: 'God "
            "is the place of the world, but the world is not God's place.' "
            "The semantic move from 'place' to a divine title reflects the "
            "depth of biblical/Rabbinic spatial theology."
        ),
        roots=["Proto-Semitic *q-w-m (to stand up)"],
        cognates=[
            "Arabic مكان (makān, place)",
            "Aramaic atrā (place — different root)",
        ],
        semantic_shift=(
            "'standing-place' → place; in Rabbinic theology: a divine name "
            "(ha-Maqom)"
        ),
    ),
    EtymologyEntry(
        language="he", lemma="לחם",
        origin_summary=(
            "From a Proto-Semitic root meaning 'bread, food, meat (in "
            "Arabic).' Leḥem is bread — appears in countless place names: "
            "Beit Leḥem (Bethlehem) = 'house of bread,' Beit ha-Leḥem = the "
            "bakery. Cognate with Arabic laḥm (meat) — interesting semantic "
            "divergence: same root, but Hebrew narrows to bread, Arabic to "
            "meat. Both are core foods."
        ),
        roots=["Proto-Semitic *l-ḥ-m (food, bread)"],
        cognates=["Arabic لحم (laḥm, meat)"],
        semantic_shift=(
            "Proto-Semitic 'food' → Hebrew 'bread' / Arabic 'meat' (cultural- "
            "dietary divergence)"
        ),
    ),
    EtymologyEntry(
        language="he", lemma="ים",
        origin_summary=(
            "From a Proto-Semitic root for 'sea, large body of water.' Yam is "
            "sea — but also 'west' (because the Mediterranean lies to the "
            "west of Israel: yamah = westward). Cognate with Arabic yamm. Yam "
            "was also a Canaanite sea-god; the biblical narratives subjugate "
            "the Canaanite Yam to YHWH (cf. the parting of the Red Sea, yam "
            "suf)."
        ),
        roots=["Proto-Semitic *yamm- (sea)"],
        cognates=["Arabic يم (yamm, sea — poetic)"],
        semantic_shift=(
            "Pan-Semitic 'sea'; in Hebrew geography, also 'west' (toward the "
            "sea)"
        ),
    ),
    EtymologyEntry(
        language="he", lemma="מדבר",
        origin_summary=(
            "From root ד-ב-ר (d-b-r) — same root as davar (word). Midbar is "
            "desert/wilderness — etymologically uncertain (perhaps 'driving- "
            "pasture' or 'the place of speech, where one hears'). Wilderness "
            "is theologically central: the wilderness wandering, the desert "
            "prophets, the wilderness of Sinai where the Torah was given. The "
            "number Bemidbar (Numbers) is named for it."
        ),
        roots=[
            "Proto-Semitic *d-b-r (to drive — possibly different sense)",
        ],
        semantic_shift=(
            "'driving-pasture' or 'place of speech' → wilderness/desert; "
            "theologically central"
        ),
    ),
    EtymologyEntry(
        language="he", lemma="הר",
        origin_summary=(
            "From a Proto-Semitic root for 'mountain.' Har is mountain — Har "
            "Sinai (Mount Sinai), Har Tziyon (Mount Zion), Har ha-Bayit "
            "(Temple Mount). Cognate with Aramaic ṭūr. Mountains in biblical "
            "theology are places of theophany (Sinai), sanctuary (Zion), and "
            "revelation. Modern Hebrew preserves the ancient form unchanged."
        ),
        roots=["Proto-Semitic *harr- (mountain)"],
        cognates=["Aramaic ṭūr (mountain — different word)"],
        semantic_shift=(
            "Pan-Semitic 'mountain'; theologically central (Sinai, Zion, "
            "Temple Mount)"
        ),
    ),
    EtymologyEntry(
        language="he", lemma="אדם",
        origin_summary=(
            "From root א-ד-מ ('-d-m) meaning 'red, ruddy.' Adam is human/Adam "
            "— etymologically 'the red one,' from adamah (earth, soil — also "
            "red in color). 'Adam from adamah' — humanity from humus (the "
            "same wordplay works in Latin). The word covers both the proper "
            "name (Adam) and the generic 'human.'"
        ),
        roots=["Proto-Semitic *'-d-m (red, ruddy earth)"],
        cognates=[
            "Arabic أديم (adīm, surface, soil)",
            "Akkadian admu (child)",
        ],
        semantic_shift=(
            "'red earth' → human (the earth-creature) → also: the proper name "
            "Adam"
        ),
    ),
    EtymologyEntry(
        language="he", lemma="רב",
        origin_summary=(
            "From root ר-ב-ב (r-b-b) meaning 'to be many, to be great.' Rabbi "
            "is teacher/master — etymologically 'great one' or 'my great one' "
            "(rabb-i with possessive). Originally a title of distinction; "
            "eventually the Jewish religious authority par excellence. Modern "
            "Hebrew rav (rabbi) and the formal Rabbi/Rebbe distinction. The "
            "same root gives ribbon (master, an old title)."
        ),
        roots=["Proto-Semitic *r-b-b (to be great, many)"],
        cognates=[
            "Aramaic rab (great, master)",
            "Arabic رب (rabb, lord — al-Rabb is a divine name)",
        ],
        semantic_shift=(
            "'to be great' → master, teacher → Rabbi as Jewish religious "
            "authority"
        ),
    ),
    EtymologyEntry(
        language="he", lemma="נביא",
        origin_summary=(
            "From root נ-ב-א (n-b-') meaning 'to call, to proclaim, to be "
            "called.' Navi is prophet — etymologically 'one called/calling' "
            "(the etymology debates which active/passive sense came first). "
            "The prophets of the Hebrew Bible (Yeshayahu, Yirmiyahu, "
            "Yeḥezkel) speak the davar of God. Cognate with Arabic nabī "
            "(prophet — the Quranic title for messenger-figures)."
        ),
        roots=["Proto-Semitic *n-b-' (to call, prophesy)"],
        cognates=["Arabic نبي (nabī, prophet)", "Aramaic nəbiyā (prophet)"],
        semantic_shift="'to call/be called' → prophet as one who speaks the divine word",
    ),
    EtymologyEntry(
        language="he", lemma="עבד",
        origin_summary=(
            "From root ע-ב-ד ('-b-d) meaning 'to work, to serve.' Eved is "
            "servant/slave — same word covers both, with context determining. "
            "The same root gives avodah (work, but also worship — service of "
            "God), the labor of the Sabbath prohibition, and the Avoda "
            "service of Yom Kippur. Cognate with Arabic 'abd (servant of...; "
            "common in names like Abdullah = 'abd Allāh)."
        ),
        roots=["Proto-Semitic *'-b-d (to work, serve)"],
        cognates=[
            "Arabic عبد ('abd, servant — as in Abdullah)",
            "Aramaic 'abdā (servant)",
        ],
        semantic_shift=(
            "'to work, serve' → servant/slave → also: worship as service of "
            "God; Sabbath labor"
        ),
    ),

    # ── JA additions (generated by gen_etymology.py) ──
    EtymologyEntry(
        language="ja", lemma="侘寂",
        origin_summary=(
            "From 侘 (wabi, originally 'misery, loneliness') and 寂 (sabi, "
            "'patina, the bloom of age'). Wabi-sabi is the Japanese aesthetic "
            "of beauty in imperfection, impermanence, and incompleteness. "
            "Originally separate concepts (16th-c. tea ceremony developed "
            "wabi; classical poetry developed sabi); fused into a unified "
            "aesthetic principle in modern usage. Reflects the Mahayana "
            "Buddhist three marks: impermanence (mujō), suffering (ku), no- "
            "self (muga)."
        ),
        roots=[
            "Japanese 侘 (wabi, misery → refined simplicity)",
            "Japanese 寂 (sabi, patina, the beauty of age)",
        ],
        cognates=["English 'wabi-sabi' (loanword, often misunderstood)"],
        semantic_shift=(
            "'misery + age-patina' → aesthetic of imperfection and "
            "impermanence"
        ),
    ),
    EtymologyEntry(
        language="ja", lemma="生き甲斐",
        origin_summary=(
            "From 生き (iki, 'life, living') and 甲斐 (kai, 'worth, effect, "
            "result'). Ikigai is 'reason for being / what makes life worth "
            "living.' Particularly associated with Okinawan longevity "
            "research (where many Okinawans cite ikigai as a longevity "
            "factor). Western popularization has somewhat distorted the "
            "original sense, but the Japanese concept centers on quotidian "
            "reasons for getting up in the morning rather than grand purpose."
        ),
        roots=[
            "Japanese 生き (iki, life)",
            "Japanese 甲斐 (kai, worth, effect)",
        ],
        cognates=["English 'ikigai' (loanword, popularized 2010s)"],
        semantic_shift="'life-worth' → reason for living; quotidian sense of purpose",
    ),
    EtymologyEntry(
        language="ja", lemma="勿体無い",
        origin_summary=(
            "From 勿体 (mottai, 'substance, importance, dignity') + 無い (nai, "
            "'none'). Mottainai expresses regret over waste — wasting "
            "something violates its essential dignity. Originally a Buddhist "
            "concept (all things have intrinsic worth/buddha-nature). Used in "
            "everyday Japanese to express anything from 'don't waste food' to "
            "deeper aesthetic-ethical regret over waste of resources, "
            "opportunities, or beauty."
        ),
        roots=[
            "Japanese 勿体 (mottai, substance, dignity)",
            "Japanese 無い (nai, none)",
        ],
        cognates=[
            "English 'mottainai' (used as ecological slogan, popularized by Wangari Maathai)",
        ],
        semantic_shift=(
            "'lacking substance/dignity' → regret over waste; eco- "
            "philosophical concept"
        ),
    ),
    EtymologyEntry(
        language="ja", lemma="おもてなし",
        origin_summary=(
            "From 表 (omote, 'front, surface') + 為し (nashi, 'doing'), or "
            "alternatively 'with no front (omote-nashi = without ulterior "
            "motive).' Omotenashi is Japanese hospitality — wholehearted, "
            "sincere, anticipatory hospitality without expectation of return. "
            "Distinguished from Western 'service' (which assumes a "
            "transaction). Central to ryokan culture, tea ceremony, and "
            "Japanese guest-host relations."
        ),
        roots=[
            "Japanese 表 (omote, surface, front)",
            "Japanese 為す (nasu, to do)",
        ],
        cognates=[
            "English 'omotenashi' (sometimes used in tourism marketing)",
        ],
        semantic_shift="'doing without ulterior motive' → wholehearted hospitality",
    ),
    EtymologyEntry(
        language="ja", lemma="甘え",
        origin_summary=(
            "From 甘い (amai, 'sweet, indulgent'). Amae is the desire to be "
            "passively loved/indulged — a complex emotion analyzed by "
            "psychiatrist Doi Takeo (The Anatomy of Dependence, 1971) as a "
            "defining Japanese psychological concept. Adults express amae "
            "toward parents, lovers, and superiors; the relationship is one "
            "of indulgent dependence. Doi argued Japanese culture preserves a "
            "recognized space for this dependence that Western culture "
            "suppresses."
        ),
        roots=["Japanese 甘い (amai, sweet)"],
        semantic_shift=(
            "'sweetness' → desire for sweet/indulgent attention → indulgent "
            "dependence (psychoanalytic concept)"
        ),
    ),
    EtymologyEntry(
        language="ja", lemma="建前",
        origin_summary=(
            "From 建 (tate, 'erecting') + 前 (mae, 'front'). Tatemae is the "
            "public/official position one presents — opposed to honne (本音, "
            "the true feelings). The tatemae/honne distinction is "
            "foundational in Japanese social interaction: maintaining harmony "
            "requires presenting tatemae, while honne is shared only in "
            "trusted contexts. Often misunderstood as 'lying' by Westerners — "
            "but it is a structured ethical framework, not deception."
        ),
        roots=[
            "Japanese 建てる (tateru, to erect, construct)",
            "Japanese 前 (mae, front)",
        ],
        semantic_shift="'constructed front' → official/public position; opposed to honne",
    ),
    EtymologyEntry(
        language="ja", lemma="本音",
        origin_summary=(
            "From 本 (hon, 'origin, true') + 音 (ne, 'sound, voice'). Honne is "
            "one's true voice/feelings — what one actually thinks, opposed to "
            "tatemae (built-up front). Sharing honne requires intimacy; among "
            "colleagues, honne might emerge only after work, often "
            "facilitated by drinking (nominication = drinking + "
            "communication)."
        ),
        roots=[
            "Japanese 本 (hon, true, origin)",
            "Japanese 音 (ne, sound, voice)",
        ],
        semantic_shift="'true voice' → true feelings; opposed to tatemae",
    ),
    EtymologyEntry(
        language="ja", lemma="和",
        origin_summary=(
            "Wa means harmony, peace, Japan itself (the older self-name of "
            "Japan). The character was used by ancient Chinese to refer to "
            "the Japanese — possibly with derogatory implications (the older "
            "倭 was replaced by the homophone 和 'harmony' as a more dignified "
            "self-designation). Wa as a cultural value (group harmony) "
            "underlies Japanese decision-making style and conflict-avoidance."
        ),
        roots=["Chinese 和 (hé, harmony — borrowed into Japanese)"],
        cognates=["Chinese 和 (hé, harmony)", "Korean 화 (hwa, harmony)"],
        semantic_shift=(
            "Chinese 'harmony' → Japanese self-designation + cardinal "
            "cultural value"
        ),
    ),
    EtymologyEntry(
        language="ja", lemma="禅",
        origin_summary=(
            "From Sanskrit dhyāna (meditation) → Chinese 禪 (chán, Chan "
            "Buddhism) → Japanese 禅 (zen). Zen is the meditative school of "
            "Buddhism that came to Japan in the 12th-13th centuries (Eisai's "
            "Rinzai, Dōgen's Sōtō). The same Sanskrit root gives Korean Seon "
            "and Vietnamese Thiền. The English 'Zen' has now entered global "
            "vocabulary as shorthand for meditative simplicity."
        ),
        roots=["Sanskrit dhyāna (meditation)", "Chinese 禪 (chán)"],
        cognates=[
            "Sanskrit 'dhyāna'",
            "Chinese 'chán'",
            "Korean 'Seon'",
            "Vietnamese 'Thiền'",
            "English 'Zen' (loanword)",
        ],
        semantic_shift=(
            "Sanskrit 'meditation' → Chinese Chan Buddhism → Japanese Zen → "
            "global cultural shorthand"
        ),
    ),
    EtymologyEntry(
        language="ja", lemma="禅問答",
        origin_summary=(
            "From 禅 (zen) + 問答 (mondō, 'question-answer dialogue'). Zen mondō "
            "is the Zen master-disciple dialogue, often featuring kōans "
            "(paradoxical riddles meant to break logical mind). Famous "
            "example: 'What is the sound of one hand clapping?' Modern "
            "Japanese uses 禅問答 idiomatically for any cryptic exchange that "
            "doesn't yield a normal answer."
        ),
        roots=["Japanese 禅 (zen)", "Japanese 問答 (mondō, dialogue)"],
        semantic_shift=(
            "'Zen dialogue' → kōan-style exchange → idiomatically: any "
            "cryptic exchange"
        ),
    ),
    EtymologyEntry(
        language="ja", lemma="義理",
        origin_summary=(
            "From Chinese 義 (yi, 'righteousness') + 理 (lǐ, 'principle'). Giri "
            "is duty/obligation — the social-ethical obligations one has to "
            "family, employer, friends. Distinguished from ninjō (人情, human "
            "feeling): the central tension in Japanese drama is giri vs. "
            "ninjō, duty vs. heart. Tokugawa-era kabuki and bunraku theatre "
            "repeatedly stages this conflict."
        ),
        roots=[
            "Chinese 義 (yi, righteousness)",
            "Chinese 理 (lǐ, principle)",
        ],
        cognates=["Korean 의리 (uiri, loyalty/duty — same Sino-Korean reading)"],
        semantic_shift=(
            "'righteous principle' → social obligation → giri/ninjō "
            "opposition in Japanese ethics"
        ),
    ),
    EtymologyEntry(
        language="ja", lemma="人情",
        origin_summary=(
            "From 人 (jin/hito, 'person') + 情 (jō, 'feeling'). Ninjō is human "
            "feeling/compassion — the warmth of human heart that may pull "
            "against giri (duty). Edo-period social philosophy and theatre "
            "treat the giri/ninjō tension as the central human dilemma. "
            "Modern Japanese uses ninjō for 'kindness, sympathy, what makes "
            "us human.'"
        ),
        roots=["Chinese 人 (rén, person)", "Chinese 情 (qíng, feeling)"],
        cognates=["Chinese 人情 (rénqíng, human feeling/sentiment)"],
        semantic_shift=(
            "'human feeling' → compassion/heart → opposed to giri (duty) in "
            "Japanese ethical drama"
        ),
    ),
    EtymologyEntry(
        language="ja", lemma="もののあわれ",
        origin_summary=(
            "From 物 (mono, 'thing') + の (no, possessive) + あわれ (aware, 'pity, "
            "melancholy, deep feeling'). Mono no aware is 'the pathos of "
            "things' — the awareness of impermanence that gives objects their "
            "poignancy. Articulated by 18th-c. literary critic Motoori "
            "Norinaga as the central aesthetic of Genji Monogatari. Already "
            "in store; included for context. Cherry blossom viewing (hanami) "
            "is a classic mono no aware practice."
        ),
        roots=["Japanese 物 (mono, thing)", "Japanese 哀れ (aware, pathos)"],
        semantic_shift=(
            "'pathos of things' → awareness of impermanence → cherry-blossom "
            "melancholy aesthetic"
        ),
    ),
    EtymologyEntry(
        language="ja", lemma="幽玄",
        origin_summary=(
            "From Chinese 幽 (yōu, 'dim, hidden, profound') + 玄 (xuán, "
            "'mystery, dark'). Yūgen is mysterious profundity — the aesthetic "
            "of suggested, hidden depth, especially in Nō theatre. "
            "Articulated by Zeami (14th-c. Nō playwright). Often translated "
            "'mysterious depth' or 'profound mystery.' Captures the value of "
            "what is suggested rather than stated, hidden rather than "
            "revealed."
        ),
        roots=["Chinese 幽 (yōu, dim)", "Chinese 玄 (xuán, mystery)"],
        cognates=["Chinese 幽玄 (yōuxuán)"],
        semantic_shift=(
            "'dim mystery' → aesthetic of profound suggestion in Nō and other "
            "traditional arts"
        ),
    ),
    EtymologyEntry(
        language="ja", lemma="鳥居",
        origin_summary=(
            "From 鳥 (tori, 'bird') + 居 (i, 'to be, dwelling'). Torii is the "
            "iconic gate at Shinto shrines — etymologically 'bird-perch.' "
            "Multiple etymologies have been proposed; the bird connection may "
            "relate to ancient bird-spirit shrine traditions. The torii marks "
            "the threshold between profane and sacred space at every Shinto "
            "shrine."
        ),
        roots=["Japanese 鳥 (tori, bird)", "Japanese 居 (i, to be, sit)"],
        semantic_shift=(
            "'bird-perch' → Shinto shrine gate; the visual icon of Shinto "
            "worldwide"
        ),
    ),
    EtymologyEntry(
        language="ja", lemma="神道",
        origin_summary=(
            "From 神 (shin/kami, 'divine, kami spirit') + 道 (dō, 'way, path'). "
            "Shintō is 'the way of the kami' — Japan's indigenous "
            "polytheistic tradition. The term shintō was coined to "
            "distinguish the indigenous tradition from Buddhism (butsudō) "
            "when Buddhism arrived in the 6th century. Kami denotes spirits "
            "in nature, ancestors, and culture-heroes — not 'gods' in the "
            "monotheistic sense."
        ),
        roots=["Chinese 神 (shén, divine)", "Chinese 道 (dào, way)"],
        cognates=["Chinese 神道 (shéndào, divine way)"],
        semantic_shift="'divine way' → Japan's indigenous religion of kami-spirits",
    ),
    EtymologyEntry(
        language="ja", lemma="侍",
        origin_summary=(
            "From the verb 侍う (saburau, 'to serve, to attend'). Samurai means "
            "'one who serves' — historically the warrior class who served the "
            "daimyo. The samurai class was abolished in the 1870s during the "
            "Meiji Restoration; the cultural ideal continues to shape "
            "Japanese self-conception (bushido). The word entered global "
            "vocabulary; English 'samurai' is among the most widely "
            "recognized Japanese loanwords."
        ),
        roots=["Japanese 侍う (saburau, to serve, attend)"],
        cognates=["English 'samurai' (loanword)"],
        semantic_shift=(
            "'one who serves' → the warrior-retainer class → cultural- "
            "historical ideal"
        ),
    ),
    EtymologyEntry(
        language="ja", lemma="武士道",
        origin_summary=(
            "From 武士 (bushi, 'warrior') + 道 (dō, 'way'). Bushidō is 'the way "
            "of the warrior' — the ethical code of the samurai. Codified in "
            "the Edo period (Yamamoto Tsunetomo's Hagakure, 18th c.) and "
            "globalized by Nitobe Inazō's English book Bushido: The Soul of "
            "Japan (1900). The seven virtues: gi (justice), yū (courage), jin "
            "(benevolence), rei (respect), makoto (sincerity), meiyo (honor), "
            "chūgi (loyalty)."
        ),
        roots=[
            "Chinese 武 (wǔ, military)",
            "Chinese 士 (shì, scholar/gentleman)",
            "Chinese 道 (dào, way)",
        ],
        cognates=["English 'bushido' (loanword via Nitobe's 1900 book)"],
        semantic_shift=(
            "'way of the warrior' → samurai ethical code → globally "
            "recognized cultural ideal"
        ),
    ),
    EtymologyEntry(
        language="ja", lemma="切腹",
        origin_summary=(
            "From 切る (kiru, 'to cut') + 腹 (hara, 'belly'). Seppuku is ritual "
            "self-disembowelment — a samurai practice for honorable suicide, "
            "also called by the more colloquial harakiri (腹切り — same "
            "characters, different reading order). Seppuku is the Sino- "
            "Japanese reading; harakiri is the kun'yomi. Banned in 1873 but "
            "persisted as ideal honor-restoration; Mishima Yukio's 1970 "
            "seppuku was the most famous late instance."
        ),
        roots=["Japanese 切る (kiru, to cut)", "Japanese 腹 (hara, belly)"],
        cognates=["English 'hara-kiri' (loanword from Japanese harakiri)"],
        semantic_shift=(
            "'belly-cutting' → ritual samurai suicide; entered global "
            "vocabulary"
        ),
    ),
    EtymologyEntry(
        language="ja", lemma="歌舞伎",
        origin_summary=(
            "From 歌 (ka, 'song') + 舞 (bu, 'dance') + 伎 (ki, 'skill'). Kabuki "
            "is the highly stylized classical theatre — etymologically 'song- "
            "dance-skill.' Originally an unconventional/'kabuku' (傾く, to "
            "lean/be eccentric) entertainment form started by Izumo no Okuni "
            "in 1603. The character writing (歌舞伎) postdates the etymology — "
            "the original meaning was 'eccentric/unconventional' (kabuku), "
            "with the auspicious characters added later."
        ),
        roots=[
            "Japanese 傾く (kabuku, to lean, be eccentric)",
            "Reanalyzed as 歌舞伎 (song-dance-skill)",
        ],
        cognates=["English 'kabuki' (loanword)"],
        semantic_shift=(
            "'eccentric performance' → song-dance-skill (folk-etymology) → "
            "classical Japanese theatre"
        ),
    ),
    EtymologyEntry(
        language="ja", lemma="俳句",
        origin_summary=(
            "From 俳 (hai, 'unconventional, comic') + 句 (ku, 'verse'). Haiku "
            "is the 5-7-5 syllable poem — etymologically 'comic verse,' from "
            "its origins as the playful opening verse (hokku) of linked- "
            "poetry (renga). Codified as independent form by Masaoka Shiki in "
            "the late 19th century. Bashō (17th c.), Buson, Issa, and Shiki "
            "are the four canonical masters."
        ),
        roots=[
            "Japanese 俳 (hai, unconventional)",
            "Japanese 句 (ku, verse)",
        ],
        cognates=["English 'haiku' (loanword)"],
        semantic_shift="'unconventional verse' → 5-7-5 form → globalized poetic genre",
    ),
    EtymologyEntry(
        language="ja", lemma="寿司",
        origin_summary=(
            "Originally from a 4th-c. Chinese-style fermented-fish-and-rice "
            "preservation method (narezushi). The character writing 寿司 "
            "('longevity-administer') is a phonetic reanalysis from the older "
            "鮨 (sushi, 'salted fish'). Modern Edomae sushi (the form "
            "globalized) was developed in early 19th-c. Edo by Hanaya Yohei. "
            "The word and food are now globally distributed; sushi is among "
            "the most recognized Japanese cultural exports."
        ),
        roots=[
            "Japanese 鮨 (sushi, salted fish — original)",
            "Reanalyzed as 寿司 (longevity-administer)",
        ],
        cognates=["English 'sushi' (loanword)"],
        semantic_shift=(
            "'salted fish' → fermented preservation → Edo-era nigiri sushi → "
            "global cuisine"
        ),
    ),
    EtymologyEntry(
        language="ja", lemma="畳",
        origin_summary=(
            "From 畳む (tatamu, 'to fold, to stack'). Tatami originally meant "
            "'something folded/piled' — the woven mats are stacked when not "
            "in use. The standardized tatami (Edo period) became the unit of "
            "room measurement (one tatami ≈ 90 × 180 cm). Room sizes are "
            "still given in tatami count: an 8-tatami room. Tatami-rooms "
            "(washitsu) embody traditional Japanese spatial sensibility."
        ),
        roots=["Japanese 畳む (tatamu, to fold)"],
        cognates=["English 'tatami' (loanword)"],
        semantic_shift=(
            "'folded thing' → woven mat → standard unit of Japanese room "
            "measurement"
        ),
    ),
    EtymologyEntry(
        language="ja", lemma="畳語",
        origin_summary=(
            "From 畳 (jō, repetition) + 語 (go, word). Jōgo is reduplication — "
            "a major morphological feature of Japanese: 人々 (hitobito, "
            "people), 山々 (yamayama, mountains), キラキラ (kirakira, sparkling), "
            "ドキドキ (dokidoki, heart-pounding). The reduplicative onomatopoeia "
            "(gitaigo, mimetic words) is one of Japanese's most distinctive "
            "features."
        ),
        roots=[
            "Japanese 畳 (jō, repetition, fold)",
            "Japanese 語 (go, word)",
        ],
        semantic_shift=(
            "'folded word' → reduplication; characteristic morphological "
            "feature of Japanese"
        ),
    ),
    EtymologyEntry(
        language="ja", lemma="桜",
        origin_summary=(
            "Sakura, the cherry blossom — possibly from saku (咲く, 'to bloom') "
            "+ ra (suffix). The flower is Japan's de facto national symbol, "
            "central to spring festivals (hanami) and military symbolism "
            "(cherry blossoms fall at their peak — like young soldiers). The "
            "cherry blossom encapsulates mono no aware: beauty is most "
            "poignant in its brevity."
        ),
        roots=["Japanese 咲く (saku, to bloom)"],
        semantic_shift=(
            "'blooming-thing' → cherry blossom → cultural/national symbol of "
            "impermanent beauty"
        ),
    ),
    EtymologyEntry(
        language="ja", lemma="富士",
        origin_summary=(
            "Fuji — the name of the iconic mountain. Etymology disputed: "
            "possibly from Ainu 'huci' (fire/grandmother goddess), or from "
            "older Japanese 'fuji' (immortal). The Buddhist character 不死 "
            "(fushi, 'not-dying/immortal') was used in some texts. Fuji-san "
            "(Mount Fuji) is the most photographed mountain in the world; "
            "Hokusai's 36 Views of Mount Fuji (1830s) made it global "
            "iconography."
        ),
        roots=[
            "Possibly Ainu huci (fire goddess) or Japanese 不死 (fushi, immortal)",
        ],
        semantic_shift=(
            "Mountain-name with multiple etymological theories; central to "
            "Japanese landscape and art"
        ),
    ),
    EtymologyEntry(
        language="ja", lemma="津波",
        origin_summary=(
            "From 津 (tsu, 'harbor') + 波 (nami, 'wave'). Tsunami is 'harbor "
            "wave' — the wave that strikes harbors with disproportionate "
            "force (open ocean ships barely notice the wave passing under "
            "them, but harbors funnel and amplify it). The 2004 Indian Ocean "
            "and 2011 Tōhoku tsunamis caused the Japanese word to displace "
            "'tidal wave' as the standard scientific and global term."
        ),
        roots=["Japanese 津 (tsu, harbor)", "Japanese 波 (nami, wave)"],
        cognates=[
            "English 'tsunami' (loanword, displaced 'tidal wave' globally)",
        ],
        semantic_shift="'harbor wave' → seismic sea wave → global scientific term",
    ),
    EtymologyEntry(
        language="ja", lemma="台風",
        origin_summary=(
            "From Chinese 颱風 (táifēng) — possibly from Cantonese tai-fung "
            "('great wind'). Taifū is typhoon. The English 'typhoon' has "
            "multiple etymological inputs: Greek typhōn (whirlwind), Arabic "
            "ṭūfān (storm), Chinese táifēng. Cross-pollinated etymology rare "
            "in single words. The Chinese borrowing into Japanese coincided "
            "with the Japanese term entering English."
        ),
        roots=["Chinese 颱風 (táifēng, great wind)"],
        cognates=[
            "English 'typhoon' (combined etymology: Chinese taifēng + Greek typhōn + Arabic ṭūfān)",
            "Greek 'typhōn' (whirlwind)",
            "Arabic طوفان (ṭūfān, storm/flood)",
        ],
        semantic_shift=(
            "'great wind' → Pacific tropical cyclone; rare convergent "
            "etymology in English"
        ),
    ),
    EtymologyEntry(
        language="ja", lemma="盆栽",
        origin_summary=(
            "From 盆 (bon, 'tray, pot') + 栽 (sai, 'cultivation, plant'). "
            "Bonsai is 'tray-planted miniature tree' — the art of cultivating "
            "dwarfed trees in shallow containers. Originated in China "
            "(penjing) ~1000 years ago; refined in Japan in the Kamakura "
            "period. Modern bonsai entered Western awareness in the late 19th "
            "century. Reflects Buddhist aesthetic of small-as-cosmos."
        ),
        roots=["Chinese 盆 (pén, tray)", "Chinese 栽 (zāi, cultivation)"],
        cognates=[
            "Chinese 盆景 (pénjǐng, ancestor of bonsai)",
            "English 'bonsai' (loanword)",
        ],
        semantic_shift="'tray-planted' → miniature potted tree art form",
    ),
    EtymologyEntry(
        language="ja", lemma="風水",
        origin_summary=(
            "From 風 (fū, 'wind') + 水 (sui, 'water'). Fūsui is the Japanese "
            "reading of Chinese 風水 (fēngshuǐ) — the geomantic art of "
            "arranging spaces in harmony with cosmic flows. Adopted from "
            "China; applied in Japanese architectural placement, gardens, and "
            "city planning (Heian-kyō was laid out with attention to fūsui). "
            "English 'feng shui' has globalized the Mandarin reading."
        ),
        roots=["Chinese 風 (fēng, wind)", "Chinese 水 (shuǐ, water)"],
        cognates=[
            "Chinese 風水 (fēngshuǐ)",
            "Korean 풍수 (pungsu)",
            "English 'feng shui' (Mandarin loanword)",
        ],
        semantic_shift="'wind and water' → cosmological geomantic art",
    ),
    EtymologyEntry(
        language="ja", lemma="禅僧",
        origin_summary=(
            "From 禅 (zen) + 僧 (sō, 'monk'). Zensō is a Zen monk. The Zen "
            "monasteries of Kamakura and Kyoto (Engaku-ji, Daitoku-ji, "
            "Myōshin-ji) shaped much of Japanese aesthetic culture: tea "
            "ceremony, ink painting, dry gardens, calligraphy all developed "
            "in Zen monastic milieus. The 'Zen monk poet' (zensō) is a "
            "recognized cultural type (Ryōkan, Ikkyū, Bashō)."
        ),
        roots=[
            "Sanskrit dhyāna → Chinese chán → Japanese zen",
            "Sanskrit saṃgha → Chinese sēng → Japanese sō (monk)",
        ],
        semantic_shift=(
            "'Zen monk' → cultural type associated with art, poetry, and "
            "aesthetic refinement"
        ),
    ),
    EtymologyEntry(
        language="ja", lemma="茶道",
        origin_summary=(
            "From 茶 (cha, 'tea') + 道 (dō, 'way'). Sadō (or chadō) is 'the way "
            "of tea' — the Japanese tea ceremony. Codified by Sen no Rikyū "
            "(1522-1591), who systematized the wabi-style tea aesthetic "
            "emphasizing rusticity, mindfulness, and ichi-go ichi-e (one "
            "moment, one meeting — each tea gathering is unrepeatable). One "
            "of the most refined ritualized aesthetic practices in world "
            "culture."
        ),
        roots=["Chinese 茶 (chá, tea)", "Chinese 道 (dào, way)"],
        cognates=["English 'sadō'/'chadō' (specialist usage)"],
        semantic_shift=(
            "'way of tea' → Japanese tea ceremony as aesthetic-spiritual "
            "discipline"
        ),
    ),
    EtymologyEntry(
        language="ja", lemma="華道",
        origin_summary=(
            "From 華 (ka, 'flower') + 道 (dō, 'way'). Kadō is 'the way of "
            "flowers' — Japanese flower arrangement, more commonly called "
            "ikebana (生け花, 'living flowers'). Originated in Buddhist temple "
            "offerings; evolved into refined art form with multiple schools "
            "(Ikenobō is the oldest, ~600 years). The aesthetic emphasizes "
            "asymmetry, line, and negative space — distinct from Western "
            "full-bouquet style."
        ),
        roots=["Chinese 華 (huá, flower, splendor)", "Chinese 道 (dào, way)"],
        cognates=["English 'ikebana' (related term, more common)"],
        semantic_shift="'way of flowers' → Japanese flower-arrangement art",
    ),
    EtymologyEntry(
        language="ja", lemma="書道",
        origin_summary=(
            "From 書 (sho, 'writing') + 道 (dō, 'way'). Shodō is 'the way of "
            "writing' — Japanese calligraphy, an art form treated with the "
            "same -dō ('way') seriousness as tea ceremony or martial arts. "
            "Practiced as both artistic and meditative discipline. The brush, "
            "ink, ink-stone, and paper are 'the four treasures of the study' "
            "(bunbō shihō)."
        ),
        roots=["Chinese 書 (shū, writing)", "Chinese 道 (dào, way)"],
        cognates=["Chinese 書道 (shūdào)"],
        semantic_shift="'way of writing' → calligraphy as artistic-meditative practice",
    ),
    EtymologyEntry(
        language="ja", lemma="柔道",
        origin_summary=(
            "From 柔 (jū, 'gentle, yielding') + 道 (dō, 'way'). Jūdō is 'the "
            "gentle way' — the martial art codified by Kanō Jigorō in 1882 "
            "from older jūjutsu (柔術). Principle: yielding to overcome "
            "('seiryoku zen'yō, maximum efficiency, minimum effort'). Olympic "
            "sport since 1964. Many '-dō' martial arts use the same "
            "morphological pattern: kendō (sword), kyūdō (bow), aikidō."
        ),
        roots=["Chinese 柔 (róu, gentle)", "Chinese 道 (dào, way)"],
        cognates=["English 'judo' (loanword)"],
        semantic_shift="'gentle way' → modern Olympic martial art codified by Kanō",
    ),
    EtymologyEntry(
        language="ja", lemma="空手",
        origin_summary=(
            "From 空 (kara, 'empty') + 手 (te, 'hand'). Karate is 'empty hand' "
            "— unarmed martial art originating in Okinawa (Ryūkyū Kingdom), "
            "influenced by Chinese martial arts. The character 空 (empty) "
            "replaced an older 唐 (Tang/Chinese) — same pronunciation, "
            "different meaning — to give the art a Buddhist 'emptiness' "
            "resonance. Spread globally after WWII."
        ),
        roots=[
            "Japanese 空 (kara, empty — replaced earlier 唐 'Tang/Chinese')",
            "Japanese 手 (te, hand)",
        ],
        cognates=["English 'karate' (loanword)"],
        semantic_shift=(
            "Originally 'Chinese hand' (唐手) → reinterpreted as 'empty hand' "
            "(空手) → modern martial art"
        ),
    ),
    EtymologyEntry(
        language="ja", lemma="弁当",
        origin_summary=(
            "From either 'biàndāng' (Chinese, 'convenience') or from "
            "Portuguese 'bento' (good, well — possibly via 16th-c. Portuguese "
            "contact). Bentō is the boxed meal. The art of bentō-making "
            "(especially kyaraben — 'character bentō' featuring decorated "
            "rice/food) is a cultural practice with international following. "
            "The bentō has crossed into mainstream global food culture."
        ),
        roots=[
            "Possibly Chinese 便當 (biàndāng, convenience)",
            "Possibly Portuguese 'bento' (good)",
        ],
        cognates=["Chinese 便當 (biàndāng)", "English 'bento' (loanword)"],
        semantic_shift=(
            "Possibly 'convenient food' or Portuguese loan → boxed meal → "
            "globally recognized food category"
        ),
    ),
    EtymologyEntry(
        language="ja", lemma="醤油",
        origin_summary=(
            "From 醤 (jō, 'sauce, fermented condiment') + 油 (yu, "
            "'oil/liquid'). Shōyu is soy sauce — etymologically 'fermented- "
            "sauce liquid.' The character 醤 originally referred to any "
            "fermented condiment (gravy, paste). Brewing technique came from "
            "China; refined in Japan, particularly Kikkoman (founded 1661). "
            "'Soy' (English) derives from shōyu via Dutch trade; 'soybean' is "
            "etymologically 'shōyu-bean.'"
        ),
        roots=[
            "Chinese 醤 (jiàng, fermented paste)",
            "Japanese 油 (yu, oil/liquid)",
        ],
        cognates=[
            "English 'soy' (from Japanese shōyu via Dutch)",
            "English 'soybean'",
        ],
        semantic_shift=(
            "'fermented liquid' → soy sauce → English 'soy' name for the bean "
            "(named after the sauce)"
        ),
    ),
    EtymologyEntry(
        language="ja", lemma="津",
        origin_summary=(
            "Tsu means harbor, port, ferry-crossing. Found in many Japanese "
            "place names: Otsu, Yotsu, Kanzaki-no-Tsu. As a place-name suffix "
            "indicates a coastal harbor. Same character as in 津波 (tsunami, "
            "harbor-wave). In modern Japanese the standalone use is largely "
            "confined to place names; the meaning persists in compounds."
        ),
        roots=["Old Japanese tsu (harbor)"],
        semantic_shift="'harbor, port' → element in coastal place names",
    ),
    EtymologyEntry(
        language="ja", lemma="山",
        origin_summary=(
            "Yama — mountain. One of the most basic Japanese words. Mountain- "
            "Shinto (the worship of mountain kami) is foundational; many "
            "mountains are themselves kami (Mt. Fuji, Mt. Mitake, Mt. Hiei). "
            "The character 山 is a pictogram of three peaks; pronounced yama "
            "(kun'yomi, native) or san/zan (on'yomi, Sino-Japanese). 'San' "
            "suffix in temple-mountain names: Hiei-zan, Kōya-san."
        ),
        roots=[
            "Old Japanese yama (mountain)",
            "Chinese 山 (shān, mountain)",
        ],
        semantic_shift="Pan-Japanese 'mountain'; central to Shinto religious geography",
    ),
    EtymologyEntry(
        language="ja", lemma="海",
        origin_summary=(
            "Umi — sea. Pictogram-derived character (originally water + "
            "mother). Japan's island geography makes umi central to identity; "
            "the four-directional sea (shihō no umi) borders Japan. In "
            "Shinto, the sea-kami (Watatsumi, Ryūjin) figure prominently. The "
            "compound 海老 (ebi, shrimp) is the sea + old (because shrimp "
            "resembles a hunched old man)."
        ),
        roots=["Old Japanese umi (sea)", "Chinese 海 (hǎi, sea)"],
        semantic_shift="Pan-Japanese 'sea'; geographically and religiously central",
    ),
    EtymologyEntry(
        language="ja", lemma="川",
        origin_summary=(
            "Kawa — river. Pictogram of three flowing lines representing a "
            "river. Found ubiquitously in Japanese place names and surnames "
            "(Tokugawa, Kawasaki, Edogawa). The 'kawa-na/-gawa' compound "
            "suffix is one of the most productive in Japanese geography. "
            "Cognate with Korean 가람 (garam) is debated; the character is "
            "shared with Chinese."
        ),
        roots=["Old Japanese kawa (river)", "Chinese 川 (chuān, river)"],
        semantic_shift=(
            "'river'; pictogram-derived; productive in place names and "
            "surnames"
        ),
    ),
    EtymologyEntry(
        language="ja", lemma="心",
        origin_summary=(
            "Kokoro — heart, mind, spirit. The character 心 is a pictogram of "
            "the human heart. Kokoro covers what English splits into 'heart' "
            "(emotion) and 'mind' (thought) and 'spirit' (will) — all unified "
            "in one Japanese word. Natsume Sōseki's novel Kokoro (1914) plays "
            "on the multivalent meaning. The compound 安心 (anshin, peace-of- "
            "heart = security) is high-frequency."
        ),
        roots=[
            "Old Japanese kokoro (heart/mind)",
            "Chinese 心 (xīn, heart)",
        ],
        cognates=["Chinese 心 (xīn)"],
        semantic_shift=(
            "Single word covering heart/mind/spirit; central in Japanese "
            "psychological vocabulary"
        ),
    ),
    EtymologyEntry(
        language="ja", lemma="気",
        origin_summary=(
            "Ki — energy/spirit/atmosphere. Borrowed from Chinese 氣 (qì) — "
            "the foundational concept of East Asian medicine and martial "
            "arts. Compound-rich: 元気 (genki, vigor/health), 病気 (byōki, "
            "illness), 空気 (kūki, air/atmosphere), 天気 (tenki, weather), 気持ち "
            "(kimochi, feeling). One of the most productive morphemes in "
            "Japanese vocabulary."
        ),
        roots=["Chinese 氣 (qì, vital energy)"],
        cognates=[
            "Chinese 氣 (qì)",
            "Korean 기 (gi)",
            "English 'qi'/'chi' (loanwords)",
        ],
        semantic_shift=(
            "'vital energy' → atmosphere, mood, vigor; one of the most "
            "productive Japanese morphemes"
        ),
    ),
    EtymologyEntry(
        language="ja", lemma="道",
        origin_summary=(
            "Michi or dō — way, path, road. The character 道 is borrowed from "
            "Chinese (dào, the Tao). In Japanese, the dō suffix marks 'way' "
            "as discipline: jūdō, kendō, sadō, kadō, shodō, bushidō, etc. "
            "Each named '-way' is treated as serious lifelong discipline. The "
            "Tao Te Ching (老子, Rōshi) is foundational reading in Japanese "
            "philosophy."
        ),
        roots=["Chinese 道 (dào, way)"],
        cognates=[
            "Chinese 道 (dào)",
            "Korean 도 (do)",
            "English 'Tao'/'Dao' (loanword)",
        ],
        semantic_shift=(
            "'way' → both literal road and discipline-as-way; productive "
            "suffix in named arts"
        ),
    ),
    EtymologyEntry(
        language="ja", lemma="魂",
        origin_summary=(
            "Tamashii — soul. Distinct from kokoro (heart/mind): tamashii is "
            "the disembodied/persistent soul, the spirit of the dead. The "
            "compound 大和魂 (yamato-damashii, 'Yamato/Japanese spirit') was "
            "used in Meiji and wartime nationalist discourse. Modern Japanese "
            "tamashii is more general: the 'soul' of an artwork, place, or "
            "person."
        ),
        roots=["Old Japanese tama (jewel/soul)", "Chinese 魂 (hún, soul)"],
        cognates=["Chinese 魂 (hún)"],
        semantic_shift=(
            "'jewel/soul' → disembodied soul → also: spirit/essence of a "
            "thing or place"
        ),
    ),
    EtymologyEntry(
        language="ja", lemma="影",
        origin_summary=(
            "Kage — shadow. The character 影 means shadow or reflection. "
            "Kagemusha (影武者, 'shadow warrior') was a body double for a "
            "daimyō; the term Akira Kurosawa popularized through his 1980 "
            "film. The dual sense (shadow AND reflection) in a single "
            "Japanese word reflects an aesthetic fascination with doubles, "
            "copies, and the play between original and image — central in "
            "Japanese theater and visual arts."
        ),
        roots=["Old Japanese kage (shadow)", "Chinese 影 (yǐng, shadow)"],
        cognates=["Chinese 影 (yǐng)"],
        semantic_shift=(
            "'shadow/reflection' → also: a body-double; aesthetic concept of "
            "original/copy"
        ),
    ),
    EtymologyEntry(
        language="ja", lemma="色",
        origin_summary=(
            "Iro — color, but also 'sensuality, eroticism.' The compound 色気 "
            "(iroke) means sex appeal; 色彩 (shikisai) means coloration in the "
            "artistic sense. The word's dual semantic field (color + "
            "eroticism) reflects Heian-era court culture (the Tale of Genji), "
            "where iro-gonomi ('connoisseur of color/love') was the cultural "
            "ideal of refined sensibility."
        ),
        roots=["Old Japanese iro (color)", "Chinese 色 (sè, color, lust)"],
        cognates=["Chinese 色 (sè)"],
        semantic_shift=(
            "'color' → also: sensuality/eroticism (the same word covers both, "
            "reflecting Heian aesthetic)"
        ),
    ),

    # ── KO additions (generated by gen_etymology.py) ──
    EtymologyEntry(
        language="ko", lemma="한",
        origin_summary=(
            "Han is a complex Korean emotional concept — often translated "
            "'unresolved resentment, sorrow, longing, regret.' Theorized as a "
            "defining Korean emotion shaped by historical suffering "
            "(colonization, partition, war). Some scholars critique han as a "
            "colonial construction (Japanese imperial discourse projected it "
            "onto Koreans); others see it as an authentic ethnopsychological "
            "category. Hanja origin: 恨 (hen, grudge/regret)."
        ),
        roots=["Sino-Korean 恨 (han, grudge, regret)"],
        cognates=[
            "Chinese 恨 (hèn, hate, regret)",
            "Japanese 恨み (urami, grudge)",
        ],
        semantic_shift=(
            "Sino-Korean 'grudge/regret' → distinctively Korean cultural "
            "emotion of accumulated, unresolved sorrow"
        ),
    ),
    EtymologyEntry(
        language="ko", lemma="정",
        origin_summary=(
            "Jeong is the deep affective bond formed through shared "
            "experience. Distinct from love (sarang) — jeong is the slow "
            "accumulation of attachment over time, applicable to "
            "relationships, places, even objects. Sometimes paired with han: "
            "jeong is the warmth that survives han. From hanja 情 (jeong, "
            "feeling, sentiment), shared with Chinese qíng and Japanese jō. A "
            "core concept in Korean interpersonal philosophy."
        ),
        roots=["Sino-Korean 情 (jeong, feeling)"],
        cognates=[
            "Chinese 情 (qíng, feeling)",
            "Japanese 情 (jō, feeling — as in 人情 ninjō)",
        ],
        semantic_shift=(
            "Sino-Korean 'feeling' → distinctively Korean concept of deep "
            "affective bond developed through shared time"
        ),
    ),
    EtymologyEntry(
        language="ko", lemma="눈치",
        origin_summary=(
            "Nunchi literally 'eye-measure' (눈 nun = eye + 치 chi = "
            "measure/sense). The art of reading social atmosphere, picking up "
            "unspoken cues, sensing what others feel. Considered a essential "
            "Korean social skill — to lack nunchi is to be socially clumsy. "
            "Jeong, han, and nunchi together form a triad of distinctively "
            "Korean interpersonal-psychological vocabulary."
        ),
        roots=["Korean 눈 (nun, eye)", "Korean 치 (chi, measure/sense)"],
        cognates=["English 'nunchi' (loanword in cross-cultural literature)"],
        semantic_shift=(
            "'eye-measure' → ability to read social atmosphere, anticipate "
            "unspoken needs"
        ),
    ),
    EtymologyEntry(
        language="ko", lemma="한국",
        origin_summary=(
            "Hanguk = the country (kuk = 國) of Han (한). The 'Han' here refers "
            "to the ancient Korean Han tribes (Three Han: Mahan, Jinhan, "
            "Byeonhan) — not to the Chinese Han dynasty. Hanguk is the South "
            "Korean self-name (North Koreans use 조선 Chosŏn). Hangugin = "
            "Korean person; Hangugmal = Korean language; Hangul = Korean "
            "script."
        ),
        roots=[
            "Korean 한 (han, ancient tribal name)",
            "Korean 국 (guk, country, from Chinese 國)",
        ],
        semantic_shift="'Han country' → Korea (South Korean self-designation)",
    ),
    EtymologyEntry(
        language="ko", lemma="한글",
        origin_summary=(
            "Hangul = the Korean alphabet, designed by King Sejong's scholars "
            "in 1443 (promulgated 1446 as 訓民正音 Hunminjeongeum, 'Correct "
            "Sounds for the Instruction of the People'). Originally called 언문 "
            "(eonmun, 'vernacular writing'); given its modern name 한글 (han = "
            "great + geul = letters) by linguist Ju Sigyeong in early 20th c. "
            "One of the few writing systems in human history with a known "
            "designer and date."
        ),
        roots=["Korean 한 (han, great)", "Korean 글 (geul, letters/writing)"],
        semantic_shift=(
            "Originally 'vernacular writing' (eonmun) → renamed 'Great "
            "Letters' (Hangul) in early 20th c."
        ),
    ),
    EtymologyEntry(
        language="ko", lemma="김치",
        origin_summary=(
            "Kimchi — fermented vegetables, Korea's national dish. Earliest "
            "forms attested ~1000 years ago; modern red kimchi (with chili) "
            "developed after the Columbian Exchange brought chili peppers in "
            "the 16th-17th century. The word kimchi derives from older 짐채 "
            "(jimchae) or 침채 (chimchae, 'salted vegetables'). UNESCO "
            "Intangible Cultural Heritage (2013, the kimjang/kimchi-making "
            "tradition)."
        ),
        roots=[
            "Older Korean 침채 (chimchae, salted vegetables) → 김치 (kimchi)",
        ],
        cognates=["English 'kimchi' (loanword)"],
        semantic_shift=(
            "'salted vegetables' → fermented vegetable preparation → Korean "
            "national dish; UNESCO intangible heritage"
        ),
    ),
    EtymologyEntry(
        language="ko", lemma="비빔밥",
        origin_summary=(
            "Bibimbap — 'mixed rice.' From 비비다 (bibida, 'to mix') + 밥 (bap, "
            "'cooked rice'). The traditional Korean dish of rice topped with "
            "assorted vegetables, meat, egg, and gochujang, mixed before "
            "eating. The Jeonju style (Jeolla province) is the most renowned. "
            "The word entered global vocabulary with the spread of Korean "
            "cuisine; Air France serves bibimbap on flights to Seoul."
        ),
        roots=["Korean 비비다 (bibida, to mix)", "Korean 밥 (bap, rice)"],
        cognates=["English 'bibimbap' (loanword)"],
        semantic_shift="'mixed rice' → iconic Korean dish; globalized name",
    ),
    EtymologyEntry(
        language="ko", lemma="막걸리",
        origin_summary=(
            "Makgeolli — milky rice-based alcohol. From 막 (mak, 'just-' or "
            "'rough/crude') + 거르다 (georeuda, 'to filter/strain'). "
            "Etymologically 'just-strained / roughly-strained' alcohol — the "
            "unfiltered, milky-white traditional Korean rice wine. Formerly a "
            "peasant drink; now experiencing artisanal revival both "
            "domestically and internationally."
        ),
        roots=[
            "Korean 막 (mak, rough/just)",
            "Korean 거르다 (georeuda, to strain)",
        ],
        cognates=["English 'makgeolli' (loanword)"],
        semantic_shift=(
            "'rough-strained' → traditional milky rice wine; artisanal "
            "renaissance from peasant drink"
        ),
    ),
    EtymologyEntry(
        language="ko", lemma="사랑",
        origin_summary=(
            "Sarang — love. Korean has multiple love-words: sarang (general "
            "love), jeong (affective bond), aejeong (formal romantic love, "
            "愛情). Sarang appears in countless K-pop and K-drama titles. The "
            "famous folk song 'Arirang' contains the line 'naerul beorigo "
            "gasineun nimeun shimrido motgaseo balbyeonganda' (the lover who "
            "leaves me will not even walk ten ri before their feet hurt) — "
            "sarang here gives the song its emotional weight."
        ),
        roots=[
            "Native Korean (debated origin: possibly from 思量 'sa-ryang, thinking-of')",
        ],
        semantic_shift="'love' as general emotion; central in Korean popular culture",
    ),
    EtymologyEntry(
        language="ko", lemma="효",
        origin_summary=(
            "Hyo = filial piety. From hanja 孝 (hyo) — a foundational "
            "Confucian virtue. The five Confucian relations (五倫 oryun) "
            "include filial piety as the cornerstone. Korean society remains "
            "markedly more Confucian than contemporary China or Japan in "
            "terms of practiced filial piety. Compounds: 효도 (hyodo, filial "
            "conduct), 효자 (hyoja, filial son), 불효 (bulhyo, unfilial conduct)."
        ),
        roots=["Sino-Korean 孝 (hyo, filial piety)"],
        cognates=["Chinese 孝 (xiào)", "Japanese 孝 (kō)"],
        semantic_shift=(
            "Confucian virtue 'filial piety' → cornerstone of Korean social "
            "ethics"
        ),
    ),
    EtymologyEntry(
        language="ko", lemma="기",
        origin_summary=(
            "Gi — vital energy/spirit, the same concept as Chinese qi and "
            "Japanese ki. From hanja 氣 (gi). Foundational in Korean "
            "traditional medicine, taekwondo, and folk-belief. Productive in "
            "compounds: 기분 (gibun, mood), 인기 (in'gi, popularity, lit. 'human- "
            "energy'), 분위기 (bunwigi, atmosphere). The same morpheme East- "
            "Asian-wide."
        ),
        roots=["Sino-Korean 氣 (gi)"],
        cognates=[
            "Chinese 氣 (qì)",
            "Japanese 気 (ki)",
            "English 'qi'/'chi' (loanwords)",
        ],
        semantic_shift="'vital energy' → atmosphere, mood; productive compound morpheme",
    ),
    EtymologyEntry(
        language="ko", lemma="양반",
        origin_summary=(
            "Yangban = the traditional Korean aristocracy. From hanja 兩班 "
            "(yang = two + ban = ranks): the 'two classes' of civil and "
            "military officials in the Joseon dynasty (1392-1910). "
            "Theoretically a meritocratic Confucian gentry (entered via civil "
            "service exam); in practice, hereditary nobility. The word "
            "survives in modern Korean as a slightly archaic term for "
            "'gentleman' (a husband may be called 우리 양반 = 'our yangban' = 'my "
            "old man')."
        ),
        roots=["Sino-Korean 兩班 (yangban, two classes)"],
        semantic_shift=(
            "'two classes' (civil + military officials) → Joseon aristocracy "
            "→ archaic 'gentleman'"
        ),
    ),
    EtymologyEntry(
        language="ko", lemma="선비",
        origin_summary=(
            "Seonbi — the Confucian scholar-gentleman ideal. The seonbi was "
            "meant to embody learning, integrity, and detachment from "
            "material gain. Often retreated from office to live in rural "
            "austerity (the seonbi-style hermitage). The seonbi ideal "
            "continues to inform Korean cultural conceptions of male "
            "intellectual integrity. Word possibly native Korean (etymology "
            "debated)."
        ),
        roots=["Native Korean 선비 (seonbi)"],
        semantic_shift=(
            "Confucian scholar-gentleman ideal; archetype of moral and "
            "intellectual integrity"
        ),
    ),
    EtymologyEntry(
        language="ko", lemma="두부",
        origin_summary=(
            "Dubu — tofu. From hanja 豆腐 (dou + fu = bean + rotting/ferment). "
            "The Chinese invention (~1st c. BCE) entered Korea ~7th-9th c. "
            "CE; refined locally. Korean dubu cuisine is distinctive (sundubu "
            "jjigae, dubu kimchi). The Japanese tofu and global English "
            "'tofu' come via Japanese; Korean preserves Sino-Korean reading."
        ),
        roots=["Chinese 豆腐 (dòufǔ, bean curd)"],
        cognates=[
            "Chinese 豆腐 (dòufu)",
            "Japanese 豆腐 (tōfu)",
            "English 'tofu' (via Japanese)",
        ],
        semantic_shift="'fermented bean' → bean curd; East Asian staple food",
    ),
    EtymologyEntry(
        language="ko", lemma="스승",
        origin_summary=(
            "Seuseung — teacher/master, especially in martial arts and "
            "traditional crafts. Distinguished from 선생 (seonsaeng, the Sino- "
            "Korean for 'teacher'): seuseung is more honorific and applies to "
            "lifelong masters. The seuseung-jeja (master-disciple) "
            "relationship is central in Korean martial arts (taekwondo) and "
            "traditional crafts. Sino-Korean origin debated."
        ),
        roots=[
            "Possibly Sino-Korean 師承 (sa-seung, master-inheritance) reanalyzed",
        ],
        semantic_shift=(
            "Master/teacher in lifelong-discipline contexts; martial arts and "
            "traditional crafts"
        ),
    ),
    EtymologyEntry(
        language="ko", lemma="선생",
        origin_summary=(
            "Seonsaeng — teacher; also general honorific 'sir/madam.' From "
            "hanja 先生 (xiānshēng = first-born). The honorific 'first-born' "
            "applied to teachers reflects a Confucian view of seniority. In "
            "modern Korean, seonsaeng-nim is the standard polite address for "
            "any educated/professional person, especially teachers, doctors. "
            "Same morphology in Japanese sensei and Chinese xiānshēng."
        ),
        roots=["Sino-Korean 先生 (seonsaeng, first-born)"],
        cognates=["Chinese 先生 (xiānshēng)", "Japanese 先生 (sensei)"],
        semantic_shift=(
            "'first-born' (Confucian seniority) → teacher → general polite "
            "honorific"
        ),
    ),
    EtymologyEntry(
        language="ko", lemma="도",
        origin_summary=(
            "Do — the Way. Korean reading of Chinese 道 (dào, the Tao). "
            "Productive suffix in martial arts: taekwondo (跆拳道, way of foot- "
            "fist), hapkido (合氣道), kumdo (劍道, way of sword). Same etymology "
            "and usage as Japanese -dō, Chinese -dào. Confucian, Daoist, and "
            "Buddhist Korean traditions all use the term."
        ),
        roots=["Chinese 道 (dào, way)"],
        cognates=["Chinese 道 (dào)", "Japanese 道 (dō)", "English 'Tao'/'Dao'"],
        semantic_shift="'way' → discipline-as-way; suffix in named martial arts",
    ),
    EtymologyEntry(
        language="ko", lemma="절",
        origin_summary=(
            "Jeol = Buddhist temple. From a native Korean root (uncertain "
            "etymology, possibly from 'jeol-hada' = to bow). All Korean "
            "Buddhist temples are 절 (jeol or sa, the Sino-Korean 寺). Common "
            "temple-name suffix: Bulguk-sa, Haein-sa. The Korean Seon (Zen) "
            "Buddhist tradition (Jogye Order) is one of Korea's most "
            "important religious institutions. UNESCO has multiple jeol on "
            "heritage lists."
        ),
        roots=["Native Korean 절 (jeol)"],
        semantic_shift=(
            "'temple' (also: 'bow' — possibly etymologically related); Korean "
            "Buddhist temple"
        ),
    ),
    EtymologyEntry(
        language="ko", lemma="임금",
        origin_summary=(
            "Imgeum — king. Native Korean word distinct from Sino-Korean 왕 "
            "(wang, 王). The two coexist: imgeum is more native/poetic, wang "
            "is the standard term in chronicle writing. Sejong the Great "
            "(Sejong daewang) is the most beloved imgeum in Korean history. "
            "The word imgeum is largely confined to historical/poetic "
            "contexts in modern Korean."
        ),
        roots=["Native Korean (uncertain etymology)"],
        semantic_shift=(
            "Native Korean 'king' (poetic, historical); Sino-Korean 왕 (wang) "
            "is the standard modern term"
        ),
    ),
    EtymologyEntry(
        language="ko", lemma="마을",
        origin_summary=(
            "Maeul = village. Native Korean word; distinct from Sino-Korean 동 "
            "(dong, ward) and 면 (myeon, district). The traditional Korean "
            "village (maeul) was organized around clan lines, with shared "
            "rituals (jangseung village guardian poles, maeul-gut shamanic "
            "rites). Modern Korean 'maeul' is used in residential complex "
            "names and rural geography."
        ),
        roots=["Native Korean 마을 (maeul)"],
        semantic_shift="'village'; native Korean term for traditional rural community",
    ),
    EtymologyEntry(
        language="ko", lemma="어머니",
        origin_summary=(
            "Eomeoni — mother. The standard formal/respectful term for "
            "mother. The diminutive 엄마 (eomma) is used by children and in "
            "intimate contexts. Korean kinship vocabulary is famously "
            "elaborated, with distinct words for paternal/maternal relatives. "
            "'Eomeoni' is the cornerstone of family vocabulary; it appears in "
            "countless Korean songs, poems, and idioms (예: 어머니의 마음 = a "
            "mother's heart)."
        ),
        roots=["Native Korean 엄 (eom, mother-root)"],
        semantic_shift="'mother' (formal); 엄마 (eomma) is the intimate/childhood form",
    ),
    EtymologyEntry(
        language="ko", lemma="아버지",
        origin_summary=(
            "Abeoji — father. Mirror of eomeoni. The intimate form is 아빠 "
            "(appa, dad/papa). Korean kinship is patrilineal in vocabulary: "
            "father's-side terms are distinct from mother's-side (paternal "
            "grandmother = 할머니, maternal = 외할머니). This Confucian-shaped "
            "vocabulary system is more elaborated than in Chinese or "
            "Japanese."
        ),
        roots=["Native Korean 압/아 (a, father-root)"],
        semantic_shift=(
            "'father' (formal); 아빠 (appa) is intimate/childhood; cornerstone "
            "of Korean kinship vocabulary"
        ),
    ),
    EtymologyEntry(
        language="ko", lemma="물",
        origin_summary=(
            "Mul — water. One of the most basic Korean words. Korean has "
            "elaborate water-vocabulary: 강 (gang, river), 바다 (bada, sea), 호수 "
            "(hosu, lake), 시내 (sinae, stream), 폭포 (pokpo, waterfall). Korean "
            "traditional water-spirits (yongwang, the dragon king) figure in "
            "shamanic and Buddhist tradition. The word 'mul' appears in "
            "countless idioms and compounds."
        ),
        roots=["Native Korean 물 (mul, water)"],
        semantic_shift="Native Korean 'water'; basic and productive",
    ),
    EtymologyEntry(
        language="ko", lemma="불",
        origin_summary=(
            "Bul — fire. Native Korean word. Confused/punned in Korean with 불 "
            "(bul) = the Buddha's-prefix (from Sanskrit Buddha through "
            "Chinese 佛 fó). The pun 'bul' (fire) and 'bul' (Buddha) is "
            "exploited in some folk-poetic registers. Both are productive: 불교 "
            "(bulgyo, Buddhism = Buddha-teaching), 불나다 (bul-nada, fire breaks "
            "out)."
        ),
        roots=["Native Korean 불 (bul, fire)"],
        cognates=[
            "Coincidental homophone with Sino-Korean 불 (bul, Buddha — from Sanskrit/Chinese)",
        ],
        semantic_shift=(
            "Native 'fire'; coincidental homophone with the Buddha-prefix "
            "creates pun-rich vocabulary"
        ),
    ),
    EtymologyEntry(
        language="ko", lemma="가족",
        origin_summary=(
            "Gajok — family. From hanja 家族 (ga = house + jok = clan/people). "
            "Korean family is traditionally extended: parents, grandparents, "
            "children, often also paternal aunts/uncles in one household "
            "(sambon-gajok = three-generation family). The hanja 族 (jok) "
            "means clan; appears in 민족 (minjok, ethnic nation) — a key Korean "
            "political concept."
        ),
        roots=["Sino-Korean 家族 (gajok, house-clan)"],
        cognates=["Chinese 家族 (jiāzú)", "Japanese 家族 (kazoku)"],
        semantic_shift="'house-clan' → family",
    ),
    EtymologyEntry(
        language="ko", lemma="민족",
        origin_summary=(
            "Minjok — ethnic nation, people. From hanja 民族 (min = people + "
            "jok = clan). A key Korean political concept: minjok stresses "
            "Korean ethnic continuity from ancient times. Both Korean states "
            "(North and South) deploy minjok-discourse to claim continuity. "
            "The 1948 Constitution and ongoing nationalist discourse rest on "
            "the minjok concept. Cognate term in Japanese minzoku, Chinese "
            "mínzú."
        ),
        roots=["Sino-Korean 民族 (minjok, people-clan)"],
        cognates=["Chinese 民族 (mínzú)", "Japanese 民族 (minzoku)"],
        semantic_shift=(
            "'people-clan' → ethnic nation; foundational political-cultural "
            "concept"
        ),
    ),
    EtymologyEntry(
        language="ko", lemma="동방예의지국",
        origin_summary=(
            "Dongbang yeuijiguk = 'Land of Eastern Courtesy/Propriety.' Sino- "
            "Korean phrase (東方禮儀之國) used historically to describe Korea — "
            "emphasizing Confucian moral cultivation as Korea's distinctive "
            "contribution to East Asian civilization. The phrase recurs in "
            "school textbooks and nationalist discourse. Self-image of Korea "
            "as preserving Confucian moral tradition more rigorously than "
            "China or Japan."
        ),
        roots=[
            "Sino-Korean 東方禮儀之國 (dongbang yeuijiguk, eastern propriety country)",
        ],
        semantic_shift=(
            "Sino-Korean idiom for Korea as land of Confucian propriety; "
            "recurrent in nationalist self-image"
        ),
    ),
    EtymologyEntry(
        language="ko", lemma="선",
        origin_summary=(
            "Seon = Korean Zen Buddhism. From the same Sanskrit dhyāna → "
            "Chinese chán → Korean seon → Japanese zen chain. Founded as a "
            "distinct Korean tradition by Doui (early 9th c.) and "
            "consolidated by Jinul (12th c.). The Jogye Order is the dominant "
            "Korean Buddhist organization, descending from Seon tradition. "
            "The Korean reading 'Seon' is widely used in academic Buddhist "
            "studies alongside Japanese 'Zen'."
        ),
        roots=["Sanskrit dhyāna → Chinese chán → Korean seon"],
        cognates=["Chinese 禪 (chán)", "Japanese 禅 (zen)", "Vietnamese Thiền"],
        semantic_shift=(
            "'meditation' → Korean Seon Buddhism (sister tradition to Chinese "
            "Chan and Japanese Zen)"
        ),
    ),
    EtymologyEntry(
        language="ko", lemma="삼강오륜",
        origin_summary=(
            "Samgang oryun = 'Three Bonds and Five Relations' — the Confucian "
            "framework of social relations: three bonds (ruler/subject, "
            "father/son, husband/wife) and five relations (above three + "
            "elder/younger, friend/friend). Foundational ethical structure of "
            "Joseon dynasty (1392-1910). Continues to shape modern Korean "
            "family/work culture. Sino-Korean phrase: 三綱五倫."
        ),
        roots=["Sino-Korean 三綱五倫 (samgang oryun)"],
        cognates=["Chinese 三綱五倫 (sāngāng wǔlún)"],
        semantic_shift=(
            "Confucian three-bonds-five-relations framework; structuring "
            "concept of Joseon ethics"
        ),
    ),
    EtymologyEntry(
        language="ko", lemma="사대부",
        origin_summary=(
            "Sadaebu = Joseon-era literati gentry. From hanja 士大夫 (sa = "
            "gentleman, daebu = great man). The educated elite who held "
            "office through civil service examinations and embodied Confucian "
            "culture. Their cultural ideal — austerity, learning, restraint — "
            "shaped the Korean cultural tradition (calligraphy, poetry, "
            "garden design). The sadaebu sensibility is foreground in much of "
            "Korean classical literature."
        ),
        roots=["Sino-Korean 士大夫 (sadaebu, gentleman + great man)"],
        cognates=["Chinese 士大夫 (shìdàfū)"],
        semantic_shift=(
            "'gentleman + great man' → Joseon literati class; cultural- "
            "aesthetic ideal"
        ),
    ),
    EtymologyEntry(
        language="ko", lemma="양반김",
        origin_summary=(
            "Dried-laver-and-rice combination — a popular Korean "
            "snack/staple, named etymologically as 'yangban gim' (gentleman's "
            "seaweed/laver). The aristocratic association of seaweed with "
            "elite tastes is preserved in the name. Korean gim (the seaweed "
            "sheets used in gimbap and as a side dish) is distinct from "
            "Japanese nori; the Korean variety is darker and more brittle, "
            "often roasted."
        ),
        roots=[
            "Sino-Korean 양반 (yangban, aristocrat)",
            "Native Korean 김 (gim, dried laver/seaweed)",
        ],
        semantic_shift="Cultural compound: seaweed snack with aristocratic naming",
    ),
    EtymologyEntry(
        language="ko", lemma="대한민국",
        origin_summary=(
            "Daehan minguk = 'Republic of Great Korea' — the official name of "
            "South Korea. From hanja 大韓民國: dae (great) + han (Korea, the "
            "Three Han) + min (people) + guk (state). The name was first used "
            "in 1897 as the Daehan Empire (Daehan Jeguk), the short-lived "
            "empire that preceded Japanese annexation. Reused for the 1948 "
            "Republic. North Korea uses 조선 (Chosŏn) for its self-name."
        ),
        roots=["Sino-Korean 大韓民國 (daehan minguk)"],
        semantic_shift=(
            "'Great Han People State' → official South Korean self-name "
            "(1948-)"
        ),
    ),
    EtymologyEntry(
        language="ko", lemma="조선",
        origin_summary=(
            "Chosŏn = the dynasty (1392-1910), and the North Korean self- "
            "name. From the ancient Gojoseon kingdom (legendary founding 2333 "
            "BCE by Dangun). The hanja 朝鮮 means 'morning calm' (literal) — "
            "hence 'Land of the Morning Calm,' a Romantic appellation "
            "popularized in 19th-c. Western writing. The North Korean state "
            "preserves Chosŏn as its self-designation: 조선민주주의인민공화국 (DPRK)."
        ),
        roots=["Sino-Korean 朝鮮 (chosŏn, morning calm)"],
        cognates=["Chinese 朝鮮 (cháoxiǎn)", "Japanese 朝鮮 (chōsen)"],
        semantic_shift=(
            "'Morning Calm' → ancient kingdom → Joseon dynasty → North Korean "
            "self-designation"
        ),
    ),
    EtymologyEntry(
        language="ko", lemma="장",
        origin_summary=(
            "Jang — fermented sauce/paste base of Korean cuisine. The three "
            "foundational jang are doenjang (된장, fermented soybean paste), "
            "gochujang (고추장, fermented chili paste), and ganjang (간장, soy "
            "sauce). The character 醬 (jang/jiang) is the same East-Asian- "
            "wide. Jang preparation is a craft tradition: traditional jang "
            "requires months-long fermentation in onggi (clay pots)."
        ),
        roots=["Chinese 醬 (jiàng, fermented sauce)"],
        cognates=["Chinese 醬 (jiàng)", "Japanese 醤 (jō)"],
        semantic_shift=(
            "'fermented sauce' → core Korean culinary base; doenjang, "
            "gochujang, ganjang"
        ),
    ),
    EtymologyEntry(
        language="ko", lemma="고추장",
        origin_summary=(
            "Gochujang = chili paste. From 고추 (gochu, chili pepper) + 장 "
            "(jang, fermented paste). Chili peppers entered Korea after the "
            "Columbian Exchange (16th-17th c.) — via Portuguese-Japanese "
            "trade routes. Modern Korean cuisine's red color and spice are "
            "post-1600 developments. Gochujang fermentation traditionally "
            "took months; commercialized in mid-20th c. Now globally "
            "recognized via Korean cuisine's spread."
        ),
        roots=[
            "Korean 고추 (gochu, chili pepper)",
            "Sino-Korean 醬 (jang, fermented paste)",
        ],
        cognates=["English 'gochujang' (loanword in food culture)"],
        semantic_shift=(
            "Post-Columbian Korean innovation: chili + fermented paste = the "
            "red base of modern Korean cuisine"
        ),
    ),
    EtymologyEntry(
        language="ko", lemma="선비정신",
        origin_summary=(
            "Seonbi-jeongsin = 'seonbi spirit' — the cultural ideal of the "
            "Confucian scholar-gentleman: austerity, learning, integrity, "
            "public service tempered by willingness to retreat from corrupt "
            "office. Cited in modern Korean discourse on civic virtue. Often "
            "invoked in critiques of materialism, calling for return to "
            "seonbi-style restraint and moral seriousness."
        ),
        roots=["Korean 선비 (seonbi)", "Sino-Korean 정신 (jeongsin, spirit)"],
        semantic_shift=(
            "'seonbi-spirit' → Korean civic-cultural ideal of scholarly "
            "restraint and integrity"
        ),
    ),
    EtymologyEntry(
        language="ko", lemma="한복",
        origin_summary=(
            "Hanbok = traditional Korean dress. From 한 (han, Korean) + 복 "
            "(bok, clothing, from Sino-Korean 服). The hanbok of the Joseon "
            "period (women's high-waisted jeogori jacket and full chima "
            "skirt; men's jeogori and baji trousers) is the modern reference "
            "form. North Korea calls the same garments 조선옷 (chosŏn-ot). Now "
            "mostly worn for ceremonies, but undergoing fashion revival."
        ),
        roots=["Korean 한 (han, Korean)", "Sino-Korean 服 (bok, clothing)"],
        semantic_shift=(
            "'Korean clothing' → traditional Korean dress; ceremonial use + "
            "modern fashion revival"
        ),
    ),
    EtymologyEntry(
        language="ko", lemma="한지",
        origin_summary=(
            "Hanji = Korean traditional paper. Made from mulberry tree bark "
            "(dak), prized for its strength and longevity (some hanji "
            "manuscripts have survived 1000+ years). UNESCO has certified "
            "hanji-making as Intangible Cultural Heritage. Used historically "
            "for documents, fans, lamp-shades, and as a wall-covering. Korean "
            "hanji is distinguished from Chinese xuanzhi and Japanese washi."
        ),
        roots=["Korean 한 (han, Korean)", "Sino-Korean 紙 (ji, paper)"],
        cognates=[
            "Japanese 和紙 (washi, Japanese paper — parallel construction)",
        ],
        semantic_shift=(
            "'Korean paper' → mulberry-bark traditional paper; UNESCO "
            "heritage"
        ),
    ),
    EtymologyEntry(
        language="ko", lemma="노래",
        origin_summary=(
            "Norae — song. Native Korean word. The verbal form 노래하다 "
            "(noraehada = to sing). Korean has rich song traditions: pansori "
            "(epic narrative singing), minyo (folk songs), and modern K-pop. "
            "The phrase 'noraebang' (노래방 = song-room) is the Korean karaoke "
            "concept; gives Korean youth culture its distinctive social "
            "ritual."
        ),
        roots=["Native Korean 노래 (norae)"],
        semantic_shift="'song'; productive in modern compounds (noraebang = karaoke)",
    ),
    EtymologyEntry(
        language="ko", lemma="춤",
        origin_summary=(
            "Chum — dance. Native Korean word. Traditional Korean dance forms "
            "include the elegant gimu (rhythmic court dance) and folk talchum "
            "(mask dance). The verbal compound 'chumeul chuda' (to dance — "
            "literally 'to dance a dance') exhibits the cognate-object "
            "pattern characteristic of Korean. K-pop choreography has "
            "globalized contemporary Korean chum culture."
        ),
        roots=["Native Korean 춤 (chum)"],
        semantic_shift="'dance'; from traditional folk dance to K-pop choreography",
    ),
    EtymologyEntry(
        language="ko", lemma="씨름",
        origin_summary=(
            "Ssireum — Korean wrestling. UNESCO Intangible Cultural Heritage "
            "(2018, jointly listed by both Koreas — a rare instance of inter- "
            "Korean cooperation). Traditional sport with ancient origins, "
            "central to harvest festivals. Mongolian-style belt wrestling: "
            "opponents grip each other's satba (cloth belt around hips and "
            "thighs). National professional ssireum exists; the most famous "
            "champion is Lee Man-gi."
        ),
        roots=["Native Korean 씨름 (ssireum)"],
        semantic_shift="'wrestling'; UNESCO heritage co-listed by both Koreas",
    ),
    EtymologyEntry(
        language="ko", lemma="두레",
        origin_summary=(
            "Dure — traditional cooperative farming/work groups. Korean "
            "villages organized labor through dure for transplanting rice, "
            "harvesting, and major construction. Reflects Korean "
            "communitarianism (jeong-based social organization) at the "
            "village level. The dure tradition has been studied by Korean "
            "ethnographers as a precursor to modern cooperative movements."
        ),
        roots=["Native Korean 두레 (dure)"],
        semantic_shift=(
            "'work cooperative' → traditional village labor organization; "
            "ethnographic concept"
        ),
    ),
    EtymologyEntry(
        language="ko", lemma="굿",
        origin_summary=(
            "Gut — Korean shamanic ritual. From a Native Korean root, "
            "possibly related to 'good' (cf. English good fortune). Performed "
            "by the mudang (female shaman, 무당) — an ancient pre-Buddhist "
            "religious tradition that survives alongside Buddhism, "
            "Confucianism, and Christianity. The mudang/gut tradition shapes "
            "Korean folk culture, music (samul nori), and spiritual "
            "sensibility."
        ),
        roots=["Native Korean 굿 (gut)"],
        semantic_shift=(
            "'shamanic ritual'; ancient tradition surviving alongside "
            "organized religions"
        ),
    ),
    EtymologyEntry(
        language="ko", lemma="산",
        origin_summary=(
            "San — mountain. From hanja 山 (shān). Korean mountain religion "
            "(sansin, the mountain god) is foundational to Korean folk "
            "belief. Most Buddhist temples are mountain temples (san-sa). "
            "Korean national parks center on mountains: Seoraksan, Hallasan, "
            "Jirisan. The Sino-Korean reading 'san' coexists with native "
            "Korean 뫼 (moe, archaic mountain)."
        ),
        roots=["Chinese 山 (shān)"],
        cognates=["Chinese 山 (shān)", "Japanese 山 (san)"],
        semantic_shift=(
            "Sino-Korean 'mountain'; productive suffix in temple names and "
            "place names"
        ),
    ),
    EtymologyEntry(
        language="ko", lemma="강",
        origin_summary=(
            "Gang — river. Sino-Korean (江, jiāng). The Han River (Hangang, "
            "한강) flows through Seoul; the Naktong, Geum, Yeongsan are other "
            "major rivers. The Han River miracle (Hangang-ui gijeok) refers "
            "to South Korea's rapid economic development. Native Korean "
            "'naet' (시내, sinae = stream) is distinct from the larger 'gang.'"
        ),
        roots=["Chinese 江 (jiāng, river)"],
        cognates=["Chinese 江 (jiāng)", "Japanese 江 (kō)"],
        semantic_shift="Sino-Korean 'river'; productive in geographical names",
    ),
    EtymologyEntry(
        language="ko", lemma="달",
        origin_summary=(
            "Dal — moon. Native Korean word. Korean lunar calendar tradition "
            "(음력 eumnyeok) shapes major festivals: Seollal (Lunar New Year), "
            "Chuseok (Mid-Autumn Festival). The moon-rabbit (dal-tokki) folk "
            "belief — that a rabbit pounds rice cakes on the moon — is shared "
            "with Chinese and Japanese tradition. Korean popular songs and "
            "proverbs use 'dal' extensively for emotional resonance."
        ),
        roots=["Native Korean 달 (dal)"],
        semantic_shift="'moon'; central in lunar-calendar festivals and folk imagination",
    ),
    EtymologyEntry(
        language="ko", lemma="해",
        origin_summary=(
            "Hae — sun. Native Korean word; also means 'year' (the solar "
            "year). Korean solar/lunar calendar duality: 해 (sun/year) vs. 달 "
            "(moon/month). Korean Buddhist and Confucian rituals are "
            "calibrated to both calendars. The Korean flag (taegeukgi) "
            "features taegeuk (yin-yang) and four trigrams of the I Ching, "
            "symbolizing cosmic harmony — sun and moon are central in this "
            "iconography."
        ),
        roots=["Native Korean 해 (hae)"],
        semantic_shift=(
            "'sun' (also 'year' — the solar cycle); central in Korean "
            "cosmology and calendar"
        ),
    ),
    EtymologyEntry(
        language="ko", lemma="꽃",
        origin_summary=(
            "Kkot — flower. Native Korean word. Korean has rich flower "
            "symbolism: mugunghwa (무궁화, hibiscus syriacus, the Korean "
            "national flower), jindallae (azalea, beloved in Kim Sowol's poem "
            "of the same name), maehwa (plum blossom). The kkot-poem (꽃-시) "
            "tradition is a recognized Korean literary subgenre. The verb 피다 "
            "(pida = to bloom) pairs with kkot in countless lyrical formulas."
        ),
        roots=["Native Korean 꽃 (kkot)"],
        semantic_shift="'flower'; rich in symbolic, literary, and national associations",
    ),
    EtymologyEntry(
        language="ko", lemma="별",
        origin_summary=(
            "Byeol — star. Native Korean word. Korean folk astronomy "
            "distinguished the Big Dipper (북두칠성, bukdu chilseong = north- "
            "dipper-seven-star), the Milky Way (은하수, eunhasu), and individual "
            "major stars. The folk belief that human lives are tied to stars "
            "(each person has a guardian star) shapes Korean folk-religious "
            "cosmology. Modern Korean preserves all these astronomical terms."
        ),
        roots=["Native Korean 별 (byeol)"],
        semantic_shift="'star'; central in folk astronomy and folk-religious cosmology",
    ),
    EtymologyEntry(
        language="ko", lemma="바람",
        origin_summary=(
            "Baram — wind, also 'desire/wish' (the same word covers both). "
            "The double meaning is exploited in poetry and song: a wind that "
            "is also a longing. The compound 'bara-da' (바라다 = to hope/wish) "
            "is from the same root. The Korean cosmological/aesthetic sense "
            "of wind as both physical and metaphysical is captured in this "
            "lexical economy."
        ),
        roots=["Native Korean 바람 (baram)"],
        semantic_shift="'wind' = 'wish/desire'; double meaning exploited in poetry",
    ),

    # ── ZH additions (generated by gen_etymology.py) ──
    EtymologyEntry(
        language="zh", lemma="龍",
        origin_summary=(
            "Lóng — dragon. The character 龍 (traditional) / 龙 (simplified) "
            "depicts a serpentine creature with horns. The Chinese dragon is "
            "benevolent (unlike Western), associated with imperial power, "
            "water, weather, and good fortune. Imperial robes, throne, and "
            "lineage are 'dragon' (long): the emperor was the 'dragon-son' "
            "(long-zi). Chinese New Year 龍年 (Year of the Dragon) is the most "
            "auspicious zodiac year."
        ),
        roots=["Oracle bone graph for the dragon-creature"],
        cognates=[
            "Japanese 龍 (ryū)",
            "Korean 룡 (ryong)",
            "Vietnamese 龍 (long)",
        ],
        semantic_shift=(
            "Pictographic dragon → imperial symbol → benevolent supernatural "
            "creature; auspicious in all East Asian cultures"
        ),
    ),
    EtymologyEntry(
        language="zh", lemma="仁",
        origin_summary=(
            "Rén — benevolence/humaneness. The defining Confucian virtue: the "
            "character 仁 combines 人 (person) + 二 (two) — humaneness is what "
            "passes between two people. 'Rén' is what distinguishes the "
            "cultivated person (君子 jūnzǐ) from the petty (小人 xiǎorén). "
            "Translations include 'benevolence,' 'humaneness,' 'goodness.' "
            "Confucius spent his career trying to define and demonstrate rén; "
            "the Analects circle the concept."
        ),
        roots=[
            "Chinese 仁 (人 person + 二 two: humaneness as between-two-persons)",
        ],
        cognates=["Japanese 仁 (jin)", "Korean 인 (in)"],
        semantic_shift=(
            "'person + two' → humaneness as relational virtue; central "
            "Confucian concept"
        ),
    ),
    EtymologyEntry(
        language="zh", lemma="義",
        origin_summary=(
            "Yì — righteousness, justice, the fitting/right thing. Paired "
            "with rén (仁) as the second of the cardinal virtues. "
            "Etymologically 我 (I/self) + 羊 (sheep — sacrificial animal, hence "
            "'auspicious/correct'). The Confucian tradition treats yì as "
            "'doing what is fitting in each situation' — context-sensitive "
            "righteousness. Modern Chinese 義務 (yìwù) = duty, 義氣 (yìqì) = "
            "loyalty among friends."
        ),
        roots=[
            "Chinese 義 (我 + 羊: self + sheep — fitting/sacrificial-correct)",
        ],
        cognates=["Japanese 義 (gi — as in giri)", "Korean 의 (ui)"],
        semantic_shift=(
            "'self + sheep' → righteousness as situational fittingness → "
            "loyalty, duty"
        ),
    ),
    EtymologyEntry(
        language="zh", lemma="禮",
        origin_summary=(
            "Lǐ — ritual/propriety. Confucian virtue: ritual conduct that "
            "constitutes social and cosmic order. The Book of Rites (Liji 禮記) "
            "compiles ritual codes. Etymologically the character depicts "
            "ritual vessels with offerings. Lǐ ranges from grand state "
            "ceremony to everyday courtesy. Confucius held that ritual "
            "without rén is empty, and rén without ritual lacks form — the "
            "two virtues are mutually constitutive."
        ),
        roots=["Chinese 禮: pictogram of ritual vessels with offerings"],
        cognates=["Japanese 礼 (rei)", "Korean 례 (rye)"],
        semantic_shift="'ritual offering' → ritual propriety → courtesy/etiquette",
    ),
    EtymologyEntry(
        language="zh", lemma="智",
        origin_summary=(
            "Zhì — wisdom. Confucian virtue: practical wisdom in evaluating "
            "people and situations. The character 智 = 知 (knowing) + 日 (sun) — "
            "knowledge made bright as sunlight. Distinguished from mere "
            "learning (學 xué) or knowledge (知 zhī): zhì is the ethical "
            "exercise of judgment. The four virtues (rén, yì, lǐ, zhì) in "
            "Mencius were extended to five with xìn (信, trust)."
        ),
        roots=["Chinese 智 = 知 + 日 (knowing + sun = enlightened knowing)"],
        cognates=["Japanese 智 (chi)", "Korean 지 (ji)"],
        semantic_shift="'enlightened knowing' → wisdom as ethical discernment",
    ),
    EtymologyEntry(
        language="zh", lemma="信",
        origin_summary=(
            "Xìn — trustworthiness, faithfulness, belief. The character 信 = 人 "
            "(person) + 言 (word/speech): a person standing by their word. The "
            "fifth Confucian virtue (rén-yì-lǐ-zhì-xìn). Modern compounds: 信任 "
            "(xìnrèn, trust), 信用 (xìnyòng, credit), 信仰 (xìnyǎng, faith). The "
            "character itself models the virtue: word and person aligned."
        ),
        roots=["Chinese 信 = 人 + 言 (person + word)"],
        cognates=["Japanese 信 (shin)", "Korean 신 (sin)"],
        semantic_shift="'person + word' → trustworthiness; the fifth Confucian virtue",
    ),
    EtymologyEntry(
        language="zh", lemma="孝",
        origin_summary=(
            "Xiào — filial piety. Foundation of Confucian family ethics. The "
            "character 孝 = 老 (elder, abbreviated) + 子 (child) — child "
            "supporting elder. The Classic of Filial Piety (Xiaojing) is one "
            "of the foundational Confucian texts. East Asian practiced filial "
            "piety differs from Western parent-respect: it includes sacrifice "
            "of personal desires for family duty, ancestor reverence, and "
            "lifelong responsibility. Modern PRC has reintroduced filial- "
            "piety-based laws (children legally required to visit parents)."
        ),
        roots=["Chinese 孝 = 老 (elder) + 子 (child)"],
        cognates=["Japanese 孝 (kō)", "Korean 효 (hyo)"],
        semantic_shift="'child supporting elder' → filial piety as foundational virtue",
    ),
    EtymologyEntry(
        language="zh", lemma="中",
        origin_summary=(
            "Zhōng — center, middle. The defining graph of China itself: 中國 "
            "(Zhōngguó) = 'Middle Kingdom.' The character is a vertical line "
            "through a square — center marker. Doctrine of the Mean (中庸 "
            "Zhōngyōng) is one of the Four Books of Confucianism. Centrality "
            "is not just geographic but cosmological-ethical: the middle way "
            "avoids extremes."
        ),
        roots=[
            "Chinese 中: pictogram of a center-marker (line through square)",
        ],
        cognates=["Japanese 中 (chū)", "Korean 중 (jung)"],
        semantic_shift=(
            "'center' → China (the Middle Kingdom) → ethical mean (Doctrine "
            "of the Mean)"
        ),
    ),
    EtymologyEntry(
        language="zh", lemma="氣",
        origin_summary=(
            "Qì — vital energy, breath, spirit. Foundational concept of "
            "Chinese cosmology, medicine, and martial arts. The character 氣 "
            "originally meant 'rising vapor/cloud' (with 米 'rice' added later "
            "— the steam rising from cooking rice). Qì circulates through "
            "meridians (jīngluò) in traditional Chinese medicine; qigong (氣功 "
            "'qi-work') cultivates it. The same morpheme East-Asian-wide: "
            "Japanese ki, Korean gi."
        ),
        roots=["Chinese 氣: original pictogram of vapor/cloud"],
        cognates=[
            "Japanese 気 (ki)",
            "Korean 기 (gi)",
            "English 'qi'/'chi' (loanword)",
        ],
        semantic_shift=(
            "'rising vapor' → vital energy → universal Chinese "
            "cosmological/medical principle"
        ),
    ),
    EtymologyEntry(
        language="zh", lemma="陰",
        origin_summary=(
            "Yīn — the dark, female, receptive principle of yin-yang "
            "cosmology. Etymologically 'shaded side of a mountain' (陰 = 阜 "
            "hill + 侌 cloud-cover). Paired with yáng (sun-side of mountain) "
            "in the foundational dualism of Chinese cosmology. Originating in "
            "the I Ching and developed by Han-dynasty cosmologists. Yīn-yáng "
            "is generative complementarity, not opposition."
        ),
        roots=["Chinese 陰: 阜 (hill) + 侌 (cloud-cover) = shaded slope"],
        cognates=[
            "Japanese 陰 (in)",
            "Korean 음 (eum)",
            "English 'yin' (loanword)",
        ],
        semantic_shift=(
            "'shaded slope' → the dark/receptive principle → cosmological "
            "pole"
        ),
    ),
    EtymologyEntry(
        language="zh", lemma="陽",
        origin_summary=(
            "Yáng — the bright, male, active principle of yin-yang cosmology. "
            "Etymologically 'sunny side of a mountain' (陽 = 阜 hill + 昜 sun- "
            "rays). Mirror of yīn. The complementary pairing yīn-yáng "
            "generates the eight trigrams of the I Ching, the five elements, "
            "and the entire Chinese cosmological scheme. The character 陽 also "
            "appears in many place names: south-of-river or north-of-mountain "
            "locations are 'yang' (sunny)."
        ),
        roots=["Chinese 陽: 阜 (hill) + 昜 (sun-rays) = sunny slope"],
        cognates=[
            "Japanese 陽 (yō)",
            "Korean 양 (yang)",
            "English 'yang' (loanword)",
        ],
        semantic_shift="'sunny slope' → the bright/active principle → cosmological pole",
    ),
    EtymologyEntry(
        language="zh", lemma="天",
        origin_summary=(
            "Tiān — heaven, sky, the divine cosmic order. The character 天 "
            "depicts a person (大) with a flat top — head/heaven above. Tiān "
            "is more abstract than the personal gods: the impersonal cosmic- "
            "moral order. The 'Mandate of Heaven' (天命 Tiānmìng) legitimates "
            "dynasties; loss of mandate justifies rebellion. Tiān is one of "
            "the most theologically rich Chinese concepts, distinct from "
            "anthropomorphic deities."
        ),
        roots=[
            "Chinese 天: pictogram of person with flat top (head/heaven)",
        ],
        cognates=["Japanese 天 (ten)", "Korean 천 (cheon)"],
        semantic_shift=(
            "'sky/head' → impersonal cosmic-moral order → Mandate of Heaven "
            "(political theology)"
        ),
    ),
    EtymologyEntry(
        language="zh", lemma="地",
        origin_summary=(
            "Dì — earth, land, ground. The earth-pole opposing heaven (天) in "
            "Chinese cosmology. Heaven is round, earth is square (the ancient "
            "cosmological model). The character 地 = 土 (earth) + 也 (phonetic). "
            "The pairing tiāndì (天地) = heaven-earth = the cosmos. Many "
            "Chinese names include 'di' for the earthly element of cosmic "
            "balance."
        ),
        roots=["Chinese 地: 土 (earth) + 也 (phonetic)"],
        cognates=["Japanese 地 (chi)", "Korean 지 (ji)"],
        semantic_shift="'earth' → cosmic pole opposing heaven → cosmos as tiandi",
    ),
    EtymologyEntry(
        language="zh", lemma="人",
        origin_summary=(
            "Rén — person/human. The character 人 is among the simplest in "
            "Chinese: a pictogram of two legs walking. The basic graph; "
            "foundation of countless compounds. 'Heaven, earth, person' "
            "(tian-di-ren, 天地人) is a triadic Chinese cosmological scheme: "
            "humans complete the cosmos by their ethical action. Confucian "
            "ethics centers on the cultivation of rén (人, person — same "
            "character as the virtue rén 仁 with different reading; they may "
            "share etymology)."
        ),
        roots=["Chinese 人: pictogram of person (two legs walking)"],
        cognates=["Japanese 人 (jin/hito)", "Korean 인 (in)"],
        semantic_shift=(
            "Pictographic 'person'; cosmologically the third pole (heaven- "
            "earth-person)"
        ),
    ),
    EtymologyEntry(
        language="zh", lemma="德",
        origin_summary=(
            "Dé — virtue, moral power, charisma. Paired with dào in the title "
            "Dao-De-Jing (道德經) — Tao Te Ching = 'Classic of the Way and "
            "Virtue.' Dé is the moral force that emanates from a virtuous "
            "person, accomplishing without coercion (the wuwei effective- "
            "action of Daoism). The character 德 = 彳 (action) + 直 (straight) + "
            "心 (heart) — straight-hearted action."
        ),
        roots=["Chinese 德: 彳 (action) + 直 (straight) + 心 (heart)"],
        cognates=["Japanese 徳 (toku)", "Korean 덕 (deok)"],
        semantic_shift=(
            "'straight-hearted action' → moral power → charisma that achieves "
            "without coercion"
        ),
    ),
    EtymologyEntry(
        language="zh", lemma="心",
        origin_summary=(
            "Xīn — heart-mind. The character 心 is a pictogram of the human "
            "heart. In classical Chinese, xīn is the seat of both thought and "
            "feeling — what English splits into 'heart' (emotion) and 'mind' "
            "(thought). Same word covers both. The Mencius vs. Xunzi debate "
            "over the nature of the heart-mind (good or self-interested?) "
            "shaped Chinese moral philosophy. Wang Yangming's school is "
            "called 'School of the Heart-Mind' (心學 xīnxué)."
        ),
        roots=["Chinese 心: pictogram of heart"],
        cognates=["Japanese 心 (kokoro)", "Korean 심 (sim)"],
        semantic_shift=(
            "'heart' = both heart and mind unified; central to philosophical "
            "anthropology"
        ),
    ),
    EtymologyEntry(
        language="zh", lemma="字",
        origin_summary=(
            "Zì — character/written word. Distinct from 詞 (cí, word/phrase): "
            "zì is the unit of writing (one character), cí is the unit of "
            "meaning. Chinese has ~50,000 distinct zì in major dictionaries; "
            "modern literacy requires ~3,000-4,000. The character 字 = 宀 "
            "(roof) + 子 (child) — etymologically 'a child under a roof' (a "
            "domesticated/cultivated thing)."
        ),
        roots=["Chinese 字: 宀 (roof) + 子 (child)"],
        cognates=["Japanese 字 (ji)", "Korean 자 (ja)"],
        semantic_shift="'child under roof' (domesticated thing) → written character",
    ),
    EtymologyEntry(
        language="zh", lemma="山",
        origin_summary=(
            "Shān — mountain. Pictogram of three peaks. One of the simplest, "
            "oldest characters. Mountain reverence is foundational in Chinese "
            "culture: the Five Sacred Mountains (五嶽 wǔyuè) — Tai Shan, Hua "
            "Shan, Heng Shan (north and south), Song Shan — define the "
            "spiritual geography. Mountains as the dwelling-place of "
            "immortals shaped Daoism. Confucius said: 'The wise delight in "
            "water; the humane delight in mountains' (智者樂水仁者樂山)."
        ),
        roots=["Chinese 山: pictogram of three peaks"],
        cognates=["Japanese 山 (san/yama)", "Korean 산 (san)"],
        semantic_shift="Pictographic mountain; spiritual geography of China",
    ),
    EtymologyEntry(
        language="zh", lemma="水",
        origin_summary=(
            "Shuǐ — water. Pictogram of flowing water. Together with 山 "
            "(mountain), shuǐ defines Chinese landscape (山水 shānshuǐ = "
            "landscape, lit. 'mountains and waters'). 山水画 (shānshuǐhuà) is "
            "the genre of landscape painting. In Daoism, water is the model "
            "of effective action: yielding yet powerful, finding the lowest "
            "place yet wearing down stone."
        ),
        roots=["Chinese 水: pictogram of flowing water"],
        cognates=["Japanese 水 (sui/mizu)", "Korean 수 (su)"],
        semantic_shift="Pictographic water; with 山 forms 山水 = landscape (the genre name)",
    ),
    EtymologyEntry(
        language="zh", lemma="風",
        origin_summary=(
            "Fēng — wind. Beyond meteorology: 'wind' in Chinese vocabulary "
            "means 'style, character, atmosphere' (風格 fēnggé = style). "
            "'Customs' (風俗 fēngsú) and 'Book of Songs' (詩經, the Feng-Ya-Song "
            "division of the songs) preserve this expanded sense. 風水 (fēng- "
            "shuǐ, wind-water) = geomancy. The character 風 (traditional) "
            "shows wind blowing through a hollow."
        ),
        roots=["Chinese 風: pictogram suggesting wind"],
        cognates=["Japanese 風 (fū/kaze)", "Korean 풍 (pung)"],
        semantic_shift=(
            "'wind' → style/atmosphere/customs; productive in compounds "
            "(fengshui, fenggu)"
        ),
    ),
    EtymologyEntry(
        language="zh", lemma="月",
        origin_summary=(
            "Yuè — moon, month. Single character serves both: the moon is the "
            "unit of the (lunar) month. Pictogram of crescent moon. Mid- "
            "Autumn Festival (中秋節) celebrates the full moon; mooncakes are "
            "eaten. The Chinese mythology of Chang'e flying to the moon is "
            "one of the most beloved stories. The character 月 is among the "
            "oldest and most stable."
        ),
        roots=["Chinese 月: pictogram of crescent moon"],
        cognates=["Japanese 月 (gatsu/tsuki)", "Korean 월 (wol)"],
        semantic_shift="'moon' = 'month'; central in lunar calendar and folklore",
    ),
    EtymologyEntry(
        language="zh", lemma="日",
        origin_summary=(
            "Rì — sun, day. Pictogram (originally a circle with dot in "
            "center). Single character serves both: the sun is the unit of "
            "the day. The character is among the simplest and oldest. Modern "
            "Chinese 日 means 'day' in dating (3月15日 = March 15); 太陽 (tàiyáng, "
            "'great yang') is now more common for 'sun' the celestial body."
        ),
        roots=["Chinese 日: pictogram of sun"],
        cognates=["Japanese 日 (nichi/hi)", "Korean 일 (il)"],
        semantic_shift="'sun' = 'day'; basic graph in countless compounds",
    ),
    EtymologyEntry(
        language="zh", lemma="家",
        origin_summary=(
            "Jiā — family, home, school of thought. The character 家 = 宀 "
            "(roof) + 豕 (pig) — a pig under a roof (the original domesticated "
            "animal in the household). 家 also means 'school of thought' "
            "(philosophical school): the Confucian school is 儒家 (rújiā), "
            "Daoist 道家 (dàojiā), Legalist 法家 (fǎjiā). The 'Hundred Schools of "
            "Thought' (諸子百家) of the Warring States period."
        ),
        roots=["Chinese 家: 宀 (roof) + 豕 (pig)"],
        cognates=["Japanese 家 (ka/ie)", "Korean 가 (ga)"],
        semantic_shift=(
            "'pig under roof' (domestic) → family, home → also: school of "
            "thought"
        ),
    ),
    EtymologyEntry(
        language="zh", lemma="國",
        origin_summary=(
            "Guó — country, state. The character 國 (traditional) shows a 戈 "
            "(halberd/weapon) defending a 口 (territory) within a 囗 (border) — "
            "a defended territory. Simplified form 国 substitutes 玉 (jade) for "
            "the weapon-territory inside, suggesting national treasure. The "
            "shift 國→国 is one of the most visible character simplifications "
            "in 1950s reform."
        ),
        roots=["Chinese 國: 戈 (weapon) + 口 (territory) + 囗 (border)"],
        cognates=["Japanese 国 (koku/kuni)", "Korean 국 (guk)"],
        semantic_shift=(
            "'defended bordered territory' → state/country; character "
            "simplified in 1950s"
        ),
    ),
    EtymologyEntry(
        language="zh", lemma="和",
        origin_summary=(
            "Hé — harmony, peace, and (conjunction). Multivalent: 和平 (hépíng, "
            "peace), 和氣 (héqì, harmonious), 和 used as conjunction 'and.' The "
            "character 和 = 禾 (grain) + 口 (mouth) — eating grain together. The "
            "Confucian/Daoist value of harmony as cosmological-social ideal. "
            "Japan adopted 和 as a self-name (see Japanese 和 entry). Hé is "
            "opposed to 同 (tóng, sameness): 'The gentleman harmonizes but "
            "does not conform' (君子和而不同)."
        ),
        roots=["Chinese 和: 禾 (grain) + 口 (mouth)"],
        cognates=["Japanese 和 (wa)", "Korean 화 (hwa)"],
        semantic_shift="'eating grain together' → harmony → 'and' (conjunction)",
    ),
    EtymologyEntry(
        language="zh", lemma="美",
        origin_summary=(
            "Měi — beautiful. Etymologically 'large sheep' (羊 sheep + 大 "
            "large) — beauty as 'big sheep,' i.e., abundance/auspiciousness. "
            "The aesthetic-ethical-religious overlap is preserved: 美 means "
            "both 'aesthetically beautiful' and 'morally good.' 美國 (Měiguó) = "
            "'beautiful country' = the United States (chosen as "
            "transliteration). 美術 (měishù) = fine arts."
        ),
        roots=["Chinese 美: 羊 (sheep) + 大 (big)"],
        cognates=["Japanese 美 (bi)", "Korean 미 (mi)"],
        semantic_shift=(
            "'big sheep / abundance' → beauty (aesthetic + ethical + "
            "auspicious)"
        ),
    ),
    EtymologyEntry(
        language="zh", lemma="好",
        origin_summary=(
            "Hǎo — good. The character 好 = 女 (woman) + 子 (child) — woman with "
            "child = good. The pairing of woman and child as the model of "
            "'good' reflects ancient social ideals. Modern Chinese hǎo is one "
            "of the most basic adjectives: 好的 (hǎo de, OK), 你好 (nǐhǎo, hello "
            "— lit. 'you good'). The third-tone hào means 'to like' — same "
            "character, different sense and tone."
        ),
        roots=["Chinese 好: 女 (woman) + 子 (child)"],
        cognates=["Japanese 好 (kō/sukimu)", "Korean 호 (ho)"],
        semantic_shift=(
            "'woman + child' → good; productive in greetings (你好) and basic "
            "vocabulary"
        ),
    ),
    EtymologyEntry(
        language="zh", lemma="愛",
        origin_summary=(
            "Ài — love. The character 愛 (traditional) contains 心 (heart) at "
            "center; the simplified 爱 removed the heart — a famously "
            "controversial simplification (critics say 'love without a "
            "heart'). Productive: 愛情 (àiqíng, romantic love), 愛人 (àirén, "
            "lover/spouse), 戀愛 (liàn'ài, dating/romantic love). The radical- "
            "removal in simplification was symbolically loaded."
        ),
        roots=[
            "Chinese 愛 (traditional, with 心 'heart' inside) → 爱 (simplified, no heart)",
        ],
        cognates=["Japanese 愛 (ai)", "Korean 애 (ae)"],
        semantic_shift=(
            "'heart-bearing love' → love (the heart removed in PRC "
            "simplification — symbolically resonant)"
        ),
    ),
    EtymologyEntry(
        language="zh", lemma="孔子",
        origin_summary=(
            "Kǒngzǐ = Master Kong = Confucius. 'Confucius' is the Latinized "
            "form coined by 17th-c. Jesuit missionaries (from Kǒng Fūzǐ, "
            "孔夫子). His real name was Kǒng Qiū (孔丘); Kǒngzǐ is the honorific "
            "'Master Kong.' The Latinization 'Confucius' has become the "
            "global standard, displacing his Chinese name in non-Chinese "
            "contexts. The Confucian tradition (儒家) has shaped East Asian "
            "civilization for ~2500 years."
        ),
        roots=[
            "Chinese 孔子 (Kǒngzǐ, Master Kong)",
            "Latinized as 'Confucius' by Jesuit missionaries",
        ],
        cognates=["Japanese 孔子 (Kōshi)", "Korean 공자 (Gongja)"],
        semantic_shift="Chinese honorific → Latinized 'Confucius' → global standard name",
    ),
    EtymologyEntry(
        language="zh", lemma="老子",
        origin_summary=(
            "Lǎozǐ — Master Lao, traditional author of the Tao Te Ching. The "
            "name literally means 'Old Master' (老 lǎo = old + 子 zǐ = master). "
            "His historicity is debated; he may be legendary. The Tao Te "
            "Ching (Daodejing 道德經, ~6th-4th c. BCE) is the foundational text "
            "of philosophical Daoism. 'Lao Tzu'/'Laozi'/'Lao-tse' are "
            "different romanizations of the same Chinese name."
        ),
        roots=["Chinese 老子 (Lǎozǐ, Old Master)"],
        semantic_shift=(
            "'Old Master' → traditional author of Tao Te Ching (historically "
            "uncertain)"
        ),
    ),
    EtymologyEntry(
        language="zh", lemma="儒",
        origin_summary=(
            "Rú — Confucian/scholar. The Confucian school is 儒家 (rújiā), "
            "Confucian scholars are 儒者 (rúzhě), Confucianism is 儒教 (rújiào). "
            "The character 儒 = 人 (person) + 需 (need) — possibly 'the person "
            "society needs.' The original meaning was 'scholar-priest' "
            "(someone who performed ritual/ceremonial functions in the Zhou "
            "dynasty); Confucius reformed this into the ethical-moral teacher "
            "tradition."
        ),
        roots=["Chinese 儒: 人 (person) + 需 (need)"],
        cognates=["Japanese 儒 (ju)", "Korean 유 (yu)"],
        semantic_shift=(
            "'scholar-priest' (Zhou ritual) → Confucian teacher → Confucian "
            "school name"
        ),
    ),
    EtymologyEntry(
        language="zh", lemma="佛",
        origin_summary=(
            "Fó — Buddha. Phonetic transcription of Sanskrit 'Buddha' via 佛陀 "
            "(Fótuó). The character was created (or re-purposed) for this "
            "Buddhist transmission ~1st century CE. From this transcription, "
            "all East Asian languages take their Buddha word: Japanese 仏 "
            "(butsu/hotoke), Korean 불 (bul), Vietnamese Phật. The Chinese "
            "character chosen for the phonetic transcription has the radical "
            "人 (person), reflecting the Buddhist concept of human "
            "enlightenment."
        ),
        roots=[
            "Sanskrit Buddha → Chinese 佛 (Fó, phonetic transcription with 'person' radical)",
        ],
        cognates=["Japanese 仏 (butsu)", "Korean 불 (bul)", "Vietnamese Phật"],
        semantic_shift=(
            "Sanskrit phonetic transcription → standard East Asian Buddha- "
            "word"
        ),
    ),
    EtymologyEntry(
        language="zh", lemma="夢",
        origin_summary=(
            "Mèng — dream. The character 夢 (traditional) shows a person in "
            "bed with eyes closed, seeing things — a genuine pictographic "
            "depiction of dreaming. Cao Xueqin's 紅樓夢 (Hónglóumèng, Dream of "
            "the Red Chamber, 18th c.) is one of the four great classical "
            "Chinese novels. Simplified to 梦. Zhuangzi's butterfly dream "
            "(莊周夢蝶) is one of the foundational Daoist parables."
        ),
        roots=["Chinese 夢: pictogram of person in bed"],
        cognates=["Japanese 夢 (yume)", "Korean 몽 (mong)"],
        semantic_shift=(
            "Pictographic dreaming → dream → philosophical concept "
            "(Zhuangzi's butterfly dream)"
        ),
    ),
    EtymologyEntry(
        language="zh", lemma="命",
        origin_summary=(
            "Mìng — life, fate, command. Three meanings unified in one "
            "character: your life, your fate, the command (from heaven) that "
            "gave it. 命運 (mìngyùn) = fate/destiny; 革命 (gémìng) = revolution = "
            "'changing the mandate'; 性命 (xìngmìng) = life. The Mandate of "
            "Heaven (天命 tiānmìng) draws on this triple sense — heaven's "
            "command-fate-life-grant."
        ),
        roots=["Chinese 命 = 口 (mouth) + 令 (order)"],
        cognates=["Japanese 命 (mei/inochi)", "Korean 명 (myeong)"],
        semantic_shift=(
            "'spoken command' → fate (what is commanded) → life (what is "
            "granted by command); the Mandate of Heaven"
        ),
    ),
    EtymologyEntry(
        language="zh", lemma="夫子",
        origin_summary=(
            "Fūzǐ — master/teacher (honorific). Confucius is 'Kǒng Fūzǐ' "
            "(孔夫子); 'Confucius' is the Latinization. The honorific 夫子 (fūzǐ) "
            "was used for venerated teachers; the Jesuit Latinization "
            "combined it with his surname. Modern Chinese reserves fūzǐ for "
            "archaic/ironic register. The semantic core: 'great man' (夫 fū) + "
            "'son/master' (子 zǐ) — the pattern of master-naming common in "
            "classical Chinese."
        ),
        roots=["Chinese 夫子: 夫 (great man) + 子 (master)"],
        semantic_shift=(
            "Honorific 'great-man-master' → archaic title for venerated "
            "teachers; the source of Latinized 'Confucius'"
        ),
    ),
    EtymologyEntry(
        language="zh", lemma="皇帝",
        origin_summary=(
            "Huángdì — emperor. The title was created by Qin Shi Huang in 221 "
            "BCE — combining 皇 (huáng, august) and 帝 (dì, mythological "
            "supreme ruler). Replaced the older 'wáng' (王, king). The Yellow "
            "Emperor (黄帝 Huáng Dì, the legendary founder) and First Emperor "
            "of Qin (秦始皇帝) marked the title. Used continuously until 1912 "
            "with the abdication of Puyi."
        ),
        roots=["Chinese 皇 (huáng, august) + 帝 (dì, supreme ruler)"],
        cognates=["Japanese 皇帝 (kōtei)", "Korean 황제 (hwangje)"],
        semantic_shift="Title created by Qin Shi Huang in 221 BCE; used until 1912",
    ),
    EtymologyEntry(
        language="zh", lemma="京",
        origin_summary=(
            "Jīng — capital. Beijing 北京 ('Northern capital') and Nanjing 南京 "
            "('Southern capital') and Tokyo 東京 ('Eastern capital' — Japanese "
            "tōkyō, same characters) all use jīng for capital. The character "
            "京 originally depicted a tall building or ceremonial mound. "
            "Capitals as pinnacles of the political-cultural order. The "
            "Korean reading is gyeong: Pyongyang's older name was 平壤 "
            "Pyongyang (no jīng); Seoul has historic name Hanseong."
        ),
        roots=["Chinese 京: pictogram of tall ceremonial building"],
        cognates=["Japanese 京 (kyō, as in Tōkyō, Kyōto)", "Korean 경 (gyeong)"],
        semantic_shift="'tall building' → capital → element in capital city names",
    ),
    EtymologyEntry(
        language="zh", lemma="酒",
        origin_summary=(
            "Jiǔ — alcohol/liquor (general term for fermented or distilled "
            "drinks). The character 酒 = 氵 (water) + 酉 (a fermenting jar — "
            "12th of the 12 zodiac branches, also represents 'rooster'). 白酒 "
            "(báijiǔ) = white liquor (the strong distilled spirit, 30-60% "
            "alcohol); 黃酒 (huángjiǔ) = yellow rice wine; 葡萄酒 (pútáojiǔ) = "
            "grape wine. Jiǔ has been central to Chinese ritual, poetry, and "
            "culture for millennia."
        ),
        roots=["Chinese 酒: 氵 (water) + 酉 (fermenting jar)"],
        cognates=["Japanese 酒 (sake/shu)", "Korean 주 (ju)"],
        semantic_shift=(
            "'fermenting jar water' → alcohol; central in ritual, poetry, "
            "social culture"
        ),
    ),
    EtymologyEntry(
        language="zh", lemma="字典",
        origin_summary=(
            "Zìdiǎn — dictionary. From 字 (zì, character) + 典 (diǎn, "
            "classic/canonical text). Chinese dictionaries are character- "
            "organized, not word-organized — reflecting the centrality of zì. "
            "The Kangxi Dictionary (康熙字典, 1716) became the canonical "
            "reference, defining 47,035 characters. Modern Chinese "
            "dictionaries continue this tradition; the search-by-radical "
            "method derives from Kangxi."
        ),
        roots=["Chinese 字 (zì, character) + 典 (diǎn, classic)"],
        cognates=["Japanese 字典 (jiten)", "Korean 자전 (jajeon)"],
        semantic_shift=(
            "'character classic' → dictionary; reflects Chinese character- "
            "organization of lexicography"
        ),
    ),
    EtymologyEntry(
        language="zh", lemma="風水",
        origin_summary=(
            "Fēngshuǐ — feng shui, geomancy. From 風 (fēng, wind) + 水 (shuǐ, "
            "water). The Chinese geomantic art of arranging spaces to "
            "harmonize with cosmic flows of qi. Originated in Han-dynasty "
            "cosmology; refined over centuries. Eight Trigrams compass "
            "(luopan 羅盤) is the practitioner's instrument. English 'feng "
            "shui' has globalized via Chinese diaspora, especially Hong Kong "
            "real estate practice."
        ),
        roots=["Chinese 風 (fēng, wind) + 水 (shuǐ, water)"],
        cognates=[
            "Japanese 風水 (fūsui)",
            "Korean 풍수 (pungsu)",
            "English 'feng shui' (loanword)",
        ],
        semantic_shift="'wind and water' → geomantic art; globalized concept",
    ),
    EtymologyEntry(
        language="zh", lemma="陰陽",
        origin_summary=(
            "Yīn-yáng — the cosmological dualism. Already covered with "
            "separate entries; included for completeness. The yīn-yáng "
            "concept appears in Chinese cosmology as early as the I Ching "
            "(Yijing 易經, ~1000 BCE). The Taiji symbol (☯, the swirling yin- "
            "yang circle) is a late visualization (Song dynasty). Yin-yang "
            "reasoning structures Chinese medicine, divination, martial arts, "
            "and aesthetics."
        ),
        roots=["Chinese 陰陽 (yīn-yáng)"],
        cognates=["Japanese 陰陽 (in'yō)", "Korean 음양 (eumyang)"],
        semantic_shift="Already covered; the foundational dualism of Chinese cosmology",
    ),
    EtymologyEntry(
        language="zh", lemma="易",
        origin_summary=(
            "Yì — change, easy. Same character covers two meanings: "
            "'change/transformation' (the principle of the I Ching) and "
            "'easy' (modern adjective). The Yijing (易經, the Book of Changes) "
            "is one of the oldest Chinese texts (~1000 BCE), foundational to "
            "all later Chinese philosophy. The 64 hexagrams of the I Ching "
            "are the divinatory/cosmological structure of constant "
            "transformation."
        ),
        roots=["Chinese 易: pictogram (debated origin)"],
        cognates=["Japanese 易 (eki/yasashii)", "Korean 역 (yeok)"],
        semantic_shift=(
            "'change/easy' → I Ching (Book of Changes) → both senses "
            "preserved in modern Chinese"
        ),
    ),
    EtymologyEntry(
        language="zh", lemma="緣",
        origin_summary=(
            "Yuán — predestined connection, karma, edge. Buddhist concept: "
            "the conditions/circumstances that bring people or things "
            "together. 'Yuánfèn' (緣分) is 'fated connection' — used to "
            "describe meaningful coincidences, romantic chemistry, or chance "
            "encounters that feel meant-to-be. 因緣 (yīn-yuán) is the Buddhist "
            "'cause-condition' framework. English 'karma' is a related but "
            "distinct concept."
        ),
        roots=[
            "Chinese 緣: 糸 (silk thread) + 彖 (phonetic) — connecting thread",
        ],
        cognates=["Japanese 縁 (en)", "Korean 연 (yeon)"],
        semantic_shift=(
            "'connecting thread' → Buddhist conditional connection → "
            "fated/meaningful encounter"
        ),
    ),
    EtymologyEntry(
        language="zh", lemma="面子",
        origin_summary=(
            "Miànzi — face, social reputation. The Chinese cultural concept "
            "of 'face' (also covered as 'lian' 臉) — losing face (丢面子 diū "
            "miànzi) and giving face (給面子 gěi miànzi) are central social "
            "transactions. Anthropologist Hsien Chin Hu's 1944 paper 'The "
            "Chinese Concepts of Face' introduced the analysis to Western "
            "sociology. 'Face' shapes Chinese business, politics, and social "
            "interaction."
        ),
        roots=["Chinese 面 (miàn, face) + 子 (zǐ, suffix)"],
        cognates=["Japanese 面子 (mentsu)", "Korean 면자 (myeonja)"],
        semantic_shift=(
            "'face' → social reputation/honor; foundational concept in "
            "Chinese social analysis"
        ),
    ),
    EtymologyEntry(
        language="zh", lemma="關係",
        origin_summary=(
            "Guānxi — relationship, connections, networks. Chinese cultural- "
            "economic concept of personal networks as the medium of business, "
            "political, and social transactions. To 'have guānxi' is to have "
            "access; to 'pull guānxi' (拉關係 lā guānxi) is to use connections "
            "to accomplish things. Critical element of Chinese business "
            "culture and a recurring theme in scholarship on Chinese society."
        ),
        roots=["Chinese 關 (guān, gate/relation) + 係 (xì, tie)"],
        cognates=["Japanese 関係 (kankei)", "Korean 관계 (gwangye)"],
        semantic_shift=(
            "'gate-tie' → relationship/connection → cultural-economic concept "
            "of personal networks"
        ),
    ),
    EtymologyEntry(
        language="zh", lemma="客家",
        origin_summary=(
            "Kèjiā — Hakka. The character 客家 = 客 (kè, guest) + 家 (jiā, "
            "household) — 'guest households.' The Hakka are a Han Chinese "
            "subgroup with distinct dialect and customs, descendants of "
            "migrants who moved south from northern China over multiple "
            "historical waves. Their walled circular Hakka houses (土樓 tǔlóu) "
            "are UNESCO heritage. The 'guest' name reflects their later "
            "arrival in southern regions."
        ),
        roots=["Chinese 客 (guest) + 家 (household)"],
        semantic_shift=(
            "'guest households' → Hakka people (the migrant Han subgroup); "
            "UNESCO heritage architecture"
        ),
    ),
    EtymologyEntry(
        language="zh", lemma="工夫",
        origin_summary=(
            "Gōngfū — skill acquired through long practice; kung fu (martial "
            "arts in English). Etymologically 'work-effort' (工 work + 夫 "
            "person), but the deeper meaning is 'time-and-skill cultivation' "
            "— gōngfū is the result of patient labor. The English 'kung fu' "
            "(Cantonese transliteration) narrowed to martial arts; the "
            "Chinese gōngfū broadly applies (a tea master has tea gōngfū, a "
            "calligrapher has brush gōngfū)."
        ),
        roots=["Chinese 工 (gōng, work) + 夫 (fū, person/effort)"],
        cognates=[
            "English 'kung fu' (Cantonese transliteration, narrowed to martial arts)",
        ],
        semantic_shift=(
            "'work-effort' → cultivated skill in any domain → English 'kung "
            "fu' (narrowed to martial arts)"
        ),
    ),
    EtymologyEntry(
        language="zh", lemma="節",
        origin_summary=(
            "Jié — joint, knot, season, festival. Multivalent: bamboo joint "
            "(節), bone joint, articulation point of a season change (節氣 jiéqì "
            "= solar term), festival (節日 jiérì), moral integrity (節操 jiécāo). "
            "The connecting metaphor: a 'point of articulation/segmentation.' "
            "The 24 solar terms (二十四節氣) traditionally divide the agricultural "
            "year. The character 節 (traditional) shows a bamboo radical "
            "above; simplified 节."
        ),
        roots=[
            "Chinese 節: 竹 (bamboo) radical above (bamboo joint as the prototype)",
        ],
        cognates=["Japanese 節 (setsu)", "Korean 절 (jeol)"],
        semantic_shift=(
            "'bamboo joint' → joint, articulation, season, festival; "
            "productive in many compounds"
        ),
    ),
]


#: Default store — import and call .get() directly in most code paths.
DEFAULT_STORE: EtymologyStore = EtymologyStore(_CURATED)
