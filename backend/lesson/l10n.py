"""Static L1-language templates for lesson explanation prose.

Strategy
────────
Static string templates keyed by (template_key, l1_code).  No external
translation API: lesson explanations are short, parameterized, and must be
deterministic and zero-latency.  Adding a new L1 language means adding rows
to _TEMPLATES and _POS_LABELS; untranslated keys fall back to English so
partial coverage is always safe.

Usage
─────
    from backend.lesson import l10n

    pos = l10n.pos_label("noun", "es")          # "un sustantivo"
    text = l10n.t("vocab.simple", "es",
                  word="“amor”", pos=pos)
    # → '"amor" es un sustantivo.'

    lang = l10n.lang_name("Spanish", "es")      # "espa\xf1ol"

Fallback chain: requested l1 → "en" → "".  Callers that receive "" should
apply their own default prose (see formatters.py).

Adding a new L1
───────────────
1. Add entries to _TEMPLATES (each key) and _POS_LABELS.
2. Optionally add entries to _LANG_NAMES and _CONFIRMED_FEATURES_LABEL.
Untranslated entries silently fall back to English.

Grammatical labels (person, number, tense, mood) remain English strings at
this layer — they originate from generators.py and are not yet localized.
The prose *structure* and connecting words are in the L1 language.
"""
from __future__ import annotations

# ── POS label phrases ──────────────────────────────────────────────────────────
# Each value is the full phrase used inside the explanation sentence, e.g.
#   EN  "is {pos}"  →  pos = "a noun"
#   ES  "es {pos}"  →  pos = "un sustantivo"
# Articles are embedded in the phrase so gender/article is correct per L1.

_POS_LABELS: dict[str, dict[str, str]] = {
    "en": {
        "noun":           "a noun",
        "verb":           "a verb",
        "adjective":      "an adjective",
        "adverb":         "an adverb",
        "auxiliary verb": "an auxiliary verb",
        "proper noun":    "a proper noun",
        "word":           "a word",
    },
    "es": {
        "noun":           "un sustantivo",
        "verb":           "un verbo",
        "adjective":      "un adjetivo",
        "adverb":         "un adverbio",
        "auxiliary verb": "un verbo auxiliar",
        "proper noun":    "un nombre propio",
        "word":           "una palabra",
    },
    "fr": {
        "noun":           "un nom",
        "verb":           "un verbe",
        "adjective":      "un adjectif",
        "adverb":         "un adverbe",
        "auxiliary verb": "un verbe auxiliaire",
        "proper noun":    "un nom propre",
        "word":           "un mot",
    },
    "de": {
        "noun":           "ein Substantiv",
        "verb":           "ein Verb",
        "adjective":      "ein Adjektiv",
        "adverb":         "ein Adverb",
        "auxiliary verb": "ein Hilfsverb",
        "proper noun":    "ein Eigenname",
        "word":           "ein Wort",
    },
    "ru": {
        "noun":           "существительное",
        "verb":           "глагол",
        "adjective":      "прилагательное",
        "adverb":         "наречие",
        "auxiliary verb": "вспомогательный глагол",
        "proper noun":    "имя собственное",
        "word":           "слово",
    },
    "ja": {
        "noun":           "名詞",
        "verb":           "動詞",
        "adjective":      "形容詞",
        "adverb":         "副詞",
        "auxiliary verb": "助動詞",
        "proper noun":    "固有名詞",
        "word":           "単語",
    },
    "pt": {
        "noun":           "um substantivo",
        "verb":           "um verbo",
        "adjective":      "um adjetivo",
        "adverb":         "um advérbio",
        "auxiliary verb": "um verbo auxiliar",
        "proper noun":    "um nome próprio",
        "word":           "uma palavra",
    },
    "it": {
        "noun":           "un sostantivo",
        "verb":           "un verbo",
        "adjective":      "un aggettivo",
        "adverb":         "un avverbio",
        "auxiliary verb": "un verbo ausiliare",
        "proper noun":    "un nome proprio",
        "word":           "una parola",
    },
    "ar": {
        "noun":           "اسم",
        "verb":           "فعل",
        "adjective":      "صفة",
        "adverb":         "ظرف",
        "auxiliary verb": "فعل مساعد",
        "proper noun":    "اسم علم",
        "word":           "كلمة",
    },
    "he": {
        "noun":           "שם עצם",
        "verb":           "פועל",
        "adjective":      "שם תואר",
        "adverb":         "תואר הפועל",
        "auxiliary verb": "פועל עזר",
        "proper noun":    "שם פרטי",
        "word":           "מילה",
    },
    "zh": {
        "noun":           "名词",
        "verb":           "动词",
        "adjective":      "形容词",
        "adverb":         "副词",
        "auxiliary verb": "助动词",
        "proper noun":    "专有名词",
        "word":           "词",
    },
    "ko": {
        "noun":           "명사",
        "verb":           "동사",
        "adjective":      "형용사",
        "adverb":         "부사",
        "auxiliary verb": "조동사",
        "proper noun":    "고유명사",
        "word":           "단어",
    },
}


def pos_label(pos_en: str, l1: str) -> str:
    """Localized POS phrase for *l1*, falling back to English."""
    return (
        _POS_LABELS.get(l1, {}).get(pos_en)
        or _POS_LABELS["en"].get(pos_en, pos_en)
    )


# ── Target-language names in L1 ────────────────────────────────────────────────
# Maps English language name → localized name in each L1.
# Keeps idiom explanations natural: "un modismo del español" not "del Spanish".

_LANG_NAMES: dict[str, dict[str, str]] = {
    "es": {
        "Arabic":     "árabe",
        "Chinese":    "chino",
        "English":    "inglés",
        "French":     "francés",
        "German":     "alemán",
        "Greek":      "griego",
        "Hebrew":     "hebreo",
        "Italian":    "italiano",
        "Japanese":   "japonés",
        "Korean":     "coreano",
        "Latin":      "latín",
        "Polish":     "polaco",
        "Portuguese": "portugués",
        "Russian":    "ruso",
        "Spanish":    "español",
        "Turkish":    "turco",
        "Ukrainian":  "ucraniano",
    },
    "fr": {
        "Arabic":     "arabe",
        "Chinese":    "chinois",
        "English":    "anglais",
        "French":     "français",
        "German":     "allemand",
        "Greek":      "grec",
        "Hebrew":     "hébreu",
        "Italian":    "italien",
        "Japanese":   "japonais",
        "Korean":     "coréen",
        "Latin":      "latin",
        "Polish":     "polonais",
        "Portuguese": "portugais",
        "Russian":    "russe",
        "Spanish":    "espagnol",
        "Turkish":    "turc",
        "Ukrainian":  "ukrainien",
    },
    "de": {
        "Arabic":     "Arabisch",
        "Chinese":    "Chinesisch",
        "English":    "Englisch",
        "French":     "Französisch",
        "German":     "Deutsch",
        "Greek":      "Griechisch",
        "Hebrew":     "Hebräisch",
        "Italian":    "Italienisch",
        "Japanese":   "Japanisch",
        "Korean":     "Koreanisch",
        "Latin":      "Latein",
        "Polish":     "Polnisch",
        "Portuguese": "Portugiesisch",
        "Russian":    "Russisch",
        "Spanish":    "Spanisch",
        "Turkish":    "Türkisch",
        "Ukrainian":  "Ukrainisch",
    },
    "ru": {
        "Arabic":     "арабского",
        "Chinese":    "китайского",
        "English":    "английского",
        "French":     "французского",
        "German":     "немецкого",
        "Greek":      "греческого",
        "Hebrew":     "иврита",
        "Italian":    "итальянского",
        "Japanese":   "японского",
        "Korean":     "корейского",
        "Latin":      "латыни",
        "Polish":     "польского",
        "Portuguese": "португальского",
        "Russian":    "русского",
        "Spanish":    "испанского",
        "Turkish":    "турецкого",
        "Ukrainian":  "украинского",
    },
    "ja": {
        "Arabic":     "アラビア語",
        "Chinese":    "中国語",
        "English":    "英語",
        "French":     "フランス語",
        "German":     "ドイツ語",
        "Greek":      "ギリシャ語",
        "Hebrew":     "ヘブライ語",
        "Italian":    "イタリア語",
        "Japanese":   "日本語",
        "Korean":     "韓国語",
        "Latin":      "ラテン語",
        "Polish":     "ポーランド語",
        "Portuguese": "ポルトガル語",
        "Russian":    "ロシア語",
        "Spanish":    "スペイン語",
        "Turkish":    "トルコ語",
        "Ukrainian":  "ウクライナ語",
    },
    "pt": {
        "Arabic":     "árabe",
        "Chinese":    "chinês",
        "English":    "inglês",
        "French":     "francês",
        "German":     "alemão",
        "Greek":      "grego",
        "Hebrew":     "hebraico",
        "Italian":    "italiano",
        "Japanese":   "japonês",
        "Korean":     "coreano",
        "Latin":      "latim",
        "Polish":     "polonês",
        "Portuguese": "português",
        "Russian":    "russo",
        "Spanish":    "espanhol",
        "Turkish":    "turco",
        "Ukrainian":  "ucraniano",
    },
    "it": {
        "Arabic":     "arabo",
        "Chinese":    "cinese",
        "English":    "inglese",
        "French":     "francese",
        "German":     "tedesco",
        "Greek":      "greco",
        "Hebrew":     "ebraico",
        "Italian":    "italiano",
        "Japanese":   "giapponese",
        "Korean":     "coreano",
        "Latin":      "latino",
        "Polish":     "polacco",
        "Portuguese": "portoghese",
        "Russian":    "russo",
        "Spanish":    "spagnolo",
        "Turkish":    "turco",
        "Ukrainian":  "ucraino",
    },
    "ar": {
        "Arabic":     "العربية",
        "Chinese":    "الصينية",
        "English":    "الإنجليزية",
        "French":     "الفرنسية",
        "German":     "الألمانية",
        "Greek":      "اليونانية",
        "Hebrew":     "العبرية",
        "Italian":    "الإيطالية",
        "Japanese":   "اليابانية",
        "Korean":     "الكورية",
        "Latin":      "اللاتينية",
        "Polish":     "البولندية",
        "Portuguese": "البرتغالية",
        "Russian":    "الروسية",
        "Spanish":    "الإسبانية",
        "Turkish":    "التركية",
        "Ukrainian":  "الأوكرانية",
    },
    "he": {
        "Arabic":     "ערבית",
        "Chinese":    "סינית",
        "English":    "אנגלית",
        "French":     "צרפתית",
        "German":     "גרמנית",
        "Greek":      "יוונית",
        "Hebrew":     "עברית",
        "Italian":    "איטלקית",
        "Japanese":   "יפנית",
        "Korean":     "קוריאנית",
        "Latin":      "לטינית",
        "Polish":     "פולנית",
        "Portuguese": "פורטוגזית",
        "Russian":    "רוסית",
        "Spanish":    "ספרדית",
        "Turkish":    "טורקית",
        "Ukrainian":  "אוקראינית",
    },
    "zh": {
        "Arabic":     "阿拉伯语",
        "Chinese":    "中文",
        "English":    "英语",
        "French":     "法语",
        "German":     "德语",
        "Greek":      "希腊语",
        "Hebrew":     "希伯来语",
        "Italian":    "意大利语",
        "Japanese":   "日语",
        "Korean":     "韩语",
        "Latin":      "拉丁语",
        "Polish":     "波兰语",
        "Portuguese": "葡萄牙语",
        "Russian":    "俄语",
        "Spanish":    "西班牙语",
        "Turkish":    "土耳其语",
        "Ukrainian":  "乌克兰语",
    },
    "ko": {
        "Arabic":     "아랍어",
        "Chinese":    "중국어",
        "English":    "영어",
        "French":     "프랑스어",
        "German":     "독일어",
        "Greek":      "그리스어",
        "Hebrew":     "히브리어",
        "Italian":    "이탈리아어",
        "Japanese":   "일본어",
        "Korean":     "한국어",
        "Latin":      "라틴어",
        "Polish":     "폴란드어",
        "Portuguese": "포르투갈어",
        "Russian":    "러시아어",
        "Spanish":    "스페인어",
        "Turkish":    "터키어",
        "Ukrainian":  "우크라이나어",
    },
}


def lang_name(english_name: str | None, l1: str) -> str | None:
    """Return *english_name* localized for *l1* display.

    Falls back to the English name when no translation is registered.
    Returns ``None`` when *english_name* is ``None``.
    """
    if english_name is None:
        return None
    return _LANG_NAMES.get(l1, {}).get(english_name, english_name)


# ── "morphological features" label ────────────────────────────────────────────

_FEATURES_FALLBACK: dict[str, str] = {
    "en": "morphological features",
    "es": "rasgos morfológicos",
    "fr": "caractéristiques morphologiques",
    "de": "morphologische Merkmale",
    "ru": "морфологические признаки",
    "ja": "形態論的特徴",
    "pt": "características morfológicas",
    "it": "caratteristiche morfologiche",
    "ar": "الخصائص الصرفية",
    "he": "מאפיינים מורפולוגיים",
    "zh": "形态特征",
    "ko": "형태론적 특징",
}


def features_fallback(l1: str) -> str:
    return _FEATURES_FALLBACK.get(l1, _FEATURES_FALLBACK["en"])


# ── Sentence templates ─────────────────────────────────────────────────────────
# Keys: <builder>.<variant>  (builder matches the formatter function name).
# Values: Python .format() strings; parameter names are documented inline.
#
# IMPORTANT: English templates MUST produce output identical to the
# pre-l10n hardcoded strings so that l1="en" is a no-op behaviour change.
#
# Grammatical label values ({person}, {number}, {tense}, {mood}) are English
# strings from generators.py and are NOT yet localized at this layer.

_TEMPLATES: dict[str, dict[str, str]] = {

    # ── vocabulary ────────────────────────────────────────────────────────────
    # {word}  quoted display label
    # {pos}   localized POS phrase, e.g. "a noun" / "un sustantivo"
    # {lemma} quoted lemma  [with_lemma variant only]
    "vocab.simple": {
        "en": "{word} is {pos}.",
        "es": "{word} es {pos}.",
        "fr": "{word} est {pos}.",
        "de": "{word} ist {pos}.",
        "ru": "{word} — это {pos}.",
        "ja": "{word}は{pos}です。",
        "pt": "{word} é {pos}.",
        "it": "{word} è {pos}.",
        "ar": "{word} هو {pos}.",
        "he": "{word} הוא {pos}.",
        "zh": "{word}是{pos}。",
        "ko": "{word}은(는) {pos}입니다.",
    },
    "vocab.with_lemma": {
        "en": "{word} is {pos}. Its base form (lemma) is {lemma}.",
        "es": "{word} es {pos}. Su forma base (lema) es {lemma}.",
        "fr": "{word} est {pos}. Sa forme de base (lemme) est {lemma}.",
        "de": "{word} ist {pos}. Die Grundform (Lemma) ist {lemma}.",
        "ru": "{word} — это {pos}. Начальная форма (лемма): {lemma}.",
        "ja": "{word}は{pos}です。基本形（レンマ）は{lemma}です。",
        "pt": "{word} é {pos}. A forma base (lema) é {lemma}.",
        "it": "{word} è {pos}. La forma base (lemma) è {lemma}.",
        "ar": "{word} هو {pos}. الجذر (اللما) هو {lemma}.",
        "he": "{word} הוא {pos}. צורת הבסיס (לֶמָּה) היא {lemma}.",
        "zh": "{word}是{pos}。基本形式（词元）是{lemma}。",
        "ko": "{word}은(는) {pos}입니다. 기본형(레마)은 {lemma}입니다.",
    },

    # ── conjugation ────────────────────────────────────────────────────────────
    # {word}, {person} (e.g. "third"), {number} (e.g. "singular"),
    # {tense}, {mood}, {lemma} — grammatical label values remain English
    "conj.full": {
        "en": "{word} is the {person}-person {number} {tense} {mood} form of {lemma}.",
        "es": "{word} es la forma {tense} {mood} de {person} persona {number} de {lemma}.",
        "fr": "{word} est la forme de {person} personne {number}, {tense} {mood}, de {lemma}.",
        "de": "{word} ist die {tense} {mood}-Form der {person} Person {number} von {lemma}.",
        "ru": "{word} — форма {person} лица {number} числа, {tense} {mood}, от {lemma}.",
        "ja": "{word}は{lemma}の{person}人称{number}、{tense} {mood}の活用形です。",
        "pt": "{word} é a forma {tense} {mood} de {person} pessoa {number} de {lemma}.",
        "it": "{word} è la forma {tense} {mood} della {person} persona {number} di {lemma}.",
        "ar": "{word} هو صيغة {person} {number}، {tense} {mood}، من {lemma}.",
        "he": "{word} היא צורת {person} {number}, {tense} {mood}, מ-{lemma}.",
        "zh": "{word}是{lemma}的{person}人称{number}、{tense}{mood}形式。",
        "ko": "{word}은(는) {lemma}의 {person}인칭 {number} {tense} {mood} 활용형입니다.",
    },
    "conj.simple": {
        "en": "{word} is a conjugated form of {lemma}.",
        "es": "{word} es una forma conjugada de {lemma}.",
        "fr": "{word} est une forme conjuguée de {lemma}.",
        "de": "{word} ist eine konjugierte Form von {lemma}.",
        "ru": "{word} — спрягаемая форма от {lemma}.",
        "ja": "{word}は{lemma}の活用形です。",
        "pt": "{word} é uma forma conjugada de {lemma}.",
        "it": "{word} è una forma coniugata di {lemma}.",
        "ar": "{word} هو شكل مصرَّف من {lemma}.",
        "he": "{word} היא צורה מוטה של {lemma}.",
        "zh": "{word}是{lemma}的一种变形。",
        "ko": "{word}은(는) {lemma}의 활용형입니다.",
    },

    # ── agreement ─────────────────────────────────────────────────────────────
    # {mod}, {mod_pos}, {noun}, {features}, {gender}, {number}
    "agree.main": {
        "en": "{mod} ({mod_pos}) and {noun} agree in {features}. The noun {noun} is {gender} {number}.",
        "es": "{mod} ({mod_pos}) y {noun} concuerdan en {features}. El sustantivo {noun} es {gender} {number}.",
        "fr": "{mod} ({mod_pos}) et {noun} s'accordent en {features}. Le nom {noun} est {gender} {number}.",
        "de": "{mod} ({mod_pos}) und {noun} stimmen in {features} überein. Das Substantiv {noun} ist {gender} {number}.",
        "ru": "{mod} ({mod_pos}) и {noun} согласуются в {features}. Существительное {noun} — {gender} рода, {number} числа.",
        "ja": "{mod}（{mod_pos}）と{noun}は{features}で一致します。名詞{noun}は{gender}の{number}です。",
        "pt": "{mod} ({mod_pos}) e {noun} concordam em {features}. O substantivo {noun} é {gender} {number}.",
        "it": "{mod} ({mod_pos}) e {noun} concordano in {features}. Il sostantivo {noun} è {gender} {number}.",
        "ar": "{mod} ({mod_pos}) و{noun} يتوافقان في {features}. الاسم {noun} هو {gender} {number}.",
        "he": "{mod} ({mod_pos}) ו-{noun} מסכימים ב-{features}. שם העצם {noun} הוא {gender} {number}.",
        "zh": "{mod}（{mod_pos}）与{noun}在{features}上一致。名词{noun}是{gender}{number}。",
        "ko": "{mod}({mod_pos})와 {noun}은(는) {features}에서 일치합니다. 명사 {noun}은(는) {gender} {number}입니다.",
    },

    # ── case_agreement ────────────────────────────────────────────────────────
    # {mod}, {mod_pos}, {noun}, {features}, {gender}, {number}, {case}
    "case.main": {
        "en": "{mod} ({mod_pos}) and {noun} agree in {features}. The noun {noun} is {gender} {number} in the {case} case.",
        "es": "{mod} ({mod_pos}) y {noun} concuerdan en {features}. El sustantivo {noun} es {gender} {number} en caso {case}.",
        "fr": "{mod} ({mod_pos}) et {noun} s'accordent en {features}. Le nom {noun} est {gender} {number} au cas {case}.",
        "de": "{mod} ({mod_pos}) und {noun} stimmen in {features} überein. Das Substantiv {noun} ist {gender} {number} im {case}.",
        "ru": "{mod} ({mod_pos}) и {noun} согласуются в {features}. Существительное {noun} — {gender} рода, {number} числа, в {case} падеже.",
        "ja": "{mod}（{mod_pos}）と{noun}は{features}で一致します。名詞{noun}は{gender}の{number}で{case}格です。",
        "pt": "{mod} ({mod_pos}) e {noun} concordam em {features}. O substantivo {noun} é {gender} {number} no caso {case}.",
        "it": "{mod} ({mod_pos}) e {noun} concordano in {features}. Il sostantivo {noun} è {gender} {number} nel caso {case}.",
        "ar": "{mod} ({mod_pos}) و{noun} يتوافقان في {features}. الاسم {noun} هو {gender} {number} في حالة {case}.",
        "he": "{mod} ({mod_pos}) ו-{noun} מסכימים ב-{features}. שם העצם {noun} הוא {gender} {number} ביחסת {case}.",
        "zh": "{mod}（{mod_pos}）与{noun}在{features}上一致。名词{noun}是{gender}{number}，{case}格。",
        "ko": "{mod}({mod_pos})와 {noun}은(는) {features}에서 일치합니다. 명사 {noun}은(는) {gender} {number}, {case}격입니다.",
    },

    # ── idiom ─────────────────────────────────────────────────────────────────
    # {word}, {lang} (localized via lang_name()), {meaning}
    "idiom.with_lang_and_meaning": {
        "en": "{word} is a {lang} idiom meaning {meaning}.",
        "es": "{word} es un modismo del {lang} que significa {meaning}.",
        "fr": "{word} est un idiome {lang} qui signifie {meaning}.",
        "de": "{word} ist eine {lang} Redewendung mit der Bedeutung {meaning}.",
        "ru": "{word} — идиома {lang}, означающая {meaning}.",
        "ja": "{word}は{meaning}という意味の{lang}の慣用句です。",
        "pt": "{word} é um idioma {lang} que significa {meaning}.",
        "it": "{word} è un idioma {lang} che significa {meaning}.",
        "ar": "{word} تعبير اصطلاحي {lang} يعني {meaning}.",
        "he": "{word} הוא ביטוי {lang} שמשמעותו {meaning}.",
        "zh": "{word}是{lang}成语，意为{meaning}。",
        "ko": "{word}은(는) {meaning}을 의미하는 {lang} 관용구입니다.",
    },
    "idiom.with_lang": {
        "en": "{word} is a {lang} idiomatic expression.",
        "es": "{word} es una expresión idiomática del {lang}.",
        "fr": "{word} est une expression idiomatique {lang}.",
        "de": "{word} ist ein {lang} idiomatischer Ausdruck.",
        "ru": "{word} — идиоматическое выражение {lang}.",
        "ja": "{word}は{lang}の慣用的表現です。",
        "pt": "{word} é uma expressão idiomática {lang}.",
        "it": "{word} è un'espressione idiomatica {lang}.",
        "ar": "{word} تعبير اصطلاحي {lang}.",
        "he": "{word} הוא ביטוי אידיומטי {lang}.",
        "zh": "{word}是{lang}惯用语。",
        "ko": "{word}은(는) {lang} 관용적 표현입니다.",
    },
    "idiom.meaning_only": {
        "en": "{word} means {meaning}.",
        "es": "{word} significa {meaning}.",
        "fr": "{word} signifie {meaning}.",
        "de": "{word} bedeutet {meaning}.",
        "ru": "{word} означает {meaning}.",
        "ja": "{word}は{meaning}という意味です。",
        "pt": "{word} significa {meaning}.",
        "it": "{word} significa {meaning}.",
        "ar": "{word} تعني {meaning}.",
        "he": "{word} פירושו {meaning}.",
        "zh": "{word}意为{meaning}。",
        "ko": "{word}은(는) {meaning}을 의미합니다.",
    },
    "idiom.plain": {
        "en": "{word} is an idiomatic expression.",
        "es": "{word} es una expresión idiomática.",
        "fr": "{word} est une expression idiomatique.",
        "de": "{word} ist ein idiomatischer Ausdruck.",
        "ru": "{word} — идиоматическое выражение.",
        "ja": "{word}は慣用的表現です。",
        "pt": "{word} é uma expressão idiomática.",
        "it": "{word} è un'espressione idiomatica.",
        "ar": "{word} تعبير اصطلاحي.",
        "he": "{word} הוא ביטוי אידיומטי.",
        "zh": "{word}是惯用语。",
        "ko": "{word}은(는) 관용적 표현입니다.",
    },

    # ── grammar ────────────────────────────────────────────────────────────────
    # {pattern} (already quoted), {usage}
    "grammar.with_usage": {
        "en": "The pattern {pattern}: {usage}",
        "es": "El patrón {pattern}: {usage}",
        "fr": "Le motif {pattern} : {usage}",
        "de": "Das Muster {pattern}: {usage}",
        "ru": "Конструкция {pattern}: {usage}",
        "ja": "パターン{pattern}：{usage}",
        "pt": "O padrão {pattern}: {usage}",
        "it": "Il pattern {pattern}: {usage}",
        "ar": "النمط {pattern}: {usage}",
        "he": "הדפוס {pattern}: {usage}",
        "zh": "语法模式{pattern}：{usage}",
        "ko": "패턴 {pattern}: {usage}",
    },
    "grammar.plain": {
        "en": "The grammatical pattern {pattern}.",
        "es": "El patrón gramatical {pattern}.",
        "fr": "Le motif grammatical {pattern}.",
        "de": "Das grammatische Muster {pattern}.",
        "ru": "Грамматическая конструкция {pattern}.",
        "ja": "文法パターン{pattern}。",
        "pt": "O padrão gramatical {pattern}.",
        "it": "Il pattern grammaticale {pattern}.",
        "ar": "النمط النحوي {pattern}.",
        "he": "הדפוס הדקדוקי {pattern}.",
        "zh": "语法模式{pattern}。",
        "ko": "문법 패턴 {pattern}.",
    },

    # ── nuance ─────────────────────────────────────────────────────────────────
    # {word}, {type_label} (already lowercased)
    "nuance.exhibits": {
        "en": "{word} exhibits {type_label}.",
        "es": "{word} presenta {type_label}.",
        "fr": "{word} présente {type_label}.",
        "de": "{word} zeigt {type_label}.",
        "ru": "{word} проявляет {type_label}.",
        "ja": "{word}は{type_label}を示します。",
        "pt": "{word} apresenta {type_label}.",
        "it": "{word} presenta {type_label}.",
        "ar": "{word} تُظهر {type_label}.",
        "he": "{word} מציג {type_label}.",
        "zh": "{word}具有{type_label}。",
        "ko": "{word}은(는) {type_label}을 나타냅니다.",
    },

    # ── script ─────────────────────────────────────────────────────────────────
    # {char} (already quoted), {meaning}
    "script.with_meaning": {
        "en": "{char} — {meaning}.",
        "es": "{char} — {meaning}.",
        "fr": "{char} — {meaning}.",
        "de": "{char} — {meaning}.",
        "ru": "{char} — {meaning}.",
        "ja": "{char} — {meaning}。",
        "pt": "{char} — {meaning}.",
        "it": "{char} — {meaning}.",
        "ar": "{char} — {meaning}.",
        "he": "{char} — {meaning}.",
        "zh": "{char}——{meaning}。",
        "ko": "{char} — {meaning}.",
    },
    "script.plain": {
        "en": "{char}",
        "es": "{char}",
        "fr": "{char}",
        "de": "{char}",
        "ru": "{char}",
        "ja": "{char}",
        "pt": "{char}",
        "it": "{char}",
        "ar": "{char}",
        "he": "{char}",
        "zh": "{char}",
        "ko": "{char}",
    },

    # ── dictionary ─────────────────────────────────────────────────────────────
    # {word} (already quoted), {gloss}, {lang}
    "dict.with_gloss": {
        "en": "{word} — {gloss}.",
        "es": "{word} — {gloss}.",
        "fr": "{word} — {gloss}.",
        "de": "{word} — {gloss}.",
        "ru": "{word} — {gloss}.",
        "ja": "{word} — {gloss}。",
        "pt": "{word} — {gloss}.",
        "it": "{word} — {gloss}.",
        "ar": "{word} — {gloss}.",
        "he": "{word} — {gloss}.",
        "zh": "{word}——{gloss}。",
        "ko": "{word} — {gloss}.",
    },
    "dict.with_lang": {
        "en": "{word} — {lang} vocabulary.",
        "es": "{word} — vocabulario {lang}.",
        "fr": "{word} — vocabulaire {lang}.",
        "de": "{word} — {lang} Wortschatz.",
        "ru": "{word} — словарный запас {lang}.",
        "ja": "{word} — {lang}の語彙。",
        "pt": "{word} — vocabulário {lang}.",
        "it": "{word} — vocabolario {lang}.",
        "ar": "{word} — مفردات {lang}.",
        "he": "{word} — אוצר מילים {lang}.",
        "zh": "{word}——{lang}词汇。",
        "ko": "{word} — {lang} 어휘.",
    },
    "dict.plain": {
        "en": "{word}",
        "es": "{word}",
        "fr": "{word}",
        "de": "{word}",
        "ru": "{word}",
        "ja": "{word}",
        "pt": "{word}",
        "it": "{word}",
        "ar": "{word}",
        "he": "{word}",
        "zh": "{word}",
        "ko": "{word}",
    },

    # ── transliteration ────────────────────────────────────────────────────────
    # {native}, {roman} (both quoted), {scheme} (e.g. " (hepburn)" or ""), {meaning}
    "translit.with_meaning": {
        "en": "{native} is romanized as {roman}{scheme} and means {meaning}.",
        "es": "{native} se romaniza como {roman}{scheme} y significa {meaning}.",
        "fr": "{native} se romanise comme {roman}{scheme} et signifie {meaning}.",
        "de": "{native} wird als {roman}{scheme} romanisiert und bedeutet {meaning}.",
        "ru": "{native} романизируется как {roman}{scheme} и означает {meaning}.",
        "ja": "{native}は{roman}{scheme}とローマ字化され、{meaning}という意味です。",
        "pt": "{native} é romanizado como {roman}{scheme} e significa {meaning}.",
        "it": "{native} si romanizza come {roman}{scheme} e significa {meaning}.",
        "ar": "{native} تُكتب بالحروف اللاتينية كـ{roman}{scheme} وتعني {meaning}.",
        "he": "{native} מתורגם לאותיות לטיניות כ-{roman}{scheme} ופירושו {meaning}.",
        "zh": "{native}的罗马字为{roman}{scheme}，意为{meaning}。",
        "ko": "{native}은(는) {roman}{scheme}으로 로마자 표기되며 {meaning}을 의미합니다.",
    },
    "translit.plain": {
        "en": "{native} is romanized as {roman}{scheme}.",
        "es": "{native} se romaniza como {roman}{scheme}.",
        "fr": "{native} se romanise comme {roman}{scheme}.",
        "de": "{native} wird als {roman}{scheme} romanisiert.",
        "ru": "{native} романизируется как {roman}{scheme}.",
        "ja": "{native}は{roman}{scheme}とローマ字化されます。",
        "pt": "{native} é romanizado como {roman}{scheme}.",
        "it": "{native} si romanizza come {roman}{scheme}.",
        "ar": "{native} تُكتب بالحروف اللاتينية كـ{roman}{scheme}.",
        "he": "{native} מתורגם לאותיות לטיניות כ-{roman}{scheme}.",
        "zh": "{native}的罗马字为{roman}{scheme}。",
        "ko": "{native}은(는) {roman}{scheme}으로 로마자 표기됩니다.",
    },
}


def t(key: str, l1: str, **kwargs: str) -> str:
    """Look up *(key, l1)* template, interpolate *kwargs*, return result.

    Fallback: English when *l1* not present; "" when *key* not found.
    Callers that receive "" should apply their own default prose.
    """
    entry = _TEMPLATES.get(key, {})
    tmpl = entry.get(l1) or entry.get("en", "")
    if not tmpl:
        return ""
    try:
        return tmpl.format(**kwargs)
    except KeyError:
        return tmpl
