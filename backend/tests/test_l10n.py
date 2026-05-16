"""Tests for backend/lesson/l10n.py — locale coverage and fallback behaviour."""
import pytest

import backend.lesson.l10n as l10n

ALL_L1 = ["en", "es", "fr", "de", "ru", "ja", "pt", "it", "ar", "he", "zh", "ko"]
ALL_POS = ["noun", "verb", "adjective", "adverb", "auxiliary verb", "proper noun", "word"]
ALL_TEMPLATE_KEYS = [
    "vocab.simple", "vocab.with_lemma",
    "conj.full", "conj.simple",
    "agree.main", "case.main",
    "idiom.with_lang_and_meaning", "idiom.with_lang", "idiom.meaning_only", "idiom.plain",
    "grammar.with_usage", "grammar.plain",
    "nuance.exhibits",
    "script.with_meaning", "script.plain",
    "dict.with_gloss", "dict.with_lang", "dict.plain",
    "translit.with_meaning", "translit.plain",
]

# Representative kwargs for each template key — simple ASCII placeholders.
_KWARGS: dict[str, dict[str, str]] = {
    "vocab.simple":                 {"word": "x", "pos": "a noun"},
    "vocab.with_lemma":             {"word": "x", "pos": "a noun", "lemma": "y"},
    "conj.full":                    {"word": "x", "person": "third", "number": "singular",
                                     "tense": "present", "mood": "indicative", "lemma": "y"},
    "conj.simple":                  {"word": "x", "lemma": "y"},
    "agree.main":                   {"mod": "x", "mod_pos": "adjective", "noun": "y",
                                     "features": "gender and number", "gender": "masculine",
                                     "number": "singular"},
    "case.main":                    {"mod": "x", "mod_pos": "adjective", "noun": "y",
                                     "features": "case and gender", "gender": "masculine",
                                     "number": "singular", "case": "nominative"},
    "idiom.with_lang_and_meaning":  {"word": "x", "lang": "Spanish", "meaning": "y"},
    "idiom.with_lang":              {"word": "x", "lang": "Spanish"},
    "idiom.meaning_only":           {"word": "x", "meaning": "y"},
    "idiom.plain":                  {"word": "x"},
    "grammar.with_usage":           {"pattern": "x", "usage": "some usage"},
    "grammar.plain":                {"pattern": "x"},
    "nuance.exhibits":              {"word": "x", "type_label": "register"},
    "script.with_meaning":          {"char": "x", "meaning": "character"},
    "script.plain":                 {"char": "x"},
    "dict.with_gloss":              {"word": "x", "gloss": "some gloss"},
    "dict.with_lang":               {"word": "x", "lang": "Latin"},
    "dict.plain":                   {"word": "x"},
    "translit.with_meaning":        {"native": "x", "roman": "y", "scheme": " (hepburn)", "meaning": "love"},
    "translit.plain":               {"native": "x", "roman": "y", "scheme": " (hepburn)"},
}


class TestPosLabel:
    @pytest.mark.parametrize("l1", ALL_L1)
    def test_all_pos_defined_for_all_locales(self, l1: str) -> None:
        for pos in ALL_POS:
            result = l10n.pos_label(pos, l1)
            assert result, f"pos_label({pos!r}, {l1!r}) returned empty"

    def test_unknown_l1_falls_back_to_english(self) -> None:
        assert l10n.pos_label("noun", "xx") == "a noun"

    def test_unknown_pos_returns_pos_itself(self) -> None:
        assert l10n.pos_label("particle", "en") == "particle"

    def test_french_noun_label(self) -> None:
        assert l10n.pos_label("noun", "fr") == "un nom"

    def test_german_verb_label(self) -> None:
        assert l10n.pos_label("verb", "de") == "ein Verb"

    def test_japanese_adjective_label(self) -> None:
        assert l10n.pos_label("adjective", "ja") == "形容詞"  # 形容詞

    def test_arabic_noun_label(self) -> None:
        assert l10n.pos_label("noun", "ar") == "اسم"  # اسم

    def test_korean_verb_label(self) -> None:
        assert l10n.pos_label("verb", "ko") == "동사"  # 동사


class TestLangName:
    @pytest.mark.parametrize("l1", ALL_L1)
    def test_spanish_is_localized_for_all_l1(self, l1: str) -> None:
        result = l10n.lang_name("Spanish", l1)
        assert result is not None
        assert result  # non-empty

    def test_english_l1_falls_back_to_english_name(self) -> None:
        # "en" has no _LANG_NAMES entry → returns the English name unchanged
        assert l10n.lang_name("Spanish", "en") == "Spanish"

    def test_none_input_returns_none(self) -> None:
        assert l10n.lang_name(None, "es") is None

    def test_unknown_language_returns_english_name(self) -> None:
        assert l10n.lang_name("Klingon", "es") == "Klingon"

    def test_french_spanish(self) -> None:
        assert l10n.lang_name("Spanish", "fr") == "espagnol"

    def test_german_japanese(self) -> None:
        assert l10n.lang_name("Japanese", "de") == "Japanisch"

    def test_russian_lang_name_genitive(self) -> None:
        # Russian entries use genitive so "idiom of {lang}" reads naturally
        assert l10n.lang_name("Spanish", "ru") == "испанского"

    def test_japanese_english_name(self) -> None:
        assert l10n.lang_name("English", "ja") == "英語"  # 英語

    def test_chinese_korean_name(self) -> None:
        assert l10n.lang_name("Korean", "zh") == "韩语"  # 韩语

    def test_korean_japanese_name(self) -> None:
        assert l10n.lang_name("Japanese", "ko") == "일본어"  # 일본어

    def test_arabic_english_name(self) -> None:
        result = l10n.lang_name("English", "ar")
        assert result == "الإنجليزية"

    def test_hebrew_french_name(self) -> None:
        result = l10n.lang_name("French", "he")
        assert result == "צרפתית"  # צרפתית


class TestFeaturesLabel:
    @pytest.mark.parametrize("l1", ALL_L1)
    def test_non_empty_for_all_locales(self, l1: str) -> None:
        result = l10n.features_fallback(l1)
        assert result

    def test_unknown_l1_falls_back_to_english(self) -> None:
        assert l10n.features_fallback("xx") == "morphological features"

    def test_french_label(self) -> None:
        assert "morphologiques" in l10n.features_fallback("fr")

    def test_japanese_label(self) -> None:
        assert l10n.features_fallback("ja") == "形態論的特徴"  # 形態論的特徴


class TestTemplates:
    @pytest.mark.parametrize("l1", ALL_L1)
    @pytest.mark.parametrize("key", ALL_TEMPLATE_KEYS)
    def test_every_template_renders_non_empty(self, l1: str, key: str) -> None:
        result = l10n.t(key, l1, **_KWARGS[key])
        assert result, f"t({key!r}, {l1!r}) returned empty"

    def test_unknown_key_returns_empty(self) -> None:
        assert l10n.t("nonexistent.key", "en", word="x") == ""

    def test_unknown_l1_falls_back_to_english(self) -> None:
        result = l10n.t("vocab.simple", "xx", word="amor", pos="a noun")
        assert "is" in result
        assert "amor" in result

    def test_missing_kwarg_returns_template_string(self) -> None:
        # Incomplete kwargs must not crash; returns raw template
        result = l10n.t("vocab.simple", "en", word="x")
        assert result  # doesn't crash

    def test_english_vocab_simple(self) -> None:
        assert l10n.t("vocab.simple", "en", word="amor", pos="a noun") == "amor is a noun."

    def test_spanish_vocab_simple(self) -> None:
        assert l10n.t("vocab.simple", "es", word="amor", pos="un sustantivo") == "amor es un sustantivo."

    def test_french_vocab_simple_uses_est(self) -> None:
        result = l10n.t("vocab.simple", "fr", word="amour", pos="un nom")
        assert "est" in result

    def test_german_vocab_simple_uses_ist(self) -> None:
        result = l10n.t("vocab.simple", "de", word="Liebe", pos="ein Substantiv")
        assert "ist" in result

    def test_russian_vocab_simple_has_dash(self) -> None:
        result = l10n.t("vocab.simple", "ru", word="love", pos="существительное")
        assert "—" in result or "это" in result  # — or это

    def test_japanese_vocab_simple_has_desu(self) -> None:
        result = l10n.t("vocab.simple", "ja", word="愛", pos="名詞")
        assert "です" in result  # です

    def test_arabic_vocab_simple_has_huwa(self) -> None:
        result = l10n.t("vocab.simple", "ar", word="x", pos="اسم")
        assert "هو" in result  # هو

    def test_hebrew_vocab_simple_has_hu(self) -> None:
        result = l10n.t("vocab.simple", "he", word="x", pos="שם עצם")
        assert "הוא" in result  # הוא

    def test_chinese_vocab_simple_has_shi_and_period(self) -> None:
        result = l10n.t("vocab.simple", "zh", word="爱", pos="名词")
        assert "是" in result  # 是
        assert "。" in result  # 。

    def test_korean_vocab_simple_has_imnida(self) -> None:
        result = l10n.t("vocab.simple", "ko", word="사랑", pos="명사")
        assert "입니다" in result  # 입니다

    def test_portuguese_vocab_simple_has_e(self) -> None:
        result = l10n.t("vocab.simple", "pt", word="amor", pos="um substantivo")
        assert "é" in result  # é

    def test_italian_vocab_simple_has_e(self) -> None:
        result = l10n.t("vocab.simple", "it", word="amore", pos="un sostantivo")
        assert "è" in result  # è

    def test_french_idiom_with_all_info(self) -> None:
        result = l10n.t(
            "idiom.with_lang_and_meaning", "fr",
            word="por supuesto", lang="espagnol", meaning="bien sur",
        )
        assert "espagnol" in result
        assert "signifie" in result

    def test_german_grammar_with_usage(self) -> None:
        result = l10n.t("grammar.with_usage", "de", pattern="be_progressive", usage="ongoing action")
        assert "Muster" in result
        assert "ongoing action" in result

    def test_japanese_translit_with_meaning(self) -> None:
        result = l10n.t(
            "translit.with_meaning", "ja",
            native="愛", roman="ai", scheme=" (hepburn)", meaning="love",
        )
        assert "ローマ字" in result  # ローマ字

    def test_chinese_dict_with_lang(self) -> None:
        result = l10n.t("dict.with_lang", "zh", word="amor", lang="拉丁语")
        assert "词汇" in result  # 词汇

    def test_korean_conj_simple(self) -> None:
        result = l10n.t("conj.simple", "ko", word="먹어요", lemma="먹다")
        assert "활용형" in result  # 활용형

    def test_arabic_nuance_exhibits(self) -> None:
        result = l10n.t("nuance.exhibits", "ar", word="x", type_label="formal register")
        assert "تُظهر" in result  # تُظهر

    def test_hebrew_agree_main(self) -> None:
        result = l10n.t(
            "agree.main", "he",
            mod="x", mod_pos="adjective", noun="y",
            features="gender and number", gender="masculine", number="singular",
        )
        assert "מסכימים" in result  # מסכימים


class TestFormattersIntegration:
    """Smoke tests through formatters.py to verify l10n is wired end-to-end."""

    def test_vocabulary_explanation_french(self) -> None:
        from backend.lesson.context import LessonContext
        from backend.lesson import formatters as fmt

        ctx = LessonContext(language_code="es", language_name="Spanish", l1_language="fr")
        result = fmt.vocabulary_explanation("libros", "noun", "libro", ctx)
        assert "est" in result
        assert "libro" in result

    def test_vocabulary_explanation_german(self) -> None:
        from backend.lesson.context import LessonContext
        from backend.lesson import formatters as fmt

        ctx = LessonContext(language_code="de", language_name="German", l1_language="de")
        result = fmt.vocabulary_explanation("Bücher", "noun", "Buch", ctx)
        assert "ist" in result
        assert "Substantiv" in result

    def test_idiom_explanation_japanese(self) -> None:
        from backend.lesson.context import LessonContext
        from backend.lesson import formatters as fmt

        ctx = LessonContext(language_code="ja", language_name="Japanese", l1_language="ja")
        result = fmt.idiom_explanation("花見", "flower viewing", ctx)
        assert "慣用句" in result or "意味" in result  # 慣用句 or 意味

    def test_dictionary_explanation_russian_with_lang(self) -> None:
        from backend.lesson.context import LessonContext
        from backend.lesson import formatters as fmt

        ctx = LessonContext(language_code="la", language_name="Latin", l1_language="ru")
        result = fmt.dictionary_explanation("amor", None, ctx)
        # Russian: lang_name("Latin", "ru") = "латыни"; template: "словарный запас {lang}"
        assert "латыни" in result  # латыни

    def test_transliteration_explanation_korean(self) -> None:
        from backend.lesson.context import LessonContext
        from backend.lesson import formatters as fmt

        ctx = LessonContext(language_code="ko", language_name="Korean", l1_language="ko")
        result = fmt.transliteration_explanation("사랑", "sarang", "", "love", ctx)
        assert "로마자" in result  # 로마자

    def test_agreement_explanation_chinese(self) -> None:
        from backend.lesson.context import LessonContext
        from backend.lesson import formatters as fmt

        ctx = LessonContext(language_code="es", language_name="Spanish", l1_language="zh")
        result = fmt.agreement_explanation(
            "grande", "adjective", "casa",
            ["gender", "number"], "feminine", "singular", ctx,
        )
        assert "一致" in result  # 一致

    def test_grammar_explanation_arabic(self) -> None:
        from backend.lesson.context import LessonContext
        from backend.lesson import formatters as fmt

        ctx = LessonContext(language_code="ar", language_name="Arabic", l1_language="ar")
        result = fmt.grammar_explanation("be_progressive", "ongoing action", ctx)
        assert "النمط" in result  # النمط


class TestGramLabel:
    """Tests for gram_label() and localize_features()."""

    # ── gram_label ────────────────────────────────────────────────────────────

    def test_english_identity(self) -> None:
        assert l10n.gram_label("tense", "present", "en") == "present"

    def test_unknown_l1_falls_back_to_english(self) -> None:
        assert l10n.gram_label("tense", "present", "xx") == "present"

    def test_unknown_category_falls_back_to_value(self) -> None:
        assert l10n.gram_label("invalid_cat", "foo", "es") == "foo"

    def test_unknown_value_falls_back_to_value(self) -> None:
        assert l10n.gram_label("tense", "nonexistent_tense", "es") == "nonexistent_tense"

    # ── person ────────────────────────────────────────────────────────────────

    def test_person_first_spanish(self) -> None:
        assert l10n.gram_label("person", "first", "es") == "primera"

    def test_person_second_french(self) -> None:
        assert l10n.gram_label("person", "second", "fr") == "deuxième"

    def test_person_third_german(self) -> None:
        assert l10n.gram_label("person", "third", "de") == "dritte"

    def test_person_russian_uses_ordinal_numeral(self) -> None:
        assert l10n.gram_label("person", "third", "ru") == "3-е"

    def test_person_portuguese_first(self) -> None:
        assert l10n.gram_label("person", "first", "pt") == "primeira"

    def test_person_italian_second(self) -> None:
        assert l10n.gram_label("person", "second", "it") == "seconda"

    # ── number ───────────────────────────────────────────────────────────────

    def test_number_singular_french(self) -> None:
        assert l10n.gram_label("number", "singular", "fr") == "singulier"

    def test_number_plural_german(self) -> None:
        assert l10n.gram_label("number", "plural", "de") == "Plural"

    def test_number_singular_russian(self) -> None:
        assert l10n.gram_label("number", "singular", "ru") == "единственное"

    def test_number_plural_italian(self) -> None:
        assert l10n.gram_label("number", "plural", "it") == "plurale"

    # ── tense ────────────────────────────────────────────────────────────────

    def test_tense_present_spanish(self) -> None:
        assert l10n.gram_label("tense", "present", "es") == "presente"

    def test_tense_imperfect_french(self) -> None:
        assert l10n.gram_label("tense", "imperfect", "fr") == "imparfait"

    def test_tense_future_german(self) -> None:
        assert l10n.gram_label("tense", "future", "de") == "Futur"

    def test_tense_past_russian(self) -> None:
        assert l10n.gram_label("tense", "past", "ru") == "прошедшее"

    def test_tense_pluperfect_portuguese(self) -> None:
        assert l10n.gram_label("tense", "pluperfect", "pt") == "mais-que-perfeito"

    def test_tense_preterite_italian(self) -> None:
        assert l10n.gram_label("tense", "preterite", "it") == "passato remoto"

    # ── mood ─────────────────────────────────────────────────────────────────

    def test_mood_indicative_spanish(self) -> None:
        assert l10n.gram_label("mood", "indicative", "es") == "indicativo"

    def test_mood_subjunctive_french(self) -> None:
        assert l10n.gram_label("mood", "subjunctive", "fr") == "subjonctif"

    def test_mood_imperative_german(self) -> None:
        assert l10n.gram_label("mood", "imperative", "de") == "Imperativ"

    def test_mood_indicative_russian(self) -> None:
        assert l10n.gram_label("mood", "indicative", "ru") == "изъявительное"

    def test_mood_conditional_italian(self) -> None:
        assert l10n.gram_label("mood", "conditional", "it") == "condizionale"

    # ── gender ───────────────────────────────────────────────────────────────

    def test_gender_masculine_spanish(self) -> None:
        assert l10n.gram_label("gender", "masculine", "es") == "masculino"

    def test_gender_feminine_french(self) -> None:
        assert l10n.gram_label("gender", "feminine", "fr") == "féminin"

    def test_gender_neuter_german(self) -> None:
        assert l10n.gram_label("gender", "neuter", "de") == "neutral"

    def test_gender_masculine_russian(self) -> None:
        assert l10n.gram_label("gender", "masculine", "ru") == "мужской"

    # ── case ─────────────────────────────────────────────────────────────────

    def test_case_nominative_german(self) -> None:
        assert l10n.gram_label("case", "nominative", "de") == "Nominativ"

    def test_case_accusative_russian(self) -> None:
        assert l10n.gram_label("case", "accusative", "ru") == "винительный"

    def test_case_dative_spanish(self) -> None:
        assert l10n.gram_label("case", "dative", "es") == "dativo"

    def test_case_instrumental_italian(self) -> None:
        assert l10n.gram_label("case", "instrumental", "it") == "strumentale"

    # ── aspect ───────────────────────────────────────────────────────────────

    def test_aspect_perfective_russian(self) -> None:
        assert l10n.gram_label("aspect", "perfective", "ru") == "совершенный"

    def test_aspect_imperfective_spanish(self) -> None:
        assert l10n.gram_label("aspect", "imperfective", "es") == "imperfectivo"

    # ── localize_features ─────────────────────────────────────────────────────

    def test_localize_features_empty_returns_fallback(self) -> None:
        result = l10n.localize_features([], "es")
        assert result == l10n.features_fallback("es")

    def test_localize_features_single_spanish(self) -> None:
        assert l10n.localize_features(["gender"], "es") == "género"

    def test_localize_features_two_spanish(self) -> None:
        result = l10n.localize_features(["gender", "number"], "es")
        assert result == "género y número"

    def test_localize_features_three_french(self) -> None:
        result = l10n.localize_features(["case", "gender", "number"], "fr")
        assert "et" in result
        assert "cas" in result
        assert "genre" in result

    def test_localize_features_russian_conjunction(self) -> None:
        result = l10n.localize_features(["gender", "number"], "ru")
        assert "и" in result

    def test_localize_features_english_identity(self) -> None:
        result = l10n.localize_features(["gender", "number"], "en")
        assert result == "gender and number"

    def test_localize_features_unknown_l1_uses_english(self) -> None:
        result = l10n.localize_features(["gender"], "xx")
        assert result == "gender"
