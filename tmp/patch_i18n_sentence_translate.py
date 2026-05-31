"""Inject sentence translation i18n keys after corpus_count in each language block."""
import pathlib
import sys

sys.stdout.reconfigure(encoding='utf-8')

ROOT   = pathlib.Path(__file__).resolve().parents[1]
TARGET = ROOT / 'frontend' / 'js' / 'i18n.js'

# Disambiguation: ES and PT both have corpus_count '{n} textos' —
# use the following placeholder_source_title line to tell them apart.
INSERTS = [
    (
        "corpus_count:             '{n} texts',",
        """\
    sentence_translate:       'Translate',
    sentence_translating:     'Translating…',
    sentence_translation_na:  'Translation unavailable',""",
    ),
    (
        "corpus_count:             '{n} textos',\n    placeholder_source_title: 'Título del artículo o capítulo',",
        """\
    sentence_translate:       'Traducir',
    sentence_translating:     'Traduciendo…',
    sentence_translation_na:  'Traducción no disponible',""",
    ),
    (
        "corpus_count:             '{n} textes',",
        """\
    sentence_translate:       'Traduire',
    sentence_translating:     'Traduction…',
    sentence_translation_na:  'Traduction indisponible',""",
    ),
    (
        "corpus_count:             '{n} Texte',",
        """\
    sentence_translate:       'Übersetzen',
    sentence_translating:     'Übersetzt…',
    sentence_translation_na:  'Übersetzung nicht verfügbar',""",
    ),
    (
        "corpus_count:             '{n} testi',",
        """\
    sentence_translate:       'Tradurre',
    sentence_translating:     'Traduzione…',
    sentence_translation_na:  'Traduzione non disponibile',""",
    ),
    (
        "corpus_count:             '{n} textos',\n    placeholder_source_title: 'Título do artigo ou capítulo',",
        """\
    sentence_translate:       'Traduzir',
    sentence_translating:     'A traduzir…',
    sentence_translation_na:  'Tradução indisponível',""",
    ),
    (
        "corpus_count:             '{n} текстов',",
        """\
    sentence_translate:       'Перевести',
    sentence_translating:     'Перевод…',
    sentence_translation_na:  'Перевод недоступен',""",
    ),
    (
        "corpus_count:             '{n}件',",
        """\
    sentence_translate:       '翻訳',
    sentence_translating:     '翻訳中…',
    sentence_translation_na:  '翻訳できません',""",
    ),
    (
        "corpus_count:             '{n}篇',",
        """\
    sentence_translate:       '翻译',
    sentence_translating:     '翻译中…',
    sentence_translation_na:  '翻译不可用',""",
    ),
    (
        "corpus_count:             '{n} نصوص',",
        """\
    sentence_translate:       'ترجمة',
    sentence_translating:     'جارٍ الترجمة…',
    sentence_translation_na:  'الترجمة غير متاحة',""",
    ),
    (
        "corpus_count:             '{n} טקסטים',",
        """\
    sentence_translate:       'תרגום',
    sentence_translating:     'מתרגם…',
    sentence_translation_na:  'תרגום אינו זמין',""",
    ),
]

content = TARGET.read_text(encoding='utf-8')

for marker, insert in INSERTS:
    idx = content.find(marker)
    if idx == -1:
        print(f'WARNING: marker not found: {repr(marker[:70])}', flush=True)
        continue
    # Insert after the first line of the marker (just after the corpus_count line)
    # Find end of corpus_count line within the marker
    first_newline = marker.index('\n') if '\n' in marker else len(marker)
    insert_at = idx + first_newline
    content = content[:insert_at] + '\n' + insert + content[insert_at:]
    print(f'OK: inserted after corpus_count in block: {marker[:50]}', flush=True)

TARGET.write_text(content, encoding='utf-8')
print('Done.', flush=True)
