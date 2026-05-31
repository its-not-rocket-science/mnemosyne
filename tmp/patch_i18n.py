# patch_i18n.py — insert stats_* keys into each language block of i18n.js
import re

with open('frontend/js/i18n.js', encoding='utf-8') as f:
    content = f.read()

def insert_after(text, marker, insertion):
    idx = text.find(marker)
    if idx == -1:
        raise ValueError(f'Marker not found: {marker[:60]!r}')
    end = idx + len(marker)
    return text[:end] + '\n' + insertion + text[end:]

# Each entry: (unique fragment of the line to match, lines to insert after it)
patches = [
    # es
    (
        "session_expired_queue:  'Sesi\\u00f3n caducada \\u2014 inicia sesi\\u00f3n para sincronizar las revisiones en cola.',",
        "    stats_due:              'Pendiente',\n    stats_streak:           'Racha',\n    stats_mastered:         'Dominado',\n    stats_today:            'Hoy',",
    ),
    # fr
    (
        "session_expired_queue:  'Session expir\\u00e9e \\u2014 reconnectez-vous pour synchroniser les r\\u00e9visions en attente.',",
        "    stats_due:              'À revoir',\n    stats_streak:           'Série',\n    stats_mastered:         'Maîtrisé',\n    stats_today:            \"Aujourd'hui\",",
    ),
    # de
    (
        "session_expired_queue:  'Sitzung abgelaufen \\u2014 melde dich an, um ausstehende Bewertungen zu synchronisieren.',",
        "    stats_due:              'Fällig',\n    stats_streak:           'Serie',\n    stats_mastered:         'Gemeistert',\n    stats_today:            'Heute',",
    ),
    # it
    (
        "session_expired_queue:  'Sessione scaduta \\u2014 accedi di nuovo per sincronizzare le revisioni in coda.',",
        "    stats_due:              'Da rivedere',\n    stats_streak:           'Serie',\n    stats_mastered:         'Padroneggiato',\n    stats_today:            'Oggi',",
    ),
    # pt
    (
        "session_expired_queue:  'Sess\\u00e3o expirada \\u2014 inicia sess\\u00e3o novamente para sincronizar as revis\\u00f5es em fila.',",
        "    stats_due:              'Pendente',\n    stats_streak:           'Sequência',\n    stats_mastered:         'Dominado',\n    stats_today:            'Hoje',",
    ),
    # ru
    (
        "session_expired_queue:  'Сессия истекла \\u2014 войдите снова для синхронизации отложенных оценок.',",
        "    stats_due:              'К повторению',\n    stats_streak:           'Серия',\n    stats_mastered:         'Освоено',\n    stats_today:            'Сегодня',",
    ),
    # ja
    (
        "session_expired_queue:  'セッションが期限切れです \\u2014 キューの復習を同期するには再ログインしてください。',",
        "    stats_due:              '期日',\n    stats_streak:           '連続',\n    stats_mastered:         '習得',\n    stats_today:            '今日',",
    ),
    # zh
    (
        "session_expired_queue:  '会话已过期 \\u2014 重新登录以同步待处理的复习。',",
        "    stats_due:              '待复习',\n    stats_streak:           '连续',\n    stats_mastered:         '已掌握',\n    stats_today:            '今天',",
    ),
    # ar
    (
        "session_expired_queue:  'انتهت الجلسة \\u2014 سجّل الدخول مجدداً لمزامنة المراجعات المعلّقة.',",
        "    stats_due:              'مستحق',\n    stats_streak:           'تسلسل',\n    stats_mastered:         'متقن',\n    stats_today:            'اليوم',",
    ),
    # he
    (
        "session_expired_queue:  'פג תוקף ההפעלה \\u2014 התחבר שוב כדי לסנכרן את הסקירות הממתינות.',",
        "    stats_due:              'לחזרה',\n    stats_streak:           'רצף',\n    stats_mastered:         'שולט',\n    stats_today:            'היום',",
    ),
]

for marker, insertion in patches:
    content = insert_after(content, marker, insertion)

with open('frontend/js/i18n.js', 'w', encoding='utf-8') as f:
    f.write(content)

print(f'Done. Applied {len(patches)} patches.')
