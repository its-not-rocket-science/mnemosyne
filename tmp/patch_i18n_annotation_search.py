"""Inject annotation_search_label and annotation_search_placeholder into i18n.js.

Anchors after corpus_drills_btn in each language block.
"""
from pathlib import Path

I18N = Path(__file__).parent.parent / 'frontend' / 'js' / 'i18n.js'

INSERTIONS = [
    # (anchor line substring, new lines to insert after)
    ("corpus_drills_btn:        'Practice confusables',",
     "    annotation_search_label:      'Search annotations',\n"
     "    annotation_search_placeholder: 'Search annotations…',"),
    ("corpus_drills_btn:        'Practicar confusiones',",
     "    annotation_search_label:      'Buscar anotaciones',\n"
     "    annotation_search_placeholder: 'Buscar anotaciones…',"),
    ("corpus_drills_btn:        'Pratiquer les confusibles',",
     "    annotation_search_label:      'Chercher des annotations',\n"
     "    annotation_search_placeholder: 'Chercher des annotations…',"),
    ("corpus_drills_btn:        'Verwechslungspaare üben',",
     "    annotation_search_label:      'Anmerkungen suchen',\n"
     "    annotation_search_placeholder: 'Anmerkungen suchen…',"),
    ("corpus_drills_btn:        'Praticare i confusabili',",
     "    annotation_search_label:      'Cerca annotazioni',\n"
     "    annotation_search_placeholder: 'Cerca annotazioni…',"),
    ("corpus_drills_btn:        'Praticar confusões',",
     "    annotation_search_label:      'Pesquisar anotações',\n"
     "    annotation_search_placeholder: 'Pesquisar anotações…',"),
    ("corpus_drills_btn:        'Тренировка похожих слов',",
     "    annotation_search_label:      'Искать аннотации',\n"
     "    annotation_search_placeholder: 'Искать аннотации…',"),
    ("corpus_drills_btn:        '紛らわしい語を練習',",
     "    annotation_search_label:      '注釈を検索',\n"
     "    annotation_search_placeholder: '注釈を検索…',"),
    ("corpus_drills_btn:        '练习易混词',",
     "    annotation_search_label:      '搜索注释',\n"
     "    annotation_search_placeholder: '搜索注释…',"),
    ("corpus_drills_btn:        'تدريب على المتشابهات',",
     "    annotation_search_label:      'البحث في التعليقات',\n"
     "    annotation_search_placeholder: 'البحث في التعليقات…',"),
    ("corpus_drills_btn:        'תרגול מילים מבלבלות',",
     "    annotation_search_label:      'חפש הערות',\n"
     "    annotation_search_placeholder: 'חפש הערות…',"),
]

text = I18N.read_text(encoding='utf-8')

for anchor, insertion in INSERTIONS:
    if anchor not in text:
        print(f'SKIP (not found): {anchor[:60].encode("ascii","replace").decode()}')
        continue
    if 'annotation_search_label' in text[text.index(anchor):text.index(anchor) + 300]:
        print(f'SKIP (already present): {anchor[:60].encode("ascii","replace").decode()}')
        continue
    text = text.replace(anchor, anchor + '\n' + insertion, 1)
    print(f'OK: {anchor[:60].encode("ascii","replace").decode()}')

I18N.write_text(text, encoding='utf-8')
print('Done.')
