"""Patch i18n.js — insert corpus note/density/dedup keys after corpus_import_url_error."""
from pathlib import Path

TARGET = Path("frontend/js/i18n.js")
lines = TARGET.read_text(encoding="utf-8").splitlines(keepends=True)

POSITIONS = {
    124:  (
        "    corpus_import_url_duplicate:  'Already imported: {title}',\n"
        "    corpus_note_add:              'Add note…',\n"
        "    corpus_note_placeholder:      'Add a note about this text…',\n"
        "    corpus_vocab_density_label:   'Known vocab',\n"
    ),
    848:  (
        "    corpus_import_url_duplicate:  'Ya importado: {title}',\n"
        "    corpus_note_add:              'Añadir nota…',\n"
        "    corpus_note_placeholder:      'Añade una nota sobre este texto…',\n"
        "    corpus_vocab_density_label:   'Vocabulario conocido',\n"
    ),
    1486: (
        "    corpus_import_url_duplicate:  'Déjà importé : {title}',\n"
        "    corpus_note_add:              'Ajouter une note…',\n"
        "    corpus_note_placeholder:      'Ajoutez une note sur ce texte…',\n"
        "    corpus_vocab_density_label:   'Vocabulaire connu',\n"
    ),
    2124: (
        "    corpus_import_url_duplicate:  'Bereits importiert: {title}',\n"
        "    corpus_note_add:              'Notiz hinzufügen…',\n"
        "    corpus_note_placeholder:      'Füge eine Notiz zu diesem Text hinzu…',\n"
        "    corpus_vocab_density_label:   'Bekannter Wortschatz',\n"
    ),
    2762: (
        "    corpus_import_url_duplicate:  'Già importato: {title}',\n"
        "    corpus_note_add:              'Aggiungi nota…',\n"
        "    corpus_note_placeholder:      'Aggiungi una nota su questo testo…',\n"
        "    corpus_vocab_density_label:   'Vocabolario noto',\n"
    ),
    3400: (
        "    corpus_import_url_duplicate:  'Já importado: {title}',\n"
        "    corpus_note_add:              'Adicionar nota…',\n"
        "    corpus_note_placeholder:      'Adicione uma nota sobre este texto…',\n"
        "    corpus_vocab_density_label:   'Vocabulário conhecido',\n"
    ),
    4038: (
        "    corpus_import_url_duplicate:  'Уже импортировано: {title}',\n"
        "    corpus_note_add:              'Добавить заметку…',\n"
        "    corpus_note_placeholder:      'Добавьте заметку об этом тексте…',\n"
        "    corpus_vocab_density_label:   'Известные слова',\n"
    ),
    4676: (
        "    corpus_import_url_duplicate:  'インポート済み: {title}',\n"
        "    corpus_note_add:              'メモを追加…',\n"
        "    corpus_note_placeholder:      'このテキストにメモを追加…',\n"
        "    corpus_vocab_density_label:   '既知の単語',\n"
    ),
    5314: (
        "    corpus_import_url_duplicate:  '已导入：{title}',\n"
        "    corpus_note_add:              '添加备注…',\n"
        "    corpus_note_placeholder:      '添加关于此文本的备注…',\n"
        "    corpus_vocab_density_label:   '已知词汇',\n"
    ),
    5952: (
        "    corpus_import_url_duplicate:  'تم الاستيراد مسبقاً: {title}',\n"
        "    corpus_note_add:              'إضافة ملاحظة…',\n"
        "    corpus_note_placeholder:      'أضف ملاحظة حول هذا النص…',\n"
        "    corpus_vocab_density_label:   'مفردات معروفة',\n"
    ),
    6590: (
        "    corpus_import_url_duplicate:  'יובא כבר: {title}',\n"
        "    corpus_note_add:              'הוספת הערה…',\n"
        "    corpus_note_placeholder:      'הוסף הערה לגבי טקסט זה…',\n"
        "    corpus_vocab_density_label:   'אוצר מילים מוכר',\n"
    ),
}

result = list(lines)
for lineno in sorted(POSITIONS.keys(), reverse=True):
    snippet = POSITIONS[lineno]
    idx = lineno - 1
    result.insert(idx + 1, snippet)

TARGET.write_text("".join(result), encoding="utf-8")
print(f"Patched {len(POSITIONS)} positions.")
