"""Patch i18n.js — add 9 offline-badge keys after corpus_import_log_dup in each locale."""
import pathlib

I18N = pathlib.Path(__file__).parent.parent / "frontend" / "js" / "i18n.js"
lines = I18N.read_text(encoding="utf-8").splitlines(keepends=True)

# Line numbers of corpus_import_log_dup in each locale (1-based), from grep output.
# Process in reverse so insertions don't shift subsequent positions.
INSERTIONS = [
    (6799, [  # HE
        "    offline_queued:               'לא מחובר · {n} בתור',\n",
        "    offline_pending:              '{n} בתור',\n",
        "    offline_syncing:              'מסנכרן…',\n",
        "    offline_synced:               'סונכרן {n}',\n",
        "    offline_jwt_expired:          'התחבר לסנכרון · {n}',\n",
        "    offline_explain_heading:      'סקירות בתור',\n",
        "    offline_explain_offline:      'יש לך {n} סקירות שמורות. הן יסתנכרנו אוטומטית עם ההתחברות.',\n",
        "    offline_explain_pending:      'יש לך {n} סקירות מוכנות לסנכרון.',\n",
        "    offline_explain_expired:      'הפגישה פגה. התחבר שוב לסנכרן {n} סקירות.',\n",
    ]),
    (6142, [  # AR
        "    offline_queued:               'غير متصل · {n} في الانتظار',\n",
        "    offline_pending:              '{n} في الانتظار',\n",
        "    offline_syncing:              'جارٍ المزامنة…',\n",
        "    offline_synced:               'تمت مزامنة {n}',\n",
        "    offline_jwt_expired:          'سجّل الدخول للمزامنة · {n}',\n",
        "    offline_explain_heading:      'مراجعات في الانتظار',\n",
        "    offline_explain_offline:      'لديك {n} مراجعة محفوظة. ستتم المزامنة تلقائياً عند إعادة الاتصال.',\n",
        "    offline_explain_pending:      'لديك {n} مراجعة جاهزة للمزامنة.',\n",
        "    offline_explain_expired:      'انتهت الجلسة. سجّل الدخول لمزامنة {n} مراجعة.',\n",
    ]),
    (5485, [  # ZH
        "    offline_queued:               '离线 · {n} 条待处理',\n",
        "    offline_pending:              '{n} 条待处理',\n",
        "    offline_syncing:              '同步中…',\n",
        "    offline_synced:               '已同步 {n} 条',\n",
        "    offline_jwt_expired:          '登录以同步 · {n}',\n",
        "    offline_explain_heading:      '待处理的复习',\n",
        "    offline_explain_offline:      '您有 {n} 条复习已离线保存，重新连接后将自动同步。',\n",
        "    offline_explain_pending:      '您有 {n} 条复习等待同步。',\n",
        "    offline_explain_expired:      '会话已过期，请重新登录以同步 {n} 条复习。',\n",
    ]),
    (4828, [  # JA
        "    offline_queued:               'オフライン · {n} 件待機中',\n",
        "    offline_pending:              '{n} 件待機中',\n",
        "    offline_syncing:              '同期中…',\n",
        "    offline_synced:               '{n} 件同期済み',\n",
        "    offline_jwt_expired:          'ログインして同期 · {n}',\n",
        "    offline_explain_heading:      '待機中の復習',\n",
        "    offline_explain_offline:      '{n} 件の復習がオフラインで保存されています。再接続時に自動同期されます。',\n",
        "    offline_explain_pending:      '{n} 件の復習が同期待ちです。',\n",
        "    offline_explain_expired:      'セッションが期限切れです。{n} 件を同期するには再ログインしてください。',\n",
    ]),
    (4171, [  # RU
        "    offline_queued:               'Офлайн · {n} в очереди',\n",
        "    offline_pending:              '{n} в очереди',\n",
        "    offline_syncing:              'Синхронизация…',\n",
        "    offline_synced:               'Синхронизировано {n}',\n",
        "    offline_jwt_expired:          'Войдите для синхронизации · {n}',\n",
        "    offline_explain_heading:      'Отложенные оценки',\n",
        "    offline_explain_offline:      'У вас {n} сохранённых оценок. Они синхронизируются при подключении.',\n",
        "    offline_explain_pending:      'У вас {n} оценок готовы к синхронизации.',\n",
        "    offline_explain_expired:      'Сессия истекла. Войдите для синхронизации {n} оценок.',\n",
    ]),
    (3514, [  # PT
        "    offline_queued:               'Offline · {n} em fila',\n",
        "    offline_pending:              '{n} em fila',\n",
        "    offline_syncing:              'Sincronizando…',\n",
        "    offline_synced:               '{n} sincronizadas',\n",
        "    offline_jwt_expired:          'Inicia sessão para sincronizar · {n}',\n",
        "    offline_explain_heading:      'Revisões em fila',\n",
        "    offline_explain_offline:      'Tens {n} revisão(ões) guardadas. Serão sincronizadas ao reconectar.',\n",
        "    offline_explain_pending:      'Tens {n} revisão(ões) prontas para sincronizar.',\n",
        "    offline_explain_expired:      'Sessão expirada. Faz login para sincronizar {n} revisão(ões).',\n",
    ]),
    (2857, [  # IT
        "    offline_queued:               'Offline · {n} in coda',\n",
        "    offline_pending:              '{n} in coda',\n",
        "    offline_syncing:              'Sincronizzazione…',\n",
        "    offline_synced:               '{n} sincronizzate',\n",
        "    offline_jwt_expired:          'Accedi per sincronizzare · {n}',\n",
        "    offline_explain_heading:      'Revisioni in coda',\n",
        "    offline_explain_offline:      'Hai {n} revisione/i salvate. Saranno sincronizzate alla riconnessione.',\n",
        "    offline_explain_pending:      'Hai {n} revisione/i pronta/e per la sincronizzazione.',\n",
        "    offline_explain_expired:      'Sessione scaduta. Accedi per sincronizzare {n} revisione/i.',\n",
    ]),
    (2200, [  # DE
        "    offline_queued:               'Offline · {n} ausstehend',\n",
        "    offline_pending:              '{n} ausstehend',\n",
        "    offline_syncing:              'Synchronisierung…',\n",
        "    offline_synced:               '{n} synchronisiert',\n",
        "    offline_jwt_expired:          'Anmelden zum Synchronisieren · {n}',\n",
        "    offline_explain_heading:      'Ausstehende Bewertungen',\n",
        "    offline_explain_offline:      'Du hast {n} gespeicherte Bewertung(en). Sie werden bei Verbindung synchronisiert.',\n",
        "    offline_explain_pending:      'Du hast {n} Bewertung(en) zur Synchronisierung bereit.',\n",
        "    offline_explain_expired:      'Sitzung abgelaufen. Melde dich an, um {n} Bewertung(en) zu synchronisieren.',\n",
    ]),
    (1543, [  # FR
        "    offline_queued:               'Hors ligne · {n} en attente',\n",
        "    offline_pending:              '{n} en attente',\n",
        "    offline_syncing:              'Synchronisation…',\n",
        "    offline_synced:               '{n} synchronisées',\n",
        "    offline_jwt_expired:          'Connectez-vous pour synchroniser · {n}',\n",
        "    offline_explain_heading:      'Révisions en attente',\n",
        "    offline_explain_offline:      'Vous avez {n} révision(s) enregistrée(s). Elles seront synchronisées à la reconnexion.',\n",
        "    offline_explain_pending:      'Vous avez {n} révision(s) prêtes à synchroniser.',\n",
        "    offline_explain_expired:      'Session expirée. Reconnectez-vous pour synchroniser {n} révision(s).',\n",
    ]),
    (886, [  # ES
        "    offline_queued:               'Sin conexión · {n} en cola',\n",
        "    offline_pending:              '{n} en cola',\n",
        "    offline_syncing:              'Sincronizando…',\n",
        "    offline_synced:               'Sincronizados {n}',\n",
        "    offline_jwt_expired:          'Inicia sesión para sincronizar · {n}',\n",
        "    offline_explain_heading:      'Revisiones en cola',\n",
        "    offline_explain_offline:      'Tienes {n} revisión(es) guardadas. Se sincronizarán al reconectar.',\n",
        "    offline_explain_pending:      'Tienes {n} revisión(es) listas para sincronizar.',\n",
        "    offline_explain_expired:      'Sesión caducada. Inicia sesión para sincronizar {n} revisión(es).',\n",
    ]),
    (143, [  # EN
        "    offline_queued:               'Offline · {n} queued',\n",
        "    offline_pending:              '{n} queued',\n",
        "    offline_syncing:              'Syncing…',\n",
        "    offline_synced:               'Synced {n}',\n",
        "    offline_jwt_expired:          'Sign in to sync · {n}',\n",
        "    offline_explain_heading:      'Queued reviews',\n",
        "    offline_explain_offline:      'You have {n} review(s) saved offline. They will sync automatically when you reconnect.',\n",
        "    offline_explain_pending:      'You have {n} review(s) ready to sync.',\n",
        "    offline_explain_expired:      'Your session has expired. Log in again to sync your {n} queued review(s).',\n",
    ]),
]

for line_no, new_lines in sorted(INSERTIONS, key=lambda x: -x[0]):
    lines[line_no:line_no] = new_lines

I18N.write_text("".join(lines), encoding="utf-8")
print(f"Patched {I18N} — added {len(INSERTIONS) * 9} lines")
