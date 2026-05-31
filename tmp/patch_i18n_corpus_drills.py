"""Inject corpus_drills_btn i18n key after sentence_translation_na in each language block."""
import pathlib
import sys

sys.stdout.reconfigure(encoding='utf-8')

ROOT   = pathlib.Path(__file__).resolve().parents[1]
TARGET = ROOT / 'frontend' / 'js' / 'i18n.js'

# sentence_translation_na is unique per language block, use it as anchor.
INSERTS = [
    ("sentence_translation_na:  'Translation unavailable',",
     "    corpus_drills_btn:        'Practice confusables',"),
    ("sentence_translation_na:  'Traducción no disponible',",
     "    corpus_drills_btn:        'Practicar confusiones',"),
    ("sentence_translation_na:  'Traduction indisponible',",
     "    corpus_drills_btn:        'Pratiquer les confusibles',"),
    ("sentence_translation_na:  'Übersetzung nicht verfügbar',",
     "    corpus_drills_btn:        'Verwechslungspaare üben',"),
    ("sentence_translation_na:  'Traduzione non disponibile',",
     "    corpus_drills_btn:        'Praticare i confusabili',"),
    ("sentence_translation_na:  'Tradução indisponível',",
     "    corpus_drills_btn:        'Praticar confusões',"),
    ("sentence_translation_na:  'Перевод недоступен',",
     "    corpus_drills_btn:        'Тренировка похожих слов',"),
    ("sentence_translation_na:  '翻訳できません',",
     "    corpus_drills_btn:        '紛らわしい語を練習',"),
    ("sentence_translation_na:  '翻译不可用',",
     "    corpus_drills_btn:        '练习易混词',"),
    ("sentence_translation_na:  'الترجمة غير متاحة',",
     "    corpus_drills_btn:        'تدريب على المتشابهات',"),
    ("sentence_translation_na:  'תרגום אינו זמין',",
     "    corpus_drills_btn:        'תרגול מילים מבלבלות',"),
]

content = TARGET.read_text(encoding='utf-8')

for marker, insert in INSERTS:
    idx = content.find(marker)
    if idx == -1:
        print(f'WARNING: marker not found: {repr(marker[:60])}', flush=True)
        continue
    insert_at = idx + len(marker)
    content = content[:insert_at] + '\n' + insert + content[insert_at:]
    print(f'OK: {marker[:50]}', flush=True)

TARGET.write_text(content, encoding='utf-8')
print('Done.', flush=True)
