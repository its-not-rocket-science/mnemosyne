/**
 * i18n.js — Minimal UI localisation for Mnemosyne.
 *
 * Supports 11 languages matching the backend plugin set.
 * The active UI language is persisted to localStorage and defaults to
 * the user's browser language on first visit.
 *
 * Exports
 * ───────
 * initUiLanguage()   — call once on page load; populates the switcher
 *                      select and applies all translations.
 * applyUiLanguage(code) — switch to a specific language code.
 * t(key)             — translate a key in the currently-active language.
 * UI_LANGUAGES       — array of { code, name, dir } for all supported langs.
 */

const LS_KEY = 'mnemosyne_ui_lang'

/** Supported UI languages: code, native name, text direction. */
export const UI_LANGUAGES = [
  { code: 'en', name: 'English',   dir: 'ltr' },
  { code: 'es', name: 'Español',   dir: 'ltr' },
  { code: 'fr', name: 'Français',  dir: 'ltr' },
  { code: 'de', name: 'Deutsch',   dir: 'ltr' },
  { code: 'it', name: 'Italiano',  dir: 'ltr' },
  { code: 'pt', name: 'Português', dir: 'ltr' },
  { code: 'ru', name: 'Русский',   dir: 'ltr' },
  { code: 'ja', name: '日本語',    dir: 'ltr' },
  { code: 'zh', name: '中文',      dir: 'ltr' },
  { code: 'ar', name: 'العربية',   dir: 'rtl' },
  { code: 'he', name: 'עברית',     dir: 'rtl' },
]

const SUPPORTED = new Set(UI_LANGUAGES.map(l => l.code))

// ── Translation table ─────────────────────────────────────────────────────────

const STRINGS = {
  en: {
    skip_to_content:        'Skip to content',
    h1:                     'Turn text into a living lesson',
    lede:                   'Paste text, parse sentences, open micro-lessons, and rate recall.',
    sign_out:               'Sign out',
    delete_account:         'Delete account',
    auth_heading:           'Sign in to continue',
    tab_signin:             'Sign in',
    tab_register:           'Create account',
    label_email:            'Email',
    label_password:         'Password',
    label_confirm_password: 'Confirm password',
    pw_hint:                'At least 8 characters.',
    btn_create_account:     'Create account',
    parse_heading:          'Create a lesson from text',
    label_language:         'Language',
    label_title:            'Title',
    optional:               '(optional)',
    label_source_url:       'Source URL',
    fetch_btn:              'Fetch',
    fetch_btn_aria:         'Fetch text from URL',
    fetch_hint:             'Enter a URL and press Fetch to import its text.',
    label_text:             'Text to parse',
    load_file:              'Load .txt file',
    textarea_placeholder:   'Paste text here, or load a .txt file above\u2026',
    btn_parse:              'Parse text',
    results_heading:        'Sentence lessons',
    results_empty:          'Parse some text above to see learnable items here.',
    privacy_policy:         'Privacy policy',
    ui_language_label:      'Interface language',
    // Dynamic labels used via t() in JS
    parsing:                'Parsing\u2026',
    loading:                'Loading\u2026',
    fetching:               'Fetching\u2026',
    signing_in:             'Signing in\u2026',
    creating_account:       'Creating account\u2026',
    account_aria:           'Account',
    authentication_aria:    'Authentication',
    signed_in_as_aria:      'Signed in as',
    offline_prefix:         'Offline —',
    offline_review:         'review',
    offline_queued:         'queued',
  },

  es: {
    skip_to_content:        'Ir al contenido',
    h1:                     'Convierte texto en una lección viva',
    lede:                   'Pega texto, analiza frases, abre microlecciones y evalúa tu memoria.',
    sign_out:               'Cerrar sesión',
    delete_account:         'Eliminar cuenta',
    auth_heading:           'Inicia sesión para continuar',
    tab_signin:             'Iniciar sesión',
    tab_register:           'Crear cuenta',
    label_email:            'Correo electrónico',
    label_password:         'Contraseña',
    label_confirm_password: 'Confirmar contraseña',
    pw_hint:                'Mínimo 8 caracteres.',
    btn_create_account:     'Crear cuenta',
    parse_heading:          'Crear una lección a partir del texto',
    label_language:         'Idioma',
    label_title:            'Título',
    optional:               '(opcional)',
    label_source_url:       'URL de origen',
    fetch_btn:              'Obtener',
    fetch_btn_aria:         'Obtener texto de la URL',
    fetch_hint:             'Escribe una URL y pulsa Obtener para importar el texto.',
    label_text:             'Texto a analizar',
    load_file:              'Cargar archivo .txt',
    textarea_placeholder:   'Pega texto aquí, o carga un archivo .txt arriba\u2026',
    btn_parse:              'Analizar texto',
    results_heading:        'Lecciones por frase',
    results_empty:          'Analiza texto arriba para ver los elementos aquí.',
    privacy_policy:         'Política de privacidad',
    ui_language_label:      'Idioma de la interfaz',
    parsing:                'Analizando\u2026',
    loading:                'Cargando\u2026',
    fetching:               'Obteniendo\u2026',
    signing_in:             'Iniciando sesión\u2026',
    creating_account:       'Creando cuenta\u2026',
    account_aria:           'Cuenta',
    authentication_aria:    'Autenticación',
    signed_in_as_aria:      'Conectado como',
    offline_prefix:         'Sin conexión —',
    offline_review:         'revisión',
    offline_queued:         'en cola',
  },

  fr: {
    skip_to_content:        'Aller au contenu',
    h1:                     'Transformez du texte en leçon vivante',
    lede:                   'Collez du texte, analysez des phrases, ouvrez des micro-leçons et évaluez votre mémorisation.',
    sign_out:               'Se déconnecter',
    delete_account:         'Supprimer le compte',
    auth_heading:           'Connectez-vous pour continuer',
    tab_signin:             'Se connecter',
    tab_register:           'Créer un compte',
    label_email:            'Adresse e-mail',
    label_password:         'Mot de passe',
    label_confirm_password: 'Confirmer le mot de passe',
    pw_hint:                'Au moins 8 caractères.',
    btn_create_account:     'Créer un compte',
    parse_heading:          'Créer une leçon à partir du texte',
    label_language:         'Langue',
    label_title:            'Titre',
    optional:               '(optionnel)',
    label_source_url:       'URL source',
    fetch_btn:              'Récupérer',
    fetch_btn_aria:         "Récupérer le texte depuis l'URL",
    fetch_hint:             'Entrez une URL et appuyez sur Récupérer pour importer le texte.',
    label_text:             'Texte à analyser',
    load_file:              'Charger un fichier .txt',
    textarea_placeholder:   'Collez du texte ici, ou chargez un fichier .txt ci-dessus\u2026',
    btn_parse:              'Analyser le texte',
    results_heading:        'Leçons par phrase',
    results_empty:          'Analysez du texte ci-dessus pour voir les éléments apprenables ici.',
    privacy_policy:         'Politique de confidentialité',
    ui_language_label:      "Langue de l'interface",
    parsing:                'Analyse\u2026',
    loading:                'Chargement\u2026',
    fetching:               'Récupération\u2026',
    signing_in:             'Connexion\u2026',
    creating_account:       'Création du compte\u2026',
    account_aria:           'Compte',
    authentication_aria:    'Authentification',
    signed_in_as_aria:      'Connecté en tant que',
    offline_prefix:         'Hors ligne —',
    offline_review:         'révision',
    offline_queued:         'en attente',
  },

  de: {
    skip_to_content:        'Zum Inhalt springen',
    h1:                     'Text in eine lebendige Lektion verwandeln',
    lede:                   'Text einfügen, Sätze analysieren, Mikrolektionen öffnen und das Erinnern bewerten.',
    sign_out:               'Abmelden',
    delete_account:         'Konto löschen',
    auth_heading:           'Anmelden, um fortzufahren',
    tab_signin:             'Anmelden',
    tab_register:           'Konto erstellen',
    label_email:            'E-Mail',
    label_password:         'Passwort',
    label_confirm_password: 'Passwort bestätigen',
    pw_hint:                'Mindestens 8 Zeichen.',
    btn_create_account:     'Konto erstellen',
    parse_heading:          'Eine Lektion aus Text erstellen',
    label_language:         'Sprache',
    label_title:            'Titel',
    optional:               '(optional)',
    label_source_url:       'Quell-URL',
    fetch_btn:              'Abrufen',
    fetch_btn_aria:         'Text von URL abrufen',
    fetch_hint:             'URL eingeben und Abrufen drücken, um den Text zu importieren.',
    label_text:             'Zu analysierender Text',
    load_file:              '.txt-Datei laden',
    textarea_placeholder:   'Text hier einfügen oder eine .txt-Datei oben laden\u2026',
    btn_parse:              'Text analysieren',
    results_heading:        'Satzlektionen',
    results_empty:          'Text oben analysieren, um lernbare Elemente hier zu sehen.',
    privacy_policy:         'Datenschutzrichtlinie',
    ui_language_label:      'Oberflächensprache',
    parsing:                'Analysiere\u2026',
    loading:                'Laden\u2026',
    fetching:               'Abrufen\u2026',
    signing_in:             'Anmelden\u2026',
    creating_account:       'Konto erstellen\u2026',
    account_aria:           'Konto',
    authentication_aria:    'Authentifizierung',
    signed_in_as_aria:      'Angemeldet als',
    offline_prefix:         'Offline —',
    offline_review:         'Wiederholung',
    offline_queued:         'wartend',
  },

  it: {
    skip_to_content:        'Vai al contenuto',
    h1:                     'Trasforma il testo in una lezione viva',
    lede:                   'Incolla del testo, analizza le frasi, apri micro-lezioni e valuta il tuo ricordo.',
    sign_out:               'Esci',
    delete_account:         'Elimina account',
    auth_heading:           'Accedi per continuare',
    tab_signin:             'Accedi',
    tab_register:           'Crea account',
    label_email:            'Email',
    label_password:         'Password',
    label_confirm_password: 'Conferma password',
    pw_hint:                'Almeno 8 caratteri.',
    btn_create_account:     'Crea account',
    parse_heading:          'Crea una lezione dal testo',
    label_language:         'Lingua',
    label_title:            'Titolo',
    optional:               '(facoltativo)',
    label_source_url:       'URL sorgente',
    fetch_btn:              'Recupera',
    fetch_btn_aria:         "Recupera testo dall'URL",
    fetch_hint:             'Inserisci un URL e premi Recupera per importare il testo.',
    label_text:             'Testo da analizzare',
    load_file:              'Carica file .txt',
    textarea_placeholder:   'Incolla il testo qui, o carica un file .txt sopra\u2026',
    btn_parse:              'Analizza testo',
    results_heading:        'Lezioni per frase',
    results_empty:          'Analizza del testo sopra per vedere gli elementi qui.',
    privacy_policy:         'Informativa sulla privacy',
    ui_language_label:      "Lingua dell'interfaccia",
    parsing:                'Analisi\u2026',
    loading:                'Caricamento\u2026',
    fetching:               'Recupero\u2026',
    signing_in:             'Accesso\u2026',
    creating_account:       'Creazione account\u2026',
    account_aria:           'Account',
    authentication_aria:    'Autenticazione',
    signed_in_as_aria:      'Connesso come',
    offline_prefix:         'Offline —',
    offline_review:         'ripetizione',
    offline_queued:         'in coda',
  },

  pt: {
    skip_to_content:        'Ir para o conteúdo',
    h1:                     'Transforme texto em uma lição viva',
    lede:                   'Cole texto, analise frases, abra micro-lições e avalie seu recall.',
    sign_out:               'Sair',
    delete_account:         'Excluir conta',
    auth_heading:           'Faça login para continuar',
    tab_signin:             'Entrar',
    tab_register:           'Criar conta',
    label_email:            'E-mail',
    label_password:         'Senha',
    label_confirm_password: 'Confirmar senha',
    pw_hint:                'Pelo menos 8 caracteres.',
    btn_create_account:     'Criar conta',
    parse_heading:          'Criar uma lição a partir do texto',
    label_language:         'Idioma',
    label_title:            'Título',
    optional:               '(opcional)',
    label_source_url:       'URL de origem',
    fetch_btn:              'Buscar',
    fetch_btn_aria:         'Buscar texto da URL',
    fetch_hint:             'Insira uma URL e pressione Buscar para importar o texto.',
    label_text:             'Texto a analisar',
    load_file:              'Carregar arquivo .txt',
    textarea_placeholder:   'Cole o texto aqui, ou carregue um arquivo .txt acima\u2026',
    btn_parse:              'Analisar texto',
    results_heading:        'Lições por frase',
    results_empty:          'Analise algum texto acima para ver os itens aqui.',
    privacy_policy:         'Política de privacidade',
    ui_language_label:      'Idioma da interface',
    parsing:                'Analisando\u2026',
    loading:                'Carregando\u2026',
    fetching:               'Buscando\u2026',
    signing_in:             'Entrando\u2026',
    creating_account:       'Criando conta\u2026',
    account_aria:           'Conta',
    authentication_aria:    'Autenticação',
    signed_in_as_aria:      'Conectado como',
    offline_prefix:         'Offline —',
    offline_review:         'revisão',
    offline_queued:         'na fila',
  },

  ru: {
    skip_to_content:        'Перейти к содержимому',
    h1:                     'Превратите текст в живой урок',
    lede:                   'Вставьте текст, разберите предложения, откройте микроуроки и оцените запоминание.',
    sign_out:               'Выйти',
    delete_account:         'Удалить аккаунт',
    auth_heading:           'Войдите, чтобы продолжить',
    tab_signin:             'Войти',
    tab_register:           'Создать аккаунт',
    label_email:            'Email',
    label_password:         'Пароль',
    label_confirm_password: 'Подтвердить пароль',
    pw_hint:                'Не менее 8 символов.',
    btn_create_account:     'Создать аккаунт',
    parse_heading:          'Создать урок из текста',
    label_language:         'Язык',
    label_title:            'Заголовок',
    optional:               '(необязательно)',
    label_source_url:       'URL источника',
    fetch_btn:              'Получить',
    fetch_btn_aria:         'Получить текст по URL',
    fetch_hint:             'Введите URL и нажмите «Получить», чтобы импортировать текст.',
    label_text:             'Текст для разбора',
    load_file:              'Загрузить .txt файл',
    textarea_placeholder:   'Вставьте текст здесь или загрузите .txt файл выше\u2026',
    btn_parse:              'Разобрать текст',
    results_heading:        'Уроки по предложениям',
    results_empty:          'Разберите текст выше, чтобы увидеть элементы для изучения.',
    privacy_policy:         'Политика конфиденциальности',
    ui_language_label:      'Язык интерфейса',
    parsing:                'Разбор\u2026',
    loading:                'Загрузка\u2026',
    fetching:               'Получение\u2026',
    signing_in:             'Вход\u2026',
    creating_account:       'Создание аккаунта\u2026',
    account_aria:           'Аккаунт',
    authentication_aria:    'Аутентификация',
    signed_in_as_aria:      'Вошли как',
    offline_prefix:         'Офлайн —',
    offline_review:         'повтор',
    offline_queued:         'в очереди',
  },

  ja: {
    skip_to_content:        'コンテンツへスキップ',
    h1:                     'テキストを生きたレッスンに変える',
    lede:                   'テキストを貼り付け、文を解析し、マイクロレッスンを開いて、記憶を評価しましょう。',
    sign_out:               'サインアウト',
    delete_account:         'アカウント削除',
    auth_heading:           '続けるにはサインインしてください',
    tab_signin:             'サインイン',
    tab_register:           'アカウント作成',
    label_email:            'メールアドレス',
    label_password:         'パスワード',
    label_confirm_password: 'パスワードの確認',
    pw_hint:                '8文字以上。',
    btn_create_account:     'アカウント作成',
    parse_heading:          'テキストからレッスンを作成',
    label_language:         '言語',
    label_title:            'タイトル',
    optional:               '（任意）',
    label_source_url:       'ソースURL',
    fetch_btn:              '取得',
    fetch_btn_aria:         'URLからテキストを取得',
    fetch_hint:             'URLを入力して「取得」を押すとテキストをインポートできます。',
    label_text:             '解析するテキスト',
    load_file:              '.txtファイルを読み込む',
    textarea_placeholder:   'ここにテキストを貼り付けるか、上から.txtファイルを読み込んでください\u2026',
    btn_parse:              'テキストを解析',
    results_heading:        '文ごとのレッスン',
    results_empty:          '上でテキストを解析すると、学習項目がここに表示されます。',
    privacy_policy:         'プライバシーポリシー',
    ui_language_label:      'インターフェース言語',
    parsing:                '解析中\u2026',
    loading:                '読み込み中\u2026',
    fetching:               '取得中\u2026',
    signing_in:             'サインイン中\u2026',
    creating_account:       'アカウント作成中\u2026',
    account_aria:           'アカウント',
    authentication_aria:    '認証',
    signed_in_as_aria:      'サインイン済み：',
    offline_prefix:         'オフライン —',
    offline_review:         '復習',
    offline_queued:         '待機中',
  },

  zh: {
    skip_to_content:        '跳至内容',
    h1:                     '将文本转化为生动课程',
    lede:                   '粘贴文本，分析句子，打开微课程，评估记忆效果。',
    sign_out:               '退出登录',
    delete_account:         '删除账户',
    auth_heading:           '登录以继续',
    tab_signin:             '登录',
    tab_register:           '创建账户',
    label_email:            '电子邮件',
    label_password:         '密码',
    label_confirm_password: '确认密码',
    pw_hint:                '至少8个字符。',
    btn_create_account:     '创建账户',
    parse_heading:          '从文本创建课程',
    label_language:         '语言',
    label_title:            '标题',
    optional:               '（可选）',
    label_source_url:       '来源网址',
    fetch_btn:              '获取',
    fetch_btn_aria:         '从网址获取文本',
    fetch_hint:             '输入网址并点击「获取」以导入文本。',
    label_text:             '待分析文本',
    load_file:              '加载 .txt 文件',
    textarea_placeholder:   '在此粘贴文本，或在上方加载 .txt 文件\u2026',
    btn_parse:              '分析文本',
    results_heading:        '按句学习',
    results_empty:          '在上方分析文本，即可在此处查看可学项目。',
    privacy_policy:         '隐私政策',
    ui_language_label:      '界面语言',
    parsing:                '分析中\u2026',
    loading:                '加载中\u2026',
    fetching:               '获取中\u2026',
    signing_in:             '登录中\u2026',
    creating_account:       '创建账户中\u2026',
    account_aria:           '账户',
    authentication_aria:    '身份验证',
    signed_in_as_aria:      '已登录为',
    offline_prefix:         '离线 —',
    offline_review:         '复习',
    offline_queued:         '排队中',
  },

  ar: {
    skip_to_content:        'تخطي إلى المحتوى',
    h1:                     'حوّل النص إلى درس حيّ',
    lede:                   'الصق النص، وحلّل الجمل، وافتح الدروس المصغّرة، وقيّم استرجاعك.',
    sign_out:               'تسجيل الخروج',
    delete_account:         'حذف الحساب',
    auth_heading:           'سجّل دخولك للمتابعة',
    tab_signin:             'تسجيل الدخول',
    tab_register:           'إنشاء حساب',
    label_email:            'البريد الإلكتروني',
    label_password:         'كلمة المرور',
    label_confirm_password: 'تأكيد كلمة المرور',
    pw_hint:                '٨ أحرف على الأقل.',
    btn_create_account:     'إنشاء حساب',
    parse_heading:          'إنشاء درس من النص',
    label_language:         'اللغة',
    label_title:            'العنوان',
    optional:               '(اختياري)',
    label_source_url:       'رابط المصدر',
    fetch_btn:              'جلب',
    fetch_btn_aria:         'جلب النص من الرابط',
    fetch_hint:             'أدخل رابطاً واضغط جلب لاستيراد النص.',
    label_text:             'النص للتحليل',
    load_file:              'تحميل ملف .txt',
    textarea_placeholder:   'الصق النص هنا، أو حمّل ملف .txt أعلاه\u2026',
    btn_parse:              'تحليل النص',
    results_heading:        'دروس الجمل',
    results_empty:          'حلّل نصاً أعلاه لرؤية العناصر القابلة للتعلم هنا.',
    privacy_policy:         'سياسة الخصوصية',
    ui_language_label:      'لغة الواجهة',
    parsing:                'تحليل\u2026',
    loading:                'تحميل\u2026',
    fetching:               'جلب\u2026',
    signing_in:             'تسجيل الدخول\u2026',
    creating_account:       'إنشاء حساب\u2026',
    account_aria:           'الحساب',
    authentication_aria:    'المصادقة',
    signed_in_as_aria:      'مسجّل دخولك بـ',
    offline_prefix:         'غير متصل —',
    offline_review:         'مراجعة',
    offline_queued:         'في الانتظار',
  },

  he: {
    skip_to_content:        'דלג לתוכן',
    h1:                     'הפוך טקסט לשיעור חי',
    lede:                   'הדבק טקסט, נתח משפטים, פתח שיעורים קצרים ודרג את זכירתך.',
    sign_out:               'התנתק',
    delete_account:         'מחק חשבון',
    auth_heading:           'התחבר כדי להמשיך',
    tab_signin:             'התחברות',
    tab_register:           'יצירת חשבון',
    label_email:            'דוא"ל',
    label_password:         'סיסמה',
    label_confirm_password: 'אשר סיסמה',
    pw_hint:                'לפחות 8 תווים.',
    btn_create_account:     'יצירת חשבון',
    parse_heading:          'צור שיעור מטקסט',
    label_language:         'שפה',
    label_title:            'כותרת',
    optional:               '(אופציונלי)',
    label_source_url:       'כתובת מקור',
    fetch_btn:              'אחזר',
    fetch_btn_aria:         'אחזר טקסט מהכתובת',
    fetch_hint:             'הכנס כתובת URL ולחץ אחזר כדי לייבא את הטקסט.',
    label_text:             'טקסט לניתוח',
    load_file:              'טען קובץ .txt',
    textarea_placeholder:   'הדבק טקסט כאן, או טען קובץ .txt למעלה\u2026',
    btn_parse:              'נתח טקסט',
    results_heading:        'שיעורי משפטים',
    results_empty:          'נתח טקסט למעלה כדי לראות פריטים ללמידה כאן.',
    privacy_policy:         'מדיניות פרטיות',
    ui_language_label:      'שפת ממשק',
    parsing:                'מנתח\u2026',
    loading:                'טוען\u2026',
    fetching:               'מאחזר\u2026',
    signing_in:             'מתחבר\u2026',
    creating_account:       'יוצר חשבון\u2026',
    account_aria:           'חשבון',
    authentication_aria:    'אימות',
    signed_in_as_aria:      'מחובר בתור',
    offline_prefix:         'לא מקוון —',
    offline_review:         'חזרה',
    offline_queued:         'בתור',
  },
}

// ── Runtime state ─────────────────────────────────────────────────────────────

let _currentLang = 'en'

/**
 * Translate a key in the currently-active UI language.
 * Falls back to English, then the key itself, so missing keys are visible.
 */
export function t(key) {
  return STRINGS[_currentLang]?.[key] ?? STRINGS.en[key] ?? key
}

/**
 * Apply translations to all annotated DOM elements and update the document
 * language and direction.  Persists the choice to localStorage.
 */
export function applyUiLanguage(code) {
  const lang     = SUPPORTED.has(code) ? code : 'en'
  _currentLang   = lang

  const meta = UI_LANGUAGES.find(l => l.code === lang) ?? UI_LANGUAGES[0]
  document.documentElement.lang = lang
  document.documentElement.dir  = meta.dir

  // data-i18n → textContent
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const val = t(el.dataset.i18n)
    if (val) el.textContent = val
  })

  // data-i18n-placeholder → placeholder attribute
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    const val = t(el.dataset.i18nPlaceholder)
    if (val) el.placeholder = val
  })

  // data-i18n-aria-label → aria-label attribute
  document.querySelectorAll('[data-i18n-aria-label]').forEach(el => {
    const val = t(el.dataset.i18nAriaLabel)
    if (val) el.setAttribute('aria-label', val)
  })

  localStorage.setItem(LS_KEY, lang)

  // Keep the switcher select in sync when called programmatically.
  const sel = document.querySelector('#ui-language')
  if (sel && sel.value !== lang) sel.value = lang
}

/**
 * Initialise the UI language system.  Detects browser language, populates
 * the #ui-language select, and applies the initial translations.
 * Must be called once on page load, before other rendering.
 */
export function initUiLanguage() {
  // Resolve language: localStorage → best browser match → 'en'
  const stored  = localStorage.getItem(LS_KEY)
  const browser = (navigator.languages ?? [navigator.language])
    .map(l => l.split('-')[0])
    .find(l => SUPPORTED.has(l))

  const initial = SUPPORTED.has(stored) ? stored
                : browser               ? browser
                : 'en'

  // Populate the language switcher.
  const sel = document.querySelector('#ui-language')
  if (sel) {
    sel.replaceChildren(
      ...UI_LANGUAGES.map(({ code, name }) => {
        const opt = document.createElement('option')
        opt.value       = code
        opt.textContent = name
        return opt
      })
    )
    sel.value = initial
    sel.addEventListener('change', () => applyUiLanguage(sel.value))
  }

  applyUiLanguage(initial)
}
