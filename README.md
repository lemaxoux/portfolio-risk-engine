# Mx Risk MGT

Moteur d'analyse de risque de portefeuille pour actions et ETF cotés US, avec
une API et une interface simple pour l'exposer.

## Objectif

Calculer, sur un portefeuille saisi manuellement ou importé en CSV, les mesures
de risque standard de la gestion quantitative — volatilité annualisée, VaR
historique et paramétrique, CVaR / Expected Shortfall, max drawdown, ratios de
Sharpe et Sortino, beta vs benchmark, matrice de corrélation, indice de
concentration (HHI) — puis mesurer l'impact de scénarios de crise réels
(krach COVID de février-mars 2020, baisse 2022) sur les poids actuels.

La priorité du projet est la **justesse des calculs** : chaque mesure est testée
contre des jeux de données synthétiques à résultat connu, et documentée avec ses
hypothèses et ses limites. Un README de méthodologie complet fait partie du
livrable, au même titre que le code.

### Périmètre v1 (volontairement étroit)

- Une seule classe d'actifs : actions / ETF cotés US.
- Un seul utilisateur, accès local — pas de multi-tenant ni d'authentification.
- Portefeuille saisi à la main ou importé en CSV, pas d'agrégation bancaire.
- Base SQLite locale, ingestion par job batch quotidien.

## Stack

| Composant | Choix | Pourquoi |
|---|---|---|
| Langage | Python 3.12 | Écosystème quant standard |
| Calcul | numpy, pandas, scipy | Séries temporelles et statistiques |
| API | FastAPI + uvicorn | Léger, typé, doc OpenAPI auto-générée |
| Base | SQLite | Suffisant pour un projet solo, aucun setup |
| Données de marché | Tiingo (plan gratuit) | 30+ ans d'historique quotidien ajusté, 1000 appels/jour |
| Planification | APScheduler | Job d'ingestion quotidien |
| Tests | pytest | Priorité aux tests du moteur de risque |
| Config | python-dotenv | Clé API hors du code |

Le fournisseur de prix est isolé derrière le module `backend/data_provider` :
aucun appel direct à l'API Tiingo ailleurs dans le code, pour qu'un changement
de fournisseur ne demande de réécrire qu'un seul adaptateur.

## Arborescence

```
app/
├── backend/
│   ├── data_provider/   # Accès aux prix — seul module qui connaît Tiingo
│   │   ├── base.py      #   contrat agnostique (DailyBar, erreurs)
│   │   └── tiingo.py    #   adaptateur : URLs, champs JSON, retries
│   ├── ingestion/       # Backfill, rattrapage, chargement à la demande
│   │   ├── universe.py  #   14 titres de dev et leurs secteurs
│   │   └── prices.py    #   écriture en base
│   ├── risk_engine/     # Calcul des mesures de risque
│   ├── api/             # Endpoints FastAPI
│   └── db/              # Schéma SQLite et initialisation
│       ├── schema.sql
│       └── init_db.py
├── data/                # Base SQLite locale (non versionnée)
├── frontend/            # Interface
├── tests/               # Tests unitaires
├── .env.example
└── requirements.txt
```

## Lancer le projet en local

Prérequis : **Python 3.12** (`python --version`).

### 1. Environnement virtuel

```powershell
# Depuis app/
python -m venv venv
.\venv\Scripts\Activate.ps1        # Windows PowerShell
# source venv/bin/activate         # macOS / Linux
pip install -r requirements.txt
```

### 2. Configuration

```powershell
copy .env.example .env             # cp .env.example .env  sur macOS / Linux
```

Puis renseigner `TIINGO_API_KEY` dans `.env` (clé disponible sur
<https://api.tiingo.com/account/api/token>). `.env` est ignoré par git.

### 3. Base de données

```powershell
python -m backend.db.init_db
```

Crée `data/mx_risk.sqlite` avec les quatre tables du schéma. La commande est
idempotente : la relancer ne détruit aucune donnée.

### 4. Ingestion des prix

```powershell
python -m backend.ingestion backfill   # chargement initial : 14 titres, 5 ans
python -m backend.ingestion refresh    # rattrapage, à lancer quotidiennement
python -m backend.ingestion add TSLA   # titre hors univers de dev
python -m backend.ingestion status     # inventaire de la base, sans appel réseau
```

Le backfill consomme 2 appels par titre (métadonnées + prix), soit 28 pour
l'univers complet — le plan gratuit en autorise 50 par heure et 1000 par jour.
`refresh` ne redemande que la fenêtre manquante depuis la dernière séance
connue de chaque titre : la machine peut rester éteinte une semaine sans
laisser de trou. Le code de sortie vaut 1 si un titre a échoué, pour qu'un
ordonnanceur le voie.

> **Profondeur et stress tests.** Cinq ans à partir de septembre 2026 remontent
> à septembre 2021 : la fenêtre couvre la baisse 2022 mais **pas** le krach
> COVID de février-mars 2020. Le scénario COVID de la Phase 5 demandera
> `BACKFILL_YEARS = 7` dans `backend/ingestion/universe.py` et un nouveau
> backfill complet.

### 5. Tests

```powershell
pytest
```

Aucun test ne sort sur le réseau : la session HTTP et le fournisseur sont
remplacés par des doubles. La suite passe hors ligne et ne consomme pas de
quota.

### 6. API

```powershell
uvicorn backend.api.main:app --reload
```

Documentation interactive sur <http://127.0.0.1:8000/docs>.
**Pas encore disponible** — l'API sera construite après le moteur de risque.

## Schéma de données

Quatre tables (`backend/db/schema.sql`) :

| Table | Contenu | Clé |
|---|---|---|
| `securities` | Univers de titres suivis | `ticker` |
| `prices` | Historique quotidien OHLC + clôture ajustée + volume | `(ticker, date)` |
| `portfolios` | Portefeuilles et leur propriétaire | `id` |
| `positions` | Lignes d'un portefeuille (quantité, prix de revient optionnel) | `id`, unique sur `(portfolio_id, ticker)` |

Deux points de conception qui comptent pour la suite :

- **`prices.adj_close` est la seule colonne à utiliser pour les rendements.**
  Elle est ajustée des splits et des dividendes ; `close` brut fausserait les
  séries à chaque détachement de dividende.
- **La clé primaire `(ticker, date)` rend l'ingestion idempotente.** Un backfill
  rejoué ne crée pas de doublons.

Les dates sont stockées en TEXT au format ISO-8601 `YYYY-MM-DD` : SQLite n'a pas
de type date natif, et pour ce format l'ordre lexicographique coïncide avec
l'ordre chronologique.

## État d'avancement

- [x] **Phase 2 — Setup** : repo, venv, arborescence, schéma SQLite, README
- [x] **Phase 3 — Ingestion** : adaptateur Tiingo, backfill 5 ans (14 titres,
  17 570 séances), rattrapage, chargement à la demande, retries sur quota
  - [ ] Reste à faire : job batch quotidien (APScheduler)
- [ ] **Phase 4 — Moteur de risque** : mesures + tests unitaires
- [ ] **Phase 5 — Stress testing** : scénarios historiques
- [ ] **Phase 6 — Recommandations** : règles de détection
- [ ] **Phase 7 — Frontend** : saisie, dashboard, vue stress test
- [ ] **Phase 8 — Documentation** : README méthodologie
- [ ] **Phase 9 — Publication**

## Données de marché

Les prix proviennent du plan gratuit de Tiingo, dont les conditions restreignent
le stockage persistant et le partage. Le projet reste non commercial et à usage
privé : la base locale n'est pas versionnée, et ce que l'application expose sont
les métriques de risque calculées, pas les séries de prix brutes.

## Avertissement

Ce projet est un outil personnel d'analyse. Il ne constitue pas un conseil en
investissement au sens réglementaire, et les mesures qu'il produit reposent sur
des hypothèses statistiques dont les limites sont documentées.
