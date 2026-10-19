"""Configuration du fil : domaines, sources et réglages.

Pour ajouter un domaine, copie un bloc de DOMAINS et adapte-le :
  - feeds    : flux RSS de vulgarisation (apportent l'image + un texte accessible)
  - epmc     : requête Europe PMC (PubMed + préprints bioRxiv/medRxiv/SportRxiv...)
  - openalex : identifiant de "field" OpenAlex (toute la science, revues "core" uniquement)
  - keywords : (optionnel) mots qui font remonter un article de vulgarisation
  - vulga / papers : nombre de cartes de chaque type par édition
Liste des fields OpenAlex : https://api.openalex.org/fields
"""

SX = "https://phys.org/rss-feed/"
MX = "https://medicalxpress.com/rss-feed/"

# Filtre "études sérieuses" réutilisé dans plusieurs requêtes Europe PMC
QUALITY = ('(PUB_TYPE:"randomized controlled trial" OR PUB_TYPE:"meta-analysis" '
           'OR PUB_TYPE:"systematic review" OR SRC:PPR)')

DOMAINS = [
    {
        "id": "chimie", "label": "Chimie", "emoji": "⚗️", "color": "#0ea5e9",
        "feeds": [SX + "chemistry-news/"],
        "openalex": 16,  # Chemistry
        "vulga": 1, "papers": 2,
    },
    {
        "id": "biochimie", "label": "Biochimie", "emoji": "🧬", "color": "#8b5cf6",
        "feeds": [SX + "chemistry-news/biochemistry/"],
        "openalex": 13,  # Biochemistry, Genetics and Molecular Biology
        "vulga": 1, "papers": 2,
    },
    {
        "id": "medicaments", "label": "Médicaments", "emoji": "💊", "color": "#ef4444",
        "feeds": [MX + "medications-news/"],
        "epmc": ('(drug OR inhibitor OR agonist OR antagonist OR antibody OR "first-in-human" OR pharmacokinetics) AND '
                 '(PUB_TYPE:"randomized controlled trial" OR PUB_TYPE:"clinical trial, phase iii" '
                 'OR PUB_TYPE:"clinical trial, phase ii" '
                 'OR (SRC:PPR AND (randomized OR randomised) AND (placebo OR "phase 2" OR "phase 3")))'),
        "vulga": 1, "papers": 2,
    },
    {
        "id": "muscu", "label": "Musculation", "emoji": "🏋️", "color": "#f97316",
        "feeds": [MX + "fitness-news/", MX + "sports-medicine-news/"],
        "keywords": ["muscle", "strength", "resistance", "weight", "hypertrophy", "protein", "creatine",
                     "exercise", "training", "athlete"],
        "epmc": ('("resistance training" OR "strength training" OR "resistance exercise" '
                 'OR "muscle hypertrophy" OR "muscle protein synthesis" OR "blood flow restriction") AND ' + QUALITY),
        "vulga": 1, "papers": 2,
    },
    {
        "id": "nutrition", "label": "Nutrition", "emoji": "🥗", "color": "#22c55e",
        "feeds": [MX + "nutrition-healthy-eating-news/"],
        "keywords": ["supplement", "protein", "creatine", "caffeine", "fasting", "diet", "vitamin", "metabol"],
        "epmc": ('(creatine OR "protein supplementation" OR "whey protein" OR caffeine OR "dietary supplement" '
                 'OR "intermittent fasting" OR "time-restricted eating" OR "ketogenic diet") AND ' + QUALITY),
        "vulga": 1, "papers": 1,
    },
    {
        "id": "neuro", "label": "Neuro & sommeil", "emoji": "🧠", "color": "#ec4899",
        "feeds": [MX + "sleep-news/", MX + "neurology-news/"],
        "openalex": 28,  # Neuroscience
        "vulga": 1, "papers": 1,
    },
    {
        "id": "longevite", "label": "Longévité", "emoji": "⏳", "color": "#14b8a6",
        "feeds": [MX + "healthy-aging-news/"],
        "epmc": ('TITLE:(longevity OR lifespan OR senescence OR senolytic OR rapamycin OR "epigenetic clock" '
                 'OR "biological age" OR "healthy aging" OR "healthy ageing" OR geroscience) '
                 'AND (aging OR ageing OR older OR mice OR human OR cells OR cellular)'),
        "keywords": ["longevity", "lifespan", "senescen", "biological ag", "dementia", "reprogramm",
                     "mitochond", "epigenetic", "during aging", "reversing age", "glp-1", "alzheimer"],
        "vulga": 1, "papers": 1,
    },
    {
        "id": "physique", "label": "Physique & astro", "emoji": "🔭", "color": "#6366f1",
        "feeds": [SX + "physics-news/", SX + "space-news/astronomy/"],
        "openalex": 31,  # Physics and Astronomy
        "vulga": 1, "papers": 1,
    },
]

# Cartes "exotiques" pour s'ouvrir à d'autres thèmes (tirées au hasard)
EXOTIC = {
    "count": 3,
    "feeds": [
        SX + "science-news/archaeology/",
        SX + "earth-news/",
        SX + "biology-news/",
        "https://techxplore.com/rss-feed/",
        "https://api.quantamagazine.org/feed/",
    ],
}

# Revues réputées : bonus de classement pour les papiers
TOP_JOURNALS = [
    "nature", "science", "cell", "pnas", "proceedings of the national academy", "elife",
    "journal of the american chemical society", "angewandte", "chem", "acs central science",
    "chemical science", "new england journal", "lancet", "jama", "bmj", "nature medicine",
    "sports medicine", "british journal of sports medicine", "medicine and science in sports",
    "medicine & science in sports", "journal of applied physiology", "journal of physiology",
    "journal of strength and conditioning", "j strength cond res", "scandinavian journal of medicine",
    "european journal of applied physiology", "american journal of clinical nutrition",
    "journal of the international society of sports nutrition", "nutrients", "aging cell",
    "neuron", "sleep", "physical review letters", "astrophysical journal", "molecular cell",
    "j cachexia sarcopenia muscle", "journal of cachexia", "geroscience", "nature aging",
]

LOOKBACK_DAYS = 7        # fenêtre de recherche au premier lancement
MAX_EDITIONS = 30        # éditions conservées dans l'historique
SUMMARY_CHARS = 340      # longueur max d'une description
# palier gratuit de l'API Gemini (secret GEMINI_API_KEY), essayés dans l'ordre
GEMINI_MODELS = ["gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.5-flash-lite"]
