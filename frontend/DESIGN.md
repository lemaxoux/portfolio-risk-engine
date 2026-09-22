# Design frontend — Mx Risk MGT

*Spécification visuelle de l'interface. Écrite avant la phase 7, pour que le
frontend soit une décision et non une accumulation de défauts. À lire
intégralement avant d'écrire la première ligne de CSS.*

---

## 0. À quoi sert ce fichier

Ce document fixe les **tokens** (couleurs, typographie, espacement) et les
**règles d'affichage** de l'application. Il a deux lecteurs :

- Claude Code, qui doit produire un frontend cohérent sans réinventer une
  palette à chaque composant ;
- un recruteur, qui doit voir qu'une interface de risque a été conçue à partir
  de contraintes méthodologiques et non à partir d'un template.

**Règle d'usage :** aucune valeur de couleur, de taille de police ou
d'espacement ne doit apparaître en dur dans un composant. Tout passe par les
variables CSS définies en §5, §6 et §7. Si une valeur manque, on l'ajoute au
jeu de tokens — on ne l'écrit pas localement.

---

## 1. Le sujet, le public, le travail de l'interface

**Le sujet.** Un moteur de risque de portefeuille dont l'argument central n'est
pas la précision, mais l'**honnêteté sur les conditions du calcul**. Six phases
de développement ont produit un backend où chaque résultat porte sa fenêtre
d'estimation, sa date de valorisation, sa méthode, le nombre d'observations qui
le composent, et — pour les seuils — s'il a été *dérivé* ou *choisi à la main*.

**Le public.** Un particulier qui investit lui-même, pas un gérant de risque
professionnel. Il comprend « une perte d'au moins 2,1 % une séance sur vingt ».
Il ne comprend pas « VaR₉₅ = 2,1 % » sans contexte, et il ne doit pas avoir à
faire semblant.

**Le travail de l'interface.** Rendre visible, sans clic, que chaque chiffre est
une *estimation sous conditions*. C'est le seul point sur lequel ce projet a
quelque chose que les concurrents n'ont pas. Une interface qui afficherait
« 2,1 % » en gros et cacherait la fenêtre d'estimation dans une infobulle
détruirait six phases de travail.

> **Le principe directeur, en une phrase :**
> *un chiffre et ses conditions sont un seul objet visuel — on ne peut pas voir
> l'un sans voir l'autre.*

Tout le reste de ce document découle de là.

---

## 2. Sites de référence — ce qu'on prend, ce qu'on laisse

| Référence | Ce qu'on prend | Ce qu'on laisse |
|---|---|---|
| **Tiingo** (tiingo.com) | Le registre : fournisseur de données sérieux, palette réduite, zéro effet. La sobriété est la marque de crédibilité du secteur. | La structure de site marketing. Ici on construit un outil, pas une landing page : pas de hero, pas de logos clients, pas de section « pricing ». |
| **Guardfolio** (guardfolio.ai) | Le concurrent direct le plus proche. On prend sa qualité de vulgarisation : des concepts quantitatifs formulés en langage courant pour un particulier, et un regroupement des mesures par *question posée* plutôt que par famille statistique. | **Son « Portfolio Health Score ».** C'est exactement le score global unique que la méthodologie de ce projet rejette (§11.1). On ne copie pas le dispositif central du concurrent qu'on a choisi de contredire. On laisse aussi l'agrégation multi-comptes, hors périmètre v1. |
| **FRED** (fred.stlouisfed.org) | **La meilleure référence du lot pour ce projet.** Chaque graphique porte, directement sous son titre et sans clic : la source, l'unité, la fréquence, la date de dernière mise à jour. C'est littéralement la discipline de provenance du backend, déjà résolue visuellement par une institution crédible. À imiter de près. | Son habillage daté (dégradés bleus, boutons biseautés). |
| **Portfolio Visualizer** | Le bloc « paramètres » affiché **au-dessus** des résultats : période, fréquence, benchmark, hypothèses. Le lecteur voit sous quelles conditions il lit avant de lire. | L'esthétique tableur des années 2010 et la densité de formulaire. |
| **Koyfin** | L'artisanat du tableau dense : alignement des colonnes de chiffres, hiérarchie des en-têtes, lisibilité à 13-14 px. | Son codage couleur de terminal (rouge/vert partout) — l'inverse exact de ce qu'on veut. |

**Ce qu'aucune des cinq ne fait et qui nous distingue :** afficher qu'un seuil a
été *choisi à la main*. Le backend le sait (`ThresholdKind.CHOSEN`), l'interface
doit le montrer.

---

## 3. Le parti pris visuel

Trois décisions, prises pour ce brief précis :

**3.1 — La couleur est rare, donc elle signifie.**
L'utilisateur a demandé un outil professionnel sobre, « pas un outil avec plein
de couleurs ». On va plus loin que « peu de couleurs » : on décide *à quoi sert*
chaque couleur. Il y en a quatre hors gris, et une seule raison d'usage chacune.
En particulier, **les pertes ne sont pas rouges**. Dans une application de
risque, presque tout ce qui est affiché est une perte (VaR, CVaR, drawdown,
scénarios) : les colorer en rouge ne distingue rien et transforme le tableau de
bord en alarme permanente. La magnitude est portée par la taille et la position,
pas par la teinte.

**3.2 — Un rapport, pas un cockpit.**
Pas de grille de tuiles identiques. L'interface est une colonne de lecture
ordonnée, qui déroule un raisonnement : *voici le portefeuille → voici ce qu'il
perd un jour ordinaire → voici ce qu'il a perdu au pire → voici qui porte le
risque → voici ce qui arrive en crise → voici ce que le moteur en conclut*.
L'ordre est l'argument. Une grille de KPI détruit l'ordre.

**3.3 — La typographie porte les chiffres, pas les titres.**
L'audace visuelle est dépensée à un seul endroit : le bloc « mesure » (§9.1),
où le chiffre, son unité et ses conditions forment un objet composé.
Les titres de section restent calmes.

---

## 4. Thème

Deux thèmes, commutables par l'utilisateur, **sombre par défaut si le système
le demande** (`prefers-color-scheme`), avec surcharge manuelle mémorisée dans
`localStorage`.

**Implémentation — le thème du système d'abord, la surcharge ensuite.** Si le
JavaScript ne s'exécute pas, la page doit quand même suivre le système :

```css
:root { color-scheme: light dark; /* + tokens du thème clair (§5.2) */ }
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) { /* tokens du thème sombre (§5.1) */ }
}
:root[data-theme="dark"]  { color-scheme: dark;  /* tokens sombres */ }
:root[data-theme="light"] { color-scheme: light; }
```

- `color-scheme` est obligatoire : sans lui, barres de défilement, champs de
  saisie et cases à cocher restent clairs dans le thème sombre. Doublé d'un
  `<meta name="color-scheme" content="light dark">` dans `<head>`.
- La surcharge est posée par un **petit script en ligne, bloquant, dans
  `<head>` de `index.html`** — pas dans le bundle React, qui est un module
  chargé après le premier rendu : l'utilisateur verrait un éclair du mauvais
  thème à chaque chargement.
- Choix mémorisé dans `localStorage`, lecture et écriture dans un `try/catch`
  (stockage bloqué ⇒ on suit le système, sans erreur).
- **Bascule à deux états**, pas trois : « comme le système » et « l'autre ».
  Choisir l'autre **fige** ce thème précis — si le système change ensuite,
  l'application ne suit pas.
- Aucun composant ne connaît le thème courant : tout passe par les variables.

- **Sombre : gris foncé, pas noir.** Fond `#1B1D1F`, pas `#000`. Un noir pur
  sur écran OLED crée un contraste de halo autour du texte fin et fatigue à la
  lecture prolongée de tableaux.
- **Clair : blanc cassé, pas blanc.** Fond `#F2F1EC`, pas `#FFF`. Registre
  papier / document, cohérent avec « un rapport, pas un cockpit ».

**Inversion volontaire de la logique des surfaces :** en sombre, une surface
surélevée est **plus claire** que le fond ; en clair, elle est **plus blanche**
que le fond. C'est l'inverse d'un simple « ajouter une ombre » : la hiérarchie
est portée par la luminance, et l'ombre portée est interdite (§12).

---

## 5. Couleurs

Tous les contrastes ci-dessous ont été **calculés**, pas estimés. Les valeurs
sont le ratio WCAG contre le fond de page du thème.

### 5.1 Thème sombre

```css
:root[data-theme="dark"] {
  --surface-0:       #1B1D1F;  /* page */
  --surface-1:       #232629;  /* bloc surélevé, ligne de tableau alternée */
  --surface-2:       #2C3033;  /* survol, en-tête de tableau */
  --border:          #41464C;  /* séparateurs de contenu */
  --border-strong:   #6F757B;  /* axes de graphique, bordures de champ (3,63:1) */

  --text-1:          #E9E7E2;  /* chiffres, titres            13,68:1 */
  --text-2:          #A2A8AE;  /* libellés, provenance         7,04:1 */
  --text-muted:      #8B9198;  /* désactivé/placeholder UNIQUEMENT */

  --accent:          #4FA69F;  /* sélection, état actif, lien  5,87:1 */
  --caveat:          #C9A227;  /* réserve méthodologique       6,99:1 */

  /* Couleurs de MARQUES graphiques (§5.4) — jamais de texte. */
  --series-1:        #1F9B92;  /* une série = une teinte */
  --loss:            #CB6E60;  /* = pôle brique de la divergente */
  --gain:            #3A95CD;  /* = pôle bleu de la divergente */
  --div-neg-strong:  #3A95CD;  /* −1 */
  --div-neg-mid:     #2F6081;  /* −0,5 */
  --div-zero:        #36383A;  /*  0 : gris neutre, distinct des surfaces */
  --div-pos-mid:     #804A41;  /* +0,5 */
  --div-pos-strong:  #CB6E60;  /* +1 */
}
```

### 5.2 Thème clair

```css
:root[data-theme="light"] {
  --surface-0:       #F2F1EC;
  --surface-1:       #FBFAF7;
  --surface-2:       #E7E5DE;
  --border:          #CBC7BC;
  --border-strong:   #868276;  /* 3,40:1 */

  --text-1:          #22252A;  /* 13,59:1 */
  --text-2:          #585E65;  /*  5,80:1 */
  --text-muted:      #6F6A62;  /*  4,74:1, désactivé uniquement */

  --accent:          #14615C;  /*  6,42:1 */
  --caveat:          #7E6110;  /*  5,15:1 */

  /* Couleurs de MARQUES graphiques (§5.4) — jamais de texte. */
  --series-1:        #058D85;
  --loss:            #A74639;
  --gain:            #1870A1;
  --div-neg-strong:  #1870A1;
  --div-neg-mid:     #7FB2D6;
  --div-zero:        #DFDEDB;
  --div-pos-mid:     #D6998F;
  --div-pos-strong:  #A74639;
}
```

### 5.3 À quoi sert chaque couleur — et rien d'autre

| Token | Seul usage autorisé |
|---|---|
| `--accent` | Élément sélectionné, onglet actif, lien, anneau de focus clavier. **Jamais** pour décorer un titre, un chiffre ou une bordure de bloc. |
| `--caveat` | Une seule chose : **ce chiffre repose sur quelque chose de contestable**. Concrètement : un seuil `ThresholdKind.CHOSEN`, le `caveat` permanent du CVaR 99 %, une fenêtre trop courte pour la régression, un scénario dont la couverture est incomplète. Un point plein de 6 px devant la ligne concernée, plus la phrase en `--caveat`. Jamais un fond coloré, jamais une icône d'alerte. |
| `--loss` / `--gain` | **Uniquement dans le tableau par ligne d'un scénario de stress**, seul endroit où le signe varie réellement d'une position à l'autre. Partout ailleurs, interdits. Ce sont des couleurs de **marque** (une petite barre à côté du chiffre), **jamais de texte** : le chiffre lui-même reste en `--text-1`. Le couple choisi est brique/bleu et non rouge/vert : un daltonisme deutan ou protan (≈ 8 % des hommes) rend rouge/vert indistinguables, brique/bleu non. Et la couleur y est le **troisième** canal, après le signe explicite (`+`/`−`) et l'ordre de tri. |
| `--series-1` | La teinte des données quand il n'y a **qu'une série** : barres de poids, barres de part de variance. Même famille que l'accent, à une luminosité de données ; l'état sélectionné se signale par un contour, jamais par ce remplissage. |
| `--div-*` | Uniquement l'échelle divergente de la heatmap de corrélation (§5.4). |

**Aucune couleur n'est jamais le seul porteur d'une information.** Test à
appliquer : passer la capture d'écran en niveaux de gris ; si une information
disparaît, le composant est faux.

### 5.4 Palettes de graphiques

**Toutes les couleurs de marques ont été validées par calcul**, pas à l'œil :
luminosité OKLCH dans la bande de chaque thème, chroma ≥ 0,10, contraste ≥ 3:1
contre les deux surfaces du thème, et séparation sous daltonisme protan et
deutan (simulation Machado 2009, ΔE OKLab). Le couple brique/bleu passe à
ΔE 16,2 (clair) et 16,1 (sombre) sous protanopie, pour un minimum requis de 8.
**Toute nouvelle couleur de graphique passe les mêmes contrôles avant d'entrer
dans `tokens.css`.**

**Règle : la couleur suit l'entité, jamais son rang ni sa valeur.** Une ligne
du portefeuille ne change pas de couleur parce qu'une autre a été ajoutée ou
parce que son poids a baissé. Conséquence directe : **un graphique à une série
prend une seule teinte** (`--series-1`) et le ticker est porté par l'axe. Six
positions ne demandent ni six teintes ni une rampe ordonnée par poids : la
longueur de la barre dit déjà le poids, la couleur n'a pas à le redire.

**Heatmap de corrélation — échelle divergente, domaine FIXÉ à [−1, +1].**

Point non négociable : le domaine ne s'adapte **jamais** aux données. Une
échelle auto-ajustée ferait paraître identiques un portefeuille dont la
corrélation maximale est 0,55 et un autre où elle est 0,97 — exactement la
comparaison que l'outil existe pour permettre.

Le positif (les positions bougent ensemble, le risque se concentre) va vers la
brique ; le négatif (diversifiant) vers le bleu. Les deux bras sont
**symétriques en luminosité** : une corrélation de −0,5 pèse visuellement
autant que +0,5. Le point médian est un **gris neutre distinct des surfaces**,
pas le fond lui-même : une cellule à zéro doit rester une cellule, sinon la
grille se désagrège et on ne distingue plus « nul » de « absent ».

```
          −1.0 (bleu)   −0.5       0.0 (gris)   +0.5     +1.0 (brique)
clair     #1870A1      #7FB2D6     #DFDEDB     #D6998F    #A74639
sombre    #3A95CD      #2F6081     #36383A     #804A41    #CB6E60
L OKLCH   .52 / .64    .74 / .47   .90 / .34   .74 / .47  .52 / .64
```

Interpolation en espace Lab entre ces cinq points. Les pas intermédiaires
(±0,5) tombent autour de 2:1 contre la surface : c'est admis pour une échelle
continue, **à condition que la valeur soit écrite dans chaque cellule** (deux
décimales, `--text-1` ou `--text-2` selon le fond). La valeur écrite est le
canal de secours, la couleur n'est qu'une lecture rapide.

Quand la corrélation n'est pas estimable (`correlation: null`), **on ne dessine
pas de heatmap vide** : on affiche `correlation_undefined_reason`, en texte.

**Contribution à la variance contre part de capital.** Une barre par ligne en
`--series-1` pour la part de variance, et un trait vertical fin en `--text-1`
à la position de la part de capital, sur le même axe. L'écart entre le bout de
la barre et le trait **est** le message ; il est aussi écrit en points à droite
(« +9,8 pts »). Légende explicite : « barre : part de la variance — trait :
part du capital ». Pas de barres appariées de deux couleurs.

---

## 6. Typographie

### 6.1 Les deux familles, et pourquoi

| Rôle | Famille | Raison |
|---|---|---|
| Chiffres, tableaux, libellés, contrôles | **IBM Plex Sans** | Possède de vrais **chiffres tabulaires** (`font-variant-numeric: tabular-nums`), condition non négociable pour aligner des colonnes de pourcentages. Terminaux légèrement équarris : lecture « instrument », pas « startup ». Excellente à 13-14 px. |
| Titres de section et **phrases du moteur de règles** | **Spectral** | Serif conçu pour l'écran, faible contraste, tient sur crème comme sur gris foncé. Usage **structurel, pas décoratif** : le backend produit des `Observation.statement` qui sont des *phrases*, pas des étiquettes. Les composer en serif distingue visuellement « ce que le moteur affirme » de « ce que le moteur a mesuré ». |
| Code, chemins d'API, format CSV d'import | IBM Plex Mono | Strictement réservé à du contenu réellement code. **Interdit pour les tickers, les libellés et les petits chiffres** (§12). |

Polices **auto-hébergées** via `@fontsource/ibm-plex-sans` et
`@fontsource/spectral` : aucune requête vers Google Fonts, aucun décalage de
mise en page au chargement, `font-display: swap`.

### 6.2 Échelle

Échelle modulaire de raison 1,25 (tierce majeure), base 16 px.

```css
--text-micro:  0.75rem;   /* 12px — unités et mentions liées à un chiffre    */
--text-sm:     0.875rem;  /* 14px — données de tableau, libellés, provenance */
--text-body:   1rem;      /* 16px — prose, phrases du moteur de règles       */
--text-lg:     1.25rem;   /* 20px — titres de section                        */
--text-xl:     1.5625rem; /* 25px — chiffre secondaire                       */
--text-2xl:    1.9375rem; /* 31px — chiffre principal d'un bloc mesure       */
--text-3xl:    2.4375rem; /* 39px — réservé : le chiffre du scénario de crise */
```

Graisses utilisées : **400** (prose, données), **500** (libellés, en-têtes),
**600** (chiffres mis en avant). Pas de 700, pas de 300.

### 6.3 Règles de composition

- **`font-variant-numeric: tabular-nums` sur tout élément contenant un chiffre.**
  Défaut global sur `table`, `.measure`, `.stat`. Sans ça, les colonnes dansent.
- Longueur de ligne : **< 80 caractères**, cible 66 pour la prose. Prose en
  Spectral : `line-height: 1.6`. Interface en Plex Sans : `1.45`. Chiffres
  principaux : `1.1`.
- **Casse phrase partout.** Pas de capitales sur les libellés (§12).
- **Format français obligatoire**, avec des caractères **fixés explicitement**
  et non laissés à `Intl.NumberFormat` : virgule décimale, **U+202F** (espace
  fine insécable) comme séparateur de milliers et avant `%`, **U+00A0** entre
  un nombre et le mot qu'il compte (« 504 séances », « 9,8 pts »). La sortie
  d'`Intl` pour `fr-FR` a changé de caractère d'espace selon les versions
  d'ICU : Node (où tournent les tests) et le navigateur peuvent différer, et
  un test qui passe ne prouverait rien. Le backend suit la même convention
  dans les phrases qu'il rédige : une interface qui afficherait `1.38%` à
  côté d'une phrase en `1,38 %` créerait deux conventions dans un même
  produit.
- Dates en `YYYY-MM-DD` dans les blocs de provenance (non ambigu, triable,
  cohérent avec l'API) ; en toutes lettres dans la prose.

---

## 7. Espacement, grille, formes

```css
--space-1: 4px;   --space-2: 8px;   --space-3: 12px;  --space-4: 16px;
--space-5: 24px;  --space-6: 32px;  --space-7: 48px;  --space-8: 64px;

--radius-sm: 3px;   /* champs, puces, cellules actives */
--radius-md: 6px;   /* blocs de contenu */
/* Il n'y a pas de --radius-lg ni de --radius-full. */
```

Deux rayons seulement, et ils sont **différents selon la hiérarchie** : un même
rayon appliqué à tout est un des marqueurs de template les plus reconnaissables.

**Grille.** Colonne de lecture centrée, `max-width: 1100px`, gouttière latérale
de 24 px minimum. Une barre latérale gauche de 220 px pour la navigation entre
sections, escamotée sous 900 px. Les tableaux peuvent déborder de la colonne de
lecture jusqu'à 1280 px, parce qu'un tableau tronqué ou en défilement
horizontal est pire qu'un tableau large.

**Alignement.** Libellés et prose à gauche. **Tous les chiffres à droite**, sans
exception, y compris dans les blocs mesure — c'est ce qui rend deux mesures
comparables d'un coup d'œil vertical.

---

## 8. Structure des écrans

### 8.1 Le bandeau permanent

Quelques informations s'appliquent à **tous** les chiffres de la page. Elles
ne défilent donc jamais : barre collante en haut, sur `--surface-1`.

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Mx Risk MGT      Portefeuille principal      83 185,85 $       [◐]      │
│           Valorisé au 2026-09-09   Fenêtre d'estimation : 504 séances     │
│                   Positions modifiées le 2026-09-21                       │
└──────────────────────────────────────────────────────────────────────────┘
```

`as_of`, la fenêtre d'estimation, la valeur du portefeuille et la date de
modification des positions sont dans le bandeau **parce qu'ils conditionnent
tout le reste**. C'est la traduction visuelle directe de la discipline du
backend. `[◐]` = bascule de thème.

- **Fenêtre d'estimation** — le bandeau lit `analysis.estimation_window`, la
  fenêtre du **panel de régime courant** publiée par l'API, et rien d'autre.
  Il ne la déduit pas d'une mesure : `risk.volatility.window` se trouve porter
  le même nombre aujourd'hui, et l'y lire promouvrait une mesure particulière
  en fenêtre du document par convention silencieuse — exactement ce que
  `AnalysisOut` refuse de faire. Le mot **estimation** borne la portée : les
  scénarios ont leurs propres périodes, et le bandeau ne parle pas pour eux.
  Chaque bloc `<Measure>` continue d'afficher la sienne ; le bandeau ne
  dispense de rien.

- **Fraîcheur des positions** (`portfolio.updated_at`) : l'`as_of` date les
  prix, pas les quantités. Si `updated_at` est nul : « Positions jamais
  modifiées depuis l'application ».
- **Fenêtre réduite** (`estimation_window.complete = false`) : point
  `--caveat` et la cause, en clair. C'est le seul endroit du bandeau où le
  nombre de séances **demandé** (`parameters.window`) apparaît. Si
  `limiting_positions` n'est pas vide : « Fenêtre réduite à 40 séances sur 504
  demandées : NEWCO n'est coté que depuis le 2026-07-14. » Si elle est vide :
  « Fenêtre réduite à 40 séances sur 504 demandées (historique incomplet) »,
  sans nommer de ligne — le backend ne nomme que ce qu'il a prouvé.
- Le bandeau peut passer à deux ou trois lignes : sa hauteur suit son
  contenu, elle n'est pas fixée à 56 px.

### 8.2 La page d'analyse

```
┌────────────┬─────────────────────────────────────────────────────────────┐
│            │  1. Le portefeuille                                         │
│ Portefeuille│     tableau : ticker, nom, quantité, prix, valeur, poids   │
│ ▸ Un jour   │     poids en barre dans sa cellule (--series-1)            │
│   ordinaire ├─────────────────────────────────────────────────────────────┤
│ ▸ Au pire   │  2. Ce qu'il perd un jour ordinaire                         │
│ ▸ Qui porte │     ┌─ mesure ─┐ ┌─ mesure ─┐ ┌─ mesure ─┐                  │
│   le risque │     │ Vol. ann.│ │ VaR 95 % │ │ VaR 99 % │                  │
│ ▸ En crise  │     └──────────┘ └──────────┘ └──────────┘                  │
│ ▸ Ce que le │     Histogramme des rendements quotidiens, avec les         │
│   moteur en │     quantiles VaR marqués et la queue CVaR ombrée.          │
│   dit       │     Sous l'histogramme : le couple normale / Student        │
│            │     côte à côte (§11.5).                                    │
│ ─────────── ├─────────────────────────────────────────────────────────────┤
│ Importer    │  3. Ce qu'il a perdu au pire                                │
│ Méthodologie│     Courbe de richesse + creux max ombré, dates de pic et   │
│            │     de creux annotées SUR la courbe, pas en légende.        │
│            ├─────────────────────────────────────────────────────────────┤
│            │  4. Qui porte le risque                                     │
│            │     Part de variance en barre, part de capital en trait     │
│            │     (§5.4). L'écart est le message.                         │
│            │     Concentration effective. Heatmap de corrélation.        │
│            ├─────────────────────────────────────────────────────────────┤
│            │  5. Ce qui se passe en crise                                │
│            │     Un bloc par scénario (§11.2). Régime calme vs crise :   │
│            │     beta et R² appariés.                                    │
│            ├─────────────────────────────────────────────────────────────┤
│            │  6. Ce que le moteur en dit                                 │
│            │     Liste d'observations (§9.2). Bandeau d'acceptation en   │
│            │     pied de section, pas en modale.                         │
└────────────┴─────────────────────────────────────────────────────────────┘
```

Autres écrans, volontairement pauvres : **saisie / import du portefeuille**
(tableau éditable + zone de dépôt CSV avec le format affiché en clair) et
**méthodologie** (le README rendu, une colonne de prose à 66 caractères).

---

## 9. Composants

### 9.1 `<Measure>` — le composant central

C'est le composant sur lequel repose la thèse du produit. Il rend un chiffre
**et** ses conditions comme un objet indissociable.

```
┌─────────────────────────────────────────┐
│ VaR 95 %, horizon 1 séance              │  text-sm / text-2 / 500
│                                         │
│                              1,38 %     │  text-2xl / text-1 / 600 / tabular
│ perte attendue 1 séance sur 20          │  text-micro / text-2
│ ─────────────────────────────────────── │  border, 1px
│ Méthode      paramétrique (normale)     │  text-micro, grille 2 colonnes
│ Fenêtre      504 séances                │  libellé text-2, valeur text-1
│ Période      2024-09-05 → 2026-09-09    │
└─────────────────────────────────────────┘
```

**Contrat.** Le bloc de provenance est **généré depuis les champs réels du
backend**, jamais saisi à la main : `VarResult.method`, `Window.observations`,
`Window.start` / `Window.end`, `VarResult.nu` quand il existe,
`ExpectedShortfallResult.tail_observations`.

**Règles dures :**

1. **La provenance ne peut pas être masquée.** Pas d'infobulle, pas
   d'accordéon, pas de « voir les détails ». Elle est dans le flux, à
   `--text-sm`/`--text-micro` mais en `--text-2` — jamais en `--text-muted`.
   *Il n'existe volontairement pas de troisième niveau de gris pour le texte de
   contenu*, précisément pour qu'on ne puisse pas effacer la provenance en la
   grisant.
2. **Convention de signe.** VaR et CVaR sont des **pertes positives** côté
   backend (`1,38 %` = « perte d'au moins 1,38 % »). L'interface les affiche
   telles quelles, avec la phrase de lecture en dessous. Elle n'ajoute **jamais**
   de signe `−`. Cas particulier à traiter explicitement : une valeur
   **négative** signifie un *gain* à ce niveau de confiance — le composant doit
   alors changer la phrase de lecture, pas juste afficher un nombre négatif.
3. **Une mesure indéfinie s'affiche indéfinie.** Quand `SortinoResult.annualised`
   est `None`, on affiche `—` et `undefined_reason` en toutes lettres. Jamais
   `0`, jamais `∞`, jamais un nombre astronomique. Le backend a déjà été corrigé
   deux fois sur des annulations catastrophiques produisant des ratios absurdes :
   l'interface ne doit pas réintroduire le problème en rendant l'absurde
   plausible.
4. **Réserve méthodologique.** Si le résultat porte un `caveat` (CVaR 99 %) ou
   un seuil `CHOSEN`, un point `--caveat` de 6 px précède le libellé et la
   phrase de réserve s'affiche sous le bloc de provenance.

### 9.2 `<Observation>` — ce que le moteur de règles affirme

Rendu depuis `rules.Observation` : `statement`, `facts`, `provenance`,
`thresholds`.

Les trois cas à distinguer visuellement — **c'est le point le plus important de
tout ce document** :

*Seuil dérivé d'une référence calculée* (`ThresholdKind.DERIVED`) — pas de point :

```
┌──────────────────────────────────────────────────────────────────┐
│  Contribution à la variance                                      │  text-sm/text-2
│  JPM pèse 25,6 % du capital et 35,4 % de la variance du          │  SPECTRAL
│  portefeuille : cette ligne porte 9,8 points de risque de        │  text-body
│  plus que de capital.                                            │
│                                                                  │
│  Référence : part de JPM dans la valeur = 25,6 % — référence     │  text-sm/text-2
│  calculée : au-dessus, la ligne pèse davantage dans le risque    │
│  que dans le capital ; en dessous, moins.                        │
│  Calculé sur 504 séances, au 2026-09-09.                         │
└──────────────────────────────────────────────────────────────────┘
```

*Seuil choisi à la main* (`ThresholdKind.CHOSEN`) — point `--caveat`, et la
mention « choisi » reste dans la phrase :

```
│  ● Seuil : corrélation forte = 70,0 % — seuil CHOISI à la main,  │  --caveat
│    non dérivé des données : convention usuelle pour qualifier    │
│    une corrélation de forte ; aucun calcul sur le portefeuille   │
│    ne la produit.                                                │
```

*Aucun seuil* (`thresholds == ()`) — **aucune ligne de seuil n'est affichée.**
C'est le cas de la concentration effective et de la part systématique : la
mesure parle d'elle-même. Ne pas inventer une ligne « seuil : n/a », ce serait
effacer exactement la qualité qu'on veut rendre visible.

`Threshold.__str__` produit déjà les trois formulations côté backend.
L'interface n'a qu'à les rendre — et à ajouter le point `--caveat` pour le seul
cas `CHOSEN`. Il n'existe aujourd'hui que **trois** seuils choisis à la main
dans tout le projet (corrélation forte 0,70 ; couverture minimale d'un scénario
80 % ; nombre minimal de séances d'une régression). Leur rareté est un résultat :
elle doit se voir.

### 9.3 Tableaux

Le composant le plus utilisé du produit. Il mérite du soin.

- En-tête sur `--surface-2`, graisse 500, casse phrase, collant au défilement.
- Séparateurs horizontaux `1px solid var(--border)` uniquement. **Pas de
  bordures verticales** : l'alignement des chiffres suffit à séparer les
  colonnes, et une grille complète alourdit inutilement.
- Colonnes de chiffres alignées à droite, tabulaires, même nombre de décimales
  dans toute une colonne.
- Survol de ligne : `--surface-2`. Pas de zébrage *en plus* du survol.
- Tri : indicateur sur l'en-tête actif en `--accent`, plus une flèche ▲/▼
  (la couleur seule ne suffit pas).
- Densité : hauteur de ligne 36 px, `--text-sm`.

### 9.4 Graphiques

- **Aucun graphique sans, directement sous son titre** : l'unité, la fenêtre,
  et la date `as_of`. Modèle FRED. Même discipline que `<Measure>`.
- Axes en `--border-strong`, grille en `--border`, **grille horizontale
  seulement**.
- Aucun dégradé de remplissage. Une aire se remplit d'une couleur à
  `opacity: 0.15`.
- Annotations **sur** le tracé (date du creux, niveau de VaR), pas en légende
  détachée quand il y a moins de 4 séries.
- Domaines : jamais d'auto-échelle pour la corrélation (§5.4). Pour les
  rendements, l'axe zéro est **toujours** visible — un axe tronqué exagère une
  variation, ce qui est une faute méthodologique, pas un choix esthétique.

---

## 10. Mouvement

Budget de mouvement : **très faible, et jamais au chargement**.

- Aucune animation d'entrée, aucun `fade-and-slide-up` de section. C'est le
  marqueur le plus courant d'une page générée.
- Transitions uniquement en réponse à une action : survol (120 ms), bascule de
  thème (180 ms sur `background-color` et `color`), ouverture d'un panneau
  (200 ms).
- `@media (prefers-reduced-motion: reduce)` : toutes les durées à 0.
- Le seul mouvement non déclenché autorisé, et facultatif : le tracé de la
  courbe de richesse qui se dessine **une fois**, en 600 ms, au premier rendu
  de la section 3. Une seule occurrence dans toute l'application.

---

## 11. Règles d'affichage non négociables

Ces six règles viennent des phases 4 à 6. Elles ne sont pas des préférences
esthétiques : ce sont les conclusions méthodologiques du backend traduites en
contraintes d'interface. Les enfreindre annule le travail des phases
précédentes.

**11.1 — Aucun score de risque global, nulle part.**
Ni note sur 100, ni jauge, ni feu tricolore, ni « Health Score », ni lettre.
Raison : agréger volatilité, concentration, beta et couverture de scénario en
un nombre unique suppose une pondération qui n'a aucune justification
théorique, et cache exactement les arbitrages que l'outil existe pour montrer.
C'est le dispositif central de Guardfolio, et le refuser est un choix de
produit assumé, à écrire dans le README.

**11.2 — La couverture d'un scénario a le même poids visuel que la perte.**
Un scénario qui projette −44,0 % en ne couvrant que 73 % du portefeuille n'est
pas le même énoncé qu'un scénario couvrant 100 %. Les deux chiffres sont dans
le même bloc, à la même taille de police. La perte n'a jamais le droit d'être
plus grosse que sa couverture.

```
┌──────────────────────────────────────────────────────────────────┐
│ Crise financière 2008 — 2007-10-09 → 2009-03-09                  │
│                                                                  │
│   À la sortie      Pire moment traversé    Couverture            │
│      −44,0 %            −47,5 %              100 %               │  ← même taille
│                                              6 lignes sur 6      │
└──────────────────────────────────────────────────────────────────┘

  et, quand la couverture est partielle :

┌────────────────────────────────────────────────────────┐
│   Perte projetée        Couverture du portefeuille     │
│         −44,0 %                    73 %                │
│                         ● 2 lignes sur 6 sans          │
│                           historique en 2007 ; la      │
│                           perte porte sur les 4 autres,│
│                           renormalisées.               │
└────────────────────────────────────────────────────────┘
```

La couverture porte le point `--caveat` **dès qu'elle est inférieure à 100 %**,
et pas seulement sous le seuil de 80 % : le seuil déclenche l'observation du
moteur de règles, l'affichage signale le fait.

**Trois chiffres, pas un.** `ScenarioResult` porte `end_to_end_return` (ce que
vaudrait le portefeuille à la sortie de l'épisode) **et** `max_drawdown` (le
pire moment traversé en chemin, qui peut être nettement plus profond). La
docstring du backend dit explicitement qu'il ne faut pas les confondre :
l'interface affiche donc les deux, côte à côte, à la même taille — plus la
couverture. Un scénario réduit à un seul chiffre laisse croire que le creux
s'est arrêté là où l'épisode s'est terminé.

**11.3 — La provenance est visible sans clic.** Détaillé en §9.1.

**11.4 — Une contribution à la variance est une amplitude, pas un verdict.**
Elle dit de combien une ligne fait bouger le portefeuille, **jamais dans quel
sens**. Sur le portefeuille de référence, XOM porte 13,9 % de la variance pour
15,8 % du capital — et c'est cette même variance qui a produit **+59,7 %**
pendant le resserrement de 2022, pendant que le portefeuille perdait 8,7 %.
Afficher une contribution à la variance seule, comme un danger, est donc une
erreur de lecture que l'interface a le devoir d'empêcher : toute vue de
concentration montre la contribution **et** le comportement réalisé en
scénario, dans le même bloc. Le backend le fait déjà — le moteur de règles
construit un « parcours » par ticker à travers les scénarios et écrit, pour
XOM, qu'il « a pesé dans les deux sens ».

**11.5 — La VaR normale et la VaR Student s'affichent en couple.**
Jamais l'une sans l'autre. L'écart entre les deux *est* l'information : il
chiffre le coût de l'hypothèse de normalité. Afficher les deux côte à côte, avec
ν (`VarResult.nu`) dans la provenance de la Student.

**11.6 — Un régime calme et un régime de crise ne se moyennent pas.**
Beta et R² s'affichent par régime, appariés, jamais fusionnés en une valeur
unique. Un beta de 0,57 en calme et de 1,07 en crise n'a pas de moyenne qui
veuille dire quelque chose.

---

## 12. Interdits

Chacun de ces points est soit un marqueur d'interface générée, soit une faute
au regard de §11.

**Interdits visuels**

- Ombre portée. La hiérarchie passe par la luminance des surfaces et par les
  bordures. Une seule exception : la barre collante, qui porte une bordure
  basse `1px` — pas une ombre.
- Un rayon de bordure unique appliqué à tout ; `border-radius: 9999px` sur des
  pastilles de statut.
- Dégradés, de fond comme de remplissage. Aucun.
- Les tuiles identiques en grille avec la même ombre douce sous chacune.
- Le noir pur `#000` et le blanc pur `#FFF`, en fond comme en texte.
- Rouge/vert pour les gains et pertes.
- Une couleur qui code le rang ou la valeur d'une ligne (rampe ordonnée par
  poids, ligne « la plus risquée » en rouge). La longueur ou la position le
  dit déjà ; la couleur suit l'entité.
- Une couleur de graphique en couleur de texte : un chiffre reste en
  `--text-1`, la couleur va sur la marque à côté.
- Émoji et icônes décoratives. Les icônes sont autorisées uniquement quand
  elles portent une fonction (tri, fermer, télécharger), en trait de 1,5 px.

**Interdits typographiques**

- Les libellés en CAPITALES, espacées ou non.
- Le « eyebrow » : une petite étiquette en capitales au-dessus de chaque titre.
- Les chaînes de méta jointes par des points médians (`A · B · C`) — la
  provenance est une **grille libellé / valeur**, qui est à la fois plus
  lisible et scannable.
- Une police monospace pour les tickers ou les petits libellés.
- Une flèche `→` accolée au texte des liens et des boutons.
- Mettre un seul mot d'un titre en italique, en gras ou en couleur.
- Les marqueurs numérotés `01 / 02 / 03`. Les sections de la page d'analyse
  sont numérotées `1.` à `6.` parce qu'elles **sont** une séquence de
  raisonnement — c'est l'unique numérotation autorisée.

**Interdits de fond**

- Tout score global (§11.1).
- Une infobulle comme seul emplacement d'une information de provenance.
- Un axe de graphique tronqué qui exclut zéro.
- Une échelle de corrélation auto-ajustée.
- Afficher `0` ou une valeur immense à la place d'une mesure indéfinie.

---

## 13. Accessibilité et états

- Texte : ratio ≥ 4,5:1 (valeurs calculées en §5). Éléments d'interface et
  limites de graphique : ≥ 3:1.
- Focus clavier : `outline: 2px solid var(--accent); outline-offset: 2px`.
  Visible sur **tous** les éléments interactifs. Jamais `outline: none`.
- Ordre de tabulation suivant l'ordre de lecture. Un lien « aller au contenu »
  en début de document.
- Tableaux : `<caption>`, `<th scope>`. Graphiques : `role="img"` et un
  `aria-label` qui énonce la conclusion, pas la forme (« VaR 95 % à 1,38 %,
  contre 1,95 % sous loi de Student »).
- **Les quatre états de chaque vue sont à dessiner, pas seulement l'état
  nominal** :
  - *vide* — aucun portefeuille : une invitation à agir, avec le format CSV
    affiché sur place ;
  - *insuffisant* — portefeuille chargé mais historique trop court pour la
    mesure : dire quelle mesure est indisponible et **pourquoi** (combien de
    séances manquent), pas un blanc ;
  - *en cours* — squelettes de la forme finale, pas un spinner centré ;
  - *erreur* — ce qui a échoué et l'action suivante, dans la voix de
    l'interface. Une erreur ne s'excuse pas et n'est jamais vague.

---

## 14. Stack et organisation

**Recommandation : Vite + React + TypeScript**, servi en fichiers statiques par
FastAPI. Pas de Next.js : il n'y a ni SSR, ni routes serveur, ni SEO à gérer —
l'API est déjà FastAPI. Ajouter Next.js ici, c'est ajouter une toolchain
complète pour six vues en lecture seule.

**Styles : CSS Modules + variables CSS.** Pas de framework utilitaire. La raison
est précise : ce document définit un jeu de tokens volontairement petit et une
douzaine de composants. L'intérêt d'un framework utilitaire est le stylage ad
hoc rapide — c'est-à-dire exactement ce qui éroderait la discipline de ce jeu de
tokens. *Si tu préfères Tailwind, c'est défendable, à une condition : que les
tokens de §5 à §7 soient la seule source de valeurs et que la palette par défaut
du framework soit désactivée.*

**Graphiques : Observable Plot.** Déclaratif, orienté marques, n'impose aucune
esthétique — ce qui compte ici puisque l'esthétique est dictée par ce document.
Il gère nativement les domaines fixes (§5.4) et les échelles divergentes.
Recharts imposerait son propre look et se verrait.

```
frontend/
├── DESIGN.md              ← ce fichier
├── src/
│   ├── styles/
│   │   ├── tokens.css     ← §5, §6, §7. SEUL endroit avec des valeurs brutes
│   │   ├── reset.css
│   │   └── typography.css
│   ├── components/
│   │   ├── Measure.tsx        ← §9.1
│   │   ├── Observation.tsx    ← §9.2
│   │   ├── DataTable.tsx      ← §9.3
│   │   ├── Provenance.tsx     ← grille libellé/valeur réutilisable
│   │   └── charts/
│   ├── lib/format.ts      ← Intl.NumberFormat('fr-FR'), un seul endroit
│   └── views/
```

`lib/format.ts` est le pendant frontend de la convention de signe du backend :
**un seul endroit** décide comment un pourcentage, une perte, une date et une
valeur indéfinie s'écrivent. Un composant qui formate un nombre lui-même est un
bug en attente.

---

## 15. Ton de l'interface

- Tout en français, casse phrase, verbes actifs. Un bouton dit ce qu'il fait :
  « Importer le portefeuille », pas « Valider ».
- Un même geste garde son nom du bouton au message de confirmation.
- Nommer les choses comme l'utilisateur les comprend. « Perte attendue une
  séance sur vingt » accompagne « VaR 95 % » — on ne remplace pas le terme
  technique, on le traduit à côté. Le particulier apprend le vocabulaire, ce qui
  est une valeur du produit.
- Les réserves méthodologiques sont écrites platement, sans dramatiser ni
  minimiser : « Moyenne de 6 séances seulement, sur une fenêtre de 504 :
  chacune pèse pour 17 % du chiffre. » Le backend produit déjà ces phrases —
  les afficher telles quelles.
- **Acceptation à la première utilisation — décision de la phase 6.** Le
  backend fournit un écran complet (`disclaimer.title`, `sections`,
  `confirmation`) : c'est une **page entière** avant le premier accès, avec la
  phrase `confirmation` comme case à cocher, pas une modale posée sur le
  dashboard. Une modale se clique sans lire ; une page qu'on traverse une fois,
  délibérément, non. Où mémoriser l'acceptation (navigateur ou API) est une
  décision de la 7B.
- Ensuite, un **rappel court et permanent** en pied de la section 6, en texte
  courant, sans case ni bouton.

---

## 16. Chiffres de référence — à utiliser dans les maquettes

Ces valeurs ont été **recalculées indépendamment** depuis la base locale
(`data/mx_risk.sqlite`, dernière clôture 2026-09-09) sur le portefeuille de
démonstration — AAPL 40, MSFT 25, JPM 60, JNJ 50, XOM 80, KO 120 — fenêtre de
504 séances, du 2024-09-05 au 2026-09-09. Elles reproduisent exactement les
constantes `DEMO_POIDS` et `DEMO_PARTS` de `tests/test_rules.py`.

**Ne pas inventer de chiffres dans les maquettes.** Une capture d'écran qui
circule avec des nombres faux est une erreur difficile à rattraper, et le
projet a déjà corrigé plusieurs fois des chiffres plausibles mais faux.

| Ligne | Poids en capital | Part de variance | Écart |
|---|---:|---:|---:|
| JPM | 25,6 % | 35,4 % | +9,8 pts |
| JNJ | 16,1 % | 7,9 % | −8,1 pts |
| XOM | 15,8 % | 13,9 % | −1,9 pts |
| AAPL | 15,2 % | 22,1 % | +6,9 pts |
| MSFT | 14,8 % | 15,4 % | +0,6 pts |
| KO | 12,6 % | 5,3 % | −7,3 pts |

- Valeur du portefeuille : 83 185,85 $ · 6 lignes · concentration effective 5,65
- Volatilité annualisée : 13,3 % (quotidienne 0,84 %)
- VaR 95 % paramétrique, 1 séance : 1,38 % — VaR 99 % : 1,95 %
- Scénarios, à parts figées depuis les poids actuels, couverture 100 % :

| Scénario | Période | À la sortie | Pire moment traversé | Ligne remarquable |
|---|---|---:|---:|---|
| Crise financière 2008 | 2007-10-09 → 2009-03-09 | **−44,0 %** | −47,5 % | JPM −64,9 % |
| Krach COVID | 2020-02-19 → 2020-03-23 | **−35,8 %** | −35,8 % | XOM −47,9 % |
| Resserrement 2022 | 2022-01-03 → 2022-10-12 | **−8,7 %** | −13,1 % | XOM **+59,7 %** |

Le resserrement 2022 est aussi le meilleur exemple de §11.2 : le portefeuille
sort de l'épisode à −8,7 % mais a traversé −13,1 % en chemin. N'afficher que le
chiffre de sortie ferait disparaître un tiers de la pire perte réellement vécue.

Régimes (beta calme 0,57 et R² 0,49 sur 504 séances) :

| Scénario | Beta de crise | R² de crise |
|---|---:|---:|
| Crise financière 2008 | 0,96 | 0,86 |
| Krach COVID | 1,07 | 0,98 |
| Resserrement 2022 | 0,73 | 0,79 |

La dernière ligne est l'exemple à utiliser partout où il faut illustrer §11.4 :
le portefeuille perd 8,7 % pendant que sa ligne énergie gagne 59,7 %.

---

## 17. Vérification avant de déclarer la phase 7 terminée

- [ ] Capture d'écran en niveaux de gris : aucune information perdue.
- [ ] Aucune couleur de graphique hors des tokens de §5 ; toute couleur ajoutée
      a passé les contrôles de §5.4 (bande, chroma, contraste, daltonisme).
- [ ] Recherche dans le code : aucun `#` hexadécimal hors de `tokens.css`.
- [ ] Recherche dans le code : aucun `px` de taille de police hors de
      `typography.css`.
- [ ] Chaque chiffre affiché a sa fenêtre et sa date visibles sans clic.
- [ ] Aucun score global nulle part.
- [ ] Un seuil `CHOSEN` est visuellement distinct d'un seuil dérivé.
- [ ] La heatmap de corrélation a le même domaine pour deux portefeuilles
      différents.
- [ ] Couverture de scénario et perte projetée ont la même taille de police.
- [ ] Navigation complète au clavier, focus visible partout.
- [ ] Les quatre états (vide, insuffisant, en cours, erreur) existent.
- [ ] Les deux thèmes testés sur la page d'analyse complète, pas seulement sur
      un composant.
- [ ] Rendu à 390 px de large sans défilement horizontal de page.
