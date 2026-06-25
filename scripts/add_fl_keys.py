"""Add fl_* field-label i18n keys to all 11 language sections in annotations.js.

Idempotent — skips any language whose keys are already present.
Target: frontend/js/i18n/annotations.js  (NOT the thin i18n.js shim)
"""
import pathlib

NEW_KEYS = {
    'en': {
        'fl_surface_form': 'Surface form',
        'fl_aspect':       'Aspect',
        'fl_voice':        'Voice',
        'fl_construction': 'Construction',
        'fl_verb_class':   'Verb class',
        'fl_romanized':    'Romanized',
        'fl_form':         'Form',
        'fl_translation':  'Translation',
        'fl_gloss':        'Gloss',
        'fl_note':         'Note',
    },
    'es': {
        'fl_surface_form': 'Forma superficial',
        'fl_aspect':       'Aspecto',
        'fl_voice':        'Voz',
        'fl_construction': 'Construcción',
        'fl_verb_class':   'Clase verbal',
        'fl_romanized':    'Romanizado',
        'fl_form':         'Forma',
        'fl_translation':  'Traducción',
        'fl_gloss':        'Glosa',
        'fl_note':         'Nota',
    },
    'fr': {
        'fl_surface_form': 'Forme de surface',
        'fl_aspect':       'Aspect',
        'fl_voice':        'Voix',
        'fl_construction': 'Construction',
        'fl_verb_class':   'Classe verbale',
        'fl_romanized':    'Romanisé',
        'fl_form':         'Forme',
        'fl_translation':  'Traduction',
        'fl_gloss':        'Glose',
        'fl_note':         'Note',
    },
    'de': {
        'fl_surface_form': 'Oberflächenform',
        'fl_aspect':       'Aspekt',
        'fl_voice':        'Genus Verbi',
        'fl_construction': 'Konstruktion',
        'fl_verb_class':   'Verbklasse',
        'fl_romanized':    'Romanisiert',
        'fl_form':         'Form',
        'fl_translation':  'Übersetzung',
        'fl_gloss':        'Glosse',
        'fl_note':         'Anmerkung',
    },
    'it': {
        'fl_surface_form': 'Forma di superficie',
        'fl_aspect':       'Aspetto',
        'fl_voice':        'Diatesi',
        'fl_construction': 'Costruzione',
        'fl_verb_class':   'Classe verbale',
        'fl_romanized':    'Romanizzato',
        'fl_form':         'Forma',
        'fl_translation':  'Traduzione',
        'fl_gloss':        'Glossa',
        'fl_note':         'Nota',
    },
    'pt': {
        'fl_surface_form': 'Forma de superfície',
        'fl_aspect':       'Aspecto',
        'fl_voice':        'Voz',
        'fl_construction': 'Construção',
        'fl_verb_class':   'Classe verbal',
        'fl_romanized':    'Romanizado',
        'fl_form':         'Forma',
        'fl_translation':  'Tradução',
        'fl_gloss':        'Glosa',
        'fl_note':         'Nota',
    },
    'ru': {
        'fl_surface_form': 'Словоформа',
        'fl_aspect':       'Вид',
        'fl_voice':        'Залог',
        'fl_construction': 'Конструкция',
        'fl_verb_class':   'Класс глагола',
        'fl_romanized':    'Романизация',
        'fl_form':         'Форма',
        'fl_translation':  'Перевод',
        'fl_gloss':        'Глосса',
        'fl_note':         'Примечание',
    },
    'ja': {
        'fl_surface_form': '表層形',
        'fl_aspect':       'アスペクト',
        'fl_voice':        '態',
        'fl_construction': '構文',
        'fl_verb_class':   '動詞クラス',
        'fl_romanized':    'ローマ字',
        'fl_form':         '形',
        'fl_translation':  '翻訳',
        'fl_gloss':        'グロス',
        'fl_note':         'メモ',
    },
    'zh': {
        'fl_surface_form': '表层形式',
        'fl_aspect':       '体',
        'fl_voice':        '语态',
        'fl_construction': '结构',
        'fl_verb_class':   '动词类',
        'fl_romanized':    '罗马化',
        'fl_form':         '形式',
        'fl_translation':  '翻译',
        'fl_gloss':        '释义',
        'fl_note':         '注释',
    },
    'ar': {
        'fl_surface_form': 'الشكل السطحي',
        'fl_aspect':       'الجانب',
        'fl_voice':        'الصيغة',
        'fl_construction': 'التركيب',
        'fl_verb_class':   'فئة الفعل',
        'fl_romanized':    'روماني',
        'fl_form':         'الصيغة',
        'fl_translation':  'الترجمة',
        'fl_gloss':        'الشرح',
        'fl_note':         'ملاحظة',
    },
    'he': {
        'fl_surface_form': 'צורה משטחית',
        'fl_aspect':       'אופן',
        'fl_voice':        'גוף',
        'fl_construction': 'מבנה',
        'fl_verb_class':   'סוג פועל',
        'fl_romanized':    'תעתיק',
        'fl_form':         'צורה',
        'fl_translation':  'תרגום',
        'fl_gloss':        'פירוש',
        'fl_note':         'הערה',
    },
}

# Anchor: the fl_separable_verb line in each language section of annotations.js.
# New keys are inserted immediately after this line.
ANCHORS = {
    'en': '    fl_separable_verb: "Separable verb",',
    'es': '    fl_separable_verb: "Verbo separable",',
    'fr': '    fl_separable_verb: "Verbe séparable",',
    'de': '    fl_separable_verb: "Trennbares Verb",',
    'it': '    fl_separable_verb: "Verbo separabile",',
    'pt': '    fl_separable_verb: "Verbo separável",',
    'ru': '    fl_separable_verb: "Отделяемый глагол",',
    'ja': '    fl_separable_verb: "分離動詞",',
    'zh': '    fl_separable_verb: "可分动词",',
    'ar': '    fl_separable_verb: "فعل منفصل",',
    'he': '    fl_separable_verb: "פועל נפרד",',
}

path = pathlib.Path('frontend/js/i18n/annotations.js')
text = path.read_text(encoding='utf-8')

inserted = 0
for lang, anchor in ANCHORS.items():
    assert anchor in text, f'Anchor not found for lang={lang!r}: {anchor!r}'
    anchor_pos = text.index(anchor)
    section_snippet = text[anchor_pos:anchor_pos + 2000]
    first_key = next(iter(NEW_KEYS[lang]))
    if f'    {first_key}:' in section_snippet or f'    {first_key} :' in section_snippet:
        continue  # already present
    if lang == 'en':
        lines = '\n'.join(f'    {k}:{" " * (24 - len(k))} "{v}",' for k, v in NEW_KEYS[lang].items())
    else:
        lines = '\n'.join(f'    {k}{" " * (22 - len(k))}: "{v}",' for k, v in NEW_KEYS[lang].items())
    text = text.replace(anchor, anchor + '\n' + lines, 1)
    inserted += len(NEW_KEYS[lang])

path.write_text(text, encoding='utf-8')
print(f'Done — {inserted} fl_ key entries added (0 = all already present).')
