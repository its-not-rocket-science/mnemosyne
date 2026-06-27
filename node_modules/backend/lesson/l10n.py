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

Grammatical labels (person, number, tense, mood, gender, case) are now
localized via ``gram_label()`` / ``localize_features()``.  The prose
structure, label values, and feature-category names are all in L1.
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


# ── Grammatical terminal labels ────────────────────────────────────────────────
# Each category maps English canonical values → per-L1 display strings.
# Falls back to the English value when a translation is absent.
# Extend each inner dict to add more L1 coverage.

_GRAM_LABELS: dict[str, dict[str, dict[str, str]]] = {
    # person — ordinal label inserted before "persona / Person / лицо / …"
    "person": {
        "first":  {"es": "primera",  "fr": "première",  "de": "erste",  "ru": "1-е",  "pt": "primeira",  "it": "prima",
                   "ja": "一人称",   "zh": "第一",       "ar": "أول",    "he": "ראשון", "ko": "일인칭"},
        "second": {"es": "segunda",  "fr": "deuxième",  "de": "zweite", "ru": "2-е",  "pt": "segunda",   "it": "seconda",
                   "ja": "二人称",   "zh": "第二",       "ar": "ثانٍ",   "he": "שני",   "ko": "이인칭"},
        "third":  {"es": "tercera",  "fr": "troisième", "de": "dritte", "ru": "3-е",  "pt": "terceira",  "it": "terza",
                   "ja": "三人称",   "zh": "第三",       "ar": "ثالث",   "he": "שלישי", "ko": "삼인칭"},
    },
    # number
    "number": {
        "singular": {"es": "singular", "fr": "singulier", "de": "Singular", "ru": "единственное",  "pt": "singular", "it": "singolare",
                     "ja": "単数",     "zh": "单数",        "ar": "مفرد",    "he": "יחיד",           "ko": "단수"},
        "plural":   {"es": "plural",   "fr": "pluriel",   "de": "Plural",   "ru": "множественное", "pt": "plural",   "it": "plurale",
                     "ja": "複数",     "zh": "复数",        "ar": "جمع",     "he": "רבים",           "ko": "복수"},
    },
    # tense
    "tense": {
        "present":      {"es": "presente",         "fr": "présent",          "de": "Präsens",         "ru": "настоящее",       "pt": "presente",          "it": "presente",
                         "ja": "現在",              "zh": "现在时",            "ar": "مضارع",           "he": "הווה",             "ko": "현재"},
        "preterite":    {"es": "pretérito",        "fr": "prétérit",         "de": "Präteritum",      "ru": "прошедшее",       "pt": "pretérito",         "it": "passato remoto",
                         "ja": "単純過去",           "zh": "简单过去时",         "ar": "ماضٍ بسيط",       "he": "עבר פשוט",         "ko": "단순과거"},
        "imperfect":    {"es": "imperfecto",       "fr": "imparfait",        "de": "Imperfekt",       "ru": "имперфект",       "pt": "imperfeito",        "it": "imperfetto",
                         "ja": "半過去",            "zh": "未完成过去时",        "ar": "ماضٍ ناقص",       "he": "עבר לא שלם",       "ko": "미완료과거"},
        "future":       {"es": "futuro",           "fr": "futur",            "de": "Futur",           "ru": "будущее",         "pt": "futuro",            "it": "futuro",
                         "ja": "未来",              "zh": "将来时",            "ar": "مستقبل",          "he": "עתיד",             "ko": "미래"},
        "conditional":  {"es": "condicional",      "fr": "conditionnel",     "de": "Konjunktiv II",   "ru": "условное",        "pt": "condicional",       "it": "condizionale",
                         "ja": "条件法",            "zh": "条件式",            "ar": "شرطي",            "he": "תנאי",             "ko": "조건법"},
        "past":         {"es": "pasado",           "fr": "passé",            "de": "Präteritum",      "ru": "прошедшее",       "pt": "passado",           "it": "passato",
                         "ja": "過去",              "zh": "过去时",            "ar": "ماضٍ",            "he": "עבר",              "ko": "과거"},
        "perfect":      {"es": "perfecto",         "fr": "passé composé",    "de": "Perfekt",         "ru": "перфект",         "pt": "perfeito",          "it": "passato prossimo",
                         "ja": "複合過去",           "zh": "复合过去时",         "ar": "ماضٍ مركب",       "he": "עבר מורכב",        "ko": "완료"},
        "pluperfect":   {"es": "pluscuamperfecto", "fr": "plus-que-parfait", "de": "Plusquamperfekt", "ru": "плюсквамперфект", "pt": "mais-que-perfeito", "it": "piuccheperfetto",
                         "ja": "大過去",            "zh": "愈过去时",           "ar": "ماضٍ بعيد",       "he": "עבר קדמון",        "ko": "대과거"},
        "past perfect": {"es": "pluscuamperfecto", "fr": "plus-que-parfait", "de": "Plusquamperfekt", "ru": "плюсквамперфект", "pt": "mais-que-perfeito", "it": "piuccheperfetto",
                         "ja": "大過去",            "zh": "过去完成时",         "ar": "ماضٍ تام",        "he": "עבר מושלם",        "ko": "과거완료"},
        "aorist":       {"es": "aoristo",          "fr": "aoriste",          "de": "Aorist",          "ru": "аорист",          "pt": "aoristo",           "it": "aoristo",
                         "ja": "アオリスト",         "zh": "不定过去时",         "ar": "ماضٍ مطلق",       "he": "אוריסט",           "ko": "아오리스트"},
    },
    # mood
    "mood": {
        "indicative":  {"es": "indicativo",  "fr": "indicatif",    "de": "Indikativ",    "ru": "изъявительное",  "pt": "indicativo",  "it": "indicativo",
                        "ja": "直説法",       "zh": "陈述语气",       "ar": "صيغة الخبر",  "he": "ישיר",           "ko": "직설법"},
        "subjunctive": {"es": "subjuntivo",  "fr": "subjonctif",   "de": "Konjunktiv I", "ru": "сослагательное", "pt": "subjuntivo",  "it": "congiuntivo",
                        "ja": "接続法",       "zh": "虚拟语气",       "ar": "صيغة المنصوب", "he": "מניע",          "ko": "가정법"},
        "imperative":  {"es": "imperativo",  "fr": "impératif",    "de": "Imperativ",    "ru": "повелительное",  "pt": "imperativo",  "it": "imperativo",
                        "ja": "命令法",       "zh": "命令语气",       "ar": "أمر",          "he": "ציווי",          "ko": "명령법"},
        "conditional": {"es": "condicional", "fr": "conditionnel", "de": "Konjunktiv II","ru": "условное",       "pt": "condicional", "it": "condizionale",
                        "ja": "条件法",       "zh": "条件式",         "ar": "شرطي",         "he": "תנאי",           "ko": "조건법"},
    },
    # gender
    "gender": {
        "masculine": {"es": "masculino", "fr": "masculin", "de": "maskulin", "ru": "мужской", "pt": "masculino", "it": "maschile",
                      "ja": "男性",      "zh": "阳性",       "ar": "مذكر",    "he": "זכר",      "ko": "남성"},
        "feminine":  {"es": "femenino",  "fr": "féminin",  "de": "feminin",  "ru": "женский", "pt": "feminino",  "it": "femminile",
                      "ja": "女性",      "zh": "阴性",       "ar": "مؤنث",    "he": "נקבה",     "ko": "여성"},
        "neuter":    {"es": "neutro",    "fr": "neutre",   "de": "neutral",  "ru": "средний", "pt": "neutro",    "it": "neutro",
                      "ja": "中性",      "zh": "中性",       "ar": "محايد",   "he": "ניטרלי",   "ko": "중성"},
    },
    # case
    "case": {
        "nominative":   {"es": "nominativo",   "fr": "nominatif",    "de": "Nominativ",    "ru": "именительный", "pt": "nominativo",   "it": "nominativo",
                         "ja": "主格",          "zh": "主格",           "ar": "رفع",          "he": "נומינטיב",     "ko": "주격"},
        "accusative":   {"es": "acusativo",    "fr": "accusatif",    "de": "Akkusativ",    "ru": "винительный",  "pt": "acusativo",    "it": "accusativo",
                         "ja": "対格",          "zh": "宾格",           "ar": "نصب",          "he": "אקוזטיב",      "ko": "목적격"},
        "dative":       {"es": "dativo",       "fr": "datif",        "de": "Dativ",        "ru": "дательный",    "pt": "dativo",       "it": "dativo",
                         "ja": "与格",          "zh": "与格",           "ar": "مفعول غير مباشر", "he": "דטיב",      "ko": "여격"},
        "genitive":     {"es": "genitivo",     "fr": "génitif",      "de": "Genitiv",      "ru": "родительный",  "pt": "genitivo",     "it": "genitivo",
                         "ja": "属格",          "zh": "属格",           "ar": "جر",           "he": "גניטיב",       "ko": "속격"},
        "instrumental": {"es": "instrumental", "fr": "instrumental", "de": "Instrumental", "ru": "творительный", "pt": "instrumental", "it": "strumentale",
                         "ja": "具格",          "zh": "工具格",         "ar": "أداتي",        "he": "אינסטרומנטל",  "ko": "도구격"},
        "locative":     {"es": "locativo",     "fr": "locatif",      "de": "Lokativ",      "ru": "предложный",   "pt": "locativo",     "it": "locativo",
                         "ja": "処格",          "zh": "处所格",         "ar": "مكاني",        "he": "לוקטיב",       "ko": "처소격"},
        "ablative":     {"es": "ablativo",     "fr": "ablatif",      "de": "Ablativ",      "ru": "аблатив",      "pt": "ablativo",     "it": "ablativo",
                         "ja": "奪格",          "zh": "离格",           "ar": "انفصالي",      "he": "אבלטיב",       "ko": "탈격"},
        "vocative":     {"es": "vocativo",     "fr": "vocatif",      "de": "Vokativ",      "ru": "звательный",   "pt": "vocativo",     "it": "vocativo",
                         "ja": "呼格",          "zh": "呼格",           "ar": "نداء",         "he": "וקטיב",        "ko": "호격"},
        "oblique":      {"es": "oblicuo",      "fr": "oblique",      "de": "Obliquus",     "ru": "косвенный",    "pt": "oblíquo",      "it": "obliquo",
                         "ja": "斜格",          "zh": "斜格",           "ar": "مائل",         "he": "אוֹבְלִיק",   "ko": "사격"},
    },
    # aspect (Russian, Slavic, Hindi)
    "aspect": {
        "imperfective": {"es": "imperfectivo", "fr": "imperfectif", "de": "imperfektiv", "ru": "несовершенный", "pt": "imperfectivo", "it": "imperfettivo",
                         "ja": "不完了体",      "zh": "未完成体",      "ar": "مستمر",       "he": "בלתי שלם",      "ko": "불완료체"},
        "perfective":   {"es": "perfectivo",   "fr": "perfectif",   "de": "perfektiv",   "ru": "совершенный",   "pt": "perfectivo",   "it": "perfettivo",
                         "ja": "完了体",        "zh": "完成体",        "ar": "تام",         "he": "שלם",           "ko": "완료체"},
    },
    # voice (Latin, Greek, Russian participles, etc.)
    "voice": {
        "active":  {"es": "activo",  "fr": "actif",   "de": "Aktiv",   "ru": "действительный", "pt": "ativo",   "it": "attivo",
                    "ja": "能動",    "zh": "主动",      "ar": "مبني للمعلوم",  "he": "פועל",   "ko": "능동"},
        "passive": {"es": "pasivo",  "fr": "passif",  "de": "Passiv",  "ru": "страдательный",  "pt": "passivo", "it": "passivo",
                    "ja": "受動",    "zh": "被动",      "ar": "مبني للمجهول",  "he": "סביל",   "ko": "수동"},
        "middle":  {"es": "medio",   "fr": "moyen",   "de": "Medium",  "ru": "средний залог",   "pt": "médio",   "it": "medio",
                    "ja": "中動",    "zh": "中动",      "ar": "صوت وسط",       "he": "אמצעי",  "ko": "중동"},
    },
    # feature category names (used in "agree in gender and number" phrases)
    "feature": {
        "gender": {"es": "género",  "fr": "genre",  "de": "Genus",   "ru": "роде",   "pt": "gênero", "it": "genere",
                   "ja": "性",      "zh": "性",      "ar": "الجنس",   "he": "מין",    "ko": "성"},
        "number": {"es": "número",  "fr": "nombre", "de": "Numerus", "ru": "числе",  "pt": "número", "it": "numero",
                   "ja": "数",      "zh": "数",      "ar": "العدد",   "he": "מספר",   "ko": "수"},
        "case":   {"es": "caso",    "fr": "cas",    "de": "Kasus",   "ru": "падеже", "pt": "caso",   "it": "caso",
                   "ja": "格",      "zh": "格",      "ar": "الإعراب", "he": "יחסה",   "ko": "격"},
    },
    # part of speech — bare labels for field display (no article; _POS_LABELS has article-prefixed phrases for explanations)
    "pos": {
        "noun":           {"es": "sustantivo",     "fr": "nom",        "de": "Substantiv",  "ru": "существительное",        "pt": "substantivo",    "it": "sostantivo",
                           "ja": "名詞",            "zh": "名词",        "ar": "اسم",          "he": "שם עצם",                 "ko": "명사"},
        "verb":           {"es": "verbo",          "fr": "verbe",      "de": "Verb",         "ru": "глагол",                 "pt": "verbo",          "it": "verbo",
                           "ja": "動詞",            "zh": "动词",        "ar": "فعل",          "he": "פועל",                   "ko": "동사"},
        "adjective":      {"es": "adjetivo",       "fr": "adjectif",   "de": "Adjektiv",     "ru": "прилагательное",         "pt": "adjetivo",       "it": "aggettivo",
                           "ja": "形容詞",          "zh": "形容词",      "ar": "صفة",          "he": "שם תואר",                "ko": "형용사"},
        "adverb":         {"es": "adverbio",       "fr": "adverbe",    "de": "Adverb",       "ru": "наречие",                "pt": "advérbio",       "it": "avverbio",
                           "ja": "副詞",            "zh": "副词",        "ar": "ظرف",          "he": "תואר הפועל",             "ko": "부사"},
        "auxiliary verb": {"es": "verbo auxiliar", "fr": "auxiliaire", "de": "Hilfsverb",    "ru": "вспомогательный глагол", "pt": "verbo auxiliar", "it": "verbo ausiliare",
                           "ja": "助動詞",          "zh": "助动词",      "ar": "فعل مساعد",    "he": "פועל עזר",               "ko": "보조동사"},
        "proper noun":    {"es": "nombre propio",  "fr": "nom propre", "de": "Eigenname",    "ru": "имя собственное",        "pt": "nome próprio",   "it": "nome proprio",
                           "ja": "固有名詞",        "zh": "专有名词",    "ar": "اسم علم",      "he": "שם פרטי",                "ko": "고유명사"},
        "word":           {"es": "palabra",        "fr": "mot",        "de": "Wort",          "ru": "слово",                  "pt": "palavra",        "it": "parola",
                           "ja": "語",              "zh": "词",          "ar": "كلمة",         "he": "מילה",                  "ko": "단어"},
    },
}

# Conjunction "and" for joining feature names in each L1.
_AND: dict[str, str] = {
    "en": "and", "es": "y", "fr": "et", "de": "und",
    "ru": "и",   "pt": "e", "it": "e",
    "ja": "と",  "ar": "و", "he": "ו", "zh": "和",  "ko": "와",
}


def gram_label(category: str, value_en: str, l1: str) -> str:
    """Localized grammatical terminal label for *l1*, falling back to *value_en*.

    Args:
        category: One of ``"person"``, ``"number"``, ``"tense"``, ``"mood"``,
                  ``"gender"``, ``"case"``, ``"aspect"``, ``"feature"``.
        value_en: English canonical label (e.g. ``"third"``, ``"present"``).
        l1:       BCP-47 learner-language code (e.g. ``"es"``).
    """
    return _GRAM_LABELS.get(category, {}).get(value_en, {}).get(l1) or value_en


def localize_features(features: list[str], l1: str) -> str:
    """Translate and join a list of grammatical feature category names for *l1*.

    E.g. ``["gender", "number"]`` → ``"género y número"`` for ``l1="es"``.
    Returns ``features_fallback(l1)`` when *features* is empty.
    """
    if not features:
        return features_fallback(l1)
    localized = [gram_label("feature", f, l1) for f in features]
    conj = _AND.get(l1, "and")
    if len(localized) == 1:
        return localized[0]
    return ", ".join(localized[:-1]) + f" {conj} " + localized[-1]


# ── Sentence templates ─────────────────────────────────────────────────────────
# Keys: <builder>.<variant>  (builder matches the formatter function name).
# Values: Python .format() strings; parameter names are documented inline.
#
# IMPORTANT: English templates MUST produce output identical to the
# pre-l10n hardcoded strings so that l1="en" is a no-op behaviour change.
#
# Grammatical label values ({person}, {number}, {tense}, {mood}, {gender},
# {case}) are now localized via gram_label() before being passed here.

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
    # {word}, {person} (localized ordinal), {number} (localized),
    # {tense}, {mood} (localized), {lemma}
    "conj.full": {
        "en": "{word} is the {person}-person {number} {tense} {mood} form of {lemma}.",
        "es": "{word} es la forma {tense} {mood} de {person} persona {number} de {lemma}.",
        "fr": "{word} est la forme de {person} personne {number}, {tense} {mood}, de {lemma}.",
        "de": "{word} ist die {tense} {mood}-Form der {person} Person {number} von {lemma}.",
        "ru": "{word} — форма глагола {lemma} ({person} лицо, {number} число, {tense}, {mood}).",
        "ja": "{word}は{lemma}の{person}人称{number}、{tense} {mood}の活用形です。",
        "pt": "{word} é a forma {tense} {mood} de {person} pessoa {number} de {lemma}.",
        "it": "{word} è la forma {tense} {mood} della {person} persona {number} di {lemma}.",
        "ar": "{word} هو صيغة {person} {number}، {tense} {mood}، من {lemma}.",
        "he": "{word} היא צורת {person} {number}, {tense} {mood}, מ-{lemma}.",
        "zh": "{word}是{lemma}的{person}人称{number}、{tense}{mood}形式。",
        "ko": "{word}은(는) {lemma}의 {person}인칭 {number} {tense} {mood} 활용형입니다.",
    },
    # {word}, {tense}, {mood}, {lemma} — used when person/number are unknown
    # (e.g. English past tense, which is uninflected for person and number)
    "conj.tense_only": {
        "en": "{word} is the {tense} {mood} form of {lemma}.",
        "es": "{word} es la forma {tense} {mood} de {lemma}.",
        "fr": "{word} est la forme {tense} {mood} de {lemma}.",
        "de": "{word} ist die {tense} {mood}-Form von {lemma}.",
        "ru": "{word} — форма глагола {lemma} ({tense}, {mood}).",
        "ja": "{word}は{lemma}の{tense} {mood}の活用形です。",
        "pt": "{word} é a forma {tense} {mood} de {lemma}.",
        "it": "{word} è la forma {tense} {mood} di {lemma}.",
        "ar": "{word} هو صيغة {tense} {mood} من {lemma}.",
        "he": "{word} היא צורת {tense} {mood} של {lemma}.",
        "zh": "{word}是{lemma}的{tense}{mood}形式。",
        "ko": "{word}은(는) {lemma}의 {tense} {mood} 활용형입니다.",
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
        "ru": "{mod} ({mod_pos}) и {noun} согласуются в {features}. Существительное {noun}: {gender} род, {number} число.",
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
        "ru": "{mod} ({mod_pos}) и {noun} согласуются в {features}. Существительное {noun}: {gender} род, {number} число, {case} падеж.",
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

    # ── Lesson titles ─────────────────────────────────────────────────────────
    # {word} = display label / surface form
    "drill.vocab_title": {
        "en": "Vocabulary: {word}",
        "es": "Vocabulario: {word}",
        "fr": "Vocabulaire : {word}",
        "de": "Wortschatz: {word}",
        "ru": "Лексика: {word}",
        "ja": "語彙：{word}",
        "pt": "Vocabulário: {word}",
        "it": "Vocabolario: {word}",
        "ar": "مفردات: {word}",
        "he": "מילון: {word}",
        "zh": "词汇：{word}",
        "ko": "어휘: {word}",
    },
    "drill.conj_title": {
        "en": "Conjugation: {word}",
        "es": "Conjugación: {word}",
        "fr": "Conjugaison : {word}",
        "de": "Konjugation: {word}",
        "ru": "Спряжение: {word}",
        "ja": "活用形：{word}",
        "pt": "Conjugação: {word}",
        "it": "Coniugazione: {word}",
        "ar": "تصريف: {word}",
        "he": "נטייה: {word}",
        "zh": "变位：{word}",
        "ko": "활용형: {word}",
    },
    "drill.agree_title": {
        "en": "Agreement: {word}",
        "es": "Concordancia: {word}",
        "fr": "Accord : {word}",
        "de": "Kongruenz: {word}",
        "ru": "Согласование: {word}",
        "ja": "一致：{word}",
        "pt": "Concordância: {word}",
        "it": "Accordo: {word}",
        "ar": "تطابق: {word}",
        "he": "הסכמה: {word}",
        "zh": "一致：{word}",
        "ko": "일치: {word}",
    },
    "drill.case_agree_title": {
        "en": "Case agreement: {word}",
        "es": "Concordancia de caso: {word}",
        "fr": "Accord de cas : {word}",
        "de": "Kasuskongruenz: {word}",
        "ru": "Падежное согласование: {word}",
        "ja": "格一致：{word}",
        "pt": "Concordância de caso: {word}",
        "it": "Accordo di caso: {word}",
        "ar": "تطابق حالة: {word}",
        "he": "הסכמת יחסה: {word}",
        "zh": "格一致：{word}",
        "ko": "격 일치: {word}",
    },

    # ── Drill prompts ─────────────────────────────────────────────────────────
    # {word} = quoted surface / display form
    # {mod}  = modifier (agreement / case drills)
    # {noun} = noun    (agreement / case drills)
    "drill.pos_blank": {
        "en": "“{word}” is a ———",
        "es": "“{word}” es ———",
        "fr": "“{word}” est ———",
        "de": "“{word}” ist ———",
        "ru": "“{word}” — это ———",
        "ja": "「{word}」は———",
        "pt": "“{word}” é ———",
        "it": "“{word}” è ———",
        "ar": "“{word}” هو ———",
        "he": "“{word}” הוא ———",
        "zh": "“{word}”是———",
        "ko": "“{word}”은(는) ———",
    },
    "drill.lemma_blank": {
        "en": "The base form (lemma) of “{word}” is ———.",
        "es": "La forma base (lema) de “{word}” es ———.",
        "fr": "La forme de base (lemme) de “{word}” est ———.",
        "de": "Die Grundform (Lemma) von “{word}” ist ———.",
        "ru": "Начальная форма (лемма) слова “{word}” — ———.",
        "ja": "「{word}」の基本形（レンマ）は———。",
        "pt": "A forma base (lema) de “{word}” é ———.",
        "it": "La forma base (lemma) di “{word}” è ———.",
        "ar": "الشكل الأساسي (اللما) لـ“{word}” هو ———.",
        "he": "צורת הבסיס (לֶמָּה) של “{word}” היא ———.",
        "zh": "“{word}”的基本形式（词元）是———。",
        "ko": "“{word}”의 기본형(레마)은 ———입니다.",
    },
    "drill.verb_form_blank": {
        "en": "“{word}” is a form of the verb ———.",
        "es": "“{word}” es una forma del verbo ———.",
        "fr": "“{word}” est une forme du verbe ———.",
        "de": "“{word}” ist eine Form des Verbs ———.",
        "ru": "“{word}” — форма глагола ———.",
        "ja": "「{word}」は動詞———の活用形です。",
        "pt": "“{word}” é uma forma do verbo ———.",
        "it": "“{word}” è una forma del verbo ———.",
        "ar": "“{word}” هو صيغة من صيغ الفعل ———.",
        "he": "“{word}” היא צורה של הפועל ———.",
        "zh": "“{word}”是动词———的一种形式。",
        "ko": "“{word}”은(는) 동사 ———의 활용형입니다.",
    },
    "drill.what_tense": {
        "en": "What tense is “{word}”?",
        "es": "¿Qué tiempo verbal tiene “{word}”?",
        "fr": "Quel est le temps de “{word}” ?",
        "de": "Welchen Tempus hat “{word}”?",
        "ru": "Какое время у “{word}”?",
        "ja": "「{word}」の時制は何ですか？",
        "pt": "Qual é o tempo de “{word}”?",
        "it": "Che tempo è “{word}”?",
        "ar": "ما زمن “{word}”؟",
        "he": "מה זמן הפועל “{word}”?",
        "zh": "“{word}”是什么时态？",
        "ko": "“{word}”의 시제는 무엇입니까?",
    },
    "drill.what_mood": {
        "en": "What mood is “{word}”?",
        "es": "¿Qué modo verbal tiene “{word}”?",
        "fr": "Quel est le mode de “{word}” ?",
        "de": "Welchen Modus hat “{word}”?",
        "ru": "Какое наклонение у “{word}”?",
        "ja": "「{word}」の法は何ですか？",
        "pt": "Qual é o modo de “{word}”?",
        "it": "Che modo è “{word}”?",
        "ar": "ما صيغة “{word}”؟",
        "he": "מה הנטייה של “{word}”?",
        "zh": "“{word}”是什么语气？",
        "ko": "“{word}”의 법은 무엇입니까?",
    },
    "drill.what_gender": {
        "en": "What gender is “{word}”?",
        "es": "¿De qué género es “{word}”?",
        "fr": "Quel est le genre de “{word}” ?",
        "de": "Welchen Genus hat “{word}”?",
        "ru": "Какой род у “{word}”?",
        "ja": "「{word}」の性は何ですか？",
        "pt": "Qual é o gênero de “{word}”?",
        "it": "Qual è il genere di “{word}”?",
        "ar": "ما جنس “{word}”؟",
        "he": "מה המין הדקדוקי של “{word}”?",
        "zh": "“{word}”是什么性？",
        "ko": "“{word}”의 성은 무엇입니까?",
    },
    "drill.what_case": {
        "en": "What case is “{mod}” … “{noun}” in?",
        "es": "¿En qué caso están “{mod}” … “{noun}”?",
        "fr": "Dans quel cas sont “{mod}” … “{noun}” ?",
        "de": "In welchem Fall stehen “{mod}” … “{noun}”?",
        "ru": "В каком падеже стоит “{mod}” … “{noun}”?",
        "ja": "「{mod}」…「{noun}」の格は何ですか？",
        "pt": "Em que caso estão “{mod}” … “{noun}”?",
        "it": "In quale caso si trovano “{mod}” … “{noun}”?",
        "ar": "ما إعراب “{mod}” … “{noun}”؟",
        "he": "באיזה יחסה נמצאים “{mod}” … “{noun}”?",
        "zh": "“{mod}”…“{noun}”是什么格？",
        "ko": "“{mod}” … “{noun}”의 격은 무엇입니까?",
    },
    "drill.reflexive_stmt": {
        "en": "“{word}” uses a reflexive pronoun.",
        "es": "“{word}” usa un pronombre reflexivo.",
        "fr": "“{word}” utilise un pronom réfléchi.",
        "de": "“{word}” verwendet ein Reflexivpronomen.",
        "ru": "“{word}” использует возвратное местоимение.",
        "ja": "「{word}」は再帰代名詞を使います。",
        "pt": "“{word}” usa um pronome reflexivo.",
        "it": "“{word}” usa un pronome riflessivo.",
        "ar": "“{word}” يستخدم ضميرًا انعكاسيًا.",
        "he": "“{word}” משתמש בכינוי חוזר.",
        "zh": "“{word}”使用反身代词。",
        "ko": "“{word}”은(는) 재귀대명사를 사용합니다.",
    },
    "drill.agree_gender_stmt": {
        "en": "”{mod}” and “{noun}” agree in gender.",
        "es": "”{mod}” y “{noun}” concuerdan en género.",
        "fr": "”{mod}” et “{noun}” s’accordent en genre.",
        "de": "”{mod}” und “{noun}” stimmen im Genus überein.",
        "ru": "”{mod}” и “{noun}” согласуются в роде.",
        "ja": "「{mod}」と「{noun}」は性で一致します。",
        "pt": "”{mod}” e “{noun}” concordam em gênero.",
        "it": "”{mod}” e “{noun}” concordano nel genere.",
        "ar": "”{mod}” و”{noun}” يتطابقان في الجنس.",
        "he": "”{mod}” ו”{noun}” מסכימים במין.",
        "zh": "”{mod}”与”{noun}”在性上一致。",
        "ko": "”{mod}”와 “{noun}”은(는) 성에서 일치합니다.",
    },

    # ── Inflection ─────────────────────────────────────────────────────────────
    "drill.inflection_title": {
        "en": "Inflection: {word}",
        "es": "Declinación: {word}",
        "fr": "Déclinaison : {word}",
        "de": "Deklination: {word}",
        "ru": "Склонение: {word}",
        "ja": "語形変化：{word}",
        "pt": "Declinação: {word}",
        "it": "Declinazione: {word}",
        "ar": "تصريف: {word}",
        "he": "נטייה: {word}",
        "zh": "格变化：{word}",
        "ko": "격변화: {word}",
    },
    # {word}, {case}, {number}, {lemma}
    "inflect.case_number": {
        "en": "{word} is the {case} {number} form of {lemma}.",
        "es": "{word} es la forma {case} {number} de {lemma}.",
        "fr": "{word} est la forme {case} {number} de {lemma}.",
        "de": "{word} ist die {case}-{number}-Form von {lemma}.",
        "ru": "{word} — форма {lemma} в {case} падеже, {number} числе.",
        "ja": "{word}は{lemma}の{case}格{number}形です。",
        "pt": "{word} é a forma {case} {number} de {lemma}.",
        "it": "{word} è la forma {case} {number} di {lemma}.",
        "ar": "{word} هي صيغة {case} {number} من {lemma}.",
        "he": "{word} היא צורת {case} {number} של {lemma}.",
        "zh": "{word}是{lemma}的{case}{number}格形式。",
        "ko": "{word}은(는) {lemma}의 {case} {number} 형태입니다.",
    },
    # {word}, {lemma}
    "inflect.simple": {
        "en": "{word} is an inflected form of {lemma}.",
        "es": "{word} es una forma flexionada de {lemma}.",
        "fr": "{word} est une forme fléchie de {lemma}.",
        "de": "{word} ist eine flektierte Form von {lemma}.",
        "ru": "{word} — словоизменительная форма от {lemma}.",
        "ja": "{word}は{lemma}の語形変化です。",
        "pt": "{word} é uma forma flexionada de {lemma}.",
        "it": "{word} è una forma flessa di {lemma}.",
        "ar": "{word} هي صيغة اشتقاقية من {lemma}.",
        "he": "{word} היא צורה נטויה של {lemma}.",
        "zh": "{word}是{lemma}的一种变形形式。",
        "ko": "{word}은(는) {lemma}의 활용형입니다.",
    },

    # ── New morphology drill prompts ───────────────────────────────────────────
    # {word} = surface form
    "drill.what_aspect": {
        "en": "What aspect is “{word}”?",
        "es": "¿Qué aspecto tiene “{word}”?",
        "fr": "Quel est l’aspect de “{word}” ?",
        "de": "Welchen Aspekt hat “{word}”?",
        "ru": "Какой вид у “{word}”?",
        "ja": "「{word}」のアスペクトは何ですか？",
        "pt": "Qual é o aspecto de “{word}”?",
        "it": "Che aspetto è “{word}”?",
        "ar": "ما صيغة “{word}”؟",
        "he": "מה הפועל “{word}”?",
        "zh": "“{word}”是什么体态？",
        "ko": "“{word}”의 상은 무엇입니까?",
    },
    # {features} = localized feature combo, {lemma} = quoted citation form
    "drill.form_recall": {
        "en": "Give the {features} form of {lemma}.",
        "es": "Da la forma {features} de {lemma}.",
        "fr": "Donnez la forme {features} de {lemma}.",
        "de": "Geben Sie die {features}-Form von {lemma}.",
        "ru": "Дайте форму {features} от {lemma}.",
        "ja": "{lemma}の{features}形を答えてください。",
        "pt": "Dê a forma {features} de {lemma}.",
        "it": "Dai la forma {features} di {lemma}.",
        "ar": "أعطِ صيغة {features} من {lemma}.",
        "he": "תן את צורת {features} של {lemma}.",
        "zh": "给出{lemma}的{features}形式。",
        "ko": "{lemma}의 {features} 형태를 쓰세요.",
    },
    # {features} = axis description, {lemma} = quoted lemma
    "drill.paradigm_cell": {
        "en": "Give the {features} form of {lemma}.",
        "es": "Da la forma {features} de {lemma}.",
        "fr": "Donnez la forme {features} de {lemma}.",
        "de": "Geben Sie die {features}-Form von {lemma}.",
        "ru": "Дайте форму {features} от {lemma}.",
        "ja": "{lemma}の{features}形を答えてください。",
        "pt": "Dê a forma {features} de {lemma}.",
        "it": "Dai la forma {features} di {lemma}.",
        "ar": "أعطِ صيغة {features} من {lemma}.",
        "he": "תן את צורת {features} של {lemma}.",
        "zh": "给出{lemma}的{features}形式。",
        "ko": "{lemma}의 {features} 형태를 쓰세요.",
    },
    # {word} = quoted surface form
    "drill.choose_equivalent": {
        "en": "Which is an equivalent construction for {word}?",
        "es": "¿Cuál es una construcción equivalente para {word}?",
        "fr": "Quelle est une construction équivalente pour {word} ?",
        "de": "Welche Konstruktion ist äquivalent zu {word}?",
        "ru": "Какая конструкция эквивалентна {word}?",
        "ja": "{word}と同等の構文はどれですか？",
        "pt": "Qual é uma construção equivalente para {word}?",
        "it": "Qual è una costruzione equivalente per {word}?",
        "ar": "أيٌّ من التراكيب مكافئ لـ{word}؟",
        "he": "איזו תרכובת שקולה ל-{word}?",
        "zh": "哪个是{word}的等效构式？",
        "ko": "{word}에 해당하는 동등 표현은 무엇입니까?",
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
