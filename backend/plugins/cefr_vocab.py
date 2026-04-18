"""CEFR vocabulary tables per language.

Each table maps language code → frozenset of spaCy lemma strings at that
CEFR level.  Only content-word lemmas are included (NOUN, ADJ, ADV, VERB) —
function words (determiners, prepositions, conjunctions) are filtered before
vocabulary extraction and would never reach the CEFR lookup.

Lemma conventions (must match spaCy output exactly):
  es / fr / it / pt / ru  — all lowercase  (tok.lemma_.lower())
  de                      — nouns Title-cased, other POS lowercase
                            (spaCy preserves German capitalisation)
  ja                      — kanji / kana as returned by spaCy + SudachiPy

Usage in plugins
────────────────
  from backend.plugins.cefr_vocab import A1

  _A1 = A1.get("es", frozenset())   # module-level constant

  # In _vocab_confidence():
  if lemma in _A1:
      return 0.90, None   # known A1 word — suppress is_oov false-positive
  if tok.is_oov:
      return 0.50, "word not found in model vocabulary ..."
  return 0.85, None

  # In _extract_vocabulary():
  if lemma in _A1:
      data["cefr_level"] = "A1"

Roadmap
───────
  A2 table: add here when curated; plugins pick it up automatically once
  the level check is extended (see ROADMAP.md "CEFR A2 vocabulary").
"""
from __future__ import annotations

# ── Spanish (es) ──────────────────────────────────────────────────────────────
_ES_A1: frozenset[str] = frozenset({
    # core verbs (infinitive / lemma)
    "ser", "estar", "tener", "haber", "hacer", "ir", "decir", "poder",
    "saber", "querer", "ver", "dar", "venir", "llegar", "pasar", "llevar",
    "hablar", "comer", "beber", "vivir", "trabajar", "estudiar", "comprar",
    "necesitar", "llamar", "creer", "pensar", "escribir", "leer",
    "escuchar", "mirar", "ayudar", "jugar", "dormir", "salir", "entrar",
    "abrir", "cerrar", "poner", "buscar", "encontrar", "conocer", "empezar",
    "dejar", "seguir", "gustar", "esperar", "preguntar", "contestar",
    # nouns
    "casa", "persona", "hombre", "mujer", "niño", "niña", "chico", "chica",
    "familia", "padre", "madre", "hermano", "hermana", "hijo", "hija",
    "amigo", "amiga", "trabajo", "tiempo", "año", "día", "mes", "semana",
    "hora", "minuto", "segundo", "país", "ciudad", "pueblo", "calle",
    "libro", "mesa", "silla", "cama", "baño", "cocina", "habitación",
    "comida", "agua", "leche", "pan", "carne", "pescado", "fruta",
    "verdura", "desayuno", "comida", "cena", "coche", "autobús", "tren",
    "avión", "dinero", "precio", "tienda", "mercado", "nombre", "número",
    "problema", "pregunta", "respuesta", "palabra", "idioma", "lengua",
    "cosa", "mundo", "gente", "vida", "lugar", "parte", "vez", "manera",
    "escuela", "universidad", "alumno", "profesor", "clase", "lección",
    "puerta", "ventana", "jardín", "parque", "playa", "montaña",
    "perro", "gato", "pájaro", "flor", "árbol",
    # adjectives
    "bueno", "malo", "grande", "pequeño", "nuevo", "viejo", "joven",
    "bonito", "feo", "alto", "bajo", "largo", "corto", "ancho", "estrecho",
    "fácil", "difícil", "rápido", "lento", "caliente", "frío", "barato",
    "caro", "libre", "ocupado", "abierto", "cerrado", "limpio", "sucio",
    "lleno", "vacío", "primero", "segundo", "tercero", "último", "mismo",
    "otro", "todo", "mucho", "poco", "bastante", "alguno", "ninguno",
    "propio", "importante", "diferente", "igual", "feliz", "triste",
    "cansado", "enfermo", "sano", "hambriento", "sediento",
    # numbers
    "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho",
    "nueve", "diez", "once", "doce", "trece", "catorce", "quince",
    "dieciséis", "diecisiete", "dieciocho", "diecinueve", "veinte",
    "treinta", "cuarenta", "cincuenta", "sesenta", "setenta", "ochenta",
    "noventa", "cien", "ciento", "mil", "millón",
    # days
    "lunes", "martes", "miércoles", "jueves", "viernes", "sábado",
    "domingo", "semana",
    # months
    "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
    "agosto", "septiembre", "octubre", "noviembre", "diciembre",
    # colours
    "rojo", "azul", "verde", "amarillo", "blanco", "negro", "gris",
    "marrón", "naranja", "rosa", "morado", "violeta",
    # common adverbs / time expressions
    "aquí", "allí", "allá", "hoy", "ayer", "mañana", "ahora", "antes",
    "después", "siempre", "nunca", "también", "tampoco", "muy", "bien",
    "mal", "más", "menos", "solo", "mucho", "poco", "tarde", "temprano",
    "pronto", "cerca", "lejos",
})

# ── French (fr) ───────────────────────────────────────────────────────────────
_FR_A1: frozenset[str] = frozenset({
    # core verbs
    "être", "avoir", "faire", "aller", "venir", "pouvoir", "vouloir",
    "savoir", "devoir", "dire", "voir", "prendre", "donner", "partir",
    "arriver", "passer", "rester", "trouver", "chercher", "mettre",
    "tenir", "appeler", "parler", "manger", "boire", "dormir",
    "travailler", "habiter", "aimer", "penser", "croire", "connaître",
    "comprendre", "lire", "écrire", "entendre", "ouvrir", "fermer",
    "acheter", "aider", "jouer", "entrer", "sortir", "marcher",
    "commencer", "finir", "attendre", "répondre", "demander",
    # nouns
    "maison", "homme", "femme", "enfant", "garçon", "fille", "famille",
    "père", "mère", "frère", "sœur", "fils", "ami", "amie",
    "travail", "temps", "année", "jour", "mois", "semaine", "heure",
    "minute", "seconde", "pays", "ville", "village", "rue", "avenue",
    "livre", "table", "chaise", "lit", "salle", "cuisine", "chambre",
    "nourriture", "eau", "lait", "pain", "viande", "poisson", "fruit",
    "légume", "petit-déjeuner", "déjeuner", "dîner",
    "voiture", "bus", "train", "avion", "vélo",
    "argent", "prix", "magasin", "marché", "nom", "numéro",
    "problème", "question", "réponse", "mot", "langue", "chose",
    "monde", "vie", "place", "fois", "façon", "école", "université",
    "élève", "professeur", "classe", "leçon", "porte", "fenêtre",
    "jardin", "parc", "plage", "montagne", "chien", "chat", "oiseau",
    "fleur", "arbre",
    # adjectives
    "bon", "mauvais", "grand", "petit", "nouveau", "vieux", "jeune",
    "beau", "laid", "haut", "bas", "long", "court", "large", "étroit",
    "facile", "difficile", "rapide", "lent", "chaud", "froid",
    "bon marché", "cher", "libre", "occupé", "ouvert", "fermé",
    "propre", "sale", "plein", "vide", "premier", "deuxième", "dernier",
    "même", "autre", "tout", "beaucoup", "peu", "important", "différent",
    "pareil", "heureux", "triste", "fatigué", "malade", "sain",
    # numbers
    "un", "deux", "trois", "quatre", "cinq", "six", "sept", "huit",
    "neuf", "dix", "onze", "douze", "treize", "quatorze", "quinze",
    "seize", "vingt", "trente", "quarante", "cinquante", "soixante",
    "cent", "mille", "million",
    # days
    "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi",
    "dimanche",
    # months
    "janvier", "février", "mars", "avril", "mai", "juin", "juillet",
    "août", "septembre", "octobre", "novembre", "décembre",
    # colours
    "rouge", "bleu", "vert", "jaune", "blanc", "noir", "gris",
    "marron", "orange", "rose", "violet",
    # adverbs / time
    "ici", "là", "aujourd'hui", "hier", "demain", "maintenant", "avant",
    "après", "toujours", "jamais", "aussi", "non plus", "très", "bien",
    "mal", "plus", "moins", "seulement", "beaucoup", "peu", "tard",
    "tôt", "vite", "près", "loin",
})

# ── German (de) ───────────────────────────────────────────────────────────────
# Nouns are Title-cased to match spaCy's German lemma convention.
_DE_A1: frozenset[str] = frozenset({
    # core verbs (lowercase)
    "sein", "haben", "machen", "gehen", "kommen", "können", "müssen",
    "sollen", "wollen", "dürfen", "mögen", "möchten", "sagen", "sehen",
    "geben", "nehmen", "bringen", "denken", "wissen", "kennen",
    "sprechen", "essen", "trinken", "schlafen", "arbeiten", "wohnen",
    "kaufen", "suchen", "finden", "öffnen", "schließen", "helfen",
    "spielen", "schreiben", "lesen", "hören", "verstehen", "beginnen",
    "anfangen", "aufhören", "warten", "antworten", "fragen", "lernen",
    "heißen", "leben", "laufen", "fahren", "fliegen", "bleiben",
    # nouns (Title-cased)
    "Haus", "Mann", "Frau", "Kind", "Junge", "Mädchen", "Familie",
    "Vater", "Mutter", "Bruder", "Schwester", "Sohn", "Tochter",
    "Freund", "Freundin", "Arbeit", "Zeit", "Jahr", "Tag", "Monat",
    "Woche", "Stunde", "Minute", "Sekunde", "Land", "Stadt", "Dorf",
    "Straße", "Buch", "Tisch", "Stuhl", "Bett", "Bad", "Küche",
    "Zimmer", "Essen", "Wasser", "Milch", "Brot", "Fleisch", "Fisch",
    "Obst", "Gemüse", "Frühstück", "Mittagessen", "Abendessen",
    "Auto", "Bus", "Zug", "Flugzeug", "Fahrrad", "Geld", "Preis",
    "Laden", "Markt", "Name", "Nummer", "Problem", "Frage", "Antwort",
    "Wort", "Sprache", "Sache", "Welt", "Leben", "Platz", "Mal",
    "Weise", "Schule", "Universität", "Schüler", "Lehrer", "Klasse",
    "Lektion", "Tür", "Fenster", "Garten", "Park", "Strand", "Berg",
    "Hund", "Katze", "Vogel", "Blume", "Baum",
    # adjectives (lowercase)
    "gut", "schlecht", "groß", "klein", "neu", "alt", "jung", "schön",
    "hässlich", "hoch", "niedrig", "lang", "kurz", "breit", "schmal",
    "einfach", "schwer", "schwierig", "schnell", "langsam", "heiß",
    "kalt", "billig", "teuer", "frei", "besetzt", "offen", "geschlossen",
    "sauber", "schmutzig", "voll", "leer", "erst", "letzt", "gleich",
    "ander", "ganz", "wichtig", "verschieden", "richtig", "falsch",
    "glücklich", "traurig", "müde", "krank", "gesund", "hungrig", "durstig",
    # numbers
    "ein", "zwei", "drei", "vier", "fünf", "sechs", "sieben", "acht",
    "neun", "zehn", "elf", "zwölf", "dreizehn", "vierzehn", "fünfzehn",
    "sechzehn", "siebzehn", "achtzehn", "neunzehn", "zwanzig",
    "dreißig", "vierzig", "fünfzig", "sechzig", "siebzig", "achtzig",
    "neunzig", "hundert", "tausend", "Million",
    # days (Title-cased — German nouns)
    "Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag",
    "Samstag", "Sonntag",
    # months (Title-cased)
    "Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
    "August", "September", "Oktober", "November", "Dezember",
    # colours (lowercase adjectives)
    "rot", "blau", "grün", "gelb", "weiß", "schwarz", "grau", "braun",
    "orange", "rosa", "lila", "violett",
    # adverbs / time
    "hier", "dort", "heute", "gestern", "morgen", "jetzt", "vorher",
    "nachher", "danach", "immer", "nie", "auch", "nicht", "sehr", "gut",
    "schlecht", "mehr", "weniger", "nur", "viel", "wenig", "spät",
    "früh", "schnell", "nah", "weit",
})

# ── Italian (it) ──────────────────────────────────────────────────────────────
_IT_A1: frozenset[str] = frozenset({
    # core verbs
    "essere", "avere", "fare", "andare", "venire", "potere", "volere",
    "sapere", "dovere", "dire", "vedere", "dare", "prendere", "portare",
    "mettere", "trovare", "cercare", "aprire", "chiudere", "aiutare",
    "giocare", "parlare", "mangiare", "bere", "dormire", "lavorare",
    "abitare", "amare", "pensare", "credere", "capire", "conoscere",
    "leggere", "scrivere", "sentire", "cominciare", "finire", "arrivare",
    "uscire", "entrare", "comprare", "chiamare", "aspettare", "rispondere",
    "chiedere", "imparare", "tornare", "partire", "guardare", "usare",
    # nouns
    "casa", "uomo", "donna", "bambino", "bambina", "ragazzo", "ragazza",
    "famiglia", "padre", "madre", "fratello", "sorella", "figlio",
    "figlia", "amico", "amica", "lavoro", "tempo", "anno", "giorno",
    "mese", "settimana", "ora", "minuto", "secondo", "paese", "città",
    "paese", "via", "libro", "tavolo", "sedia", "letto", "bagno",
    "cucina", "camera", "cibo", "acqua", "latte", "pane", "carne",
    "pesce", "frutto", "verdura", "colazione", "pranzo", "cena",
    "macchina", "autobus", "treno", "aereo", "bicicletta",
    "soldi", "prezzo", "negozio", "mercato", "nome", "numero",
    "problema", "domanda", "risposta", "parola", "lingua", "cosa",
    "mondo", "vita", "posto", "volta", "modo", "scuola", "università",
    "studente", "professore", "classe", "lezione", "porta", "finestra",
    "giardino", "parco", "spiaggia", "montagna", "cane", "gatto",
    "uccello", "fiore", "albero",
    # adjectives
    "buono", "cattivo", "grande", "piccolo", "nuovo", "vecchio", "giovane",
    "bello", "brutto", "alto", "basso", "lungo", "corto", "largo",
    "stretto", "facile", "difficile", "veloce", "lento", "caldo",
    "freddo", "economico", "caro", "libero", "occupato", "aperto",
    "chiuso", "pulito", "sporco", "pieno", "vuoto", "primo", "secondo",
    "ultimo", "stesso", "altro", "tutto", "molto", "poco", "importante",
    "diverso", "uguale", "felice", "triste", "stanco", "malato", "sano",
    # numbers
    "uno", "due", "tre", "quattro", "cinque", "sei", "sette", "otto",
    "nove", "dieci", "undici", "dodici", "tredici", "quattordici",
    "quindici", "sedici", "diciassette", "diciotto", "diciannove",
    "venti", "trenta", "quaranta", "cinquanta", "sessanta", "settanta",
    "ottanta", "novanta", "cento", "mille", "milione",
    # days
    "lunedì", "martedì", "mercoledì", "giovedì", "venerdì",
    "sabato", "domenica",
    # months
    "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
    "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre",
    # colours
    "rosso", "blu", "verde", "giallo", "bianco", "nero", "grigio",
    "marrone", "arancione", "rosa", "viola",
    # adverbs / time
    "qui", "là", "oggi", "ieri", "domani", "adesso", "ora", "prima",
    "dopo", "sempre", "mai", "anche", "molto", "bene", "male", "più",
    "meno", "solo", "tanto", "poco", "tardi", "presto", "vicino",
    "lontano",
})

# ── Portuguese (pt) ───────────────────────────────────────────────────────────
_PT_A1: frozenset[str] = frozenset({
    # core verbs
    "ser", "estar", "ter", "haver", "fazer", "ir", "vir", "poder",
    "querer", "saber", "dizer", "ver", "dar", "trazer", "chegar",
    "passar", "deixar", "seguir", "falar", "comer", "beber", "dormir",
    "trabalhar", "morar", "amar", "pensar", "acreditar", "conhecer",
    "entender", "compreender", "ler", "escrever", "ouvir", "ajudar",
    "jogar", "entrar", "sair", "abrir", "fechar", "comprar", "buscar",
    "procurar", "encontrar", "começar", "terminar", "acabar",
    "esperar", "responder", "perguntar", "aprender", "voltar",
    "olhar", "usar", "precisar", "gostar",
    # nouns
    "casa", "homem", "mulher", "criança", "menino", "menina",
    "rapaz", "rapariga", "família", "pai", "mãe", "irmão", "irmã",
    "filho", "filha", "amigo", "amiga", "trabalho", "tempo", "ano",
    "dia", "mês", "semana", "hora", "minuto", "segundo", "país",
    "cidade", "vila", "rua", "livro", "mesa", "cadeira", "cama",
    "casa de banho", "cozinha", "quarto", "comida", "água", "leite",
    "pão", "carne", "peixe", "fruta", "legume", "pequeno-almoço",
    "almoço", "jantar", "carro", "autocarro", "comboio", "avião",
    "bicicleta", "dinheiro", "preço", "loja", "mercado", "nome",
    "número", "problema", "pergunta", "resposta", "palavra", "língua",
    "coisa", "mundo", "vida", "lugar", "vez", "modo", "escola",
    "universidade", "aluno", "professor", "aula", "lição", "porta",
    "janela", "jardim", "parque", "praia", "montanha", "cão", "gato",
    "pássaro", "flor", "árvore",
    # adjectives
    "bom", "mau", "grande", "pequeno", "novo", "velho", "jovem",
    "bonito", "feio", "alto", "baixo", "longo", "curto", "largo",
    "estreito", "fácil", "difícil", "rápido", "lento", "quente",
    "frio", "barato", "caro", "livre", "ocupado", "aberto", "fechado",
    "limpo", "sujo", "cheio", "vazio", "primeiro", "segundo", "último",
    "mesmo", "outro", "todo", "muito", "pouco", "importante",
    "diferente", "igual", "feliz", "triste", "cansado", "doente", "saudável",
    # numbers
    "um", "dois", "três", "quatro", "cinco", "seis", "sete", "oito",
    "nove", "dez", "onze", "doze", "treze", "catorze", "quinze",
    "dezasseis", "dezassete", "dezoito", "dezanove", "vinte",
    "trinta", "quarenta", "cinquenta", "sessenta", "setenta",
    "oitenta", "noventa", "cem", "cento", "mil", "milhão",
    # days
    "segunda", "terça", "quarta", "quinta", "sexta", "sábado",
    "domingo",
    # months
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
    # colours
    "vermelho", "azul", "verde", "amarelo", "branco", "preto",
    "cinza", "cinzento", "castanho", "laranja", "rosa", "roxo",
    # adverbs / time
    "aqui", "ali", "lá", "hoje", "ontem", "amanhã", "agora", "antes",
    "depois", "sempre", "nunca", "também", "muito", "bem", "mal",
    "mais", "menos", "só", "apenas", "tarde", "cedo", "perto", "longe",
})

# ── Russian (ru) ──────────────────────────────────────────────────────────────
_RU_A1: frozenset[str] = frozenset({
    # core verbs (infinitive lemma, lowercase)
    "быть", "иметь", "делать", "идти", "ходить", "приходить", "уходить",
    "мочь", "хотеть", "знать", "говорить", "сказать", "видеть",
    "давать", "дать", "брать", "взять", "думать", "понимать",
    "любить", "жить", "работать", "учиться", "учить", "покупать",
    "купить", "искать", "найти", "открывать", "открыть", "закрывать",
    "закрыть", "помогать", "помочь", "играть", "писать", "написать",
    "читать", "прочитать", "слушать", "смотреть", "посмотреть",
    "есть", "пить", "спать", "начинать", "начать", "кончать",
    "кончить", "ждать", "отвечать", "ответить", "спрашивать",
    "спросить", "учиться", "возвращаться", "вернуться", "использовать",
    "нужно", "надо",
    # nouns (lowercase in Russian spaCy)
    "дом", "человек", "мужчина", "женщина", "ребёнок", "ребенок",
    "мальчик", "девочка", "семья", "отец", "мать", "брат", "сестра",
    "сын", "дочь", "друг", "подруга", "работа", "время", "год", "день",
    "месяц", "неделя", "час", "минута", "секунда", "страна", "город",
    "деревня", "улица", "книга", "стол", "стул", "кровать", "ванная",
    "кухня", "комната", "еда", "вода", "молоко", "хлеб", "мясо",
    "рыба", "фрукт", "овощ", "завтрак", "обед", "ужин", "машина",
    "автобус", "поезд", "самолёт", "велосипед", "деньги", "цена",
    "магазин", "рынок", "имя", "номер", "проблема", "вопрос", "ответ",
    "слово", "язык", "вещь", "мир", "жизнь", "место", "раз", "способ",
    "школа", "университет", "ученик", "учитель", "класс", "урок",
    "дверь", "окно", "сад", "парк", "пляж", "гора", "собака", "кошка",
    "птица", "цветок", "дерево",
    # adjectives
    "хороший", "плохой", "большой", "маленький", "новый", "старый",
    "молодой", "красивый", "некрасивый", "высокий", "низкий", "длинный",
    "короткий", "широкий", "узкий", "лёгкий", "трудный", "тяжёлый",
    "быстрый", "медленный", "горячий", "холодный", "дешёвый", "дорогой",
    "свободный", "занятой", "открытый", "закрытый", "чистый", "грязный",
    "полный", "пустой", "первый", "второй", "последний", "одинаковый",
    "другой", "весь", "многий", "мало", "важный", "разный", "правильный",
    "неправильный", "счастливый", "грустный", "усталый", "больной",
    "здоровый",
    # numbers
    "один", "два", "три", "четыре", "пять", "шесть", "семь", "восемь",
    "девять", "десять", "одиннадцать", "двенадцать", "тринадцать",
    "четырнадцать", "пятнадцать", "шестнадцать", "семнадцать",
    "восемнадцать", "девятнадцать", "двадцать", "тридцать", "сорок",
    "пятьдесят", "шестьдесят", "семьдесят", "восемьдесят", "девяносто",
    "сто", "тысяча", "миллион",
    # days
    "понедельник", "вторник", "среда", "четверг", "пятница",
    "суббота", "воскресенье",
    # months
    "январь", "февраль", "март", "апрель", "май", "июнь", "июль",
    "август", "сентябрь", "октябрь", "ноябрь", "декабрь",
    # colours
    "красный", "синий", "голубой", "зелёный", "жёлтый", "белый",
    "чёрный", "серый", "коричневый", "оранжевый", "розовый",
    "фиолетовый",
    # adverbs / time
    "здесь", "тут", "там", "сегодня", "вчера", "завтра", "сейчас",
    "раньше", "потом", "после", "всегда", "никогда", "тоже", "очень",
    "хорошо", "плохо", "больше", "меньше", "только", "много", "мало",
    "поздно", "рано", "быстро", "близко", "далеко",
})

# ── Japanese (ja) ─────────────────────────────────────────────────────────────
# Lemmas as returned by spaCy + SudachiPy (kanji/kana forms).
# Coverage is limited compared to alphabetic languages — extend as patterns
# in authentic text emerge from user feedback.
_JA_A1: frozenset[str] = frozenset({
    # core verbs (dictionary form)
    "食べる", "飲む", "行く", "来る", "する", "ある", "いる", "見る",
    "聞く", "話す", "読む", "書く", "買う", "寝る", "起きる", "働く",
    "住む", "分かる", "知る", "思う", "言う", "教える", "勉強する",
    "使う", "入る", "出る", "開ける", "閉める", "手伝う", "遊ぶ",
    "始める", "終わる", "帰る", "探す", "待つ", "答える", "聞こえる",
    "見える", "会う", "乗る", "降りる",
    # nouns
    "人", "男", "女", "子供", "男の子", "女の子", "家族", "父", "母",
    "兄", "弟", "姉", "妹", "息子", "娘", "友達", "仕事", "時間",
    "年", "月", "日", "週間", "時", "分", "秒", "国", "町", "村",
    "道", "本", "机", "椅子", "ベッド", "お風呂", "台所", "部屋",
    "食べ物", "水", "牛乳", "パン", "肉", "魚", "果物", "野菜",
    "朝ごはん", "昼ごはん", "晩ごはん", "車", "バス", "電車",
    "飛行機", "自転車", "お金", "値段", "店", "名前", "番号",
    "問題", "質問", "答え", "言葉", "言語", "もの", "世界", "生活",
    "場所", "学校", "大学", "生徒", "先生", "クラス", "授業",
    "ドア", "窓", "庭", "公園", "海", "山", "犬", "猫", "鳥",
    "花", "木",
    # adjectives (i-adj dictionary form / na-adj base)
    "大きい", "小さい", "新しい", "古い", "若い", "よい", "良い",
    "悪い", "高い", "低い", "長い", "短い", "広い", "狭い",
    "易しい", "難しい", "速い", "遅い", "熱い", "冷たい", "暑い",
    "寒い", "安い", "高い", "きれい", "かわいい", "楽しい", "嬉しい",
    "悲しい", "疲れる", "元気",
    # numbers
    "一", "二", "三", "四", "五", "六", "七", "八", "九", "十",
    "百", "千", "万",
    # days
    "月曜日", "火曜日", "水曜日", "木曜日", "金曜日", "土曜日",
    "日曜日",
    # months (as nouns: 一月 etc. — spaCy typically lemmatises to kanji numerals)
    "一月", "二月", "三月", "四月", "五月", "六月", "七月",
    "八月", "九月", "十月", "十一月", "十二月",
    # colours
    "赤", "青", "緑", "黄色", "白", "黒", "灰色", "茶色", "オレンジ",
    "ピンク", "紫",
    # common adverbs / time expressions
    "ここ", "そこ", "あそこ", "今日", "昨日", "明日", "今", "前",
    "後", "いつも", "ぜんぜん", "とても", "よく", "もっと", "少し",
    "たくさん", "もう", "まだ",
})

# ── Chinese Simplified (zh) ───────────────────────────────────────────────────
# Keys are jieba surface/canonical forms (no .lower() needed — Chinese has no case).
_ZH_A1: frozenset[str] = frozenset({
    # core verbs
    "是", "有", "做", "去", "来", "能", "可以", "要", "想", "知道",
    "说", "看", "给", "拿", "买", "找", "开", "关", "帮", "玩",
    "写", "读", "听", "学", "工作", "住", "爱", "想", "吃", "喝",
    "睡", "开始", "结束", "等", "回答", "问", "用", "需要", "喜欢",
    "回", "走", "跑", "坐", "站", "看", "带", "送",
    # nouns — people & family
    "人", "男人", "女人", "孩子", "男孩", "女孩", "家庭", "父亲",
    "母亲", "爸爸", "妈妈", "哥哥", "弟弟", "姐姐", "妹妹", "儿子",
    "女儿", "朋友",
    # nouns — time
    "时间", "年", "月", "日", "天", "周", "星期", "小时", "分钟",
    "秒", "今天", "昨天", "明天", "现在", "早上", "下午", "晚上",
    # nouns — place & travel
    "国家", "城市", "村", "街道", "路", "家", "学校", "大学",
    "商店", "市场", "公园", "海边", "山", "公司",
    # nouns — home & everyday
    "书", "桌子", "椅子", "床", "浴室", "厨房", "房间", "门", "窗",
    # nouns — food & drink
    "食物", "水", "牛奶", "面包", "肉", "鱼", "水果", "蔬菜",
    "早饭", "午饭", "晚饭", "米饭", "面条",
    # nouns — transport & money
    "汽车", "公共汽车", "火车", "飞机", "自行车", "钱", "价格",
    # nouns — language & school
    "名字", "号码", "问题", "答案", "词", "语言", "老师", "学生",
    "课", "作业",
    # nouns — nature & animals
    "狗", "猫", "鸟", "花", "树",
    # adjectives
    "好", "坏", "大", "小", "新", "旧", "老", "年轻", "漂亮",
    "高", "矮", "长", "短", "宽", "窄", "容易", "难", "快", "慢",
    "热", "冷", "便宜", "贵", "干净", "脏", "满", "空",
    "第一", "第二", "最后", "同", "另", "所有", "很多", "一点",
    "重要", "不同", "快乐", "难过", "累", "生病", "健康",
    # numbers
    "一", "二", "三", "四", "五", "六", "七", "八", "九", "十",
    "十一", "十二", "二十", "三十", "四十", "五十", "六十", "七十",
    "八十", "九十", "百", "千", "万",
    # days
    "星期一", "星期二", "星期三", "星期四", "星期五", "星期六",
    "星期天", "星期日",
    # months
    "一月", "二月", "三月", "四月", "五月", "六月",
    "七月", "八月", "九月", "十月", "十一月", "十二月",
    # colours
    "红", "蓝", "绿", "黄", "白", "黑", "灰", "棕", "橙", "粉", "紫",
    # adverbs / time
    "这里", "那里", "今天", "昨天", "明天", "现在", "以前", "以后",
    "总是", "从不", "也", "非常", "很", "好", "更", "只", "多",
    "少", "晚", "早", "快", "近", "远",
})

# ── Arabic (ar) ───────────────────────────────────────────────────────────────
# Keys are undiacritised (tashkeel-stripped) forms — must match output of
# arabic.py's _strip_tashkeel() exactly.
_AR_A1: frozenset[str] = frozenset({
    # core verbs (past-tense root form as typically cited)
    "كان", "صار", "أصبح", "فعل", "ذهب", "جاء", "أتى", "أخذ", "أعطى",
    "قال", "رأى", "عرف", "قدر", "أراد", "فهم", "وجد", "بحث", "فتح",
    "أغلق", "ساعد", "لعب", "كتب", "قرأ", "سمع", "درس", "عمل",
    "سكن", "أحب", "اشترى", "أكل", "شرب", "نام", "بدأ", "انتهى",
    "انتظر", "أجاب", "سأل", "استخدم", "احتاج", "رجع", "مشى", "ركب",
    # nouns — people & family
    "إنسان", "رجل", "امرأة", "طفل", "ولد", "بنت", "عائلة", "أسرة",
    "أب", "أم", "أخ", "أخت", "ابن", "ابنة", "صديق", "صديقة",
    # nouns — time
    "وقت", "سنة", "عام", "شهر", "أسبوع", "يوم", "ساعة", "دقيقة",
    "ثانية",
    # nouns — place & travel
    "بلد", "مدينة", "قرية", "شارع", "بيت", "مدرسة", "جامعة",
    "دكان", "سوق", "حديقة", "شاطئ", "جبل",
    # nouns — home & everyday
    "كتاب", "طاولة", "كرسي", "سرير", "حمام", "مطبخ", "غرفة",
    "باب", "نافذة",
    # nouns — food & drink
    "طعام", "ماء", "حليب", "خبز", "لحم", "سمك", "فاكهة", "خضار",
    "فطور", "غداء", "عشاء",
    # nouns — transport & money
    "سيارة", "حافلة", "قطار", "طائرة", "دراجة", "مال", "ثمن",
    # nouns — language & school
    "اسم", "رقم", "مشكلة", "سؤال", "جواب", "كلمة", "لغة",
    "طالب", "معلم", "درس", "فصل",
    # nouns — nature & animals
    "كلب", "قطة", "طائر", "زهرة", "شجرة",
    # adjectives
    "جيد", "سيئ", "كبير", "صغير", "جديد", "قديم", "شاب", "جميل",
    "طويل", "قصير", "واسع", "ضيق", "سهل", "صعب", "سريع", "بطيء",
    "حار", "بارد", "رخيص", "غالي", "نظيف", "وسخ", "ممتلئ", "فارغ",
    "أول", "ثاني", "أخير", "مهم", "مختلف", "سعيد", "حزين", "تعبان",
    "مريض", "صحي",
    # numbers
    "واحد", "اثنان", "ثلاثة", "أربعة", "خمسة", "ستة", "سبعة",
    "ثمانية", "تسعة", "عشرة", "أحد عشر", "اثنا عشر", "عشرون",
    "ثلاثون", "مئة", "ألف",
    # days
    "الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة",
    "السبت", "الأحد",
    # months (Levantine/Modern Standard Arabic)
    "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
    "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر",
    # colours
    "أحمر", "أزرق", "أخضر", "أصفر", "أبيض", "أسود", "رمادي",
    "بني", "برتقالي", "وردي", "بنفسجي",
    # adverbs / time
    "هنا", "هناك", "اليوم", "أمس", "غدا", "الآن", "قبل", "بعد",
    "دائما", "أبدا", "أيضا", "جدا", "كثيرا", "قليلا",
    "متأخرا", "مبكرا", "بعيدا", "قريبا",
})

# ── Hebrew (he) ───────────────────────────────────────────────────────────────
# Keys are nikud-stripped (unvocalised) forms — must match output of
# hebrew.py's _strip_nikud() exactly.
_HE_A1: frozenset[str] = frozenset({
    # core verbs (infinitive / common conjugation stem)
    "היה", "עשה", "הלך", "בא", "יכול", "רצה", "ידע", "אמר",
    "ראה", "נתן", "לקח", "חשב", "הבין", "מצא", "חיפש", "פתח",
    "סגר", "עזר", "שיחק", "כתב", "קרא", "שמע", "למד", "עבד",
    "גר", "אהב", "קנה", "אכל", "שתה", "ישן", "התחיל", "סיים",
    "חיכה", "ענה", "שאל", "השתמש", "צריך", "חזר", "הלך", "רץ",
    # nouns — people & family
    "אדם", "איש", "אישה", "ילד", "ילדה", "משפחה", "אב", "אמא",
    "אח", "אחות", "בן", "בת", "חבר", "חברה",
    # nouns — time
    "זמן", "שנה", "חודש", "שבוע", "יום", "שעה", "דקה", "שנייה",
    # nouns — place & travel
    "ארץ", "עיר", "כפר", "רחוב", "בית", "בית ספר", "אוניברסיטה",
    "חנות", "שוק", "גן", "חוף", "הר",
    # nouns — home & everyday
    "ספר", "שולחן", "כיסא", "מיטה", "אמבטיה", "מטבח", "חדר",
    "דלת", "חלון",
    # nouns — food & drink
    "אוכל", "מים", "חלב", "לחם", "בשר", "דג", "פרי", "ירק",
    "ארוחת בוקר", "ארוחת צהריים", "ארוחת ערב",
    # nouns — transport & money
    "מכונית", "אוטובוס", "רכבת", "מטוס", "אופניים", "כסף", "מחיר",
    # nouns — language & school
    "שם", "מספר", "בעיה", "שאלה", "תשובה", "מילה", "שפה",
    "תלמיד", "מורה", "שיעור", "כיתה",
    # nouns — nature & animals
    "כלב", "חתול", "ציפור", "פרח", "עץ",
    # adjectives
    "טוב", "רע", "גדול", "קטן", "חדש", "ישן", "צעיר", "יפה",
    "גבוה", "נמוך", "ארוך", "קצר", "רחב", "צר", "קל", "קשה",
    "מהיר", "איטי", "חם", "קר", "זול", "יקר", "נקי", "מלוכלך",
    "מלא", "ריק", "ראשון", "שני", "אחרון", "חשוב", "שונה",
    "שמח", "עצוב", "עייף", "חולה", "בריא",
    # numbers
    "אחד", "שניים", "שלושה", "ארבעה", "חמישה", "שישה", "שבעה",
    "שמונה", "תשעה", "עשרה", "אחד עשר", "שנים עשר", "עשרים",
    "שלושים", "מאה", "אלף",
    # days
    "ראשון", "שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת",
    # months (Gregorian names used in modern Hebrew)
    "ינואר", "פברואר", "מרץ", "אפריל", "מאי", "יוני",
    "יולי", "אוגוסט", "ספטמבר", "אוקטובר", "נובמבר", "דצמבר",
    # colours
    "אדום", "כחול", "ירוק", "צהוב", "לבן", "שחור", "אפור",
    "חום", "כתום", "ורוד", "סגול",
    # adverbs / time
    "כאן", "שם", "היום", "אתמול", "מחר", "עכשיו", "לפני", "אחרי",
    "תמיד", "אף פעם", "גם", "מאוד", "הרבה", "קצת", "מאוחר",
    "מוקדם", "רחוק", "קרוב",
})

# ── Public API ────────────────────────────────────────────────────────────────

#: Map from language code to frozenset of A1 lemmas.
A1: dict[str, frozenset[str]] = {
    "es": _ES_A1,
    "fr": _FR_A1,
    "de": _DE_A1,
    "it": _IT_A1,
    "pt": _PT_A1,
    "ru": _RU_A1,
    "ja": _JA_A1,
    "zh": _ZH_A1,
    "ar": _AR_A1,
    "he": _HE_A1,
}
