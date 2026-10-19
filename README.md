# Synapse — ton fil d'actualité scientifique

Une web app installable sur ton téléphone qui te propose ~23 cartes **3 fois par semaine**
(lundi, mercredi, vendredi) : titre + image + courte description, tu cliques pour lire.

- **Domaines** : Chimie, Biochimie, Médicaments, Musculation, Nutrition, Neuro & sommeil,
  Longévité, Physique & astro + 3 cartes « Hors des sentiers battus » tirées au hasard.
- **Niveau mixte** : chaque domaine mélange un article de vulgarisation (avec vraie image)
  et des papiers bruts (couverture générée, résumé = conclusion de l'abstract).
- **Badge 🔓 Texte intégral gratuit** : seulement des versions légales (revues open access,
  PubMed Central, préprints, dépôts d'auteurs — données Unpaywall via OpenAlex).
- **★ À lire** : tes favoris, conservés d'une édition à l'autre (sur ton téléphone).
- 100 % gratuit, aucune clé API obligatoire.

## Mise en ligne (15 minutes, une seule fois)

1. **Crée un compte** sur <https://github.com> si besoin.
2. **Crée un dépôt public** nommé `synapse` (bouton *New repository*, coche rien d'autre).
3. **Envoie les fichiers.** Le plus simple : installe [GitHub Desktop](https://desktop.github.com),
   *File → Add local repository* sur ce dossier, puis *Publish repository*.
   Ou en ligne de commande, depuis ce dossier :
   ```bash
   git init -b main
   git add .
   git commit -m "Synapse v1"
   git remote add origin https://github.com/TON-PSEUDO/synapse.git
   git push -u origin main
   ```
4. **Active le site** : dans le dépôt → *Settings → Pages* → *Source : Deploy from a branch* →
   branche `main`, dossier `/docs` → *Save*.
5. **Autorise la mise à jour automatique** : *Settings → Actions → General* →
   *Workflow permissions* → **Read and write permissions** → *Save*.
6. **Teste** : onglet *Actions* → « Nouvelle édition » → *Run workflow*. Une minute plus tard,
   une nouvelle édition apparaît.
7. **Sur ton téléphone**, ouvre `https://TON-PSEUDO.github.io/synapse/` puis
   - iPhone (Safari) : Partager → *Sur l'écran d'accueil*
   - Android (Chrome) : ⋮ → *Installer l'application*

## Personnaliser

Tout se règle dans [`collector/config.py`](collector/config.py) :
ajouter un domaine, changer les mots-clés, le nombre de cartes, la liste des revues favorites,
les flux « exotiques ». Les horaires sont dans [`.github/workflows/update.yml`](.github/workflows/update.yml).

Tester en local : `python collector/collect.py` puis `python -m http.server 8765 --directory docs`
et ouvrir <http://localhost:8765>.

### Options gratuites

- **Résumés IA en français + « L'essentiel de l'édition »** (Gemini, palier gratuit) : crée une clé sur
  <https://aistudio.google.com/apikey>, puis ajoute-la dans
  *Settings → Secrets and variables → Actions → New repository secret* sous le nom `GEMINI_API_KEY`.
  Sur le palier gratuit, Google peut utiliser les textes envoyés (ici, des abstracts publics).

- **Résumés TL;DR d'une phrase** (IA de Semantic Scholar) : demande une clé gratuite sur
  <https://www.semanticscholar.org/product/api#api-key-form>, puis ajoute-la dans
  *Settings → Secrets and variables → Actions* sous le nom `S2_API_KEY`.
- `OPENALEX_MAILTO` (même endroit) : ton email, pour des requêtes OpenAlex plus rapides.

## Sources

| Rôle | Source |
|---|---|
| Vulgarisation + images | Phys.org, Medical Xpress, Tech Xplore, Quanta Magazine (RSS) |
| Papiers biomédicaux, muscu, nutrition, médicaments | Europe PMC (PubMed + préprints medRxiv, bioRxiv, SportRxiv…) |
| Papiers chimie, biochimie, neuro, physique | OpenAlex (revues « core » uniquement) |
| Liens texte intégral légaux | OpenAlex / Unpaywall, PubMed Central |

## Idées v2

- Résumé audio / podcast de l'édition (synthèse vocale des descriptions, ou envoi des
  papiers en libre accès dans NotebookLM pour un podcast à deux voix).
- Bouton « moins de ça » pour affiner le fil.
- Résumés et traduction en français par IA (quelques € par mois).
