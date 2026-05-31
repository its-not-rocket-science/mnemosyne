"""Patch i18n.js to add corpus polish keys after corpus_vocab_density_label in each locale block."""
import pathlib, re

I18N = pathlib.Path(__file__).parent.parent / "frontend" / "js" / "i18n.js"
src = I18N.read_text(encoding="utf-8")
lines = src.splitlines(keepends=True)

# Locale-specific translations indexed by line number of corpus_vocab_density_label
# (line numbers are 1-based; processing in reverse to preserve offsets)
INSERTIONS = [
    # (line_number, insertion_lines)
    # HE - line 6667
    (6667, [
        "    corpus_collection_all:        'כל המדפים',\n",
        "    corpus_collection_new:        'מדף חדש…',\n",
        "    corpus_collection_add:        'הוסף למדף',\n",
        "    corpus_bulk_select:           'בחר',\n",
        "    corpus_bulk_done:             'סיום',\n",
        "    corpus_bulk_tag_add:          'הוסף תגית',\n",
        "    corpus_bulk_tag_remove:       'הסר תגית',\n",
        "    corpus_import_log_btn:        'היסטוריית יבוא',\n",
        "    corpus_import_log_empty:      'אין היסטוריה',\n",
        "    corpus_import_log_ok:         'יובא',\n",
        "    corpus_import_log_fail:       'נכשל',\n",
        "    corpus_import_log_dup:        'כפול',\n",
    ]),
    # AR - line 6022
    (6022, [
        "    corpus_collection_all:        'كل الرفوف',\n",
        "    corpus_collection_new:        'رف جديد…',\n",
        "    corpus_collection_add:        'أضف إلى الرف',\n",
        "    corpus_bulk_select:           'تحديد',\n",
        "    corpus_bulk_done:             'تمام',\n",
        "    corpus_bulk_tag_add:          'إضافة وسم',\n",
        "    corpus_bulk_tag_remove:       'إزالة وسم',\n",
        "    corpus_import_log_btn:        'سجل الاستيراد',\n",
        "    corpus_import_log_empty:      'لا يوجد سجل',\n",
        "    corpus_import_log_ok:         'تم الاستيراد',\n",
        "    corpus_import_log_fail:       'فشل',\n",
        "    corpus_import_log_dup:        'مكرر',\n",
    ]),
    # ZH - line 5377
    (5377, [
        "    corpus_collection_all:        '全部书架',\n",
        "    corpus_collection_new:        '新建书架…',\n",
        "    corpus_collection_add:        '添加到书架',\n",
        "    corpus_bulk_select:           '选择',\n",
        "    corpus_bulk_done:             '完成',\n",
        "    corpus_bulk_tag_add:          '添加标签',\n",
        "    corpus_bulk_tag_remove:       '移除标签',\n",
        "    corpus_import_log_btn:        '导入历史',\n",
        "    corpus_import_log_empty:      '无历史记录',\n",
        "    corpus_import_log_ok:         '已导入',\n",
        "    corpus_import_log_fail:       '失败',\n",
        "    corpus_import_log_dup:        '重复',\n",
    ]),
    # JA - line 4732
    (4732, [
        "    corpus_collection_all:        '全シェルフ',\n",
        "    corpus_collection_new:        '新しいシェルフ…',\n",
        "    corpus_collection_add:        'シェルフに追加',\n",
        "    corpus_bulk_select:           '選択',\n",
        "    corpus_bulk_done:             '完了',\n",
        "    corpus_bulk_tag_add:          'タグを追加',\n",
        "    corpus_bulk_tag_remove:       'タグを削除',\n",
        "    corpus_import_log_btn:        'インポート履歴',\n",
        "    corpus_import_log_empty:      '履歴なし',\n",
        "    corpus_import_log_ok:         'インポート済み',\n",
        "    corpus_import_log_fail:       '失敗',\n",
        "    corpus_import_log_dup:        '重複',\n",
    ]),
    # RU - line 4087
    (4087, [
        "    corpus_collection_all:        'Все полки',\n",
        "    corpus_collection_new:        'Новая полка…',\n",
        "    corpus_collection_add:        'Добавить на полку',\n",
        "    corpus_bulk_select:           'Выбрать',\n",
        "    corpus_bulk_done:             'Готово',\n",
        "    corpus_bulk_tag_add:          'Добавить тег',\n",
        "    corpus_bulk_tag_remove:       'Удалить тег',\n",
        "    corpus_import_log_btn:        'История импорта',\n",
        "    corpus_import_log_empty:      'Нет истории',\n",
        "    corpus_import_log_ok:         'Импортировано',\n",
        "    corpus_import_log_fail:       'Ошибка',\n",
        "    corpus_import_log_dup:        'Дубликат',\n",
    ]),
    # PT - line 3442
    (3442, [
        "    corpus_collection_all:        'Todas as prateleiras',\n",
        "    corpus_collection_new:        'Nova prateleira…',\n",
        "    corpus_collection_add:        'Adicionar à prateleira',\n",
        "    corpus_bulk_select:           'Selecionar',\n",
        "    corpus_bulk_done:             'Concluído',\n",
        "    corpus_bulk_tag_add:          'Adicionar etiqueta',\n",
        "    corpus_bulk_tag_remove:       'Remover etiqueta',\n",
        "    corpus_import_log_btn:        'Histórico de importação',\n",
        "    corpus_import_log_empty:      'Sem histórico',\n",
        "    corpus_import_log_ok:         'Importado',\n",
        "    corpus_import_log_fail:       'Falhou',\n",
        "    corpus_import_log_dup:        'Duplicado',\n",
    ]),
    # IT - line 2797
    (2797, [
        "    corpus_collection_all:        'Tutti gli scaffali',\n",
        "    corpus_collection_new:        'Nuovo scaffale…',\n",
        "    corpus_collection_add:        'Aggiungi allo scaffale',\n",
        "    corpus_bulk_select:           'Seleziona',\n",
        "    corpus_bulk_done:             'Fine',\n",
        "    corpus_bulk_tag_add:          'Aggiungi tag',\n",
        "    corpus_bulk_tag_remove:       'Rimuovi tag',\n",
        "    corpus_import_log_btn:        'Storico importazioni',\n",
        "    corpus_import_log_empty:      'Nessuno storico',\n",
        "    corpus_import_log_ok:         'Importato',\n",
        "    corpus_import_log_fail:       'Fallito',\n",
        "    corpus_import_log_dup:        'Duplicato',\n",
    ]),
    # DE - line 2152
    (2152, [
        "    corpus_collection_all:        'Alle Regale',\n",
        "    corpus_collection_new:        'Neues Regal…',\n",
        "    corpus_collection_add:        'Zum Regal hinzufügen',\n",
        "    corpus_bulk_select:           'Auswählen',\n",
        "    corpus_bulk_done:             'Fertig',\n",
        "    corpus_bulk_tag_add:          'Tag hinzufügen',\n",
        "    corpus_bulk_tag_remove:       'Tag entfernen',\n",
        "    corpus_import_log_btn:        'Importverlauf',\n",
        "    corpus_import_log_empty:      'Kein Verlauf',\n",
        "    corpus_import_log_ok:         'Importiert',\n",
        "    corpus_import_log_fail:       'Fehlgeschlagen',\n",
        "    corpus_import_log_dup:        'Duplikat',\n",
    ]),
    # FR - line 1507
    (1507, [
        "    corpus_collection_all:        'Tous les rayons',\n",
        "    corpus_collection_new:        'Nouveau rayon…',\n",
        "    corpus_collection_add:        'Ajouter au rayon',\n",
        "    corpus_bulk_select:           'Sélectionner',\n",
        "    corpus_bulk_done:             'Terminé',\n",
        "    corpus_bulk_tag_add:          'Ajouter un tag',\n",
        "    corpus_bulk_tag_remove:       'Supprimer le tag',\n",
        "    corpus_import_log_btn:        'Historique des imports',\n",
        "    corpus_import_log_empty:      'Aucun historique',\n",
        "    corpus_import_log_ok:         'Importé',\n",
        "    corpus_import_log_fail:       'Échec',\n",
        "    corpus_import_log_dup:        'Doublon',\n",
    ]),
    # ES - line 862
    (862, [
        "    corpus_collection_all:        'Todos los estantes',\n",
        "    corpus_collection_new:        'Nuevo estante…',\n",
        "    corpus_collection_add:        'Añadir al estante',\n",
        "    corpus_bulk_select:           'Seleccionar',\n",
        "    corpus_bulk_done:             'Listo',\n",
        "    corpus_bulk_tag_add:          'Añadir etiqueta',\n",
        "    corpus_bulk_tag_remove:       'Quitar etiqueta',\n",
        "    corpus_import_log_btn:        'Historial de importación',\n",
        "    corpus_import_log_empty:      'Sin historial',\n",
        "    corpus_import_log_ok:         'Importado',\n",
        "    corpus_import_log_fail:       'Error',\n",
        "    corpus_import_log_dup:        'Duplicado',\n",
    ]),
    # EN - line 131
    (131, [
        "    corpus_collection_all:        'All shelves',\n",
        "    corpus_collection_new:        'New shelf…',\n",
        "    corpus_collection_add:        'Add to shelf',\n",
        "    corpus_bulk_select:           'Select',\n",
        "    corpus_bulk_done:             'Done',\n",
        "    corpus_bulk_tag_add:          'Add tag',\n",
        "    corpus_bulk_tag_remove:       'Remove tag',\n",
        "    corpus_import_log_btn:        'Import history',\n",
        "    corpus_import_log_empty:      'No import history',\n",
        "    corpus_import_log_ok:         'Imported',\n",
        "    corpus_import_log_fail:       'Failed',\n",
        "    corpus_import_log_dup:        'Duplicate',\n",
    ]),
]

# Process in reverse line-number order so insertions don't shift subsequent positions
for line_no, new_lines in sorted(INSERTIONS, key=lambda x: -x[0]):
    # Insert AFTER line_no (0-based index = line_no - 1, insert after means splice at line_no)
    idx = line_no  # 0-based: line_no is after the target line (1-based)
    lines[idx:idx] = new_lines

I18N.write_text("".join(lines), encoding="utf-8")
print(f"Patched {I18N} — added {len(INSERTIONS) * 12} lines")
