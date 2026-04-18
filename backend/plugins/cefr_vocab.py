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
    # body parts
    "cabeza", "cara", "ojo", "oreja", "nariz", "boca", "diente", "cuello",
    "brazo", "mano", "dedo", "pierna", "pie", "espalda", "estómago", "pelo",
    # animals (extended)
    "caballo", "vaca", "elefante", "serpiente", "conejo", "cerdo", "oveja",
    "león", "ratón", "tigre", "oso", "mono", "pato", "zorro", "lobo",
    # food & drink (extended)
    "banana", "mantequilla", "pastel", "zanahoria", "queso", "chocolate",
    "huevo", "helado", "zumo", "jugo", "cebolla", "pasta", "pizza",
    "patata", "arroz", "ensalada", "sal", "bocadillo", "sopa", "azúcar",
    "tomate", "miel", "champiñón", "fresa", "uva", "limón", "judía",
    "pimiento", "naranja",
    # clothes & accessories
    "ropa", "bota", "abrigo", "vestido", "sombrero", "chaqueta", "vaquero",
    "camisa", "zapato", "falda", "suéter", "camiseta", "pantalón",
    "paraguas", "calcetín", "guante", "bufanda", "cinturón", "anillo",
    "reloj", "bicicleta",
    # technology & media
    "cámara", "computadora", "ordenador", "correo", "internet", "teléfono",
    "radio", "televisión", "vídeo", "blog", "web", "revista", "periódico",
    # places (extended)
    "aeropuerto", "bar", "cafetería", "cine", "granja", "gimnasio",
    "hospital", "hotel", "isla", "biblioteca", "museo", "piscina",
    "restaurante", "supermercado", "teatro", "fábrica", "castillo",
    "iglesia", "mezquita",
    # people & professions
    "actor", "actriz", "adulto", "artista", "cliente", "bailarín",
    "conductor", "granjero", "enfermero", "jugador", "policía", "científico",
    "adolescente", "turista", "visitante", "camarero", "trabajador",
    "escritor", "cantante", "médico", "bebé", "cocinero", "dentista",
    "ingeniero", "piloto", "soldado",
    # verbs (extended)
    "construir", "cambiar", "elegir", "escalar", "costar", "decidir",
    "morir", "dibujar", "arreglar", "volar", "adivinar", "odiar",
    "incluir", "presentar", "reír", "perder", "mover", "pintar",
    "pagar", "relajar", "recordar", "repetir", "montar", "enviar",
    "viajar", "despertar", "vestir", "ganar", "correr", "vender",
    "nadar", "caer", "romper", "soñar", "preferir", "prometer",
    "cantar", "mostrar",
    # adjectives (extended)
    "asustado", "increíble", "enojado", "rubio", "aburrido", "peligroso",
    "oscuro", "delicioso", "seco", "emocionado", "famoso", "fantástico",
    "gordo", "simpático", "gracioso", "genial", "duro", "casado", "moderno",
    "perfecto", "popular", "posible", "tranquilo", "real", "rico",
    "especial", "fuerte", "verdadero", "cálido", "maravilloso", "hermoso",
    "correcto", "terrible", "seguro", "inteligente", "perezoso", "educado",
    "grosero", "raro", "delgado", "afortunado",
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
    # body parts
    "tête", "visage", "œil", "oreille", "nez", "bouche", "dent", "cou",
    "bras", "main", "doigt", "jambe", "pied", "dos", "ventre", "cheveu",
    # animals (extended)
    "cheval", "vache", "éléphant", "serpent", "lapin", "cochon", "mouton",
    "lion", "souris", "tigre", "ours", "singe", "canard", "renard", "loup",
    # food & drink (extended)
    "banane", "beurre", "gâteau", "carotte", "fromage", "chocolat",
    "œuf", "glace", "jus", "oignon", "pâte", "pizza", "pomme",
    "riz", "salade", "sel", "sandwich", "soupe", "sucre", "tomate",
    "miel", "champignon", "fraise", "raisin", "citron", "haricot",
    "poivron",
    # clothes & accessories
    "botte", "manteau", "robe", "chapeau", "veste", "jean", "chemise",
    "chaussure", "jupe", "pull", "tee-shirt", "pantalon", "parapluie",
    "chaussette", "gant", "écharpe", "ceinture", "bague", "montre",
    # technology & media
    "caméra", "ordinateur", "courriel", "internet", "téléphone", "radio",
    "télévision", "vidéo", "blog", "site", "magazine", "journal",
    "programme", "vélo", "taxi",
    # places (extended)
    "aéroport", "bar", "café", "cinéma", "ferme", "gymnase",
    "hôpital", "hôtel", "île", "bibliothèque", "musée", "piscine",
    "restaurant", "supermarché", "théâtre", "usine", "château",
    "église", "mosquée",
    # people & professions
    "acteur", "actrice", "adulte", "artiste", "client", "danseur",
    "chauffeur", "fermier", "infirmier", "joueur", "policier",
    "scientifique", "adolescent", "touriste", "visiteur", "serveur",
    "travailleur", "écrivain", "chanteur", "bébé", "médecin",
    "cuisinier", "dentiste", "ingénieur", "pilote", "soldat",
    # verbs (extended)
    "construire", "changer", "choisir", "grimper", "coûter", "décider",
    "mourir", "dessiner", "expliquer", "réparer", "voler", "oublier",
    "deviner", "haïr", "inclure", "présenter", "garder", "rire",
    "perdre", "bouger", "peindre", "payer", "détendre", "répéter",
    "monter", "envoyer", "voyager", "réveiller", "porter", "gagner",
    "courir", "vendre", "nager", "tomber", "casser", "rêver",
    "marier", "préférer", "promettre", "chanter", "montrer",
    # adjectives (extended)
    "effrayé", "incroyable", "colère", "blond", "ennuyeux", "dangereux",
    "sombre", "délicieux", "sec", "excité", "célèbre", "fantastique",
    "gros", "sympa", "drôle", "génial", "dur", "marié", "moderne",
    "parfait", "populaire", "possible", "joli", "calme", "réel",
    "riche", "spécial", "fort", "vrai", "merveilleux", "correct",
    "terrible", "sûr", "intelligent", "paresseux", "poli", "grossier",
    "bizarre", "mince", "chanceux",
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
    # body parts (Title-cased nouns)
    "Kopf", "Gesicht", "Auge", "Ohr", "Nase", "Mund", "Zahn", "Hals",
    "Arm", "Hand", "Finger", "Bein", "Fuß", "Rücken", "Bauch", "Haar",
    # animals (extended — Title-cased)
    "Pferd", "Kuh", "Elefant", "Schlange", "Kaninchen", "Schwein",
    "Schaf", "Löwe", "Maus", "Tiger", "Bär", "Affe", "Ente", "Fuchs",
    "Wolf",
    # food & drink (extended — Title-cased)
    "Banane", "Butter", "Kuchen", "Karotte", "Käse", "Schokolade",
    "Ei", "Eis", "Saft", "Zwiebel", "Nudel", "Pizza", "Kartoffel",
    "Reis", "Salat", "Salz", "Sandwich", "Suppe", "Zucker", "Tomate",
    "Honig", "Pilz", "Erdbeere", "Traube", "Zitrone", "Bohne",
    "Paprika", "Orange",
    # clothes & accessories (Title-cased)
    "Kleidung", "Stiefel", "Mantel", "Kleid", "Hut", "Jacke", "Jeans",
    "Hemd", "Schuh", "Rock", "Pullover", "T-Shirt", "Hose",
    "Regenschirm", "Socke", "Handschuh", "Schal", "Gürtel", "Ring",
    "Uhr", "Fahrrad",
    # technology & media (Title-cased)
    "Kamera", "Computer", "E-Mail", "Internet", "Telefon", "Radio",
    "Fernseher", "Video", "Blog", "Webseite", "Zeitschrift", "Zeitung",
    "Programm", "Taxi",
    # places (extended — Title-cased)
    "Flughafen", "Bar", "Café", "Kino", "Bauernhof", "Fitnessstudio",
    "Krankenhaus", "Hotel", "Insel", "Bibliothek", "Museum",
    "Schwimmbad", "Restaurant", "Supermarkt", "Theater", "Fabrik",
    "Schloss", "Kirche", "Moschee",
    # people & professions (Title-cased)
    "Schauspieler", "Schauspielerin", "Erwachsener", "Künstler",
    "Kunde", "Tänzer", "Fahrer", "Bauer", "Krankenschwester",
    "Spieler", "Polizist", "Wissenschaftler", "Teenager", "Tourist",
    "Besucher", "Kellner", "Arbeiter", "Schriftsteller", "Sänger",
    "Baby", "Arzt", "Koch", "Zahnarzt", "Ingenieur", "Pilot", "Soldat",
    # verbs (lowercase)
    "bauen", "ändern", "wählen", "klettern", "entscheiden", "sterben",
    "zeichnen", "erklären", "reparieren", "vergessen", "raten", "hassen",
    "einschließen", "vorstellen", "behalten", "lachen", "verlieren",
    "meinen", "vermissen", "bewegen", "malen", "bezahlen", "entspannen",
    "erinnern", "wiederholen", "reiten", "rennen", "schicken", "stehen",
    "schwimmen", "reisen", "aufwachen", "tragen", "gewinnen",
    "verkaufen", "fallen", "brechen", "träumen", "heiraten",
    "bevorzugen", "versprechen", "singen", "zeigen",
    # adjectives (lowercase)
    "ängstlich", "erstaunlich", "wütend", "blond", "langweilig",
    "gefährlich", "dunkel", "lecker", "trocken", "aufgeregt", "berühmt",
    "fantastisch", "dick", "freundlich", "lustig", "großartig", "hart",
    "verheiratet", "modern", "perfekt", "beliebt", "möglich", "hübsch",
    "ruhig", "echt", "reich", "sicher", "speziell", "stark", "wahr",
    "wunderbar", "schrecklich", "klug", "faul", "höflich", "unhöflich",
    "seltsam", "dünn", "glücklich",
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
    # body parts
    "testa", "faccia", "occhio", "orecchio", "naso", "bocca", "dente",
    "collo", "braccio", "mano", "dito", "gamba", "piede", "schiena",
    "pancia", "capello",
    # animals (extended)
    "cavallo", "mucca", "elefante", "serpente", "coniglio", "maiale",
    "pecora", "leone", "topo", "tigre", "orso", "scimmia", "anatra",
    "volpe", "lupo",
    # food & drink (extended)
    "banana", "burro", "torta", "carota", "formaggio", "cioccolato",
    "uovo", "gelato", "succo", "cipolla", "pasta", "pizza", "patata",
    "riso", "insalata", "sale", "panino", "zuppa", "zucchero",
    "pomodoro", "miele", "fungo", "fragola", "uva", "limone",
    "fagiolo", "peperone",
    # clothes & accessories
    "vestiti", "stivale", "cappotto", "vestito", "cappello", "giacca",
    "jeans", "camicia", "scarpa", "gonna", "maglione", "maglietta",
    "pantaloni", "ombrello", "calzino", "guanto", "sciarpa", "cintura",
    "anello", "orologio", "bicicletta",
    # technology & media
    "macchina fotografica", "computer", "email", "internet", "telefono",
    "radio", "televisione", "video", "blog", "sito", "rivista",
    "giornale", "programma", "taxi",
    # places (extended)
    "aeroporto", "bar", "caffè", "cinema", "fattoria", "palestra",
    "ospedale", "hotel", "isola", "biblioteca", "museo", "piscina",
    "ristorante", "supermercato", "teatro", "fabbrica", "castello",
    "chiesa", "moschea",
    # people & professions
    "attore", "attrice", "adulto", "artista", "cliente", "ballerino",
    "autista", "contadino", "infermiere", "giocatore", "poliziotto",
    "scienziato", "adolescente", "turista", "visitatore", "cameriere",
    "lavoratore", "scrittore", "cantante", "neonato", "dottore",
    "cuoco", "dentista", "ingegnere", "pilota", "soldato",
    # verbs (extended)
    "costruire", "cambiare", "scegliere", "arrampicarsi", "costare",
    "decidere", "morire", "disegnare", "spiegare", "riparare", "volare",
    "dimenticare", "indovinare", "odiare", "includere", "presentare",
    "tenere", "ridere", "perdere", "muovere", "dipingere", "pagare",
    "rilassare", "ricordare", "ripetere", "cavalcare", "correre",
    "mandare", "stare", "nuotare", "viaggiare", "svegliare", "portare",
    "vincere", "vendere", "cadere", "rompere", "sognare", "sposare",
    "preferire", "promettere", "cantare", "mostrare",
    # adjectives (extended)
    "spaventato", "incredibile", "arrabbiato", "biondo", "noioso",
    "pericoloso", "scuro", "delizioso", "asciutto", "emozionato",
    "famoso", "fantastico", "grasso", "simpatico", "divertente",
    "geniale", "duro", "sposato", "moderno", "perfetto", "popolare",
    "possibile", "carino", "tranquillo", "reale", "ricco", "speciale",
    "forte", "vero", "meraviglioso", "corretto", "terribile", "sicuro",
    "intelligente", "pigro", "educato", "maleducato", "strano",
    "magro", "fortunato",
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
    # body parts
    "cabeça", "rosto", "olho", "orelha", "nariz", "boca", "dente",
    "pescoço", "braço", "mão", "dedo", "perna", "pé", "costas",
    "barriga", "cabelo",
    # animals (extended)
    "cavalo", "vaca", "elefante", "cobra", "coelho", "porco", "ovelha",
    "leão", "rato", "tigre", "urso", "macaco", "pato", "raposa", "lobo",
    # food & drink (extended)
    "banana", "manteiga", "bolo", "cenoura", "queijo", "chocolate",
    "ovo", "gelado", "sorvete", "sumo", "suco", "cebola", "massa",
    "pizza", "batata", "arroz", "salada", "sal", "sandes", "sanduíche",
    "sopa", "açúcar", "tomate", "mel", "cogumelo", "morango", "uva",
    "limão", "feijão", "pimento",
    # clothes & accessories
    "roupa", "bota", "casaco", "vestido", "chapéu", "jaqueta", "jeans",
    "camisa", "sapato", "saia", "camisola", "camiseta", "calças",
    "guarda-chuva", "meia", "luva", "cachecol", "cinto", "anel",
    "relógio", "taxi",
    # technology & media
    "câmara", "computador", "email", "internet", "telefone", "rádio",
    "televisão", "vídeo", "blog", "website", "revista", "jornal",
    "programa",
    # places (extended)
    "aeroporto", "bar", "café", "cinema", "quinta", "ginásio",
    "hospital", "hotel", "ilha", "biblioteca", "museu", "piscina",
    "restaurante", "supermercado", "teatro", "fábrica", "castelo",
    "igreja", "mesquita",
    # people & professions
    "ator", "atriz", "adulto", "artista", "cliente", "bailarino",
    "motorista", "agricultor", "enfermeiro", "jogador", "polícia",
    "cientista", "adolescente", "turista", "visitante", "empregado",
    "trabalhador", "escritor", "cantor", "bebé", "bebê", "médico",
    "cozinheiro", "dentista", "engenheiro", "piloto", "soldado",
    # verbs (extended)
    "construir", "mudar", "escolher", "escalar", "custar", "decidir",
    "morrer", "desenhar", "explicar", "arranjar", "voar", "esquecer",
    "adivinhar", "odiar", "incluir", "apresentar", "guardar", "rir",
    "perder", "mover", "pintar", "pagar", "relaxar", "lembrar",
    "repetir", "montar", "correr", "mandar", "nadar", "viajar",
    "acordar", "vestir", "ganhar", "vender", "cair", "partir",
    "sonhar", "casar", "preferir", "prometer", "cantar", "mostrar",
    # adjectives (extended)
    "assustado", "incrível", "zangado", "loiro", "aborrecido",
    "perigoso", "escuro", "delicioso", "seco", "emocionado", "famoso",
    "fantástico", "gordo", "simpático", "engraçado", "óptimo", "duro",
    "casado", "moderno", "perfeito", "popular", "possível", "giro",
    "calmo", "real", "rico", "especial", "forte", "verdadeiro",
    "quente", "maravilhoso", "correto", "terrível", "seguro",
    "inteligente", "preguiçoso", "educado", "malcriado", "estranho",
    "magro", "sortudo",
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
    # body parts
    "голова", "лицо", "глаз", "ухо", "нос", "рот", "зуб", "шея",
    "рука", "палец", "нога", "спина", "живот", "волос",
    # animals (extended)
    "лошадь", "корова", "слон", "змея", "кролик", "свинья", "овца",
    "лев", "мышь", "тигр", "медведь", "обезьяна", "утка", "лиса",
    "волк",
    # food & drink (extended)
    "банан", "масло", "торт", "морковь", "сыр", "шоколад", "яйцо",
    "мороженое", "сок", "лук", "макароны", "пицца", "картошка",
    "рис", "салат", "соль", "бутерброд", "суп", "сахар", "помидор",
    "мёд", "гриб", "клубника", "виноград", "лимон", "фасоль",
    "перец",
    # clothes & accessories
    "одежда", "ботинок", "сапог", "пальто", "платье", "шляпа",
    "шапка", "куртка", "джинсы", "рубашка", "туфля", "юбка",
    "свитер", "футболка", "брюки", "зонт", "носок", "перчатка",
    "шарф", "ремень", "кольцо", "часы", "велосипед",
    # technology & media
    "камера", "компьютер", "имейл", "интернет", "телефон", "радио",
    "телевизор", "видео", "блог", "сайт", "журнал", "газета",
    "программа", "такси",
    # places (extended)
    "аэропорт", "бар", "кафе", "кинотеатр", "ферма", "спортзал",
    "больница", "отель", "остров", "библиотека", "музей", "бассейн",
    "ресторан", "супермаркет", "театр", "завод", "замок", "церковь",
    "мечеть",
    # people & professions
    "актёр", "актриса", "взрослый", "художник", "клиент", "танцор",
    "водитель", "фермер", "медсестра", "игрок", "полицейский",
    "учёный", "певец", "подросток", "турист", "посетитель",
    "официант", "рабочий", "писатель", "младенец", "врач", "повар",
    "стоматолог", "инженер", "пилот", "солдат",
    # verbs (extended)
    "строить", "менять", "выбирать", "карабкаться", "стоить",
    "решать", "умирать", "рисовать", "объяснять", "чинить", "летать",
    "забывать", "угадывать", "ненавидеть", "включать", "представлять",
    "сохранять", "смеяться", "терять", "двигаться", "красить",
    "платить", "отдыхать", "помнить", "повторять", "ехать", "бегать",
    "посылать", "стоять", "плавать", "путешествовать", "просыпаться",
    "носить", "выигрывать", "продавать", "падать", "ломать", "мечтать",
    "жениться", "предпочитать", "обещать", "петь", "показывать",
    # adjectives (extended)
    "испуганный", "удивительный", "злой", "русый", "скучный",
    "опасный", "тёмный", "вкусный", "сухой", "взволнованный",
    "знаменитый", "фантастический", "толстый", "дружелюбный",
    "смешной", "замечательный", "жёсткий", "женатый", "замужем",
    "современный", "идеальный", "популярный", "возможный", "симпатичный",
    "тихий", "настоящий", "богатый", "особенный", "сильный",
    "прекрасный", "правильный", "ужасный", "уверенный", "умный",
    "ленивый", "вежливый", "грубый", "странный", "тонкий", "везучий",
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
    # body parts
    "頭", "顔", "目", "耳", "鼻", "口", "歯", "首", "腕", "手",
    "指", "足", "背中", "お腹", "髪",
    # animals (extended)
    "馬", "牛", "象", "蛇", "うさぎ", "豚", "羊", "ライオン",
    "ねずみ", "トラ", "クマ", "サル", "アヒル", "キツネ", "オオカミ",
    # food & drink (extended)
    "バナナ", "バター", "ケーキ", "にんじん", "チーズ", "チョコレート",
    "卵", "アイスクリーム", "ジュース", "たまねぎ", "パスタ", "ピザ",
    "じゃがいも", "ご飯", "サラダ", "塩", "サンドイッチ", "スープ",
    "砂糖", "トマト", "はちみつ", "きのこ", "いちご", "ぶどう",
    "レモン", "豆", "ピーマン",
    # clothes & accessories
    "服", "ブーツ", "コート", "ワンピース", "帽子", "ジャケット",
    "ジーンズ", "シャツ", "靴", "スカート", "セーター", "Tシャツ",
    "ズボン", "傘", "靴下", "手袋", "マフラー", "ベルト", "指輪",
    "時計", "自転車",
    # technology & media
    "カメラ", "パソコン", "メール", "インターネット", "電話",
    "ラジオ", "テレビ", "ビデオ", "ブログ", "ウェブサイト",
    "雑誌", "新聞", "番組", "タクシー",
    # places (extended)
    "空港", "バー", "カフェ", "映画館", "農場", "ジム", "病院",
    "ホテル", "島", "図書館", "美術館", "プール", "レストラン",
    "スーパー", "劇場", "工場", "城", "教会", "モスク",
    # people & professions
    "俳優", "大人", "芸術家", "お客さん", "ダンサー", "運転手",
    "農家", "看護師", "選手", "警察官", "科学者", "歌手",
    "ティーンエイジャー", "観光客", "訪問者", "ウェイター",
    "労働者", "作家", "赤ちゃん", "医者", "料理人", "歯医者",
    "エンジニア", "パイロット", "兵士",
    # verbs (extended)
    "建てる", "変える", "選ぶ", "登る", "かかる", "決める", "死ぬ",
    "描く", "説明する", "直す", "飛ぶ", "忘れる", "笑う", "失う",
    "動く", "払う", "覚える", "繰り返す", "走る", "送る", "立つ",
    "泳ぐ", "旅行する", "着る", "勝つ", "売る", "転ぶ", "壊す",
    "夢見る", "結婚する", "好む", "約束する", "歌う", "見せる",
    # i-adjectives (extended)
    "怖い", "すごい", "美しい", "暗い", "乾いた", "太った", "面白い",
    "賢い", "強い", "温かい", "正しい", "ひどい", "細い",
    # na-adjective bases / nouns used attributively (extended)
    "有名", "退屈", "危険", "元気", "静か", "現代的", "完璧",
    "人気", "可能", "特別", "安全", "丁寧", "奇妙", "幸運",
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
    # body parts
    "头", "脸", "眼睛", "耳朵", "鼻子", "嘴", "牙齿", "脖子",
    "手臂", "手", "手指", "腿", "脚", "背", "肚子", "头发",
    # animals (extended)
    "马", "牛", "大象", "蛇", "兔子", "猪", "羊", "狮子",
    "老鼠", "老虎", "熊", "猴子", "鸭子", "狐狸", "狼",
    # food & drink (extended)
    "香蕉", "黄油", "蛋糕", "胡萝卜", "奶酪", "巧克力",
    "鸡蛋", "冰淇淋", "果汁", "洋葱", "意大利面", "比萨",
    "土豆", "沙拉", "盐", "三明治", "汤", "糖", "西红柿",
    "蜂蜜", "蘑菇", "草莓", "葡萄", "柠檬", "豆子", "辣椒",
    # clothes & accessories
    "衣服", "靴子", "外套", "连衣裙", "帽子", "夹克", "牛仔裤",
    "衬衫", "鞋", "裙子", "毛衣", "T恤", "裤子", "雨伞",
    "袜子", "手套", "围巾", "腰带", "戒指", "手表", "自行车",
    # technology & media
    "相机", "电脑", "邮件", "网络", "手机", "收音机",
    "电视", "视频", "博客", "网站", "杂志", "报纸", "节目",
    "出租车",
    # places (extended)
    "机场", "酒吧", "咖啡馆", "电影院", "农场", "健身房",
    "医院", "酒店", "岛", "图书馆", "博物馆", "游泳池",
    "餐厅", "超市", "剧院", "工厂", "城堡", "教堂", "清真寺",
    # people & professions
    "演员", "成人", "艺术家", "顾客", "舞蹈演员", "司机",
    "农民", "护士", "运动员", "警察", "科学家", "歌手",
    "青少年", "游客", "访客", "服务员", "工人", "作家",
    "婴儿", "医生", "厨师", "牙医", "工程师", "飞行员", "士兵",
    # verbs (extended)
    "建造", "改变", "选择", "爬", "花费", "决定", "死",
    "画", "解释", "修理", "飞", "忘记", "猜", "恨",
    "包括", "介绍", "保持", "笑", "失去", "移动",
    "支付", "放松", "记得", "重复", "骑", "发送",
    "游泳", "旅行", "醒来", "穿", "赢", "卖",
    "跌倒", "打破", "做梦", "结婚", "更喜欢", "承诺",
    "唱", "展示",
    # adjectives (extended)
    "害怕", "令人惊讶", "生气", "美丽", "无聊",
    "危险", "黑暗", "美味", "干燥", "兴奋", "著名",
    "极好", "胖", "友好", "有趣", "聪明", "现代",
    "完美", "流行", "可能", "可爱", "安静",
    "富有", "特别", "强壮", "温暖", "精彩", "正确",
    "可怕", "安全", "懒", "有礼貌", "粗鲁", "奇怪",
    "苗条", "幸运",
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
    # body parts
    "رأس", "وجه", "عين", "أذن", "أنف", "فم", "سن", "رقبة",
    "ذراع", "يد", "إصبع", "ساق", "قدم", "ظهر", "بطن", "شعر",
    # animals (extended)
    "حصان", "بقرة", "فيل", "ثعبان", "أرنب", "خنزير", "خروف",
    "أسد", "فأر", "نمر", "دب", "قرد", "بطة", "ثعلب", "ذئب",
    # food & drink (extended)
    "موز", "زبدة", "كعكة", "جزر", "جبن", "شوكولاتة", "بيض",
    "عصير", "بصل", "معكرونة", "بيتزا", "بطاطس", "أرز", "سلطة",
    "ملح", "شطيرة", "شوربة", "سكر", "طماطم", "عسل", "فطر",
    "فراولة", "عنب", "ليمون", "فاصوليا", "فلفل",
    # clothes & accessories
    "ملابس", "حذاء", "معطف", "فستان", "قبعة", "سترة", "جينز",
    "قميص", "تنورة", "كنزة", "بنطلون", "مظلة", "جورب", "قفاز",
    "وشاح", "حزام", "خاتم", "ساعة", "دراجة", "تاكسي",
    # technology & media
    "كاميرا", "حاسوب", "بريد", "إنترنت", "هاتف", "راديو",
    "تلفزيون", "فيديو", "مدونة", "موقع", "مجلة", "جريدة",
    "برنامج",
    # places (extended)
    "مطار", "بار", "مقهى", "سينما", "مزرعة", "نادٍ",
    "مستشفى", "فندق", "جزيرة", "مكتبة", "متحف", "مسبح",
    "مطعم", "سوبرماركت", "مسرح", "مصنع", "قلعة", "كنيسة",
    "مسجد",
    # people & professions
    "ممثل", "ممثلة", "بالغ", "فنان", "زبون", "راقص", "سائق",
    "مزارع", "ممرضة", "لاعب", "شرطي", "عالم", "مغنٍ",
    "مراهق", "سائح", "زائر", "نادل", "عامل", "كاتب",
    "رضيع", "طبيب", "طباخ", "مهندس", "طيار", "جندي",
    # verbs (extended)
    "بنى", "غير", "اختار", "تسلق", "كلف", "قرر", "مات",
    "رسم", "شرح", "أصلح", "طار", "نسي", "خمن", "كره",
    "تضمن", "قدم", "حافظ", "ضحك", "خسر", "تحرك", "دهن",
    "دفع", "استرخى", "تذكر", "كرر", "ركب", "ركض", "أرسل",
    "وقف", "سبح", "سافر", "استيقظ", "لبس", "فاز", "باع",
    "سقط", "كسر", "حلم", "تزوج", "فضل", "وعد", "غنى",
    "أظهر",
    # adjectives (extended)
    "خائف", "مذهل", "غاضب", "أشقر", "ممل", "خطير",
    "مظلم", "لذيذ", "جاف", "متحمس", "مشهور", "رائع",
    "سمين", "ودود", "مضحك", "عظيم", "متزوج", "حديث",
    "مثالي", "شعبي", "ممكن", "هادئ", "حقيقي",
    "غني", "خاص", "قوي", "دافئ", "رهيب",
    "آمن", "ذكي", "كسول", "مؤدب", "وقح", "غريب",
    "نحيف", "محظوظ",
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
    # body parts
    "ראש", "פנים", "עין", "אוזן", "אף", "פה", "שן", "צוואר",
    "זרוע", "יד", "אצבע", "רגל", "גב", "בטן", "שיער",
    # animals (extended)
    "סוס", "פרה", "פיל", "נחש", "ארנב", "חזיר", "כבש",
    "אריה", "עכבר", "נמר", "דב", "קוף", "ברווז", "שועל", "זאב",
    # food & drink (extended)
    "בננה", "חמאה", "עוגה", "גזר", "גבינה", "שוקולד",
    "ביצה", "גלידה", "מיץ", "בצל", "פסטה", "פיצה",
    "אורז", "סלט", "מלח", "כריך", "מרק", "סוכר",
    "עגבניה", "דבש", "פטרייה", "תות", "ענב", "לימון",
    "שעועית", "פלפל",
    # clothes & accessories
    "בגדים", "מגף", "מעיל", "שמלה", "כובע", "ז'קט", "ג'ינס",
    "חולצה", "נעל", "חצאית", "סוודר", "מכנסיים",
    "מטריה", "גרב", "כפפה", "צעיף", "חגורה", "טבעת", "שעון",
    "אופניים",
    # technology & media
    "מצלמה", "מחשב", "אימייל", "אינטרנט", "טלפון", "רדיו",
    "טלוויזיה", "וידאו", "בלוג", "אתר", "מגזין", "עיתון",
    "תוכנית", "מונית",
    # places (extended)
    "שדה", "בר", "קפה", "קולנוע", "חווה", "מועדון",
    "מלון", "אי", "ספרייה", "מוזיאון", "בריכה",
    "מסעדה", "סופרמרקט", "תיאטרון", "מפעל", "טירה",
    "כנסייה", "מסגד",
    # people & professions
    "שחקן", "שחקנית", "מבוגר", "אמן", "לקוח", "רקדן",
    "נהג", "חקלאי", "אחות", "שוטר", "מדען", "זמר",
    "מתבגר", "תייר", "מבקר", "מלצר", "פועל", "סופר",
    "תינוק", "רופא", "טבח", "מהנדס", "טייס", "חייל",
    # verbs (extended)
    "בנה", "שינה", "בחר", "טיפס", "עלה", "החליט", "מת",
    "צייר", "הסביר", "תיקן", "טס", "שכח", "ניחש", "שנא",
    "כלל", "הציג", "שמר", "צחק", "איבד", "זז", "צבע",
    "שילם", "נרגע", "זכר", "חזר", "רכב", "רץ", "שלח",
    "עמד", "שחה", "נסע", "התעורר", "לבש", "ניצח", "מכר",
    "נפל", "שבר", "חלם", "התחתן", "העדיף", "הבטיח",
    "שר", "הראה",
    # adjectives (extended)
    "מפחד", "מדהים", "כועס", "בלונד", "משעמם", "מסוכן",
    "חשוך", "טעים", "יבש", "נרגש", "מפורסם", "נפלא",
    "שמן", "ידידותי", "מצחיק", "נהדר", "קשה", "נשוי",
    "מודרני", "מושלם", "פופולרי", "אפשרי", "חמוד", "שקט",
    "אמיתי", "עשיר", "מיוחד", "חזק", "נכון", "חמים",
    "נורא", "בטוח", "חכם", "עצלן", "מנומס", "גס",
    "מוזר", "רזה", "מזל",
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
