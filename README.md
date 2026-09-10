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
| Planification | Planificateur de tâches Windows | `refresh` est un script à lancer, pas un démon à surveiller |
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
│   ├── risk_engine/     # Mesures de risque
│   │   ├── measures.py  #   fonctions pures : tableaux → nombres
│   │   ├── returns.py   #   rendements et alignement des dates
│   │   ├── portfolio.py #   chargement SQLite, poids en valeur
│   │   ├── engine.py    #   composition + fenêtre d'estimation
│   │   └── config.py    #   taux sans risque, fenêtre, λ EWMA
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
python -m backend.ingestion backfill   # chargement initial : 14 titres depuis 2005
python -m backend.ingestion refresh    # rattrapage, à lancer quotidiennement
python -m backend.ingestion add TSLA   # titre hors univers de dev
python -m backend.ingestion status     # inventaire de la base, sans appel réseau
```

Un titre inconnu coûte 2 appels (métadonnées + prix), un titre déjà en base un
seul : les métadonnées ne changent quasiment jamais et ne sont redemandées que
sur `--refresh-metadata`. Le plan gratuit autorise 50 appels par heure et 1000
par jour. `refresh` ne redemande que la fenêtre manquante depuis la dernière
séance connue de chaque titre : la machine peut rester éteinte une semaine sans
laisser de trou. Le code de sortie vaut 1 si un titre a échoué, pour qu'un
ordonnanceur le voie.

**La profondeur est ancrée à une date fixe, pas à une durée glissante.**
`BACKFILL_START = 2005-01-01` dans `backend/ingestion/universe.py`. Une fenêtre
exprimée en années cesse silencieusement de couvrir un événement à mesure que
le temps passe : « 5 ans » couvrait le krach COVID jusqu'en mars 2025, puis a
cessé de le faire sans que rien ne change dans le code ni n'échoue. Le scénario
disparaît en douce, et on ne s'en aperçoit qu'en lisant des résultats qui ne
veulent plus dire ce qu'on croit. Une date d'ancrage ne peut qu'étendre la
couverture. 2005 donne les trois scénarios de stress — crise financière 2008,
COVID 2020, baisse 2022 — avec trois ans de contexte avant 2008.

Un titre introduit en bourse après cette date entre avec l'historique qui
existe : le fournisseur renvoie ce qu'il a, et `status` montre la couverture
réelle obtenue titre par titre.

> **Cette profondeur sert au rejeu de scénarios, pas à l'estimation du risque
> courant.** Une VaR historique ou une volatilité annualisée calculées sur les
> 21 ans complets seraient dominées par 2008 : elles décriraient un régime de
> marché révolu, pas le risque d'aujourd'hui. Le moteur de risque (Phase 4)
> doit estimer sur une fenêtre récente (1 à 2 ans) ou pondérer les rendements
> exponentiellement (EWMA, façon RiskMetrics). L'historique long n'est là que
> pour rejouer des périodes de crise identifiées sur les poids actuels du
> portefeuille.

### 5. Moteur de risque

```python
from backend.db.init_db import connect
from backend.risk_engine import analyse_portfolio

with connect() as conn:
    rapport = analyse_portfolio(conn, portfolio_id=1)      # fenêtre 504 par défaut
    print(rapport.volatility.annualised, rapport.volatility.window)
```

**Rendements : simples entre titres, log dans le temps.** Le rendement d'un
portefeuille est la moyenne pondérée des rendements **simples** de ses lignes
(`r_p = Σ wᵢ·rᵢ`), parce que la valeur du portefeuille est la somme des valeurs
des lignes. Les rendements log, eux, s'additionnent dans le temps — c'est ce qui
justifie la règle du √T — mais pas entre titres : `ln(Σ wᵢ(1+rᵢ)) ≠ Σ wᵢ·ln(1+rᵢ)`.
L'écart est faible au quotidien et se creuse sur les grandes variations, donc
précisément dans les queues de distribution que le risque cherche à mesurer.

**Poids constants.** Les poids d'aujourd'hui, en valeur de marché, sont
appliqués à tout l'historique : c'est l'hypothèse de rééquilibrage quotidien,
qui répond à « quel risque porte l'allocation que je détiens ? ». L'alternative
buy-and-hold, à poids dérivants depuis une date d'achat, mesure une performance
réalisée — une autre question.

**Alignement par date.** Les séries sont appariées sur la date, jamais par
position dans le tableau : seules les séances où tous les titres cotent sont
retenues. Une séance manquante sur un seul titre décalerait sinon toute sa série
d'un cran, sans que rien ne le signale.

**Fenêtre d'estimation.** Paramètre explicite, 504 séances (2 ans) par défaut.
Chaque résultat porte la fenêtre utilisée et le nombre d'observations
effectivement retenu, ainsi qu'un indicateur `complete` si l'historique n'a pas
suffi. Une volatilité de 18 % ne veut pas dire la même chose estimée sur deux ans
ou sur vingt, et rien dans le nombre seul ne permet de le deviner.

| Mesure | Convention | Hypothèse à connaître |
|---|---|---|
| Volatilité | écart-type × √252 | le √T suppose des rendements i.i.d. — ni l'autocorrélation ni le regroupement de volatilité ne le respectent |
| Volatilité EWMA | `σ²ₜ = λσ²ₜ₋₁ + (1−λ)r²ₜ₋₁`, λ = 0,94 | sans centrage (convention RiskMetrics quotidienne) : sur une série constante non nulle, elle rend `\|r\|·√252` là où l'écart-type rend 0 |
| Max drawdown | pic **glissant** | un pic global postérieur au creux mesurerait une perte impossible à subir |
| Sharpe | `√252 × moy(r−rf) / σ(r−rf)` | annualisé une seule fois ; `rf` retranché aux deux termes |
| Sortino | `√252 × moy(r−cible) / DD` | `DD` divise par le nombre **total** de périodes, pas par le seul compte des négatives |
| HHI | `Σ wᵢ²`, référence `1/N` | positions longues uniquement — un poids négatif est refusé, pas calculé |

Chaque résultat porte sa provenance : la fenêtre d'estimation pour les mesures
estimées sur un historique, la **date de valorisation** pour le HHI
(`ConcentrationResult.valuation_date`), qui est ponctuel et n'a pas de fenêtre.
Aucun chiffre ne doit être ininterprétable isolément.

Le refus d'un poids négatif est délibérément une exception levée par le moteur :
rendre un nombre ininterprétable serait pire qu'échouer. Il revient à la couche
de présentation (Phase 7) d'attraper cette `ValueError` et d'afficher le reste
du rapport — volatilité, drawdown, Sharpe et Sortino restent valides sur un
portefeuille long/short — en signalant la seule concentration comme non
calculable.

**Taux sans risque : 3,90 %**, bons du Trésor américain à 13 semaines,
**équivalent coupon**, observé le **9 septembre 2026**. Défini dans `config.py`
et converti géométriquement en taux quotidien.

Deux précisions qui comptent. D'abord, c'est l'équivalent coupon et non le taux
d'escompte : ce dernier rapporte la décote à la valeur *faciale* du bon sur une
année de 360 jours, alors qu'on achète sous le pair et qu'on détient 365 jours.
Il sort donc plus bas que le rendement réel, et l'utiliser gonflerait les
rendements excédentaires — donc le Sharpe — sans qu'aucun calcul ne soit faux
par ailleurs.

Ensuite, la date d'observation est inscrite à côté de la valeur
(`RISK_FREE_RATE_OBSERVED_ON`) et voyage avec le résultat
(`SharpeResult.risk_free_observed_on`). Ce taux a bougé de 6 points de base en
une semaine : sans date, la constante devient une hypothèse invisible dont plus
personne ne peut juger la péremption. Un taux surchargé par
`MX_RISK_FREE_RATE=0.035` dans `.env` ressort avec une date `None` — le moteur
ne sait pas d'où vient une valeur qu'on lui impose.

Quand aucun rendement de la fenêtre ne passe sous la cible, le Sortino vaut
`None` et non `inf` : le ratio est indéfini, pas infini, et une valeur infinie se
propagerait dans un tableau de bord en se faisant passer pour un résultat.

### 6. Tests

```powershell
pytest
```

Aucun test ne sort sur le réseau : la session HTTP et le fournisseur sont
remplacés par des doubles. La suite passe hors ligne et ne consomme pas de
quota.

### 7. API

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
- [x] **Phase 3 — Ingestion** : adaptateur Tiingo, backfill ancré à 2005,
  rattrapage, chargement à la demande, retries sur quota
  - Pas de job APScheduler : écarté volontairement. `refresh` est appelé par le
    Planificateur de tâches Windows ou à la main — un démon à surveiller
    coûterait plus que le problème qu'il résout pour un batch quotidien.
- [x] **Phase 4A — Moteur, mesures d'une série** : rendements simples/log,
  poids en valeur, fenêtre d'estimation, volatilité (écart-type et EWMA), max
  drawdown, Sharpe, Sortino, HHI
  - [ ] **Phase 4B** : covariance, corrélation, beta vs benchmark, VaR
    historique et paramétrique, CVaR
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
