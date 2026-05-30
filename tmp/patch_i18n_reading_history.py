"""Inject reading_resume_btn into i18n.js after annotation_search_placeholder."""
from pathlib import Path

I18N = Path(__file__).parent.parent / 'frontend' / 'js' / 'i18n.js'

INSERTIONS = [
    ("annotation_search_placeholder: 'Search annotations…',",
     "    reading_resume_btn:           'Resume',"),
    ("annotation_search_placeholder: 'Buscar anotaciones…',",
     "    reading_resume_btn:           'Reanudar',"),
    ("annotation_search_placeholder: 'Chercher des annotations…',",
     "    reading_resume_btn:           'Reprendre',"),
    ("annotation_search_placeholder: 'Anmerkungen suchen…',",
     "    reading_resume_btn:           'Fortfahren',"),
    ("annotation_search_placeholder: 'Cerca annotazioni…',",
     "    reading_resume_btn:           'Riprendi',"),
    ("annotation_search_placeholder: 'Pesquisar anotações…',",
     "    reading_resume_btn:           'Retomar',"),
    ("annotation_search_placeholder: 'Искать аннотации…',",
     "    reading_resume_btn:           'Продолжить',"),
    ("annotation_search_placeholder: '注釈を検索…',",
     "    reading_resume_btn:           '再開',"),
    ("annotation_search_placeholder: '搜索注释…',",
     "    reading_resume_btn:           '继续',"),
    ("annotation_search_placeholder: 'البحث في التعليقات…',",
     "    reading_resume_btn:           'استئناف',"),
    ("annotation_search_placeholder: 'חפש הערות…',",
     "    reading_resume_btn:           'המשך',"),
]

text = I18N.read_text(encoding='utf-8')

for anchor, insertion in INSERTIONS:
    if anchor not in text:
        print(f'SKIP (not found): {anchor[:50].encode("ascii","replace").decode()}')
        continue
    if 'reading_resume_btn' in text[text.index(anchor):text.index(anchor) + 200]:
        print(f'SKIP (exists): {anchor[:50].encode("ascii","replace").decode()}')
        continue
    text = text.replace(anchor, anchor + '\n' + insertion, 1)
    print(f'OK: {anchor[:50].encode("ascii","replace").decode()}')

I18N.write_text(text, encoding='utf-8')
print('Done.')
