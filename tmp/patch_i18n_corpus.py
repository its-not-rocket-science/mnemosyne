"""Inject corpus browser i18n keys after stats_today in each language block."""
import pathlib
import sys

sys.stdout.reconfigure(encoding='utf-8')

ROOT   = pathlib.Path(__file__).resolve().parents[1]
TARGET = ROOT / 'frontend' / 'js' / 'i18n.js'

INSERTS = {
    "stats_today:            'Today',": """\
    corpus_browser_btn:       'Corpus',
    corpus_browser_heading:   'Text library',
    corpus_filter_search_placeholder: 'Search titles…',
    corpus_type_all:          'All types',
    corpus_type_pasted:       'Pasted text',
    corpus_type_file:         'Uploaded file',
    corpus_empty:             'No texts found',
    corpus_load_more:         'Load more',
    corpus_open_btn:          'Open',
    corpus_char_count:        '{n} chars',
    corpus_count:             '{n} texts',""",

    "stats_today:            'Hoy',": """\
    corpus_browser_btn:       'Corpus',
    corpus_browser_heading:   'Biblioteca de textos',
    corpus_filter_search_placeholder: 'Buscar títulos…',
    corpus_type_all:          'Todos los tipos',
    corpus_type_pasted:       'Texto pegado',
    corpus_type_file:         'Archivo subido',
    corpus_empty:             'No se encontraron textos',
    corpus_load_more:         'Cargar más',
    corpus_open_btn:          'Abrir',
    corpus_char_count:        '{n} caracteres',
    corpus_count:             '{n} textos',""",

    "stats_today:            \"Aujourd'hui\",": """\
    corpus_browser_btn:       'Corpus',
    corpus_browser_heading:   'Bibliothèque de textes',
    corpus_filter_search_placeholder: 'Chercher des titres…',
    corpus_type_all:          'Tous les types',
    corpus_type_pasted:       'Texte collé',
    corpus_type_file:         'Fichier importé',
    corpus_empty:             'Aucun texte trouvé',
    corpus_load_more:         'Charger plus',
    corpus_open_btn:          'Ouvrir',
    corpus_char_count:        '{n} caractères',
    corpus_count:             '{n} textes',""",

    "stats_today:            'Heute',": """\
    corpus_browser_btn:       'Korpus',
    corpus_browser_heading:   'Textbibliothek',
    corpus_filter_search_placeholder: 'Titel suchen…',
    corpus_type_all:          'Alle Typen',
    corpus_type_pasted:       'Eingefügter Text',
    corpus_type_file:         'Hochgeladene Datei',
    corpus_empty:             'Keine Texte gefunden',
    corpus_load_more:         'Mehr laden',
    corpus_open_btn:          'Öffnen',
    corpus_char_count:        '{n} Zeichen',
    corpus_count:             '{n} Texte',""",

    "stats_today:            'Oggi',": """\
    corpus_browser_btn:       'Corpus',
    corpus_browser_heading:   'Libreria di testi',
    corpus_filter_search_placeholder: 'Cerca titoli…',
    corpus_type_all:          'Tutti i tipi',
    corpus_type_pasted:       'Testo incollato',
    corpus_type_file:         'File caricato',
    corpus_empty:             'Nessun testo trovato',
    corpus_load_more:         'Carica altro',
    corpus_open_btn:          'Apri',
    corpus_char_count:        '{n} caratteri',
    corpus_count:             '{n} testi',""",

    "stats_today:            'Hoje',": """\
    corpus_browser_btn:       'Corpus',
    corpus_browser_heading:   'Biblioteca de textos',
    corpus_filter_search_placeholder: 'Pesquisar títulos…',
    corpus_type_all:          'Todos os tipos',
    corpus_type_pasted:       'Texto colado',
    corpus_type_file:         'Ficheiro carregado',
    corpus_empty:             'Nenhum texto encontrado',
    corpus_load_more:         'Carregar mais',
    corpus_open_btn:          'Abrir',
    corpus_char_count:        '{n} caracteres',
    corpus_count:             '{n} textos',""",

    "stats_today:            'Сегодня',": """\
    corpus_browser_btn:       'Корпус',
    corpus_browser_heading:   'Библиотека текстов',
    corpus_filter_search_placeholder: 'Поиск по названиям…',
    corpus_type_all:          'Все типы',
    corpus_type_pasted:       'Вставленный текст',
    corpus_type_file:         'Загруженный файл',
    corpus_empty:             'Тексты не найдены',
    corpus_load_more:         'Загрузить ещё',
    corpus_open_btn:          'Открыть',
    corpus_char_count:        '{n} симв.',
    corpus_count:             '{n} текстов',""",

    "stats_today:            '今日',": """\
    corpus_browser_btn:       'コーパス',
    corpus_browser_heading:   'テキスト一覧',
    corpus_filter_search_placeholder: 'タイトルを検索…',
    corpus_type_all:          'すべての種類',
    corpus_type_pasted:       '貼り付けたテキスト',
    corpus_type_file:         'アップロードファイル',
    corpus_empty:             'テキストが見つかりません',
    corpus_load_more:         'さらに読み込む',
    corpus_open_btn:          '開く',
    corpus_char_count:        '{n}文字',
    corpus_count:             '{n}件',""",

    "stats_today:            '今天',": """\
    corpus_browser_btn:       '语料库',
    corpus_browser_heading:   '文本库',
    corpus_filter_search_placeholder: '搜索标题…',
    corpus_type_all:          '所有类型',
    corpus_type_pasted:       '粘贴文本',
    corpus_type_file:         '上传文件',
    corpus_empty:             '未找到文本',
    corpus_load_more:         '加载更多',
    corpus_open_btn:          '打开',
    corpus_char_count:        '{n}字符',
    corpus_count:             '{n}篇',""",

    "stats_today:            'اليوم',": """\
    corpus_browser_btn:       'المدونة',
    corpus_browser_heading:   'مكتبة النصوص',
    corpus_filter_search_placeholder: 'البحث في العناوين…',
    corpus_type_all:          'جميع الأنواع',
    corpus_type_pasted:       'نص ملصق',
    corpus_type_file:         'ملف مُحمَّل',
    corpus_empty:             'لا توجد نصوص',
    corpus_load_more:         'تحميل المزيد',
    corpus_open_btn:          'فتح',
    corpus_char_count:        '{n} حرف',
    corpus_count:             '{n} نصوص',""",

    "stats_today:            'היום',": """\
    corpus_browser_btn:       'קורפוס',
    corpus_browser_heading:   'ספריית טקסטים',
    corpus_filter_search_placeholder: 'חיפוש כותרות…',
    corpus_type_all:          'כל הסוגים',
    corpus_type_pasted:       'טקסט מודבק',
    corpus_type_file:         'קובץ שהועלה',
    corpus_empty:             'לא נמצאו טקסטים',
    corpus_load_more:         'טעינת עוד',
    corpus_open_btn:          'פתח',
    corpus_char_count:        '{n} תווים',
    corpus_count:             '{n} טקסטים',""",
}

content = TARGET.read_text(encoding='utf-8')

for marker, insert in INSERTS.items():
    idx = content.find(marker)
    if idx == -1:
        print(f'WARNING: marker not found: {marker[:60]}', flush=True)
        continue
    insert_at = idx + len(marker)
    content = content[:insert_at] + '\n' + insert + content[insert_at:]
    print(f'OK: inserted after stats_today in block containing: {marker[13:30]}', flush=True)

TARGET.write_text(content, encoding='utf-8')
print('Done.', flush=True)
