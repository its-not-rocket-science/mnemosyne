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

A1 tables added at project start.
A2 tables added 2026-05-28.  Plugin priority: A1 (0.90) → A2 (0.88) → in-vocab (0.85) → OOV (0.50)
B1 tables added 2026-05-28.  Plugin priority: A1 (0.90) → A2 (0.88) → B1 (0.86) → in-vocab (0.85) → OOV (0.50)

  # In _extract_vocabulary():
  if lemma in _A1:
      data["cefr_level"] = "A1"

A2 tables added 2026-05-28.  Plugin priority:
  A1 (0.90) → A2 (0.88) → in-vocab (0.85) → OOV (0.50)
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

# ── Spanish A2 (es) ───────────────────────────────────────────────────────────
_ES_A2: frozenset[str] = frozenset({
    # extended family & relationships
    "abuelo", "abuela", "nieto", "nieta", "tío", "tía", "primo", "prima",
    "sobrino", "sobrina", "suegro", "suegra", "yerno", "nuera", "cuñado",
    "cuñada", "pareja", "novio", "novia", "colega", "vecino", "vecina",
    "compañero", "conocido",
    # extended workplace & school
    "oficina", "reunión", "jefe", "jefa", "empleado", "empresa", "negocio",
    "proyecto", "informe", "plazo", "sueldo", "salario", "contrato",
    "asignatura", "examen", "nota", "deberes", "tarea", "carrera", "título",
    "materia", "conferencia", "pizarra", "cuaderno",
    # extended travel & transport
    "pasaporte", "billete", "reserva", "maleta", "equipaje", "aduanas",
    "facturación", "tarjeta de embarque", "llegada", "salida", "andén",
    "autopista", "atasco", "aparcamiento", "parada", "ferry", "crucero",
    "excursión", "turismo", "alojamiento",
    # extended home & furniture
    "salón", "comedor", "pasillo", "garaje", "sótano", "ático",
    "estante", "cajón", "lámpara", "alfombra", "cortina", "espejo",
    "nevera", "microondas", "lavadora", "secadora", "grifo", "enchufe",
    # weather
    "lluvia", "nieve", "viento", "tormenta", "rayo", "trueno", "niebla",
    "nublado", "despejado", "temperatura", "húmedo", "helada",
    "grado", "pronóstico",
    # health & body
    "dolor de cabeza", "fiebre", "resfriado", "gripe", "farmacia",
    "receta", "medicina", "pastilla", "operación", "emergencia",
    "ambulancia", "herida", "alergia", "cita",
    # shopping & money
    "recibo", "descuento", "oferta", "talla", "probador", "marca",
    "cartera", "tarjeta", "cuenta", "factura", "cambio", "efectivo",
    "bolsa", "etiqueta", "devolución",
    # food & cooking
    "receta", "ingrediente", "sabor", "menú", "plato", "postre",
    "primer plato", "aperitivo", "propina", "mezclar", "hervir",
    "hornear", "freír", "cortar", "preparar",
    # entertainment & culture
    "concierto", "actuación", "exposición", "obra", "personaje",
    "trama", "escena", "entrada", "espectáculo", "festival", "galería",
    "artículo", "capítulo", "novela", "poema",
    # sport & hobbies
    "equipo", "campeonato", "partido", "torneo", "puntuación", "gol",
    "entrenamiento", "entrenador", "aficionado", "atleta", "carrera",
    "natación", "ciclismo", "senderismo", "jardinería", "fotografía",
    "pintura", "música", "baile",
    # communication & technology
    "mensaje", "correo electrónico", "llamada", "contacto", "dirección",
    "aplicación", "red social", "contraseña", "pantalla", "teclado",
    "impresora", "archivo", "descargar", "subir", "actualizar",
    # extended nature
    "bosque", "río", "lago", "desierto", "océano", "costa", "horizonte",
    "valle", "campo", "pradera", "selva", "cascada", "volcán",
    # extended adjectives
    "cómodo", "incómodo", "amargo", "dulce", "ácido", "picante",
    "suave", "redondo", "cuadrado", "plano", "profundo",
    "curioso", "serio", "nervioso",
    "orgulloso", "avergonzado", "sorprendido", "preocupado", "celoso",
    "emocionante", "relajante", "útil", "inútil", "disponible",
    # extended verbs
    "sugerir", "aceptar", "rechazar", "quejarse",
    "recomendar", "describir", "imaginar", "planificar",
    "organizar", "comparar", "explicar", "convencer", "invitar",
    "celebrar", "felicitar", "disculparse", "agradecer", "disfrutar",
    "mejorar", "empeorar", "continuar", "pertenecer", "consistir",
    # extended adverbs & expressions
    "definitivamente", "probablemente", "quizás", "especialmente",
    "principalmente", "generalmente", "normalmente", "a veces",
    "raramente", "casi", "demasiado", "suficiente",
    "ya", "todavía", "aún", "enseguida", "de repente",
})

# ── French A2 (fr) ────────────────────────────────────────────────────────────
_FR_A2: frozenset[str] = frozenset({
    # extended family & relationships
    "grand-père", "grand-mère", "petit-fils", "petite-fille", "oncle",
    "tante", "cousin", "cousine", "neveu", "nièce", "beau-père",
    "belle-mère", "gendre", "belle-fille", "beau-frère", "belle-sœur",
    "partenaire", "fiancé", "fiancée", "collègue", "voisin", "voisine",
    "camarade",
    # extended workplace & school
    "bureau", "réunion", "chef", "employé", "entreprise", "affaire",
    "projet", "rapport", "délai", "salaire", "contrat", "promotion",
    "matière", "examen", "note", "carrière", "diplôme",
    "conférence", "tableau", "cahier",
    # extended travel & transport
    "passeport", "billet", "réservation", "valise", "bagage", "douane",
    "enregistrement", "carte d'embarquement", "arrivée", "départ",
    "quai", "autoroute", "embouteillage", "parking", "arrêt",
    "ferry", "croisière", "excursion", "tourisme", "hébergement",
    # extended home & furniture
    "salon", "salle à manger", "couloir", "garage", "sous-sol",
    "grenier", "étagère", "tiroir", "lampe", "tapis", "rideau",
    "miroir", "réfrigérateur", "micro-onde", "lave-linge", "robinet",
    "prise", "escalier", "balcon",
    # weather
    "pluie", "neige", "vent", "orage", "éclair", "tonnerre", "brouillard",
    "nuageux", "dégagé", "température", "humide", "gel", "degré",
    "météo", "prévision",
    # health & body
    "mal de tête", "fièvre", "rhume", "grippe", "pharmacie", "ordonnance",
    "médicament", "comprimé", "opération", "urgence", "ambulance",
    "blessure", "allergie", "rendez-vous",
    # shopping & money
    "reçu", "réduction", "solde", "taille", "cabine d'essayage", "marque",
    "portefeuille", "carte", "compte", "facture", "monnaie", "espèce",
    "sac", "étiquette", "remboursement",
    # food & cooking
    "recette", "ingrédient", "saveur", "menu", "plat", "dessert",
    "entrée", "pourboire", "mélanger", "bouillir", "cuire", "frire",
    "couper", "préparer", "goûter",
    # entertainment & culture
    "concert", "spectacle", "exposition", "pièce", "personnage",
    "intrigue", "scène", "entrée", "festival", "galerie",
    "article", "chapitre", "roman", "poème",
    # sport & hobbies
    "équipe", "championnat", "match", "tournoi", "score", "but",
    "entraînement", "entraîneur", "fan", "athlète", "course",
    "natation", "cyclisme", "randonnée", "jardinage", "photographie",
    "peinture", "musique", "danse",
    # communication & technology
    "message", "appel", "contact", "adresse", "application",
    "réseau social", "mot de passe", "écran", "clavier",
    "imprimante", "fichier", "télécharger", "mettre à jour",
    # extended nature
    "forêt", "rivière", "lac", "désert", "océan", "côte", "horizon",
    "vallée", "champ", "prairie", "jungle", "cascade", "volcan",
    # extended adjectives
    "confortable", "amer", "sucré", "acide", "épicé", "doux",
    "rond", "carré", "plat", "profond", "curieux", "sérieux",
    "ennuyé", "nerveux", "fier", "gêné", "surpris", "inquiet",
    "jaloux", "passionnant", "relaxant", "utile", "inutile",
    # extended verbs
    "suggérer", "accepter", "refuser", "se plaindre",
    "recommander", "décrire", "imaginer", "espérer", "planifier",
    "organiser", "comparer", "convaincre", "inviter", "célébrer",
    "féliciter", "s'excuser", "remercier", "profiter", "améliorer",
    "continuer", "appartenir", "consister",
    # extended adverbs
    "définitivement", "probablement", "peut-être", "surtout",
    "principalement", "généralement", "normalement", "parfois",
    "rarement", "presque", "assez", "trop", "suffisamment",
    "déjà", "encore", "tout de suite", "soudain",
})

# ── German A2 (de) ────────────────────────────────────────────────────────────
# Nouns Title-cased; other POS lowercase.
_DE_A2: frozenset[str] = frozenset({
    # extended family & relationships
    "Großvater", "Oma", "Opa", "Großmutter", "Enkel", "Enkelin",
    "Onkel", "Tante", "Cousin", "Cousine", "Neffe", "Nichte",
    "Schwiegervater", "Schwiegermutter", "Schwiegersohn", "Schwiegertochter",
    "Schwager", "Schwägerin", "Partner", "Partnerin", "Verlobte",
    "Kollege", "Kollegin", "Nachbar", "Nachbarin", "Mitschüler",
    # extended workplace & school
    "Büro", "Besprechung", "Sitzung", "Chef", "Chefin", "Mitarbeiter",
    "Firma", "Unternehmen", "Geschäft", "Projekt", "Bericht", "Frist",
    "Gehalt", "Vertrag", "Beförderung", "Fach", "Prüfung", "Note",
    "Hausaufgabe", "Laufbahn", "Abschluss", "Vortrag", "Tafel", "Heft",
    # extended travel & transport
    "Reisepass", "Ticket", "Reservierung", "Koffer", "Gepäck", "Zoll",
    "Check-in", "Bordkarte", "Ankunft", "Abfahrt", "Bahnsteig",
    "Autobahn", "Stau", "Parkplatz", "Haltestelle", "Fähre", "Kreuzfahrt",
    "Ausflug", "Touristik", "Unterkunft",
    # extended home & furniture
    "Wohnzimmer", "Esszimmer", "Flur", "Keller", "Dachboden",
    "Balkon", "Regal", "Schublade", "Lampe", "Teppich", "Vorhang",
    "Spiegel", "Kühlschrank", "Mikrowelle", "Waschmaschine", "Trockner",
    "Hahn", "Steckdose", "Treppe",
    # weather
    "Regen", "Schnee", "Wind", "Gewitter", "Blitz", "Donner", "Nebel",
    "bewölkt", "heiter", "Temperatur", "feucht", "Frost", "Grad",
    "Wetterbericht", "Vorhersage",
    # health & body
    "Kopfschmerzen", "Fieber", "Erkältung", "Grippe", "Apotheke",
    "Rezept", "Medikament", "Tablette", "Operation", "Notfall",
    "Krankenwagen", "Wunde", "Allergie", "Termin",
    # shopping & money
    "Quittung", "Rabatt", "Angebot", "Größe", "Umkleidekabine", "Marke",
    "Geldbeutel", "Karte", "Konto", "Rechnung", "Wechselgeld", "Bargeld",
    "Tüte", "Etikett", "Rückgabe",
    # food & cooking
    "Rezept", "Zutat", "Geschmack", "Speisekarte", "Gericht", "Nachtisch",
    "Vorspeise", "Trinkgeld", "mischen", "kochen", "backen", "braten",
    "schneiden", "zubereiten", "schmecken",
    # entertainment & culture
    "Konzert", "Aufführung", "Ausstellung", "Stück", "Figur", "Handlung",
    "Szene", "Eintrittskarte", "Festival", "Galerie",
    "Artikel", "Kapitel", "Roman", "Gedicht",
    # sport & hobbies
    "Mannschaft", "Meisterschaft", "Spiel", "Turnier", "Ergebnis", "Tor",
    "Training", "Trainer", "Fan", "Athlet", "Rennen",
    "Schwimmen", "Radfahren", "Wandern", "Gärtnern", "Fotografieren",
    "Malen", "Kochen", "Musik", "Tanzen",
    # communication & technology
    "Nachricht", "Anruf", "Kontakt", "Adresse", "App", "soziales Netzwerk",
    "Passwort", "Bildschirm", "Tastatur", "Drucker", "Datei",
    "herunterladen", "aktualisieren",
    # extended nature
    "Wald", "Fluss", "See", "Wüste", "Ozean", "Küste", "Horizont",
    "Tal", "Feld", "Wiese", "Dschungel", "Wasserfall", "Vulkan",
    # extended adjectives (lowercase)
    "gemütlich", "bitter", "süß", "sauer", "scharf", "weich",
    "rund", "quadratisch", "flach", "tief", "neugierig", "ernst",
    "gelangweilt", "nervös", "stolz", "verlegen", "überrascht",
    "besorgt", "eifersüchtig", "aufregend", "entspannend", "nützlich",
    "nutzlos", "verfügbar",
    # extended verbs (lowercase)
    "vorschlagen", "akzeptieren", "ablehnen", "sich beschweren",
    "empfehlen", "beschreiben", "hoffen", "planen",
    "organisieren", "vergleichen", "überzeugen", "einladen",
    "feiern", "gratulieren", "sich entschuldigen", "danken", "genießen",
    "verbessern", "fortsetzen", "gehören", "bestehen",
    # extended adverbs
    "definitiv", "wahrscheinlich", "vielleicht", "besonders", "hauptsächlich",
    "normalerweise", "manchmal", "selten", "fast", "ziemlich",
    "genug", "bereits", "noch", "plötzlich",
})

# ── Italian A2 (it) ───────────────────────────────────────────────────────────
_IT_A2: frozenset[str] = frozenset({
    # extended family & relationships
    "nonno", "nonna", "nipote", "zio", "zia", "cugino", "cugina",
    "suocero", "suocera", "genero", "nuora", "cognato", "cognata",
    "fidanzato", "fidanzata", "collega", "vicina",
    "compagno", "conoscente",
    # extended workplace & school
    "ufficio", "riunione", "capo", "dipendente", "azienda", "affare",
    "progetto", "rapporto", "scadenza", "stipendio", "contratto",
    "materia", "esame", "voto", "compito", "carriera", "titolo",
    "conferenza", "lavagna", "quaderno",
    # extended travel & transport
    "passaporto", "biglietto", "prenotazione", "valigia", "bagaglio",
    "dogana", "check-in", "carta d'imbarco", "arrivo", "partenza",
    "binario", "autostrada", "ingorgo", "parcheggio", "fermata",
    "traghetto", "crociera", "gita", "turismo", "alloggio",
    # extended home & furniture
    "soggiorno", "sala da pranzo", "corridoio", "garage", "cantina",
    "soffitta", "balcone", "scaffale", "cassetto", "lampada",
    "tappeto", "tenda", "specchio", "frigorifero", "microonde",
    "lavatrice", "rubinetto", "presa", "scala",
    # weather
    "pioggia", "neve", "vento", "temporale", "fulmine", "tuono",
    "nebbia", "nuvoloso", "sereno", "temperatura", "umido",
    "gelo", "grado", "previsione",
    # health & body
    "mal di testa", "febbre", "raffreddore", "influenza", "farmacia",
    "ricetta", "medicina", "compressa", "operazione", "emergenza",
    "ambulanza", "ferita", "allergia", "appuntamento",
    # shopping & money
    "scontrino", "sconto", "offerta", "taglia", "camerino", "marca",
    "portafoglio", "carta", "conto", "fattura", "resto", "contanti",
    "borsa", "etichetta", "reso",
    # food & cooking
    "ricetta", "ingrediente", "sapore", "menù", "piatto", "dessert",
    "antipasto", "mancia", "mescolare", "bollire", "infornare",
    "friggere", "tagliare", "preparare", "assaggiare",
    # entertainment & culture
    "concerto", "spettacolo", "mostra", "opera", "personaggio",
    "trama", "scena", "biglietto", "festival", "galleria",
    "articolo", "capitolo", "romanzo", "poesia",
    # sport & hobbies
    "squadra", "campionato", "partita", "torneo", "punteggio", "gol",
    "allenamento", "allenatore", "tifoso", "atleta",
    "nuoto", "ciclismo", "escursionismo", "giardinaggio", "fotografia",
    "pittura", "musica", "ballo",
    # communication & technology
    "messaggio", "chiamata", "contatto", "indirizzo", "app",
    "social network", "password", "schermo", "tastiera",
    "stampante", "file", "scaricare", "aggiornare",
    # extended nature
    "bosco", "fiume", "lago", "deserto", "oceano", "costa", "orizzonte",
    "valle", "campo", "prato", "giungla", "cascata", "vulcano",
    # extended adjectives
    "comodo", "amaro", "dolce", "aspro", "piccante", "morbido",
    "tondo", "quadrato", "piatto", "profondo", "curioso", "serio",
    "annoiato", "nervoso", "orgoglioso", "imbarazzato", "sorpreso",
    "preoccupato", "geloso", "emozionante", "rilassante", "utile",
    "inutile", "disponibile",
    # extended verbs
    "suggerire", "accettare", "rifiutare", "lamentarsi",
    "consigliare", "descrivere", "immaginare", "sperare", "pianificare",
    "organizzare", "confrontare", "convincere", "invitare",
    "festeggiare", "congratularsi", "scusarsi", "ringraziare", "godere",
    "migliorare", "continuare", "appartenere",
    # extended adverbs
    "sicuramente", "probabilmente", "forse", "specialmente",
    "principalmente", "generalmente", "di solito", "a volte",
    "raramente", "quasi", "abbastanza", "troppo", "già",
    "ancora", "improvvisamente",
})

# ── Portuguese A2 (pt) ────────────────────────────────────────────────────────
_PT_A2: frozenset[str] = frozenset({
    # extended family & relationships
    "avô", "avó", "neto", "neta", "tio", "tia", "primo", "prima",
    "sobrinho", "sobrinha", "sogro", "sogra", "genro", "nora",
    "cunhado", "cunhada", "namorado", "namorada", "colega", "vizinho",
    "vizinha", "companheiro", "conhecido",
    # extended workplace & school
    "escritório", "reunião", "chefe", "funcionário", "empresa", "negócio",
    "projeto", "relatório", "prazo", "salário", "contrato", "promoção",
    "disciplina", "exame", "nota", "tarefa", "carreira", "título",
    "conferência", "quadro", "caderno",
    # extended travel & transport
    "passaporte", "bilhete", "reserva", "mala", "bagagem", "alfândega",
    "check-in", "cartão de embarque", "chegada", "partida", "plataforma",
    "autoestrada", "engarrafamento", "estacionamento", "paragem",
    "ferryboat", "cruzeiro", "excursão", "turismo", "alojamento",
    # extended home & furniture
    "sala de estar", "sala de jantar", "corredor", "garagem", "cave",
    "sótão", "varanda", "prateleira", "gaveta", "candeeiro",
    "tapete", "cortina", "espelho", "frigorífico", "micro-ondas",
    "máquina de lavar", "torneira", "tomada", "escadas",
    # weather
    "chuva", "neve", "vento", "tempestade", "relâmpago", "trovão",
    "nevoeiro", "nublado", "temperatura", "húmido",
    "geada", "grau", "previsão",
    # health & body
    "dor de cabeça", "febre", "constipação", "gripe", "farmácia",
    "receita", "medicamento", "comprimido", "operação", "emergência",
    "ambulância", "ferida", "alergia", "consulta",
    # shopping & money
    "recibo", "desconto", "oferta", "tamanho", "cabine de prova", "marca",
    "carteira", "cartão", "conta", "fatura", "troco",
    "saco", "etiqueta", "devolução",
    # food & cooking
    "receita", "ingrediente", "sabor", "menu", "prato", "sobremesa",
    "entrada", "gorjeta", "misturar", "ferver", "assar",
    "fritar", "cortar", "preparar", "provar",
    # entertainment & culture
    "concerto", "espetáculo", "exposição", "peça", "personagem",
    "enredo", "cena", "bilhete", "festival", "galeria",
    "artigo", "capítulo", "romance", "poema",
    # sport & hobbies
    "equipa", "campeonato", "jogo", "torneio", "pontuação", "golo",
    "treino", "treinador", "adepto", "atleta",
    "natação", "ciclismo", "caminhada", "jardinagem", "fotografia",
    "pintura", "culinária", "música", "dança",
    # communication & technology
    "mensagem", "chamada", "contacto", "endereço", "aplicação",
    "rede social", "palavra-passe", "ecrã", "teclado",
    "impressora", "ficheiro", "descarregar", "atualizar",
    # extended nature
    "floresta", "rio", "lago", "deserto", "oceano", "costa", "horizonte",
    "vale", "campo", "prado", "selva", "cascata", "vulcão",
    # extended adjectives
    "confortável", "amargo", "doce", "ácido", "picante", "suave",
    "redondo", "quadrado", "plano", "profundo", "curioso", "sério",
    "nervoso", "orgulhoso", "envergonhado", "surpreendido",
    "preocupado", "ciumento", "emocionante", "relaxante", "útil",
    "inútil", "disponível",
    # extended verbs
    "sugerir", "aceitar", "recusar", "queixar-se",
    "recomendar", "descrever", "imaginar", "planear",
    "organizar", "comparar", "convencer", "convidar",
    "celebrar", "felicitar", "desculpar", "agradecer", "desfrutar",
    "melhorar", "continuar", "pertencer",
    # extended adverbs
    "definitivamente", "provavelmente", "talvez", "especialmente",
    "principalmente", "geralmente", "normalmente", "às vezes",
    "raramente", "quase", "bastante", "demasiado", "já",
    "ainda", "de repente",
})

# ── Russian A2 (ru) ───────────────────────────────────────────────────────────
_RU_A2: frozenset[str] = frozenset({
    # extended family & relationships
    "дедушка", "бабушка", "внук", "внучка", "дядя", "тётя",
    "двоюродный брат", "двоюродная сестра", "племянник", "племянница",
    "свёкор", "свекровь", "тесть", "тёща", "зять", "невестка",
    "деверь", "невестка", "жених", "невеста", "коллега", "сосед",
    "соседка", "одноклассник",
    # extended workplace & school
    "офис", "совещание", "начальник", "сотрудник", "компания",
    "бизнес", "проект", "отчёт", "срок", "зарплата", "контракт",
    "повышение", "предмет", "экзамен", "оценка", "домашнее задание",
    "карьера", "диплом", "лекция", "доска", "тетрадь",
    # extended travel & transport
    "паспорт", "билет", "бронирование", "чемодан", "багаж", "таможня",
    "регистрация", "посадочный талон", "прилёт", "отправление",
    "перрон", "шоссе", "пробка", "парковка", "остановка",
    "паром", "круиз", "экскурсия", "туризм", "жильё",
    # extended home & furniture
    "гостиная", "столовая", "коридор", "гараж", "подвал",
    "чердак", "балкон", "полка", "ящик", "лампа",
    "ковёр", "штора", "зеркало", "холодильник", "микроволновка",
    "стиральная машина", "кран", "розетка", "лестница",
    # weather
    "дождь", "снегопад", "ветер", "буря", "молния", "гром",
    "туман", "облачный", "ясный", "температура", "влажный",
    "мороз", "градус", "прогноз погоды",
    # health & body
    "головная боль", "жар", "насморк", "грипп", "аптека",
    "рецепт", "лекарство", "таблетка", "операция", "скорая помощь",
    "рана", "аллергия", "запись к врачу",
    # shopping & money
    "чек", "скидка", "акция", "размер", "примерочная", "бренд",
    "кошелёк", "карточка", "счёт", "квитанция", "сдача", "наличные",
    "пакет", "этикетка", "возврат",
    # food & cooking
    "рецепт", "ингредиент", "вкус", "меню", "блюдо", "десерт",
    "закуска", "чаевые", "перемешивать", "кипятить", "печь",
    "жарить", "резать", "готовить", "пробовать",
    # entertainment & culture
    "концерт", "спектакль", "выставка", "пьеса", "персонаж",
    "сюжет", "сцена", "билет", "фестиваль", "галерея",
    "статья", "глава", "роман", "стихотворение",
    # sport & hobbies
    "команда", "чемпионат", "матч", "турнир", "счёт", "гол",
    "тренировка", "тренер", "болельщик", "спортсмен",
    "плавание", "велоспорт", "пеший туризм", "садоводство",
    "фотография", "рисование", "кулинария", "музыка", "танцы",
    # communication & technology
    "сообщение", "звонок", "контакт", "адрес", "приложение",
    "социальная сеть", "пароль", "экран", "клавиатура",
    "принтер", "файл", "скачать", "обновить",
    # extended nature
    "лес", "река", "озеро", "пустыня", "океан", "побережье",
    "горизонт", "долина", "поле", "луг", "джунгли", "водопад",
    "вулкан",
    # extended adjectives
    "удобный", "горький", "сладкий", "кислый", "острый", "мягкий",
    "круглый", "квадратный", "плоский", "глубокий", "любопытный",
    "серьёзный", "скучающий", "нервный", "гордый", "смущённый",
    "удивлённый", "обеспокоенный", "ревнивый", "захватывающий",
    "расслабляющий", "полезный", "бесполезный", "доступный",
    # extended verbs
    "предлагать", "принимать", "отказываться", "жаловаться",
    "советовать", "описывать", "воображать", "надеяться", "планировать",
    "организовывать", "сравнивать", "убеждать", "приглашать",
    "праздновать", "поздравлять", "извиняться", "благодарить",
    "наслаждаться", "улучшать", "продолжать", "принадлежать",
    # extended adverbs
    "определённо", "вероятно", "может быть", "особенно",
    "главным образом", "обычно", "иногда", "редко",
    "почти", "довольно", "слишком", "уже", "всё ещё", "вдруг",
})

# ── Japanese A2 (ja) ──────────────────────────────────────────────────────────
_JA_A2: frozenset[str] = frozenset({
    # extended family & relationships
    "祖父", "祖母", "孫", "叔父", "叔母", "おじ", "おば", "いとこ",
    "甥", "姪", "義父", "義母", "義兄", "義弟", "婚約者",
    "同僚", "隣人", "クラスメート",
    # extended workplace & school
    "オフィス", "会議", "上司", "社員", "会社", "プロジェクト",
    "報告書", "締め切り", "給料", "契約", "昇進", "科目",
    "試験", "成績", "宿題", "キャリア", "卒業証書", "講義",
    "黒板", "ノート",
    # extended travel & transport
    "パスポート", "予約", "スーツケース", "荷物", "税関",
    "チェックイン", "搭乗券", "到着", "出発", "ホーム",
    "高速道路", "渋滞", "駐車場", "停留所", "フェリー",
    "クルーズ", "観光", "宿泊",
    # extended home & furniture
    "居間", "食堂", "廊下", "車庫", "地下室", "屋根裏",
    "バルコニー", "棚", "引き出し", "ランプ", "カーペット",
    "カーテン", "鏡", "冷蔵庫", "電子レンジ", "洗濯機",
    "蛇口", "コンセント", "階段",
    # weather
    "雨", "雪", "風", "嵐", "雷", "稲妻", "霧",
    "曇り", "晴れ", "気温", "湿度", "霜", "度", "天気予報",
    # health & body
    "頭痛", "熱", "風邪", "インフルエンザ", "薬局", "処方箋",
    "薬", "錠剤", "手術", "救急", "救急車", "傷", "アレルギー",
    "予約",
    # shopping & money
    "レシート", "割引", "セール", "サイズ", "試着室", "ブランド",
    "財布", "カード", "口座", "請求書", "おつり", "現金",
    "袋", "値札", "返品",
    # food & cooking
    "レシピ", "材料", "味", "メニュー", "料理", "デザート",
    "前菜", "チップ", "混ぜる", "沸かす", "焼く",
    "揚げる", "切る", "準備する", "味見する",
    # entertainment & culture
    "コンサート", "公演", "展覧会", "演劇", "登場人物",
    "プロット", "場面", "チケット", "フェスティバル", "ギャラリー",
    "記事", "章", "小説", "詩",
    # sport & hobbies
    "チーム", "選手権", "試合", "トーナメント", "スコア", "ゴール",
    "練習", "コーチ", "ファン",
    "水泳", "サイクリング", "ハイキング", "ガーデニング", "写真撮影",
    "絵画", "料理", "音楽", "ダンス",
    # communication & technology
    "メッセージ", "通話", "連絡先", "住所", "アプリ",
    "ソーシャルメディア", "パスワード", "画面", "キーボード",
    "プリンター", "ファイル", "ダウンロード", "アップデート",
    # extended nature
    "森", "川", "湖", "砂漠", "大洋", "海岸", "地平線",
    "谷", "野原", "草原", "ジャングル", "滝", "火山",
    # extended adjectives
    "快適", "苦い", "甘い", "酸っぱい", "辛い", "柔らかい",
    "丸い", "四角い", "平ら", "深い", "好奇心旺盛", "真剣",
    "退屈した", "緊張した", "誇りに思う", "恥ずかしい", "驚いた",
    "心配した", "嫉妬した", "わくわくする", "リラックスできる",
    "役に立つ", "役に立たない",
    # extended verbs
    "提案する", "受け入れる", "断る", "文句を言う",
    "勧める", "描写する", "想像する", "希望する", "計画する",
    "整理する", "比べる", "納得させる", "招待する",
    "祝う", "おめでとうと言う", "謝る", "感謝する", "楽しむ",
    "改善する", "続ける", "属する",
    # extended adverbs
    "確かに", "たぶん", "おそらく", "特に", "主に",
    "普通は", "時々", "めったに", "ほとんど", "かなり",
    "すでに", "突然",
})

# ── Chinese A2 (zh) ───────────────────────────────────────────────────────────
_ZH_A2: frozenset[str] = frozenset({
    # extended family & relationships
    "祖父", "爷爷", "祖母", "奶奶", "孙子", "孙女", "叔叔", "阿姨",
    "表兄", "表姐", "表弟", "表妹", "侄子", "侄女",
    "公公", "婆婆", "女婿", "儿媳", "姐夫", "妹夫",
    "男朋友", "女朋友", "同事", "邻居", "同学",
    # extended workplace & school
    "办公室", "会议", "老板", "员工", "生意",
    "项目", "报告", "截止日期", "工资", "合同", "晋升",
    "科目", "考试", "成绩", "职业", "文凭",
    "讲座", "黑板", "笔记本",
    # extended travel & transport
    "护照", "预订", "行李箱", "行李", "海关",
    "值机", "登机牌", "抵达", "出发", "站台",
    "高速公路", "堵车", "停车场", "车站", "渡轮",
    "游轮", "旅游", "住宿",
    # extended home & furniture
    "客厅", "饭厅", "走廊", "车库", "地下室", "阁楼",
    "阳台", "书架", "抽屉", "台灯", "地毯", "窗帘",
    "镜子", "冰箱", "微波炉", "洗衣机", "水龙头",
    "插座", "楼梯",
    # weather
    "下雨", "下雪", "刮风", "暴风雨", "闪电", "雷声",
    "大雾", "多云", "晴朗", "气温", "潮湿", "结冰",
    "摄氏度", "天气预报",
    # health & body
    "头疼", "发烧", "感冒", "流感", "药店", "处方",
    "药物", "药片", "手术", "急救", "救护车", "伤口",
    "过敏", "预约",
    # shopping & money
    "收据", "折扣", "特价", "尺码", "试衣间", "品牌",
    "钱包", "信用卡", "账户", "账单", "找零", "现金",
    "购物袋", "标签", "退货",
    # food & cooking
    "食谱", "材料", "味道", "菜单", "菜肴", "甜点",
    "开胃菜", "小费", "搅拌", "煮沸", "烘烤",
    "油炸", "切", "准备", "品尝",
    # entertainment & culture
    "音乐会", "表演", "展览", "戏剧", "角色",
    "情节", "场景", "门票", "节日", "画廊",
    "文章", "章节", "小说", "诗",
    # sport & hobbies
    "队", "锦标赛", "比赛", "联赛", "比分", "进球",
    "训练", "教练", "球迷",
    "骑行", "徒步", "园艺", "摄影",
    "绘画", "烹饪", "音乐", "舞蹈",
    # communication & technology
    "短信", "通话", "联系方式", "地址", "应用程序",
    "社交媒体", "密码", "屏幕", "键盘",
    "打印机", "文件", "下载", "更新",
    # extended nature
    "森林", "河流", "湖泊", "沙漠", "大海", "海岸线",
    "地平线", "山谷", "农田", "草地", "丛林", "瀑布",
    "火山",
    # extended adjectives
    "舒适", "苦", "甜", "酸", "辣", "软",
    "圆的", "方的", "平的", "深的", "好奇", "严肃",
    "紧张", "骄傲", "害羞", "惊讶",
    "担心", "嫉妒", "令人兴奋", "令人放松", "有用",
    "没用",
    # extended verbs
    "建议", "接受", "拒绝", "抱怨",
    "推荐", "描述", "想象", "希望", "计划",
    "组织", "比较", "说服", "邀请",
    "庆祝", "祝贺", "道歉", "感谢", "享受",
    "改善", "继续", "属于",
    # extended adverbs
    "肯定", "也许", "特别是", "主要",
    "通常", "有时", "很少", "几乎", "相当",
    "已经", "仍然", "突然",
})

# ── Arabic A2 (ar) ────────────────────────────────────────────────────────────
# Unvocalised forms matching arabic.py's _strip_tashkeel() output.
_AR_A2: frozenset[str] = frozenset({
    # extended family & relationships
    "جد", "جدة", "حفيد", "حفيدة", "عم", "عمة", "خال", "خالة",
    "ابن العم", "ابنة العم", "ابن الخال", "ابنة الخال",
    "ابن الأخ", "ابنة الأخ", "حماة", "حمو", "صهر", "كنة",
    "خطيب", "خطيبة", "زميل", "جار", "جارة", "زميل دراسة",
    # extended workplace & school
    "مكتب", "اجتماع", "رئيس", "موظف", "شركة", "أعمال",
    "مشروع", "تقرير", "موعد نهائي", "راتب", "عقد", "ترقية",
    "مادة", "امتحان", "علامة", "واجب", "مهنة", "شهادة",
    "محاضرة", "لوحة", "دفتر",
    # extended travel & transport
    "جواز سفر", "تذكرة", "حجز", "حقيبة سفر", "أمتعة", "جمارك",
    "تسجيل وصول", "بطاقة صعود", "وصول", "مغادرة", "رصيف",
    "طريق سريع", "ازدحام", "موقف سيارات", "محطة", "عبارة",
    "رحلة بحرية", "جولة سياحية", "سياحة", "إقامة",
    # extended home & furniture
    "غرفة المعيشة", "غرفة الطعام", "ممر", "مرآب", "قبو",
    "شرفة", "رف", "درج", "مصباح", "سجادة",
    "ستارة", "مرآة", "ثلاجة", "ميكروويف", "غسالة",
    "صنبور", "مقبس", "سلم",
    # weather
    "مطر", "ثلج", "ريح", "عاصفة", "برق", "رعد", "ضباب",
    "غائم", "مشمس", "درجة الحرارة", "رطب", "صقيع",
    "درجة", "توقعات الطقس",
    # health & body
    "صداع", "حمى", "نزلة برد", "إنفلونزا", "صيدلية", "وصفة طبية",
    "دواء", "حبة", "عملية", "طوارئ", "سيارة إسعاف", "جرح",
    "حساسية", "موعد",
    # shopping & money
    "إيصال", "خصم", "عرض", "مقاس", "غرفة تجريب", "علامة تجارية",
    "محفظة", "بطاقة", "حساب", "فاتورة", "فكة", "نقود",
    "حقيبة", "ملصق", "إرجاع",
    # food & cooking
    "وصفة", "مكون", "نكهة", "قائمة طعام", "طبق", "حلوى",
    "مقبلات", "بقشيش", "خلط", "غلي", "طهي",
    "قلي", "قطع", "تحضير", "تذوق",
    # entertainment & culture
    "حفلة موسيقية", "عرض", "معرض", "مسرحية", "شخصية",
    "حبكة", "مشهد", "تذكرة", "مهرجان", "معرض فني",
    "مقالة", "رواية", "قصيدة",
    # sport & hobbies
    "فريق", "بطولة", "مباراة", "دوري", "نتيجة", "هدف",
    "تدريب", "مدرب", "مشجع", "رياضي",
    "سباحة", "ركوب الدراجات", "مشي لمسافات طويلة", "بستنة",
    "تصوير فوتوغرافي", "طبخ", "موسيقى", "رقص",
    # communication & technology
    "رسالة", "مكالمة", "جهة اتصال", "عنوان", "تطبيق",
    "وسائل التواصل الاجتماعي", "كلمة مرور", "شاشة", "لوحة مفاتيح",
    "طابعة", "ملف", "تنزيل", "تحديث",
    # extended nature
    "غابة", "نهر", "بحيرة", "صحراء", "محيط", "ساحل",
    "أفق", "وادي", "حقل", "مرج", "غابة استوائية", "شلال",
    "بركان",
    # extended adjectives
    "مريح", "مرّ", "حلو", "حامض", "لاذع", "ناعم",
    "دائري", "مربع", "مسطح", "عميق", "فضولي", "جاد",
    "ملول", "متوتر", "فخور", "محرج", "مندهش",
    "قلق", "غيور", "مثير", "مريح", "مفيد",
    "غير مفيد", "متاح",
    # extended verbs
    "اقترح", "تقبّل", "رفض", "اشتكى",
    "أوصى", "وصف", "تخيل", "أمل", "خطط",
    "نظّم", "قارن", "أقنع", "دعا", "احتفل",
    "هنأ", "اعتذر", "شكر", "استمتع", "حسّن",
    "استمر", "انتمى",
    # extended adverbs
    "بالتأكيد", "على الأرجح", "ربما", "خاصة",
    "أساسا", "عادة", "أحيانا", "نادرا",
    "تقريبا", "إلى حد ما", "فعلا", "لا يزال", "فجأة",
})

# ── Hebrew A2 (he) ────────────────────────────────────────────────────────────
# Unvocalised forms matching hebrew.py's _strip_nikud() output.
_HE_A2: frozenset[str] = frozenset({
    # extended family & relationships
    "סבא", "סבתא", "נכד", "נכדה", "דוד", "דודה", "בן דוד", "בת דוד",
    "אחיין", "אחיינית", "חותן", "חותנת", "חתן", "כלה",
    "גיס", "גיסה", "עמית", "שכן", "שכנה",
    "חבר לכיתה",
    # extended workplace & school
    "משרד", "פגישה", "מנהל", "עובד", "עסק",
    "פרויקט", "דוח", "מועד אחרון", "משכורת", "חוזה", "קידום",
    "מקצוע", "בחינה", "ציון", "שיעורי בית", "קריירה", "תעודה",
    "הרצאה", "לוח", "מחברת",
    # extended travel & transport
    "דרכון", "כרטיס", "הזמנה", "מזוודה", "מטען", "מכס",
    "צ'ק-אין", "כרטיס עלייה", "הגעה", "יציאה", "רציף",
    "כביש מהיר", "פקק", "חניה", "תחנה", "מעבורת",
    "שייט", "טיול", "תיירות", "אכסניה",
    # extended home & furniture
    "סלון", "חדר אוכל", "מסדרון", "מוסך", "מרתף",
    "עליית גג", "מרפסת", "מדף", "מגירה", "מנורה",
    "שטיח", "וילון", "מראה", "מקרר", "מיקרוגל",
    "מכונת כביסה", "ברז", "שקע", "מדרגות",
    # weather
    "גשם", "שלג", "רוח", "סופה", "ברק", "רעם", "ערפל",
    "מעונן", "בהיר", "טמפרטורה", "לח", "כפור",
    "מעלה", "תחזית מזג אוויר",
    # health & body
    "כאב ראש", "נזלת", "שפעת", "בית מרקחת", "מרשם",
    "תרופה", "כדור", "ניתוח", "חירום", "אמבולנס", "פצע",
    "אלרגיה", "תור",
    # shopping & money
    "קבלה", "הנחה", "מבצע", "מידה", "חדר הלבשה", "מותג",
    "ארנק", "כרטיס", "חשבון", "חשבונית", "עודף", "מזומן",
    "שקית", "תווית", "החזרה",
    # food & cooking
    "מתכון", "מרכיב", "טעם", "תפריט", "מנה", "קינוח",
    "מנה ראשונה", "טיפ", "לערבב", "להרתיח", "לאפות",
    "לטגן", "לחתוך", "להכין", "לטעום",
    # entertainment & culture
    "קונצרט", "מופע", "תערוכה", "מחזה", "דמות",
    "עלילה", "סצנה", "כרטיס", "פסטיבל", "גלריה",
    "מאמר", "פרק", "רומן", "שיר",
    # sport & hobbies
    "קבוצה", "אליפות", "משחק", "טורניר", "תוצאה", "שער",
    "אימון", "מאמן", "אוהד", "ספורטאי",
    "שחייה", "רכיבה על אופניים", "טיול רגלי", "גינון",
    "צילום", "ציור", "בישול", "מוזיקה", "ריקוד",
    # communication & technology
    "הודעה", "שיחה", "איש קשר", "כתובת", "אפליקציה",
    "רשת חברתית", "סיסמה", "מסך", "מקלדת",
    "מדפסת", "קובץ", "להוריד", "לעדכן",
    # extended nature
    "יער", "נהר", "אגם", "מדבר", "אוקיינוס",
    "אופק", "עמק", "ג'ונגל", "מפל", "הר געש",
    # extended adjectives
    "נוח", "מר", "מתוק", "חמוץ", "חריף", "רך",
    "עגול", "מרובע", "שטוח", "עמוק", "סקרן", "רציני",
    "משועמם", "עצבני", "גאה", "מביך", "מופתע",
    "דואג", "מקנא", "מרגש", "מרגיע", "שימושי",
    "חסר תועלת", "זמין",
    # extended verbs
    "הציע", "קיבל", "סירב", "התלונן",
    "המליץ", "תיאר", "דמיין", "קיווה", "תכנן",
    "ארגן", "השווה", "שכנע", "הזמין", "חגג",
    "איחל", "התנצל", "הודה", "נהנה", "שיפר",
    "המשיך", "השתייך",
    # extended adverbs
    "בהחלט", "כנראה", "אולי", "במיוחד",
    "בעיקר", "בדרך כלל", "לפעמים", "לעיתים נדירות",
    "כמעט", "למדי", "כבר", "עדיין", "לפתע",
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

#: Map from language code to frozenset of A2 lemmas (excludes A1 items).
A2: dict[str, frozenset[str]] = {
    "es": _ES_A2,
    "fr": _FR_A2,
    "de": _DE_A2,
    "it": _IT_A2,
    "pt": _PT_A2,
    "ru": _RU_A2,
    "ja": _JA_A2,
    "zh": _ZH_A2,
    "ar": _AR_A2,
    "he": _HE_A2,
}

# ═══════════════════════════════════════════════════════════════════════════════
# B1 — Threshold (intermediate) vocabulary
# ═══════════════════════════════════════════════════════════════════════════════
# B1 covers abstract concepts, opinions/argumentation, news/current affairs,
# environment, social issues, and extended cognitive/communicative vocabulary.
# ~380 lemmas per language.  No item may appear in A1 or A2 for the same lang.

# ── Spanish B1 (es) ───────────────────────────────────────────────────────────
_ES_B1: frozenset[str] = frozenset({
    # abstract concepts & nouns
    "opinión", "situación", "solución", "resultado", "relación",
    "oportunidad", "decisión", "razón", "detalle", "hecho",
    "diferencia", "desarrollo", "efecto", "ventaja",
    "desventaja", "propósito", "valor", "papel", "calidad",
    "proceso", "método", "nivel", "atención", "esfuerzo",
    "posibilidad", "responsabilidad", "importancia", "aspecto",
    "causa", "condición", "contexto", "dificultad", "evidencia",
    "función", "impacto", "influencia", "asunto", "conocimiento",
    "límite", "pérdida", "significado", "necesidad", "período",
    "presión", "principio", "progreso", "tasa", "sentido",
    "etapa", "estructura", "sistema", "término", "perspectiva",
    "conclusión", "teoría", "afirmación", "análisis", "crítica",
    "propuesta", "alternativa", "tendencia", "consecuencia",
    "suposición", "hipótesis", "argumento",
    # opinions & debate
    "debate", "discusión", "punto de vista", "juicio",
    "recomendación", "evaluación", "acuerdo", "desacuerdo",
    # work & professional (B1 depth)
    "presentación", "solicitud", "entrevista", "departamento",
    "habilidad", "calificación", "formación", "objetivo",
    "estrategia", "presupuesto", "beneficio", "recurso",
    "colaboración", "rendimiento", "desempeño", "logro",
    "retroalimentación", "capacitación", "liderazgo",
    # news & current affairs
    "anuncio", "elección", "conflicto",
    "acontecimiento", "crisis", "desafío", "protesta", "reforma",
    "campaña", "política", "gobierno", "sociedad", "economía",
    "estadística", "encuesta", "titular", "fuente", "cobertura",
    "declaración", "acuerdo internacional", "tratado",
    # technology & digital (B1 depth)
    "software", "dispositivo", "red", "datos", "seguridad",
    "privacidad", "plataforma", "programa", "interfaz",
    "usuario", "base de datos", "almacenamiento", "actualización",
    "aplicación móvil", "inteligencia artificial", "automatización",
    # health & medicine (extended)
    "tratamiento", "síntoma", "diagnóstico", "terapia",
    "rehabilitación", "vacuna", "antibiótico", "especialista",
    "dosis", "efecto secundario", "prevención", "cronicidad",
    "bienestar mental", "estrés", "burnout",
    # environment & sustainability
    "clima", "medio ambiente", "contaminación", "sostenible",
    "recurso natural", "especie", "hábitat", "emisión",
    "huella de carbono", "biodiversidad", "sequía", "inundación",
    "deforestación", "calentamiento global", "reciclable",
    "residuo", "impacto ambiental", "energía solar",
    "energía eólica", "panel solar", "transición energética",
    # education & learning (B1 depth)
    "investigación", "tesis", "beca",
    "taller", "seminario", "metodología", "institución",
    "academia", "matrícula", "resultado académico",
    "aprendizaje autónomo", "competencia",
    # social issues & society
    "igualdad", "diversidad", "inclusión", "discriminación",
    "prejuicio", "pobreza", "desigualdad", "justicia",
    "derechos", "obligación", "ciudadanía", "integración",
    "migración", "refugiado", "comunidad", "voluntariado",
    "solidaridad", "bienestar", "cohesión social", "tolerancia",
    "equidad", "marginación", "exclusión", "accesibilidad",
    # extended abstract adjectives
    "complejo", "sencillo", "general", "específico", "particular",
    "cierto", "evidente", "normal", "original", "reciente",
    "grave", "similar", "típico", "variado", "eficiente",
    "eficaz", "flexible", "innovador", "creativo", "crítico",
    "lógico", "abstracto", "concreto", "fundamental", "relevante",
    "significativo", "notable", "considerable", "excepcional",
    "moderado", "intenso", "permanente", "temporal", "global",
    "nacional", "internacional", "público", "privado",
    "oficial", "formal", "informal", "urgente", "inevitable",
    "razonable", "adecuado", "insuficiente", "excesivo",
    # extended verbs (cognitive & communicative)
    "considerar", "analizar", "interpretar", "debatir",
    "argumentar", "dudar", "reconocer", "percibir",
    "reflexionar", "evaluar", "justificar", "demostrar",
    "comprobar", "investigar", "resolver", "implementar",
    "adaptar", "transformar", "contribuir", "participar",
    "colaborar", "comunicar", "negociar", "gestionar",
    "coordinar", "establecer", "determinar", "identificar",
    "priorizar", "supervisar", "promover", "apoyar",
    "defender", "cuestionar", "criticar", "influir",
    "prevenir", "reducir", "aumentar",
    # extended adverbs & discourse connectors
    "sin embargo", "aunque", "por lo tanto", "por otro lado",
    "en cambio", "a pesar de", "no obstante", "en consecuencia",
    "en resumen", "anteriormente", "actualmente", "próximamente",
    "claramente", "evidentemente",
    "en términos generales", "en particular", "al contrario",
    "de hecho", "por supuesto", "en cuanto a", "con respecto a"
})
# ── French B1 (fr) ────────────────────────────────────────────────────────────
_FR_B1: frozenset[str] = frozenset({
    # abstract concepts & nouns
    "opinion", "situation", "solution", "résultat", "relation",
    "opportunité", "décision", "raison", "détail", "fait",
    "différence", "changement", "développement", "effet", "avantage",
    "inconvénient", "valeur", "rôle", "qualité",
    "processus", "méthode", "niveau", "attention", "effort",
    "possibilité", "responsabilité", "importance", "aspect",
    "cause", "condition", "contexte", "difficulté", "preuve",
    "fonction", "impact", "influence", "connaissance",
    "limite", "perte", "signification", "besoin", "période",
    "pression", "principe", "progrès", "sens",
    "étape", "structure", "système", "terme", "perspective",
    "conclusion", "théorie", "affirmation", "analyse", "critique",
    "proposition", "alternative", "tendance", "conséquence",
    "supposition", "hypothèse", "argument",
    # opinions & debate
    "débat", "discussion", "point de vue", "jugement",
    "recommandation", "évaluation", "accord", "désaccord",
    # work & professional (B1 depth)
    "présentation", "candidature", "entretien", "département",
    "compétence", "qualification", "formation", "objectif",
    "stratégie", "budget", "bénéfice", "ressource",
    "collaboration", "performance", "rendement", "réalisation",
    "retour d'information", "leadership",
    # news & current affairs
    "annonce", "élection", "conflit",
    "événement", "crise", "défi", "manifestation", "réforme",
    "campagne", "politique", "gouvernement", "société", "économie",
    "statistique", "sondage", "titre", "source", "couverture",
    "déclaration", "traité",
    # technology & digital (B1 depth)
    "logiciel", "appareil", "réseau", "données", "sécurité",
    "confidentialité", "plateforme", "interface",
    "utilisateur", "base de données", "stockage", "mise à jour",
    "application mobile", "intelligence artificielle", "automatisation",
    # health & medicine (extended)
    "traitement", "symptôme", "diagnostic", "thérapie",
    "rééducation", "vaccin", "antibiotique", "spécialiste",
    "dose", "effet secondaire", "prévention", "chronicité",
    "santé mentale", "stress", "épuisement professionnel",
    # environment & sustainability
    "climat", "environnement", "pollution", "durable",
    "ressource naturelle", "habitat", "émission",
    "empreinte carbone", "biodiversité", "sécheresse", "inondation",
    "déforestation", "réchauffement climatique", "recyclable",
    "déchet", "impact environnemental", "énergie solaire",
    "énergie éolienne", "transition énergétique",
    # education & learning (B1 depth)
    "recherche", "mémoire", "bourse",
    "atelier", "séminaire", "méthodologie", "institution",
    "académie", "inscription", "résultat scolaire",
    "apprentissage autonome", "compétence",
    # social issues & society
    "égalité", "diversité", "inclusion", "discrimination",
    "préjugé", "pauvreté", "inégalité", "justice",
    "droits", "obligation", "citoyenneté", "intégration",
    "migration", "réfugié", "communauté", "bénévolat",
    "solidarité", "bien-être", "cohésion sociale", "tolérance",
    "équité", "marginalisation", "exclusion", "accessibilité",
    # extended abstract adjectives
    "complexe", "simple", "général", "spécifique", "particulier",
    "certain", "évident", "normal", "original", "récent",
    "grave", "similaire", "typique", "varié", "efficace",
    "flexible", "innovant", "créatif", "critique", "logique",
    "abstrait", "concret", "fondamental", "pertinent",
    "significatif", "notable", "considérable", "exceptionnel",
    "modéré", "intense", "permanent", "temporaire", "mondial",
    "national", "international", "officiel", "formel", "informel",
    "urgent", "inévitable", "raisonnable", "adéquat",
    "insuffisant", "excessif",
    # extended verbs (cognitive & communicative)
    "considérer", "analyser", "interpréter", "débattre",
    "argumenter", "douter", "reconnaître", "percevoir",
    "réfléchir", "évaluer", "justifier", "démontrer",
    "vérifier", "enquêter", "résoudre", "mettre en œuvre",
    "adapter", "transformer", "contribuer", "participer",
    "collaborer", "communiquer", "négocier", "gérer",
    "coordonner", "établir", "déterminer", "identifier",
    "superviser", "promouvoir", "soutenir", "défendre",
    "remettre en question", "critiquer", "influencer",
    "prévenir", "réduire", "augmenter",
    # extended adverbs & discourse connectors
    "cependant", "bien que", "donc", "en outre",
    "d'autre part", "en revanche", "malgré", "néanmoins",
    "par conséquent", "en résumé", "auparavant", "actuellement",
    "prochainement", "clairement", "évidemment",
    "en général", "en particulier",
    "au contraire", "en fait", "bien sûr", "quant à"
})
# ── German B1 (de) ────────────────────────────────────────────────────────────
# Nouns Title-cased; verbs/adjectives/adverbs lowercase.
_DE_B1: frozenset[str] = frozenset({
    # abstract nouns (Title-cased)
    "Meinung", "Situation", "Lösung", "Beziehung",
    "Gelegenheit", "Entscheidung", "Grund", "Detail", "Tatsache",
    "Unterschied", "Änderung", "Entwicklung", "Wirkung", "Vorteil",
    "Nachteil", "Zweck", "Wert", "Rolle", "Qualität",
    "Prozess", "Methode", "Niveau", "Aufmerksamkeit", "Anstrengung",
    "Möglichkeit", "Verantwortung", "Wichtigkeit", "Aspekt",
    "Ursache", "Bedingung", "Kontext", "Schwierigkeit", "Beweis",
    "Funktion", "Auswirkung", "Einfluss", "Angelegenheit", "Wissen",
    "Grenze", "Verlust", "Bedeutung", "Bedürfnis", "Zeitraum",
    "Druck", "Grundsatz", "Fortschritt", "Sinn",
    "Stufe", "Struktur", "System", "Begriff", "Perspektive",
    "Schlussfolgerung", "Theorie", "Aussage", "Analyse", "Kritik",
    "Vorschlag", "Alternative", "Tendenz", "Konsequenz",
    "Annahme", "Hypothese", "Argument",
    # debate & opinion nouns
    "Debatte", "Diskussion", "Standpunkt", "Urteil",
    "Empfehlung", "Bewertung", "Einigkeit", "Meinungsverschiedenheit",
    # work & professional nouns (B1 depth)
    "Präsentation", "Bewerbung", "Vorstellungsgespräch", "Abteilung",
    "Fähigkeit", "Qualifikation", "Ausbildung", "Ziel",
    "Strategie", "Budget", "Nutzen", "Ressource",
    "Zusammenarbeit", "Leistung", "Führung", "Rückmeldung",
    # news & current affairs nouns
    "Ankündigung", "Wahl", "Konflikt",
    "Ereignis", "Krise", "Herausforderung", "Protest", "Reform",
    "Kampagne", "Regierung", "Gesellschaft", "Wirtschaft",
    "Statistik", "Umfrage", "Schlagzeile", "Quelle",
    "Erklärung",
    # technology nouns
    "Software", "Gerät", "Netzwerk", "Daten", "Sicherheit",
    "Datenschutz", "Plattform", "Schnittstelle",
    "Benutzer", "Datenbank", "Speicherung", "Aktualisierung",
    "Künstliche Intelligenz", "Automatisierung",
    # health nouns
    "Behandlung", "Symptom", "Diagnose", "Therapie",
    "Rehabilitation", "Impfstoff", "Antibiotikum", "Spezialist",
    "Dosis", "Nebenwirkung", "Vorbeugung", "Burnout",
    # environment nouns
    "Klima", "Umwelt", "Verschmutzung", "Ressource",
    "Art", "Lebensraum", "Emission", "Biodiversität",
    "Dürre", "Überschwemmung", "Abholzung", "Klimawandel",
    "Abfall", "Solarenergie", "Windenergie",
    # education nouns
    "Forschung", "These", "Stipendium", "Konferenz",
    "Workshop", "Seminar", "Methodik", "Institution",
    "Akademie", "Einschreibung", "Kompetenz",
    # social issues nouns
    "Gleichheit", "Vielfalt", "Inklusion", "Diskriminierung",
    "Vorurteil", "Armut", "Ungerechtigkeit", "Gerechtigkeit",
    "Pflicht", "Staatsbürgerschaft", "Integration",
    "Migration", "Flüchtling", "Gemeinschaft", "Ehrenamt",
    "Solidarität", "Wohlbefinden", "Toleranz", "Zugänglichkeit",
    # abstract adjectives (lowercase)
    "komplex", "allgemein", "spezifisch",
    "offensichtlich", "ursprünglich",
    "ähnlich", "typisch", "vielfältig", "effizient",
    "wirksam", "flexibel", "innovativ", "kreativ",
    "kritisch", "logisch", "abstrakt", "konkret",
    "grundlegend", "relevant", "bedeutsam", "bemerkenswert",
    "erheblich", "außergewöhnlich", "gemäßigt", "intensiv",
    "dauerhaft", "vorübergehend", "global", "lokal",
    "öffentlich", "privat", "offiziell", "formell", "informell",
    "dringend", "unvermeidlich", "angemessen", "unzureichend",
    # verbs (lowercase)
    "betrachten", "analysieren", "interpretieren", "debattieren",
    "argumentieren", "zweifeln", "wahrnehmen",
    "nachdenken", "bewerten", "rechtfertigen", "beweisen",
    "überprüfen", "untersuchen", "lösen", "umsetzen",
    "anpassen", "transformieren", "beitragen", "teilnehmen",
    "verhandeln", "verwalten", "koordinieren", "feststellen",
    "bestimmen", "identifizieren", "beaufsichtigen", "fördern",
    "verteidigen", "hinterfragen", "beeinflussen",
    "verhindern", "reduzieren", "erhöhen",
    # adverbs & connectors (lowercase)
    "jedoch", "deshalb", "außerdem", "andererseits",
    "im Gegensatz dazu", "trotzdem", "folglich",
    "zusammenfassend", "zuvor", "gegenwärtig", "demnächst",
    "eindeutig", "offensichtlich",
    "im Allgemeinen", "insbesondere", "im Gegenteil",
    "tatsächlich", "natürlich"
})
# ── Italian B1 (it) ───────────────────────────────────────────────────────────
_IT_B1: frozenset[str] = frozenset({
    # abstract concepts & nouns
    "opinione", "situazione", "soluzione", "risultato", "relazione",
    "opportunità", "decisione", "ragione", "dettaglio", "fatto",
    "differenza", "cambiamento", "sviluppo", "effetto", "vantaggio",
    "svantaggio", "scopo", "valore", "ruolo", "qualità",
    "processo", "metodo", "livello", "attenzione", "sforzo",
    "possibilità", "responsabilità", "importanza", "aspetto",
    "causa", "condizione", "contesto", "difficoltà", "prova",
    "funzione", "impatto", "questione", "conoscenza",
    "limite", "perdita", "significato", "necessità", "periodo",
    "pressione", "principio", "progresso", "senso",
    "fase", "struttura", "sistema", "termine", "prospettiva",
    "conclusione", "teoria", "affermazione", "analisi", "critica",
    "proposta", "alternativa", "tendenza", "conseguenza",
    "ipotesi", "argomento",
    # opinions & debate
    "dibattito", "discussione", "punto di vista", "giudizio",
    "raccomandazione", "valutazione", "accordo", "disaccordo",
    # work & professional (B1 depth)
    "presentazione", "candidatura", "colloquio", "dipartimento",
    "abilità", "qualificazione", "formazione", "obiettivo",
    "strategia", "budget", "beneficio", "risorsa",
    "collaborazione", "prestazione", "rendimento", "leadership",
    "retroazione", "capacità",
    # news & current affairs
    "annuncio", "elezione", "conflitto",
    "evento", "crisi", "sfida", "protesta", "riforma",
    "campagna", "politica", "governo", "società", "economia",
    "statistica", "sondaggio", "fonte", "trattato",
    # technology & digital (B1 depth)
    "software", "dispositivo", "rete", "dati", "sicurezza",
    "privacy", "piattaforma", "interfaccia",
    "utente", "database", "archiviazione", "aggiornamento",
    "intelligenza artificiale", "automazione",
    # health & medicine (extended)
    "trattamento", "sintomo", "diagnosi", "terapia",
    "riabilitazione", "vaccino", "antibiotico", "specialista",
    "dose", "effetto collaterale", "prevenzione", "burnout",
    # environment & sustainability
    "clima", "ambiente", "inquinamento", "sostenibile",
    "risorsa naturale", "specie", "habitat", "emissione",
    "impronta di carbonio", "biodiversità", "siccità", "alluvione",
    "deforestazione", "cambiamento climatico", "riciclabile",
    "rifiuto", "impatto ambientale", "energia solare",
    "energia eolica", "transizione energetica",
    # education & learning (B1 depth)
    "ricerca", "tesi", "borsa di studio",
    "laboratorio", "seminario", "metodologia", "istituzione",
    "accademia", "iscrizione", "competenza",
    "apprendimento autonomo",
    # social issues & society
    "uguaglianza", "diversità", "inclusione", "discriminazione",
    "pregiudizio", "povertà", "disuguaglianza", "giustizia",
    "diritti", "obbligo", "cittadinanza", "integrazione",
    "migrazione", "rifugiato", "comunità", "volontariato",
    "solidarietà", "benessere", "coesione sociale", "tolleranza",
    "equità", "marginalizzazione", "esclusione", "accessibilità",
    # extended abstract adjectives
    "complesso", "semplice", "generale", "specifico", "particolare",
    "certo", "evidente", "normale", "originale", "recente",
    "simile", "tipico", "vario", "efficiente",
    "flessibile", "innovativo", "creativo", "critico", "logico",
    "astratto", "concreto", "fondamentale", "pertinente",
    "significativo", "notevole", "considerevole", "eccezionale",
    "moderato", "intenso", "permanente", "temporaneo", "globale",
    "nazionale", "internazionale", "ufficiale", "formale", "informale",
    "urgente", "inevitabile", "ragionevole", "adeguato",
    "insufficiente", "eccessivo",
    # extended verbs (cognitive & communicative)
    "considerare", "analizzare", "interpretare", "dibattere",
    "argomentare", "dubitare", "riconoscere", "percepire",
    "riflettere", "valutare", "giustificare", "dimostrare",
    "verificare", "indagare", "risolvere", "implementare",
    "adattare", "trasformare", "contribuire", "partecipare",
    "collaborare", "comunicare", "negoziare", "gestire",
    "coordinare", "stabilire", "determinare", "identificare",
    "supervisionare", "promuovere", "sostenere", "difendere",
    "mettere in discussione", "influenzare",
    "prevenire", "ridurre", "aumentare",
    # extended adverbs & discourse connectors
    "tuttavia", "sebbene", "quindi", "inoltre",
    "d'altra parte", "al contrario", "nonostante", "di conseguenza",
    "in sintesi", "in precedenza", "attualmente", "prossimamente",
    "chiaramente", "evidentemente", "soprattutto",
    "in generale", "in particolare", "in effetti", "certamente"
})
# ── Portuguese B1 (pt) ────────────────────────────────────────────────────────
_PT_B1: frozenset[str] = frozenset({
    # abstract concepts & nouns
    "opinião", "situação", "solução", "resultado", "relação",
    "oportunidade", "decisão", "razão", "detalhe", "facto",
    "diferença", "mudança", "desenvolvimento", "efeito", "vantagem",
    "desvantagem", "propósito", "valor", "papel", "qualidade",
    "processo", "método", "nível", "atenção", "esforço",
    "possibilidade", "responsabilidade", "importância", "aspeto",
    "causa", "condição", "contexto", "dificuldade", "evidência",
    "função", "impacto", "influência", "assunto", "conhecimento",
    "limite", "perda", "significado", "necessidade", "período",
    "pressão", "princípio", "progresso", "sentido",
    "fase", "estrutura", "sistema", "termo", "perspetiva",
    "conclusão", "teoria", "afirmação", "análise", "crítica",
    "proposta", "alternativa", "tendência", "consequência",
    "hipótese", "argumento",
    # opinions & debate
    "debate", "discussão", "ponto de vista", "julgamento",
    "recomendação", "avaliação", "acordo", "desacordo",
    # work & professional (B1 depth)
    "apresentação", "candidatura", "entrevista", "departamento",
    "habilidade", "qualificação", "formação", "objetivo",
    "estratégia", "orçamento", "benefício", "recurso",
    "colaboração", "desempenho", "rendimento", "liderança",
    "feedback", "capacidade",
    # news & current affairs
    "anúncio", "eleição", "conflito",
    "evento", "crise", "desafio", "protesto", "reforma",
    "campanha", "política", "governo", "sociedade", "economia",
    "estatística", "sondagem", "fonte", "tratado",
    # technology & digital (B1 depth)
    "software", "dispositivo", "rede", "dados", "segurança",
    "privacidade", "interface",
    "utilizador", "base de dados", "armazenamento", "atualização",
    "inteligência artificial", "automação",
    # health & medicine (extended)
    "tratamento", "sintoma", "diagnóstico", "terapia",
    "reabilitação", "vacina", "antibiótico", "especialista",
    "dose", "efeito secundário", "prevenção", "burnout",
    # environment & sustainability
    "clima", "ambiente", "poluição", "sustentável",
    "recurso natural", "espécie", "hábitat", "emissão",
    "pegada de carbono", "biodiversidade", "seca", "inundação",
    "desflorestação", "aquecimento global", "reciclável",
    "resíduo", "impacto ambiental", "energia solar",
    "energia eólica", "transição energética",
    # education & learning (B1 depth)
    "investigação", "dissertação", "bolsa",
    "oficina", "seminário", "metodologia", "instituição",
    "academia", "matrícula", "competência",
    "aprendizagem autónoma",
    # social issues & society
    "igualdade", "diversidade", "inclusão", "discriminação",
    "preconceito", "pobreza", "desigualdade", "justiça",
    "direitos", "obrigação", "cidadania", "integração",
    "migração", "refugiado", "comunidade", "voluntariado",
    "solidariedade", "bem-estar", "coesão social", "tolerância",
    "equidade", "marginalização", "exclusão", "acessibilidade",
    # extended abstract adjectives
    "complexo", "simples", "geral", "específico", "particular",
    "certo", "evidente", "normal", "original", "recente",
    "semelhante", "típico", "variado", "eficiente",
    "flexível", "inovador", "criativo", "crítico", "lógico",
    "abstrato", "concreto", "fundamental", "relevante",
    "significativo", "notável", "considerável", "excecional",
    "moderado", "intenso", "permanente", "temporário", "global",
    "nacional", "internacional", "oficial", "formal", "informal",
    "urgente", "inevitável", "razoável", "adequado",
    "insuficiente", "excessivo",
    # extended verbs (cognitive & communicative)
    "considerar", "analisar", "interpretar", "debater",
    "argumentar", "duvidar", "reconhecer", "perceber",
    "refletir", "avaliar", "justificar", "demonstrar",
    "verificar", "investigar", "resolver", "implementar",
    "adaptar", "transformar", "contribuir", "participar",
    "colaborar", "comunicar", "negociar", "gerir",
    "coordenar", "estabelecer", "determinar", "identificar",
    "supervisionar", "promover", "apoiar", "defender",
    "questionar", "criticar", "influenciar",
    "prevenir", "reduzir", "aumentar",
    # extended adverbs & discourse connectors
    "contudo", "embora", "portanto", "além disso",
    "por outro lado", "ao contrário", "apesar de", "no entanto",
    "consequentemente", "em resumo", "anteriormente", "atualmente",
    "proximamente", "claramente", "evidentemente",
    "em geral", "em particular",
    "na verdade", "certamente"
})
# ── Russian B1 (ru) ───────────────────────────────────────────────────────────
_RU_B1: frozenset[str] = frozenset({
    # abstract concepts & nouns
    "мнение", "ситуация", "решение", "результат", "отношение",
    "возможность", "причина", "деталь", "факт",
    "различие", "изменение", "развитие", "эффект", "преимущество",
    "недостаток", "цель", "ценность", "роль", "качество",
    "процесс", "метод", "уровень", "внимание", "усилие",
    "ответственность", "важность", "аспект",
    "условие", "контекст", "трудность", "доказательство",
    "функция", "влияние", "знание",
    "потеря", "смысл", "потребность", "период",
    "давление", "принцип", "прогресс",
    "этап", "структура", "система", "термин", "перспектива",
    "вывод", "теория", "утверждение", "анализ", "критика",
    "предложение", "альтернатива", "тенденция", "последствие",
    "предположение", "гипотеза", "аргумент",
    # opinions & debate
    "дискуссия", "обсуждение", "точка зрения", "суждение",
    "рекомендация", "согласие", "несогласие",
    # work & professional (B1 depth)
    "презентация", "заявка", "собеседование", "отдел",
    "навык", "квалификация", "обучение", "стратегия",
    "бюджет", "выгода", "ресурс",
    "сотрудничество", "производительность", "руководство",
    "обратная связь", "способность",
    # news & current affairs
    "доклад", "объявление", "выборы", "конфликт",
    "событие", "кризис", "вызов", "протест", "реформа",
    "кампания", "политика", "правительство", "общество", "экономика",
    "статистика", "опрос", "заголовок", "источник", "договор",
    # technology & digital (B1 depth)
    "программное обеспечение", "устройство", "сеть", "данные",
    "безопасность", "конфиденциальность", "платформа",
    "интерфейс", "пользователь", "база данных", "хранение",
    "обновление", "искусственный интеллект", "автоматизация",
    # health & medicine (extended)
    "лечение", "симптом", "диагноз", "терапия",
    "реабилитация", "вакцина", "антибиотик", "специалист",
    "доза", "побочный эффект", "профилактика", "выгорание",
    # environment & sustainability
    "климат", "окружающая среда", "загрязнение", "устойчивый",
    "природный ресурс", "вид", "среда обитания", "выброс",
    "углеродный след", "биоразнообразие", "засуха", "наводнение",
    "вырубка лесов", "глобальное потепление", "перерабатываемый",
    "отходы", "экологическое воздействие", "солнечная энергия",
    "ветровая энергия",
    # education & learning (B1 depth)
    "исследование", "диссертация", "стипендия", "конференция",
    "мастер-класс", "семинар", "методология", "учреждение",
    "академия", "компетентность",
    # social issues & society
    "равенство", "разнообразие", "включённость", "дискриминация",
    "предрассудок", "бедность", "неравенство", "справедливость",
    "права", "обязанность", "гражданство", "интеграция",
    "миграция", "беженец", "сообщество", "волонтёрство",
    "солидарность", "благополучие", "толерантность", "доступность",
    # extended abstract adjectives
    "сложный", "простой", "общий", "конкретный", "особый",
    "определённый", "очевидный", "нормальный", "оригинальный",
    "недавний", "похожий", "типичный", "разнообразный",
    "эффективный", "гибкий", "инновационный", "творческий",
    "критический", "логический", "абстрактный", "фундаментальный",
    "актуальный", "значимый", "заметный", "значительный",
    "исключительный", "умеренный", "интенсивный", "постоянный",
    "временный", "глобальный", "национальный", "международный",
    "официальный", "формальный", "неформальный",
    "срочный", "неизбежный", "разумный", "достаточный",
    # extended verbs (cognitive & communicative)
    "рассматривать", "анализировать", "интерпретировать",
    "дискутировать", "аргументировать", "сомневаться",
    "признавать", "воспринимать", "размышлять",
    "оценивать", "обосновывать", "доказывать",
    "проверять", "исследовать", "разрешать", "внедрять",
    "адаптировать", "преобразовывать", "вносить вклад",
    "участвовать", "сотрудничать", "переговариваться",
    "управлять", "координировать", "устанавливать",
    "определять", "идентифицировать", "продвигать",
    "поддерживать", "защищать", "подвергать сомнению",
    "влиять", "предотвращать", "уменьшать", "увеличивать",
    # extended adverbs & discourse connectors
    "однако", "хотя", "поэтому", "кроме того",
    "с другой стороны", "напротив", "несмотря на", "тем не менее",
    "следовательно", "в итоге", "ранее", "в настоящее время",
    "в ближайшее время", "ясно", "очевидно",
    "в целом", "в частности",
    "на самом деле", "конечно"
})
# ── Japanese B1 (ja) ──────────────────────────────────────────────────────────
_JA_B1: frozenset[str] = frozenset({
    # abstract concepts & nouns
    "意見", "状況", "解決策", "結果", "関係",
    "機会", "決定", "理由", "詳細", "事実",
    "違い", "変化", "発展", "効果", "利点",
    "欠点", "目的", "価値", "役割", "品質",
    "プロセス", "方法", "レベル", "注意", "努力",
    "可能性", "責任", "重要性", "側面",
    "原因", "条件", "文脈", "困難", "証拠",
    "機能", "影響", "知識",
    "損失", "意味", "必要性", "期間",
    "圧力", "原則", "進歩", "感覚",
    "段階", "構造", "システム", "用語", "視点",
    "結論", "理論", "主張", "分析", "批判",
    "提案", "代替案", "傾向", "結果", "仮説",
    # opinions & debate
    "議論", "討論", "観点", "判断",
    "勧告", "評価", "合意", "不一致",
    # work & professional (B1 depth)
    "プレゼンテーション", "申請", "面接", "部門",
    "スキル", "資格", "目標",
    "戦略", "予算", "メリット", "リソース",
    "コラボレーション", "パフォーマンス", "リーダーシップ",
    "フィードバック", "能力",
    # news & current affairs
    "発表", "選挙", "紛争",
    "出来事", "危機", "課題", "抗議", "改革",
    "キャンペーン", "政治", "政府", "社会", "経済",
    "統計", "世論調査", "見出し", "出典", "条約",
    # technology & digital (B1 depth)
    "ソフトウェア", "デバイス", "ネットワーク", "データ",
    "セキュリティ", "プライバシー", "プラットフォーム",
    "インターフェース", "ユーザー", "データベース",
    "ストレージ", "人工知能", "自動化",
    # health & medicine (extended)
    "治療", "症状", "診断", "療法",
    "リハビリ", "ワクチン", "抗生物質", "専門医",
    "投与量", "副作用", "予防", "燃え尽き症候群",
    # environment & sustainability
    "気候", "環境", "汚染", "持続可能",
    "自然資源", "種", "生息地", "排出",
    "炭素フットプリント", "生物多様性", "干ばつ", "洪水",
    "森林伐採", "地球温暖化", "再生可能",
    "廃棄物", "環境への影響", "太陽エネルギー",
    "風力エネルギー", "エネルギー転換",
    # education & learning (B1 depth)
    "研究", "論文", "奨学金",
    "ワークショップ", "セミナー", "方法論", "機関",
    "アカデミー", "登録", "能力",
    # social issues & society
    "平等", "多様性", "包括性", "差別",
    "偏見", "貧困", "不平等", "公正",
    "権利", "義務", "市民権", "統合",
    "移住", "難民", "コミュニティ", "ボランティア活動",
    "連帯", "幸福", "寛容", "アクセシビリティ",
    # extended abstract adjectives
    "複雑な", "一般的な", "具体的な", "特定の",
    "明確な", "通常の", "独自の", "最近の",
    "深刻な", "類似した", "典型的な", "様々な",
    "効率的な", "柔軟な", "革新的な", "創造的な",
    "批判的な", "論理的な", "抽象的な", "根本的な",
    "関連した", "重要な", "注目に値する", "相当な",
    "例外的な", "穏やかな", "激しい", "永続的な",
    "一時的な", "国際的な", "公式の", "非公式の",
    # extended verbs (cognitive & communicative)
    "検討する", "分析する", "解釈する", "議論する",
    "主張する", "疑う", "認識する", "感知する",
    "反省する", "評価する", "正当化する", "証明する",
    "調査する", "実施する", "適応する", "変革する",
    "貢献する", "参加する", "協力する", "交渉する",
    "管理する", "調整する", "確立する", "特定する",
    "監督する", "推進する", "支持する", "反論する",
    "影響を与える", "防止する", "削減する", "増加させる",
    # extended adverbs & discourse connectors
    "しかし", "したがって", "また", "一方",
    "それにもかかわらず", "その結果", "以前", "現在",
    "近いうちに", "明確に", "明らかに",
    "一般的に", "具体的には",
    "実際には", "もちろん"
})
# ── Chinese B1 (zh) ───────────────────────────────────────────────────────────
_ZH_B1: frozenset[str] = frozenset({
    # abstract concepts & nouns
    "意见", "情况", "解决方案", "结果", "关系",
    "机会", "原因", "细节", "事实",
    "区别", "变化", "发展", "效果", "优势",
    "劣势", "目的", "价值", "作用", "质量",
    "过程", "方法", "层次", "注意力", "努力",
    "可能性", "责任", "重要性", "方面",
    "原因", "条件", "背景", "困难", "证据",
    "功能", "影响", "知识",
    "损失", "意义", "需求", "时期",
    "压力", "原则", "进步", "意义",
    "阶段", "结构", "系统", "术语", "视角",
    "结论", "理论", "主张", "分析", "批评",
    "提议", "替代方案", "趋势", "后果",
    "假设", "论点",
    # opinions & debate
    "辩论", "讨论", "观点", "判断",
    "评估", "同意", "不同意",
    # work & professional (B1 depth)
    "演示", "申请", "面试", "部门",
    "技能", "资格", "培训", "目标",
    "战略", "预算", "收益", "资源",
    "合作", "绩效", "领导力",
    "反馈", "能力",
    # news & current affairs
    "公告", "选举", "冲突",
    "事件", "危机", "挑战", "抗议", "改革",
    "运动", "政策", "政府", "社会", "经济",
    "统计数据", "民意调查", "标题", "来源", "条约",
    # technology & digital (B1 depth)
    "软件", "设备", "数据",
    "隐私", "平台", "程序", "界面",
    "用户", "数据库", "存储",
    "人工智能", "自动化",
    # health & medicine (extended)
    "治疗", "症状", "诊断", "疗法",
    "康复", "疫苗", "抗生素", "专科医生",
    "剂量", "副作用", "预防", "职业倦怠",
    # environment & sustainability
    "气候", "环境", "污染", "可持续",
    "自然资源", "物种", "栖息地", "排放",
    "碳足迹", "生物多样性", "干旱", "洪水",
    "森林砍伐", "全球变暖", "可回收",
    "废物", "环境影响", "太阳能",
    "风能", "能源转型",
    # education & learning (B1 depth)
    "研究", "论文", "奖学金",
    "研讨会", "方法论", "机构",
    "学院", "注册", "能力",
    # social issues & society
    "平等", "多样性", "包容性", "歧视",
    "偏见", "贫困", "不平等", "正义",
    "权利", "义务", "公民权", "融合",
    "移民", "难民", "社区", "志愿活动",
    "团结", "福祉", "宽容", "无障碍",
    # extended abstract adjectives
    "复杂", "简单", "一般", "具体", "特定",
    "明确", "正常", "独特", "近期",
    "严重", "相似", "典型", "多样",
    "高效", "灵活", "创新", "有创意",
    "批判性", "合理的", "抽象", "根本",
    "相关", "显著",
    "特殊", "温和", "激烈", "持久",
    "临时", "国际", "官方", "正式", "非正式",
    # extended verbs (cognitive & communicative)
    "考虑", "分析", "辩论",
    "论证", "怀疑", "承认", "感知",
    "反思", "评估", "证明", "核实",
    "调查", "执行", "适应", "转变",
    "促进", "谈判", "协调", "确立",
    "确定", "监督", "推广", "支持",
    "挑战", "影响", "预防", "减少", "增加",
    # extended adverbs & discourse connectors
    "然而", "因此", "此外", "另一方面",
    "相反", "尽管", "不过", "因此",
    "总的来说", "目前", "不久后",
    "明显地", "尤其是",
    "具体地", "实际上", "当然"
})
# ── Arabic B1 (ar) ────────────────────────────────────────────────────────────
# Unvocalised forms matching arabic.py's _strip_tashkeel() output.
_AR_B1: frozenset[str] = frozenset({
    # abstract concepts & nouns
    "رأي", "حالة", "حل", "علاقة",
    "فرصة", "قرار", "سبب", "تفصيل", "حقيقة",
    "فرق", "تغيير", "تطور", "أثر", "ميزة",
    "عيب", "قيمة", "دور", "جودة",
    "أسلوب", "مستوى", "انتباه", "جهد",
    "إمكانية", "مسؤولية", "أهمية", "جانب",
    "سبب", "شرط", "سياق", "صعوبة", "دليل",
    "وظيفة", "تأثير", "معرفة",
    "خسارة", "معنى", "حاجة", "مرحلة",
    "ضغط", "مبدأ", "تقدم", "مفهوم",
    "هيكل", "نظام", "مصطلح", "منظور",
    "استنتاج", "نظرية", "تصريح", "تحليل", "نقد",
    "مقترح", "بديل", "اتجاه", "عواقب",
    "افتراض", "فرضية", "حجة",
    # opinions & debate
    "نقاش", "مناقشة", "وجهة نظر", "حكم",
    "توصية", "تقييم", "اتفاق", "خلاف",
    # work & professional (B1 depth)
    "عرض تقديمي", "طلب", "مقابلة", "قسم",
    "مهارة", "تأهيل", "غاية",
    "استراتيجية", "ميزانية", "فائدة", "مورد",
    "تعاون", "أداء", "قيادة",
    "تغذية راجعة", "كفاءة",
    # news & current affairs
    "إعلان", "انتخابات", "صراع",
    "حدث", "أزمة", "تحدي", "احتجاج", "إصلاح",
    "حملة", "سياسة", "حكومة", "مجتمع", "اقتصاد",
    "إحصاء", "استطلاع", "مصدر", "معاهدة",
    # technology & digital (B1 depth)
    "جهاز", "شبكة", "بيانات", "أمان",
    "خصوصية", "منصة", "واجهة",
    "مستخدم", "قاعدة بيانات", "تخزين",
    "ذكاء اصطناعي", "أتمتة",
    # health & medicine (extended)
    "علاج", "أعراض", "تشخيص", "علاج طبيعي",
    "تأهيل", "لقاح", "مضاد حيوي", "متخصص",
    "جرعة", "أعراض جانبية", "وقاية", "إرهاق",
    # environment & sustainability
    "مناخ", "بيئة", "تلوث", "مستدام",
    "مورد طبيعي", "نوع", "موطن", "انبعاثات",
    "بصمة الكربون", "تنوع بيولوجي", "جفاف", "فيضان",
    "إزالة الغابات", "الاحترار العالمي", "قابل للتدوير",
    "نفايات", "أثر بيئي", "طاقة شمسية",
    "طاقة رياح", "تحول طاقوي",
    # education & learning (B1 depth)
    "منحة", "مؤتمر",
    "ورشة", "ندوة", "منهجية", "مؤسسة",
    "أكاديمية", "تسجيل", "كفاءة",
    # social issues & society
    "مساواة", "تنوع", "شمول", "تمييز",
    "تحيز", "فقر", "عدم مساواة", "عدالة",
    "جنسية", "اندماج",
    "هجرة", "لاجئ", "مجتمع", "تطوع",
    "تضامن", "رفاهية", "تسامح",
    # extended abstract adjectives
    "معقد", "بسيط", "محدد",
    "واضح", "طبيعي", "أصيل",
    "مشابه", "نموذجي", "متنوع",
    "فعال", "مرن", "مبتكر", "إبداعي",
    "نقدي", "منطقي", "مجرد", "أساسي",
    "ذو صلة", "ملحوظ",
    "استثنائي", "معتدل", "مكثف", "دائم",
    "مؤقت", "عالمي", "دولي", "رسمي", "غير رسمي",
    # extended verbs (cognitive & communicative)
    "يراعي", "يحلل", "يفسر", "يناقش",
    "يجادل", "يشكك", "يعترف", "يدرك",
    "يفكر", "يقيم", "يبرر", "يثبت",
    "يتحقق", "يبحث", "يحل", "ينفذ",
    "يكيف", "يحول", "يساهم", "يشارك",
    "يتعاون", "يتواصل", "يتفاوض", "يدير",
    "ينسق", "يحدد", "يشرف", "يروج",
    "يدعم", "يدافع", "يتحدى", "يؤثر",
    "يمنع", "يقلل", "يزيد",
    # extended adverbs & discourse connectors
    "ومع ذلك", "لذلك", "علاوة على ذلك",
    "من ناحية أخرى", "على العكس", "بالرغم من",
    "نتيجة لذلك", "باختصار", "سابقاً",
    "حالياً", "قريباً", "بوضوح", "من الواضح",
    "بشكل رئيسي", "عموماً",
    "بالتحديد", "في الواقع", "بالطبع"
})
# ── Hebrew B1 (he) ────────────────────────────────────────────────────────────
# Unvocalised consonantal forms matching hebrew.py's _strip_nikud() output.
_HE_B1: frozenset[str] = frozenset({
    # abstract concepts & nouns
    "דעה", "מצב", "פתרון", "קשר",
    "הזדמנות", "החלטה", "סיבה", "פרט", "עובדה",
    "הבדל", "שינוי", "התפתחות", "השפעה", "יתרון",
    "חיסרון", "מטרה", "ערך", "תפקיד", "איכות",
    "תהליך", "שיטה", "רמה", "תשומת לב", "מאמץ",
    "אפשרות", "אחריות", "חשיבות", "היבט",
    "גורם", "תנאי", "הקשר", "קושי", "ראיה",
    "תפקוד",
    "אובדן", "משמעות", "צורך", "תקופה",
    "לחץ", "עיקרון", "התקדמות", "תחושה",
    "שלב", "מבנה", "מערכת", "מונח", "נקודת מבט",
    "מסקנה", "תיאוריה", "טענה", "ביקורת",
    "הצעה", "חלופה", "מגמה", "השלכה",
    "השערה", "טיעון",
    # opinions & debate
    "ויכוח", "דיון", "השקפה", "שיפוט",
    "המלצה", "הערכה", "הסכמה", "אי הסכמה",
    # work & professional (B1 depth)
    "מצגת", "בקשה", "ראיון", "מחלקה",
    "כישרון", "כישורים", "הכשרה", "יעד",
    "אסטרטגיה", "תקציב", "תועלת", "משאב",
    "שיתוף פעולה", "ביצועים", "מנהיגות",
    "משוב", "יכולת",
    # news & current affairs
    "הכרזה", "בחירות", "סכסוך",
    "אירוע", "משבר", "אתגר", "מחאה", "רפורמה",
    "קמפיין", "פוליטיקה", "ממשלה", "כלכלה",
    "נתונים סטטיסטיים", "סקר", "כותרת", "מקור", "הסכם",
    # technology & digital (B1 depth)
    "תוכנה", "מכשיר", "רשת", "נתונים", "אבטחה",
    "פרטיות", "פלטפורמה", "ממשק",
    "משתמש", "מסד נתונים", "אחסון", "עדכון",
    "בינה מלאכותית", "אוטומציה",
    # health & medicine (extended)
    "טיפול", "תסמין", "אבחנה", "טיפול רפואי",
    "שיקום", "חיסון", "אנטיביוטיקה", "מומחה",
    "מינון", "תופעת לוואי", "מניעה", "שחיקה",
    # environment & sustainability
    "אקלים", "סביבה", "זיהום", "בר קיימא",
    "משאב טבעי", "מין", "בית גידול", "פליטה",
    "טביעת רגל פחמנית", "מגוון ביולוגי", "בצורת", "שיטפון",
    "כריתת יערות", "התחממות עולמית", "ניתן למחזר",
    "פסולת", "השפעה סביבתית", "אנרגיה סולארית",
    "אנרגיה רוחית", "מעבר אנרגטי",
    # education & learning (B1 depth)
    "מחקר", "עבודת גמר", "מלגה", "כנס",
    "סדנה", "סמינר", "מתודולוגיה", "מוסד",
    "אקדמיה", "הרשמה", "כשירות",
    # social issues & society
    "שוויון", "גיוון", "הכלה", "אפליה",
    "דעה קדומה", "עוני", "אי שוויון", "צדק",
    "זכויות", "חובה", "אזרחות", "שילוב",
    "הגירה", "פליט", "קהילה", "התנדבות",
    "סולידריות", "רווחה", "סובלנות", "נגישות",
    # extended abstract adjectives
    "מורכב", "פשוט", "כללי", "ספציפי",
    "ברור", "רגיל", "מקורי",
    "חמור", "דומה", "טיפוסי", "מגוון",
    "יעיל", "גמיש", "חדשני", "יצירתי",
    "ביקורתי", "הגיוני", "מופשט", "בסיסי",
    "רלוונטי", "משמעותי", "בולט", "ניכר",
    "יוצא דופן", "מתון", "עצים", "קבוע",
    "זמני", "בינלאומי", "רשמי", "בלתי רשמי",
    # extended verbs (cognitive & communicative)
    "לשקול", "לנתח", "לפרש", "לדון",
    "לטעון", "לפקפק", "להכיר", "לתפוס",
    "להרהר", "להעריך", "להצדיק", "להוכיח",
    "לאמת", "לחקור", "לפתור", "ליישם",
    "להתאים", "לשנות", "לתרום", "להשתתף",
    "לשתף פעולה", "לתקשר", "לנהל משא ומתן",
    "לנהל", "לתאם", "לבסס", "לזהות",
    "לפקח", "לקדם", "לתמוך", "להגן",
    "לערער", "להשפיע", "למנוע", "להפחית",
    # extended adverbs & discourse connectors
    "עם זאת", "לכן", "בנוסף",
    "מצד שני", "להיפך", "למרות", "בכל זאת",
    "כתוצאה", "בקצרה", "בעבר",
    "כיום", "בקרוב", "בבירור", "ברור",
    "בפרט", "למעשה", "כמובן"
})
#: Map from language code to frozenset of B1 lemmas (excludes A1 and A2 items).
B1: dict[str, frozenset[str]] = {
    "es": _ES_B1,
    "fr": _FR_B1,
    "de": _DE_B1,
    "it": _IT_B1,
    "pt": _PT_B1,
    "ru": _RU_B1,
    "ja": _JA_B1,
    "zh": _ZH_B1,
    "ar": _AR_B1,
    "he": _HE_B1,
}
