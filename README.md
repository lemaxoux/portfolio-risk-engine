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
| Tests | pytest, Vitest | Priorité aux tests du moteur de risque |
| Config | python-dotenv | Clé API hors du code |
| Frontend | Vite + React + TypeScript | Six vues en lecture seule : ni SSR, ni routes serveur, ni SEO. Next.js ajouterait une toolchain complète pour rien |
| Styles | CSS Modules + variables CSS | L'intérêt d'un framework utilitaire est le stylage ad hoc — c'est-à-dire ce qui éroderait le jeu de tokens de `DESIGN.md` |
| Types de l'API | openapi-typescript | Engendrés depuis un schéma commité, jamais écrits à la main |

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
│   │   ├── measures.py  #   pur : vol, drawdown, Sharpe, Sortino, HHI
│   │   ├── covariance.py#   pur : matrices, variance de portefeuille, beta
│   │   ├── var.py       #   pur : VaR, Expected Shortfall, Monte Carlo
│   │   ├── scenarios.py #   catalogue des épisodes — données seules
│   │   ├── stress.py    #   pur : trajectoire achat-conservation
│   │   ├── regime.py    #   pur : ratio d'amplification, prédiction du beta
│   │   ├── returns.py   #   rendements et alignement des dates
│   │   ├── portfolio.py #   chargement SQLite, poids en valeur
│   │   ├── engine.py    #   composition + fenêtre d'estimation
│   │   └── config.py    #   taux sans risque, fenêtre, ddof, λ EWMA
│   ├── typography.py    # Espaces insécables du texte rédigé côté serveur
│   ├── rules/           # Moteur de règles — décrit, ne prescrit pas
│   │   ├── rules.py     #   les six règles et leurs observations
│   │   ├── thresholds.py#   seuils et provenance
│   │   └── disclaimer.py#   texte du bandeau d'acceptation
│   ├── api/             # HTTP — ne calcule rien, ne fait aucun SQL
│   │   ├── app.py       #   application FastAPI, liée à 127.0.0.1
│   │   ├── schemas.py   #   schémas pydantic, champ par champ
│   │   ├── validation.py#   contrôle des positions soumises
│   │   ├── csv_import.py#   lecture CSV (Excel français compris)
│   │   ├── errors.py    #   exceptions → codes HTTP utilisables
│   │   ├── dependencies.py # connexion SQLite par requête
│   │   └── routes/      #   méta, univers, portefeuilles, analyse
│   └── db/              # Schéma SQLite, initialisation, écritures
│       ├── schema.sql
│       ├── init_db.py
│       ├── migrate.py   #   ALTER TABLE explicites, idempotents
│       └── portfolios.py#   écriture des portefeuilles et positions
├── data/                # Base SQLite locale (non versionnée)
├── frontend/            # Interface — Vite + React + TypeScript
│   ├── DESIGN.md        #   spécification visuelle, à lire avant tout CSS
│   ├── src/styles/      #   tokens.css : SEUL fichier avec des valeurs brutes
│   ├── src/api/         #   openapi.json commité + types ENGENDRÉS
│   ├── src/lib/         #   format.ts : seul endroit qui écrit un nombre
│   ├── src/components/  #   Measure, Provenance, Bandeau, ThemeToggle
│   └── src/views/       #   écran d'acceptation, sections de l'analyse
├── tools/               # Outils de développement, hors application
│   ├── openapi_schema.py#   écrit le schéma OpenAPI que le frontend compile
│   └── espace_fine.py   #   engendre la police de l'espace fine (U+202F)
├── tests/               # Tests unitaires
├── .env.example
├── CLAUDE.md            # conventions et commandes, en une page, pour Claude Code
├── requirements.txt         # exécution
└── requirements-dev.txt     # pytest, httpx2
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
pip install -r requirements-dev.txt   # seulement pour lancer les tests
```

`requirements.txt` ne contient que ce dont l'application a besoin pour
tourner. Le client HTTP dont dépend le `TestClient` de FastAPI est dans
`requirements-dev.txt` : une application qui n'émet aucun appel sortant en
dehors de l'ingestion n'a pas à embarquer un client HTTP en production.

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

**Base déjà existante :** `init_db` crée en `IF NOT EXISTS`, il ne migre donc
pas. Les colonnes ajoutées à `portfolios` en phase 7A (`name`, `updated_at`)
demandent un passage explicite :

```powershell
python -m backend.db.migrate
```

Idempotent lui aussi, et sans écriture de données : `updated_at` reste `NULL`
sur les lignes antérieures, parce que leur date de modification n'est pas
connue. L'API refuse de démarrer sur une base non migrée, en indiquant la
commande — plutôt que d'échouer à la première requête sur un
« no such column ».

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

**Un split ou un dividende fait recharger tout l'historique du titre.** À
chacune de ces opérations, Tiingo recalcule tous les `adj_close` antérieurs à
la séance. Un rattrapage qui ne réécrirait que la fenêtre manquante mélangerait
deux bases d'ajustement, et le rendement de la séance de jonction mesurerait
l'écart entre elles au lieu du rendement réel. Ce défaut a existé jusqu'en
phase 7C, pour les dividendes. KO au 2026-09-09 : −1,51 % stocké contre
−0,92 % réel, pour un dividende de 0,53 détaché le 2026-09-15. SPY et NVDA
étaient touchés de la même façon. Dès qu'une séance récupérée porte `divCash`
non nul ou `splitFactor` différent de 1, `refresh` recharge l'historique
complet du titre et le remplace d'un bloc (`replace_history`), en journalisant
la raison. Le coût est d'un appel par titre et par opération, soit quatre par
an pour un titre à dividende trimestriel. Une reprise qui revient vide ne
supprime rien.

**Réparer une base écrite avant ce correctif : `rebuild`.** Le correctif
protège les rattrapages à venir, mais pas les jonctions déjà fausses. Il faut
les réparer par une commande explicite, jamais par effet de bord :

```powershell
python -m backend.ingestion rebuild                  # tous les titres en base
python -m backend.ingestion rebuild --tickers KO SPY # par lot
```

1. La commande vérifie d'abord le budget : un appel par titre, aucun de
   métadonnées. Au-delà de 50 appels, la limite horaire du plan gratuit, elle
   ne lance rien et demande des lots `--tickers` à une heure d'intervalle.
2. Elle copie la base vers `data/backup-AAAA-MM-JJ.sqlite` par l'API de
   sauvegarde de SQLite. Une sauvegarde existante n'est jamais écrasée : une
   deuxième le même jour prend le suffixe `-2`.
3. Elle recharge l'historique complet de chaque titre depuis
   `BACKFILL_START` et le remplace d'un bloc.
4. Elle affiche le nombre d'appels prévus, puis le nombre d'appels effectués.

Seule la table `prices` est réécrite. `portfolios`, `positions` et
`securities` ne sont pas touchées : un test le vérifie par l'autoriseur de
SQLite, qui voit chaque écriture tentée. Avec les 14 titres actuels, la
reconstruction coûte 14 appels. Un `refresh` lancé dans la même heure s'y
ajoute.

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
(`ConcentrationResult.as_of`), qui est ponctuel et n'a pas de fenêtre.
Aucun chiffre ne doit être ininterprétable isolément.

### Mesures multi-titres

| Mesure | Convention | Hypothèse à connaître |
|---|---|---|
| Covariance / corrélation | observations **complètes** | jamais paire à paire : des recouvrements différents selon les couples peuvent rendre la matrice non semi-définie positive |
| Beta / R² | `β = Cov(r_p, r_m)/Var(r_m)` | régression sur rendements **bruts**, pas excédentaires |
| VaR historique | quantile empirique, `method="lower"` | aucune hypothèse de loi ; ne peut rien dire d'un choc pire que la fenêtre ; refusée sous 1/(1 − α) séances, 20 à 95 %, 100 à 99 % (seuil dérivé) |
| VaR paramétrique | `−(μ + z_α·σ_p)`, `σ_p = √(wᵀΣw)` | normalité ; `μ = 0` par défaut |
| CVaR / ES | moyenne au-delà du quantile | porte son nombre d'observations de queue ; refusée avec la VaR historique du même niveau |
| Contribution à la variance | `wᵢ·(Σw)ᵢ / (wᵀΣw)` | somme exactement à 100 % ; poids ET corrélation ; peut être négative |
| Monte Carlo | Cholesky + tirages normaux, graine fixe | même hypothèse de normalité que la VaR paramétrique |
| Monte Carlo Student | ν par maximum de vraisemblance, échelle `S = Σ·(ν−2)/ν` | queues épaisses à covariance inchangée ; `ν ≤ 2` refusé ; `ν > 30` refusé, la Student ne se distinguant plus de la normale (seuil choisi) |

**Une seule convention de degrés de liberté : `config.DDOF = 1`.** numpy n'est
pas cohérent avec lui-même — `np.cov` utilise `ddof=1`, `np.std` et `np.var`
utilisent `ddof=0`. Si covariance et volatilité ne partageaient pas la même
convention, `√(wᵀΣw)` ne retomberait pas sur la volatilité de la série du
portefeuille : l'écart vaut `N/(N−1)`, soit 0,1 % sur 504 séances — assez petit
pour passer pour un arrondi, assez réel pour être une incohérence. C'est une
**identité algébrique**, pas une approximation, et un test la verrouille à la
tolérance flottante (sur données réelles, l'écart mesuré est exactement nul).

**Convention de signe : la VaR est une PERTE POSITIVE.** Une VaR 95 % de 0,021
se lit « perte d'au moins 2,1 % une séance sur vingt ». L'alternative — rendre
le rendement négatif du quantile — coexiste dans la littérature, et mélanger
les deux est la source classique des bugs de signe : les deux produisent des
nombres plausibles qui ne se contredisent que dans les inégalités. Une valeur
négative signifie donc un gain à ce niveau de confiance, pas une erreur.

**Le CVaR porte sa taille de queue.** À 99 % sur 504 séances, la moyenne ne
repose que sur 6 séances : le chiffre reste calculable, mais son incertitude n'a
rien à voir avec celle du même calcul à 95 %. `tail_observations` est porté par le
résultat, et à 99 % un avertissement y est attaché en permanence (`caveat`) : la
queue y est courte par construction, ce n'est pas une anomalie qu'un seuil
détecterait.

**Le Monte Carlo est une vérification croisée**, pas une redondance : sous
normalité, il doit converger vers la VaR paramétrique quand les tirages
augmentent. Un écart persistant signalerait une erreur dans l'une des deux
implémentations. Graine fixe : un chiffre de risque qui change à chaque
exécution n'est ni auditable ni comparable à celui de la veille.

**Le Monte Carlo en loi de Student chiffre le coût de l'hypothèse de
normalité.** Le Monte Carlo normal converge vers la VaR paramétrique par
construction : il valide le Cholesky, pas le modèle. Tirer en Student
multivariée donne à la simulation une raison d'exister. Activé par
`analyse_portfolio(..., monte_carlo=True)`.

- **ν par maximum de vraisemblance**, sur la série du portefeuille — sous une
  Student multivariée à ν commun, toute combinaison linéaire est une Student de
  même ν. Pas par la méthode des moments : `ν = 6/κ + 4` n'est définie que pour
  ν > 4 et ne peut structurellement jamais descendre en dessous, alors que les
  rendements actions quotidiens se situent entre 3 et 6. Et pas par
  `scipy.stats.t.fit` tel quel : sur la série réelle du portefeuille de
  démonstration, son optimisation par défaut s'arrête à ν = 2,01, treize unités
  de log-vraisemblance sous le vrai maximum (ν ≈ 4,07). L'estimateur retenu
  standardise les données et part de plusieurs valeurs de ν ; un test de
  non-régression sur cette série figée vérifie qu'il ne fait jamais moins bien
  que scipy.
- **Le piège de mise à l'échelle.** Une Student multivariée de matrice d'échelle
  S a pour covariance `S·ν/(ν−2)`, pas S. Passer la covariance empirique comme
  échelle rendrait les simulations plus volatiles d'un facteur `√(ν/(ν−2))` —
  +29 % à ν = 5 — et gonflerait la VaR pour une raison sans rapport avec les
  queues épaisses. D'où `S = Σ·(ν−2)/ν` : la covariance simulée égale Σ, et
  l'écart avec le Monte Carlo normal mesure la forme des queues, et rien d'autre.
  `ν ≤ 2` lève une erreur : la covariance n'existe pas.
- **La géométrie attendue se vérifie.** À variance égale, une loi leptokurtique
  a des épaules plus minces et des extrêmes plus lourds. Sur le portefeuille de
  démonstration (ν = 4,07, fenêtre au 9 septembre 2026), la VaR Student est moins
  sévère que la normale à 95 % (1,27 % contre 1,38 %) et plus sévère à 99 %
  (2,22 % contre 1,95 %) — la même géométrie que la VaR historique face à la
  paramétrique. Près de ν = 2, cette géométrie s'inverse : l'ajustement de
  variance y écrase les quantiles modérés. Un ν estimé à peine au-dessus de 2 est
  donc d'abord le symptôme probable d'un ajustement raté.
- **Au-delà de ν = 30, pas de Student : le quatrième seuil choisi à la main du
  projet** (`config.MAX_STUDENT_NU`, déclaré dans
  `rules.thresholds.STUDENT_NU_CEILING`). Le cinquième, en deçà : sous 30
  séances, pas d'ajustement du tout (`config.MIN_DISTRIBUTION_OBSERVATIONS`,
  déclaré dans `rules.thresholds.MIN_DISTRIBUTION_SAMPLE`).
  - *Le défaut.* La normale est la limite de la Student quand ν tend vers
    l'infini : sur des rendements sans queue épaisse, le maximum de
    vraisemblance pousse ν vers l'infini. Sur la base réelle, un titre seul sur
    une fenêtre courte rendait ν = 6 × 10¹⁵ (PG, 60 séances), et de 10¹² à
    10¹⁴ pour BAC, CVX, JNJ, NVDA, PFE et SPY. La provenance publiait ce
    nombre, et au-delà de 10²⁷ son écriture faisait tomber l'analyse en 500 —
    c'était le cas du portefeuille de démonstration demandé sur 60 séances.
  - *Pourquoi 30.* À variance égale, la VaR Student s'écarte de la normale de
    2,05 % au plus à 99 % et de 0,31 % au plus à 95 %, en relatif ; l'écart ne
    passe sous 2 % à 99 % qu'à partir de ν ≈ 30,7. C'est bien moins que
    l'erreur d'estimation elle-même : l'erreur type relative d'un écart-type
    d'échantillon vaut environ 1/√(2n), soit 9 % sur 60 séances et 3,2 % encore
    sur 504. Ce chiffre est calculé sous normalité ; avec des queues épaisses,
    l'erreur est plus grande encore, et l'argument est donc prudent.
    `tests/test_student.py` tient ces écarts.
  - *Un refus, pas un plafond.* Borner ν à 30 dans l'optimiseur publierait
    « ν = 30 » comme s'il avait été estimé. `var.fit_student_t` rend toujours
    son maximum ; c'est `engine.student_fit` qui refuse de s'en servir.
  - *Ce qui est publié* décrit un résultat, pas une panne, et n'écrit ni la
    valeur de ν ni le caractère : « Sur cette fenêtre de 60 séances, la loi de
    Student ne se distingue pas de la normale (degrés de liberté estimés
    supérieurs à 30, seuil choisi à la main) : les rendements ne montrent pas
    de queues plus épaisses que la normale. Sur une fenêtre courte, cela peut
    aussi signifier qu'aucun choc extrême n'y figure. »
  - *Ce que cela change.* Mesuré sur la copie figée : à 504 séances, rien — ni
    sur les quatorze titres seuls, ni sur le portefeuille de démonstration,
    dont la réponse est identique octet pour octet (ν = 4,07). Sur 60, 120 et
    252 séances, 15 des 45 cas passent en « Student refusée », dont des ν
    modérés juste au-dessus du seuil (PG 30,7, démonstration 34, JNJ 45).
  - `typography.number` écrit désormais tout nombre fini, jusqu'au plus grand
    flottant : la précision de `decimal` suit le nombre au lieu de rester à 28
    chiffres.

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
ne sait pas d'où vient une valeur qu'on lui impose. Celui qui impose un taux
peut en fournir la provenance avec lui :
`analyse_portfolio(conn, 1, annual_risk_free=0.035, risk_free_observed_on=date(...))`.
`None` signifie alors une date réellement inconnue, pas une date perdue en
chemin.

Quand aucun rendement de la fenêtre ne passe sous la cible, le Sortino vaut
`None` et non `inf` : le ratio est indéfini, pas infini, et une valeur infinie se
propagerait dans un tableau de bord en se faisant passer pour un résultat.

### 6. Scénarios de stress

```python
from backend.risk_engine import run_all_scenarios

for r in run_all_scenarios(conn, portfolio_id=1):
    print(r.summary())
```

**Les scénarios sont des données**, dans `scenarios.py` : nom, bornes, indice de
référence, description. En ajouter un ne demande de toucher à aucune logique.

| Épisode | Fenêtre | Amplitude S&P 500 |
|---|---|---|
| Crise financière 2008 | 2007-10-09 → 2009-03-09 | −55,2 % |
| Krach COVID | 2020-02-19 → 2020-03-23 | −33,7 % |
| Resserrement 2022 | 2022-01-03 → 2022-10-12 | −24,5 % |

Les fenêtres sont bornées **pic à creux**, pas par année civile : un scénario
« 2008 » calé sur le 1er janvier commencerait trois mois après le sommet et
manquerait le premier quart de la baisse. Ces dates sont **vérifiées par des
tests** contre l'historique en base : la date de début doit être le plus haut du
benchmark et la date de fin son plus bas, chacune sur une fenêtre élargie de trois
mois de part et d'autre. Vérifier le sommet à l'intérieur de la seule fenêtre ne
prouverait rien — le pic courant du premier jour est ce premier jour par
construction : un faux début placé le 11 août 2008, en pleine baisse, passait ce
contrôle naïf, et il est rejeté par le contrôle élargi. Une borne fausse ne se
verrait pas autrement : le calcul rendrait un chiffre plausible pour un épisode
qui n'est pas celui annoncé.

**Le portefeuille actuel entre dans l'épisode.** Au premier jour de la fenêtre,
chaque ligne pèse son poids d'aujourd'hui en valeur de marché ; les quantités qui
en découlent sont ensuite figées jusqu'à la fin. Appliquer les quantités
d'aujourd'hui aux cours de 2007 serait faux : une ligne qui pèse 15 % aujourd'hui
entrerait dans la crise à 2 %, et le rejeu porterait sur un portefeuille qui n'a
rien à voir avec celui détenu.

> **Rupture de convention assumée avec la Phase 4.** Le moteur calcule la série
> de rendements à **poids constants** ; pendant un scénario, ce sont les
> **quantités** qui restent constantes (achat-conservation). À un jour, l'écart est nul — les poids n'ont
> pas le temps de dériver. Sur les dix-sept mois de 2008, des poids constants
> supposent un rééquilibrage quotidien : vendre chaque jour ce qui a le mieux
> tenu pour racheter ce qui vient de chuter, pendant toute la descente. Ce n'est
> pas ce que fait un porteur passif, et lui prêter ce rééquilibrage donnerait un
> résultat plus flatteur que la réalité.

**Deux mesures distinctes**, à ne pas confondre : le rendement de **bout en
bout** (ce que vaut le portefeuille au dernier jour de l'épisode, le point bas
du marché, qui n'est pas la sortie de crise) et le **pire moment traversé**
(drawdown maximum intra-fenêtre), qui peut être plus profond. Le drawdown est
celui de la trajectoire du portefeuille, jamais la somme des pires points de
chaque ligne : cette dernière composerait un épisode fictif où toutes les lignes
toucheraient leur plancher le même jour.

**La couverture est déclarée, jamais silencieuse.** Un titre introduit en 2019
n'a rien à dire sur 2008. Trois comportements étaient possibles : faire échouer
tout le scénario (trop fragile), exclure la ligne en silence (dangereux — le
chiffre ne décrit plus qu'une partie du portefeuille et personne ne le voit), ou
déclarer la couverture. Chaque
résultat porte donc le nombre de lignes couvertes et **la fraction de la valeur**
qu'elles représentent — en valeur et non en nombre de lignes, parce qu'écarter
une ligne à 1 % et une ligne à 40 % n'ont pas la même portée. En couverture partielle,
les chiffres portent sur la seule partie couverte, poids renormalisés : les
lignes exclues ne sont **pas** supposées stables, ce qui diluerait la perte dans
une valeur non rejouée. `summary()` ne peut pas présenter un chiffre comme
couvrant l'ensemble quand ce n'est pas le cas, et sans aucune ligne couverte
aucun chiffre n'est produit.

> **Ce que le chiffre ne dit pas.** La perte du portefeuille entier. Les
> lignes exclues n'ont pas été rejouées, et rien ne mesure ce qu'elles
> auraient fait : la perte de l'ensemble a pu être plus lourde ou plus légère.
> Supposer ces lignes stables diluerait la perte dans une valeur non rejouée.
> Les exclure et renormaliser — l'option retenue — ne fabrique aucun
> rendement, mais ne décrit que la partie couverte, et la décrit d'autant
> moins que la couverture baisse ; `summary()` le rappelle. Une version
> précédente affirmait que la partie exclue, cotée plus récemment, était « en
> moyenne plus spéculative », et la perte « probablement sous-estimée ». Le
> moteur ne mesure ni l'un ni l'autre : ces formules ont été retirées de tous
> les textes publiés le 2026-10-05, et un test les y refuse.

Chaque scénario décompose la perte **ligne par ligne** : les contributions somment
exactement au rendement de bout en bout, et distinguent le rendement propre du
titre de son poids dans la perte — une petite ligne peut s'effondrer sans peser.

### Régime calme, régime de crise

```python
from backend.risk_engine import compare_all_regimes

for c in compare_all_regimes(conn, portfolio_id=1):
    print(c.summary())
```

Le résultat central de l'enchaînement Phase 4 → Phase 5 : le beta estimé en
régime calme, celui de la gestion courante, prédit-il la perte subie quand la
crise arrive ? Pour chaque scénario, trois grandeurs à ne pas confondre.

| Grandeur | Définition | Nature |
|---|---|---|
| Ratio d'amplification réalisé | `ln(1+R_p) / ln(1+R_b)` sur la fenêtre | un **rapport** de deux nombres : ni régression, ni résidu, ni erreur type |
| Beta régressé de crise | pente des rendements quotidiens dans la fenêtre | une **estimation** : R², erreur type, observations, drapeau d'échantillon mince |
| Prédiction du beta calme | `exp(β_calme · ln(1+R_b)) − 1` | ce que la gestion courante laissait attendre |

Le ratio n'est volontairement **pas** appelé « beta 2008 » : ce nom laisserait
croire à une estimation qui n'a pas eu lieu. Les deux premiers sont en log parce
qu'on met à l'échelle un rendement multi-périodes (bloc 4A : les log s'agrègent
dans le temps). Un beta régressé sur moins de 60 séances est signalé comme
reposant sur un échantillon trop mince : les 23 rendements du krach COVID ne
suffisent pas à une pente stable, et le chiffre ne doit pas en avoir l'apparence.

**L'écart entre la prédiction et la perte réelle est le livrable.** Quand le
ratio et le beta de crise divergent, c'est un résultat, pas une anomalie : la
régression mesure la co-variation quotidienne autour des moyennes, et une dérive
propre au portefeuille pendant l'épisode change le rendement cumulé sans changer
la pente. En couverture partielle, perte, ratio, beta de crise et beta calme
portent tous sur les mêmes lignes couvertes, pour que l'écart ne mélange pas un
effet de couverture à un effet de régime.

Chaque comparaison porte aussi `systematic_share_change`, l'écart entre le R² de
crise et le R² de régime calme. **Le R² est la lecture la plus directe de la
dégradation de la diversification** : il mesure la part de la variance du
portefeuille expliquée par le marché, c'est-à-dire la part de risque qui ne se
diversifie pas. Il parle plus encore que le beta, qui mêle l'intensité du
co-mouvement et le rapport des volatilités.

Illustration sur le portefeuille de démonstration (six titres ; régime calme sur
504 séances au 9 septembre 2026 : β = 0,57 ± 0,03, **R² = 0,49**) :

| Scénario | Perte réelle | Prédite par β calme | Écart | Ratio | β de crise | R² de crise (calme 0,49) |
|---|---|---|---|---|---|---|
| Crise 2008 | −44,0 % | −36,6 % | −7,4 pts | 0,72 | 0,96 ± 0,02 | **0,86** (+0,36) |
| COVID | −35,8 % | −20,8 % | −15,0 pts | 1,08 | 1,07 ± 0,03 | **0,98** (+0,48) |
| Resserrement 2022 | −8,7 % | −14,7 % | +6,0 pts | 0,32 | 0,73 ± 0,03 | **0,79** (+0,29) |

Les betas de crise reposent sur 355, 23 et 195 séances ; celui du COVID est
signalé comme reposant sur un échantillon trop mince.

**Le co-mouvement avec le marché augmente dans les trois crises, sans
exception.** Le beta passe de 0,57 à 0,96, 1,07 et 0,73 ; le R² de 0,49 à 0,86,
0,98 et 0,79. En régime calme, la moitié seulement du risque du portefeuille est
systématique ; en crise, entre les quatre cinquièmes et la quasi-totalité. La
hausse ne tient pas à la seule fenêtre COVID, trop courte : elle vaut aussi sur
les deux fenêtres assez longues pour une régression stable, 2008 et 2022. La
diversification se dégrade précisément quand on en a besoin.

**Ce qui varie d'un épisode à l'autre, c'est seulement l'ampleur d'une
performance idiosyncratique qui vient compenser.** Nulle en 2020 : le ratio
rejoint le beta de crise (1,08 contre 1,07) et la perte suit le marché. Partielle
en 2008 : au beta de crise, la perte aurait atteint −53,7 % ; la tenue de lignes
défensives la ramène à −44,0 %, ce qui reste plus lourd que ce qu'annonçait le
beta calme. Plus que complète en 2022 : une ligne énergie en forte hausse fait
finir le portefeuille mieux que prévu, alors même que sa sensibilité au marché
avait augmenté.

> **Le risque systématique monte de façon fiable ; la compensation relève de la
> chance.** Les règles de recommandation de la Phase 6 ne devront jamais compter
> dessus. Une diversification jugée sur le régime calme surestime la protection
> disponible en crise, et un épisode où une ligne a sauvé le portefeuille ne dit
> rien du suivant.

### 7. Moteur de règles

```python
from backend.rules import evaluate_portfolio

rapport = evaluate_portfolio(conn, portfolio_id=1)
print(rapport.render())       # observations, seuils et provenance
print(rapport.disclaimer)     # texte du bandeau d'acceptation
```

Le moteur de règles s'appuie sur les sorties des Phases 4 et 5 **et ne recalcule
rien** : chaque règle lit un résultat déjà produit et le met en mots. Un test
vérifie que le module n'importe aucun module de calcul.

**Il décrit des propriétés, il ne prescrit pas d'actions.** « Cette ligne pèse
35 % des variations de votre portefeuille » est un fait vérifiable ; « vous
devriez l'alléger » est un conseil en investissement, que rien dans ce projet ne permet de
donner — le moteur ignore l'horizon de placement, les objectifs, la fiscalité et le
reste du patrimoine. C'est la position honnête, et la seule défendable
juridiquement. La preuve que ça compte est dans les chiffres du projet : une règle
« réduis la ligne énergie » aurait visé précisément la ligne qui a apporté +9,4
points au portefeuille en 2022, pendant que le marché perdait un quart de sa
valeur. La concentration amplifie la variance dans les deux sens, et les
observations disent les deux. Une garde lexicale vérifie qu'aucune observation ne
contient de formulation prescriptive ; ce n'est pas une preuve, mais un filet.

**Pas de score de risque global.** C'est la sortie la plus tentante pour un outil
grand public et la plus mauvaise : elle comprime des grandeurs non commensurables
— une concentration, une part systématique, une couverture de scénario — en un
nombre dont l'échelle ne veut rien dire, et elle invite exactement à la lecture
prescriptive qu'on évite. Un tel chiffre fonctionne quand un conseiller humain
l'interprète ; sans cet intermédiaire, il a l'air d'une autorité sans en être une.
Le résultat est une liste d'observations, et rien d'autre.

**Une mesure ajoutée avant les règles : la contribution de chaque ligne à la
variance**, `cᵢ = wᵢ·(Σw)ᵢ / (wᵀΣw)`. Elle tient compte du poids *et* de la
corrélation : une ligne de 10 % très corrélée au reste contribue davantage qu'une
ligne de 10 % décorrélée, ce que le poids seul ne dit pas. Les contributions
somment exactement à 100 %, ce qu'un test vérifie à la tolérance flottante ; une
contribution négative signale une ligne qui a évolué à rebours du reste.

| Règle | Ce qu'elle décrit | Seuil |
|---|---|---|
| 1. Concentration effective | lignes effectives en capital (`1/Σwᵢ²`) **et** en risque (`1/Σcᵢ²`), et l'écart entre les deux | aucun en régime normal ; 60 séances **choisies** et 3 séances **dérivées** pour la moitié « en risque » |
| 2. Contribution à la variance | part du risque face à la part du capital, et parcours de la ligne dans les crises rejouées | référence calculée : la part de capital de la ligne ; 60 séances **choisies** et 3 séances **dérivées** pour la taille d'échantillon |
| 3. Diversification apparente | paires qui ont largement évolué ensemble ; sinon, la paire la plus corrélée | corrélation 0,70 **choisie** ; paire la plus corrélée, relative au portefeuille ; 60 séances **choisies** et 3 séances **dérivées** pour la taille d'échantillon |
| 4. Part systématique | part de la variance expliquée par le marché, qui ne se dilue pas en détenant davantage d'actions américaines | aucun en régime normal ; 60 séances **choisies** et 3 séances **dérivées** pour la taille d'échantillon |
| 5. Dégradation en crise | part systématique en régime calme face à chaque crise rejouée ; la conclusion ne compte que les crises estimées sur assez de séances, les autres sont citées à part avec leur sens | 60 séances **choisies** pour signaler un échantillon trop mince |
| 6. Couverture d'un scénario | portée d'un scénario incomplet ; sous 80 %, aucun chiffre principal | 80 % **choisi** |

**Les observations sont écrites pour un lecteur qui part de zéro.** Elles
s'affichent telles quelles en section 6, à côté des phrases de lecture
(section 10). Depuis le chantier « Textes de lecture » (2026-10-05), elles
vouvoient et parlent en mots courants. Les noms ci-dessus restent ceux des
règles dans le code (`RuleId`, champ `rule`) ; le libellé affiché
(`rule_label`) est une question ou un constat :

| Règle (`rule`) | Libellé affiché (`rule_label`) |
|---|---|
| `effective_concentration` | Combien de lignes, en réalité |
| `variance_contribution` | Poids dans les variations |
| `apparent_diversification` | Lignes qui bougent ensemble |
| `systematic_share` | Part qui suit le marché |
| `crisis_degradation` | Le portefeuille en crise |
| `scenario_coverage` | Crise rejouée en partie |

- Le vocabulaire : « variations » pour la variance, « la part qui suit le
  marché » pour la part systématique, « jours de bourse » pour les séances,
  « ces deux dernières années » pour la fenêtre (`Window.period_label`), « le
  S&P 500 » pour SPY (`engine.benchmark_name`).
- Ce qu'une ligne a apporté dans une crise se dit par le verbe : « a coûté
  7,6 points », « a rapporté 9,4 points ». Le chiffre signé reste dans les
  faits publiés.
- Une crise se nomme avec son article : « pendant la Crise financière 2008 »,
  « le Krach COVID ». Le catalogue le déclare (`Scenario.article`), parce que
  le genre d'un nom ne se devine pas. Sans article déclaré, la phrase dit
  « l'épisode … ».
- Ce qui ne change pas : les faits (`facts`), les seuils et leur texte, les
  provenances, l'identifiant `rule`, et aucun nombre.

**Une crise estimée sur trop peu de séances n'entre pas dans une conclusion.**
La règle 5 écrivait que la part systématique « augmente dans les 3 crises
rejouées », alors que la même phrase qualifiait le krach COVID (23 séances)
d'échantillon trop mince. Un chiffre qu'on vient de juger fragile ne peut pas
être compté ensuite comme une preuve. Le décompte ne porte désormais que sur
les crises estimées sur au moins 60 séances. Les autres sont citées à part, et
chacune dit si elle va dans le même sens. Sans aucune crise suffisante, aucune
conclusion générale n'est tirée. Les faits publiés suivent la phrase :
`crises_comparees` et `crises_en_hausse` ne comptent que les crises
suffisantes, et `crises_comparees_echantillon_mince` et
`crises_en_hausse_echantillon_mince` comptent les autres à part. Aucune autre
règle ne publie de décompte de ce type.

**Deux régimes de taille d'échantillon, et la frontière entre eux n'est pas une
convention.** Les **quatre** règles qui reposent sur la matrice de covariance —
concentration effective (moitié « en risque »), contribution à la variance,
diversification apparente, part systématique — lisent `window.observations`, le
nombre de séances RÉELLEMENT utilisées, et non la fenêtre demandée.

- **Sous 3 observations, la règle refuse de chiffrer.** Une régression avec
  constante a `n − 2` degrés de liberté résiduels : à deux observations il n'en
  reste aucun, la droite passe exactement par les deux points, son R² vaut 1 et
  la corrélation vaut ±1 — *quelles que soient les données*. Ce ne sont pas des
  estimations bruyantes, ce sont des identités arithmétiques, et le chiffre
  serait le même pour deux titres pris au hasard. Aucune mention d'« échantillon
  mince » ne répare une phrase qui affirme une identité comme si elle décrivait
  le portefeuille. L'observation dit donc que le calcul n'a pas de sens, et
  combien de jours il faudrait : « Sur 2 jours de bourse, une corrélation n'a
  pas de sens : il en faut au moins 3. » La raison algébrique reste publiée
  avec le seuil (`MIN_ESTIMABLE_SAMPLE.rationale`), sous la phrase ; elle ira
  aussi dans la page de méthodologie.
- **De 3 à 59 observations, la règle chiffre et le signale**, avec le seuil
  `MIN_REGRESSION_SAMPLE` attaché — exactement ce que la règle 5 faisait déjà
  pour le R² de crise. Le chiffre dit quelque chose, mal.

**La même frontière vaut pour les contributions à la variance.** À `n = 2` la
covariance est de rang 1 — `Σ ∝ δδᵀ`, où `δ` est l'écart entre les deux
rendements — et la contribution de la ligne `i` vaut exactement `wᵢδᵢ / (wᵀδ)` :
la part de chaque ligne dans **une** différence journalière, présentée comme une
décomposition de variance. Vérifié à `1e-16` près.

**La singularité de `Σ` quand `n ≤ k` ne crée pas de troisième régime**,
contrairement à ce qu'on pourrait craindre : les contributions n'ont besoin que
de `wᵀΣw > 0`, jamais d'une inverse, et chaque covariance qui les compose garde
ses `n − 1` degrés de liberté. Mesuré sur un modèle à un facteur, 7 lignes,
3 000 tirages, contre une vérité connue :

| n | rang Σ | erreur abs. médiane | P(contribution < 0) | lignes eff. (vrai : 5,30) |
|---|---|---|---|---|
| **2** | **1** | **0,1216** | **73,1 %** | **2,88** |
| 3 | 2 | 0,0688 | 49,8 % | 4,20 |
| 7 | 6 *(singulière)* | 0,0344 | 11,6 % | 4,98 |
| 8 | 7 *(inversible)* | 0,0309 | 7,3 % | 5,04 |
| 60 | 7 | 0,0104 | 0,0 % | 5,28 |

Le passage `n = 7 → 8`, où `Σ` cesse d'être singulière, ne produit aucune
rupture. La seule est à `n = 2`, et elle est exacte.

`MIN_ESTIMABLE_OBSERVATIONS` est le seul seuil du projet déclaré **`DERIVED`
sans venir d'une référence du portefeuille** : il ne se choisit pas, il se
démontre. Le `kind` porte cette différence pour une machine, pas seulement la
phrase. Le moteur connaissait déjà la frontière :
`covariance.Beta.standard_error` est documenté « None en dessous de trois
observations, où elle n'est pas définie ».

**Pourquoi le contrôle est dans les règles et pas sur le paramètre.** L'API
plafonne `window` à `MIN_REGRESSION_OBSERVATIONS`, mais ce plancher ne protège
pas : le panel aligné se réduit à l'INTERSECTION des dates, et une seule ligne
cotée depuis peu — un titre chargé par `ingestion add` — fait tomber une demande
de 504 séances à 39 observations sans qu'aucun paramètre ait changé. Seul un
contrôle sur `window.observations` voit ce cas.

**La concentration se dit en capital et en risque.** Le nombre de lignes
effectives en capital seul est la plus flatteuse des deux lectures : un
portefeuille équilibré en montants peut porter l'essentiel de sa variance sur
quelques lignes volatiles et corrélées. L'écart entre les deux nombres est
l'observation la plus utile de la règle — le risque ne se répartit pas comme le
capital. La phrase le dit sans formule : les lignes « pèsent comme 5,7 lignes
de même montant, mais font bouger le portefeuille comme 4,4 seulement ».

**Une couverture de scénario minimale à 80 %, choisie à la main.** Sous 80 % de
la valeur, la partie rejouée ne représente plus assez l'ensemble pour en tirer
un chiffre. Le seuil est plus strict qu'un pile ou face pour une raison
d'arithmétique : à 80 %, même si la partie exclue avait perdu deux fois plus
que la partie couverte, la perte de l'ensemble ne dépasserait le chiffre affiché
que d'un cinquième — contre moitié plus à 50 %.

Ni le seuil ni l'observation ne disent dans quel sens l'ensemble aurait
différé : le moteur ne le mesure pas. La phrase s'en tient à ce qu'il sait :
« Les lignes absentes n'ont pas été rejouées : la perte de l'ensemble a pu être
différente. »

**Le CVaR à 99 % porte un avertissement permanent, pas une règle.** À 99 %, la
queue ne compte que 1 % de la fenêtre : 6 séances sur 504. Un seuil « moins de 10
observations » serait allumé à chaque calcul, et une alerte permanente n'informe
plus. L'avertissement est donc attaché au chiffre lui-même
(`ExpectedShortfallResult.caveat`), plutôt que présenté comme une anomalie
détectée. Sur le portefeuille de démonstration, le CVaR à 99 % de 3,00 %
est accompagné de : « Moyenne de 6 jours de bourse seulement, sur 504 : chacun pèse pour 17 % du chiffre. »

**Les seuils sont traités explicitement**, car ils sont le point faible de tout
moteur de règles. Par ordre de préférence : pas de seuil du tout quand la mesure
parle d'elle-même ; un seuil dérivé d'une référence calculée ; un seuil relatif au
portefeuille lui-même ; en dernier recours seulement, un nombre rond choisi à la
main. Chaque observation porte ses seuils et leur provenance, et un seuil choisi
le dit en toutes lettres — « choisi à la main (non dérivé des données) » —,
selon la même règle de provenance que les fenêtres d'estimation et les dates de
valorisation. La ligne de seuil s'écrit en casse phrase : la valeur, puis la
provenance après une virgule, puis la justification en phrase (« corrélation
forte = 0,70, choisi à la main (non dérivé des données). Convention usuelle
pour qualifier une corrélation de forte ; aucun calcul sur le portefeuille ne
la produit. »). Elle portait un second deux-points et le mot « CHOISI » en
capitales (décision du 2026-10-05). La provenance dit d'où vient la valeur :
« choisi à la main (non dérivé des données) » pour un seuil choisi,
« démontré (le même pour tout portefeuille) » pour un seuil démontré (les 3
séances estimables, le minimum d'une VaR historique), « calculée sur ce
portefeuille » pour une référence, accordé avec le nom du seuil : « part de
JPM dans la valeur = 24,5 %, calculée sur ce portefeuille. » Une référence
disait « référence calculée » ou « relatif au portefeuille », et la ligne, qui
commence par « Référence : », répétait le mot (décision du 2026-10-06).

**Un seuil n'est pas une référence.** Chaque ligne porte un `role` en plus de
son `kind`. Un **seuil** est une frontière posée d'avance, la même pour tout
portefeuille : la corrélation forte à 0,70, choisie, ou les 3 séances
estimables, démontrées. Une **référence** est une valeur calculée sur ce
portefeuille, à laquelle la mesure se compare : la part de capital d'une ligne,
ou la corrélation de sa paire la plus corrélée. L'interface écrit « Seuil : »
ou « Référence : » d'après ce champ (DESIGN.md §9.2). `kind` ne suffit pas à
trancher, puisque `derived` couvre les deux cas. Le constructeur refuse une
référence choisie à la main et un seuil relatif au portefeuille.

**Un même nombre a la même forme dans un même bloc.** Chaque seuil déclare la
précision de son écriture (`decimals`), et la phrase comme la ligne de seuil
écrivent `Threshold.displayed`. Le seuil choisi s'écrivait « 0,70 » dans la
phrase et « 0,7 » dessous. Désormais, c'est « 0,70 » aux deux endroits. La
valeur n'est plus arrondie avant d'être écrite : `round()` tranche les
égalités au pair et `typography` comme `toFixed`. Une corrélation de 0,125
se serait écrite « 0,12 » sous une phrase qui dit « 0,13 ».

Illustration sur le portefeuille de démonstration (données au 9 septembre 2026,
la copie figée que lisent les tests) :

> Vos 6 lignes pèsent comme 5,7 lignes de même montant, mais font bouger le portefeuille comme 4,4 seulement : le risque est plus concentré que l'argent. Avec des montants égaux, elles compteraient pour 6. À ne regarder que les montants, on surestime donc la diversification.
>
> JPM représente 25,6 % de la valeur du portefeuille et 35,4 % de ses variations, soit 9,8 points de plus. Plus une ligne pèse dans les variations, plus elle pèse sur le résultat, à la baisse comme à la hausse. Dans les crises rejouées, JPM a coûté au portefeuille à chaque fois, de 16,6 points (Crise financière 2008) à 8,7 points (Resserrement monétaire 2022).
>
> XOM représente 15,8 % de la valeur du portefeuille et 13,9 % de ses variations, soit 1,9 point de moins. Dans les crises rejouées, XOM a joué dans les deux sens : il a coûté 7,6 points (Krach COVID), mais rapporté 9,4 points (Resserrement monétaire 2022).
>
> Ces deux dernières années, 49 % des variations de votre portefeuille ont suivi celles du marché, le S&P 500. Cette part ne se dilue pas en ajoutant d'autres actions américaines. Les 51 % restants sont propres à vos lignes : c'est sur eux seuls que la diversification agit.
>
> La part des variations qui suit le marché passe de 49 % ces deux dernières années à 86 % pendant la Crise financière 2008 et à 79 % pendant le Resserrement monétaire 2022. Dans ces deux crises, la diversification entre vos lignes s'est affaiblie au moment où elle aurait servi. Le Krach COVID va dans le même sens (98 %), mais sur 23 jours de bourse seulement : trop peu pour conclure.

### Texte du bandeau d'acceptation

Seulement le texte ; l'écran qui le portera relève de la Phase 7. Sa source est
`backend/rules/disclaimer.py`, qui tire la taille de la fenêtre de la configuration
du moteur : le texte ne peut pas annoncer 504 séances le jour où le calcul en
utiliserait un autre nombre. Le bandeau **vouvoie**, comme les observations et
toute la page depuis les textes de lecture du 2026-10-05 : les observations
tutoyaient, et un seul registre vaut désormais partout. C'est le seul texte du
projet à portée quasi juridique. Ce texte n'a pas été relu par un juriste.

> **Avant d'utiliser Mx Risk MGT**
>
> **Un outil informatif, pas un conseil.** Mx Risk MGT décrit des propriétés statistiques de votre portefeuille. Il ne constitue pas un conseil en investissement réglementé, ni une recommandation d'acheter, de vendre ou de conserver un titre. Il ne connaît ni votre horizon de placement, ni vos objectifs, ni votre situation fiscale, ni le reste de votre patrimoine : aucune de ses observations ne peut en tenir compte.
>
> **Aucune garantie d'exactitude.** Les données de marché proviennent d'un fournisseur tiers et peuvent comporter des erreurs, des retards ou des omissions. Les calculs reposent sur des hypothèses statistiques et peuvent eux-mêmes être erronés. Aucune garantie n'est donnée sur l'exactitude, l'exhaustivité ou l'actualité des données ni des calculs.
>
> **Les mesures décrivent un régime, pas un avenir.** Les mesures de risque courantes (volatilité, VaR, CVaR, beta, corrélations) sont estimées sur les 504 dernières séances de bourse, soit environ 2 ans. Elles décrivent le comportement du portefeuille pendant cette période. Elles ne prédisent pas son comportement futur, qui peut s'en écarter fortement, en particulier lors d'une crise.
>
> **Les scénarios rejouent des crises passées, ils ne prédisent pas les prochaines.** Les scénarios de stress appliquent à votre portefeuille actuel les mouvements réellement observés pendant des crises passées. Ils ne prédisent ni la survenue, ni l'ampleur, ni la forme d'une prochaine crise, qui ne ressemblera pas nécessairement à celles-ci.
>
> **Utilisation à vos risques.** Vous utilisez cet outil à vos propres risques, et les décisions que vous prenez relèvent de votre seule responsabilité. La responsabilité de l'auteur de l'outil ne peut être engagée pour les conséquences de décisions fondées sur les informations qu'il affiche.
>
> *J'ai lu ces limites, je les comprends, et j'utilise cet outil en connaissance de cause.*

### 8. Tests

```powershell
pytest
```

Aucun test ne sort sur le réseau : la session HTTP et le fournisseur sont
remplacés par des doubles, et le client de test de FastAPI parle directement à
l'application ASGI en mémoire. La suite passe hors ligne et ne consomme pas de
quota.

Les tests d'API n'écrivent jamais dans `data/mx_risk.sqlite` : chacun travaille
sur une copie jetable ou sur une base synthétique construite pour le cas
étudié. Ceux qui ont besoin des vraies séries — la forme des queues, la
couverture réelle d'un scénario de 2008 — sont ignorés si la base locale est
absente.

**Aucun test ne lit la base vivante.** `refresh` y ajoute des séances chaque
jour et `rebuild` la réécrit : un test qui la lirait vérifierait l'état du
fichier, pas le code. `tests/conftest.py` en est le seul accès. Il copie la
base et la tronque à `DATE_GEL` (2026-09-09), et offre trois fixtures :

- `base_figee_partagee`, une copie pour toute la session, en lecture seule
  sur le disque ;
- `base_figee`, une copie propre au test, pour qui y crée des portefeuilles ;
- `analyse_reelle`, la réponse `/analysis` du portefeuille de démonstration.

`tests/test_gel_des_tests.py` lit l'arbre syntaxique de chaque fichier de
tests. Il échoue sur toute autre ouverture : `BASE_REELLE`, `get_db_path`,
`connect()` sans chemin, une chaîne en `mx_risk.sqlite`. Il est exercé par
des témoins dans les deux sens.

La réponse `/analysis` de référence est calculée **une fois par session** :
c'est un objet HTTP déjà reçu, que la vingtaine de tests concernés se contentent
de lire, et la base qui l'a produite est fermée avant le premier d'entre eux. La
recalculer par test coûtait 2,7 s — copie de 9 Mo, analyse complète, scénarios,
régimes — pour un résultat identique à chaque tour. Un test qui ÉCRIRAIT sur la
base réelle ne réutilise pas cette fixture : il se copie la base dans son propre
`tmp_path`. La frontière est là — lire une réponse se partage, toucher une base
ne se partage pas.

`tests/test_api_discipline.py` ne teste aucun comportement : il inspecte l'arbre
syntaxique de `backend/api/` pour vérifier qu'aucun module n'y fait
d'arithmétique, n'y écrit de SQL, n'y appelle `asdict()` ni n'y supprime les
champs nuls. Une règle écrite dans un README se contourne sans bruit.

Ce que la garde d'arithmétique voit : les quatre opérations, la puissance, le
modulo, les affectations augmentées, `round()` et `abs()`, et la **négation
d'une valeur** — `-resultat.value` est exactement l'inversion de signe que
`risk_engine.var` redoute, une VaR rendue en perte positive et republiée en
rendement négatif se lirait comme un gain sans qu'aucun test de valeur ne
bronche. `-1` reste un littéral, `int | None` reste une annotation.

La détection est une fonction (`calculs_dans`) exercée par deux jeux de témoins,
dans les deux sens : treize extraits qui **doivent** être détectés, neuf qui ne
doivent pas l'être. Une garde qu'on n'a jamais vue échouer ne prouve rien — un
`CALCULS` vidé par mégarde passerait au vert sur toute la couche et la
déclarerait propre.

### 9. API

```powershell
python -m backend.api
```

Documentation interactive sur <http://127.0.0.1:8000/docs>.

L'adresse d'écoute est **écrite dans le point d'entrée**, pas laissée en option
de ligne de commande. L'application est mono-utilisateur et locale : elle n'a ni
authentification, ni notion d'utilisateur, ni contrôle d'accès. Une API sans
authentification exposée sur une interface réseau donnerait à quiconque partage
le réseau le droit de lire et de supprimer les portefeuilles — et un défaut
qu'on peut contredire d'un argument est un défaut qu'on finit par contredire.

| Méthode | Chemin | Rôle |
|---|---|---|
| GET | `/api/meta` | dernière séance en base, taille de l'univers |
| GET | `/api/securities` | univers : ticker, nom, secteur, première et dernière date de prix |
| POST | `/api/portfolios` | crée un portefeuille, renvoie son `id` |
| GET | `/api/portfolios` | liste ; positions stockées, et valorisées quand elles le sont |
| GET | `/api/portfolios/{id}` | un portefeuille ; positions stockées et valorisées |
| PUT | `/api/portfolios/{id}/positions` | remplace **toutes** les positions ; `line` facultatif par position, renvoyé dans les refus |
| POST | `/api/portfolios/{id}/positions/csv` | import CSV (multipart) |
| GET | `/api/csv-format` | format lu par l'import CSV : colonnes, séparateurs, décimales, encodages, limites, exemple |
| DELETE | `/api/portfolios/{id}` | supprime le portefeuille et ses positions |
| GET | `/api/portfolios/{id}/analysis` | rapport, scénarios, régimes, observations, bandeau |

#### L'analyse est un seul endpoint, et c'est une décision

Le rapport de risque, les scénarios de stress, la comparaison de régimes, les
observations et le bandeau d'acceptation sortent d'un **unique** appel plutôt
que de quatre.

La raison est la cohérence temporelle. Si la base était rafraîchie entre deux
appels, la section « volatilité » et la section « scénarios » décriraient deux
états différents de la base, et **rien dans les réponses ne le signalerait** :
chacune serait juste, l'assemblage serait faux. Une seule réponse garantit un
seul `as_of` pour toute la page.

L'objection habituelle — « le Monte Carlo coûte trop cher pour être dans la
réponse par défaut » — ne tient pas ici, mesures à l'appui sur six titres :
analyse avec Monte Carlo à 100 000 tirages 0,28 s, scénarios 0,05 s, régimes
0,25 s, règles négligeable. Moins d'une seconde pour la page entière. Découper
paierait un risque d'incohérence pour une économie qui n'existe pas.

#### Ce que la couche API ne fait pas

**Elle ne calcule rien.** Aucune arithmétique dans `backend/api/` — la règle est
vérifiée en inspectant l'arbre syntaxique des modules
(`tests/test_api_discipline.py`), pas seulement écrite ici. Chaque nombre publié
sort d'un attribut, d'une propriété ou d'une méthode du moteur, déjà testés. Si
une valeur manque, elle s'ajoute au moteur avec son test.

**Une connexion SQLite par requête**, jamais partagée entre requêtes, ouverte
et refermée par la dépendance `get_connection`. FastAPI l'ouvre, exécute la
route et la referme dans trois fils du pool qui peuvent différer : la
connexion est donc ouverte avec `check_same_thread=False`
(`connect(cross_thread=True)`). Elle passe de main en main sans jamais servir à
deux fils en même temps. Sans cela, des requêtes simultanées — la page de
saisie en envoie plusieurs — répondaient 500 au hasard
(`tests/test_api_dependencies.py`).

**Elle ne fait aucun SQL.** Les lectures sur les données de marché vivent dans
`risk_engine/portfolio.py`, les écritures de données utilisateur dans
`db/portfolios.py`. Une requête dans la couche HTTP créerait une troisième
frontière avec la base, et obligerait une future commande en ligne à importer
la couche HTTP pour écrire une position.

**Elle ne formate rien.** Les valeurs restent des **fractions** : une VaR de
1,38 % se sérialise `0.0138`. Le pourcentage, la virgule décimale et l'arrondi
sont décidés à un seul endroit, côté frontend (`frontend/DESIGN.md` §6).

**Mais le backend RÉDIGE du texte**, et ce texte-là est affiché tel quel :
observations du moteur de règles, `summary()` des scénarios, `caveat` du CVaR,
`rendered` des seuils, bandeau d'acceptation. Il suit donc la typographie
française, avec des espaces **insécables** (`backend/typography.py`) :

| | Où | Pourquoi |
|---|---|---|
| **U+202F** espace fine | avant `%`, séparateur de milliers | sinon « 25,6 % » se coupe et le `%` part seul à la ligne |
| **U+00A0** espace insécable | entre un nombre et le mot qu'il compte | sinon « 504 séances » devient « 504 » puis « séances » |
| **U+00A0** espace insécable | avant « : », « ; », « ? », « ! », après « « » et avant « » » | sinon « : ticker » commence une ligne que « Colonnes obligatoires » finit |

Deux tests balaient la réponse `/analysis` entière et refusent toute espace
ordinaire dans ces deux positions ; un troisième vérifie en sens inverse que les
caractères sont bien présents, sans quoi les deux premiers surveilleraient une
absence vide. Le portefeuille de référence est couvert à 100 % par les trois
crises : un quatrième test balaie donc une réponse à couverture partielle, seul
endroit où se publie la justification du seuil de couverture de 80 %. Elle
portait deux espaces ordinaires avant « % ».

**La ponctuation haute et les guillemets sont composés à la publication.** Les
phrases du moteur et des règles s'écrivent avec des espaces ordinaires, lisibles
dans le code ; `typography.prose` les rend insécables avant « : », « ; », « ? »
et « ! » suivis d'un blanc, et dans les guillemets, et seulement là. Elle pose
aussi un caractère de liaison invisible (U+2060) après le tiret court d'une
paire comme « JNJ–KO », qui se coupait sinon en fin de ligne, le « KO »
renvoyé seul à la ligne suivante, et après chaque trait d'union d'une date ISO
citée dans un texte (« valorisation au 2026-09-25 »), qui se coupait sinon
avant son jour ; les faits et le sujet d'une observation, qui ne sont pas de la
prose, gardent la paire nue, et les champs de date (`as_of`, `start`, `end`),
qui sont des données, restent nus. Elle s'applique une fois, aux champs de texte
rédigé des schémas — typés `Texte` (`Annotated[str, AfterValidator(prose)]`),
48 champs : raisons, phrases, réserves, provenances, libellés de période et
d'indice, bandeau — et aux corps
d'erreur (`detail`, `problems[].problem`). Les identifiants et les saisies
(ticker, nom d'un portefeuille, nom de fichier, exemple de CSV) restent des
`str` : on ne retouche pas ce que quelqu'un a tapé. `tests/test_textes_publies.py`
balaie, comme `test_nombres_publies.py` pour les nombres, la référence, une
réponse synthétique, trois fenêtres réduites, le catalogue, le bandeau et six
corps d'erreur (404, 409, et quatre 422 : positions, import, nombre illisible,
encodage) ; trois contrôles en sens inverse vérifient que deux-points,
point-virgule et guillemets insécables sont bien présents. Les quatre signes
prennent la même espace insécable, pas une espace fine.

**Aucune lettre grecque hors de la provenance.** Spectral, la police des
phrases, n'a pas de glyphe grec : le « ν » de repli s'y lit « v ». La même
garde refuse toute lettre grecque ailleurs que dans `method` et `detail` d'une
mesure, qui s'affichent en IBM Plex Sans (« ν = 4,07 », « μ = 0 »,
« λ=0,94 »). Les raisons de refus ne citent plus aucune formule ; celle des
contributions à deux séances est ici : la covariance y est de rang 1,
Σ ∝ δδᵀ, et la part de chaque ligne vaut wᵢδᵢ / (wᵀδ).

Le frontend applique la même convention de son côté pour les nombres qu'il
formate lui-même, et pour les deux-points et guillemets de ses propres
chaînes. Dans les messages d'erreur, seuls les nombres SAISIS passent par
`typography` (`exact`) : le reste est un diagnostic, pas un texte de rapport.

#### Les choix de sérialisation qui comptent

**Les positions stockées voyagent avec le portefeuille.** `positions` rend
chaque ligne telle qu'elle est en base — ticker, quantité, prix de revient —,
que la valorisation réussisse ou non. Sans elles, un portefeuille vide ne se
reconnaissait qu'en cherchant « sans position » dans le texte de
`valuation_error`, et un portefeuille dont une ligne a perdu ses prix ne
pouvait pas être prérempli pour être réparé : `GET /{id}` répond 409, et la
liste ne rendait que `valuation: null`. Les positions sont lues une seule fois
et servent aussi à la valorisation, pour ne pas décrire deux états.

**Pas de `dataclasses.asdict()`.** Il copie les champs et ignore silencieusement
les `@property` et les méthodes. Un convertisseur générique aurait publié une
API d'où manqueraient, sans la moindre erreur, `prediction_gap` — que le moteur
décrit comme « le livrable » de la comparaison de régimes —,
`systematic_share_change`, le `caveat` permanent du CVaR à 99 %,
`Threshold.chosen`, `value_share`, `summary()` et `render()`. Chaque schéma
énumère donc ses champs à la main.

**Le refus vit dans la MESURE, pas seulement dans la phrase.** Sous trois
observations, `matrices.correlation`, `beta` et `variance_contributions`
sortent `null` avec leur raison, dans le moteur. Un moteur de règles qui
refuserait de commenter des valeurs encore publiées ne protégerait de rien : en
7B, une carte de chaleur lit la matrice et un graphe à barres lit les
contributions — pas les phrases. Une matrice de corrélations toutes à ±1 reste
symétrique et de diagonale 1 ; des contributions dégénérées somment quand même
à 1. Les deux ont l'air de ce qu'elles prétendent être.

**La pente du beta est `null` aussi, pas seulement son R².** À zéro degré de
liberté résiduel la droite passe exactement par les points : elle n'a pas
d'erreur type, ce n'est plus une estimation. Publier la pente en nullifiant le
seul R² laisserait croire que la sensibilité au marché a été mesurée et que
seule sa qualité d'ajustement manque. `risk.beta` valant `null` garde un sens
distinct : aucun benchmark demandé.

**Chaque refus n'affirme que ce qui est vrai de SA mesure.** Les trois refusent
sous le même *seuil*, pas pour la même *raison*. La partie commune se limite
donc à ce qui vaut des trois — **à deux observations, le centrage ne laisse
qu'une seule direction** : les écarts à la moyenne valent ±δ/2, et tout se
calcule à partir de ce seul δ. Chacune dégénère ensuite à sa manière :

| Mesure | Ce qui dégénère | Pourquoi |
|---|---|---|
| corrélation | le coefficient vaut ±1, quelles que soient les données | deux points centrés sont colinéaires |
| beta | la pente n'a pas d'erreur type et prend n'importe quelle valeur | une régression avec constante a `n − 2` degrés de liberté résiduels, aucun à `n = 2` |
| contributions | `Σ` est de rang 1 et la part de chaque ligne vaut `wᵢδᵢ / (wᵀδ)` | une covariance d'échantillon est de rang au plus `n − 1`, le centrage retirant une dimension |

Un texte commun serait faux pour deux d'entre elles. « Le coefficient vaut ±1 »
est vrai d'une corrélation et faux d'une pente : à `n = 2` un beta vaut
n'importe quoi — 11,84 puis 8,65 sur deux fenêtres de la base réelle. Et
« une régression avec constante » est **hors sujet** pour une décomposition de
variance, où il n'y a aucune régression. Une explication fausse attachée à un
refus juste est pire qu'un refus sans explication : le lecteur en tire une
conclusion sur ses données.

Depuis les textes de lecture, les raisons publiées le disent sans formule et
en jours de bourse, puisqu'elles s'affichent à la place du chiffre. Chacune
nomme SA mesure et le seuil — « Sur 2 jours de bourse, une corrélation n'a
pas de sens : il en faut au moins 3. » —, et seule la corrélation garde une
conséquence, vraie d'elle seule : « Avec deux jours, elle vaudrait +1 ou −1
quels que soient les titres. » Le beta et les contributions n'en citent
aucune plutôt qu'une empruntée. La démonstration reste ci-dessus ; elle ira
dans la page méthodologie.

#### Où s'arrête le refus

**On refuse ce qui ne dépend plus des données, et ce qui n'est plus la mesure
annoncée ; on signale ce qui en dépend mal.** C'est toute la ligne de partage,
et elle explique pourquoi la volatilité reste publiée à `n = 2`, signalée,
alors que la corrélation disparaît — et la VaR historique avec elle, pour une
autre raison.

| | À `n = 2` | Traitement |
|---|---|---|
| corrélation, beta, contributions | **identités arithmétiques** — la valeur ne bouge plus avec les données | `null` + raison |
| VaR historique et CVaR, sous 1/(1 − α) séances | **plus la mesure annoncée** — aucune séance ne tombe dans la queue : le quantile n'est que le minimum de la fenêtre | `null` + raison |
| covariance, volatilité, VaR paramétrique, drawdown | **estimations à un degré de liberté** — très mauvaises, mais elles bougent | publiées |
| volatilités, VaR paramétrique normale, sous 30 séances | estimations minces | publiées **et marquées** : `caveat` |

Une volatilité sur deux observations est un mauvais chiffre, pas un faux
chiffre : changez les données, elle change. Une corrélation sur deux
observations vaut ±1 quoi qu'on fasse — elle ne mesure rien. Les mauvaises
estimations sont couvertes par les trois dispositifs qui existent déjà pour ça :
`window.observations` sur chaque mesure, `limiting_positions` qui nomme la ligne
responsable, et le seuil de 60 séances qui les signale dans les observations.

**Sous 30 séances, la volatilité et la VaR paramétrique normale portent une
réserve.** Les trois volatilités (écart-type, EWMA, matrice) et la VaR normale
des deux niveaux sortent avec `caveat`, la phrase du moteur : « Estimation
mince : 7 jours de bourse seulement, moins que les 30 retenus pour estimer une
courbe (seuil choisi à la main). Quelques jours suffisent à déplacer ce
chiffre, et l'outil n'en tire aucune conclusion. » Elle dit « jours de
bourse », « courbe » et « l'outil » parce qu'elle s'affiche à côté d'une
phrase de lecture, devant un lecteur qui ne connaît ni la loi normale ni le
moteur de règles. Le seuil est le même que
celui de l'ajustement de Student, et c'est le cinquième seuil choisi à la main
(`rules.thresholds.MIN_DISTRIBUTION_SAMPLE`) : sous normalité, l'écart-type
d'échantillon varie d'environ 1/√(2n) d'une fenêtre à l'autre, 13 % sur 30
séances, 27 % sur 7. La phrase dit qu'aucune conclusion n'en dépend, et c'est
vérifié : `tests/test_rules.py` remplace chaque volatilité et chaque VaR du
rapport par un piège qui lève à la moindre lecture, et les six règles
s'évaluent quand même. À 30 séances et au-delà, `caveat` vaut `null`.

**Sous 1/(1 − α) séances, la VaR historique et sa CVaR sont refusées.** Une VaR
historique à α est le quantile empirique à 1 − α : la queue qu'il borne compte
n·(1 − α) séances. Sous une, aucune n'y tombe, et le quantile « lower » rend le
pire rendement de la fenêtre, quel que soit α : sur 7 séances, la VaR 95 % et la
VaR 99 % valaient toutes deux 0,50 %, et la page lisait « une séance sur cent »
sous un chiffre qui n'était que le pire de sept jours. Le chiffre bougeait
avec les données, mais ce n'était plus la mesure annoncée. D'où un seuil
DÉMONTRÉ, pas choisi : n ≥ 1/(1 − α), 20 séances à 95 %, 100 à 99 %
(`config.historical_var_min_observations`, déclaré dans
`rules.thresholds.historical_var_sample`). En deçà, `historical_var.value` vaut
`null` et `undefined_reason` dit, par exemple : « Sur 7 jours de bourse,
aucun ne tombe dans le 1 % le plus mauvais : il en faut au moins 100 pour ce
calcul. » La CVaR du même niveau, qui moyenne cette queue, est refusée avec
elle, pour la même raison et avec le même texte — `value`, `threshold` et
`tail_observations` à `null` —, et
l'histogramme ne dessine ni le trait ni l'ombre d'un niveau refusé. Sur la
copie figée, l'API refusant toute fenêtre sous 60 séances, seules les
fenêtres de 60 à 99 basculent, à 99 % ; la référence à 504 séances ne bouge
pas.

`matrices.covariance` reste publiée pour une raison de plus : `wᵀΣw` est la
variance de la série du portefeuille, estimable dès deux observations, et c'est
elle qui porte la volatilité paramétrique et la VaR.

**Un indéfini se dit.** Quand `SortinoResult.annualised` vaut `None`, la réponse
porte `annualised: null` **et** `undefined_reason`. `response_model_exclude_none`
est banni de cette API : il supprimerait exactement le champ qui explique le
blanc, et le client afficherait un vide au lieu d'une raison.

**Pas de NaN ni d'Infinity.** Ce ne sont pas du JSON valide, et `JSON.parse`
plante dessus. Deux gardes : les schémas les refusent à la construction en
nommant le champ fautif, et le rendu de Starlette refuse de les écrire. Un test
relit les **octets** d'une vraie réponse avec un analyseur strict.

**Les matrices portent leur ordre.** `correlation` et `covariance` sortent en
`{ "tickers": [...], "values": [[...]] }`, et la **même** liste gouverne les
poids et les contributions à la variance. Chaque cellule est extraite par son
couple d'étiquettes : l'alignement n'est pas vérifié après coup, il est
impossible à rater. Une matrice de corrélation est symétrique et de diagonale
1 — des libellés décalés d'un cran donneraient une carte de chaleur plausible et
fausse.

**Deux conventions de signe cohabitent dans l'Expected Shortfall.** `value` est
une perte positive (`0.0300` = perte moyenne de 3 %), `threshold` est le
quantile brut de la distribution des **rendements**, donc négatif (`-0.0173`).
L'écart vient du moteur, dont l'en-tête annonce pourtant que « toutes les
valeurs de ce module sont des pertes positives » ; la couche API publie le
nombre tel quel plutôt que de le retourner, ce qui serait de l'arithmétique et
publierait une valeur que le moteur n'a jamais produite. Le champ porte donc sa
convention dans sa description OpenAPI, et un test verrouille la relation :
`threshold` vaut l'opposé de `historical_var.value` au même niveau de confiance.

**Chaque mesure garde sa fenêtre.** Aucune fenêtre au niveau du document : le
beta est régressé sous une contrainte d'échantillon qui lui est propre, un
scénario à couverture partielle a sa propre portée. Seule la fenêtre *demandée*
figure en tête, sous `parameters`, nommée comme telle.

**Les seuils sont lisibles par une machine.** Chaque seuil sort avec
`kind: "chosen" | "derived" | "portfolio_relative"`, sa valeur, son
`rationale` et sa phrase rendue. Le client distingue un seuil choisi à la main
d'un seuil dérivé sans chercher le mot « choisi » dans du texte français.

**Un scénario, c'est trois chiffres indissociables :** `end_to_end_return`,
`max_drawdown` (le pire moment traversé, souvent plus profond) et
`coverage.value_share`. Ils sont trois champs requis du même objet ; les deux
premiers valent `null` ensemble, avec la raison, quand aucune ligne n'est
couverte.

**Le volet Student accompagne toujours la VaR normale.** L'écart entre les deux
chiffre le coût de l'hypothèse de normalité. Quand le moteur refuse d'ajuster
une Student — ν ≤ 2, série trop courte, ν au-delà de 30 —, les champs sortent
à `null` et
`student_unavailable_reason` porte le refus du moteur mot pour mot, le reste du
rapport étant servi normalement. Comme celle du Monte Carlo, la raison est en
clair quand la cause est certaine : « Pas assez de jours pour ajuster la loi
de Student : il en faut au moins 30, la période en compte 7. », et pour
ν ≤ 2, « la loi de Student ne s'ajuste pas à vos variations (degrés de
liberté estimés à 1,90, il en faut plus de 2) : aucun chiffre n'en sort ».
Au-delà de ν = 30 : « vos variations ne s'écartent pas de la loi normale : la
loi de Student donnerait le même chiffre (seuil choisi à la main) ». Aucune
de ces phrases n'écrit la lettre ν : elles s'affichent en
Spectral, qui n'a pas de glyphe grec, et le ν de la police de repli s'y lit
« v ». La provenance des VaR Student garde « ν = 4,07 » : elle s'affiche en
IBM Plex Sans, qui a le grec. `tests/test_risk_engine.py` vérifie qu'aucune
raison de refus n'écrit de lettre grecque. La route passe `monte_carlo=True` là où le
moteur a `False` par défaut : divergence volontaire, commentée à l'appel.

**Le Monte Carlo normal ne dépend pas de ν, et ne tombe plus avec la
Student.** Il tombait avec elle : le moteur levait une exception pour tout
refus de la Student, et la route rejouait l'analyse sans aucune simulation.
Rare tant que seul ν ≤ 2 était refusé, courant depuis le seuil de 30 — douze
cas sur quarante-cinq sur la copie figée, fenêtres de 60 à 252 séances. Les
deux volets sont désormais calculés séparément par `analyse_portfolio`, et
chacun porte SA raison : `student_unavailable_reason` pour la Student,
`monte_carlo_unavailable_reason` pour le Monte Carlo normal, qui ne tombe que
sur une covariance non définie positive — moins de séances que de lignes,
une ligne en double. Sur une fenêtre de trois séances pour trois lignes, les
deux manquent, chacun pour sa cause, et aucune raison ne tient lieu de
l'autre. La raison du Monte Carlo sera lue par un particulier : quand la
cause est la longueur de la fenêtre — n séances pour k lignes donnent une
covariance de rang n − 1 au plus, singulière dès que n ≤ k, ce qui est une
certitude et non une supposition —, elle le dit en clair : « La fenêtre
compte 8 séances pour 9 lignes : il en faut davantage que de lignes pour
simuler le portefeuille. » Les autres causes gardent le message technique,
qui nomme ce qu'il faut vérifier. Le moteur rédige les deux, l'API les publie, comme
`correlation_undefined_reason`. La route garde un filet pour une erreur
imprévue des simulations : elle sert alors le rapport sans elles, avec ce
message pour raison des deux volets. La réponse du portefeuille de
démonstration est identique octet pour octet, hormis le nouveau champ à
`null`.

**`limiting_positions` nomme la ligne qui raccourcit la fenêtre.** Le panel est
aligné sur l'**intersection** des dates : une ligne à 5 % du portefeuille, cotée
depuis quarante séances, ramène toutes les mesures à son propre historique — le
beta passe de 0,57 à 0,32, la VaR 95 % de 1,38 % à 1,12 %. `window.complete`
disait déjà que la fenêtre était courte ; il ne disait pas à cause de qui, et
c'est la seule information sur laquelle l'utilisateur peut agir.

L'attribution est **prouvée, pas devinée** : une ligne n'est nommée que si sa
première séance disponible est exactement celle où le panel commence. Quand la
troncature vient d'un trou au milieu d'une série plutôt que d'une entrée en
cotation tardive, la liste est vide — mieux vaut ne désigner personne que
désigner à tort. Elle est vide aussi quand la fenêtre est pleine : elle a alors
été bornée par la demande, et nommer une ligne ferait porter à quelqu'un la
responsabilité d'un choix de paramètre.

#### Ce que citent les phrases de lecture

Les textes de lecture de la page disent chaque mesure en calendrier, en
dollars et en période, pour un lecteur qui n'a jamais entendu parler de VaR.
Le client ne calcule rien : chaque donnée qu'ils citent est publiée par le
moteur, avec ses tests (`test_risk_measures.py`, `test_risk_engine.py`,
`test_api_analysis.py`).

| Donnée | Où | Ce que c'est |
|---|---|---|
| `amount` | chaque VaR, chaque CVaR, `drawdown`, `worst_day` | la mesure appliquée à la valeur du portefeuille au jour de la valorisation (`measures.amount`), même signe qu'elle, `null` avec elle |
| `end_to_end_amount` | chaque scénario | le résultat de bout en bout appliqué à la valeur d'aujourd'hui des lignes couvertes |
| `recovery_date`, `recovery_sessions` | `drawdown` | la première séance, après le creux, où la valeur retrouve son pic, et les séances écoulées depuis le creux ; `null` sans retour avant la fin de la fenêtre, ou sans baisse |
| `worst_day` | `risk` | la pire séance de la fenêtre, en perte positive comme la VaR, avec sa date et son montant |
| `benchmark_volatility` | `risk` | la volatilité de l'indice de référence, sur les mêmes séances que le portefeuille, par la même méthode et avec la même réserve sous 30 séances ; `null` sans indice |
| `benchmark_label`, `benchmark_description` | `parameters` ; `benchmark_label` aussi sur chaque régime | « le S&P 500 », « l'indice de 500 grandes entreprises américaines » (`universe.BENCHMARK_NAMES`) ; `null` pour un indice sans nom connu, que la phrase cite par son ticker |
| `period_label` | chaque VaR, CVaR et volatilité, `drawdown` ; `estimation_period_label` ; `calm_period_label` sur chaque régime | la période obtenue, dite pour un lecteur : « ces deux dernières années » |
| `coverage_sufficient` | chaque scénario | la partie rejouée atteint-elle le seuil choisi de 80 % de la valeur |

**Un montant est une conversion d'échelle, pas une perte reconstituée.**
« 1,06 % représente environ 890 USD sur la valeur d'aujourd'hui » est exact ;
« le portefeuille a perdu 890 USD » ne l'est pas, puisqu'il ne valait pas
cette somme le jour de la perte. Le pire moment traversé d'une crise n'a pas
de montant : il se mesure depuis un plus haut atteint pendant l'épisode,
souvent au-dessus du point de départ, et le multiplier par la valeur de
départ ne donnerait aucune perte réelle.

**La période est celle des séances obtenues**, jamais celle de la fenêtre
demandée (`engine.period_label`) :

- à partir de 252 séances, et à moins d'un vingtième d'année d'un nombre
  entier : en années, « ces deux dernières années » ;
- sinon, à partir de 21 séances : en mois arrondis, « ces 14 derniers mois » ;
- en deçà : en jours de bourse, « ces sept derniers jours de bourse ».

Les nombres s'écrivent en lettres jusqu'à dix (`typography.cardinal`). C'est
la règle du bandeau d'acceptation (`disclaimer._duree`), sauf sous un mois,
où celle-ci écrirait « environ 0 mois ». Seul le régime **calme** reçoit un
libellé : une fenêtre de crise se termine dans le passé, et « ces 17 derniers
mois » y serait faux. Le libellé voyage à côté de la fenêtre, dans l'objet de
la mesure : `WindowOut` garde ses cinq champs partout dans la réponse.

**La couverture minimale vit désormais dans le moteur.**
`config.MIN_SCENARIO_COVERAGE_SHARE` (0,80) est la constante que lit le seuil
`rules.thresholds.MIN_SCENARIO_COVERAGE` : même nombre, même texte. Le moteur
publie le verdict avec chaque scénario, pour qu'une phrase de lecture ne cite
jamais comme la perte du portefeuille ce que le moteur de règles refuse d'en
dire.

**La réponse de référence n'a pas bougé.** Sur la copie figée, à 504 et à 60
séances, toutes les valeurs existantes sont identiques, nombres relus tels
qu'ils sont écrits dans les octets. Seuls s'ajoutent les champs ci-dessus :
48 à 504 séances, 40 à 60.

#### Historique insuffisant : troncature ou exclusion — décision v1

Une ligne sans historique suffisant est traitée **différemment selon l'endroit**,
et il faut le savoir :

| | Ce qui est fait | Ce qui est décrit |
|---|---|---|
| **Scénarios de stress** | la ligne est **exclue**, les poids restants renormalisés | la période complète, sur une **partie** du portefeuille (`coverage.value_share`) |
| **Régime courant** | toute l'analyse est **tronquée** à l'historique commun | le portefeuille **entier**, sur une période plus courte (`limiting_positions`) |

Les deux sont honnêtes puisque les deux sont déclarés, mais ils ne sont pas
cohérents entre eux. **La troncature est conservée en v1** parce qu'elle
n'écarte aucune ligne détenue : le chiffre décrit bien le portefeuille qu'on a,
sur une fenêtre plus courte. L'exclusion avec renormalisation — décrire la
fenêtre complète sur une partie du portefeuille — part au **backlog v2**, où
elle demandera la même déclaration de couverture que les scénarios.

**`benchmark` est insensible à la casse**, comme les tickers des positions :
`?benchmark=spy` et `?benchmark=SPY` font la même chose. Deux portes d'entrée de
la même API ne peuvent pas avoir deux exigences différentes sur la même donnée —
`spy` dans un CSV s'importe sans broncher.

**Le plancher de `window` vient du moteur.** Le paramètre est borné par
`MIN_REGRESSION_OBSERVATIONS` (60), pas par un littéral : `window=2` servait
auparavant un rapport en 200 où le R² valait 1 et toutes les corrélations ±1,
par construction. Ce plancher n'est pas la protection — la fenêtre effective
peut tomber bien plus bas à cause d'une ligne à l'historique court —, il évite
seulement qu'un rapport à moitié dégénéré soit demandé exprès. Le contrôle qui
compte est dans le moteur de règles, sur `window.observations`.

**`as_of` ne s'invente pas.** Celui de `/api/meta` est la dernière séance
présente en base. Celui d'une analyse est la date de valorisation du
portefeuille — la plus **ancienne** des dernières clôtures de ses lignes, seule
date à laquelle la valorisation est vraie pour toutes. Les deux peuvent
différer, et c'est voulu. Aucun des deux n'est `date.today()`.

#### Codes d'erreur

Les messages du moteur sont **relayés mot pour mot** : `PortfolioError` porte
déjà « Aucun prix en base pour ['SPY']. Lancer : `python -m backend.ingestion
add SPY` », et l'écraser en 500 générique remplacerait une instruction par un
aveu d'impuissance.

| Code | Quand | Exemple |
|---|---|---|
| 404 | le portefeuille n'existe pas | vérifié par une lecture explicite, jamais en cherchant un mot dans un message |
| 409 | il existe mais n'est pas analysable | aucune position, aucun prix pour une ligne, benchmark absent, moins de trois séances communes à tous les titres |
| 422 | la requête est refusée | ticker inconnu, quantité négative, doublon, CSV illisible, fenêtre hors domaine |

Un refus porte toujours la même forme, y compris pour les rejets de validation
de FastAPI :

```json
{
  "detail": "Ticker inconnu : XYZ. Titres disponibles : AAPL, … Pour en ajouter un : python -m backend.ingestion add XYZ",
  "problems": [{"line": 3, "field": "ticker", "value": "XYZ", "problem": "…"}]
}
```

`line` est le numéro de ligne tel que l'utilisateur le voit : celui du fichier
pour un import CSV, en-tête compris ; pour une saisie en JSON, celui que le
client fournit avec chaque position (`PositionIn.line`), par exemple le rang
dans son tableau ; `null` sinon. L'API ne l'interprète pas, elle le renvoie.
Sans lui, un refus de quantité en JSON ne portait ni ligne ni ticker
structuré, et le client n'aurait pu le rattacher à sa ligne qu'en lisant la
phrase.

Rien n'est écrit tant que tout n'est pas valide : les problèmes sont accumulés
et rendus ensemble, jamais levés au premier rencontré. Un import à moitié
appliqué produirait une valorisation plausible et fausse.

#### Import CSV

```
ticker;quantity;cost_basis
AAPL;40;185,20
MSFT;25;
```

L'en-tête est requis ; `cost_basis` est facultatif. L'import **remplace toutes**
les positions, comme le `PUT` : le fichier déposé *est* le portefeuille, et un
import qui ajouterait doublerait les quantités à chaque dépôt du même fichier.

« Un CSV » n'est pas un format. Sur un Windows français, « Enregistrer sous →
CSV » produit du **point-virgule**, du **CP1252** et des **décimales à la
virgule**. Trois choses sont donc déduites des octets, puis **rendues dans la
réponse**, parce que c'est de la provenance :

```json
"source": {"filename": "portefeuille.csv", "encoding": "cp1252",
           "delimiter": ";", "decimal_separator": ",", "rows_read": 6}
```

Encodages acceptés : UTF-8 avec BOM, UTF-8, CP1252 — la marque d'octets est
cherchée explicitement plutôt que tentée en premier, sans quoi un fichier sans
BOM serait annoncé « utf-8-sig », ce qui serait une provenance fausse. Les
espaces de milliers d'un tableur (fine insécable, insécable, ordinaire) sont
admis. La virgule décimale n'est acceptée qu'avec le séparateur `;` : avec `,`
en séparateur de champs, une virgule dans un nombre est une fin de colonne.
Fichiers limités à 1 Mo — un portefeuille fait quelques kilo-octets.

**Un nombre suit une grammaire, pas `float()`.** Une fois ses espaces de
milliers retirées, il doit s'écrire `[+-]chiffres[,|.chiffres]` : signe
facultatif, chiffres latins, au plus une décimale suivie de chiffres
(`csv_import.NOMBRE`). `float()`, qui servait jusqu'en 7B.3a, acceptait aussi
`1e3`, `inf`, `nan`, `1_000`, `.5` et des chiffres d'autres écritures : rien
de ce qu'écrit un tableur, et rien que le tableau de saisie saurait lire. Le
lecteur du client applique la même expression, et une liste de cas partagée
(`frontend/src/lib/nombres-saisis.json`) est lue par les deux suites de
tests : ils acceptent et refusent exactement les mêmes entrées. Le signe moins
reste admis à la lecture, pour que la validation refuse une quantité négative
avec la bonne explication.

**`decimal_separator` rend ce qui a été OBSERVÉ, pas ce qui était admis.** Avec
`;`, la virgule *est* acceptée — mais un fichier `;` dont les quantités s'écrivent
`40.5` n'en contient aucune, et annoncer `,` décrirait la règle de lecture plutôt
que le fichier. Quatre valeurs : `,`, `.`, `mixte` quand le fichier mélange les
deux écritures, et `aucune` quand tous les nombres sont entiers. Les deux
dernières sont des informations en soi — un fichier mixte sort d'un assemblage à
la main.

Sont refusés avec un message situé à la ligne : ticker inconnu, ticker sans
historique de prix, quantité nulle ou négative, doublon, en-tête absent,
colonne en trop non vide.

**Une colonne en trop n'est jamais ignorée en silence.** Le lecteur lisait les
colonnes qu'il connaissait et laissait tomber les autres : avec `,` en
séparateur, `ALFA,1,5` donnait la quantité 1 et `185,20` le prix de revient
185, sans un mot. Une ligne plus large que l'en-tête est désormais refusée :
« 3 colonnes lues, l'en-tête en a 2 », suivi de « avec le séparateur `,`, une
virgule décimale coupe le nombre en deux » quand le séparateur est la virgule
et que ce qui déborde n'est fait que de chiffres. Une colonne en trop VIDE —
le séparateur final d'un export de tableur — reste tolérée, en ligne comme en
en-tête. Le refus tombe à la lecture, avant toute écriture : une seule ligne
refusée, aucune position écrite.

**Le format est publié par le lecteur lui-même : `GET /api/csv-format`.**
L'écran d'import l'affiche en clair, sur place, et le lit là plutôt que d'en
garder une copie, qui deviendrait le format affiché le jour où le lecteur
changerait — même raison que pour `GET /api/disclaimer`. Chaque valeur vient
de la table ou de la constante que le lecteur consulte : colonnes requises et
facultatives, séparateurs de champs et décimales admises pour chacun
(`DECIMALES_ADMISES`, par laquelle le lecteur tranche lui-même), espaces de
milliers, encodages, taille et nombre de lignes maximaux, et un exemple — le
fichier ci-dessus. Les tests ne comparent pas la réponse à des constantes
recopiées : ils font lire au vrai lecteur chaque séparateur, chaque décimale,
chaque espace et chaque encodage annoncés, et importent l'exemple sur la copie
figée.

### 10. Frontend

La spécification visuelle est `frontend/DESIGN.md`, écrite avant la première
ligne de CSS. Elle fixe les tokens et les règles d'affichage ; elle se lit
intégralement avant d'y toucher.

```powershell
cd frontend
npm install                 # versions FIGÉES, package-lock.json commité
npm run dev                 # http://localhost:5173
npm test                    # Vitest
npm run build               # contrôle de types puis bundle dans dist/
```

**Deux processus en développement, un seul en production.** `npm run dev` sert
la page et relaie `/api` vers `python -m backend.api` sur 127.0.0.1:8000 ; en
production, FastAPI sert `frontend/dist` à la racine. Dans les deux cas le
navigateur ne voit qu'une origine, et **le backend n'a aucun middleware CORS** :
une permission qui ne servirait jamais en production est une permission qu'on
finit par élargir.

Sans `frontend/dist`, l'application démarre quand même et sert l'API seule : la
suite Python tourne sur une machine où Node n'a jamais été installé. Et le repli
sur `index.html` ne masque jamais l'API — `GET /api/nexiste-pas` rend un 404
JSON, pas la page, sans quoi une faute de frappe dans une URL deviendrait
indébogable (`backend/api/static.py`).

#### Les types de l'API sont engendrés, jamais écrits à la main

```powershell
python -m tools.openapi_schema      # écrit frontend/src/api/openapi.json
cd frontend; npm run api:types      # en dérive src/api/schema.ts
```

Le schéma est **commité**, et `tests/test_openapi_schema.py` le compare octet
pour octet à ce que l'application publie. Un champ ajouté à un schéma pydantic
sans régénération fait échouer la suite Python — du côté qui a changé, pas six
mois plus tard dans le navigateur. La génération lit ce fichier et non un
serveur en marche : un `npm run build` ne doit dépendre ni d'un uvicorn allumé
ni d'une base à jour, et en relisant un commit on doit pouvoir dire quel schéma
le frontend compilait.

#### Ce que le frontend ne fait pas

Il ne calcule **aucune mesure** — symétrique de la règle d'or de l'API. Ni
somme, ni écart, ni moyenne côté client : une valeur manquante s'ajoute au
moteur avec son test, puis au schéma. L'écart entre la VaR normale et la VaR
Student n'est donc pas soustrait, les deux chiffres sont posés côte à côte.

Deux disciplines sont vérifiées mécaniquement par `src/styles/tokens.test.ts` :
aucun code hexadécimal de couleur hors de `tokens.css`, aucune taille de police
en `px`. Comme `tests/test_api_discipline.py`, la garde porte sur le code et non
sur le texte brut — sinon elle se déclencherait sur sa propre explication.

`src/lib/format.ts` est le seul endroit qui écrit un nombre. Les caractères y
sont **fixés**, pas laissés à `Intl` : U+202F pour les milliers et avant « % »,
U+00A0 entre un nombre et le mot qu'il compte, U+2212 pour le signe négatif —
exactement ceux de `backend/typography.py`. La sortie d'`Intl` pour `fr-FR` a
changé d'espace selon les versions d'ICU, et Node et le navigateur en embarquent
de différents : un test écrit contre `Intl` passerait sans rien prouver.
`tests/test_typographie_partagee.py` tient les deux moitiés ensemble depuis la
suite Python, parce que c'est le backend qui bouge.

**L'espace fine avant « % » en Spectral, mesurée et non supposée.** Les
phrases du moteur, composées en Spectral, affichaient « 50% » alors que l'API
envoie bien U+202F. La cause, mesurée dans Chrome et dans les fichiers de
police :

- Le sous-ensemble latin de Spectral revendique U+202F dans sa
  `unicode-range` (U+2000-206F), mais son cmap ne le contient pas. IBM Plex
  Sans ne le contient pas non plus. Le navigateur ne cherche donc aucune
  autre police.
- Chrome synthétise une demi-espace de la police principale : 0,125 em en
  Spectral (1,75 px sur les phrases en 14 px), 0,118 em en Plex. Georgia
  seule donne aussi une demi-espace ; Times New Roman, qui a le glyphe,
  0,200 em.
- La largeur n'est donc pas nulle. C'est le blanc qui manque : Spectral serre
  ses chiffres, avec des approches de 33 et 12 unités autour de « 0 » et
  « % », contre 60 et 65 en Plex. Il reste 0,170 em de blanc en Spectral
  contre 0,243 em en Plex.

Le correctif est une police auto-hébergée de 644 octets, engendrée par
`tools/espace_fine.py`. Elle est déclarée dans la famille 'Spectral' pour
U+202F seulement, en 400 et en 500, après les faces de @fontsource. Elle
dessine une espace vide de 0,200 em, la largeur de Times New Roman, d'Arial
et de Cambria. Le blanc passe à 0,245 em, celui de Plex. Remesuré dans la
page : 0,200 em en Spectral, Plex inchangé, et la hauteur de ligne identique
avec ou sans l'espace fine. U+00A0 et U+2212 sont dessinés par les deux
familles elles-mêmes : 0,250 et 0,500 em en Spectral, 0,236 et 0,600 em en
Plex. `src/styles/typography.test.ts` lit la police sans décompresseur et
vérifie la déclaration.

Côté backend, tout nombre écrit dans une phrase passe par `backend/typography.py`
(`number`, `percent`, `signed_points`, `compact`), qui arrondit comme `toFixed`
et non comme le `format` de Python. `tests/test_nombres_publies.py` le vérifie
sur les RÉPONSES de l'API, chaîne par chaîne : aucun « 4.07 », aucun trait
d'union en guise de signe moins, quelle que soit la façon dont le nombre a été
écrit. Un nombre SAISI, cité dans un refus, passe par `exact` : la plus courte
écriture qui relit le même flottant, à la française — « Quantité nulle ou
négative pour MSFT (−3) » et non « (-3.0) ».

#### Les textes de lecture

Le lecteur visé part de zéro (DESIGN.md §1). Chaque mesure garde son libellé
technique et son chiffre, et reçoit en dessous trois éléments :

- une phrase concrète, qui dit la mesure en calendrier, en dollars et en
  période ;
- une ligne sur ce que le chiffre ne dit pas ;
- sa provenance, sous l'intertitre « Détails du calcul », jamais repliée.

Chaque section s'ouvre en outre sur la question à laquelle elle répond. Les
textes validés, avec leurs variantes et leurs garde-fous, sont dans
`textes-lecture.md`, hors dépôt.

**Composer n'est pas calculer.** Les phrases vivent dans `src/lib/phrases.ts`
et ne citent que des champs publiés (section 9, « Ce que citent les phrases
de lecture ») :

- La fréquence d'un niveau de confiance vient d'une table
  (`LECTURE_CONFIANCE`). « Un jour de bourse sur vingt, soit à peu près une
  fois par mois » est associé à 0,95, il n'en est pas dérivé. Un niveau absent
  de la table garde son nom technique.
- Le montant vient du moteur. L'arrondir à la dizaine de dollars est du
  formatage (`format.montantArrondi`), comme choisir des décimales.
- Une tournure ne dépend que du signe d'un champ publié : perte ou gain,
  « mais » ou « et », même sens ou sens inverse. Jamais d'une comparaison
  entre deux mesures.

**Ce que les phrases s'interdisent, et pourquoi.**

- « A perdu » : la composition d'aujourd'hui est rejouée sur le passé. D'où
  « aurait perdu », et un montant qui « représente » une part de la valeur
  d'aujourd'hui.
- « Perte attendue » sous une VaR : c'est un seuil, « 1,06 % ou plus ». La
  ligne de la VaR à 95 % cite la pire séance de la fenêtre, contre l'idée de
  plafond. Celle de la VaR à 99 % dit sur combien de jours elle repose.
- « La normale sous-estime vos mauvais jours » : sur le portefeuille de
  démonstration, la normale est la plus sévère des deux courbes à 95 %.
- Un montant pour le pire moment traversé d'une crise : il se mesure depuis
  un plus haut atteint pendant l'épisode. Sous le seuil de couverture de 80 %,
  aucune perte n'est citée.
- Une conclusion tirée d'un beta de crise estimé sur trop peu de jours.
- La variation de l'indice dans la phrase sur ce que le beta laissait
  attendre : 0,57 × 55,2 % ne redonne pas 36,7 %, puisque le moteur compose
  les rendements.
- Une lecture par la couleur des cases de corrélation : les nombres écrits
  portent l'information.

`phrases.test.ts` fige ces textes sur les chiffres du portefeuille de
démonstration, variantes comprises. `Measure.test.ts` vérifie l'ordre du bloc,
et qu'aucun `<details>` ne replie la provenance.

#### Aucun tiret cadratin dans l'interface

Décision du 2026-10-05 (DESIGN.md §6.3), sans exception : ni le client ni
l'API n'écrivent de tiret cadratin (U+2014). Dans une phrase, la ponctuation
dit le lien : deux-points, virgule, parenthèses ou point.

- **Lignes de seuil** : la valeur, puis la provenance après une virgule,
  puis la justification en phrase, sans second deux-points ni capitales
  (décision du 2026-10-05). « corrélation forte = 0,70, choisi à la main
  (non dérivé des données). Convention usuelle… »
- **Refus d'une ligne** : « Ligne 4 : XYZ n'est pas un titre connu. », suivi
  des titres disponibles. Le sujet vient d'abord, dans l'API comme dans le
  client, pour que la première phrase ne porte pas un second deux-points :
  la valeur citée ouvre la phrase (« dix » n'est pas une quantité lisible.),
  comme le mot qui manque (Quantité absente, 1 colonne(s) lue(s)…). Une
  valeur refusée se cite entre guillemets français, dans l'API comme dans le
  client (décision du 2026-10-05) ; l'import CSV la citait entre apostrophes
  droites. Après « Ligne N : », la minuscule, sauf devant un ticker
  (`phrases.messageDeLigne`).
- **Valeur absente** : c'est le seul tiret isolé de l'interface. Un tiret
  court (U+2013), écrit par `<Absent>` avec le texte « non disponible » pour
  un lecteur d'écran. Le bloc mesure, les tableaux et les chiffres d'une
  crise le rendent tous par `avecAbsence`.
- **Refus d'un champ de saisie** : le tiret qui le précédait devient un
  trait vertical de 2 px, celui du contour d'un champ refusé.
- **Bandeau d'acceptation** : une incise passe entre parenthèses. Le texte
  change, donc son empreinte aussi : l'écran d'acceptation revient une fois.

Deux gardes tiennent la règle. `tests/test_textes_publies.py` la vérifie sur
les réponses de l'API, puis sur chaque chaîne du code qui publie, parce que
les réponses de test ne déclenchent pas toutes les phrases. Il écarte la
documentation OpenAPI et le journal de la commande d'ingestion, que la page
n'affiche pas. `src/lib/ponctuation.test.ts` la vérifie sur les chaînes et le
JSX du client, ses feuilles de style et `index.html`, et refuse un tiret
d'absence posé sans `<Absent>`. Le tiret court d'une paire (« JNJ–KO »), le
signe moins et la flèche d'une période ne sont pas concernés ; ce README non
plus.

#### Le tableau du portefeuille sous 900 px

À 390 px, le tableau de la section 1 défilait dans son cadre de 342 px, et
l'ordre de DESIGN.md §8.2 (ticker, nom, quantité, prix, valeur, poids)
rejetait hors de l'écran les deux colonnes les plus utiles : Valeur
commençait à 339 px, Poids à 428. Sous 900 px, le point de rupture de la page,
l'ordre devient ticker, valeur, poids, puis nom, quantité, prix. Les trois
premières tiennent en 304 px sans défilement. Les trois autres ne sont pas
masquées, le cadre les fait défiler, la colonne du ticker restant en place.

Le CSS ne sait pas déplacer une cellule de tableau. L'ordre vient donc de
`useEtroit()` (`src/lib/largeur.ts`, `matchMedia`) plutôt que d'une colonne
dupliquée et masquée selon la largeur, qui doublerait le contenu du
document. Hors navigateur, l'ordre est l'ordre large. Le nom ne se coupe
plus : coupé, il faisait passer sa rangée sur trois lignes, loin des 36 px
de §9.3.

Une `<caption>` a la largeur de son tableau, pas celle de l'écran : à 390 px,
« Positions détenues, valorisées à la dernière clôture » courait sur 673 px
et se coupait au bord du cadre. Le cadre est un conteneur (`container-type:
inline-size`), et la légende est bornée à `100cqi` et collée à gauche : elle
passe à la ligne et ne défile pas avec les colonnes. Les refus sous une ligne
du tableau de saisie, dans une cellule qui couvre toute la rangée, suivent la
même règle. À 1280 px, cadre et tableau ont la même largeur : rien ne change.

L'en-tête d'un tableau n'est pas collant, à aucune largeur (DESIGN.md §9.3) :
dans le cadre qui défile à l'horizontale, il s'accrocherait au cadre et non à
la page. Seule la première colonne reste collante, à l'horizontale.
`DataTable.test.ts` lit la feuille de style et le vérifie, avec la première
colonne pour témoin.

#### La diagonale de la carte de corrélation

La corrélation d'une ligne avec elle-même vaut 1 par définition. Peinte à la
teinte la plus forte de l'échelle, la diagonale attirait l'œil sans rien
apprendre. Elle est désormais posée sur `--surface-1`, hors échelle, et son
« 1,00 » reste écrit en `--text-2`. `--surface-2` aurait été plus visible,
mais il se confond en thème clair avec le gris `--div-zero` d'une corrélation
nulle (#E7E5DE contre #DFDEDB). La légende nomme la diagonale. Le domaine de
l'échelle reste fixé à [−1, +1], puisqu'il ne dépend pas des cellules qu'elle
colore.

#### Acceptation

L'écran d'acceptation est une **page entière**, pas une modale : une modale se
clique sans lire. Le texte vient de `GET /api/disclaimer`, en lecture seule et
sans portefeuille — il précède l'existence du moindre portefeuille, et une copie
embarquée dans le bundle deviendrait le texte réellement lu le jour où le
bandeau changerait. L'acceptation est mémorisée dans le navigateur sous
l'**empreinte du texte** : on ne mémorise pas « a accepté » mais « a accepté ce
texte-là », et une limite reformulée fait revenir l'écran.

#### Les pages et leurs adresses

Quatre adresses, lues par `src/lib/route.ts` sans bibliothèque de routage :
`/`, `/portefeuilles`, `/portefeuilles/<id>` (l'analyse) et
`/portefeuilles/<id>/positions` (la saisie). De vraies adresses et non des
fragments : les fragments servent déjà aux ancres des sections, et une
adresse se recharge, se partage, s'ouvre dans un onglet. FastAPI rend
`index.html` pour toute adresse hors de `/api`, Vite aussi en développement.
Les liens internes restent de vrais `<a href>` (`components/Lien.tsx`) : clic
du milieu et Ctrl + clic ouvrent un onglet, comme partout.

- **`/`** rouvre le dernier portefeuille consulté, mémorisé dans le
  navigateur comme le thème, ou le premier de la liste, ou la liste vide.
  C'est une redirection, qui remplace l'entrée d'historique.
- **La liste des portefeuilles est chargée une fois**, puis relue après chaque
  écriture (`src/lib/liste.ts`). Chaque page y lit ce qu'elle doit savoir d'un
  portefeuille avant tout autre appel — qu'il existe, son nom, qu'il est vide
  (`positions`) —, sans attendre un 404 ni lire le texte d'un 409.
- **La page Portefeuilles** choisit, crée et supprime. La suppression se
  confirme sur place, sous le tableau ; la question reçoit le focus et nomme ce
  qui disparaît. Un menu déroulant dans le bandeau a été écarté : il changerait
  de page au moindre coup de flèche (WCAG 3.2.2). DESIGN.md §8.2.
- **Une annonce, une page.** Ce qu'une action vient de faire (« Portefeuille
  « Démo » supprimé. ») est écrit dans une seule région `role="status"`,
  présente même vide, et n'apparaît que sur la page à laquelle elle est
  adressée. Le chargement n'est pas annoncé : la page porte `aria-busy`.
- **Le focus suit la page.** Après une navigation décidée par l'utilisateur, le
  titre de la nouvelle page (`<h1 tabIndex={-1}>`) reçoit le focus, et
  l'onglet prend son titre. Pas au chargement, ni après une redirection.
- **La garde des modifications non enregistrées** : une page peut en poser une
  (`poserGarde`) ; toute navigation interne la consulte et, si elle refuse,
  rien ne bouge et la page affiche sa confirmation sur place. Le retour
  arrière du navigateur, qui ne se laisse pas annuler, remet la page courante
  dans l'historique avant de la consulter.

#### La page de saisie

`/portefeuilles/<id>/positions` (`views/Positions.tsx`,
`components/TableauSaisie.tsx`, `lib/saisie.ts`).

- **Le tableau est le portefeuille.** L'enregistrer envoie un `PUT`, qui
  remplace toutes les positions. Il s'ouvre sur les positions telles que
  stockées, prix de revient compris, et repart d'elles après chaque écriture.
  Un nombre stocké est réécrit avec juste assez de décimales pour se relire à
  l'identique : enregistrer le tableau sans y toucher ne change rien, ce
  qu'un test vérifie de bout en bout (import CSV de « 185,20 », puis renvoi
  par le tableau).
- **Le seul contrôle local est syntaxique** : un nombre tapé se lit-il ? Même
  grammaire que l'import CSV, et mêmes cas de test. Ticker inconnu, doublon,
  quantité nulle ou négative, ligne sans ticker : c'est le serveur qui les
  refuse, avec le numéro de ligne affiché (`line`), et chaque refus va sous
  sa ligne, relié à son champ (`aria-describedby`, `aria-invalid`). Une
  commande à lancer y sort en code. La liste des refus est reprise au-dessus
  du bouton, et reçoit le focus.
- **« Historique depuis »** montre la première séance de prix de chaque
  ligne, lue dans `/api/securities` : une ligne cotée depuis peu raccourcira
  la fenêtre de toute l'analyse, et on le voit avant d'enregistrer. C'est
  l'état « insuffisant » de cette page. Le prix de revient est facultatif, et
  la page dit qu'il ne sert à aucune mesure.
- **Des modifications non enregistrées ne se perdent pas en silence** :
  avertissement natif à la fermeture ou au rechargement (`beforeunload`), et
  garde sur la navigation interne, dont la question s'affiche sur place, en
  tête de page, focalisée.
- **Sous 900 px, la quantité suit le ticker.** À 390 px, l'ordre large
  (ticker, nom, historique, quantité, prix de revient) laissait la quantité
  hors du cadre de 342 px. Sous le point de rupture, l'ordre devient ticker,
  quantité, puis nom, historique, prix de revient, par `useEtroit`, comme le
  tableau de la section 1 ; la tabulation suit l'ordre affiché.
- **Chaque champ est nommé** par l'en-tête de sa colonne et le numéro de sa
  ligne (« Quantité ligne 3 »), sans libellé recopié. Pendant l'envoi, le
  bouton dit ce qu'il fait et se désactive ; il retrouve ensuite le focus.

#### L'import et le format affiché

- **Le format est celui que publie le lecteur** (`GET /api/csv-format`),
  affiché en clair par `components/FormatCsv.tsx` : l'exemple, un vrai
  fichier, puis les règles. Le frontend ne fait que nommer en français les
  codes publiés (`lib/csv.ts`). Il n'existe qu'un composant, montré partout
  où l'on arrive sans portefeuille ou sans position (§13) : la liste vide,
  l'analyse d'un portefeuille vide, la page de saisie.
- **Un vrai champ de fichier, et une zone de dépôt autour**
  (`components/DepotCsv.tsx`) : le champ natif se prend au clavier ; un
  fichier glissé lui est confié.
- **Rien n'est écrit sans confirmation.** Choisir un fichier ne l'importe
  pas : la phrase dit ce qui sera remplacé (« les 6 lignes actuelles de
  « Démo » ») et si le tableau porte des modifications non enregistrées, qui
  seront perdues ; le bouton dit le geste, « Importer le portefeuille ».
- **Ce qui a été lu** s'affiche après l'import comme une provenance :
  fichier, encodage, séparateur, décimale observée, lignes lues. Ce bloc
  reçoit le focus, le bouton d'import ayant disparu ; un import refusé rend
  le focus au bouton, désactivé pendant l'envoi.
- **Les messages du serveur sont découpés** (`segmenter`) : une commande
  `python -m …` sort en bloc, un littéral cité entre accents graves (« le
  séparateur `,` ») reste dans la phrase, en code. Un refus unique ne
  s'affiche qu'une fois, avec son numéro de ligne.
- **Limites connues** : pas d'aperçu, l'API n'ayant pas de lecture sans
  écriture ; et un fichier dont la lecture refuse une ligne ne passe pas à
  la validation, si bien qu'un ticker inconnu ailleurs dans le fichier ne
  se voit qu'au dépôt suivant.

#### Les quatre états de l'analyse

DESIGN.md §13 : vide, insuffisant, en cours, erreur, et pas seulement l'état
nominal (`views/Analyse.tsx`).

- **Vide** — le portefeuille n'a aucune position, ce que la liste dit sans
  appel d'analyse : une invitation, un lien vers la saisie, le format CSV.
- **Insuffisant, pour la page** — le moteur a les positions mais n'en tire
  pas d'analyse : l'API répond 409 (moins de trois séances communes, indice
  absent). C'est un état de la base, pas une panne : le message du moteur,
  sans le ton d'une alerte, la commande à lancer en bloc, un lien vers la
  saisie, et la section 1 depuis la valorisation de la liste.
- **Insuffisant, pour une mesure** — une fenêtre courte donne une analyse,
  où chaque mesure indisponible dit pourquoi, avec ce qui a été reçu et ce
  qu'il faut : corrélation, contributions, Student (« Pas assez de jours
  pour ajuster la loi de Student : il en faut au moins 30, la période en
  compte 7. »),
  Monte Carlo normal (« La fenêtre compte 7 séances pour 7 lignes »), crises
  non couvertes. Le bandeau nomme la ligne qui raccourcit la fenêtre.
  Vérifié sur une copie de la base où JMKE, SPCX et ASBH, cotés depuis 2026,
  ont été ajoutés par `ingestion add` : fenêtres de 40, 72 et 7 séances.
- **En cours** — la forme du début de la page, sans animation : section 1 et
  son tableau, puis deux blocs mesure ; `aria-busy`, et un titre de page lu.
- **Erreur** — le message de l'API et l'action suivante, « Recharger
  l'analyse ».

L'analyse est redemandée quand le CONTENU des positions change, et non leur
`updated_at`, daté au jour près : deux enregistrements le même jour auraient
sinon laissé l'analyse du premier.

## Schéma de données

Quatre tables (`backend/db/schema.sql`) :

| Table | Contenu | Clé |
|---|---|---|
| `securities` | Univers de titres suivis | `ticker` |
| `prices` | Historique quotidien OHLC + clôture ajustée + volume | `(ticker, date)` |
| `portfolios` | Portefeuilles : nom, propriétaire, date de dernière modification des positions | `id` |
| `positions` | Lignes d'un portefeuille (quantité, prix de revient optionnel) | `id`, unique sur `(portfolio_id, ticker)` |

Deux points de conception qui comptent pour la suite :

- **`prices.adj_close` est la seule colonne à utiliser pour les rendements.**
  Elle est ajustée des splits et des dividendes ; `close` brut fausserait les
  séries à chaque détachement de dividende.
- **La clé primaire `(ticker, date)` rend l'ingestion idempotente.** Un backfill
  rejoué ne crée pas de doublons.
- **`portfolios.updated_at` date les POSITIONS, pas l'enregistrement.** Il est
  écrit à chaque remplacement des positions, et jamais à la création : c'est la
  fraîcheur des positions qui informe, pas l'âge de la ligne. `NULL` se lit
  « jamais modifié depuis l'application » — vrai d'un portefeuille encore vide,
  et vrai des lignes antérieures à la migration, dont la date de modification
  n'est pas connue.

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
- [x] **Phase 4B — Mesures multi-titres** : covariance et corrélation sur
  données complètes, beta et R² vs SPY, VaR historique / paramétrique /
  Monte Carlo, CVaR avec taille de queue
- [x] **Phase 5A — Mécanique des scénarios** : catalogue déclaratif, bornes
  auto-vérifiées, achat-conservation, couverture déclarée, contributions
- [x] **Phase 5B — Régimes et queues épaisses** : comparaison régime calme /
  crise, Monte Carlo en loi de Student, biais de couverture documenté, bornes
  vérifiées sur fenêtre élargie
- [x] **Phase 6 — Moteur de règles** : six règles descriptives, contribution
  à la variance et lignes effectives en risque, seuils à provenance déclarée,
  avertissement permanent sur le CVaR à 99 %, aucun score global, texte du
  bandeau d'acceptation (vouvoyé)
- [x] **Phase 7A — API HTTP** : huit endpoints, analyse en une seule réponse,
  schémas pydantic explicites (aucun `asdict`), indéfinis rendus avec leur
  raison, matrices étiquetées, seuils à `kind` machine, import CSV résistant à
  Excel français, erreurs du moteur relayées en 4xx utilisables
  - Migration `portfolios` : `name` et `updated_at`, idempotente
  - Zéro arithmétique et zéro SQL dans `backend/api/`, vérifiés par test
  - Taille d'échantillon appliquée aux quatre règles qui lisent la covariance,
    sur la fenêtre EFFECTIVE ; refus des mesures dégénérées dans le moteur —
    corrélation, beta et contributions à la variance `null` avec une raison
    propre à chacune ; ligne limitante nommée avec sa première date
- [ ] **Phase 7B — Frontend**
  - [x] **7B.1 — Fondations** : Vite + React + TypeScript à versions figées,
    tokens et thème de `DESIGN.md` §4–§7, polices auto-hébergées, `format.ts`
    aux points de code fixés, client d'API, écran d'acceptation, bandeau
    permanent, `<Measure>` / `<Provenance>`, section 2 « Ce qu'il perd un jour
    ordinaire »
    - Publication de `estimation_window` : la fenêtre du panel de régime
      courant, sous son propre nom — le bandeau ne la déduit pas d'une mesure
    - `GET /api/disclaimer` en lecture seule, pour l'écran d'acceptation
    - FastAPI sert `frontend/dist` sans jamais masquer l'API ; aucun CORS
  - [x] **7B.2 — Page d'analyse et graphiques** : les six sections de
    `DESIGN.md` §8.2, Observable Plot à version figée derrière une enveloppe
    qui porte unité, fenêtre et date sous chaque titre et redessine au
    changement de thème ; navigation latérale, ancres en tête de page sous
    900 px
    - Publication des séries (rendements, richesse avec son point de départ),
      de l'histogramme en classes FIXES de 0,25 point comptées par le moteur,
      de la valorisation ligne à ligne et de la devise (`USD`, hypothèse du
      périmètre)
    - Tout nombre écrit dans un texte publié passe par `backend/typography.py`,
      vérifié sur les réponses de l'API
    - Copie de la base réelle figée au 2026-09-09 pour les tests qui la lisent
  - [x] **7C — Corrections avant 7B.3** : données, règles, retouches
    - Dividendes : `refresh` recharge tout l'historique d'un titre sur
      `divCash` comme sur split ; `ingestion rebuild` répare une base déjà
      écrite, après sauvegarde. Lancé par Maxence sur `data/mx_risk.sqlite`
      le 2026-09-28 (14 appels)
    - Tous les tests sur base réelle passent par la copie figée ; une garde
      l'impose
    - Règle 5 : une crise estimée sur trop peu de séances n'entre plus dans
      la conclusion, ni dans les faits qui la fondent
    - `<Observation>` : « Référence » pour une valeur du portefeuille ; un même
      nombre a la même forme dans la phrase et la ligne de seuil
    - Espace fine avant « % » en Spectral : une face qui dessine U+202F
    - Section 1 sous 900 px : ticker, valeur, poids d'abord ; diagonale de la
      carte de corrélation hors échelle ; `CLAUDE.md`
  - [x] **7B.3a — Saisie, import, choix du portefeuille, quatre états**
    - En-tête des tableaux non collant (DESIGN.md §9.3)
    - Correctifs du moteur trouvés en préparant l'état « insuffisant » : 409
      et non 422 à deux séances communes ; Student refusée au-delà de
      ν = 30, quatrième seuil choisi à la main ; `typography.number` écrit
      tout nombre fini
    - Monte Carlo normal et volet Student découplés : chacun sa raison
      (`monte_carlo_unavailable_reason`, `student_unavailable_reason`)
    - API : positions stockées dans la liste, numéro de ligne d'une saisie,
      format CSV publié ; colonne en trop d'un CSV refusée
    - Routes et page Portefeuilles : choix, création, suppression confirmée
      sur place ; `/` rouvre le dernier portefeuille consulté
    - Page de saisie : tableau éditable, refus rangés à leur ligne, garde des
      modifications non enregistrées ; un même lecteur de nombres pour le
      tableau et le CSV ; connexion SQLite d'une requête entre fils
    - Import CSV : zone de dépôt, confirmation de ce qui est remplacé,
      provenance de la lecture ; format affiché en clair dans les trois
      états vides
    - Les quatre états de l'analyse : vide, insuffisant (page et mesure,
      raison du Monte Carlo comprise), en cours, erreur
    - Correctifs relevés aux captures : VaR historique et CVaR refusées sous
      1/(1 − α) séances, seuil dérivé ; volatilité et VaR normale marquées
      minces sous 30 séances, cinquième seuil choisi à la main ; refus de la
      Student en clair, sans lettre grecque
    - Typographie publiée : espace insécable avant « : », « ; », « ? », « ! »
      et dans les guillemets, posée par `typography.prose` et vérifiée des
      deux côtés ; quantité refusée écrite par `typography.exact`
    - À 390 px : légendes et refus bornés à leur cadre ; dans le tableau de
      saisie, la quantité suit le ticker ; la légende de l'histogramme ne
      décrit que ce qui est tracé
  - [ ] **Textes de lecture** — chantier ouvert le 2026-10-05, avant le test
    utilisateur et la 7B.3b : chaque mesure dite en calendrier, en dollars et
    en période, pour un lecteur qui part de zéro
    - [x] Données publiées par le moteur : montants, retour au pic, pire
      séance, volatilité et nom de l'indice de référence, libellés de
      période, verdict de couverture d'un scénario
    - [x] Raisons de refus du moteur en clair, en jours de bourse : VaR et
      CVaR historiques, Student, mesures non estimables, crises et
      comparaisons de régimes indisponibles, lignes exclues d'une crise
    - [x] Sections 1 à 5 : phrase concrète, ligne « ne dit pas » et
      « Détails du calcul » sous chaque mesure, introduction de chaque
      section, libellés en mots courants ; DESIGN.md à jour, chiffres de
      §16 rafraîchis au 2026-09-25
    - [x] Section 6 : les observations du moteur de règles en mots
      courants, vouvoyées, avec leurs libellés ; réserves du moteur en
      jours de bourse. Réponse de référence : seuls des textes changent,
      aucun nombre
    - [x] Aucun tiret cadratin dans l'interface : ponctuation des textes
      publiés et affichés, tiret court et « non disponible » pour une
      valeur absente, gardes des deux côtés
  - [ ] 7B.3b — Méthodologie, checklist §17, tableaux équivalents aux
    graphiques
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
des hypothèses statistiques dont les limites sont documentées. Le texte complet
présenté à l'utilisateur figure dans la section « Texte du bandeau
d'acceptation ».
