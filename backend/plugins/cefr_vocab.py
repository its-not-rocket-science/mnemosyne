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

Priority chain (confidence returned by _vocab_confidence):
  A1 (0.90) → A2 (0.88) → B1 (0.86) → in-vocab (0.85)
  → B2/C1/C2 only suppress OOV: B2 (0.84) → C1 (0.82) → C2 (0.80) → OOV (0.50)

  # In _extract_vocabulary():
  if lemma in _A1:
      data["cefr_level"] = "A1"
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
    "bon", "mauvais", "petit", "nouveau", "vieux", "jeune",
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
    "effrayé", "incroyable", "colère", "blond", "ennuyeux", "dangereux", "délicieux", "sec", "excité", "célèbre", "fantastique",
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
    "glücklich", "müde", "krank", "gesund", "hungrig", "durstig",
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
    "erinnern", "reiten", "rennen", "schicken", "stehen",
    "schwimmen", "reisen", "aufwachen", "tragen", "gewinnen",
    "verkaufen", "fallen", "brechen", "träumen", "heiraten",
    "bevorzugen", "versprechen", "singen", "zeigen",
    # adjectives (lowercase)
    "ängstlich", "erstaunlich", "wütend", "blond", "langweilig",
    "gefährlich", "dunkel", "lecker", "trocken", "aufgeregt", "fantastisch", "dick", "freundlich", "lustig", "großartig", "hart",
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
    "платить", "отдыхать", "помнить", "ехать", "бегать",
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
    "動く", "払う", "覚える", "走る", "送る", "立つ",
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
    "画", "修理", "飞", "忘记", "猜", "恨",
    "包括", "介绍", "保持", "笑", "失去", "移动",
    "支付", "放松", "记得", "重复", "骑", "发送",
    "游泳", "旅行", "醒来", "穿", "赢", "卖",
    "跌倒", "打破", "做梦", "结婚", "更喜欢", "承诺",
    "唱", "展示",
    # adjectives (extended)
    "害怕", "令人惊讶", "生气", "美丽", "无聊",
    "危险", "美味", "干燥", "兴奋", "著名",
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
    "جيد", "سيئ", "كبير", "صغير", "جديد", "شاب", "جميل",
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
    "مراهق", "سائح", "زائر", "نادل", "كاتب",
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
    "مظلم", "لذيذ", "جاف", "مشهور", "رائع",
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
    "היה", "עשה", "הלך", "בא", "יכול", "רצה", "אמר",
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
    "שמח", "עייף", "חולה", "בריא",
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
    "proyecto", "informe", "plazo", "sueldo", "salario", "asignatura", "examen", "nota", "deberes", "tarea", "carrera", "título",
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
    "cartera", "tarjeta", "cuenta", "factura", "cambio", "bolsa", "etiqueta", "devolución",
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
    "projet", "rapport", "délai", "salaire", "promotion",
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
    "recommander", "décrire", "imaginer", "espérer", "organiser", "comparer", "convaincre", "inviter", "célébrer",
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
    "empfehlen", "beschreiben", "hoffen", "planen", "vergleichen", "überzeugen", "einladen",
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
    "progetto", "rapporto", "scadenza", "stipendio", "materia", "esame", "voto", "compito", "carriera", "titolo",
    "conferenza", "lavagna", "quaderno",
    # extended travel & transport
    "passaporto", "biglietto", "prenotazione", "valigia", "dogana", "check-in", "carta d'imbarco", "arrivo", "partenza",
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
    "consigliare", "descrivere", "immaginare", "sperare", "organizzare", "confrontare", "convincere", "invitare",
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
    "projeto", "relatório", "prazo", "salário", "promoção",
    "disciplina", "exame", "nota", "tarefa", "carreira", "título",
    "conferência", "quadro", "caderno",
    # extended travel & transport
    "passaporte", "bilhete", "reserva", "mala", "alfândega",
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
    "勧める", "描写する", "想像する", "希望する", "計画する", "比べる", "納得させる", "招待する",
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
    "组织", "说服", "邀请",
    "庆祝", "祝贺", "道歉", "感谢", "享受", "继续", "属于",
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
    "فريق", "بطولة", "مباراة", "دوري", "تدريب", "مدرب", "مشجع", "رياضي",
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
    "קבלה", "מבצע", "מידה", "חדר הלבשה", "מותג",
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
    "קבוצה", "אליפות", "משחק", "טורניר", "שער",
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

# ── Finnish (fi) ─────────────────────────────────────────────────────────────
# Lemma conventions: spaCy fi_core_news_sm lowercase lemmas.
# Verbs → 1st infinitive (mennä, olla); Nouns → nom. sg. (talo, kissa).
_FI_A1: frozenset[str] = frozenset({
    # core verbs (1st infinitive)
    "olla", "mennä", "tulla", "tehdä", "saada", "voida", "sanoa",
    "nähdä", "pitää", "haluta", "antaa", "ottaa", "tietää", "lähteä",
    "asua", "syödä", "juoda", "nukkua", "katsoa", "puhua",
    "ymmärtää", "kysyä", "vastata", "oppia", "lukea", "kirjoittaa", "kuulla",
    # family / people
    "isä", "äiti", "lapsi", "tyttö", "poika", "ystävä", "perhe",
    "mies", "nainen",
    # home / school / daily objects
    "talo", "huone", "ovi", "ikkuna", "kirja", "puhelin", "raha", "koulu",
    # transport
    "auto", "bussi", "juna",
    # animals
    "koira", "kissa",
    # food / drink
    "vesi", "ruoka", "leipä", "kahvi", "maito",
    # time
    "nimi", "vuosi", "päivä", "viikko", "kuukausi", "aamu", "ilta", "yö",
    # nature / geography
    "aurinko", "lumi", "maa", "kaupunki", "kauppa",
    # basic adjectives
    "hyvä", "huono", "iso", "pieni", "uusi", "vanha", "nuori",
    "kaunis", "nopea", "kallis", "halpa", "pitkä", "lyhyt", "kylmä", "lämmin",
    # numbers 1–10, 100, 1000
    "yksi", "kaksi", "kolme", "neljä", "viisi", "kuusi",
    "seitsemän", "kahdeksan", "yhdeksän", "kymmenen", "sata", "tuhat",
    # weekdays
    "maanantai", "tiistai", "keskiviikko", "torstai", "perjantai",
    "lauantai", "sunnuntai",
    # basic colours
    "punainen", "sininen", "vihreä", "keltainen", "musta", "valkoinen",
    "harmaa", "ruskea",
})

_FI_A2: frozenset[str] = frozenset({
    # verbs not in A1
    "rakastaa", "herätä", "pukeutua", "auttaa", "maksaa", "ostaa",
    "myydä", "varata", "tilata", "tarvita", "käyttää", "toivoa",
    "muistaa", "unohtaa", "kokeilla", "matkustaa", "juosta", "kävellä",
    "ajaa", "lentää", "uida", "harrastaa", "opiskella", "työskennellä",
    "laittaa", "kokata", "siivota", "pestä", "korjata", "rakentaa",
    "esitellä", "tavata", "kiittää", "pyytää", "odottaa", "lähettää",
    "soittaa", "etsiä", "löytää", "avata", "sulkea", "valmistaa",
    "pakata", "vierailla", "jutella", "nauraa", "itkeä", "levätä",
    "iloita", "surra", "rentoutua", "innostua",
    # seasons / weather
    "iltapäivä", "kevät", "kesä", "syksy", "talvi", "pilvi", "sade",
    "lämpötila", "tuuli", "ukkonen", "jää",
    # nature / terrain
    "järvi", "joki", "meri", "vuori", "metsä", "pelto", "piha",
    "puutarha", "ranta", "puisto", "katu", "tie", "silta",
    # services / buildings
    "ravintola", "kahvila", "hotelli", "lentokenttä", "rautatieasema",
    "apteekki", "pankki", "posti", "kirjasto", "sairaala", "yliopisto",
    "toimisto",
    # travel
    "matka", "lento", "lippu", "passi", "laukku",
    # clothing
    "paita", "housut", "takki", "kenkä", "hattu", "huivi",
    # occupations / study
    "ammatti", "lääkäri", "opettaja", "kurssi", "todistus", "kokous",
    # media / culture
    "lehti", "televisio", "radio", "elokuva", "musiikki", "tanssi",
    "urheilu", "kuva", "valokuva", "taide", "museo", "teatteri", "harrastus",
    # celebrations
    "syntymäpäivä", "juhla", "lahja", "kukka", "kakku",
    # food extended
    "hedelmä", "liha", "kala", "kana", "muna", "juusto",
    "peruna", "tomaatti", "omena", "appelsiini", "banaani", "mansikka",
    "riisi", "pasta", "kasvikset",
    # home rooms / housing
    "keittiö", "olohuone", "makuuhuone", "kylpyhuone", "parveke",
    "naapuri", "asunto", "vuokra", "kerrostalo",
    # technology
    "sähköposti", "internet", "tietokone", "tabletti", "sovellus",
    # health basics
    "kipu", "lääke", "resepti",
    # misc nouns
    "apu", "ongelma", "kysymys", "vastaus", "idea", "asia", "tapahtuma",
    "kieli", "historia", "tulevaisuus", "rutiini", "käytäntö",
    # extra colours
    "vaaleanpunainen", "oranssi", "violetti",
    # adjectives not in A1
    "kiva", "mukava", "hauska", "tylsä", "vaikea", "helppo",
    "mielenkiintoinen", "tärkeä", "hyödyllinen", "tarpeellinen",
    "oikea", "väärä", "sama", "erilainen", "tavallinen",
    "terve", "sairas", "väsynyt", "iloinen", "surullinen",
    "pelokas", "innostunut", "rauhallinen", "kiireinen", "herkullinen",
    "kuuma", "viileä", "kostea", "kuiva", "tuore", "raskas", "kevyt",
    "leveä", "kapea",
})

_FI_B1: frozenset[str] = frozenset({
    # verbs
    "kehittää", "parantaa", "vaikuttaa", "osallistua", "järjestää",
    "hoitaa", "huolehtia", "kuvailla", "selittää", "vertailla",
    "arvioida", "analysoida", "suunnitella", "toteuttaa", "saavuttaa",
    "epäonnistua", "onnistua", "päättää", "valita", "hyväksyä",
    "hylätä", "ehdottaa", "suostua", "kieltäytyä", "väittää",
    "todistaa", "myöntää", "kiistää", "johtaa", "hallita",
    "ohjata", "neuvoa", "tutkia", "selvittää", "raportoida",
    "julkaista", "ilmoittaa", "osata", "pystyä", "jaksaa",
    "muodostaa", "kuulua", "liittyä", "erota", "yhdistyä",
    "kuvata", "muuttua", "kasvaa", "vahvistaa", "heikentää",
    # society / politics
    "yhteiskunta", "hallitus", "politiikka", "puolue", "vaalit",
    "laki", "oikeus", "talous", "budjetti", "verotus",
    "eläke", "sosiaalituet", "poliisi", "armeija",
    # environment
    "ympäristö", "saastuminen", "ilmastonmuutos", "kierrätys",
    "energiankulutus", "luonnonvarat", "suojelu",
    # abstract nouns
    "ajatus", "mielipide", "käsitys", "arvo", "periaate",
    "tavoite", "unelma", "ratkaisu", "tulos", "muutos",
    "kasvu", "kehitys", "edistys", "haaste", "riski",
    "mahdollisuus", "uhka", "vaikutus", "asenne", "motivaatio",
    "taito", "kyky", "rakenne", "normi",
    # work / business
    "yritys", "organisaatio", "johtaja", "esimies", "asiantuntija",
    "kokemus", "osaaminen", "koulutus", "ura", "palkka",
    "sopimus", "neuvottelu", "projekti", "tehtävä", "vastuu",
    # communication / relations
    "viestintä", "yhteistyö", "suhde", "luottamus", "tuki",
    "konflikti", "päätös", "ehdotus",
    # health (intermediate)
    "terveydenhuolto", "diagnoosi", "hoito", "leikkaus", "toipuminen",
    "stressi", "uupumus", "mielenterveys", "kuntoutus",
    # culture / arts
    "kirjallisuus", "runous", "näytelmä", "dokumentti",
    "kritiikki", "arvostelu", "teos", "näyttely",
    # science / technology
    "tutkimus", "tiede", "teknologia", "tekoäly", "digitalisaatio",
    "ohjelmointi", "data",
    # education
    "tutkinto", "opinnot", "seminaari", "väitöskirja",
    # adjectives
    "merkittävä", "oleellinen", "keskeinen", "välttämätön",
    "tehokas", "kestävä", "nykyinen", "entinen", "tuleva",
    "historiallinen", "kansainvälinen", "kansallinen", "alueellinen",
    "paikallinen", "julkinen", "yksityinen", "poliittinen",
    "sosiaalinen", "taloudellinen", "teknologinen", "tieteellinen",
    "kulttuurinen", "taiteellinen", "ammatillinen", "henkilökohtainen",
    "yleinen", "konkreettinen", "abstrakti", "monimutkainen",
    "yksinkertainen", "laaja", "vakava", "kriittinen",
    "aktiivinen", "passiivinen", "riippuvainen", "itsenäinen",
    "vastuullinen", "luotettava", "epävarma",
    # extra nouns / verbs to reach 200
    "prosessi", "menetelmä", "tekijä", "yhteys", "vuorovaikutus",
    "osallistuminen", "muutos", "standardi",
    "tulostavoite", "mittari", "indikaattori", "seuraus", "vaikuttavuus",
    "toiminto", "peruste",
})

_FI_B2: frozenset[str] = frozenset({
    # verbs (formal / academic register)
    "priorisoida", "koordinoida", "fasilitoida", "optimoida",
    "standardisoida", "kyseenalaistaa", "hyödyntää", "integroida",
    "legitimoida", "hahmottaa", "systematisoida", "visualisoida",
    "implementoida", "evaluoida", "modernisoida",
    # nouns (institutional / management)
    "lainsäädäntö", "oikeuslaitos", "demokratia", "autoritarismi",
    "byrokratia", "infrastruktuuri", "instituutio", "mekanismi",
    "paradigma", "hierarkia", "konsensus", "kompromissi",
    "dilemma", "konteksti", "perspektiivi", "dimensio", "aspekti",
    "fenomeeni", "diskurssi", "retoriikka", "narratiivi", "ideologia",
    "ekosysteemi", "biodiversiteetti", "resilienssi",
    "transformaatio", "innovaatio", "disruptio",
    "kapasiteetti", "kompetenssi", "legitimiteetti", "transparenssi",
    # adjectives
    "pragmaattinen", "strateginen", "systemaattinen", "hierarkkinen",
    "institutionaalinen", "byrokraattinen", "demokraattinen",
    "autoritaarinen", "liberaali", "konservatiivinen", "progressiivinen",
    "interdisiplinaarinen", "kokonaisvaltainen",
    "johdonmukainen", "epäjohdonmukainen", "implisiittinen", "eksplisiittinen",
    "normatiivinen", "deskriptiivinen", "metodinen", "rationaalinen",
})

_FI_C1: frozenset[str] = frozenset({
    # verbs (philosophical / specialist)
    "eksplikoida", "konstituoida", "dekonstruoida", "problematisoida",
    "kontekstualisoida", "konkretisoida", "operationalisoida",
    "rekonstituoida", "reifioida", "instrumentalisoida",
    # nouns (philosophical / analytical)
    "epistemologia", "metodologia", "ontologia", "aksiologia",
    "hermeneutiikka", "fenomenologia", "teleologia", "dialektiikka",
    "emansipaatio", "hegemonia", "intersubjektiviteetti",
    "representaatio", "signifikaatio", "konnotaatio", "denotaatio",
    "semiootiikka", "intertekstuaalisuus", "polyfonia", "parataksi",
    "hypotaksi", "ambivalenssi", "paradoksi", "aporia", "antinomia",
    "pleonasmi", "episteme", "logosentrismi", "subjektiviteetti",
    "objektiviteetti", "artikulaatio",
    # adjectives
    "episteeminen", "ontologinen", "aksiologinen", "teleologinen",
    "dialektinen", "hermeneutinen", "fenomenologinen",
    "emansipatoorinen", "hegemoninen", "intersubjektiivinen",
    "ambivalentti", "aporettinen", "tautologinen",
    "intertekstuaalinen", "logosentristinen", "polyfooninen",
})

_FI_C2: frozenset[str] = frozenset({
    # nouns (rhetoric / literary theory / archaic)
    "anakoluti", "zeugma", "syllepsi", "antistasis", "anadiplosis",
    "epistrofi", "chiasmi", "litotes", "prosopopoeia", "ekfrasi",
    "diegesis", "mimesis", "katarsis", "anagnorisis", "hamartia",
    "hybris", "nemesis", "peripeteia", "eudaimonia", "ataraxia",
    "apatheia", "parrhesia", "arete", "phronesis", "kairos",
    "apofaasi", "polyptoon", "antanaklasis", "epifora", "anafora",
    # archaic / rare Finnish nouns
    "elämänväsymys", "kaihomielisyys", "synkkämielisyys", "sielunrauha",
    "ylevyys", "jalomielisyys", "anteliaisuus", "pyyteettömyys",
    "uhrautuvaisuus", "autuus", "hurskaus", "katumus",
    "teeskentely", "hurskastelu", "vilpittömyys",
    # archaic / rare adjectives
    "jalomielinen", "synkkämielinen", "kaihomielinen",
    "ylevä", "hyveellinen", "hartainen", "hurskas",
    "melankolinen", "katuvainen", "nöyrä",
    "apostolinen", "profeetallinen", "eristäytyvä",
    "kiihkottoman", "apaattinen", "arvoituksellinen",
})

# ── Turkish (tr) ──────────────────────────────────────────────────────────────
# Lemma conventions: zeyrek lemmas normalised (İ→i, I→ı, lowercase).
# Verbs → infinitive with -(m)ak/-(m)ek (gitmek, yapmak).
_TR_A1: frozenset[str] = frozenset({
    # core verbs
    "gitmek", "gelmek", "yapmak", "olmak", "bilmek", "istemek", "görmek",
    "vermek", "almak", "demek", "söylemek", "anlamak", "okumak", "yazmak",
    "yemek", "içmek", "uyumak", "kalkmak", "oturmak", "beklemek",
    "bakmak", "dinlemek", "konuşmak", "çalışmak", "öğrenmek",
    "bulmak", "başlamak", "bitmek", "açmak", "kapatmak", "sevmek",
    # family / people
    "anne", "baba", "çocuk", "kız", "erkek", "arkadaş", "aile",
    # home / school / daily objects
    "ev", "oda", "kapı", "okul", "kitap", "masa", "sandalye",
    # transport
    "araba", "otobüs", "tren",
    # animals
    "köpek", "kedi",
    # food / drink
    "su", "yemek", "ekmek", "çay", "süt",
    # everyday items
    "para", "telefon",
    # time
    "isim", "yıl", "gün", "hafta", "ay", "sabah", "akşam", "gece",
    # nature / geography
    "güneş", "ülke", "şehir", "sokak",
    # adjectives
    "iyi", "kötü", "büyük", "küçük", "yeni", "eski", "genç",
    "güzel", "hızlı", "yavaş", "pahalı", "ucuz", "uzun", "kısa",
    "sıcak", "soğuk",
    # numbers 1–10, 100, 1000
    "iki", "üç", "dört", "beş", "altı", "yedi",
    "sekiz", "dokuz", "on", "yüz", "bin",
    # weekdays
    "pazartesi", "salı", "çarşamba", "perşembe", "cuma",
    "cumartesi", "pazar",
    # basic colours
    "kırmızı", "mavi", "yeşil", "sarı", "siyah", "beyaz",
    "gri", "kahverengi", "turuncu", "mor",
})

_TR_A2: frozenset[str] = frozenset({
    # verbs not in A1
    "uyanmak", "giyinmek", "ödemek", "satmak", "kullanmak",
    "planlamak", "hatırlamak", "unutmak", "denemek", "koşmak",
    "yürümek", "uçmak", "yüzmek", "pişirmek", "temizlemek",
    "yıkamak", "kiralamak", "tanışmak", "tanıtmak", "kaydetmek",
    "göndermek", "aramak", "taşımak", "seçmek", "kazanmak",
    "kaybetmek", "gülmek", "ağlamak", "korkmak", "dinlenmek",
    "hazırlanmak", "alışmak", "katılmak", "ayrılmak", "buluşmak",
    "tekrarlamak", "sormak", "anlatmak", "düşünmek", "hissetmek",
    "indirmek", "çıkarmak",
    # seasons / weather
    "öğle", "bahar", "yaz", "sonbahar", "kış", "bulut", "yağmur",
    "rüzgar", "sıcaklık", "kar",
    # nature / terrain
    "göl", "nehir", "deniz", "dağ", "orman", "tarla", "bahçe",
    "park", "cadde", "köprü",
    # travel
    "yolculuk", "uçuş", "bilet", "pasaport", "bavul",
    # clothing
    "gömlek", "pantolon", "mont", "ayakkabı", "şapka", "atkı",
    # occupations
    "meslek", "doktor", "hemşire", "öğretmen",
    # media / culture
    "gazete", "televizyon", "radyo", "film", "müzik", "dans",
    "spor", "fotoğraf", "resim", "sanat", "müze", "tiyatro", "hobi",
    # celebrations
    "doğum günü", "parti", "hediye", "çiçek", "pasta",
    # technology
    "email", "internet", "bilgisayar", "tablet", "uygulama",
    # food extended
    "sebze", "meyve", "et", "balık", "tavuk", "yumurta", "peynir",
    "patates", "domates", "elma", "portakal", "muz", "çilek",
    "pirinç", "makarna",
    # home rooms / housing
    "mutfak", "salon", "yatak odası", "banyo", "teras",
    "komşu", "daire", "kira", "apartman",
    # services / buildings
    "lokanta", "kafe", "otel", "havalimanı", "eczane",
    "banka", "postane", "kütüphane", "hastane", "üniversite", "ofis",
    # health basics
    "sağlık", "hastalık", "ağrı", "ilaç", "reçete",
    # home items
    "sabun", "havlu", "ayna", "koltuk", "raf", "çanta", "kalem",
    "defter", "sözlük",
    # misc
    "manzara", "mevsim", "şarkı", "oyun", "ders", "sınıf",
    "müzisyen", "ressam", "yazar", "şef", "avukat", "mühendis",
    # adjectives not in A1
    "hoş", "sevimli", "ilginç", "meşgul", "yorgun", "mutlu",
    "üzgün", "korkmuş", "heyecanlı", "sakin", "rahat",
    "zor", "kolay", "önemli", "faydalı", "gerekli",
    "mümkün", "imkansız", "doğru", "yanlış", "aynı", "farklı",
    "sıradan", "özel", "normal", "sağlıklı", "hasta",
    "taze", "ağır", "hafif", "geniş", "dar",
    "temiz", "kirli", "dolu", "boş", "açık", "kapalı",
    "pembe", "lacivert",
})

_TR_B1: frozenset[str] = frozenset({
    # verbs
    "geliştirmek", "iyileştirmek", "etkilemek",
    "organize etmek", "ilgilenmek", "tarif etmek", "fark etmek", "belirtmek",
    "açıklamak", "karşılaştırmak", "analiz etmek",
    "başarıya ulaşmak", "başarısız olmak", "karar vermek",
    "kabul etmek", "reddetmek", "önermek", "yönetmek",
    "kontrol etmek", "araştırmak", "bildirmek", "yayımlamak",
    "duyurmak", "oluşturmak", "bağlanmak", "birleşmek",
    "değişmek", "büyümek", "güçlendirmek", "zayıflamak",
    # society / politics
    "toplum", "hükümet", "siyaset", "seçim",
    "kanun", "hukuk", "ekonomi", "bütçe", "vergi",
    "emeklilik", "sosyal yardımlar", "askerlik",
    # environment
    "çevre", "kirlilik", "iklim değişikliği", "geri dönüşüm",
    "enerji tüketimi", "doğal kaynaklar", "koruma",
    # abstract nouns
    "düşünce", "görüş", "anlayış", "değer", "ilke",
    "hedef", "hayal", "çözüm", "sonuç", "değişim",
    "büyüme", "gelişme", "ilerleme", "zorluk", "risk",
    "fırsat", "tehdit", "etki", "tutum", "motivasyon",
    "beceri", "yetenek", "yapı", "norm",
    # work / business
    "şirket", "kuruluş", "lider", "müdür", "uzman",
    "deneyim", "eğitim", "kariyer", "maaş",
    "sözleşme", "müzakere", "proje", "görev", "sorumluluk",
    # communication / relations
    "iletişim", "işbirliği", "ilişki", "güven", "destek",
    "çatışma", "karar", "öneri",
    # health (intermediate)
    "sağlık hizmetleri", "tanı", "tedavi", "ameliyat", "iyileşme",
    "stres", "tükenmişlik", "ruh sağlığı", "rehabilitasyon",
    # culture / arts
    "edebiyat", "şiir", "belgesel",
    "eleştiri", "inceleme", "eser", "sergi",
    # science / technology
    "araştırma", "bilim", "teknoloji", "yapay zeka", "dijitalleşme",
    "programlama", "veri",
    # education
    "diploma", "akademi", "seminer", "tez",
    # adjectives
    "temel", "merkezi", "zorunlu",
    "etkili", "sürdürülebilir", "mevcut",
    "tarihsel", "uluslararası", "ulusal", "bölgesel",
    "yerel", "kamusal", "siyasi",
    "sosyal", "ekonomik", "teknolojik", "bilimsel",
    "kültürel", "sanatsal", "mesleki", "kişisel",
    "genel", "somut", "soyut", "karmaşık",
    "basit", "ciddi", "kritik",
    "aktif", "pasif", "bağımsız", "sorumlu",
    "güvenilir", "belirsiz",
    # extra nouns to reach 200
    "amaç", "hedef", "ilerleme", "reform", "kriz",
    "süreç", "yöntem", "faktör",
    "gelir", "harcama", "kaynak", "yatırım", "büyüme",
    "rekabet", "strateji", "politika", "model",
    "nüfus", "istatistik", "rapor", "analiz", "sonuç",
    "başarı", "başarısızlık", "fırsat", "zorluk", "çözüm",
    "olanak", "sınırlama", "önlem", "etken",
    "bağlantı", "etkileşim", "katılım", "yenilik", "standart",
    "itibar", "baskı", "koordinasyon", "denge", "etkinlik", "kapsamlı",
    "makale", "bölüm", "örnek", "yaklaşım", "davranış",
    "alan", "durum", "koşul", "düzey",
})

_TR_B2: frozenset[str] = frozenset({
    # verbs (academic / formal)
    "önceliklendirmek", "koordine etmek", "kolaylaştırmak", "optimize etmek",
    "standartlaştırmak", "sorgulamak", "meşrulaştırmak",
    "entegre etmek", "modernize etmek", "kavramsallaştırmak",
    "sistematize etmek", "değerlendirmek", "uygulayabilmek",
    # nouns (institutional / academic)
    "mevzuat", "yargı", "demokrasi", "otokrasi",
    "bürokratizm", "altyapı", "kurum", "mekanizma",
    "paradigma", "hiyerarşi", "konsensüs", "uzlaşma",
    "ikilem", "bağlam", "perspektif", "boyut", "yön",
    "olgu", "söylem", "retorik", "anlatı", "ideoloji",
    "ekosistem", "biyoçeşitlilik", "esneklik",
    "dönüşüm", "inovasyon", "aksaklık",
    "kapasite", "yetkinlik", "meşruiyet", "şeffaflık",
    # adjectives
    "pragmatik", "stratejik", "sistematik", "hiyerarşik",
    "kurumsal", "bürokratik", "demokratik",
    "otoriter", "liberal", "muhafazakar", "ilerici",
    "disiplinlerarası", "bütüncül",
    "tutarlı", "tutarsız", "örtük",
    "normatif", "betimleyici", "metodolojik", "rasyonel", "sistematik",
})

_TR_C1: frozenset[str] = frozenset({
    # verbs
    "açımlamak", "kurmak", "yapısökmek", "sorunsallaştırmak",
    "bağlamsallaştırmak", "somutlaştırmak", "işlevselleştirmek",
    "yeniden kurmak", "nesneleştirmek", "araçsallaştırmak",
    # nouns
    "epistemoloji", "metodoloji", "ontoloji", "aksiyoloji",
    "hermeneutik", "fenomenoloji", "teleoloji", "diyalektik",
    "özgürleşme", "hegemonya", "öznelerarasılık",
    "temsil", "anlamlandırma", "çağrışım", "gönderim",
    "göstergebilim", "metinlerarasılık", "çoğul seslilik",
    "bağdaşıklık", "artgönderim", "belirsizlik",
    "paradoks", "çıkmaz", "çelişki", "tekrarsöz",
    "bilgi", "mantık merkezcilik", "öznellik",
    "nesnellik", "dile getirme",
    # adjectives
    "epistemik", "ontolojik", "aksiyolojik", "teleolojik",
    "diyalektik", "hermenötik", "fenomenolojik",
    "özgürleştirici", "hegemonik", "öznelerarası",
    "muğlak", "paradoksal", "söylemsel",
    "metinlerarası", "çoğuldisiplinli", "mantık merkezci",
    "çığır açıcı", "dönüştürücü",
})

_TR_C2: frozenset[str] = frozenset({
    # nouns (rhetoric / literary theory)
    "anakoluton", "zeugma", "sillepsis", "antistasis",
    "anadiplosis", "epistrophe", "khiasmos", "litotes",
    "prosopopeia", "ekphrasis", "diegesis", "mimesis",
    "katharsis", "anagnorisis", "hamartia", "hybris",
    "nemesis", "peripeteia", "eudaimonia", "ataraxia",
    "apatheia", "parrhesia", "arete", "phronesis", "kairos",
    "apophasis", "polyptoton", "antanaklasis", "epiphora",
    "anaphora",
    # archaic / rare Turkish nouns
    "mükalemât", "münakaşa", "mütalaa", "mülahaza", "iddia",
    "müdahale", "müdavele", "münasebet", "mutabakat",
    "mütalaasızlık", "müracaat", "müzaharet",
    "tefekkür", "tezahür", "tecellî", "teşekkül",
    "istikbal", "istidlâl", "istikamet",
    "mazhar", "müktesep", "mükemmeliyet",
    "hakikat", "hakimiyet", "hilkat",
    "ibret", "idrak", "ihata",
    "kemal", "kemalist", "müfrit",
})

# ── Hindi (hi) ────────────────────────────────────────────────────────────────
# Lemma conventions: stanza Devanagari lemmas.
# Verbs → infinitive (जाना, करना); Nouns/Adj → base form (घर, अच्छा).
_HI_A1: frozenset[str] = frozenset({
    # core verbs
    "जाना", "आना", "करना", "होना", "देना", "लेना", "बोलना",
    "देखना", "सुनना", "खाना", "पीना", "पढ़ना", "लिखना", "सोना",
    "जानना", "समझना", "पूछना", "चाहना", "मिलना",
    # family / people
    "माँ", "पिता", "बच्चा", "लड़की", "लड़का", "दोस्त", "परिवार",
    "आदमी", "औरत",
    # home / school / objects
    "घर", "किताब", "स्कूल", "पैसा", "फोन",
    # transport
    "कार", "बस", "ट्रेन",
    # animals
    "कुत्ता", "बिल्ली",
    # food / drink
    "पानी", "रोटी", "चाय", "दूध",
    # time
    "नाम", "साल", "दिन", "हफ्ता", "महीना", "सुबह", "शाम", "रात",
    # nature / geography
    "सूरज", "बर्फ", "देश", "शहर", "सड़क", "दुकान",
    # adjectives
    "अच्छा", "बुरा", "बड़ा", "छोटा", "नया", "पुराना", "जवान",
    "सुंदर", "तेज़", "धीमा", "महंगा", "सस्ता", "लंबा", "ठंडा", "गर्म",
    # numbers
    "एक", "दो", "तीन", "चार", "पाँच", "छह", "सात", "आठ", "नौ",
    "दस", "सौ", "हजार",
    # weekdays
    "सोमवार", "मंगलवार", "बुधवार", "गुरुवार", "शुक्रवार",
    "शनिवार", "रविवार",
    # basic colours
    "लाल", "नीला", "हरा", "पीला", "काला", "सफेद", "भूरा",
})

_HI_A2: frozenset[str] = frozenset({
    # verbs not in A1
    "रहना", "चलना", "खेलना", "सीखना", "पहनना", "लाना",
    "खरीदना", "बेचना", "भेजना", "ढूंढना", "खोलना", "बंद करना",
    "हँसना", "रोना", "डरना", "पहुँचना", "बैठना", "उठना",
    "पकड़ना", "छोड़ना", "बचाना", "बनाना", "चुनना", "जीतना",
    "हारना", "गाना", "नाचना", "दौड़ना", "तैरना", "उड़ना",
    "पकाना", "धोना", "सुधारना", "रुकना", "बदलना", "सोचना",
    "भूलना", "डालना", "निकालना", "चढ़ना", "उतरना",
    # seasons / weather
    "दोपहर", "वसंत", "गर्मी", "पतझड़", "सर्दी", "बादल",
    "बारिश", "हवा", "तापमान", "धूप", "कोहरा",
    # nature / terrain / animals
    "झील", "नदी", "समुद्र", "पहाड़", "जंगल", "खेत", "बगीचा",
    "पेड़", "पत्ता", "जानवर", "पक्षी", "घोड़ा", "गाय", "बकरी",
    "बंदर", "शेर", "हाथी",
    # travel
    "यात्रा", "उड़ान", "टिकट", "पासपोर्ट", "बैग",
    # clothing
    "कमीज़", "पैंट", "कोट", "जूता", "टोपी", "मफलर",
    # occupations
    "पेशा", "डॉक्टर", "नर्स", "टीचर",
    # media / culture
    "अखबार", "टेलीविजन", "रेडियो", "फिल्म", "संगीत",
    "नृत्य", "खेल", "फोटो", "चित्र", "कला", "संग्रहालय",
    "थिएटर", "शौक",
    # celebrations
    "जन्मदिन", "त्योहार", "उपहार", "फूल", "केक",
    # technology
    "ईमेल", "इंटरनेट", "कंप्यूटर", "मोबाइल", "एप्लिकेशन",
    # food extended
    "सब्जी", "फल", "मांस", "मछली", "मुर्गी", "अंडा", "पनीर",
    "आलू", "टमाटर", "सेब", "संतरा", "केला", "स्ट्रॉबेरी",
    "चावल", "पास्ता",
    # home rooms / housing
    "रसोई", "बैठक", "शयनकक्ष", "बाथरूम", "बालकनी",
    "पड़ोसी", "मकान", "किराया", "अपार्टमेंट",
    # services / buildings
    "रेस्तरां", "कैफे", "होटल", "हवाई अड्डा", "रेलवे स्टेशन",
    "दवाई की दुकान", "बैंक", "डाकघर", "पुस्तकालय",
    "अस्पताल", "विश्वविद्यालय", "कार्यालय",
    # health basics
    "स्वास्थ्य", "बीमारी", "दर्द", "दवा", "नुस्खा",
    # misc nouns
    "शब्द", "भाषा", "प्रश्न", "उत्तर", "विचार",
    # body parts
    "सिर", "हाथ", "पैर", "आँख", "कान", "नाक", "मुँह", "दाँत", "बाल", "पेट", "गला", "पीठ",
    # more food
    "दाल", "चपाती", "सलाद",
    # more places
    "मंदिर", "मस्जिद", "बाज़ार",
    # adjectives not in A1
    "प्यारा", "मज़ेदार", "दिलचस्प", "थका", "खुश", "दुखी",
    "उत्साहित", "शांत", "व्यस्त", "स्वादिष्ट", "ज़रूरी",
    "आसान", "कठिन", "सही", "गलत", "साफ", "गंदा",
    "भारी", "हल्का", "चौड़ा", "संकरा", "गीला", "सूखा",
    "ताज़ा", "खुला", "बंद",
    # extra colours
    "नारंगी", "गुलाबी", "बैंगनी",
})

_HI_B1: frozenset[str] = frozenset({
    # verbs
    "उभरना", "जुड़ना", "टूटना", "बिगड़ना", "बढ़ना", "फैलना",
    "झुकना", "उलझना", "खिलना", "मुरझाना", "जगाना",
    "पहचानना", "मनाना", "जांचना", "नकारना", "स्वीकारना",
    "संभालना", "प्रभावित करना", "शामिल होना", "नेतृत्व करना",
    "व्यवस्थित करना", "घोषणा करना", "प्रकाशित करना",
    "रिपोर्ट करना", "विश्लेषण करना", "मूल्यांकन करना",
    "योजना बनाना", "लागू करना", "हासिल करना",
    "सुझाव देना", "प्रबंधन करना",
    # society / politics
    "समाज", "सरकार", "राजनीति", "चुनाव",
    "कानून", "न्याय", "अर्थव्यवस्था", "बजट", "कर",
    "सेवानिवृत्ति", "सामाजिक सेवाएं", "पुलिस", "सेना",
    # environment
    "पर्यावरण", "प्रदूषण", "जलवायु परिवर्तन", "पुनर्चक्रण",
    "ऊर्जा खपत", "प्राकृतिक संसाधन", "संरक्षण",
    # abstract nouns
    "राय", "समझ", "मूल्य", "सिद्धांत",
    "लक्ष्य", "सपना", "समाधान", "परिणाम",
    "परिवर्तन", "प्रगति", "चुनौती", "खतरा",
    "संभावना", "प्रभाव", "रुचि", "प्रेरणा",
    "दृष्टिकोण", "रवैया", "योग्यता",
    # work / business
    "कंपनी", "संगठन", "नेता", "प्रबंधक", "विशेषज्ञ",
    "अनुभव", "कौशल", "शिक्षा", "करियर", "वेतन",
    "अनुबंध", "वार्ता", "परियोजना", "कार्य", "जिम्मेदारी",
    # communication / relations
    "संचार", "सहयोग", "संबंध", "विश्वास", "समर्थन",
    "संघर्ष", "निर्णय", "प्रस्ताव",
    # health (intermediate)
    "स्वास्थ्य सेवा", "निदान", "उपचार", "ऑपरेशन", "रिकवरी",
    "तनाव", "थकान", "मानसिक स्वास्थ्य", "पुनर्वास",
    # culture / arts
    "साहित्य", "कविता", "नाटक", "दस्तावेज़",
    "समीक्षा", "रचना", "प्रदर्शनी",
    # science / technology
    "अनुसंधान", "विज्ञान", "प्रौद्योगिकी", "कृत्रिम बुद्धिमत्ता",
    "डिजिटलीकरण", "प्रोग्रामिंग", "डेटा",
    # education
    "डिग्री", "पाठ्यक्रम", "संगोष्ठी", "शोध प्रबंध",
    "परीक्षा", "छात्रवृत्ति",
    # extra verbs
    "मानना", "जोड़ना", "घटाना", "समझाना", "सिखाना",
    "बुलाना", "लौटना", "रोकना", "हटाना", "दर्शाना",
    # society / geography
    "राजधानी", "राज्य", "पड़ोस", "नागरिक", "जनसंख्या",
    "समुदाय", "वर्ग", "पीढ़ी",
    # economy / work
    "व्यापार", "उद्योग", "उत्पादन", "निर्यात", "आयात",
    "रोजगार", "बेरोजगारी",
    # media / communication
    "समाचार", "पत्रकारिता", "विज्ञापन", "प्रचार",
    # culture / transport
    "संस्कृति", "वाहन", "परिवहन", "यातायात", "सुविधा",
    # health / wellness
    "योग", "ध्यान", "व्यायाम", "आहार",
    # adjectives
    "महत्वपूर्ण", "आवश्यक", "केंद्रीय", "अनिवार्य",
    "प्रभावी", "टिकाऊ", "वर्तमान", "ऐतिहासिक",
    "अंतरराष्ट्रीय", "राष्ट्रीय", "क्षेत्रीय",
    "सार्वजनिक", "निजी", "राजनीतिक",
    "सामाजिक", "आर्थिक", "वैज्ञानिक",
    "सांस्कृतिक", "व्यावसायिक", "व्यक्तिगत",
    "सामान्य", "जटिल", "सरल", "गंभीर",
    "सक्रिय", "स्वतंत्र", "जिम्मेदार",
    "विश्वसनीय", "अनिश्चित",
    "नैतिक", "सामूहिक", "व्यापक", "संभावित",
    "अस्थायी", "स्थायी", "क्रमिक", "अचानक",
    "प्रत्यक्ष", "सक्षम",
    "गतिविधि",
})

_HI_B2: frozenset[str] = frozenset({
    # verbs (academic / formal)
    "प्राथमिकता देना", "समन्वय करना", "सुगम बनाना", "अनुकूलित करना",
    "मानकीकृत करना", "प्रश्न उठाना", "वैधता प्रदान करना",
    "एकीकृत करना", "आधुनिकीकरण करना", "अवधारणाओं को परिभाषित करना",
    "संहिताबद्ध करना", "औपचारिकीकरण करना",
    # nouns (institutional / academic)
    "विधान", "न्यायपालिका", "लोकतंत्र", "निरंकुशता",
    "नौकरशाही", "बुनियादी ढांचा", "संस्था", "तंत्र",
    "प्रतिमान", "पदानुक्रम", "सहमति", "समझौता",
    "दुविधा", "संदर्भ", "परिप्रेक्ष्य", "आयाम", "पहलू",
    "प्रवचन", "अलंकारशास्त्र", "आख्यान", "विचारधारा",
    "पारिस्थितिक तंत्र", "जैव विविधता", "लचीलापन",
    "रूपांतरण", "नवाचार", "व्यवधान",
    "क्षमता", "दक्षता", "वैधता", "पारदर्शिता",
    # adjectives
    "व्यावहारिक", "रणनीतिक", "व्यवस्थित", "श्रेणीबद्ध",
    "संस्थागत", "नौकरशाही", "लोकतांत्रिक",
    "सत्तावादी", "उदार", "रूढ़िवादी", "प्रगतिशील",
    "अंतःविषय", "समग्र",
    "सुसंगत", "असंगत", "अंतर्निहित", "स्पष्ट",
    "मानदंड", "वर्णनात्मक", "पद्धतिगत", "तर्कसंगत",
})

_HI_C1: frozenset[str] = frozenset({
    # nouns (philosophical / analytical)
    "ज्ञानमीमांसा", "प्रणालीशास्त्र", "सत्तामीमांसा", "मूल्यमीमांसा",
    "व्याख्याशास्त्र", "परिघटनाविज्ञान", "द्वंद्ववाद",
    "उत्तर-संरचनावाद", "मुक्तिशास्त्र", "आधिपत्य",
    "पारस्परिक-व्यक्तिपरकता", "प्रतिनिधित्व", "अर्थीकरण",
    "अर्थव्यंजना", "सांकेतिकता", "पाठांतरता",
    "बहुस्वरता", "अस्पष्टता", "विरोधाभास",
    "अपोरिया", "प्रतिविरोध", "पुनरावृत्ति",
    "ज्ञान-केंद्रवाद", "व्यक्तिपरकता", "वस्तुनिष्ठता",
    "अंतर्विरोध", "तार्किकता", "सार्वभौमिकता",
    "विशिष्टता", "प्रासंगिकता",
    # adjectives
    "ज्ञानमीमांसीय", "सत्तामीमांसीय", "मूल्यमीमांसीय", "दूरदर्शी",
    "द्वंद्वात्मक", "व्याख्याशास्त्रीय", "परिघटनावैज्ञानिक",
    "मुक्तिकारी", "आधिपत्यवादी", "पारस्परिक",
    "अस्पष्ट", "विरोधाभासी", "प्रवचनात्मक",
    "पाठांतरात्मक", "बहुअनुशासनीय", "तार्किक-केंद्रवादी",
    "युगांतरकारी", "रूपांतरणशील", "अन्वेषणशील",
    "परावर्तनशील", "आत्म-संदर्भात्मक", "संरचनात्मक",
    "अंतर्विरोधी", "पुनर्विचारशील", "समालोचनात्मक",
})

_HI_C2: frozenset[str] = frozenset({
    # nouns (rhetoric / literary theory / very rare)
    "अनाकोलुथन", "ज़ेउग्मा", "सिल्लेप्सिस", "अन्तिस्तासिस",
    "अनाडिप्लोसिस", "एपिस्ट्रोफ़े", "काइस्मस", "लिटोटेस",
    "प्रोसोपोपोइया", "एकफ़्रेसिस", "डाइजेसिस", "माइमेसिस",
    "कैथार्सिस", "अनग्नोरिसिस", "हमार्टिया", "हाइब्रिस",
    "नेमेसिस", "पेरिपेटिया", "यूडाइमोनिया", "अटारैक्सिया",
    "अपाथिया", "पैरहेसिया", "अरेते", "फ्रोनेसिस", "काइरोस",
    "अपोफ़ेसिस", "पॉलिप्टोटोन", "अन्तानाक्लासिस",
    # archaic / rare Hindi nouns
    "आत्मग्लानि", "विषाद", "वैराग्य", "तृष्णा", "निर्वेद",
    "क्षोभ", "विस्मय", "अवसाद", "उत्कंठा", "लालसा",
    "श्रद्धा", "भक्ति", "वैभव", "परमार्थ", "अध्यात्म",
    "अहंकार", "माया", "मोह", "क्रोध", "लोभ",
    "अनित्यता", "शाश्वतता", "पुनर्जन्म", "कर्मफल",
    # archaic / rare adjectives
    "विषादग्रस्त", "वैरागी", "अध्यात्मिक", "परमार्थी",
    "अहंकारी", "मोहग्रस्त", "क्रोधी", "लोभी",
    "श्रद्धावान", "भक्तिमान",
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
    "fi": _FI_A1,
    "tr": _TR_A1,
    "hi": _HI_A1,
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
    "fi": _FI_A2,
    "tr": _TR_A2,
    "hi": _HI_A2,
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
    "opinión", "situación", "solución", "relación",
    "oportunidad", "decisión", "razón", "detalle", "hecho",
    "diferencia", "desarrollo", "efecto", "ventaja",
    "desventaja", "propósito", "valor", "papel", "calidad", "método", "nivel", "atención", "esfuerzo",
    "posibilidad", "responsabilidad", "importancia", "aspecto",
    "causa", "condición", "dificultad", "evidencia",
    "función", "influencia", "asunto", "conocimiento",
    "límite", "pérdida", "significado", "necesidad", "período",
    "presión", "principio", "progreso", "tasa", "sentido",
    "etapa", "estructura", "sistema", "término", "afirmación", "análisis", "crítica", "alternativa", "consecuencia",
    "suposición", "argumento",
    # opinions & debate
    "debate", "discusión", "punto de vista", "juicio",
    "recomendación", "evaluación", "acuerdo", "desacuerdo",
    # work & professional (B1 depth)
    "presentación", "solicitud", "entrevista", "departamento",
    "habilidad", "calificación", "formación", "estrategia", "presupuesto", "beneficio", "colaboración", "desempeño", "logro", "capacitación", "liderazgo",
    # news & current affairs
    "anuncio", "elección", "conflicto",
    "acontecimiento", "crisis", "desafío", "protesta", "campaña", "política", "gobierno", "sociedad", "economía",
    "estadística", "encuesta", "titular", "fuente", "cobertura",
    "declaración", "acuerdo internacional", "tratado",
    # technology & digital (B1 depth)
    "software", "dispositivo", "red", "datos", "seguridad",
    "privacidad", "plataforma", "programa", "interfaz",
    "usuario", "base de datos", "almacenamiento", "actualización",
    "aplicación móvil", "inteligencia artificial", "automatización",
    # health & medicine (extended)
    "tratamiento", "síntoma", "terapia",
    "rehabilitación", "vacuna", "antibiótico", "especialista",
    "dosis", "efecto secundario", "prevención", "cronicidad",
    "bienestar mental", "estrés", "burnout",
    # environment & sustainability
    "clima", "medio ambiente", "contaminación", "recurso natural", "especie", "hábitat", "emisión",
    "huella de carbono", "biodiversidad", "sequía", "inundación",
    "deforestación", "calentamiento global", "reciclable",
    "residuo", "impacto ambiental", "energía solar",
    "energía eólica", "panel solar", "transición energética",
    # education & learning (B1 depth)
    "investigación", "tesis", "beca",
    "taller", "seminario", "academia", "matrícula", "resultado académico",
    "aprendizaje autónomo", "competencia",
    # social issues & society
    "igualdad", "inclusión", "discriminación",
    "prejuicio", "pobreza", "justicia",
    "derechos", "obligación", "migración", "refugiado", "comunidad", "voluntariado",
    "solidaridad", "bienestar", "cohesión social", "tolerancia",
    "equidad", "marginación", "exclusión", "accesibilidad",
    # extended abstract adjectives
    "complejo", "sencillo", "general", "específico", "particular",
    "cierto", "evidente", "normal", "original", "reciente",
    "grave", "similar", "típico", "variado", "eficiente", "flexible", "creativo", "crítico",
    "lógico", "abstracto", "concreto", "notable", "considerable", "excepcional",
    "moderado", "intenso", "permanente", "temporal", "global",
    "nacional", "internacional", "público", "privado",
    "oficial", "formal", "informal", "inevitable",
    "razonable", "adecuado", "insuficiente", "excesivo",
    # extended verbs (cognitive & communicative)
    "considerar", "analizar", "argumentar", "dudar", "reconocer", "percibir",
    "reflexionar", "evaluar", "demostrar",
    "comprobar", "resolver", "adaptar", "contribuir", "participar",
    "colaborar", "comunicar", "negociar", "coordinar", "establecer", "determinar", "supervisar", "apoyar",
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
    "opinion", "situation", "relation",
    "opportunité", "décision", "raison", "détail", "fait",
    "différence", "changement", "développement", "effet", "avantage",
    "inconvénient", "valeur", "rôle", "qualité", "méthode", "niveau", "attention", "effort",
    "possibilité", "importance", "aspect",
    "cause", "condition", "contexte", "difficulté", "preuve",
    "fonction", "influence", "connaissance",
    "limite", "perte", "signification", "besoin", "période",
    "pression", "principe", "progrès", "sens",
    "étape", "structure", "système", "terme", "conclusion", "affirmation", "analyse", "critique",
    "proposition", "alternative", "conséquence",
    "supposition", "argument",
    # opinions & debate
    "débat", "discussion", "point de vue", "jugement",
    "recommandation", "évaluation", "accord", "désaccord",
    # work & professional (B1 depth)
    "présentation", "candidature", "entretien", "département",
    "compétence", "qualification", "formation", "stratégie", "budget", "bénéfice", "ressource",
    "collaboration", "performance", "réalisation",
    "retour d'information", "leadership",
    # news & current affairs
    "annonce", "élection", "conflit",
    "événement", "crise", "défi", "manifestation", "campagne", "politique", "société", "économie",
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
    "atelier", "séminaire", "institution",
    "académie", "inscription", "résultat scolaire",
    "apprentissage autonome", "compétence",
    # social issues & society
    "égalité", "diversité", "inclusion", "discrimination",
    "préjugé", "pauvreté", "justice",
    "droits", "obligation", "citoyenneté", "migration", "réfugié", "communauté", "bénévolat",
    "solidarité", "bien-être", "cohésion sociale", "tolérance", "marginalisation", "exclusion", "accessibilité",
    # extended abstract adjectives
    "complexe", "simple", "général", "spécifique", "particulier",
    "certain", "évident", "normal", "original", "récent",
    "grave", "similaire", "typique", "varié", "flexible", "créatif", "critique", "logique",
    "abstrait", "concret", "fondamental", "notable", "considérable", "modéré", "intense", "permanent", "temporaire", "mondial",
    "national", "international", "officiel", "formel", "informel", "inévitable", "raisonnable", "adéquat",
    "insuffisant", "excessif",
    # extended verbs (cognitive & communicative)
    "considérer", "analyser", "débattre",
    "argumenter", "douter", "reconnaître", "percevoir",
    "réfléchir", "démontrer", "résoudre", "mettre en œuvre",
    "adapter", "contribuer", "participer",
    "collaborer", "communiquer", "négocier", "coordonner", "établir", "déterminer", "superviser", "défendre",
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
    "Nachteil", "Zweck", "Wert", "Rolle", "Qualität", "Methode", "Niveau", "Aufmerksamkeit", "Anstrengung",
    "Möglichkeit", "Wichtigkeit", "Aspekt",
    "Ursache", "Bedingung", "Schwierigkeit", "Beweis",
    "Funktion", "Auswirkung", "Einfluss", "Angelegenheit", "Wissen",
    "Grenze", "Verlust", "Bedeutung", "Bedürfnis", "Zeitraum",
    "Druck", "Grundsatz", "Fortschritt", "Sinn",
    "Stufe", "System", "Begriff", "Schlussfolgerung", "Aussage", "Analyse", "Kritik",
    "Vorschlag", "Alternative", "Annahme", "Argument",
    # debate & opinion nouns
    "Debatte", "Diskussion", "Standpunkt", "Urteil", "Einigkeit", "Meinungsverschiedenheit",
    # work & professional nouns (B1 depth)
    "Präsentation", "Bewerbung", "Vorstellungsgespräch", "Abteilung",
    "Fähigkeit", "Qualifikation", "Ausbildung", "Ziel", "Budget", "Nutzen", "Zusammenarbeit", "Leistung", "Führung", "Rückmeldung",
    # news & current affairs nouns
    "Ankündigung", "Wahl", "Konflikt",
    "Ereignis", "Krise", "Protest", "Reform",
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
    "Klima", "Umwelt", "Verschmutzung", "Art", "Lebensraum", "Emission", "Biodiversität",
    "Dürre", "Überschwemmung", "Abholzung", "Klimawandel",
    "Abfall", "Solarenergie", "Windenergie",
    # education nouns
    "Forschung", "These", "Stipendium", "Konferenz",
    "Workshop", "Seminar", "Institution",
    "Akademie", "Einschreibung", # social issues nouns
    "Gleichheit", "Vielfalt", "Inklusion", "Diskriminierung",
    "Vorurteil", "Armut", "Ungerechtigkeit", "Gerechtigkeit",
    "Pflicht", "Staatsbürgerschaft", "Migration", "Flüchtling", "Gemeinschaft", "Ehrenamt",
    "Solidarität", "Wohlbefinden", "Toleranz", "Zugänglichkeit",
    # abstract adjectives (lowercase) "allgemein", "spezifisch",
    "offensichtlich", "ursprünglich",
    "ähnlich", "typisch", "vielfältig", "wirksam", "flexibel", "innovativ", "kreativ",
    "kritisch", "logisch", "abstrakt", "konkret",
    "grundlegend", "bedeutsam", "bemerkenswert",
    "erheblich", "außergewöhnlich", "gemäßigt", "intensiv",
    "dauerhaft", "vorübergehend", "global", "lokal",
    "öffentlich", "privat", "offiziell", "formell", "informell",
    "dringend", "unvermeidlich", "unzureichend",
    # verbs (lowercase)
    "betrachten", "analysieren", "debattieren",
    "argumentieren", "zweifeln", "wahrnehmen",
    "nachdenken", "bewerten", "beweisen", "untersuchen", "lösen", "umsetzen",
    "anpassen", "beitragen", "teilnehmen",
    "verhandeln", "verwalten", "feststellen",
    "bestimmen", "beaufsichtigen", "fördern",
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
    "opinione", "situazione", "relazione",
    "opportunità", "ragione", "dettaglio", "fatto",
    "differenza", "cambiamento", "sviluppo", "effetto", "vantaggio",
    "svantaggio", "scopo", "valore", "ruolo", "qualità", "metodo", "livello", "attenzione", "sforzo",
    "possibilità", "importanza", "aspetto",
    "causa", "condizione", "contesto", "difficoltà", "prova", "questione", "conoscenza",
    "limite", "perdita", "significato", "necessità", "periodo",
    "pressione", "principio", "progresso", "senso",
    "fase", "struttura", "sistema", "termine", "prospettiva", "affermazione", "analisi", "critica",
    "proposta", "alternativa", "argomento",
    # opinions & debate
    "dibattito", "discussione", "punto di vista", "giudizio",
    "raccomandazione", "valutazione", "accordo", "disaccordo",
    # work & professional (B1 depth)
    "presentazione", "candidatura", "colloquio", "dipartimento",
    "abilità", "qualificazione", "formazione", "strategia", "budget", "beneficio", "risorsa",
    "collaborazione", "prestazione", "leadership",
    "retroazione", "capacità",
    # news & current affairs
    "annuncio", "elezione", "conflitto",
    "evento", "crisi", "sfida", "protesta", "campagna", "politica", "governo", "società", "economia",
    "statistica", "sondaggio", "fonte", "trattato",
    # technology & digital (B1 depth)
    "software", "dispositivo", "rete", "dati", "sicurezza",
    "privacy", "piattaforma", "interfaccia",
    "utente", "database", "archiviazione", "aggiornamento",
    "intelligenza artificiale", "automazione",
    # health & medicine (extended)
    "trattamento", "sintomo", "terapia",
    "riabilitazione", "vaccino", "antibiotico", "specialista",
    "dose", "effetto collaterale", "prevenzione", "burnout",
    # environment & sustainability
    "clima", "ambiente", "inquinamento", "risorsa naturale", "specie", "habitat", "emissione",
    "impronta di carbonio", "biodiversità", "siccità", "alluvione",
    "deforestazione", "cambiamento climatico", "riciclabile",
    "rifiuto", "impatto ambientale", "energia solare",
    "energia eolica", "transizione energetica",
    # education & learning (B1 depth)
    "ricerca", "tesi", "borsa di studio",
    "laboratorio", "seminario", "istituzione",
    "accademia", "iscrizione", "competenza",
    "apprendimento autonomo",
    # social issues & society
    "uguaglianza", "inclusione", "discriminazione",
    "pregiudizio", "povertà", "disuguaglianza", "giustizia",
    "diritti", "obbligo", "cittadinanza", "migrazione", "rifugiato", "comunità", "volontariato",
    "solidarietà", "benessere", "coesione sociale", "tolleranza",
    "equità", "marginalizzazione", "esclusione", "accessibilità",
    # extended abstract adjectives
    "complesso", "semplice", "generale", "specifico", "particolare",
    "certo", "evidente", "normale", "originale", "recente",
    "simile", "tipico", "vario", "efficiente",
    "flessibile", "creativo", "critico", "logico",
    "astratto", "concreto", "notevole", "eccezionale",
    "moderato", "intenso", "permanente", "temporaneo", "globale",
    "nazionale", "internazionale", "ufficiale", "formale", "informale", "inevitabile", "ragionevole", "adeguato",
    "insufficiente", "eccessivo",
    # extended verbs (cognitive & communicative)
    "considerare", "analizzare", "dibattere", "dubitare", "riconoscere", "percepire",
    "riflettere", "valutare", "dimostrare", "risolvere", "adattare", "contribuire", "partecipare", "comunicare", "negoziare", "coordinare", "stabilire", "determinare", "supervisionare", "sostenere", "difendere",
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
    "opinião", "situação", "relação",
    "oportunidade", "razão", "detalhe", "facto",
    "diferença", "mudança", "desenvolvimento", "efeito", "vantagem",
    "desvantagem", "propósito", "valor", "papel", "qualidade", "método", "nível", "atenção", "esforço",
    "possibilidade", "importância", "aspeto",
    "causa", "condição", "dificuldade", "evidência",
    "função", "influência", "assunto", "conhecimento",
    "limite", "perda", "significado", "necessidade", "período",
    "pressão", "princípio", "progresso", "sentido",
    "fase", "estrutura", "sistema", "termo", "perspetiva", "afirmação", "análise", "crítica",
    "proposta", "alternativa", "consequência", "argumento",
    # opinions & debate
    "debate", "discussão", "ponto de vista", "julgamento",
    "recomendação", "avaliação", "acordo", "desacordo",
    # work & professional (B1 depth)
    "apresentação", "candidatura", "entrevista", "departamento",
    "habilidade", "qualificação", "formação", "estratégia", "orçamento", "benefício", "colaboração", "desempenho", "liderança",
    "feedback", # news & current affairs
    "anúncio", "eleição", "conflito",
    "evento", "crise", "desafio", "protesto", "campanha", "política", "governo", "sociedade", "economia",
    "estatística", "sondagem", "fonte", "tratado",
    # technology & digital (B1 depth)
    "software", "dispositivo", "rede", "dados", "segurança",
    "privacidade", "interface",
    "utilizador", "base de dados", "armazenamento", "atualização",
    "inteligência artificial", "automação",
    # health & medicine (extended)
    "tratamento", "sintoma", "terapia",
    "reabilitação", "vacina", "antibiótico", "especialista",
    "dose", "efeito secundário", "prevenção", "burnout",
    # environment & sustainability
    "clima", "ambiente", "poluição", "recurso natural", "espécie", "hábitat", "emissão",
    "pegada de carbono", "biodiversidade", "seca", "inundação",
    "desflorestação", "aquecimento global", "reciclável",
    "resíduo", "impacto ambiental", "energia solar",
    "energia eólica", "transição energética",
    # education & learning (B1 depth)
    "investigação", "dissertação", "bolsa",
    "oficina", "seminário", "instituição",
    "academia", "matrícula", "competência",
    "aprendizagem autónoma",
    # social issues & society
    "igualdade", "inclusão", "discriminação",
    "preconceito", "pobreza", "desigualdade", "justiça",
    "direitos", "obrigação", "cidadania", "migração", "refugiado", "comunidade", "voluntariado",
    "solidariedade", "bem-estar", "coesão social", "tolerância",
    "equidade", "marginalização", "exclusão", "acessibilidade",
    # extended abstract adjectives
    "complexo", "simples", "geral", "específico", "particular",
    "certo", "evidente", "normal", "original", "recente",
    "semelhante", "típico", "variado", "eficiente",
    "flexível", "criativo", "crítico", "lógico",
    "abstrato", "concreto", "notável", "excecional",
    "moderado", "intenso", "permanente", "temporário", "global",
    "nacional", "internacional", "oficial", "formal", "informal", "inevitável", "razoável", "adequado",
    "insuficiente", "excessivo",
    # extended verbs (cognitive & communicative)
    "considerar", "analisar", "debater",
    "argumentar", "duvidar", "reconhecer", "perceber",
    "refletir", "demonstrar", "resolver", "adaptar", "contribuir", "participar",
    "colaborar", "comunicar", "negociar", "coordenar", "estabelecer", "determinar", "supervisionar", "apoiar", "defender",
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
    "недостаток", "цель", "ценность", "роль", "качество", "метод", "уровень", "внимание", "усилие",
    "ответственность", "важность", "аспект",
    "условие", "трудность", "доказательство",
    "функция", "знание",
    "потеря", "смысл", "потребность", "период",
    "давление", "принцип", "прогресс",
    "этап", "структура", "система", "термин", "вывод", "утверждение", "анализ", "критика",
    "предложение", "альтернатива", "предположение", "аргумент",
    # opinions & debate
    "дискуссия", "обсуждение", "точка зрения", "суждение",
    "рекомендация", "согласие", "несогласие",
    # work & professional (B1 depth)
    "презентация", "заявка", "собеседование", "отдел",
    "навык", "квалификация", "обучение", "бюджет", "выгода", "сотрудничество", "производительность", "руководство",
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
    "климат", "окружающая среда", "загрязнение", "природный ресурс", "вид", "среда обитания", "выброс",
    "углеродный след", "биоразнообразие", "засуха", "наводнение",
    "вырубка лесов", "глобальное потепление", "перерабатываемый",
    "отходы", "экологическое воздействие", "солнечная энергия",
    "ветровая энергия",
    # education & learning (B1 depth) "диссертация", "стипендия", "конференция",
    "мастер-класс", "семинар", "учреждение",
    "академия", "компетентность",
    # social issues & society
    "равенство", "разнообразие", "включённость", "дискриминация",
    "предрассудок", "бедность", "неравенство", "справедливость",
    "права", "обязанность", "гражданство", "миграция", "беженец", "сообщество", "волонтёрство",
    "солидарность", "благополучие", "толерантность", "доступность",
    # extended abstract adjectives
    "сложный", "простой", "общий", "конкретный", "особый",
    "определённый", "очевидный", "нормальный", "оригинальный",
    "недавний", "похожий", "типичный", "разнообразный", "гибкий", "творческий", "логический", "абстрактный", "актуальный", "значимый", "заметный", "значительный",
    "исключительный", "умеренный", "интенсивный", "постоянный",
    "временный", "национальный", "международный",
    "официальный", "формальный", "неформальный",
    "срочный", "неизбежный", "разумный", "достаточный",
    # extended verbs (cognitive & communicative)
    "рассматривать", "дискутировать", "сомневаться",
    "признавать", "воспринимать", "размышлять", "доказывать", "разрешать", "внедрять",
    "адаптировать", "преобразовывать", "вносить вклад",
    "участвовать", "сотрудничать", "переговариваться",
    "управлять", "определять", "идентифицировать", "продвигать",
    "поддерживать", "подвергать сомнению",
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
    "違い", "変化", "発展", "利点",
    "欠点", "価値", "役割", "品質",
    "プロセス", "方法", "レベル", "注意", "努力",
    "可能性", "責任", "重要性", "原因", "困難", "機能", "損失", "意味", "必要性", "期間",
    "圧力", "進歩", "感覚",
    "段階", "構造", "システム", "用語", "主張", "批判",
    "提案", "代替案", "結果", # opinions & debate "討論", "勧告", "合意", "不一致",
    # work & professional (B1 depth)
    "プレゼンテーション", "申請", "面接", "部門",
    "スキル", "資格", "予算", "メリット", "リソース",
    "コラボレーション", "パフォーマンス", "リーダーシップ",
    "フィードバック", # news & current affairs
    "発表", "選挙", "紛争",
    "出来事", "危機", "抗議", "キャンペーン", "政治", "政府", "社会", "経済",
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
    # education & learning (B1 depth) "論文", "奨学金",
    "ワークショップ", "セミナー", "方法論", "機関",
    "アカデミー", "登録", # social issues & society
    "平等", "包括性", "差別",
    "偏見", "貧困", "不平等", "公正",
    "権利", "義務", "市民権", "移住", "難民", "コミュニティ", "ボランティア活動",
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
    # extended verbs (cognitive & communicative) "分析する", "解釈する", "議論する", "疑う", "認識する", "感知する",
    "反省する", "正当化する", "調査する", "適応する", "変革する", "参加する", "協力する", "交渉する",
    "管理する", "特定する",
    "監督する", "支持する", "反論する",
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
    "意见", "情况", "解决方案", "关系",
    "机会", "原因", "细节", "事实",
    "区别", "变化", "发展", "效果", "优势",
    "劣势", "价值", "作用", "过程", "方法", "层次", "注意力", "努力",
    "可能性", "责任", "重要性", "方面",
    "方向", "程度", "结合",
    "原因", "背景", "困难", "功能", "损失", "意义", "需求", "时期",
    "压力", "进步", "意义",
    "阶段", "术语", "理论", "主张", "批评",
    "提议", "替代方案", "论点",
    # opinions & debate
    "辩论", "讨论", "同意", "不同意",
    # work & professional (B1 depth)
    "演示", "申请", "面试", "部门",
    "技能", "资格", "培训", "战略", "预算", "收益", "资源", "领导力",
    "反馈", # news & current affairs
    "公告", "选举", "冲突",
    "事件", "危机", "抗议", "运动", "政策", "政府", "社会", "经济",
    "统计数据", "民意调查", "标题", "来源", "条约",
    # technology & digital (B1 depth)
    "软件", "设备", "隐私", "平台", "程序", "界面",
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
    # education & learning (B1 depth) "论文", "奖学金",
    "研讨会", "机构",
    "学院", "注册", # social issues & society
    "平等", "歧视",
    "偏见", "贫困", "不平等", "正义",
    "权利", "义务", "公民权", "移民", "难民", "社区", "志愿活动",
    "团结", "福祉", "宽容", "无障碍",
    # extended abstract adjectives
    "复杂", "简单", "一般", "特定",
    "明确", "正常", "独特", "近期",
    "严重", "相似", "典型", "多样", "有创意",
    "批判性", "合理的", "根本",
    "相关", "显著",
    "特殊", "温和", "激烈", "持久",
    "临时", "国际", "官方", "正式", "非正式",
    # extended verbs (cognitive & communicative)
    "考虑", "辩论", "怀疑", "承认", "感知",
    "反思", "核实", "执行", "适应", "转变", "谈判", "确立",
    "确定", "监督", "推广", "支持", "预防", "减少", "增加",
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
    "فرق", "تغيير", "تطور", "ميزة",
    "عيب", "قيمة", "دور", "أسلوب", "مستوى", "انتباه", "جهد", "مسؤولية", "أهمية", "جانب",
    "سبب", "شرط", "صعوبة", "وظيفة", "خسارة", "معنى", "حاجة", "مرحلة",
    "ضغط", "تقدم", "هيكل", "نظام", "مصطلح", "نظرية", "تصريح", "تحليل", "نقد",
    "مقترح", "بديل", "عواقب", "فرضية", "حجة",
    # opinions & debate
    "نقاش", "مناقشة", "وجهة نظر", "توصية", "تقييم", "اتفاق", "خلاف",
    # work & professional (B1 depth)
    "عرض تقديمي", "طلب", "مقابلة", "قسم",
    "مهارة", "تأهيل", "ميزانية", "فائدة", "مورد", "قيادة",
    "تغذية راجعة", # news & current affairs
    "إعلان", "انتخابات", "صراع",
    "حدث", "أزمة", "تحدي", "احتجاج", "حملة", "سياسة", "حكومة", "مجتمع", "اقتصاد",
    "إحصاء", "استطلاع", "مصدر", "معاهدة",
    # technology & digital (B1 depth)
    "جهاز", "شبكة", "أمان",
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
    "ورشة", "ندوة", "مؤسسة",
    "أكاديمية", "تسجيل", # social issues & society
    "مساواة", "تنوع", "تمييز",
    "تحيز", "فقر", "عدم مساواة", "عدالة",
    "جنسية", "اندماج",
    "هجرة", "لاجئ", "مجتمع", "تطوع",
    "تضامن", "رفاهية", "تسامح",
    # extended abstract adjectives
    "معقد", "بسيط", "محدد",
    "واضح", "طبيعي", "مشابه", "نموذجي", "متنوع",
    "فعال", "إبداعي",
    "نقدي", "مجرد", "أساسي",
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
    "הבדל", "התפתחות", "יתרון",
    "חיסרון", "ערך", "תפקיד", "תהליך", "שיטה", "רמה", "תשומת לב", "מאמץ",
    "אפשרות", "אחריות", "חשיבות", "היבט", "תנאי", "קושי", "תפקוד",
    "אובדן", "משמעות", "צורך", "תקופה",
    "לחץ", "התקדמות", "תחושה",
    "שלב", "מבנה", "מערכת", "מונח", "תיאוריה", "טענה", "ביקורת",
    "הצעה", "חלופה", "השלכה",
    "השערה", "טיעון",
    # opinions & debate
    "ויכוח", "דיון", "השקפה", "המלצה", "הערכה", "הסכמה", "אי הסכמה",
    # work & professional (B1 depth)
    "מצגת", "בקשה", "ראיון", "מחלקה",
    "כישרון", "כישורים", "הכשרה", "תקציב", "תועלת", "משאב",
    "שיתוף פעולה", "מנהיגות",
    "משוב", "יכולת",
    # news & current affairs
    "הכרזה", "בחירות", "סכסוך",
    "אירוע", "משבר", "מחאה", "קמפיין", "פוליטיקה", "ממשלה", "כלכלה",
    "נתונים סטטיסטיים", "סקר", "כותרת", "מקור", "הסכם",
    # technology & digital (B1 depth)
    "תוכנה", "מכשיר", "רשת", "אבטחה",
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
    "סדנה", "סמינר", "מוסד",
    "אקדמיה", "הרשמה", "כשירות",
    # social issues & society
    "שוויון", "הכלה", "אפליה",
    "דעה קדומה", "עוני", "אי שוויון", "צדק",
    "זכויות", "חובה", "אזרחות", "הגירה", "פליט", "קהילה", "התנדבות",
    "סולידריות", "רווחה", "סובלנות", "נגישות",
    # extended abstract adjectives
    "מורכב", "פשוט", "כללי", "ספציפי",
    "ברור", "רגיל", "מקורי",
    "חמור", "דומה", "טיפוסי", "מגוון",
    "יעיל", "יצירתי", "בסיסי",
    "רלוונטי", "משמעותי", "בולט", "יוצא דופן", "מתון", "עצים", "קבוע", "בינלאומי", "רשמי", "בלתי רשמי",
    # extended verbs (cognitive & communicative) "לפרש", "לטעון", "לפקפק", "להכיר", "לתפוס",
    "להרהר", "להצדיק", "לפתור", "לשנות", "לתרום", "להשתתף",
    "לשתף פעולה", "לתקשר", "לנהל משא ומתן", "לבסס", "לזהות",
    "לפקח", "לתמוך", "להגן", "להשפיע", "למנוע", "להפחית",
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
    "fi": _FI_B1,
    "tr": _TR_B1,
    "hi": _HI_B1,
}

# ──────────────────────────────────────────────────────────────────────────────
# B2 tables (upper-intermediate: ~270 lemmas / lang)
# Confidence 0.84 — only overrides OOV (tok.is_oov); below in-vocab (0.85)
# ──────────────────────────────────────────────────────────────────────────────

# ── Spanish B2 ────────────────────────────────────────────────────────────────
_ES_B2: frozenset[str] = frozenset({
    # verbs
    "acreditar", "aludir", "avalar", "carecer", "ceder",
    "conllevar", "corroborar", "deducir",
    "delimitar", "denunciar", "derivar", "descartar", "difundir",
    "discernir", "dilucidar", "elaborar", "emerger", "emprender",
    "encauzar", "exhibir", "financiar", "fomentar", "formular",
    "fluctuar", "fundamentar", "generar", "implicar", "impulsar", "incidir", "incurrir",
    "inferir", "instaurar", "integrar", "manejar", "mermar", "mitigar", "modificar",
    "obtener", "orientar", "plantear", "ponderar", "postular", "profundizar", "recabar", "reclamar",
    "reforzar", "registrar", "regular", "señalar", "sintetizar",
    "superar", "sustentar", "suscitar", "validar",
    "valorar", "vislumbrar",
    # nouns
    "arraigo", "auge", "bagaje", "cohesión", "componente", "conjetura", "connotación", "cooperación", "coyuntura", "desfase", "dilema", "dimensión", "discurso", "distribución", "dinámica", "eficiencia", "entorno", "escenario",
    "evolución", "fiabilidad", "financiación", "fluctuación",
    "hegemonía", "hincapié", "identidad", "índice", "iniciativa", "inversión",
    "jerarquía", "legitimidad", "marco", "matiz", "mecanismo", "norma", "organismo", "paradigma", "pauta", "premisa", "proyección", "régimen", "repercusión", "resiliencia",
    "rigor", "sesgo", "síntesis", "sostenibilidad", "trayectoria", "umbral", "variable", "viabilidad",
    "vínculo", "precedente", "indicador",
    "infraestructura", "intervención", "legislación", "obstáculo", "subvención",
    "transición", "vulnerabilidad",
    # adjectives
    "ambivalente", "audaz", "cauteloso", "certero", "concluyente",
    "contundente", "crucial", "determinante", "dinámico", "efímero", "equívoco", "exhaustivo", "explícito",
    "genuino", "gradual", "holístico", "imperioso", "implícito",
    "indispensable", "ineludible", "inherente", "integral",
    "metodológico", "multidisciplinario", "óptimo", "ponderable", "potencial", "pragmático", "preciso", "prioritario",
    "progresivo", "provisional", "rentable", "riguroso",
    "sesgado", "sistémico", "subjetivo",
    "sutil", "sustancial", "tangible", "tenaz", "transversal", "versátil", "viable",
})

# ── French B2 ─────────────────────────────────────────────────────────────────
_FR_B2: frozenset[str] = frozenset({
    # verbs
    "accréditer", "alléger", "allouer", "anticiper", "attribuer",
    "cautionner", "compenser", "confronter", "consolider",
    "contester", "corroborer", "déduire", "délimiter",
    "dénoncer", "diffuser", "discerner", "élaborer",
    "émerger", "entreprendre", "exhiber", "financer",
    "fluctuer", "formuler", "générer", "implanter", "impliquer", "impulser", "inciter", "inférer",
    "instaurer", "intégrer", "investiguer", "maîtriser", "mentionner", "minimiser", "modifier",
    "obtenir", "orienter", "pondérer", "postuler",
    "prioriser", "réclamer", "renforcer", "régulariser",
    "synthétiser", "valider", "valoriser", "susciter", "recueillir", "surmonter", # nouns
    "ancrage", "apogée", "aptitude", "autonomie", "bagages",
    "biais", "cohérence", "cohésion", "composante", "connotation",
    "contingence", "coopération", "critère",
    "déséquilibre", "dynamique", "échéance", "échelon",
    "efficacité", "efficience", "enjeu", "entité", "évolution", "fiabilité", "financement", "fluctuation", "fragilité",
    "gouvernance", "hégémonie", "identité", "implication", "indice", "investissement",
    "légitimité", "mécanisme", "modèle", "nuance", "paramètre", "préalable", "prémisse", "projections", "référence", "régime", "résilience", "rigueur", "scénario", "secteur", "trajectoire", "transition", "variable",
    "vulnérabilité", "viabilité", "pertinence", "lacune", "vecteur", "faisabilité", "contrainte", "disposition", "dilemme",
    "séquençage", # adjectives
    "ambigu", "ambivalent", "audacieux", "cauteleux", "cohérent",
    "concluant", "conséquent", "crucial", "déterminant", "dynamique", "éphémère", "équivoque", "exhaustif", "explicite",
    "graduel", "holistique", "implicite", "indispensable",
    "inéluctable", "inhérent", "intégral", "méthodique",
    "multidisciplinaire", "nuancé", "optimal", "pondéré", "pragmatique", "précis", "prioritaire", "progressif",
    "provisoire", "rigoureux", "systémique", "tangible",
    "tenace", "transversal", "viable", "versatile",
})

# ── German B2 ─────────────────────────────────────────────────────────────────
_DE_B2: frozenset[str] = frozenset({
    # verbs (lowercase)
    "abwägen", "anwenden", "auswerten", "begründen",
    "beurteilen", "berücksichtigen", "charakterisieren", "demonstrieren",
    "differenzieren", "diskutieren", "dokumentieren",
    "einschätzen", "erläutern", "erörtern", "evaluieren",
    "formulieren", "gestalten", "gliedern", "illustrieren", "implementieren", "klassifizieren", "konzipieren", "legitimieren", "modifizieren", "nachweisen",
    "optimieren", "präzisieren", "priorisieren",
    "quantifizieren", "regulieren",
    "strukturieren", "synthetisieren", "systematisieren", "validieren", "vermitteln", "widersprechen",
    "zurückführen", "zusammenfassen",
    # nouns (Title-case)
    "Ambivalenz", "Ansatz", "Autonomie", "Beurteilung", "Charakteristik", "Differenzierung", "Dilemma",
    "Dimension", "Diskurs", "Dynamik", "Effizienz", "Erkenntnisse", "Evaluation", "Faktor", "Fluktuation",
    "Fragmentierung", "Gleichgewicht", "Grundlage", "Hierarchie", "Identität", "Implementation", "Indikator",
    "Infrastruktur", "Investition", "Kohärenz", "Kohäsion", "Konvergenz", "Kriterium",
    "Legitimität", "Mechanismus", "Modell", "Nachhaltigkeit",
    "Nuance", "Objektivität", "Organisation", "Paradigma",
    "Parameter", "Polarisierung", "Priorität", "Regulierung", "Relevanz", "Resilienz", "Sektor", "Systemik", "Transformation", "Transparenz", "Variable", "Verflechtung", "Verhältnis", "Verständnis", "Widerspruch",
    "Zusammenhang", "Ausmaß", "Einschränkung", "Voraussetzung",
    # adjectives
    "adäquat", "ambivalent", "charakteristisch",
    "deterministisch", "dynamisch", "explizit", "ephemer", "graduell", "holistisch", "implizit", "inhärent",
    "integral", "kohärent", "konzeptionell", "legitim",
    "methodisch", "nachhaltig", "normativ", "objektiv", "optimal",
    "pragmatisch", "präzise", "rigoros", "signifikant",
    "systematisch", "tangibel", "transversal", "transparent", "valide",
    "viabel", "wesentlich",
})

# ── Italian B2 ────────────────────────────────────────────────────────────────
_IT_B2: frozenset[str] = frozenset({
    # verbs
    "accreditare", "affrontare", "ampliare", "avallare",
    "cedere", "citare", "consolidare",
    "contestare", "corroborare", "dedurre", "delimitare",
    "denunciare", "derivare", "diffondere", "discernere", "elaborare",
    "emergere", "esibire", "finanziare", "fluttuare", "formulare",
    "generare", "implicare",
    "inferire", "instaurare", "integrare", "investigare", "limitare", "menzionare",
    "modificare", "mitigare", "ottenere", "orientare", "ponderare", "postulare", "proporre", "rafforzare",
    "reclamare", "registrare", "regolare", "sintetizzare", "suscitare", "validare", "valorizzare", "superare",
    # nouns
    "ambito", "autonomia", "coesione",
    "coerenza", "componente", "congettura",
    "connotazione", "cooperazione", "criterio", "dilemma", "dimensione", "discorso",
    "distribuzione", "dinamica", "efficienza", "entità",
    "evoluzione", "fattore", "fenomeno", "finanziamento", "fluttuazione", "gerarchia", "identità", "indice",
    "infrastruttura", "iniziativa", "investimento",
    "legittimità", "meccanismo", "modello", "norma", "organismo", "paradigma", "parametro",
    "percorso", "premessa", "proiezione", "regime", "resilienza", "rigore", "scenario", "settore", "sostenibilità", "traiettoria", "transizione", "variabile",
    "vulnerabilità", "fattibilità", "vincolo", "lacuna", "indicatore", "intervento", "legislazione",
    # adjectives
    "ambiguo", "ambivalente", "audace", "coerente", "conclusivo", "cruciale", "determinante", "dinamico", "effimero", "equivoco", "esaustivo", "esplicito", "graduale", "olistico", "implicito", "indispensabile", "ineludibile",
    "inerente", "integrale", "metodologico", "multidisciplinare",
    "oggettivo", "ottimale", "pragmatico", "preciso",
    "prioritario", "progressivo", "provvisorio", "rigoroso", "rilevante",
    "redditizio", "sistemico", "soggettivo",
    "sottile", "sostanziale", "tangibile", "tenace", "trasversale", "versatile", "valido",
})

# ── Portuguese B2 ─────────────────────────────────────────────────────────────
_PT_B2: frozenset[str] = frozenset({
    # verbs
    "ampliar", "ceder", "citar",
    "concluir", "confrontar", "consolidar", "contestar", "corroborar",
    "deduzir", "delimitar", "denunciar", "derivar", "difundir",
    "discernir", "elaborar", "emergir", "exibir", "financiar",
    "flutuar", "formular", "gerar", "implicar", "inferir", "instaurar", "integrar", "mencionar",
    "mitigar", "modificar", "obter", "orientar", "planejar",
    "ponderar", "postular", "propor", "reforçar", "registrar", "regular", "sintetizar",
    "suscitar", "validar", "valorizar", "superar", "sustentar",
    # nouns
    "âmbito", "arraigamento", "auge", "coesão", "componente", "conjetura", "conotação", "cooperação", "critério", "desequilíbrio", "dilema", "dimensão", "discurso",
    "distribuição", "dinâmica", "eficiência", "entidade",
    "evolução", "fator", "fenômeno", "financiamento", "flutuação",
    "fragilidade", "governança", "hegemonia", "identidade", "índice", "iniciativa", "investimento",
    "legitimidade", "mecanismo", "modelo", "norma",
    "nuance", "organismo", "paradigma", "parâmetro", "premissa", "projeção", "regime", "resiliência", "rigor", "setor", "sustentabilidade", "trajetória", "transição", "variável",
    "vulnerabilidade", "viabilidade", "lacuna", "vínculo", "indicador", "infraestrutura", "intervenção",
    # adjectives
    "ambíguo", "ambivalente", "audaz", "coerente", "conclusivo", "crucial", "determinante", "dinâmico", "efêmero", "equívoco", "exaustivo", "explícito", "gradual", "holístico", "implícito", "indispensável", "ineludível",
    "inerente", "integral", "metodológico", "multidisciplinar", "ótimo", "pragmático", "preciso",
    "prioritário", "progressivo", "provisório", "rigoroso", "rentável", "sistêmico", "subjetivo",
    "sutil", "substancial", "tangível", "tenaz", "transversal", "versátil", "viável",
})

# ── Russian B2 ────────────────────────────────────────────────────────────────
_RU_B2: frozenset[str] = frozenset({
    # verbs "выявлять", "демонстрировать",
    "документировать", "применять", "разрабатывать", "систематизировать",
    "синтезировать", "формулировать", "характеризовать", "корректировать", "минимизировать", "мобилизовать",
    "модифицировать", "оптимизировать", "прогнозировать", "реализовывать", "регулировать", "стимулировать", "структурировать",
    "трансформировать", # nouns
    "амбивалентность", "аргументация", "аутентичность",
    "взаимодействие", "глобализация",
    "дефицит", "дилемма", "дисбаланс", "динамика", "идентичность", "интерпретация", "инфраструктура", "инициатива", "категория", "коэффициент", "критерий", "легитимность", "механизм", "обоснование", "парадигма", "параметр", "приоритет", "прогноз", "реализация", "регулирование",
    "результативность", "риск", "сектор", "синтез", "трансформация", "уязвимость", "фактор", "финансирование", "целостность", "эволюция", "эффективность",
    "устойчивость", "противоречие", "надёжность", "сценарий", "обязательство", "диверсификация",
    # adjectives
    "адекватный", "амбивалентный", "аналитический", "динамичный", "когерентный", "комплексный", "конструктивный", "методологический", "нормативный",
    "объективный", "оптимальный", "прагматичный", "прозрачный",
    "рациональный", "релевантный", "результативный", "системный",
    "стратегический", "целостный", "последовательный", "существенный",
})

# ── Japanese B2 ───────────────────────────────────────────────────────────────
_JA_B2: frozenset[str] = frozenset({
    "論じる", "把握する",
    "考察する", "検証する", "推測する",
    "判断する", "導入する", "構築する", "解析する", "識別する", "区別する", "統合する", "最適化する", "合理化する", "強化する", "促進する", "実現する", "示唆する", "影響する", "依存する", "関連する",
    "複雑だ", "曖昧だ", "柔軟だ", "合理的だ", "批判的だ",
    "体系的だ", "総合的だ", "包括的だ", "根本的だ", "抽象的だ", "展開", "枠組み", "体制", "仕組み", "手法", "方針", "指針",
    "基準", "規範", "概念", "モデル", "パラダイム",
    "パターン", "動向", "成果", "実績",
    "障壁", "制約", "要因", "変数", "指標",
    "格差", "不均衡", "矛盾", "ジレンマ", "曖昧さ", "複雑性", "連携", "協力", "計画", "政策", "革新", "技術", "情報", "技能", "調査", "報告", "論点", "根拠", "推論", "要約", "解釈", "分類", "定義", "優先", "持続可能性", "効率性", "有効性",
    "透明性", "正当性", "包摂", "脆弱性",
})

# ── Chinese B2 ────────────────────────────────────────────────────────────────
_ZH_B2: frozenset[str] = frozenset({ "阐述", "实施", "制定", "构建",
    "推断", "验证", "整合", "优化", "推进",
    "实现", "揭示", "突出", "区分",
    "辨别", "归纳", "演绎", "对比", "批判", "检验", "探讨", "确认", "反驳", "纠正", "完善", "扩展", "深化", "调整", "整理", "规划",
    "框架", "机制", "体系", "维度", "层面", "立场", "理念", "概念", "规范", "标准",
    "模式", "范式", "模型", "途径", "策略", "方案", "成效", "效率", "效能", "因素", "变量", "指标", "参数",
    "差距", "矛盾", "困境", "障碍", "约束", "局限",
    "潜力", "动态", "演变", "转型", "整合", "协作", "互动", "参与", "贡献", "信息", "依据", "论据", "认知", "理解", "诠释", "可持续性", "透明度", "合法性",
    "脆弱性", "韧性", "复杂性", "不确定性",
    "综合", "全面", "深入", "客观", "主观", "动态", "静态", "相对", "绝对", "有效", "可行", "合理", "批判", "包容", })

# ── Arabic B2 ─────────────────────────────────────────────────────────────────
_AR_B2: frozenset[str] = frozenset({
    "يُحلّل", "يُقيّم", "يُناقش", "يُبرهن", "يُوضّح", "يُطبّق",
    "يُطوّر", "يُصمّم", "يُنفّذ", "يُرسّخ", "يُدمج", "يُنسّق",
    "يُحسّن", "يُعزّز", "يُروّج", "يُحقّق", "يُثبت", "يُظهر",
    "يُميّز", "يُصنّف", "يُعرّف", "يُبسّط", "يُحدّد",
    "يُراقب", "يُرصد", "يُخطّط", "يُصلح", "يُكيّف",
    "يُحاجج", "يُقارن", "يُقيس", "يُستنتج",
    "إطار", "آلية", "نموذج", "معيار",
    "متغير", "مؤشر", "بُعد", "رؤية", "مسار", "فاعلية", "مآل",
    "تناقض", "إشكالية", "تحدٍّ", "قيد", "حاجز", "ديناميكية", "تحوّل", "ابتكار", "تكامل", "تفاعل", "مشاركة", "إسهام", "إدراك", "تفسير",
    "تنوّع", "استدامة", "شفافية", "شرعية", "هشاشة",
    "مرونة", "تعقيد", "تداخل",
    "شامل", "منهجي", "موضوعي", "مجرّد", "ملموس",
    "ديناميكي", "نسبي", "مطلق", "فعّال", "ناقد", "هادف",
})

# ── Hebrew B2 ─────────────────────────────────────────────────────────────────
_HE_B2: frozenset[str] = frozenset({ "להסביר", "לפתח", "לתכנן", "לבצע", "לשלב", "לייעל", "להשיג", "להדגים", "להבחין", "לסווג", "להגדיר",
    "לסכם", "לבקר", "לאתגר", "לחזק", "לצמצם", "לרכז", "לבחון", "להסיק", "להשוות", "מסגרת", "מנגנון", "מודל", "מושג", "קריטריון", "משתנה", "מדד", "ממד", "מסלול", "יעילות",
    "אפקטיביות", "סתירה", "בעייתיות", "מגבלה", "פוטנציאל", "דינמיקה", "חדשנות", "שיתוף",
    "אינטראקציה", "השתתפות", "תרומה", "תפיסה", "פרשנות", "כוללנות",
    "קיימות", "שקיפות", "לגיטימיות", "שבירות", "חוסן", "מורכבות",
    "מקיף", "שיטתי", "אובייקטיבי", "סובייקטיבי", "קונקרטי", "דינמי", "יחסי", "מוחלט", "אפקטיבי", "ישים", })

#: Map from language code to frozenset of B2 lemmas (excludes A1–B1 items).
B2: dict[str, frozenset[str]] = {
    "es": _ES_B2,
    "fr": _FR_B2,
    "de": _DE_B2,
    "it": _IT_B2,
    "pt": _PT_B2,
    "ru": _RU_B2,
    "ja": _JA_B2,
    "zh": _ZH_B2,
    "ar": _AR_B2,
    "he": _HE_B2,
    "fi": _FI_B2,
    "tr": _TR_B2,
    "hi": _HI_B2,
}

# ──────────────────────────────────────────────────────────────────────────────
# C1 tables (advanced: ~240 lemmas / lang)
# Confidence 0.82 — only overrides OOV (tok.is_oov); below in-vocab (0.85)
# ──────────────────────────────────────────────────────────────────────────────

# ── Spanish C1 ────────────────────────────────────────────────────────────────
_ES_C1: frozenset[str] = frozenset({
    # verbs
    "abogar", "abrogar", "amalgamar", "atenuar", "catalizar",
    "circunscribir", "cohibir", "confluir", "decaer", "deliberar",
    "desestimar", "disipar", "elucidar", "emanar", "emancipar", "erosionar", "escindir", "exacerbar", "exhortar",
    "extirpar", "homologar", "impugnar", "invocar", "irrumpir",
    "menguar", "obviar", "perpetuar", "prescindir", "proclamar",
    "proscribir", "recapitular", "reiterar", "reprochar", "revertir",
    "salvaguardar", "socavar", "subsumir", "sucumbir", "suprimir",
    "tergiversar", "transgredir", "trascender", "vindicar", "yuxtaponer",
    "abstraer", "contravenir", "esgrimir", "fustigar",
    "instigar", "perpetrar", "precipitar", "subyugar",
    # nouns
    "abismo", "afán", "amalgama", "antagonismo", "aporía", "artificio",
    "asidero", "atavismo", "axioma", "compendio", "correlato",
    "cuestionamiento", "disrupción", "eclosión", "epítome",
    "escepticismo", "expediente", "fisura", "impugnación", "incongruencia",
    "inflexión", "latencia", "legado", "menoscabo", "metamorfosis",
    "nexo", "obsolescencia", "ocaso", "paradoja", "parangón",
    "postulado", "propensión", "quiebre", "reciprocidad", "simulacro",
    "trasfondo", "vicisitud", "axiología", "cosmovisión", "dialéctica",
    "espectro", "imperativo", "ontología", "teleología", "epistemología",
    "anomalía", "antítesis", "catarsis", "correlación", "dogma",
    "eufemismo", "falacia", "ironía", "metáfora", "silogismo",
    "tautología", "acometida", "complicidad", "corolario", "denotación",
    "empirismo", "éxodo", "idiosincrasia", "intertextualidad", "moratoria", "relato", "substrato", "utopía", "paradoja",
    # adjectives
    "acucioso", "antitético", "apremiante", "arcaico",
    "atávico", "axiomático", "categórico", "connotativo", "consustancial",
    "contingente", "deontológico", "dialéctico", "disonante", "dogmático",
    "empírico", "epistemológico", "existencial", "falaz", "filosófico",
    "hermenéutico", "hipotético", "ideológico", "inductivo", "innato",
    "intrínseco", "irrevocable", "metafísico", "mítico", "ontológico",
    "paradójico", "perentorio", "polifacético", "prescriptivo",
    "relacional", "retórico", "semiótico", "simbólico", "sinérgico",
    "teleológico", "utópico",
})

# ── French C1 ─────────────────────────────────────────────────────────────────
_FR_C1: frozenset[str] = frozenset({
    # verbs
    "abdiquer", "abroger", "amalgamer", "atténuer", "catalyser",
    "circonscrire", "confluir", "décliner", "délibérer", "dissimuler",
    "dissiper", "éluder", "émanciper", "éroder", "exacerber",
    "exhorter", "extirper", "homologuer", "impugner", "infléchir",
    "instiller", "invoquer", "menguer", "omettre", "perpétuer",
    "proclamer", "proscrire", "récapituler", "réitérer", "réprouver",
    "révoquer", "sauvegarder", "saper", "succomber", "supprimer",
    "transgresser", "transcender", "vindiqer", "juxtaposer",
    "abstraire", "contrevenir", "escamoter", "fustiger", "instiguer",
    "perpétrer", "précipiter", "subjuguer", "déconstruire",
    # nouns
    "abîme", "amalgame", "antagonisme", "aporie", "artifice",
    "atavisme", "axiome", "compendium", "corrélat", "déconstruction",
    "désenchantement", "disruption", "éclosion", "épistémologie",
    "épitome", "scepticisme", "expédient", "fissure", "impugnation",
    "incongruence", "inflexion", "latence", "legs", "mensonge",
    "métamorphose", "nexus", "obsolescence", "paradoxe", "postulat", "propension", "réciprocité", "simulacre", "substratum",
    "trasfondo", "vicissitude", "axiologie", "cosmovision", "dialectique",
    "spectre", "impératif", "ontologie", "téléologie",
    "anomalie", "antithèse", "catharsis", "corrélation", "dogme",
    "euphémisme", "fallace", "ironie", "métaphore", "syllogisme",
    "tautologie", "complicité", "corollaire", "dénotation",
    "empirisme", "idiosyncrasie", "moratoire", "substrat", "utopie", "déterminisme",
    # adjectives
    "acéré", "anachronique", "antithétique", "atavique", "axiomatique",
    "catégorique", "connotatif", "consubstantiel", "contingent",
    "déontologique", "dialectique", "dissonant", "dogmatique",
    "empirique", "épistémologique", "existentiel", "fallacieux",
    "philosophique", "herméneutique", "hypothétique", "idéologique",
    "inductif", "inné", "intrinsèque", "irrévocable", "métaphysique",
    "mythique", "ontologique", "paradoxal", "prescriptif",
    "relationnel", "rhétorique", "sémiotique", "symbolique",
    "synergique", "téléologique", "utopique",
})

# ── German C1 ─────────────────────────────────────────────────────────────────
_DE_C1: frozenset[str] = frozenset({
    # verbs (lowercase)
    "abdanken", "abrogieren", "amalgamieren", "abschwächen", "katalysieren",
    "eingrenzen", "deliberieren", "dissipieren", "emanzipieren",
    "erodieren", "verschärfen", "ermahnen", "extirpieren", "homologieren",
    "anfechten", "anrufen", "einbrechen", "verewigen", "proklamieren", "rekapitulieren", "rügen", "rückgängig machen",
    "schützen", "untergraben", "subsumieren", "unterliegen", "unterdrücken",
    "überschreiten", "transzendieren", "vindizieren", "nebeneinanderstellen",
    "abstrahieren", "zuwiderhandeln", "dekonstruieren",
    # nouns (Title-case)
    "Abgrund", "Amalgam", "Antagonismus", "Aporie", "Atavismus",
    "Axiom", "Kompendium", "Korrelat", "Dekonstruktion",
    "Disruption", "Epistemologie", "Skeptizismus",
    "Inkongruenz", "Inflexion", "Latenz", "Vermächtnis",
    "Metamorphose", "Nexus", "Obsoleszenz", "Paradox",
    "Postulat", "Propensität", "Reziprozität", "Simulakrum",
    "Substrat", "Wechselfälle", "Axiologie", "Weltanschauung",
    "Dialektik", "Spektrum", "Imperativ", "Ontologie",
    "Teleologie", "Anomalie", "Antithese", "Katharsis",
    "Korrelation", "Dogma", "Euphemismus", "Fehlschluss",
    "Ironie", "Metapher", "Syllogismus", "Tautologie",
    "Komplizität", "Korollar", "Denotation",
    "Empirismus", "Idiosynkrasie", "Moratorium", "Prärogative",
    "Utopie", "Determinismus", "Intersubjektivität",
    # adjectives
    "anachronistisch", "antithetisch", "atavistisch", "axiomatisch",
    "kategorisch", "konnotativ", "konsubstantiell", "kontingent",
    "deontologisch", "dialektisch", "dissonant", "dogmatisch",
    "empirisch", "epistemologisch", "existenziell", "trügerisch",
    "philosophisch", "hermeneutisch", "hypothetisch", "ideologisch",
    "induktiv", "angeboren", "intrinsisch", "unwiderruflich",
    "metaphysisch", "mythisch", "ontologisch", "paradox", "präskriptiv",
    "relational", "rhetorisch", "semiotisch", "symbolisch",
    "synergetisch", "teleologisch", "stillschweigend", "utopisch",
})

# ── Italian C1 ────────────────────────────────────────────────────────────────
_IT_C1: frozenset[str] = frozenset({
    # verbs
    "abdicare", "abrogare", "amalgamare", "attenuare", "catalizzare",
    "circoscrivere", "confluire", "decadere", "deliberare", "dissipare",
    "eludere", "emancipare", "erodere", "esacerbare", "esortare",
    "estirpare", "omologare", "impugnare", "invocare", "irrompere",
    "perpetuare", "proclamare", "proscrivere", "riepilogare", "reiterare",
    "biasimare", "revocare", "salvaguardare", "minare", "sussumere",
    "soccombere", "sopprimere", "trasgredire", "trascendere",
    "rivendicare", "giustapporre", "astrarre", "contravvenire",
    "fustigare", "istigare", "perpetrare", "precipitare", "soggiogare",
    # nouns
    "abisso", "amalgama", "antagonismo", "aporia", "artificio",
    "atavismo", "assioma", "compendio", "correlato", "decostruzione",
    "disruzione", "epistemologia", "epitome", "scetticismo",
    "incongruenza", "inflessione", "latenza", "lascito",
    "metamorfosi", "nesso", "obsolescenza", "paradosso",
    "postulato", "propensione", "reciprocità", "simulacro",
    "sostrato", "vicissitudine", "assiologia", "visione del mondo",
    "dialettica", "spettro", "imperativo", "ontologia",
    "teleologia", "anomalia", "antitesi", "catarsi",
    "correlazione", "dogma", "eufemismo", "fallacia",
    "ironia", "metafora", "sillogismo", "tautologia",
    "complicità", "corollario", "denotazione",
    "empirismo", "idiosincrasia", "moratoria", "utopia", "determinismo", "intersoggettività",
    # adjectives
    "anacronistico", "antitetico", "atavico", "assiomatico",
    "categorico", "connotativo", "consustanziale", "contingente",
    "deontologico", "dialettico", "dissonante", "dogmatico",
    "empirico", "epistemologico", "esistenziale", "fallace",
    "filosofico", "ermeneutico", "ipotetico", "ideologico",
    "induttivo", "innato", "intrinseco", "irrevocabile",
    "metafisico", "mitico", "ontologico", "paradossale",
    "prescrittivo", "relazionale", "retorico", "semiotico",
    "simbolico", "sinergico", "teleologico", "tacito", "utopico",
})

# ── Portuguese C1 ─────────────────────────────────────────────────────────────
_PT_C1: frozenset[str] = frozenset({
    # verbs
    "abdicar", "ab-rogar", "amalgamar", "atenuar", "catalizar",
    "circunscrever", "confluir", "decair", "deliberar", "dissipar",
    "eludir", "emancipar", "erodir", "exacerbar", "exortar",
    "extirpar", "homologar", "impugnar", "invocar", "irromper",
    "perpetuar", "proclamar", "proscrever", "recapitular", "reiterar",
    "repreender", "revogar", "salvaguardar", "solapar", "subsumir",
    "sucumbir", "suprimir", "transgredir", "transcender", "justapor", "abstrair", "contravir",
    "fustigar", "instigar", "perpetrar", "precipitar", "subjugar",
    # nouns
    "abismo", "amalgama", "antagonismo", "aporia", "artifício",
    "atavismo", "axioma", "compêndio", "correlato", "desconstrução",
    "disrupção", "epistemologia", "epítome", "ceticismo",
    "incongruência", "inflexão", "latência", "legado",
    "metamorfose", "nexo", "obsolescência", "paradoxo",
    "postulado", "propensão", "reciprocidade", "simulacro",
    "substrato", "vicissitude", "axiologia", "cosmovisão",
    "dialética", "espectro", "imperativo", "ontologia",
    "teleologia", "anomalia", "antítese", "catarse",
    "correlação", "dogma", "eufemismo", "falácia",
    "ironia", "metáfora", "silogismo", "tautologia",
    "cumplicidade", "corolário", "denotação",
    "empirismo", "idiossincrasia", "moratória", "utopia", "determinismo", "intersubjetividade",
    # adjectives
    "anacrônico", "antitético", "atávico", "axiomático",
    "categórico", "conotativo", "consubstancial", "contingente",
    "deontológico", "dialético", "dissonante", "dogmático",
    "empírico", "epistemológico", "existencial", "falacioso",
    "filosófico", "hermenêutico", "hipotético", "ideológico",
    "indutivo", "inato", "intrínseco", "irrevogável",
    "metafísico", "mítico", "ontológico", "paradoxal",
    "prescritivo", "relacional", "retórico", "semiótico",
    "simbólico", "sinérgico", "teleológico", "utópico",
})

# ── Russian C1 ────────────────────────────────────────────────────────────────
_RU_C1: frozenset[str] = frozenset({
    # verbs
    "абстрагировать", "amalgamировать", "ослаблять", "катализировать",
    "ограничивать", "deliberировать", "рассеивать", "эмансипировать",
    "эродировать", "обострять", "увещевать", "искоренять",
    "ходатайствовать", "вторгаться", "увековечивать", "провозглашать",
    "запрещать", "рекапитулировать", "осуждать",
    "отменять", "подрывать", "подчинять", "поддаваться",
    "подавлять", "нарушать", "трансцендировать", "декonstruировать",
    "абстрагироваться", "противоречить",
    # nouns
    "пропасть", "амальгама", "антагонизм", "апория", "атавизм",
    "аксиома", "компендиум", "коррелят", "деконструкция",
    "эпистемология", "эпитоме", "скептицизм",
    "инконгруентность", "латентность", "наследие",
    "метаморфоза", "нексус", "постулат", "реципрокность", "симулякр",
    "субстрат", "превратности", "аксиология", "мировоззрение",
    "диалектика", "спектр", "императив", "онтология",
    "телеология", "аномалия", "антитезис", "катарсис",
    "корреляция", "догма", "эвфемизм", "заблуждение",
    "ирония", "метафора", "силлогизм", "тавтология",
    "соучастие", "следствие", "коннотация",
    "эмпиризм", "идиосинкразия", "мораторий",
    "утопия", "детерминизм", "интерсубъективность",
    "нигилизм", "плюрализм", "релятивизм",
    # adjectives
    "анахроничный", "антитетический", "атавистический", "аксиоматический",
    "категорический", "коннотативный", "контингентный",
    "деонтологический", "диалектический", "диссонантный", "догматический",
    "эмпирический", "эпистемологический", "экзистенциальный",
    "философский", "герменевтический", "гипотетический", "идеологический",
    "индуктивный", "врождённый", "внутренний", "метафизический",
    "мифический", "онтологический", "парадоксальный",
    "риторический", "семиотический", "символический", "синергетический",
    "телеологический", "тацитный", "утопический",
})

# ── Japanese C1 ───────────────────────────────────────────────────────────────
_JA_C1: frozenset[str] = frozenset({
    "棄権する", "廃止する", "融合する", "緩和する", "触媒する",
    "限定する", "審議する", "解消する", "解放する", "浸食する",
    "悪化させる", "訓戒する", "根絶する", "宣言する", "禁止する",
    "要約する", "非難する", "廃止する", "保護する",
    "弱体化する", "包摂する", "降伏する", "抑圧する", "超越する", "並置する", "抽象化する", "違反する",
    "深淵", "融合体", "拮抗", "アポリア", "隔世遺伝", "公理",
    "集成", "認識論", "懐疑主義",
    "不整合", "潜在性", "遺産",
    "変容", "パラドックス",
    "公準", "互恵性", "シミュラクラ",
    "基体", "変転", "価値論", "世界観",
    "弁証法", "スペクトル", "命令", "存在論",
    "目的論", "異常", "対位法", "カタルシス",
    "相関", "教義", "婉曲", "誤謬",
    "皮肉", "隠喩", "三段論法", "同語反復",
    "共犯", "系論", "外示",
    "経験主義", "特異性", "モラトリアム",
    "ユートピア", "決定論", "間主観性",
    "虚無主義", "多元主義", "相対主義",
    "アナクロニズム", "本質主義",
    "時代錯誤な", "反命題的", "公理的",
    "断定的", "含意的", "同質的", "偶発的",
    "義務論的", "弁証法的", "不協和な", "独断的",
    "経験的", "認識論的", "実存的",
    "哲学的", "解釈学的", "仮定的", "イデオロギー的",
    "帰納的", "生得的", "内在的", "形而上学的",
    "神話的", "存在論的", "逆説的",
    "修辞的", "記号論的", "象徴的", "目的論的",
})

# ── Chinese C1 ────────────────────────────────────────────────────────────────
_ZH_C1: frozenset[str] = frozenset({
    "退位", "废除", "缓和", "催化",
    "限定", "审议", "消散", "解放", "侵蚀",
    "加剧", "告诫", "根除", "宣告", "禁止",
    "概括", "重申", "谴责", "保护",
    "削弱", "归摄", "屈服", "压制", "超越",
    "并置", "抽象化", "违背",
    "深渊", "融合体", "对立", "悖论", "隔代遗传", "公理",
    "纲要", "认识论", "怀疑主义",
    "不一致", "潜在性", "遗产",
    "蜕变", "悖论", "互惠性", "拟像",
    "基质", "变迁", "价值论", "世界观",
    "辩证法", "谱系", "命令", "本体论",
    "目的论", "异常", "反题", "净化",
    "相关性", "教条", "委婉", "谬误",
    "讽刺", "隐喻", "三段论", "同义反复",
    "共谋", "外延",
    "经验主义", "特质", "暂缓",
    "乌托邦", "决定论", "主体间性",
    "虚无主义", "多元主义", "相对主义", "本质主义",
    "时代错误的", "反命题的", "公理的",
    "断然的", "含蓄的", "同质的", "偶然的",
    "义务论的", "辩证的", "不协调的", "教条的",
    "经验的", "认识论的", "存在主义的",
    "哲学的", "诠释学的", "假设的", "意识形态的",
    "归纳的", "天赋的", "内在的", "形而上学的",
    "神话的", "本体论的", "悖论的",
    "修辞的", "符号学的", "象征的", "目的论的",
})

# ── Arabic C1 ─────────────────────────────────────────────────────────────────
_AR_C1: frozenset[str] = frozenset({
    "يَتَخَلَّى", "يُلغي", "يَمتَزج", "يُخفِّف", "يُحفِّز",
    "يَتَداوَل", "يَتبدَّد", "يُحرِّر", "يَتآكَل",
    "يُفاقِم", "يَحثُّ", "يَستأصِل", "يُعلِن", "يَحظُر",
    "يُلخِّص", "يُكرِّر", "يُنكِر",
    "يُبطِل", "يَحفَظ", "يَنخَر",
    "يَخضَع", "يَقمَع", "يَتجاوَز",
    "يَضَع جَنبًا إلى جَنب",
    "هُوَّة", "تآلُف", "تضادّ", "بداهة", "رَجعيَّة",
    "بديهيَّة", "ملخَّص", "إبستيمولوجيا", "تشكيكيَّة",
    "تنافر", "كامِنيَّة", "إرث",
    "تحوُّل", "نَقِيض", "تبادُليَّة",
    "مَسرَح", "رُكيزة", "أكسيولوجيا", "رُؤيَة عالَمِيَّة",
    "جدَليَّة", "طَيف", "أمر واجب", "أُنطولوجيا",
    "غائيَّة", "شُذوذ", "نقيض", "تَطهير",
    "ترابُط", "عقيدة", "كِناية", "مغالطة",
    "سُخرية", "استعارة", "قياس", "تكرار",
    "تواطُؤ", "لازِمة", "دلالة",
    "تجريبيَّة", "خُصوصية", "تأجيل",
    "يوتوبيا", "حَتميَّة", "بين الذوات",
    "عَدَميَّة", "تعدُّدية", "نسبيَّة",
    "مفارَقة تاريخيَّة", "جَوهَريَّة",
    "مُتناقض مع العصر", "ضدّ-أطروحي", "بديهي",
    "قاطع", "ضمني", "متجانس", "عَرَضي",
    "واجبي", "جدَلي", "متنافر", "عقائدي",
    "تجريبي", "معرفي", "وجودي",
    "فلسفي", "تأويلي", "افتراضي", "أيديولوجي",
    "استنتاجي", "فطري", "ميتافيزيقي",
    "أسطوري", "وجودي", "مفارِق",
    "خطابي", "سيميائي", "رمزي", "غائي",
})

# ── Hebrew C1 ─────────────────────────────────────────────────────────────────
_HE_C1: frozenset[str] = frozenset({
    "לוותר", "לבטל", "להתמזג", "להקל", "לזרז",
    "להגביל", "להתדיין", "להתפוגג", "לשחרר", "לשחוק",
    "להחריף", "להזהיר", "לעקור", "להכריז", "לאסור",
    "לסכם מחדש", "לחזור על", "לגנות", "לדכא", "להתעלות",
    "להציב זה לצד זה", "להפשיט", "להפר",
    "תהום", "תמהיל", "ניגוד", "אפוריה", "אטוויזם",
    "אקסיומה", "מאסף", "אפיסטמולוגיה", "סקפטיות",
    "חוסר עקביות", "חביון", "מורשת",
    "מטמורפוזה", "פרדוקס", "הדדיות", "סימולקרום",
    "מצע", "אקסיולוגיה", "תפיסת עולם",
    "דיאלקטיקה", "ספקטרום", "ציווי", "אונטולוגיה",
    "טלאולוגיה", "אנומליה", "אנטיתזה", "קתרזיס",
    "קורלציה", "דוגמה", "אופמיזם", "כשל",
    "אירוניה", "מטאפורה", "סילוגיזם", "טאוטולוגיה",
    "שותפות לפשע", "קורולריה", "דנוטציה",
    "אמפיריציזם", "אידיוסינקרטיות", "מורטוריום",
    "אוטופיה", "דטרמיניזם", "בין-סובייקטיביות",
    "ניהיליזם", "פלורליזם", "רלטיביזם", "אסנציאליזם",
    "אנכרוניסטי", "אנטי-תזאי", "אקסיומטי",
    "קטגורי", "קונוטטיבי", "הומוגני", "מקרי",
    "דאונטולוגי", "דיאלקטי", "דיסוננטי", "דוגמטי",
    "אמפירי", "אפיסטמי", "אקזיסטנציאלי",
    "פילוסופי", "הרמנויטי", "היפותטי", "אידיאולוגי",
    "אינדוקטיבי", "מולד", "אינהרנטי", "מטאפיזי",
    "מיתי", "אונטולוגי", "פרדוקסלי",
    "רטורי", "סמיוטי", "סמלי", "טלאולוגי",
})

#: Map from language code to frozenset of C1 lemmas (excludes A1–B2 items).
C1: dict[str, frozenset[str]] = {
    "es": _ES_C1,
    "fr": _FR_C1,
    "de": _DE_C1,
    "it": _IT_C1,
    "pt": _PT_C1,
    "ru": _RU_C1,
    "ja": _JA_C1,
    "zh": _ZH_C1,
    "ar": _AR_C1,
    "he": _HE_C1,
    "fi": _FI_C1,
    "tr": _TR_C1,
    "hi": _HI_C1,
}

# ──────────────────────────────────────────────────────────────────────────────
# C2 tables (mastery: ~190 lemmas / lang)
# Confidence 0.80 — only overrides OOV (tok.is_oov); below in-vocab (0.85)
# ──────────────────────────────────────────────────────────────────────────────

# ── Spanish C2 ────────────────────────────────────────────────────────────────
_ES_C2: frozenset[str] = frozenset({
    # verbs (rare/literary/archaic-formal)
    "abominar", "acaecer", "adolecer", "aliterarse",
    "anatemizar", "anteceder", "atormentar", "beatificar", "coadyuvar",
    "consagrar", "devengar", "dimanar", "dirimir", "estigmatizar", "excomulgar", "fenecer", "fulminar",
    "glorificar", "impetrar", "inmolar", "inquirir", "lacerar",
    "lisonjear", "macerar", "merodear", "mortificar", "ostentar",
    "patentizar", "penar", "perecer", "perfilar", "preconizar",
    "premiar", "pretender", "prorrumpir", "pugnar", "purgar",
    "recusar", "renegar", "resarcir", "resignarse",
    "sancionar", "secularizar", "sublimar", "tolerar", "vacilar",
    "venerar", "vituperar", "yacer",
    # nouns (literary/archaic/very formal)
    "acervo", "acrimonia", "alambique", "altruismo", "anacronismo",
    "apostasía", "arcano", "banalidad", "baluarte", "cataclismo",
    "cénit", "cónclave", "confín", "contumacia", "crepúsculo", "efigie", "elucubración", "encomio", "epifanía",
    "epopeya", "estirpe", "éxtasis", "fatum", "fervor",
    "hastío", "impávido", "indolencia", "insidia", "jactancia",
    "laberinto", "lamento", "lascivia", "letargo", "linaje",
    "magnificencia", "mártir", "nimbo", "panteón", "parsimonia",
    "pátina", "penumbra", "pervivencia", "pompa", "portento",
    "presagio", "prodigio", "saga", "serenidad", "soliloquio",
    "solipsismo", "sopor", "tormento", "umbría", "veneración",
    "vestigio", "villanía", "yermo",
    # adjectives (very formal/literary/archaic)
    "acérrimo", "adlátere", "altisonante", "amorfo", "apócrifo", "arduo", "beatífico", "cenital", "ciclópeo",
    "contumaz", "desmesurado", "dracónico", "egrégio", "eximio",
    "fabuloso", "fatídico", "fatuo", "férreo", "fúnebre",
    "gárrulo", "glacial", "hórrido", "inclito", "inefable",
    "inescrutable", "infausto", "ingente", "insigne", "íntegro",
    "irascible", "lóbrego", "luciferino", "macabro", "magno",
    "nimio", "nímio", "ominoso", "omnipotente", "omnisciente",
    "perenne", "póstumo", "prístino", "profuso", "pugnable",
    "saturnino", "seráfico", "solemne", "sombrío", "torpe", "truculento", "vetusto", "vívido",
})

# ── French C2 ─────────────────────────────────────────────────────────────────
_FR_C2: frozenset[str] = frozenset({
    # verbs
    "abhorrer", "abominer", "advenir", "anathématiser", "antécéder",
    "beatifier", "coadjuver", "consacrer", "stigmatiser", "excommunier",
    "périr", "fulminer", "glorifier", "implorer", "immoler", "flatter", "macérer", "mortifier", "afficher",
    "renoncer", "purger", "séculariser", "sublimer",
    "vénérer", "vitupérer", "gésir",
    # nouns
    "acrimonie", "alambic", "altruisme", "anachronisme", "apostasie",
    "arcane", "banalité", "bastion", "cataclysme", "zénith",
    "conclave", "confins", "contumace", "crépuscule",
    "dédain", "effigie", "élucubration", "éloge", "épiphanie",
    "épopée", "estirpe", "extase", "destin", "ferveur",
    "langueur", "indolence", "insidiosité", "jactance",
    "labyrinthe", "lamentation", "lascivité", "léthargie", "lignage",
    "magnificence", "martyr", "nimbe", "panthéon", "parcimonie",
    "patine", "pénombre", "pompe", "portent",
    "présage", "prodige", "saga", "sérénité", "soliloque",
    "solipsisme", "torpeur", "tourment", "vénération",
    "vestige", "vilenie",
    # adjectives
    "acerbe", "altisonant", "amorphe", "apocryphe",
    "béatifique", "cyclopéen", "contumace", "démesuré",
    "draconien", "égrégore", "fabuleux",
    "fatidique", "fat", "funèbre", "funeste",
    "glacial", "horrible", "illustre", "ineffable",
    "inscrutable", "infâme", "ingénu", "insignifiant",
    "irascible", "lugubre", "macabre", "omineux", "omnipotent", "omniscient", "perpétuel",
    "posthume", "pristine", "profus", "saturnin",
    "séraphique", "solennel", "truculent", "vétuste", "vivide",
})

# ── German C2 ─────────────────────────────────────────────────────────────────
_DE_C2: frozenset[str] = frozenset({
    # verbs
    "verabscheuen", "verfluchen", "verherrlichen", "verklären",
    "versteinern", "verwünschen", "weihen", "anprangern", "beschwören", "brandmarken", "entehren",
    "entlarven", "entheiligen", "entsagen", "erbarmen",
    "freveln", "geißeln", "kasteien", "lästern",
    "martyrisieren", "schmähen", "sühnen", "vergotten",
    # nouns (Title-case)
    "Abscheu", "Acrimonie", "Alchemie", "Altruismus", "Anachronismus",
    "Apostasie", "Arcanum", "Bastion", "Kataklysmik", "Zenit",
    "Konzil", "Contumaz", "Dämmerung",
    "Efigie", "Epiphanie", "Epos", "Ekstase",
    "Inbrunst", "Gleichgültigkeit", "Labyrint", "Klage",
    "Lüsternheit", "Lethargie", "Abstammung",
    "Herrlichkeit", "Märtyrer", "Nimbus", "Pantheon", "Besonnenheit",
    "Patina", "Halbdunkel", "Prunk", "Omen",
    "Prophezeiung", "Wundertat", "Saga", "Gelassenheit",
    "Selbstgespräch", "Solipsismus", "Torheit", "Qual",
    "Verehrung", "Überrest", "Bosheit", "Einöde",
    # adjectives
    "abscheulich", "altertümlich", "apokryph",
    "selig", "kolossal", "maßlos",
    "drakonisch", "fabelhaft",
    "verhängnisvoll", "eisig",
    "entsetzlich", "unaussprechlich",
    "unergründlich", "unheilsam", "gewaltig", "ehrwürdig",
    "jähzornig", "düster", "unheilvoll", "grandios",
    "unheilverkündend", "allmächtig", "allwissend", "immerwährend",
    "posthum", "unverfälscht", "üppig",
    "düsterlich", "feierlich", "finster",
    "grausam", "uralt", "lebendig",
})

# ── Italian C2 ────────────────────────────────────────────────────────────────
_IT_C2: frozenset[str] = frozenset({
    # verbs
    "aborrire", "abominare", "accadere", "anatematizzare",
    "beatificare", "consacrare", "coadiuvare",
    "stigmatizzare", "scomunicare",
    "perire", "fulminare", "glorificare", "implorare", "immolare", "adulare", "macerare", "ostentare",
    "rinunciare", "purgare", "secolarizzare", "sublimare",
    "venerare", "vituperare", "giacere",
    # nouns
    "acrimonia", "alambicco", "altruismo", "anacronismo", "apostasia",
    "arcano", "banalità", "bastione", "cataclisma", "zenit",
    "conclave", "contumacia", "crepuscolo",
    "effigie", "elucubrazione", "encomio", "epifania",
    "epopea", "stirpe", "estasi", "fervore",
    "languore", "indolenza", "insidiosità", "iattanza",
    "labirinto", "lamento", "lascivia", "letargia", "lignaggio",
    "magnificenza", "martire", "nimbo", "pantheon", "parsimonia",
    "patina", "penombra", "pompa", "portento",
    "presagio", "prodigio", "saga", "serenità", "soliloquio",
    "solipsismo", "torpore", "tormento", "venerazione",
    "vestigio", "vigliaccheria",
    # adjectives
    "acerbo", "altisonante", "amorfo", "apocrifo",
    "beatifico", "ciclopeo", "contumax", "smisurato",
    "draconiano", "favoloso", "fatidico",
    "funebre", "funesto", "glaciale", "orrendo",
    "illustre", "ineffabile", "imperscrutabile", "nefasto",
    "ingente", "insigne", "irascibile", "lugubre",
    "macabro", "magnifico", "omninoso", "omnipotente",
    "perenne", "postumo", "pristino", "profuso",
    "serafico", "solenne", "cupo", "truculento",
    "vetusto", "vivido",
})

# ── Portuguese C2 ─────────────────────────────────────────────────────────────
_PT_C2: frozenset[str] = frozenset({
    # verbs
    "abominar", "acontecer", "anatematizar", "beatificar",
    "consagrar", "coadjuvar", "estigmatizar", "excomungar",
    "perecer", "fulminar", "glorificar", "implorar", "imolar",
    "inquirir", "lisonjear", "macerar", "ostentar",
    "renunciar", "purgar", "secularizar", "sublimar",
    "venerar", "vituperar", "jazer",
    # nouns
    "acrimônia", "alambique", "altruísmo", "anacronismo", "apostasia",
    "arcano", "banalidade", "baluarte", "cataclismo", "zênite",
    "conclave", "contumácia", "crepúsculo",
    "efigie", "elucubração", "encômio", "epifania",
    "epopeia", "estirpe", "êxtase", "fervência",
    "languor", "indolência", "insídia", "jactância",
    "labirinto", "lamento", "lascívia", "letargia", "linhagem",
    "magnificência", "mártir", "nimbo", "panteão", "parcimônia",
    "pátina", "penumbra", "pompa", "portento",
    "presságio", "prodígio", "saga", "serenidade", "solilóquio",
    "solipsismo", "torpor", "tormento", "veneração",
    "vestígio", "vilania",
    # adjectives
    "acérrimo", "altisonante", "amorfo", "apócrifo",
    "beatífico", "ciclópeo", "contumaz", "desmesurado",
    "draconiano", "fabuloso", "fatídico",
    "fúnebre", "funesto", "glacial", "hórrido",
    "ilustre", "inefável", "inescrutável", "infausto",
    "ingente", "insigne", "irascível", "lúgubre",
    "macabro", "magno", "ominoso", "onipotente",
    "perene", "póstumo", "prístino", "profuso",
    "seráfico", "solene", "sombrio", "truculento",
    "vetusto", "vívido",
})

# ── Russian C2 ────────────────────────────────────────────────────────────────
_RU_C2: frozenset[str] = frozenset({
    # verbs
    "богохульствовать", "возносить", "воздавать", "вопиять",
    "воспевать", "геройствовать", "глумиться", "гнушаться",
    "довлеть", "изничтожать", "изрыгать", "кануть",
    "лицедействовать", "льстить", "мздоимствовать", "неистовствовать",
    "ниспровергать", "обличать", "опровергать", "остервенеть",
    "поносить", "превозносить", "пренебрегать", "сетовать",
    "скорбеть", "трепетать", "уничижать", "хулить",
    # nouns
    "алчность", "анахронизм", "апостасия", "архив", "аскеза",
    "блаженство", "бренность", "величие", "вероотступничество",
    "вожделение", "гнусность", "грядущее", "двуличие",
    "деспотизм", "дремота", "духовность", "забвение",
    "злодеяние", "инертность", "исступление", "лабиринт",
    "летаргия", "лицемерие", "мартирий", "мрак",
    "нечестие", "нимб", "пантеон", "пастораль",
    "перипетия", "пламень", "плач", "помпа",
    "потомство", "предзнаменование", "прельщение", "причастность",
    "прозрение", "пустошь", "скверна", "смятение",
    "сумерки", "тщеславие", "укоризна", "умозрение",
    "фатум", "хаос", "экстаз",
    # adjectives
    "алчный", "апокрифический", "архаичный", "аскетичный",
    "благостный", "бренный", "величественный", "гнусный",
    "дряхлый", "забытый", "зловещий", "зыбкий",
    "исконный", "лицемерный", "мрачный", "нечестивый",
    "неизречённый", "ничтожный", "огненный", "первозданный",
    "потусторонний", "сакральный", "скорбный", "сумеречный",
    "тленный", "торжественный", "трагический", "тщетный",
    "умозрительный", "устаревший", "ярый",
})

# ── Japanese C2 ───────────────────────────────────────────────────────────────
_JA_C2: frozenset[str] = frozenset({
    "忌避する", "呪詛する", "崇拝する", "悼む", "嘆く",
    "罵倒する", "美化する", "冒涜する", "奉じる",
    "嘲弄する", "玩弄する", "讃える", "誹謗する",
    "懺悔する", "殉じる", "赴く", "葬る",
    "貶める", "崇める", "省みる",
    "強欲", "時代錯誤", "背教", "神秘", "禁欲",
    "至福", "無常", "偉大さ", "背信", "官能",
    "忌まわしさ", "未来", "偽善",
    "専制主義", "昏睡", "霊性", "忘却",
    "悪行", "不活動", "狂乱", "迷宮",
    "嗜眠", "偽善", "殉難", "闇",
    "不敬", "光輪", "万神殿", "田園",
    "紆余曲折", "炎", "嘆き", "壮麗",
    "子孫", "前兆", "誘惑", "帰属",
    "洞察", "荒野", "悪", "混乱",
    "薄暮", "虚栄", "叱責", "思索",
    "宿命", "現象", "混沌", "恍惚",
    "強欲な", "外典の", "古風な", "禁欲的な",
    "至福の", "無常の", "荘厳な", "忌まわしい",
    "老朽化した", "忘れられた", "不吉な", "はかない",
    "本来の", "偽善的な", "陰鬱な", "不敬な",
    "言い表せない", "取るに足らない", "燃えるような", "原初的な",
    "幽冥の", "神聖な", "悲痛な", "薄暮の",
    "束の間の", "厳粛な", "悲劇的な", "虚しい",
    "思索的な", "時代遅れの", "熱烈な",
})

# ── Chinese C2 ────────────────────────────────────────────────────────────────
_ZH_C2: frozenset[str] = frozenset({
    "憎恶", "诅咒", "崇拜", "悼念", "哀叹",
    "谩骂", "美化", "亵渎", "奉行",
    "嘲弄", "玩弄", "颂扬", "诽谤",
    "忏悔", "殉道", "前往", "埋葬",
    "贬低", "敬奉", "反省",
    "贪婪", "叛教", "神秘", "禁欲",
    "极乐", "无常", "伟大", "背信", "情欲",
    "可恶", "未来", "伪善",
    "专制主义", "昏迷", "灵性", "遗忘",
    "恶行", "惰性", "狂乱", "迷宫",
    "嗜睡", "虚伪", "殉难", "不虔诚", "光环", "万神殿", "田园",
    "曲折", "炎焰", "哀鸣", "壮丽",
    "后裔", "预兆", "诱惑", "归属",
    "洞察", "荒野", "邪恶", "混乱",
    "暮色", "虚荣", "责备", "玄思",
    "命运", "现象", "混沌", "狂喜",
    "贪婪的", "外典的", "古朴的", "禁欲的",
    "极乐的", "无常的", "雄伟的", "可恶的",
    "陈旧的", "被遗忘的", "不祥的", "短暂的",
    "固有的", "虚伪的", "阴郁的", "不虔诚的",
    "难以言表的", "微不足道的", "燃烧的", "原始的",
    "幽冥的", "神圣的", "悲痛的", "暮色的",
    "转瞬即逝的", "庄严的", "悲剧的", "徒劳的",
    "玄思的", "过时的", "狂热的",
})

# ── Arabic C2 ─────────────────────────────────────────────────────────────────
_AR_C2: frozenset[str] = frozenset({
    "يَكره", "يَلعن", "يعبد", "يَرثي", "يَندب",
    "يَشتم", "يُمجِّد", "يُدنِّس", "يَلتزم",
    "يَسخر", "يَعبث", "يُمجِّد", "يَفتري",
    "يَتوب", "يَستشهد", "يَغدو", "يَدفن",
    "يُهين", "يُبجِّل", "جَشَع", "أناكرونيزم", "ارتداد", "غموض", "زُهد",
    "نعيم", "فَناء", "عَظَمة", "خيانة", "شَهوة",
    "دَناءة", "مستقبل", "نفاق",
    "استبداد", "سُبات", "روحانية", "نسيان",
    "إثم", "خُمول", "هيجان", "متاهة",
    "خَدَر", "رياء", "استشهاد", "ظلام",
    "كفر", "هالة", "بانثيون", "رعوية",
    "تقلبات", "لهيب", "عويل", "جلال",
    "ذرية", "فأل", "إغراء", "انتماء",
    "بصيرة", "براري", "شر", "فوضى",
    "غسق", "خيلاء", "عتاب", "تأمّل",
    "قضاء", "ظاهرة", "فوضى", "نشوة",
    "جَشِع", "أبوكريفي", "زاهد",
    "نَعيمي", "فانٍ", "مهيب", "مقيت",
    "بالٍ", "منسي", "مشؤوم", "عابر", "منافق", "كئيب", "كافر",
    "لا يوصف", "تافه", "مشتعل", "بدائي",
    "أخروي", "مقدَّس", "محزن", "شفقي",
    "عابر", "مهيب", "مأساوي", "باطل",
    "تأملي", "بائد", })

# ── Hebrew C2 ─────────────────────────────────────────────────────────────────
_HE_C2: frozenset[str] = frozenset({
    "לשנוא", "לקלל", "לסגוד", "לאבל", "להתאונן",
    "לגדף", "לפאר", "לחלל", "לדבוק",
    "ללעוג", "לשעשע", "לשבח", "להשמיץ",
    "לחזור בתשובה", "להיות קדוש", "ללכת", "לקבור",
    "להשפיל", "לכבד", "חמדנות", "כפירה", "מסתורין", "פרישות",
    "אושר עליון", "חולפות", "גדולה", "בגידה", "תאווה",
    "שפלות", "עתיד", "צביעות",
    "עריצות", "תרדמת", "רוחניות", "שכחה",
    "עוון", "אדישות", "התפרצות", "מבוך",
    "נרדמות", "חנופה", "קידוש השם", "חשכה",
    "כפירה", "הילה", "פנתיאון", "פסטורלי", "להבה", "יללה", "הדר",
    "צאצאים", "סימן", "פיתוי", "שייכות",
    "תובנה", "ישימון", "רשע", "תוהו",
    "דמדומים", "יוהרה", "תוכחה", "הרהור",
    "גזרה", "תופעה", "כאוס", "אקסטזה",
    "חמדן", "אפוקריפי", "ארכאי", "פרוש",
    "עליון", "חולף", "אדיר", "מתועב",
    "ישן נושן", "נשכח", "מזעזע", "ראשוני", "צבוע", "קודר", "כופר",
    "שאין לתארו", "בוער", "קדמוני",
    "שאחרי המוות", "קדוש", "של שחר",
    "חולף", "חגיגי", "טרגי", "לשווא",
    "הרהורי", "מיושן", "נלהב",
})

#: Map from language code to frozenset of C2 lemmas (excludes A1–C1 items).
C2: dict[str, frozenset[str]] = {
    "es": _ES_C2,
    "fr": _FR_C2,
    "de": _DE_C2,
    "it": _IT_C2,
    "pt": _PT_C2,
    "ru": _RU_C2,
    "ja": _JA_C2,
    "zh": _ZH_C2,
    "ar": _AR_C2,
    "he": _HE_C2,
    "fi": _FI_C2,
    "tr": _TR_C2,
    "hi": _HI_C2,
}
