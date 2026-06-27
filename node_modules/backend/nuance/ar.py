"""Arabic nuance extractor — definite article, negation markers, root-pattern note."""
from __future__ import annotations

import re
from typing import Any

from backend.schemas.parse import CandidateObject, RelationHint

# Strip tashkeel (Arabic short-vowel diacriticals) for surface matching
_TASHKEEL_RE = re.compile(
    r"[ً-ٟؐ-ؚۖ-ۜ۟-۪ۤۧۨ-ۭ]"
)


def _strip(s: str) -> str:
    return _TASHKEEL_RE.sub("", s)


_NEGATION: dict[str, tuple[str, str]] = {
    "لا": (
        "negation_la",
        "«لا» negates present/future verbs and makes categorical negations: "
        "لا أعرف (I don't know). Also used for nominal negation: لا إله إلا الله.",
    ),
    "لم": (
        "negation_lam",
        "«لم» negates past actions and requires the jussive (مجزوم) verb form: "
        "لم يذهب (he didn't go). It shifts present-tense morphology to past meaning.",
    ),
    "لن": (
        "negation_lan",
        "«لن» negates future actions using the subjunctive (منصوب) mood: "
        "لن يذهب (he will not go). It is the emphatic future negation particle.",
    ),
    "ما": (
        "negation_ma",
        "«ما» negates past verbs (Classical/literary) or nominal predicates. "
        "In MSA it also functions as 'whatever/that which' (relative pronoun).",
    ),
    "ليس": (
        "negation_laysa",
        "«ليس» is a defective verb meaning 'to not be'. It negates nominal sentences "
        "in the present tense and governs accusative on its predicate: "
        "ليسَ هذا صحيحًا (This is not correct).",
    ),
}

_DEF_ARTICLE_RE = re.compile(r"^ال")

# Arabic verbs with fixed prepositional government (the noun after the
# preposition takes genitive). Key combines verb root + preposition.
_VERBAL_GOV: dict[str, tuple[str, str]] = {
    "اعتمد على":  ("ala+genitive", "«اعتمد على» (i'tamada 'alā, to rely on) takes 'alā + genitive: اعتمد على صديقه (he relied on his friend)"),
    "بحث عن":     ("an+genitive",  "«بحث عن» (baḥatha 'an, to search for) takes 'an + genitive: يبحث عن عمل (he is looking for work)"),
    "آمن بـ":     ("bi+genitive",  "«آمن بـ» (āmana bi-, to believe in) takes bi- + genitive: آمن بالله (he believed in God)"),
    "ذهب إلى":    ("ila+genitive", "«ذهب إلى» (dhahaba ilā, to go to) takes ilā + genitive: ذهب إلى المدرسة (he went to school)"),

    # ── AR additions (gen_verbal_government.py) ──
    'تكلم عن': ('an+genitive', "«تكلم عن» (takallama 'an, to speak about) takes 'an + genitive: تكلم عن مشاكله (he spoke about his problems)"),
    'سأل عن': ('an+genitive', "«سأل عن» (sa'ala 'an, to ask about) takes 'an + genitive: سألت عنك (I asked about you). Distinct from سأل + acc (to ask someone)"),
    'تخلى عن': ('an+genitive', "«تخلى عن» (takhallā 'an, to abandon) takes 'an + genitive: تخلى عن أصدقائه (he abandoned his friends)"),
    'عبر عن': ('an+genitive', "«عبر عن» ('abbara 'an, to express) takes 'an + genitive: عبر عن مشاعره (he expressed his feelings)"),
    'اعتذر عن': ('an+genitive', "«اعتذر عن» (i'tadhara 'an, to apologize for) takes 'an + genitive: اعتذر عن خطئه (he apologized for his mistake)"),
    'توقف عن': ('an+genitive', "«توقف عن» (tawaqqafa 'an, to stop from) takes 'an + genitive: توقف عن التدخين (he stopped smoking)"),
    'ابتعد عن': ('an+genitive', "«ابتعد عن» (ibta'ada 'an, to move away from) takes 'an + genitive: ابتعد عن الخطر (he moved away from danger)"),
    'دافع عن': ('an+genitive', "«دافع عن» (dāfa'a 'an, to defend) takes 'an + genitive: دافع عن وطنه (he defended his homeland)"),
    'أجاب على': ('ala+genitive', "«أجاب على» (ajāba 'alā, to answer) takes 'alā + genitive: أجاب على السؤال (he answered the question). Also أجاب عن with 'an"),
    'وافق على': ('ala+genitive', "«وافق على» (wāfaqa 'alā, to agree to) takes 'alā + genitive: وافق على الاقتراح (he agreed to the proposal)"),
    'اطلع على': ('ala+genitive', "«اطلع على» (iṭṭala'a 'alā, to look at, get acquainted with) takes 'alā + genitive: اطلع على التقرير (he reviewed the report)"),
    'حافظ على': ('ala+genitive', "«حافظ على» (ḥāfaẓa 'alā, to preserve, maintain) takes 'alā + genitive: حافظ على صحته (he maintained his health)"),
    'ضحك على': ('ala+genitive', "«ضحك على» (ḍaḥika 'alā, to laugh at, deceive) takes 'alā + genitive: ضحك علي (he tricked me / he laughed at me)"),
    'عثر على': ('ala+genitive', "«عثر على» ('athara 'alā, to find, come across) takes 'alā + genitive: عثرت على المفاتيح (I found the keys)"),
    'حصل على': ('ala+genitive', "«حصل على» (ḥaṣala 'alā, to obtain) takes 'alā + genitive: حصل على الجائزة (he obtained the prize)"),
    'حكم على': ('ala+genitive', "«حكم على» (ḥakama 'alā, to judge, sentence) takes 'alā + genitive: حكم عليه بالسجن (he sentenced him to prison)"),
    'خاف من': ('min+genitive', "«خاف من» (khāfa min, to fear) takes min + genitive: خاف من الكلب (he was afraid of the dog)"),
    'تعجب من': ('min+genitive', "«تعجب من» (ta'ajjaba min, to wonder at) takes min + genitive: تعجب من جرأته (he wondered at his audacity)"),
    'استفاد من': ('min+genitive', "«استفاد من» (istafāda min, to benefit from) takes min + genitive: استفدت من الدرس (I benefited from the lesson)"),
    'خرج من': ('min+genitive', "«خرج من» (kharaja min, to exit from) takes min + genitive: خرج من البيت (he left the house)"),
    'اشترى من': ('min+genitive', "«اشترى من» (ishtarā min, to buy from) takes min + genitive: اشترى من السوق (he bought from the market)"),
    'غضب من': ('min+genitive', "«غضب من» (ghaḍiba min, to be angry at) takes min + genitive: غضب من الخادم (he was angry at the servant)"),
    'ضحك من': ('min+genitive', "«ضحك من» (ḍaḥika min, to laugh at) takes min + genitive: ضحك من النكتة (he laughed at the joke). Compare ضحك على (to laugh AT mockingly)"),
    'اقترب من': ('min+genitive', "«اقترب من» (iqtaraba min, to approach) takes min + genitive: اقترب من الباب (he approached the door)"),
    'تعلم من': ('min+genitive', "«تعلم من» (ta'allama min, to learn from) takes min + genitive: تعلمت من أبي (I learned from my father)"),
    'شعر بـ': ('bi+genitive', "«شعر بـ» (sha'ara bi-, to feel) takes bi- + genitive: شعر بالخوف (he felt fear)"),
    'اعتنى بـ': ('bi+genitive', "«اعتنى بـ» ('itanā bi-, to take care of) takes bi- + genitive: تعتني بأطفالها (she takes care of her children)"),
    'رحب بـ': ('bi+genitive', "«رحب بـ» (raḥḥaba bi-, to welcome) takes bi- + genitive: رحب بالضيوف (he welcomed the guests)"),
    'فرح بـ': ('bi+genitive', "«فرح بـ» (fariḥa bi-, to rejoice at) takes bi- + genitive: فرح بنجاحه (he was happy about his success)"),
    'استمتع بـ': ('bi+genitive', "«استمتع بـ» (istamta'a bi-, to enjoy) takes bi- + genitive: استمتع بالعطلة (he enjoyed the vacation)"),
    'فاز بـ': ('bi+genitive', "«فاز بـ» (fāza bi-, to win) takes bi- + genitive: فاز بالميدالية (he won the medal)"),
    'اعترف بـ': ('bi+genitive', "«اعترف بـ» (i'tarafa bi-, to admit, acknowledge) takes bi- + genitive: اعترف بخطئه (he admitted his mistake)"),
    'اهتم بـ': ('bi+genitive', "«اهتم بـ» (ihtamma bi-, to be concerned with) takes bi- + genitive: يهتم بالسياسة (he is interested in politics)"),
    'اتصل بـ': ('bi+genitive', "«اتصل بـ» (ittaṣala bi-, to contact) takes bi- + genitive: اتصلت بصديقي (I contacted my friend)"),
    'التقى بـ': ('bi+genitive', "«التقى بـ» (iltaqā bi-, to meet) takes bi- + genitive: التقيت بالمدير (I met the director). Also iltaqā ma'a"),
    'وعد بـ': ('bi+genitive', "«وعد بـ» (wa'ada bi-, to promise) takes bi- + genitive: وعد بالحضور (he promised to come)"),
    'ذكر بـ': ('bi+genitive', "«ذكر بـ» (dhakkara bi-, to remind of) takes acc of person + bi- + genitive: ذكرني بالموعد (he reminded me of the appointment)"),
    'بدأ بـ': ('bi+genitive', "«بدأ بـ» (bada'a bi-, to begin with) takes bi- + genitive: بدأ بالقراءة (he began with reading)"),
    'أمسك بـ': ('bi+genitive', "«أمسك بـ» (amsaka bi-, to grasp, seize) takes bi- + genitive: أمسك بيدي (he held my hand)"),
    'نظر إلى': ('ila+genitive', "«نظر إلى» (naẓara ilā, to look at) takes ilā + genitive: نظرت إليه (I looked at him)"),
    'استمع إلى': ('ila+genitive', "«استمع إلى» (istama'a ilā, to listen to) takes ilā + genitive: استمع إلى الموسيقى (he listened to the music)"),
    'بعث إلى': ('ila+genitive', "«بعث إلى» (ba'atha ilā, to send to) takes ilā + genitive: بعث رسالة إلى أمه (he sent a letter to his mother)"),
    'أشار إلى': ('ila+genitive', "«أشار إلى» (ashāra ilā, to point at, refer to) takes ilā + genitive: أشار إلى الباب (he pointed to the door)"),
    'وصل إلى': ('ila+genitive', "«وصل إلى» (waṣala ilā, to arrive at) takes ilā + genitive: وصل إلى البيت (he arrived home)"),
    'التفت إلى': ('ila+genitive', "«التفت إلى» (iltafata ilā, to turn toward, attend to) takes ilā + genitive: التفت إلى الضيف (he turned to the guest)"),
    'اشتاق إلى': ('ila+genitive', "«اشتاق إلى» (ishtāqa ilā, to long for) takes ilā + genitive: اشتقت إلى وطني (I longed for my homeland)"),
    'احتاج إلى': ('ila+genitive', "«احتاج إلى» (iḥtāja ilā, to need) takes ilā + genitive: أحتاج إلى مساعدة (I need help)"),
    'بحث في': ('fi+genitive', "«بحث في» (baḥatha fī, to research, investigate) takes fī + genitive: بحث في القضية (he investigated the case). Distinct from بحث عن (to search for)"),
    'فكر في': ('fi+genitive', "«فكر في» (fakkara fī, to think about) takes fī + genitive: فكرت في الموضوع (I thought about the topic)"),
    'رغب في': ('fi+genitive', "«رغب في» (raghiba fī, to desire) takes fī + genitive: رغب في الزواج (he desired to marry)"),
    'شارك في': ('fi+genitive', "«شارك في» (shāraka fī, to participate in) takes fī + genitive: شارك في المؤتمر (he participated in the conference)"),
    'تأمل في': ('fi+genitive', "«تأمل في» (ta'ammala fī, to contemplate) takes fī + genitive: تأمل في الحياة (he contemplated life)"),
    'نجح في': ('fi+genitive', "«نجح في» (najaḥa fī, to succeed in) takes fī + genitive: نجح في الامتحان (he passed the exam)"),
    'فشل في': ('fi+genitive', "«فشل في» (fashila fī, to fail in) takes fī + genitive: فشل في المحاولة (he failed in the attempt). Mirror of najaḥa"),
    'تخصص في': ('fi+genitive', "«تخصص في» (takhaṣṣaṣa fī, to specialize in) takes fī + genitive: يتخصص في الطب (he specializes in medicine)"),
    'تكلم مع': ("ma'a+genitive", "«تكلم مع» (takallama ma'a, to talk with) takes ma'a + genitive: تكلم مع المدير (he spoke with the manager). Distinct from takallama 'an (about)"),
    'تحدث مع': ("ma'a+genitive", "«تحدث مع» (taḥaddatha ma'a, to converse with) takes ma'a + genitive: تحدثت مع جدي (I conversed with my grandfather)"),
    'تعاون مع': ("ma'a+genitive", "«تعاون مع» (ta'āwana ma'a, to cooperate with) takes ma'a + genitive: تعاون مع زملائه (he cooperated with his colleagues)"),
    'اختلف مع': ("ma'a+genitive", "«اختلف مع» (ikhtalafa ma'a, to disagree with) takes ma'a + genitive: اختلف مع رأيه (he disagreed with his opinion)"),
    'اتفق مع': ("ma'a+genitive", "«اتفق مع» (ittafaqa ma'a, to agree with) takes ma'a + genitive: اتفق مع زميله (he agreed with his colleague). Mirror of ikhtalafa ma'a"),
    'كتب لـ': ('li+genitive', "«كتب لـ» (kataba li-, to write to/for) takes li- + genitive: كتب رسالة لأبيه (he wrote a letter to his father)"),
    'غفر لـ': ('li+genitive', "«غفر لـ» (ghafara li-, to forgive someone) takes li- + genitive of person: غفر لي (he forgave me). Religious-register frequent"),
    'دعا لـ': ('li+genitive', "«دعا لـ» (da'ā li-, to pray for, invite) takes li- + genitive: دعا لأخيه بالصحة (he prayed for his brother's health). Compare دعا إلى (to call to)"),
    'أعطى': ('double+accusative', "«أعطى» (a'ṭā, to give) takes double accusative — recipient + thing given: أعطيته كتاباً (I gave him a book)"),
    'علم': ('double+accusative', "«علم» ('allama, to teach) takes double accusative: علمته العربية (I taught him Arabic). Form II — causative of 'alima (to know)"),
    'منح': ('double+accusative', "«منح» (manaḥa, to grant) takes double accusative: منحه جائزة (he granted him a prize). Formal register"),
    'كسا': ('double+accusative', "«كسا» (kasā, to clothe) takes double accusative: كساه ثوباً (he clothed him with a garment). Person clothed + garment both in acc"),
    'ظن': ('double+accusative', "«ظن» (ẓanna, to think, suppose) governs double accusative as a 'verb of the heart': ظنه صديقاً (he thought him a friend). The 'افعال القلوب' (verbs of the heart) take double acc"),
}


def _tok_text(tok: Any) -> str:
    return tok.text if hasattr(tok, "text") else str(tok)


def _lemma(c: CandidateObject) -> str:
    return c.lesson_data.get("lemma", c.canonical_form)


class ArabicNuanceExtractor:
    language = "ar"

    def extract_nuance(
        self,
        sentence: str,
        tokens: list[Any],
        candidates: list[CandidateObject],
        language: str,
    ) -> list[CandidateObject]:
        out: list[CandidateObject] = []
        seen: set[str] = set()
        out.extend(self._phrase_families(tokens))
        out.extend(self._definite_article(tokens, seen))
        out.extend(self._negation_markers(tokens, seen))
        out.extend(self._verbal_government(candidates, seen))
        out.extend(self._root_pattern(candidates, seen))
        out.extend(self._verb_form(candidates, seen))
        out.extend(self._proclitic(candidates, seen))
        return out

    def _verbal_government(
        self, candidates: list[CandidateObject], seen: set[str]
    ) -> list[CandidateObject]:
        out = []
        for c in candidates:
            if c.type not in ("vocabulary", "conjugation"):
                continue
            lemma = _lemma(c)
            if lemma not in _VERBAL_GOV:
                continue
            required_case, example = _VERBAL_GOV[lemma]
            cf = f"nuance:ar:verbal_government:{lemma}"
            if cf in seen:
                continue
            seen.add(cf)
            out.append(CandidateObject(
                canonical_form=cf,
                surface_form=c.surface_form,
                type="nuance",
                label=c.label,
                lesson_data={
                    "nuance_type": "verbal_government",
                    "explanation": (
                        f"{example}. "
                        "Many Arabic verbs take a fixed preposition that selects the meaning — "
                        "the noun after the preposition is in the genitive (مجرور). "
                        f"Required structure: {required_case}."
                    ),
                    "register": "neutral",
                    "learner_level": "B1",
                    "source": "heuristic",
                    "lemma": lemma,
                    "required_case": required_case,
                },
                confidence=0.85,
                relation_hints=[RelationHint(
                    relation_type="nuance_of",
                    target_canonical_form=lemma,
                    target_type="vocabulary",
                )],
            ))
        return out

    def _phrase_families(self, tokens: list[Any]) -> list[CandidateObject]:
        from backend.dictionary.phrase_families import match_phrase_families
        return match_phrase_families([_tok_text(t) for t in tokens], self.language)

    def _definite_article(
        self, tokens: list[Any], seen: set[str]
    ) -> list[CandidateObject]:
        cf = "nuance:ar:definite_article"
        for tok in tokens:
            surface = _tok_text(tok)
            if not _DEF_ARTICLE_RE.match(_strip(surface)):
                continue
            if cf in seen:
                break
            seen.add(cf)
            return [CandidateObject(
                canonical_form=cf,
                surface_form=surface,
                type="nuance",
                label=surface,
                lesson_data={
                    "nuance_type": "definite_article",
                    "explanation": (
                        "«ال» (al-) is the Arabic definite article, a prefix clitic. "
                        "It assimilates to following sun letters (حروف شمسية): "
                        "الشمس → ash-shams (not *al-shams). "
                        "Moon letters (حروف قمرية) do not trigger assimilation: "
                        "القمر → al-qamar. The article is invariable for gender and case."
                    ),
                    "register": "neutral",
                    "learner_level": "A1",
                    "source": "heuristic",
                },
                confidence=0.90,
            )]
        return []

    def _negation_markers(
        self, tokens: list[Any], seen: set[str]
    ) -> list[CandidateObject]:
        out = []
        for tok in tokens:
            surface = _tok_text(tok)
            stripped = _strip(surface)
            if stripped not in _NEGATION:
                continue
            nuance_type, explanation = _NEGATION[stripped]
            cf = f"nuance:ar:{nuance_type}"
            if cf in seen:
                continue
            seen.add(cf)
            out.append(CandidateObject(
                canonical_form=cf,
                surface_form=surface,
                type="nuance",
                label=surface,
                lesson_data={
                    "nuance_type": nuance_type,
                    "explanation": explanation,
                    "register": "neutral",
                    "learner_level": "A2",
                    "source": "heuristic",
                    "particle": stripped,
                },
                confidence=0.85,
            ))
        return out

    def _verb_form(
        self, candidates: list[CandidateObject], seen: set[str]
    ) -> list[CandidateObject]:
        """Emit aspect nuance when CAMeL Tools provides aspect data."""
        _ASPECT_NOTES: dict[str, tuple[str, str]] = {
            "p": (
                "perfective_aspect",
                "Perfective aspect (الماضي) indicates a completed action. "
                "In Arabic the root-and-pattern system encodes aspect directly: "
                "فَعَلَ (fa'ala) is the citation form for perfective active. "
                "The perfective stem is also used in conditional clauses.",
            ),
            "i": (
                "imperfective_aspect",
                "Imperfective aspect (المضارع) indicates an ongoing or incomplete "
                "action. The imperfective stem uses person/gender/number prefixes "
                "(ي-، ت-، ن-، أ-) and suffixes to build the full paradigm.",
            ),
            "c": (
                "imperative_mood",
                "Imperative (الأمر) is used for direct commands. It is derived from "
                "the jussive (مجزوم) stem, typically by removing the imperfective "
                "prefix and adjusting the initial vowel.",
            ),
        }
        out = []
        for c in candidates:
            aspect = c.lesson_data.get("aspect", "")
            if not aspect or aspect not in _ASPECT_NOTES:
                continue
            nuance_type, explanation = _ASPECT_NOTES[aspect]
            cf = f"nuance:ar:{nuance_type}"
            if cf in seen:
                continue
            seen.add(cf)
            out.append(CandidateObject(
                canonical_form=cf,
                surface_form=c.surface_form,
                type="nuance",
                label=c.label,
                lesson_data={
                    "nuance_type": nuance_type,
                    "explanation": explanation,
                    "register": "neutral",
                    "learner_level": "B1",
                    "source": "plugin",
                    "aspect": aspect,
                },
                confidence=0.80,
                relation_hints=[RelationHint(
                    relation_type="nuance_of",
                    target_canonical_form=c.canonical_form,
                    target_type=c.type,
                )],
            ))
        return out

    def _proclitic(
        self, candidates: list[CandidateObject], seen: set[str]
    ) -> list[CandidateObject]:
        """Emit proclitic nuance when CAMeL Tools provides prc1/prc2 data."""
        _CLITIC_NOTES: dict[str, tuple[str, str]] = {
            "bi+": (
                "proclitic_bi",
                "«بِ» (bi-) is a prepositional proclitic meaning 'in', 'with', or 'by'. "
                "It attaches to the following word without a space: "
                "بِالبَيتِ (in the house), بِقَلَمٍ (with a pen).",
            ),
            "li+": (
                "proclitic_li",
                "«لِ» (li-) is a prepositional proclitic meaning 'for', 'to', or 'of'. "
                "It attaches to the following word: لِلطَّالِبِ (for the student).",
            ),
            "ka+": (
                "proclitic_ka",
                "«كَ» (ka-) is a prepositional proclitic meaning 'like' or 'as'. "
                "It attaches to the following word: كَالأَسَدِ (like a lion).",
            ),
            "wa+": (
                "proclitic_wa",
                "«وَ» (wa-) is the conjunction 'and' as a proclitic. "
                "It attaches to the following word: وَالبَيتُ (and the house). "
                "It is among the most frequent words in Arabic text.",
            ),
            "fa+": (
                "proclitic_fa",
                "«فَ» (fa-) is a conjunction proclitic meaning 'so', 'then', or 'and then'. "
                "It marks logical consequence or narrative sequence: فَكَتَبَ (and so he wrote).",
            ),
        }
        out = []
        for c in candidates:
            for field in ("prc1", "prc2"):
                clitic = c.lesson_data.get(field, "")
                if not clitic or clitic not in _CLITIC_NOTES:
                    continue
                nuance_type, explanation = _CLITIC_NOTES[clitic]
                cf = f"nuance:ar:{nuance_type}"
                if cf in seen:
                    continue
                seen.add(cf)
                out.append(CandidateObject(
                    canonical_form=cf,
                    surface_form=c.surface_form,
                    type="nuance",
                    label=c.label,
                    lesson_data={
                        "nuance_type": nuance_type,
                        "explanation": explanation,
                        "register": "neutral",
                        "learner_level": "A2",
                        "source": "plugin",
                        "clitic": clitic,
                    },
                    confidence=0.75,
                ))
        return out

    def _root_pattern(
        self, candidates: list[CandidateObject], seen: set[str]
    ) -> list[CandidateObject]:
        """Fire when a candidate already carries root metadata (e.g. from ArabicAdapter)."""
        out = []
        for c in candidates:
            root = c.lesson_data.get("root")
            if not root:
                continue
            form = c.lesson_data.get("form") or c.lesson_data.get("pattern")
            cf = f"nuance:ar:root_pattern:{root}"
            if cf in seen:
                continue
            seen.add(cf)
            out.append(CandidateObject(
                canonical_form=cf,
                surface_form=c.surface_form,
                type="nuance",
                label=c.label,
                lesson_data={
                    "nuance_type": "root_pattern",
                    "explanation": (
                        f"Arabic root «{root}» participates in the consonantal root-and-pattern "
                        "system. Words are built by inserting a root (usually 3 consonants) into "
                        "a pattern (وزن wazn): فعل (verb), فاعل (agent), مفعول (object/result). "
                        + (f"This word follows pattern «{form}»." if form else "")
                    ),
                    "register": "neutral",
                    "learner_level": "B2",
                    "source": "plugin",
                    "root": root,
                    "form": form,
                },
                confidence=0.80,
                relation_hints=[RelationHint(
                    relation_type="nuance_of",
                    target_canonical_form=c.canonical_form,
                    target_type=c.type,
                )],
            ))
        return out
