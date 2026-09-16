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
│   ├── rules/           # Moteur de règles — décrit, ne prescrit pas
│   │   ├── rules.py     #   les six règles et leurs observations
│   │   ├── thresholds.py#   seuils et provenance
│   │   └── disclaimer.py#   texte du bandeau d'acceptation
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
(`ConcentrationResult.as_of`), qui est ponctuel et n'a pas de fenêtre.
Aucun chiffre ne doit être ininterprétable isolément.

### Mesures multi-titres

| Mesure | Convention | Hypothèse à connaître |
|---|---|---|
| Covariance / corrélation | observations **complètes** | jamais paire à paire : des recouvrements différents selon les couples peuvent rendre la matrice non semi-définie positive |
| Beta / R² | `β = Cov(r_p, r_m)/Var(r_m)` | régression sur rendements **bruts**, pas excédentaires |
| VaR historique | quantile empirique, `method="lower"` | aucune hypothèse de loi ; ne peut rien dire d'un choc pire que la fenêtre |
| VaR paramétrique | `−(μ + z_α·σ_p)`, `σ_p = √(wᵀΣw)` | normalité ; `μ = 0` par défaut |
| CVaR / ES | moyenne au-delà du quantile | porte son nombre d'observations de queue |
| Contribution à la variance | `wᵢ·(Σw)ᵢ / (wᵀΣw)` | somme exactement à 100 % ; poids ET corrélation ; peut être négative |
| Monte Carlo | Cholesky + tirages normaux, graine fixe | même hypothèse de normalité que la VaR paramétrique |
| Monte Carlo Student | ν par maximum de vraisemblance, échelle `S = Σ·(ν−2)/ν` | queues épaisses à covariance inchangée ; `ν ≤ 2` refusé |

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
bout** (ce que vaut le portefeuille à la sortie) et le **pire moment traversé**
(drawdown maximum intra-fenêtre), qui peut être plus profond. Le drawdown est
celui de la trajectoire du portefeuille, jamais la somme des pires points de
chaque ligne : cette dernière composerait un épisode fictif où toutes les lignes
toucheraient leur plancher le même jour.

**La couverture est déclarée, jamais silencieuse.** Un titre introduit en 2019
n'a rien à dire sur 2008. Trois comportements étaient possibles : faire échouer
tout le scénario (trop fragile), exclure la ligne en silence (dangereux — la
perte est sous-estimée et personne ne le voit), ou déclarer la couverture. Chaque
résultat porte donc le nombre de lignes couvertes et **la fraction de la valeur**
qu'elles représentent — en valeur et non en nombre de lignes, parce qu'écarter
une ligne à 1 % et une ligne à 40 % n'ont pas la même portée. En couverture partielle,
les chiffres portent sur la seule partie couverte, poids renormalisés : les
lignes exclues ne sont **pas** supposées stables, ce qui diluerait la perte dans
une valeur non rejouée. `summary()` ne peut pas présenter un chiffre comme
couvrant l'ensemble quand ce n'est pas le cas, et sans aucune ligne couverte
aucun chiffre n'est produit.

> **Direction du biais.** Les deux options disponibles sous-estiment la perte,
> par des mécanismes différents. Supposer les lignes exclues stables dilue la
> perte. Les exclure et renormaliser — l'option retenue — décrit la partie la
> plus établie du portefeuille : une ligne absente de l'historique d'une crise
> est par construction cotée plus récemment, donc en moyenne plus jeune et plus
> spéculative, précisément le profil qui aurait le plus souffert. Le biais
> s'aggrave quand la couverture baisse. La renormalisation reste le bon choix,
> puisqu'elle ne fabrique aucun rendement, mais la perte réelle aurait
> vraisemblablement été plus lourde ; `summary()` le rappelle.

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
35 % de la variance de ton portefeuille » est un fait vérifiable ; « tu devrais
l'alléger » est un conseil en investissement, que rien dans ce projet ne permet de
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
| 1. Concentration effective | lignes effectives en capital (`1/Σwᵢ²`) **et** en risque (`1/Σcᵢ²`), et l'écart entre les deux | aucun |
| 2. Contribution à la variance | part du risque face à la part du capital, et parcours de la ligne dans les crises rejouées | référence calculée : la part de capital de la ligne |
| 3. Diversification apparente | paires qui ont largement évolué ensemble ; sinon, la paire la plus corrélée | corrélation 0,70 **choisie** ; paire la plus corrélée, relative au portefeuille |
| 4. Part systématique | part de la variance expliquée par le marché, qui ne se dilue pas en détenant davantage d'actions américaines | aucun |
| 5. Dégradation en crise | part systématique en régime calme face à chaque crise rejouée | 60 séances **choisies** pour signaler un échantillon trop mince |
| 6. Couverture d'un scénario | portée d'un scénario incomplet et direction de son biais ; sous 80 %, aucun chiffre principal | 80 % **choisi** |

**La concentration se dit en capital et en risque.** Le nombre de lignes
effectives en capital seul est la plus flatteuse des deux lectures : un
portefeuille équilibré en montants peut porter l'essentiel de sa variance sur
quelques lignes volatiles et corrélées. L'écart entre les deux nombres est
l'observation la plus utile de la règle — le risque ne se répartit pas comme le
capital.

**Une couverture de scénario minimale à 80 %, choisie à la main.** Le biais de la
renormalisation est orienté : une ligne absente de l'historique d'une crise est
cotée plus récemment, donc en moyenne plus spéculative, et le chiffre calculé sur
le reste décrit la partie la plus solide du portefeuille. Un seuil plus strict
qu'un pile ou face s'impose. À 80 %, même si la partie exclue avait perdu deux
fois plus que la partie couverte, la perte de l'ensemble ne dépasserait le chiffre
affiché que d'un cinquième — contre moitié plus à 50 %.

**Le CVaR à 99 % porte un avertissement permanent, pas une règle.** À 99 %, la
queue ne compte que 1 % de la fenêtre : 6 séances sur 504. Un seuil « moins de 10
observations » serait allumé à chaque calcul, et une alerte permanente n'informe
plus. L'avertissement est donc attaché au chiffre lui-même
(`ExpectedShortfallResult.caveat`), plutôt que présenté comme une anomalie
détectée. Sur le portefeuille de démonstration, le CVaR à 99 % de 3,00 %
est accompagné de : « Moyenne de 6 séances seulement, sur une fenêtre de 504 : chacune pèse pour 17 % du chiffre. »

**Les seuils sont traités explicitement**, car ils sont le point faible de tout
moteur de règles. Par ordre de préférence : pas de seuil du tout quand la mesure
parle d'elle-même ; un seuil dérivé d'une référence calculée ; un seuil relatif au
portefeuille lui-même ; en dernier recours seulement, un nombre rond choisi à la
main. Chaque observation porte ses seuils et leur provenance, et un seuil choisi
le dit en toutes lettres — « seuil CHOISI à la main, non dérivé des données » —,
selon la même règle de provenance que les fenêtres d'estimation et les dates de
valorisation.

Illustration sur le portefeuille de démonstration (données au 9 septembre 2026) :

> Tes 6 lignes se comportent comme 5,7 lignes effectives en capital, mais comme 4,4 en risque (inverse de la somme des carrés des poids, puis des contributions à la variance). En capital, l'équipondération en donnerait 6. Le risque se concentre davantage que le capital : la lecture en capital seule est la plus flatteuse des deux.
>
> JPM pèse 25,6 % de la valeur du portefeuille et 35,4 % de sa variance. Sa part du risque dépasse sa part du capital de 9,8 points. Plus une ligne pèse dans la variance, plus elle pèse sur le résultat du portefeuille, dans les deux sens : à la baisse comme à la hausse. Dans les crises rejouées, la contribution de JPM au résultat du portefeuille a été négative à chaque fois, de −16,6 pts (Crise financière 2008) à −8,7 pts (Resserrement monétaire 2022).
>
> XOM pèse 15,8 % de la valeur du portefeuille et 13,9 % de sa variance. Sa part du risque est inférieure à sa part du capital de 1,9 point. Dans les crises rejouées, XOM a pesé dans les deux sens : −7,6 pts (Krach COVID), mais +9,4 pts (Resserrement monétaire 2022).
>
> Sur 504 séances, 49 % de la variance du portefeuille s'explique par les mouvements de SPY (R² 0,49). Cette part est du risque de marché : elle est commune aux actions américaines, et en détenir davantage ne la dilue pas. Les 51 % restants sont propres aux lignes détenues ; c'est sur eux seuls que la diversification entre lignes a prise.
>
> La part systématique du risque passe de 49 % en régime calme à 86 % (Crise financière 2008), 98 % (Krach COVID — échantillon trop mince) et 79 % (Resserrement monétaire 2022) dans les crises rejouées. Elle augmente dans les 3 crises rejouées : la diversification entre lignes s'est affaiblie précisément pendant les épisodes où elle aurait servi. Un R² de crise estimé sur moins de 60 séances repose sur un échantillon trop mince (Krach COVID).

### Texte du bandeau d'acceptation

Seulement le texte ; l'écran qui le portera relève de la Phase 7. Sa source est
`backend/rules/disclaimer.py`, qui tire la taille de la fenêtre de la configuration
du moteur : le texte ne peut pas annoncer 504 séances le jour où le calcul en
utiliserait un autre nombre. Le bandeau **vouvoie** alors que les observations
tutoient : c'est le seul texte du projet à portée quasi juridique, et un registre
formel l'y distingue du reste. Ce texte n'a pas été relu par un juriste.

> **Avant d'utiliser Mx Risk MGT**
>
> **Un outil informatif, pas un conseil.** Mx Risk MGT décrit des propriétés statistiques de votre portefeuille. Il ne constitue pas un conseil en investissement réglementé, ni une recommandation d'acheter, de vendre ou de conserver un titre. Il ne connaît ni votre horizon de placement, ni vos objectifs, ni votre situation fiscale, ni le reste de votre patrimoine : aucune de ses observations ne peut en tenir compte.
>
> **Aucune garantie d'exactitude.** Les données de marché proviennent d'un fournisseur tiers et peuvent comporter des erreurs, des retards ou des omissions. Les calculs reposent sur des hypothèses statistiques et peuvent eux-mêmes être erronés. Aucune garantie n'est donnée sur l'exactitude, l'exhaustivité ou l'actualité des données ni des calculs.
>
> **Les mesures décrivent un régime, pas un avenir.** Les mesures de risque courantes — volatilité, VaR, CVaR, beta, corrélations — sont estimées sur les 504 dernières séances de bourse, soit environ 2 ans. Elles décrivent le comportement du portefeuille pendant cette période. Elles ne prédisent pas son comportement futur, qui peut s'en écarter fortement, en particulier lors d'une crise.
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
remplacés par des doubles. La suite passe hors ligne et ne consomme pas de
quota.

### 9. API

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
des hypothèses statistiques dont les limites sont documentées. Le texte complet
présenté à l'utilisateur figure dans la section « Texte du bandeau
d'acceptation ».
