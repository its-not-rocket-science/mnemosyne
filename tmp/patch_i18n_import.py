"""Patch i18n.js — insert corpus URL-import keys after corpus_continue_btn in all 11 blocks."""
from pathlib import Path

TARGET = Path("frontend/js/i18n.js")
lines = TARGET.read_text(encoding="utf-8").splitlines(keepends=True)

# Map: 1-based line number of corpus_continue_btn → insertion snippet
# Run:  grep -n corpus_continue_btn frontend/js/i18n.js
POSITIONS = {
    117:  (
        "    corpus_type_article:          'Web article',\n"
        "    corpus_import_url_btn:        '+ Import from URL',\n"
        "    corpus_import_url_placeholder: 'https://…',\n"
        "    corpus_import_url_lang_aria:  'Language',\n"
        "    corpus_import_url_submit:     'Import',\n"
        "    corpus_import_url_success:    'Imported: {title}',\n"
        "    corpus_import_url_error:      'Could not import that URL.',\n"
    ),
    834:  (
        "    corpus_type_article:          'Artículo web',\n"
        "    corpus_import_url_btn:        '+ Importar desde URL',\n"
        "    corpus_import_url_placeholder: 'https://…',\n"
        "    corpus_import_url_lang_aria:  'Idioma',\n"
        "    corpus_import_url_submit:     'Importar',\n"
        "    corpus_import_url_success:    'Importado: {title}',\n"
        "    corpus_import_url_error:      'No se pudo importar esa URL.',\n"
    ),
    1465: (
        "    corpus_type_article:          'Article web',\n"
        "    corpus_import_url_btn:        '+ Importer depuis URL',\n"
        "    corpus_import_url_placeholder: 'https://…',\n"
        "    corpus_import_url_lang_aria:  'Langue',\n"
        "    corpus_import_url_submit:     'Importer',\n"
        "    corpus_import_url_success:    'Importé : {title}',\n"
        "    corpus_import_url_error:      \"Impossible d'importer cette URL.\",\n"
    ),
    2096: (
        "    corpus_type_article:          'Webartikel',\n"
        "    corpus_import_url_btn:        '+ URL importieren',\n"
        "    corpus_import_url_placeholder: 'https://…',\n"
        "    corpus_import_url_lang_aria:  'Sprache',\n"
        "    corpus_import_url_submit:     'Importieren',\n"
        "    corpus_import_url_success:    'Importiert: {title}',\n"
        "    corpus_import_url_error:      'URL konnte nicht importiert werden.',\n"
    ),
    2727: (
        "    corpus_type_article:          'Articolo web',\n"
        "    corpus_import_url_btn:        '+ Importa da URL',\n"
        "    corpus_import_url_placeholder: 'https://…',\n"
        "    corpus_import_url_lang_aria:  'Lingua',\n"
        "    corpus_import_url_submit:     'Importa',\n"
        "    corpus_import_url_success:    'Importato: {title}',\n"
        "    corpus_import_url_error:      \"Impossibile importare quell'URL.\",\n"
    ),
    3358: (
        "    corpus_type_article:          'Artigo web',\n"
        "    corpus_import_url_btn:        '+ Importar de URL',\n"
        "    corpus_import_url_placeholder: 'https://…',\n"
        "    corpus_import_url_lang_aria:  'Idioma',\n"
        "    corpus_import_url_submit:     'Importar',\n"
        "    corpus_import_url_success:    'Importado: {title}',\n"
        "    corpus_import_url_error:      'Não foi possível importar esse URL.',\n"
    ),
    3989: (
        "    corpus_type_article:          'Статья',\n"
        "    corpus_import_url_btn:        '+ Импорт из URL',\n"
        "    corpus_import_url_placeholder: 'https://…',\n"
        "    corpus_import_url_lang_aria:  'Язык',\n"
        "    corpus_import_url_submit:     'Импорт',\n"
        "    corpus_import_url_success:    'Импортировано: {title}',\n"
        "    corpus_import_url_error:      'Не удалось импортировать URL.',\n"
    ),
    4620: (
        "    corpus_type_article:          'ウェブ記事',\n"
        "    corpus_import_url_btn:        '+ URLからインポート',\n"
        "    corpus_import_url_placeholder: 'https://…',\n"
        "    corpus_import_url_lang_aria:  '言語',\n"
        "    corpus_import_url_submit:     'インポート',\n"
        "    corpus_import_url_success:    'インポート完了: {title}',\n"
        "    corpus_import_url_error:      'URLをインポートできませんでした。',\n"
    ),
    5251: (
        "    corpus_type_article:          '网页文章',\n"
        "    corpus_import_url_btn:        '+ 从 URL 导入',\n"
        "    corpus_import_url_placeholder: 'https://…',\n"
        "    corpus_import_url_lang_aria:  '语言',\n"
        "    corpus_import_url_submit:     '导入',\n"
        "    corpus_import_url_success:    '已导入：{title}',\n"
        "    corpus_import_url_error:      '无法导入该 URL。',\n"
    ),
    5882: (
        "    corpus_type_article:          'مقال ويب',\n"
        "    corpus_import_url_btn:        '+ استيراد من URL',\n"
        "    corpus_import_url_placeholder: 'https://…',\n"
        "    corpus_import_url_lang_aria:  'اللغة',\n"
        "    corpus_import_url_submit:     'استيراد',\n"
        "    corpus_import_url_success:    'تم الاستيراد: {title}',\n"
        "    corpus_import_url_error:      'تعذّر استيراد هذا الرابط.',\n"
    ),
    6513: (
        "    corpus_type_article:          'מאמר אינטרנט',\n"
        "    corpus_import_url_btn:        '+ ייבוא מ-URL',\n"
        "    corpus_import_url_placeholder: 'https://…',\n"
        "    corpus_import_url_lang_aria:  'שפה',\n"
        "    corpus_import_url_submit:     'ייבוא',\n"
        "    corpus_import_url_success:    'יובא: {title}',\n"
        "    corpus_import_url_error:      'לא ניתן לייבא את ה-URL.',\n"
    ),
}

# Insert after each target line (1-based → 0-based index)
# Process in reverse order so line numbers stay valid
result = list(lines)
for lineno in sorted(POSITIONS.keys(), reverse=True):
    snippet = POSITIONS[lineno]
    idx = lineno - 1  # 0-based
    result.insert(idx + 1, snippet)

TARGET.write_text("".join(result), encoding="utf-8")
print(f"Patched {len(POSITIONS)} positions.")
