# Design frontend — Portfolio Risk Engine

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
professionnel. Il part de zéro : il n'a jamais entendu parler de VaR, de
volatilité, de corrélation ni de bêta. « VaR 95 % : 1,06 % » ne lui dit rien,
et « une perte d'au moins 1,06 %, une séance sur vingt », pourtant exact, guère
plus. Il comprend une fréquence dite en calendrier, un montant en dollars et
une période : « Ces deux dernières années, environ un jour de bourse sur
vingt, soit à peu près une fois par mois, votre portefeuille aurait perdu
1,06 % ou plus. Sur sa valeur d'aujourd'hui, 1,06 % représente environ
890 USD. » Il ne doit pas avoir à faire semblant.

**Le travail de l'interface.** Rendre visible, sans clic, que chaque chiffre est
une *estimation sous conditions*. C'est le seul point sur lequel ce projet a
quelque chose que les concurrents n'ont pas. Une interface qui afficherait
« 2,1 % » en gros et cacherait la fenêtre d'estimation dans une infobulle
détruirait six phases de travail. Une condition écrite dans des mots que le
lecteur ne comprend pas reste cachée, elle aussi : chaque chiffre est donc dit
en mots courants, sous son libellé technique (§9.1, §15).

> **Le principe directeur, en une phrase :**
> *un chiffre et ses conditions sont un seul objet visuel — on ne peut pas voir
> l'un sans voir l'autre.*

Tout le reste de ce document découle de là.

---

## 2. Sites de référence — ce qu'on prend, ce qu'on laisse

| Référence | Ce qu'on prend | Ce qu'on laisse |
|---|---|---|
| **Tiingo** (tiingo.com) | Le registre : fournisseur de données sérieux, palette réduite, zéro effet. La sobriété est la marque de crédibilité du secteur. | La structure de site marketing : pas de hero, pas de logos clients, pas de section « pricing ». La page d'accueil de la démonstration (§19) n'y fait pas exception : c'est une page de l'outil, une colonne de lecture. |
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
| `--caveat` | Une seule chose : **ce chiffre repose sur quelque chose de contestable**. Concrètement : un seuil `ThresholdKind.CHOSEN`, le `caveat` permanent du CVaR 99 %, une fenêtre trop courte pour la régression, une volatilité ou une VaR paramétrique estimée sur moins de 30 séances, un scénario dont la couverture est incomplète. Un point plein de 6 px devant la ligne concernée, plus la phrase en `--caveat`. Jamais un fond coloré, jamais une icône d'alerte. |
| `--loss` / `--gain` | **Uniquement là où s'affiche l'apport signé d'une ligne à un scénario de crise** : le tableau par ligne d'un scénario de stress (section 5) et le tableau des apports par crise rejouée de « Qui porte le risque » (section 4). Ce sont les seuls endroits où le signe varie réellement d'une position à l'autre ; dans la section 4, il empêche de lire une grosse part de variance comme une ligne qui fait perdre. Partout ailleurs, interdits. Ce sont des couleurs de **marque** (une petite barre à côté du chiffre), **jamais de texte** : le chiffre lui-même reste en `--text-1`. Le couple choisi est brique/bleu et non rouge/vert : un daltonisme deutan ou protan (≈ 8 % des hommes) rend rouge/vert indistinguables, brique/bleu non. Et la couleur y est le **troisième** canal, après le signe explicite (`+`/`−`) et l'ordre de tri. |
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
décimales). La valeur écrite est le canal de secours, la couleur n'est qu'une
lecture rapide.

**L'encre de la valeur est choisie par contraste avec sa cellule : `--text-1`
ou `--surface-0`, la plus contrastée des deux.** `--text-2` ne sert pas ici.
Aux extrémités de l'échelle, ni `--text-1` ni `--text-2` ne suffisent : sur la
brique de +1, `--text-1` ne donne que 2,6:1 en thème clair et 2,8:1 en thème
sombre. Sur ces cellules saturées, il faut l'encre inverse, la surface de la
page (`encreDeCellule`, `src/components/charts/correlation.ts`).

**La diagonale ne prend pas la couleur de +1.** La corrélation d'une ligne avec
elle-même vaut 1 par définition ; peinte à la teinte la plus forte, elle
attirerait l'œil sans rien apprendre. Elle est posée sur `--surface-1`, hors
échelle, et son « 1,00 » est écrit en `--text-2`. Pas sur `--surface-2`, qui se
confond en thème clair avec le gris `--div-zero` d'une corrélation nulle
(#E7E5DE contre #DFDEDB). La légende nomme la diagonale. Le domaine reste fixé
à [−1, +1].

**La légende de la carte** (décision du 2026-10-06). Sous la grille,
l'échelle de couleurs, cinq pastilles de −1,0 à 1,0, puis la clé de la
diagonale. La lecture de l'échelle (« +1 : les deux lignes bougent toujours
dans le même sens… ») passe à droite de la carte à partir de 900 px, dans la
place que des cellules de 64 px au plus laissent vide, le haut de ses
capitales sur le haut de la première rangée de cellules. Sous 900 px, elle
reste sous la grille, entre l'échelle et la diagonale. Le titre et ses
conditions courent sur toute la largeur.

Quand la corrélation n'est pas estimable (`correlation: null`), **on ne dessine
pas de heatmap vide** : on affiche `correlation_undefined_reason`, en texte.

**Contribution à la variance contre part de capital.** Une barre par ligne en
`--series-1` pour la part de variance, et un trait vertical fin en `--text-1`
à la position de la part de capital, sur le même axe. L'écart entre le bout de
la barre et le trait **est** le message ; il est aussi écrit en points à droite
(« +8,2 pts »). Légende explicite, en mots courants (§15) : « barre : part dans
les variations, trait : part dans la valeur ». Pas de barres appariées de
deux couleurs.

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
- **Justifié pour la prose longue au-delà de 900 px, avec coupure ; aligné à
  gauche partout ailleurs** (décisions du 2026-10-06). **Une ligne justifiée
  n'ouvre aucune espace de plus de 2,5 fois la normale, avec ou sans
  dictionnaire de césure** : seule la prose qui tient cette condition est
  justifiée. Mesurée dans Chrome, elle se réduit aux chapeaux et, depuis le
  2026-10-08, à la prose de la méthodologie. Les chapeaux sont justifiés à
  partir de 900 px avec `hyphens: auto` (la page déclare sa langue, `fr` ou
  `en-US`, sans quoi aucun mot ne se coupe) et la coupure de lignes
  ordinaire ; leur ligne la plus lâche est à 2,0, avec comme sans
  dictionnaire. **En anglais** (chantier 7D), la même règle, remesurée le
  2026-10-08 sur les six chapeaux des quatre analyses de la copie, à 1280 px :
  leur ligne la plus lâche est à 1,27 avec le dictionnaire de coupure anglais
  et à 1,78 sans lui. Ils restent justifiés ; un chapeau anglais qui
  dépasserait 2,5 serait aligné à gauche, en anglais seulement.
  **La prose de la méthodologie** (décision du 2026-10-08), ses paragraphes
  seulement, est justifiée à partir de 900 px grâce à des coupures
  conditionnelles (U+00AD) posées au build dans le texte livré
  (`contenu/coupures.ts`, `coupuresAuBuild.ts`) : avec `hyphens: auto`, elle
  montait à 3,35 en français et 3,16 en anglais sans dictionnaire, un mot
  long qu'aucune coupure ne venait rompre ; avec ses coupures, sa ligne la
  plus lâche est à 2,34 et 2,12, avec comme sans dictionnaire, à 900, 1024,
  1280 et 1440 px. Elle prend **`hyphens: manual`** : seules ces coupures
  servent, jamais le dictionnaire du navigateur, et la mise en page est la
  même partout, quoi que le visiteur ait téléchargé. Sous 900 px,
  **`hyphens: none`** : `manual`, la valeur par défaut, suivrait les coupures
  dans le texte aligné à gauche. Les coupures tombent dans les paragraphes
  (étiquette en tête comprise), jamais dans un titre, une liste, une
  formule, le texte d'un lien ou une entité ; au moins deux lettres avant
  une coupure et trois après ; aucune dans un mot qui porte une capitale ou
  un chiffre (« VaR », « Student », « S&P 500 ») ; les coupures que les
  motifs ne trouvent pas sont données dans une liste unique. La source ne
  change pas, et ses gardes la lisent telle qu'elle est écrite. Tout le reste est
  aligné à gauche, à toutes les largeurs, et passe en `text-wrap: pretty`, qui
  évite une dernière ligne d'un seul mot : légendes de tableau et de
  graphique, « Détails du calcul », lignes de seuil, cellules, libellés,
  boutons, messages d'erreur, et tout le texte sous 900 px.
  **Essayés justifiés, puis remis à gauche** : les phrases de lecture des
  mesures et les observations, dont les espaces montaient de 2,8 à 4,9 fois
  la normale, un groupe qui ne se coupe pas (« 890 USD »,
  « 4 septembre 2026 », « 8,3 points ») reportant toute sa largeur à la ligne
  suivante ; puis les introductions de section et l'écran d'acceptation, qui
  tenaient sous 2,5 avec le dictionnaire de césure français mais montaient à
  3,0 et 2,9 sans lui. Chrome télécharge ce dictionnaire après coup : un
  visiteur peut ne pas l'avoir. Mesurés le 2026-10-08 avec les coupures de
  la méthodologie, posées pour l'essai seulement : 2,18 pour les
  introductions, 1,64 et 1,60 pour l'acceptation, avec comme sans
  dictionnaire. **Ils restent alignés à gauche** (décision du 2026-10-09) :
  les coupures de la méthodologie sont posées au build dans un fichier du
  client, et ces textes n'en sont pas. Le texte de l'acceptation vient de
  l'API, et les introductions sont composées par le client, certaines au
  moment du rendu. Les justifier demanderait des coupures dans les réponses
  de l'API, ou les motifs de césure dans le bundle. La prose
  justifiée ne prend pas `pretty` : pour éviter une dernière ligne courte, il
  raccourcit les lignes d'avant, que la justification étire ensuite.
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
- **Format anglais en anglais** (chantier 7D), fixé de même des deux côtés
  (`format.ts`, `backend/typography.py`, ARCHITECTURE.md, « One formatter on
  each side ») : point décimal,
  virgule des milliers à partir de quatre chiffres (« 1,000 », « 504 »),
  aucune espace avant `%` (« 1.06% »), le même signe moins U+2212, U+00A0
  entre un nombre et le mot qu'il compte (« 504 sessions ») et dans une date
  longue (« April 4, 2025 », après le mois et après la virgule). Le
  singulier est réservé au nombre qui s'écrit « 1 » : « 1.9 points »,
  « 0 sessions ». Les dates de provenance restent en ISO.
- **U+00A0 avant « : », « ; », « ? » et « ! », après « « » et avant « » ».**
  Avec une espace ordinaire, le signe ou le guillemet fermant part seul en
  début de ligne : « Colonnes obligatoires » finissait une ligne que
  « : ticker » commençait. Chaque moitié tient la règle de son côté. Le backend
  la pose à la publication sur tout texte rédigé (`typography.prose`), vérifiée
  sur les réponses par `tests/test_textes_publies.py`. Le frontend l'écrit dans
  son code — `&nbsp;` dans le texte et les attributs JSX, `\u00a0` dans une
  chaîne, `cite()` pour un nom cité —, vérifiée sur le code source par
  `src/lib/ponctuation.test.ts`, qui lit les chaînes et le JSX avec le
  compilateur TypeScript (une recherche de texte prendrait chaque ternaire
  `a ? b : c` pour de la prose). L'espace est la même, insécable, devant les
  quatre signes : pas d'espace fine. **En anglais**, aucune espace, ni
  ordinaire ni insécable, avant ces signes, et des guillemets doubles “ ”
  sans espace intérieure, jamais « » ; un libellé de l'écran cité garde sa
  ponctuation hors des guillemets (“The worst days”.). La même garde le
  vérifie sur les fichiers anglais.
- **Une paire ne se coupe pas au tiret.** Une coupure de ligne est permise
  juste après un tiret court : « La paire la plus liée est JNJ– » finissait
  une ligne que « KO, à 0,42. » commençait. Le backend pose donc, à la
  publication, un caractère de liaison invisible et sans largeur (U+2060)
  après le tiret court d'une paire (`typography.prose`, vérifié par
  `tests/test_textes_publies.py`). Le tiret lui-même ne change pas. Le sujet
  d'une observation, qui peut être une paire, tient sur une seule ligne
  (`white-space: nowrap`).
- **Une date ne se coupe pas au trait d'union.** Une coupure de ligne est
  permise après le trait d'union d'une date ISO : sous « Détails du calcul »
  d'une observation, « valorisation au 2026-09- » finissait une ligne que
  « 25 » commençait (captures du 2026-10-05, à 390 px). Le backend pose le
  même caractère de liaison (U+2060) après chaque trait d'union d'une date
  citée dans un texte rédigé (`typography.prose`). Le client lie de même la
  date ISO d'une phrase qu'il compose (`dateISOLiee`, `format.ts`), dans les
  deux langues : la fraîcheur des positions et la fenêtre réduite du bandeau,
  l'unité et la description de la courbe de valeur, les poids figés d'une
  crise rejouée (l'anglais depuis le chantier 7D, après une date coupée à
  1280 px ; le français depuis le 7E). Une date affichée seule par le client
  dans sa propre cellule (« Valorisé au », liste des portefeuilles) n'est pas
  concernée : elle ne s'est jamais coupée, et le client ne cherche aucun motif
  dans un texte du backend.
- **Aucun tiret cadratin (U+2014) dans l'interface, sans exception** (décision
  du 2026-10-05) : ni dans ce que le frontend compose, ni dans ce que le
  backend publie. Dans une phrase, la ponctuation dit le lien : deux-points,
  virgule, parenthèses ou point : « en temps ordinaire et en crise (jamais
  moyennées) ». Le titre de l'onglet s'écrit « Analyse de « Démo » (Portfolio
  Risk Engine) ». Sur l'écran d'acceptation, c'est le titre de l'écran seul,
  « Avant d'utiliser Portfolio Risk Engine » : il nomme déjà le produit, qui
  n'est pas répété entre parenthèses (décision du 2026-10-10).
  **Un refus de ligne s'écrit « Ligne 4 : XYZ n'est pas un titre connu. »**
  Le sujet vient d'abord, pour que la première phrase ne porte pas un second
  deux-points (« Ligne 4 : ticker inconnu : XYZ »). Après le deux-points, la
  minuscule : « Ligne 2 : quantité manquante. », sauf devant un ticker.
  **Une valeur absente est le seul tiret isolé** : un tiret court (U+2013),
  écrit par `<Absent>` avec le texte « non disponible » qu'un lecteur d'écran
  lit à sa place. La raison de l'absence s'affiche à côté, comme avant (§9.1,
  règle 3). Le refus d'un champ de saisie, que précédait un tiret, porte à la
  place un trait vertical de 2 px, celui du contour d'un champ refusé.
  Ne sont pas concernés : le tiret court d'une paire (« JNJ–KO »), le signe
  moins (U+2212) et la flèche d'une période (→). Ce document et les
  commentaires du code ne sont pas l'interface : ils gardent leurs tirets. Les
  documents publics du dépôt (README.md, METHODOLOGY.md, ARCHITECTURE.md) n'en
  ont aucun (`tests/test_documents_publics.py`).
  Vérifié des deux côtés : `tests/test_textes_publies.py` sur les réponses de
  l'API et sur chaque chaîne du code qui les écrit ; `src/lib/ponctuation.test.ts`
  sur les chaînes et le JSX du client, ses feuilles de style et `index.html`.
- **Aucune lettre grecque dans la prose.** Spectral n'a pas de glyphe grec :
  ses sous-ensembles ne couvrent pas U+0370–03FF, et un « ν » y passe dans une
  police de repli où il se lit « v ». Le grec reste dans la provenance
  (« ν = 4,07 », « μ = 0 », « λ=0,94 »), écrite en IBM Plex Sans, qui l'a.
  `tests/test_textes_publies.py` refuse toute lettre grecque ailleurs que dans
  `method` et `detail` d'une mesure.
- **U+202F en Spectral : une face dédiée.** Ni Spectral ni IBM Plex Sans ne
  dessinent U+202F, et le sous-ensemble latin de Spectral le revendique dans
  sa `unicode-range` sans l'avoir : Chrome synthétise alors une demi-espace,
  et comme Spectral serre ses chiffres, « 50 % » se lit « 50% ». Une police
  de 644 octets (`src/styles/fonts/espace-fine.ttf`, engendrée par
  `tools/espace_fine.py`) est déclarée dans la famille 'Spectral' pour
  U+202F seulement, en 400 et 500 : une espace vide de 0,200 em, qui ramène
  le blanc au niveau de Plex. Mesures : archive du README français
  (`../README-fr.md`, hors dépôt), section 10.
- **Les formules de la méthodologie, en IBM Plex Sans.** Spectral n'a pas de
  lettre grecque : une formule, même d'une lettre (« σ »), s'écrit dans un
  élément en Plex Sans, en ligne ou en bloc, et la prose n'en contient
  aucune (`tests/test_methodologie.py`). Indices et exposants passent par
  `<sub>` et `<sup>` : Plex n'a ni ᵀ ni ᵢ. Deux signes ne sont dessinés par
  aucune des polices du produit, √ et ≥ : ils viennent de la police de
  repli, comme le √ et le → des provenances (décision du 2026-10-07 ; une
  face de complément ne se discutera que si les captures montrent un défaut
  visible). `src/contenu/methodologie.test.ts` tient la liste des caractères
  admis, établie en lisant les polices.
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

**Alignement.** Libellés et prose à gauche, sauf les chapeaux au-delà de
900 px, justifiés (§6.3). **Tous les chiffres à droite**, sans
exception, y compris dans les blocs mesure — c'est ce qui rend deux mesures
comparables d'un coup d'œil vertical.

---

## 8. Structure des écrans

### 8.1 Le bandeau permanent

Quelques informations s'appliquent à **tous** les chiffres de la page. À
partir de 900 px, elles ne défilent donc jamais : barre collante en haut, sur
`--surface-1`. **Sous 900 px, le bandeau défile avec la page** (décision du
2026-10-08, chantier 7E). À 320 × 225 px, la fenêtre d'un écran de
1280 × 1024 zoomé à 400 % (WCAG 1.4.10), il mesurait 309 px sur l'analyse de
démonstration, 372 avec une fenêtre réduite : collant, il couvrait toute la
fenêtre, à toute position ; à 390 px, il en prenait 274 à 317. Chaque mesure
garde sa fenêtre et sa date dans son bloc (§9.1, §17) : aucune provenance ne
se perd quand il sort de l'écran. Le seuil est celui de la mise en page
(`lib/largeur.ts`).

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│  Portfolio Risk Engine    Portefeuille principal   84 076,05 USD  [English] [◐]  │
│               Valorisé au 2026-09-25   Fenêtre d'estimation : 504 séances         │
│                       Positions modifiées le 2026-09-23                           │
└──────────────────────────────────────────────────────────────────────────────────┘
```

`as_of`, la fenêtre d'estimation, la valeur du portefeuille et la date de
modification des positions sont dans le bandeau **parce qu'ils conditionnent
tout le reste**. C'est la traduction visuelle directe de la discipline du
backend. `[English]` = bouton de langue (ci-dessous), `[◐]` = bascule de
thème.

La valeur s'écrit avec le **code ISO** de la devise publiée par l'API
(`valuation.currency`), jamais avec un symbole : à Montréal, « $ » sans
qualificatif se lit dollar canadien.

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
- **Mesure du 2026-10-10** (chantier 9.1b : le produit, qui s'appelait
  « Mx Risk MGT », devient « Portfolio Risk Engine »). Un constat de ce jour,
  dans Chrome, pas une valeur à tenir. La marque fait 193 px de large (128
  avant), sur une ligne à toutes les largeurs de 320 à 1440 px, et la page ne
  déborde à aucune. À 320 × 225, 390, 900 et 1280 px, dans les deux langues
  et les deux thèmes, la hauteur du bandeau n'a pas changé : 309 à 312, 274,
  176 et 102 px sur l'analyse de démonstration ; 372 à 375, 317, 184 et
  110 px avec une fenêtre réduite. Entre ces largeurs, la colonne de la
  marque, plus large de 46 px en français et de 66 px en anglais, décale
  d'autant les seuils du bandeau d'analyse : il tient sur une rangée à partir
  de 1107 à 1130 px selon la langue et le thème (1061 à 1079 px avant), et
  sur deux à partir de 641 px (575 à 595 px avant). Dans ces deux bandes, il
  a une rangée de plus qu'avant : 59 px sous 900 px, où il défile avec la
  page, et 74 px au-dessus, où il est collant (71 et 51 px avec une fenêtre
  réduite, plus 22 px sur deux bandes de même largeur, vers 700 et 1200 px,
  où les conditions passent à une par ligne). Le bandeau des autres pages ne
  change à aucune largeur. Accepté sans toucher à la feuille de style.

**Le bouton de langue** (chantier 7D, décisions du 2026-10-07 et du
2026-10-08). À côté de la bascule de thème, sur toutes les pages ; sur
l'écran d'acceptation, qui n'a pas de bandeau, en tête de la colonne, avant
le texte qu'un visiteur arrivé dans la mauvaise langue ne pourrait pas lire.
Comme la bascule, il dit ce que le clic fait : « English » sur la page
française, « Français » sur la page anglaise, chaque nom dans sa langue et
avec l'attribut `lang` de la langue visée. Son nom accessible commence par ce
libellé et le complète dans la langue de la page : « English (le site passe
en anglais) ». Pas d'état sous le libellé : la page dit déjà sa langue. Même
dessin que la bascule, sur une ligne.

- **Qui choisit.** Le choix est mémorisé dans le navigateur
  (`mx-risk-langue`). Au premier passage, la première langue du navigateur
  qui est du français ou de l'anglais décide, sinon le français, et rien
  n'est mémorisé tant que l'utilisateur n'a pas choisi. `?lang=en` (ou
  `?lang=fr`) sur n'importe quelle adresse impose la langue et la mémorise
  comme un choix, puis disparaît de l'adresse ; le bouton n'ajoute rien à
  l'adresse. Comme le thème, un script en ligne de `index.html` pose
  l'attribut `lang` de la page (`fr` ou `en-US`) avant le premier rendu : la
  coupure des mots en dépend (§6.3).
- **L'acceptation d'abord.** Passer à une langue dont l'écran d'acceptation
  n'a pas encore été accepté affiche cet écran à la place de la page, comme à
  l'arrivée (§15) ; la saisie, si elle a des modifications non enregistrées,
  pose d'abord sa question, comme pour un départ. Une langue déjà acceptée
  remplace le texte sur place : chaque appel à l'API porte la langue
  affichée (`?lang=`), et les pages se relisent.
- **À 390 px, le bandeau ne gagne pas en hauteur** : le bouton partage la
  ligne du thème. Sur le bandeau d'analyse, cette ligne est déjà pleine (la
  valeur, puis la bascule dont l'état tient sur deux lignes) : sous 32 rem de
  large, le bouton passe sous la valeur, à gauche de la bascule, et la
  valeur et le bouton empilés restent moins hauts qu'elle. Au-dessus, les
  trois tiennent sur une ligne.

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
│   moteur en │     quantiles VaR marqués et la queue CVaR ombrée, sauf     │
│   dit       │     ceux d'un niveau que le moteur refuse.                  │
│             │     Sous l'histogramme : le couple normale / Student        │
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

**Chaque section s'ouvre sur une introduction**, sous son titre : la question
à laquelle elle répond, en deux lignes et en mots courants. « Combien votre
portefeuille peut-il perdre en une journée ? On rejoue ces deux dernières
années sur sa composition d'aujourd'hui : c'est le passé, pas une
prévision. » De la prose, comme les chapeaux : Spectral, `--text-body`, mais
en `--text-1`, à la largeur de prose, alignée à gauche à toutes les largeurs
(§6.3). Elle ne remplace pas les chapeaux des sous-parties, qui expliquent un
choix de méthode.

**Section 1 sous 900 px.** L'ordre des colonnes devient ticker, valeur,
poids, puis nom, quantité, prix : à 390 px, l'ordre large rejetait hors de
l'écran les deux colonnes les plus utiles. Les trois premières tiennent sans
défilement ; les autres ne sont pas masquées, le cadre les fait défiler, le
ticker restant en place. Le nom ne se coupe pas (`nowrap`). L'ordre vient de
`useEtroit()` (`src/lib/largeur.ts`), le CSS ne sachant pas déplacer une
cellule.

Autres écrans, volontairement pauvres : **saisie / import du portefeuille**
(tableau éditable + zone de dépôt CSV avec le format affiché en clair).

**Méthodologie** (`/methodologie`, 7B.3b, décision du 2026-10-07) : comment
chaque chiffre est calculé, pour un lecteur qui part de zéro. Ce n'est pas
METHODOLOGY.md rendu, mais un texte propre à la page, dans un fichier de
contenu par langue (`src/contenu/methodologie.fr.md`) ; METHODOLOGY.md, en
anglais, reste la référence technique. Le texte suit l'ordre de l'analyse : ce que fait l'outil, les
données, les conventions, puis chaque mesure affichée, section par section
(ce qu'elle calcule, sa formule, ses hypothèses, ses limites), les crises
rejouées, les seuils et les refus. Chaque terme technique y est expliqué à
sa première apparition (§15). Il ne cite aucun chiffre d'un portefeuille,
seulement les constantes du moteur, que `tests/test_methodologie.py`
compare au moteur. Une colonne de prose en Spectral, à la largeur de prose,
ses paragraphes justifiés à partir de 900 px avec les coupures posées au
build, à gauche en dessous (§6.3). Les formules en IBM Plex Sans, en ligne ou en
bloc, chacune précédée de la phrase qui la dit en mots, sans bibliothèque de
mise en forme mathématique. Chaque partie et chaque entrée a une ancre fixe
(`#var-historique`), la même dans toutes les langues : c'est elle que vise
le lien d'une mesure vers sa méthode (§9.1, règle 5). Le rail liste les parties de la page,
sans numéro, puis les pages ; sous 900 px, la même liste en tête de page. Le
bandeau nomme le dernier portefeuille consulté, s'il existe encore, pour que
« Analyse » et « Positions et import » y mènent.

**Portefeuilles** (`/portefeuilles`, ajouté en 7B.3a) : le choix du
portefeuille affiché. Un tableau — nom (lien vers son analyse), lignes,
valeur, date de valorisation, date de modification des positions ; un
portefeuille vide ou non valorisable le dit dans sa ligne, avec la raison du
moteur —, une création explicite (un nom, puis le portefeuille existe, vide),
et une suppression confirmée **sur place**, sous le tableau, jamais en
modale : la question nomme ce qui disparaît avec lui, ses positions. Le
bandeau y mène par « Changer de portefeuille », sous le nom du portefeuille.
Un menu déroulant qui changerait de page à la sélection est écarté : il
déplace l'utilisateur au moindre coup de flèche (WCAG 3.2.2). `/` rouvre le
dernier portefeuille consulté, mémorisé dans le navigateur comme le thème, ou
à défaut le premier.

Sous les six sections, après un séparateur, le rail liste les pages de
l'application — « Analyse », « Positions et import », « Portefeuilles »,
« Méthodologie » —, la page courante marquée comme l'est la section en cours.
Sous 900 px, la même liste suit les ancres, en tête de page. La page
Portefeuilles, qui n'a pas de sections, a la même liste de pages : la
méthodologie s'atteint de partout. Hors de l'analyse, le bandeau se
réduit à la marque, au portefeuille en vue et à la bascule de thème : la date
de valorisation et la fenêtre d'estimation n'y conditionnent aucun chiffre.

---

## 9. Composants

### 9.1 `<Measure>` — le composant central

C'est le composant sur lequel repose la thèse du produit. Il rend un chiffre
**et** ses conditions comme un objet indissociable.

```
┌─────────────────────────────────────────┐
│ VaR 95 % historique, horizon 1 séance   │  text-sm / text-2 / 500
│                                         │
│                              1,06 %     │  text-2xl / text-1 / 600 / tabular
│ Ces deux dernières années, environ un   │  phrase concrète : text-sm / text-1
│ jour de bourse sur vingt, soit à peu    │  Plex Sans, alignée à gauche
│ près une fois par mois, votre           │
│ portefeuille aurait perdu 1,06 % ou     │
│ plus. Sur sa valeur d'aujourd'hui,      │
│ 1,06 % représente environ 890 USD. Les  │
│ autres jours, il aurait perdu moins, ou │
│ gagné.                                  │
│ Ce n'est pas un plafond : le pire jour, │  ce qu'il ne dit pas : text-sm / text-2
│ le 4 avril 2025, il aurait perdu        │
│ 5,87 %.                                 │
│ ─────────────────────────────────────── │  border, 1px
│ Détails du calcul                       │  intertitre : text-micro / text-2 / 500
│ Méthode      historique                 │  text-micro, grille 2 colonnes
│ Calcul       quantile empirique, …      │  libellé text-2, valeur text-1
│ Fenêtre      504 séances                │
│ Période      2024-09-23 → 2026-09-25    │
│ Méthodologie La VaR historique          │  lien vers l'entrée (règle 5)
└─────────────────────────────────────────┘
```

**Sous le chiffre, trois éléments, dans cet ordre.**

1. **La phrase concrète** dit la mesure en calendrier (« environ un jour de
   bourse sur vingt, soit à peu près une fois par mois »), en dollars
   (« environ 890 USD » sur la valeur d'aujourd'hui) et en période (« ces deux
   dernières années »). Deux ou trois phrases : elle ne tient plus en
   `--text-micro`. Elle passe en `--text-sm` et `--text-1`, alignée à gauche
   à toutes les largeurs (§6.3) et bornée à la largeur de prose. Elle est en
   IBM Plex Sans, puisque c'est l'interface qui la compose, pas le moteur
   (§6.1).
2. **Ce que le chiffre ne dit pas** : une phrase courte, sans étiquette, en
   `--text-2`. Elle manque quand la réserve du moteur le dit déjà, comme pour
   la CVaR à 99 %.
3. **« Détails du calcul »** : l'intertitre du bloc de provenance. Il nomme ce
   bloc, il ne le replie pas (règle 1). Sa dernière ligne mène à la méthode
   (règle 5).

Ces phrases sont composées dans `src/lib/phrases.ts`, à partir de champs
publiés et sans calcul. La fréquence vient d'une table, le montant et la
période viennent du moteur, et l'arrondi à la dizaine de dollars est du
formatage (`format.ts`). Une phrase ne choisit sa tournure que sur le signe
d'un champ publié : perte ou gain, même sens ou sens inverse.

**Contrat.** Le bloc de provenance est **généré depuis les champs réels du
backend**, jamais saisi à la main : `VarResult.method`, `Window.observations`,
`Window.start` / `Window.end`, `VarResult.nu` quand il existe,
`ExpectedShortfallResult.tail_observations`. Sa dernière ligne,
« Méthodologie », est la seule qui ne vienne pas d'un champ publié : un lien
vers la méthode (règle 5).

**Règles dures :**

1. **La provenance ne peut pas être masquée.** Pas d'infobulle, pas
   d'accordéon, pas de « voir les détails ». Elle est dans le flux, à
   `--text-sm`/`--text-micro` mais en `--text-2` — jamais en `--text-muted`.
   *Il n'existe volontairement pas de troisième niveau de gris pour le texte de
   contenu*, précisément pour qu'on ne puisse pas effacer la provenance en la
   grisant. L'intertitre « Détails du calcul » la nomme ; rien ne la replie.
2. **Convention de signe.** VaR et CVaR sont des **pertes positives** côté
   backend (`1,06 %` : « aurait perdu 1,06 % ou plus »). L'interface les
   affiche telles quelles, avec la phrase de lecture en dessous. Elle n'ajoute
   **jamais** de signe `−`. Cas particulier à traiter explicitement : une
   valeur **négative** signifie un *gain* à ce niveau de confiance — le
   composant doit alors changer la phrase de lecture, pas juste afficher un
   nombre négatif. Cette phrase ne cite aucun chiffre : elle devrait sinon
   retourner le signe de celui qui est affiché juste au-dessus.
3. **Une mesure indéfinie s'affiche indéfinie.** Quand `SortinoResult.annualised`
   est `None`, on affiche le tiret d'absence (un tiret court `–`, doublé de
   « non disponible » pour un lecteur d'écran, §6.3) et `undefined_reason` en
   toutes lettres. Jamais
   `0`, jamais `∞`, jamais un nombre astronomique. Le backend a déjà été corrigé
   deux fois sur des annulations catastrophiques produisant des ratios absurdes :
   l'interface ne doit pas réintroduire le problème en rendant l'absurde
   plausible. La raison prend la place de la phrase concrète, et la ligne
   suivante dit que l'absence de chiffre n'est pas l'absence de risque.
4. **Réserve méthodologique.** Si le résultat porte un `caveat` (CVaR 99 %) ou
   un seuil `CHOSEN`, un point `--caveat` de 6 px précède le libellé et la
   phrase de réserve s'affiche sous le bloc de provenance.
5. **Le lien vers sa méthode** (chantier 7E, décisions du 2026-10-08). La
   dernière ligne des « Détails du calcul » est « Méthodologie », puis un lien
   par entrée de la méthodologie qui explique la mesure
   (`/methodologie#var-historique`), selon l'annexe A de la proposition de
   méthodologie, réunie dans `contenu/methodes.ts`. Le texte d'un lien est le
   titre de son entrée, dans la langue de la page ; dans une même ligne, les
   entrées qui suivent la première prennent une minuscule initiale, sauf un
   sigle (« Les trois chiffres d'une crise, la couverture »). Une valeur
   refusée ajoute « Quand l'outil refuse un chiffre ». Le lien ne replie rien
   et ne remplace aucune ligne publiée. `methode` est obligatoire sur
   `<Measure>` et `<Graphique>` : un bloc sans lien ne compile pas. Le même
   lien termine les conditions d'un graphique (§9.4), la ligne « Détails du
   calcul » d'une crise rejouée et les lignes de conditions des sections 1
   et 6 ; il suit le tableau de la section 4, chaque tableau de sensibilité
   et chaque raison de refus qui remplace un bloc. Le bandeau n'en porte pas.
   Chaque lien a une clé, son bloc et son ancre (les deux liens « La VaR
   historique » de la section 2 restent distincts) : au retour arrière depuis
   la méthodologie, il reprend le focus, amené sous le bandeau comme une
   ancre, même si la langue ou le thème ont changé là-bas (§13).

### 9.2 `<Observation>` — ce que le moteur de règles affirme

Rendu depuis `rules.Observation` : `statement`, `facts`, `provenance`,
`thresholds`. La provenance s'y lit sous le libellé « Détails du calcul »,
comme sous un bloc mesure (§9.1).

**Les observations parlent au même lecteur que les phrases de lecture**
(§1, §15). Le moteur de règles les rédige en mots courants : il vouvoie, dit
« variations » pour la variance, « la part qui suit le marché » pour la part
systématique, « jours de bourse » pour les séances, et la période en mots
(« ces deux dernières années »). Le libellé de chaque règle suit : « Combien
de lignes, en réalité », « Poids dans les variations », « Lignes qui bougent
ensemble », « Part qui suit le marché », « Le portefeuille en crise »,
« Crise rejouée en partie ». Le terme exact reste dans les lignes de seuil et
dans les détails du calcul, qui ne changent pas. L'interface affiche ces
phrases telles quelles, alignées à gauche à toutes les largeurs (§6.3).

**Le sujet, à côté du libellé**, dit de quoi parle l'observation : un ticker,
une paire, le nom d'une crise, ou « portefeuille ». Ce n'est jamais une clé
technique : une crise rejouée en partie a pour sujet « Crise financière
2008 », pas `gfc_2008`. Il n'est pas affiché quand le libellé le dit déjà :
« Le portefeuille en crise » ne se double pas d'un « portefeuille ».

Les trois cas à distinguer visuellement — **c'est le point le plus important de
tout ce document** :

*Seuil dérivé d'une référence calculée* (`ThresholdKind.DERIVED`) — pas de point :

```
┌──────────────────────────────────────────────────────────────────┐
│  Poids dans les variations   JPM                                 │  text-sm/text-2
│  JPM représente 24,5 % de la valeur du portefeuille et 32,7 %    │  SPECTRAL
│  de ses variations, soit 8,2 points de plus. Plus une ligne      │  text-body
│  pèse dans les variations, plus elle pèse sur le résultat, à la  │
│  baisse comme à la hausse. Dans les crises rejouées, JPM a       │
│  coûté au portefeuille à chaque fois, de 15,9 points (Crise      │
│  financière 2008) à 8,3 points (Resserrement monétaire 2022).    │
│                                                                  │
│  Référence : part de JPM dans la valeur = 24,5 %, calculée sur   │  text-sm/text-2
│  ce portefeuille. Au-dessus, la ligne pèse davantage dans le     │
│  risque que dans le capital ; en dessous, moins.                 │
│  Détails du calcul   fenêtre d'estimation : 504 séances,         │
│  2024-09-23 → 2026-09-25                                         │
└──────────────────────────────────────────────────────────────────┘
```

*Seuil choisi à la main* (`ThresholdKind.CHOSEN`) — point `--caveat`, et la
mention « choisi » reste dans la phrase :

```
│  ● Seuil : corrélation forte = 0,70, choisi à la main (non       │  --caveat
│    dérivé des données). Convention usuelle pour qualifier une    │
│    corrélation de forte ; aucun calcul sur le portefeuille ne    │
│    la produit.                                                   │
```

La ligne de seuil s'écrit en casse phrase (§6.3, décision du 2026-10-05) :
la valeur, puis la provenance après une virgule, puis la justification en
phrase. Elle portait un second deux-points et le mot « CHOISI » en capitales.
La provenance dit d'où vient la valeur : « choisi à la main (non dérivé des
données) », « démontré (le même pour tout portefeuille) » pour les 3 séances
estimables, et, pour une référence, « calculée sur ce portefeuille », accordé
avec le nom du seuil (décision du 2026-10-06). Une référence disait
« référence calculée » ou « relatif au portefeuille ».

*Aucun seuil* (`thresholds == ()`) — **aucune ligne de seuil n'est affichée.**
C'est le cas de la concentration effective (« Combien de lignes, en réalité »)
et de la part systématique (« Part qui suit le marché ») : la mesure parle
d'elle-même. Ne pas inventer une ligne « seuil : n/a », ce serait
effacer exactement la qualité qu'on veut rendre visible.

`Threshold.__str__` produit déjà les trois formulations côté backend.
L'interface n'a qu'à les rendre — et à ajouter le point `--caveat` pour le seul
cas `CHOSEN`. Il n'existe aujourd'hui que **cinq** seuils choisis à la main
dans tout le projet (corrélation forte 0,70 ; couverture minimale d'un scénario
80 % ; nombre minimal de séances d'une régression ; ν maximal d'une loi de
Student, 30 ; nombre minimal de séances pour estimer une loi, 30). Leur rareté
est un résultat : elle doit se voir.

Le cinquième non plus n'apparaît dans aucune observation. Sous 30 séances, le
moteur n'ajuste pas de loi de Student, et il marque la volatilité et la VaR
paramétrique normale comme estimations minces : point `--caveat` devant le
libellé, phrase du moteur sous la provenance (§9.1, règle 4), qui dit
« seuil choisi à la main ». Le chiffre reste affiché — il bouge avec les
données —, et aucune règle ne le lit.

Le quatrième n'apparaît dans aucune observation : c'est le moteur qui
l'applique, en refusant l'ajustement de la Student au-delà de ν = 30. Il se
lit dans la phrase qui remplace la VaR Student en section 2
(`student_unavailable_reason`), qui dit « seuil choisi à la main » et
n'écrit jamais ν.

### 9.3 Tableaux

Le composant le plus utilisé du produit. Il mérite du soin.

- En-tête sur `--surface-2`, graisse 500, casse phrase. **Pas d'en-tête
  collant.** Un tableau trop large défile à l'horizontale dans son propre
  cadre (`overflow-x: auto`), et ce cadre devient le conteneur de défilement
  de ses cellules : un en-tête collant s'y accrocherait, pas à la page, et ne
  collerait donc jamais, à aucune largeur. Le faire coller demanderait un
  défilement vertical imbriqué (piège au pouce sur mobile) ou un en-tête
  dupliqué et synchronisé en script. Les tableaux du produit font au plus une
  quinzaine de lignes : l'en-tête reste presque toujours visible, le coût ne
  se justifie pas. Les tableaux des valeurs d'un graphique (§9.4) en font
  davantage, jusqu'à quelque 500 rangées pour la courbe de valeur ; ils sont
  repliés par défaut, et leurs deux ou trois colonnes (une tranche et son
  compte, une séance et sa valeur) se lisent sans leur en-tête en vue. Ils
  prennent la largeur de leurs colonnes, 24 rem au moins, et non celle de la
  colonne de lecture : deux colonnes étirées sur 800 px écartaient chaque
  compte de sa tranche.
- **La première colonne (le ticker) est collante à l'horizontale** : quand le
  cadre défile, elle reste en place et nomme la ligne.
- **Un cadre qui défile se prend au clavier** (chantier 7E, §13). Tant que le
  tableau déborde, le cadre est une région nommée par la légende
  (`role="region"`, `aria-labelledby`) et un arrêt de tabulation : les
  flèches le font défiler, dans tous les navigateurs. Un tableau qui tient
  dans sa colonne n'en a pas besoin, et la région y doublerait l'annonce de
  la légende. Un élément qui reçoit le focus dans le cadre y est amené en
  entier, à droite de la colonne collante, dont la largeur est mesurée :
  Chrome ne fait pas défiler un cadre vers un élément déjà en partie visible
  (à 390 px, l'en-tête « Nom » restait visible sur 11 px de ses 43).
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
- **Sous chaque graphique, ses valeurs en tableau, repliées** (chantier 7E,
  décisions du 2026-10-08). Un `<details>` natif, fermé, dernier élément de
  la figure : Entrée et Espace l'ouvrent, et la recherche de la page ouvre un
  repli qui contient le texte cherché. Son libellé visible est le même
  partout, « Les valeurs du graphique, en tableau » ; le titre du graphique
  le suit en texte masqué, pour qu'un lecteur d'écran sache lequel il ouvre,
  le nom accessible commençant par le texte visible (WCAG 2.5.3). Dedans, un
  `<DataTable>` (`<caption>`, `<th scope>`) : **les mêmes valeurs que le
  dessin**, lues dans la réponse de l'API et écrites par `format.ts`, toutes
  et dans l'ordre publié, **sans calcul ni sélection**. Les classes vides de
  l'histogramme restent, et la courbe garde ses quelque 500 jours. Ce que le
  dessin porte en plus de ses valeurs y est écrit avec ses valeurs publiées :
  les traits et la zone ombrée de l'histogramme, sous son tableau, choisis
  par le même filtre que le dessin ; le pic et le creux de la courbe, dans
  une colonne « Repère », posés par égalité avec les dates publiées. Un
  graphique dont le tableau suit déjà la figure, les parts dans les
  variations, n'en reçoit pas de second : son tracé le désigne
  (`aria-describedby` vers la légende de ce tableau).
- Les infobulles ne sont qu'une commodité de souris : tout ce qu'elles disent
  (le compte d'une tranche, la valeur d'un jour, la corrélation d'une paire)
  est dans le tableau.
- La dernière paire des conditions, sous le titre, mène à la méthode du
  graphique (§9.1, règle 5) : « Méthodologie  Le graphique des variations ».

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
produit assumé, écrit dans le README (« What it refuses to do »).

**11.2 — La couverture d'un scénario a le même poids visuel que la perte.**
Un scénario qui projette −44,0 % en ne couvrant que 73 % du portefeuille n'est
pas le même énoncé qu'un scénario couvrant 100 %. Les deux chiffres sont dans
le même bloc, à la même taille de police. La perte n'a jamais le droit d'être
plus grosse que sa couverture.

```
┌──────────────────────────────────────────────────────────────────┐
│ Crise financière 2008   2007-10-09 → 2009-03-09                  │
│                                                                  │
│   Au point bas du marché   Pire moment traversé  Couverture      │
│          −44,0 %                 −47,7 %           100 %         │  ← même taille
│                                                  6 lignes sur 6  │
└──────────────────────────────────────────────────────────────────┘

  et, quand la couverture est partielle :

┌──────────────────────────────────────────────────────────────────┐
│   Au point bas du marché   Pire moment traversé  Couverture      │
│          −44,0 %                 −47,7 %            73 %         │
│                                                ● 4 lignes sur 6  │
│                                                                  │
│ ● 2 lignes sur 6 sans historique sur toute la période ;          │
│   la perte porte sur les 4 autres, renormalisées.                │
└──────────────────────────────────────────────────────────────────┘
```

La couverture porte le point `--caveat` **dès qu'elle est inférieure à 100 %**,
et pas seulement sous le seuil de 80 % : le seuil déclenche l'observation du
moteur de règles, l'affichage signale le fait.

**Trois chiffres, pas un.** `ScenarioResult` porte `end_to_end_return` (ce que
vaudrait le portefeuille au point bas du marché, où s'arrête chaque épisode
du catalogue) **et** `max_drawdown` (le pire moment traversé en chemin, qui
peut être nettement plus profond). La docstring du backend dit explicitement
qu'il ne faut pas les confondre : l'interface affiche donc les deux, côte à
côte, à la même taille — plus la couverture. Un scénario réduit à un seul
chiffre laisse croire que le creux s'est arrêté là où l'épisode s'est terminé.
Le premier libellé dit « Au point bas du marché », pas « À la sortie » : pour
un débutant, « à la sortie » veut dire « une fois la crise finie ».

**La phrase de lecture ne donne de montant qu'au premier chiffre.** Le pire
moment traversé se mesure depuis le plus haut atteint pendant l'épisode,
souvent au-dessus du point de départ. En 2008, 47,7 % de la valeur
d'aujourd'hui ne correspondrait à aucune perte réelle. La phrase le dit donc
« 47,7 % sous son plus haut, atteint le 26 décembre 2007 », sans montant. Sous
le seuil de couverture de 80 %, elle ne cite aucune perte : « Seules 4 lignes
sur 6 existaient alors (73 % de la valeur) : trop peu pour dire ce qu'aurait
perdu l'ensemble. » Le moteur de règles ne donne pas non plus de chiffre
principal sous ce seuil.

**11.3 — La provenance est visible sans clic.** Détaillé en §9.1.

**11.4 — Une contribution à la variance est une amplitude, pas un verdict.**
Elle dit de combien une ligne fait bouger le portefeuille, **jamais dans quel
sens**. Sur le portefeuille de référence, XOM porte 12,9 % de la variance pour
15,3 % du capital — et c'est cette même variance qui a produit **+59,7 %**
pendant le resserrement de 2022, pendant que le portefeuille perdait 9,1 %.
Afficher une contribution à la variance seule, comme un danger, est donc une
erreur de lecture que l'interface a le devoir d'empêcher : toute vue de
concentration montre la contribution **et** le comportement réalisé en
scénario, dans le même bloc. Le backend le fait déjà — le moteur de règles
construit un « parcours » par ticker à travers les scénarios et écrit, pour
XOM, qu'il « a joué dans les deux sens : il a coûté 7,3 points (Krach COVID),
mais rapporté 9,1 points (Resserrement monétaire 2022) ».

**11.5 — La VaR normale et la VaR Student s'affichent en couple.**
Jamais l'une sans l'autre. L'écart entre les deux *est* l'information : il
chiffre le coût de l'hypothèse de normalité. Afficher les deux côte à côte, avec
ν (`VarResult.nu`) dans la provenance de la Student.

**11.6 — Un régime calme et un régime de crise ne se moyennent pas.**
Beta et R² s'affichent par régime, appariés, jamais fusionnés en une valeur
unique. Un beta de 0,57 en calme et de 1,07 en crise n'a pas de moyenne qui
veuille dire quelque chose. La phrase de lecture donne les deux. D'un beta de
crise estimé sur trop peu de jours, comme les 23 du krach COVID, elle ne tire
aucune conclusion.

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
  Visible sur **tous** les éléments interactifs. Jamais `outline: none`. Son
  contraste est de 4,62:1 au moins sur les trois surfaces des deux thèmes,
  colonne collante d'un tableau comprise (`styles/anneau.test.ts`).
- Ordre de tabulation suivant l'ordre de lecture. Un lien « aller au contenu »
  en début de document, sur toutes les pages : sur l'écran d'acceptation, il
  mène au titre du texte, après le bouton de langue (chantier 7E).
- **Le focus n'est jamais caché sous le bandeau collant** (chantier 7E, WCAG
  2.4.11). La page réserve sa hauteur à tout ce qu'elle fait défiler, ancres
  comme tabulation (`scroll-padding` de `html` sur `--hauteur-bandeau`,
  nulle sous 900 px, où le bandeau défile avec la page, §8.1). Mesuré à
  390 px avant ce chantier : en Maj+Tab, quatre liens disparaissaient
  entièrement sous un bandeau de 274 px.
- **Une ancre donne le focus au titre qu'elle vise** : une partie de la
  méthodologie, et, depuis le chantier 7E, une section de l'analyse, dont le
  titre porte `tabIndex={-1}`. Le focus restait sur le corps de la page, sans
  anneau, et le Tab suivant repartait du haut. L'anneau d'un titre suit son
  texte (`fit-content`), titres de page compris.
- **Une ancre vers une page qui charge encore est attendue** (2026-10-12,
  chantier 9.4). Une section de l'analyse n'existe qu'une fois l'analyse
  lue : `/portefeuilles/1#en-crise`, ouverte d'une autre page ou retrouvée
  par un retour arrière, s'ouvrait en haut, l'ancre ignorée. La page vise
  maintenant le titre quand elle est prête, comme la méthodologie : sur une
  arrivée directe, le titre sous le bandeau et le focus laissé où il est ;
  sur un lien suivi ou un retour arrière, le focus au titre. En attendant,
  le focus n'est posé nulle part : il ne se déplace qu'une fois. Une page
  prête sans ce titre s'ouvre comme sans ancre, et le retour depuis la
  méthode garde la priorité.
- **Le focus ne se perd pas après un geste** (chantier 7E). « Retirer » le
  porte au ticker de la rangée qui prend la place ; « Rester sur la page », à
  ce qui l'avait (le lien suivi, le bouton de langue) ; un refus de champ, au
  champ, que son refus décrit. Un changement de langue vers un écran
  d'acceptation le porte au titre de cet écran ; vers une langue déjà
  acceptée, il reste au bouton, l'analyse affichée restant en place, occupée
  (`aria-busy`), pendant qu'elle se relit. Accepter ouvre la page en haut, son
  titre focalisé. Les règles qui n'ont pas besoin d'un document sont des
  fonctions pures (`lib/focus.ts`).
- **Le retour depuis la méthode** (chantier 7E). Suivre le lien d'une mesure
  vers sa méthode (§9.1, règle 5) note, dans l'entrée d'historique quittée,
  la clé de ce lien et la position de la page. Au retour arrière, une fois
  la page relue, le lien de même clé reprend le focus, amené sous le bandeau
  avec l'écart d'une ancre (`scroll-margin` de 16 px) et gardé là pendant
  que la page s'installe ; la position notée ne sert que si la clé n'est
  plus sur la page.
  Une langue ou un thème changés sur la méthodologie n'y font rien : la clé
  ne dépend que du bloc et de l'ancre.
- **Le titre caché de l'analyse** (« Analyse de « Démo » ») reçoit le focus
  après une navigation, pour qu'un lecteur d'écran dise le nom de la page.
  Il n'est pas un arrêt de tabulation, et son anneau ne se voit pas : le Tab
  suivant en montre un (décision du 2026-10-08).
- Aucun défilement adouci : ceux que le code demande (ancres, focus, retour
  arrière) sont instantanés.
- Tableaux : `<caption>`, `<th scope>`. Graphiques : `role="img"` et un
  `aria-label` qui énonce la conclusion, pas la forme (« VaR 95 % à 1,38 %,
  contre 1,95 % sous loi de Student »), et leurs valeurs en tableau replié
  (§9.4). Une exception, la carte de corrélation : son étiquette dit ce
  qu'elle montre (« Corrélations deux à deux de 6 lignes, valeur écrite dans
  chaque cellule »). La paire la plus liée, sa conclusion naturelle, n'est
  publiée par le moteur que dans une des trois branches de sa règle
  (`apparent_diversification`) : `paire` et `correlation_max` quand aucune
  paire n'est forte ; une observation par paire forte, avec `correlation` et
  la paire dans `subject` ; `correlation_max` nul quand la corrélation n'est
  pas estimable. Une étiquette tirée de là ne tiendrait que pour certains
  portefeuilles (décision du 2026-10-08).
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

  Sur le site, les pages du portefeuille saisi ont en plus les états du
  serveur de calcul : réveil, calcul, refus, limite, sans réponse (§20.7).

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

- **Deux langues** (chantier 7D) : le français, langue par défaut, et
  l'anglais américain, ponctuation de Chicago. Dans les deux, casse phrase,
  titres compris, et verbes actifs. Un bouton dit ce qu'il fait : « Importer
  le portefeuille », « Import the portfolio », pas « Valider ». Les règles
  qui suivent sont écrites pour le français ; l'anglais les suit, transposées
  (dernier point avant l'acceptation).
- Un même geste garde son nom du bouton au message de confirmation.
- Nommer les choses comme l'utilisateur les comprend. Sous « VaR 95 % » :
  « Ces deux dernières années, environ un jour de bourse sur vingt, soit à peu
  près une fois par mois, votre portefeuille aurait perdu 1,06 % ou plus. » On
  ne remplace pas le terme technique, on le traduit à côté. Le particulier
  apprend le vocabulaire, ce qui est une valeur du produit. Chaque terme est
  expliqué une fois, là où il apparaît pour la première fois dans la page :
  « La VaR, ou valeur à risque, répond à une question… ».
- **« Jour de bourse » dans les phrases**, « séance » dans les détails du
  calcul, les libellés techniques et les unités des graphiques.
- **Vouvoiement, et conditionnel pour le passé rejoué.** Les mesures rejouent
  le passé sur la composition d'aujourd'hui, que le portefeuille n'avait pas
  forcément : « aurait perdu », jamais « a perdu ». Un montant « représente »
  une part de la valeur d'aujourd'hui ; il ne dit jamais ce qui a été perdu
  en dollars, puisque le portefeuille ne valait pas cette somme le jour de la
  perte.
- **Traduire sans trahir.** Une VaR est un **seuil dépassé**, pas une perte
  attendue : un jour de bourse sur vingt, la perte *atteint ou dépasse* ce
  niveau, d'où « 1,06 % ou plus ». Ce qu'elle vaut en moyenne ces jours-là est
  la CVaR (« la perte moyenne des pires jours »). Écrire « perte attendue »
  sous une VaR ferait lire le seuil comme cette moyenne, et sous-estimer la
  queue. La formulation de référence est dans `src/lib/phrases.fr.ts`, et
  `phrases.en.ts` en anglais ; la convention de signe est fixée dans
  `risk_engine/var.py`.
- **Une fréquence vient d'une table, jamais d'une division.** « Un jour de
  bourse sur vingt » est associé à 0,95, il n'en est pas dérivé : un niveau
  absent de la table garde son nom technique (« au niveau de confiance
  85 % »).
- Les réserves méthodologiques sont écrites platement, sans dramatiser ni
  minimiser : « Moyenne de 6 jours de bourse seulement, sur 504 : chacun pèse
  pour 17 % du chiffre. » Le backend produit déjà ces phrases — les afficher
  telles quelles. Elles disent « jours de bourse » et « l'outil », comme les
  phrases à côté desquelles elles s'affichent.
- **En anglais, les mêmes règles, transposées** (chantier 7D ;
  `anglais-proposition.md` §c.3, document de cadrage hors dépôt, et les
  décisions de la passation, §10.2 et §11.2).
  - « You » pour le vouvoiement, aucune contraction (« does not »), et pas de
    « we » pour l'outil : « the tool », ou le passif.
  - **« Would have » pour le passé rejoué.** Le prétérit ou le présent
    seulement dans une phrase qui porte elle-même son cadre (« Over the past
    two years, … », « In the replayed crises, … »), ou qui suit une phrase
    de la même observation qui le pose (« Over the same period, … »).
  - Une VaR se lit « a loss of at least 1.06% » ou « 1.06% or more », jamais
    « expected loss » ; un montant « represents about 890 USD » « on its
    value today », jamais « lost 890 USD ».
  - **« Trading day » dans les phrases**, « session » dans les détails du
    calcul, les libellés techniques et les unités.
  - Rien de prescriptif (ni « should », « must », « consider », « reduce »,
    « avoid », ni « diversify » comme verbe), aucune note globale (« overall
    rating » pour « note globale », le mot « score » interdit), aucune
    phrase qui affirme ce que le moteur ne mesure pas, aucun tiret
    cadratin. Une phrase anglaise ne dit ni plus ni plus fort que la
    française, et cite les mêmes nombres.
  - **Les termes sont ceux du glossaire** (`anglais-proposition.md` §c.2,
    avec « Small-sample estimate » pour « Estimation mince ») : « holding »
    pour une ligne du portefeuille, « security » pour un titre,
    « fluctuations » pour les variations, « Calculation details » pour
    « Détails du calcul », « What carries the risk », « Worst point along
    the way ». Un terme qui n'y est pas se signale au rapport du lot qui
    l'emploie.
- **Acceptation à la première utilisation — décision de la phase 6.** Le
  backend fournit un écran complet (`disclaimer.title`, `sections`,
  `confirmation`) : c'est une **page entière** avant le premier accès, avec la
  phrase `confirmation` comme case à cocher, pas une modale posée sur le
  dashboard. Une modale se clique sans lire ; une page qu'on traverse une fois,
  délibérément, non. Où mémoriser l'acceptation (navigateur ou API) est une
  décision de la 7B. Elle se traverse **une fois par langue** (chantier 7D) :
  le texte anglais est un autre texte. Son bouton dit la page où il mène,
  celle de l'adresse d'arrivée (« Ouvrir la méthodologie », « Open the
  methodology »), et la phrase sous lui le même geste. Dans la
  démonstration, cet écran n'est posé que devant les deux pages du
  portefeuille saisi (chantier 9.6, §20.3) : il a été décidé pour quelqu'un
  qui analyse son propre portefeuille, et les portefeuilles d'exemple ne le
  sont pas (décision du 2026-10-11, §19). Son texte y reste lisible, à un
  clic au plus de chaque page. L'application locale garde son acceptation
  telle quelle.
- Ensuite, un **rappel court et permanent** en pied de la section 6, en texte
  courant, sans case ni bouton.

---

## 16. Chiffres de référence — à utiliser dans les maquettes

**Chiffres rafraîchis le 2026-10-05, valorisés au 2026-09-25.** Ils ont été
**recalculés indépendamment**, sans le moteur, sur une copie de la base locale
(`data/mx_risk.sqlite`, dernière clôture 2026-09-25), et concordent avec la
réponse de l'API. Portefeuille de démonstration : AAPL 40, MSFT 25, JPM 60,
JNJ 50, XOM 80, KO 120 ; fenêtre de 504 séances, du 2024-09-23 au 2026-09-25.
Les exemples chiffrés de ce document les reprennent.

Les tests ne les lisent pas. Ils tournent sur une copie de la base figée au
2026-09-09 (`tests/conftest.py`), dont les chiffres diffèrent : les constantes
`DEMO_POIDS` et `DEMO_PARTS` de `tests/test_rules.py` gardent ceux de cette
date (JPM y pèse 25,6 % du capital et 35,4 % de la variance).

**Ne pas inventer de chiffres dans les maquettes.** Une capture d'écran qui
circule avec des nombres faux est une erreur difficile à rattraper, et le
projet a déjà corrigé plusieurs fois des chiffres plausibles mais faux.

| Ligne | Poids en capital | Part de variance | Écart |
|---|---:|---:|---:|
| JPM | 24,5 % | 32,7 % | +8,2 pts |
| AAPL | 16,2 % | 24,5 % | +8,3 pts |
| JNJ | 16,1 % | 7,9 % | −8,2 pts |
| MSFT | 15,3 % | 16,7 % | +1,3 pts |
| XOM | 15,3 % | 12,9 % | −2,3 pts |
| KO | 12,5 % | 5,3 % | −7,3 pts |

L'écart est arrondi depuis les valeurs exactes, comme sur la page : il peut
différer d'un dixième de la différence des deux colonnes arrondies (MSFT,
XOM, KO).

- Valeur du portefeuille : 84 076,05 USD · 6 lignes · lignes effectives 5,72
  en capital, 4,53 en risque
- Volatilité annualisée : 13,3 % (quotidienne 0,84 %) ; SPY sur les mêmes
  séances : 16,5 %
- VaR historique, 1 séance : 1,06 % à 95 %, 1,69 % à 99 %
- VaR paramétrique normale, 1 séance : 1,38 % à 95 %, 1,95 % à 99 %
- CVaR : 1,69 % à 95 % (moyenne de 26 séances), 3,00 % à 99 % (6 séances)
- Pire séance : −5,87 %, le 2025-04-04
- Perte maximale pic-creux : −14,8 %, du pic du 2025-02-19 au creux du
  2025-04-08 ; pic retrouvé le 2025-06-23, 51 séances après le creux
- Montants, sur 84 076,05 USD et arrondis à la dizaine comme dans les
  phrases : VaR historique 890 et 1 420 USD ; VaR normale 1 160 et
  1 640 USD ; CVaR 1 420 et 2 520 USD ; pire séance 4 940 USD ; creux
  12 480 USD

La VaR de Student (1,27 % à 95 %, 2,21 % à 99 %) est lue dans la réponse de
l'API : son ajustement n'a pas été refait hors du moteur.

Scénarios, à parts figées depuis les poids actuels, couverture 100 % :

| Scénario | Période | Au point bas du marché | Pire moment traversé | Ligne remarquable |
|---|---|---:|---:|---|
| Crise financière 2008 | 2007-10-09 → 2009-03-09 | **−44,0 %** (36 960 USD) | −47,7 % | JPM −64,9 % |
| Krach COVID | 2020-02-19 → 2020-03-23 | **−35,5 %** (29 860 USD) | −35,5 % | XOM −47,9 % |
| Resserrement 2022 | 2022-01-03 → 2022-10-12 | **−9,1 %** (7 640 USD) | −13,3 % | XOM **+59,7 %** |

Le pire moment traversé se mesure depuis le plus haut atteint pendant
l'épisode : le 2007-12-26 en 2008, le 2022-03-30 en 2022. C'est pourquoi il
n'a pas de montant (§11.2).

Le resserrement 2022 est aussi le meilleur exemple de §11.2 : le portefeuille
finit l'épisode à −9,1 %, mais il a été 13,3 % sous son plus haut en chemin.
N'afficher que le premier chiffre ferait disparaître la pire baisse
réellement traversée.

Régimes (beta calme 0,57 et R² 0,50 sur 504 séances, du 2024-09-23 au
2026-09-25) :

| Scénario | Beta de crise | R² de crise | Séances | Attendu d'après le beta calme | Rejoué |
|---|---:|---:|---:|---:|---:|
| Crise financière 2008 | 0,95 | 0,86 | 355 | −36,7 % | −44,0 % |
| Krach COVID | 1,07 | 0,98 | 23 | −20,9 % | −35,5 % |
| Resserrement 2022 | 0,74 | 0,80 | 195 | −14,8 % | −9,1 % |

Le beta du krach COVID repose sur 23 séances, moins que les 60 du seuil
choisi : la page le donne, mais n'en conclut rien. L'attendu vaut
(1 + R_SPY)^beta − 1 ; il ne se lit pas comme 0,57 × la perte de SPY.

La dernière ligne est l'exemple à utiliser partout où il faut illustrer §11.4 :
le portefeuille perd 9,1 % pendant que sa ligne énergie gagne 59,7 %.

---

## 17. Vérification avant de déclarer la phase 7 terminée

Cochée le 2026-10-08, à la clôture du chantier 7E, en français et en
anglais. Une preuve par point ; le détail est dans la passation (§12), les
captures et les outils dans `docs/` (hors dépôt).

- [x] Capture d'écran en niveaux de gris : aucune information perdue.
      *Preuve* : l'analyse entière en achromatopsie émulée par Chrome, sombre
      et clair, deux langues (`captures/7E/gris-*`). Traits et zone de
      l'histogramme écrits, barre et trait distingués par la forme, apports
      signés, valeur dans chaque cellule, point et mot « choisi », liens
      soulignés.
- [x] Aucune couleur de graphique hors des tokens de §5 ; toute couleur ajoutée
      a passé les contrôles de §5.4 (bande, chroma, contraste, daltonisme).
      *Preuve* : `couleurs.test.ts` (chaque couleur lue est un token déclaré),
      `correlation.test.ts` (l'échelle sur les tokens de §5.4). La 7E n'ajoute
      aucune couleur.
- [x] Recherche dans le code : aucun `#` hexadécimal hors de `tokens.css`.
      *Preuve* : `rg` sur `src` et `index.html`, tests exclus : 0. Le dernier,
      dans un commentaire de `correlation.ts`, nomme désormais ses tokens.
- [x] Recherche dans le code : aucun `px` de taille de police hors de
      `typography.css`.
      *Preuve* : `rg` sur `font-size` et `fontSize` : 0.
- [x] Chaque chiffre affiché a sa fenêtre et sa date visibles sans clic.
      *Preuve* : `docs/outils/etats-17.mjs` : les 29 figures et blocs de
      l'analyse portent une date hors de tout repli, aucune provenance n'est
      repliée (trois largeurs, deux langues) ; `Measure.test.ts`. Les
      tableaux repliés (§9.4) ne portent que des valeurs déjà dessinées.
- [x] Aucun score global nulle part.
      *Preuve* : `test_rules.py` (aucun champ, aucun texte), les gardes de
      `libelles.test.ts`, `phrases.en.test.ts` et `test_methodologie.py` ; le
      texte rendu des 72 écrans capturés, où « note globale » et « overall
      rating » ne figurent que dans la phrase de la méthodologie qui dit
      pourquoi il n'y en a pas.
- [x] Un seuil `CHOSEN` est visuellement distinct d'un seuil dérivé.
      *Preuve* : `Observation.test.ts` (point et classe `choisi` pour un seuil
      choisi, et lui seul, sans lire le mot) ; la section 6 capturée, en
      niveaux de gris compris.
- [x] La heatmap de corrélation a le même domaine pour deux portefeuilles
      différents.
      *Preuve* : `correlation.test.ts`, « domaine fixe, indépendant des
      données » : deux matrices, la même échelle, [−1, +1].
- [x] Couverture de scénario et perte projetée ont la même taille de police.
      *Preuve* : `SectionCrise.test.ts` (la même classe) ; mesuré dans
      Chrome, les trois chiffres des trois crises : IBM Plex Sans, 39 px,
      600, trois largeurs, deux langues.
- [x] Navigation complète au clavier, focus visible partout.
      *Preuve* : `docs/outils/clavier.mjs` à 1280, 390 et 320 px, deux
      langues : chaque arrêt a son anneau, aucun n'est caché ni rogné, aucun
      piège, chaque arrêt de l'analyse photographié à 1280 ; l'anneau à
      4,62:1 au moins (`anneau.test.ts`, et mesuré dans la page, colonne
      collante comprise).
- [x] Les quatre états (vide, insuffisant, en cours, erreur) existent.
      *Preuve* : `etats-17.mjs` les capture dans les deux langues, aux trois
      variantes, le 409 servi depuis la réponse de référence ; ASBH pour la
      mesure insuffisante.
- [x] Les deux thèmes testés sur la page d'analyse complète, pas seulement sur
      un composant.
      *Preuve* : l'analyse de démonstration et celle d'ASBH, section par
      section, en sombre et en clair à 1280, deux langues (`captures/7E/fr`,
      `en`).
- [x] Rendu à 390 px de large sans défilement horizontal de page.
      *Preuve* : aucune des 138 captures ne déborde (`journal.json`),
      tableaux dépliés compris (`tableaux-deplies.mjs`) ; à 320 × 225, six
      écrans sans défilement horizontal (`etats-17.mjs`).

---

## 18. Le mode démonstration

**Section du 2026-10-10, chantier 9.2, amendée le 2026-10-14 (chantier
9.6).** Le site public est une démonstration : le même client, servi en
fichiers statiques (`npm run build:demo`). Ses trois portefeuilles
d'exemple, « Démo », « Tech » et « Défensif » (« Demo », « Tech » et
« Defensive » en anglais), valorisés au 2026-09-09, sont lus dans des
réponses de l'API enregistrées par `python -m tools.export_demo`, au lieu
d'appeler l'API. Le portefeuille que le visiteur saisit est envoyé à un
serveur public, qui l'analyse sans rien garder (§20). Tout ce que ce
document demande d'une page vaut pour elle : les deux langues, les deux
thèmes, la méthodologie. Cette section, la §19 et la §20 disent seulement
ce qui diffère.

### 18.1 Rien n'écrit en base, rien n'est grisé

Le client ne lit le mode (`DEMO`, dans `api/client.ts`) que pour quatre
choses : masquer ce qui écrit en base, afficher la mention, rendre la page
d'accueil à l'adresse `/`, et rendre les deux pages du portefeuille saisi,
les seules devant lesquelles l'écran d'acceptation est posé (§19, §20). Ce
qui est masqué n'est pas rendu, et sort du build :

- **Portefeuilles** : le formulaire « Nouveau portefeuille », la colonne
  « Actions » entière (le lien « Positions » et le bouton « Supprimer ») et
  la confirmation de suppression. Restent la phrase d'introduction, la
  légende et les cinq autres colonnes, et le bloc « Votre portefeuille »
  s'y ajoute (§20.8).
- **Navigation**, rail et liste d'ancres : l'entrée « Positions et import »,
  sauf quand le portefeuille en vue est le portefeuille saisi (§19.5).
- **Analyse** d'un portefeuille d'exemple, états vide et insuffisant : le
  lien vers les positions et le format du fichier.
- **Les écritures en base** : créer, supprimer, saisir ou importer les
  positions d'un portefeuille de la base. Leurs écrans ne sont pas rendus,
  et leurs requêtes sortent du build (18.2). La saisie du site envoie au
  serveur public, et garde dans le navigateur (§20.6).

Aucune entrée grisée, aucun « bientôt » : une page ne propose que ce qui
existe.

### 18.2 L'adresse des positions, et un numéro inconnu

`/portefeuilles/<id>/positions` n'est l'adresse d'aucune page de la
démonstration. Elle rend l'état existant « Page introuvable » : « Aucune
page à cette adresse », l'adresse citée, le lien « Voir les portefeuilles ».
Les portefeuilles d'exemple ne se modifient pas. Les deux adresses du
portefeuille saisi, `/portefeuilles/saisi` et
`/portefeuilles/saisi/positions`, sont des pages du site (§20.2) ; dans
l'application, elles rendent « Page introuvable ».

Un numéro de portefeuille inconnu rend « Portefeuille introuvable », avec le
texte de l'application : c'est la liste qui dit ce qui existe, avant tout
autre appel.

### 18.3 La mention

En tête du contenu de chaque page (`Cadre`), sous le bandeau, avant le
titre :

- « Démonstration : 3 portefeuilles d'exemple, ou le vôtre, valorisés au
  9 septembre 2026. »
- « Demonstration: 3 sample portfolios, or your own, valued as of
  September 9, 2026. »

Depuis le chantier 9.6, elle dit, sur chaque page, la date de tous les
cours, ceux de l'analyse d'un portefeuille saisi compris. Jusque-là, elle
disait « 3 portefeuilles fixes », « 3 fixed portfolios ».

Du texte courant (`--text-sm`, `--text-2`), qui défile avec la page. Avec
son lien, mesurée le 2026-10-14 : trois lignes à 390 et à 320 px, deux à
1 350 px, dans les deux langues (§20.11). Pas dans le bandeau, qui y
gagnerait une ligne à toutes les largeurs (§8.1). Elle se termine par un
lien vers l'avertissement (§19). Elle ne promet aucune fonction à venir.

Le nombre et la date passent par `format.ts`. Leurs valeurs sont écrites
dans `contenu/demo.ts`, et tenues égales à la date du gel des tests et au
nombre de portefeuilles de `demo/compositions.json`.

### 18.4 La fraîcheur des positions

Les portefeuilles de la démonstration sont écrits par l'export, pas par
l'application : `updated_at` est nul, et le bandeau dit la phrase de §8.1,
« Positions jamais modifiées depuis l'application », « Positions never
changed in the app ». La colonne de la liste dit « jamais », « never ».
Aucune date n'est inventée, et aucune ne suit la date de valorisation.

**Mesure du 2026-10-10**, dans Chrome, sur le build de démonstration. Un
constat de ce jour, pas une valeur à tenir. Le bandeau de l'analyse a la
même hauteur avec les trois noms, dans les deux langues et les deux thèmes :
274,27, 175,98 et 102,30 px à 390, 900 et 1280 px, comme en §8.1. À
320 × 225, il mesure 329,34 px en français sombre et 332,25 px en clair,
soit 20,29 px de plus qu'avec une date : la phrase d'une date absente y
prend une ligne de plus. En anglais, 311,95 px, comme avec une date. Aucun
débordement à ces quatre largeurs.

### 18.5 Les quatre états (§13)

- *vide* et *insuffisant* : les trois portefeuilles d'exemple ne les
  atteignent pas, l'export exige une analyse de chacun. Une liste vide n'est
  pas un état de la démonstration, qui n'a rien pour créer un portefeuille
  en base : elle se dit comme un fichier illisible. Le portefeuille saisi a
  son état vide (§20.7).
- *en cours* : les squelettes, inchangés.
- *erreur* : la démonstration a ses propres textes. Ses fichiers n'ont pas
  de serveur à démarrer : « L'API ne répond pas. La démarrer : python -m
  backend.api » n'y est jamais affiché, ni « L'API a répondu un corps
  vide ». Le serveur public a ses propres états et ses propres textes
  (§20.7).
  - La requête n'aboutit pas : « Les données de la démonstration n'ont pas
    pu être chargées. Vérifier la connexion, puis recharger la page. »,
    « The demonstration data could not be loaded. Check the connection, then
    reload the page. »
  - Le fichier manque ou n'est pas du JSON : « Le fichier
    `fr/portfolios.json` de la démonstration manque ou n'est pas lisible.
    Recharger la page. », « The demonstration file `en/portfolios.json` is
    missing or cannot be read. Reload the page. » Le nom du fichier est
    rendu en code, comme un séparateur cité par l'import.
  - Le titre de la page quand le démarrage échoue : « Démonstration
    indisponible », « Demonstration unavailable ». Depuis le 2026-10-11, le
    démarrage de la démonstration n'attend aucun fichier (§19) : ce titre
    ne s'y affiche plus.

  Un hébergeur statique rend sa page d'accueil, avec un 200, pour un fichier
  absent : le statut ne dit rien. Seul un corps qui se lit comme un document
  JSON non vide est une réponse.

### 18.6 Ce qui ne change pas

La méthodologie et ses renvois ; les six sections de l'analyse et le rappel
en pied de la section 6 ; la légende « Portefeuilles en base » et le texte
d'un numéro inconnu. L'écran d'acceptation et l'adresse `/` ont changé le
2026-10-11 (§19), l'écran d'acceptation de nouveau le 2026-10-14 (§20.3).

---

## 19. La page d'accueil

**Section du 2026-10-11, chantier 9.3.** Une spécification : à cette date,
rien n'en est codé, et la 9.4 la code. Dans la démonstration (§18),
l'adresse `/` rend une page qui présente le projet à quelqu'un qui ne le
connaît pas, et l'écran d'acceptation n'est plus posé. L'application locale
ne change pas : `/` y reste une redirection (§8.2), l'acceptation une page
à traverser (§15), et son build ne reçoit ni cette page, ni ses images, ni
ses métadonnées. Comme la §18, cette section dit seulement ce qui diffère.

Le mode n'est lu que pour les quatre choses de §18.1. Deux sont décrites
ici, chacune avec ce qu'elle entraîne : rendre la page d'accueil, donc le
chemin qui y mène (la marque cliquable et l'entrée « Présentation »,
19.5) ; ne pas poser l'écran d'acceptation devant les portefeuilles
d'exemple, donc ce qui garde son texte lisible (la page de
l'avertissement, son entrée et le lien de la mention, 19.6). Depuis le
2026-10-14, il est posé devant les pages du portefeuille saisi (§20.3).

### 19.1 La page et son ordre

Le lecteur est un recruteur, en finance ou en informatique. Il ne connaît
ni le produit ni la VaR, et lira deux minutes. La page est courte et mène à
la démonstration.

Elle s'appelle « Présentation », « Overview », dans la liste des pages
comme dans l'onglet (« Présentation (Portfolio Risk Engine) », §6.3) : le
nom dit ce qu'elle est. « Accueil » ne dirait que sa place, et dans
l'application locale `/` reste une redirection.

Sept parties, dans cet ordre, qui est l'argument (§3.2). Les intertitres
sont ceux de la page ; ils n'ont pas de numéro (§12).

1. **Ce que fait l'outil.** Le titre, « Le risque d'un portefeuille,
   chaque chiffre avec ses conditions », et un chapeau : ce que l'outil
   mesure, les questions auxquelles l'analyse répond, pour quel lecteur,
   et que tout y décrit le passé.
2. **« La démonstration ».** Ce qu'est le site, puis le tableau des
   portefeuilles, chacun un lien vers son analyse. En second, parce que
   c'est là que la page mène : sur un téléphone, l'entrée se voit sans
   défiler longtemps. Depuis le chantier 9.6, le texte dit que le site
   analyse aussi le portefeuille du visiteur, sur une base de cours
   arrêtée à la date du tableau, et un lien suit le tableau, « Saisir ou
   importer votre portefeuille », « Enter or import your portfolio » : un
   lien, pas un bouton d'appel (19.2).
3. **« Ce qui le distingue ».** Trois points, chacun une phrase d'attaque
   puis son paragraphe : « Un chiffre et ses conditions se lisent
   ensemble. », avec la première capture ; « Aucune note globale. » ; « Un
   chiffre qui ne veut plus rien dire n'est pas donné. »
   **La première capture suit le troisième point** (2026-10-12, accord
   donné d'avance le 2026-10-11), et non le premier. Sous le premier, elle
   commençait à 925 px du haut de la page en anglais et à 945 px en
   français, à 1350 × 940 : dans le premier écran en anglais, où aucune
   image ne figure (19.9, point 2). Sous le troisième, elle commence à
   1 239 px en anglais et à 1 259 px en français. Sa légende ne change pas.
4. **« Un résultat ».** Une phrase de l'analyse, avec ses conditions
   (19.3).
5. **« Comment il a été construit ».** La section « How it was built » du
   README, ni plus ni moins.
6. **« Ce que la démonstration ne montre pas ».** La saisie, avec la
   seconde capture, et un lien vers l'installation, dans le README.
   Depuis le chantier 9.6, le site a sa saisie : la partie dit ce que
   l'application installée fait de plus (ses cours mis à jour, un titre
   ajouté à sa base, plusieurs portefeuilles gardés) et ce que le site
   limite (des cours arrêtés à une date, une liste de titres fermée, un
   portefeuille gardé dans le navigateur seulement). La capture de la
   saisie, sa légende et son texte alternatif sont retirés (décision du
   2026-10-13) ; le titre et le lien restent.
7. **« Liens »**, puis l'auteur.

**La page n'affirme que ce que le moteur fait.** Le troisième point
distingue le refus du signalement, comme le moteur (§9.1, règles 3 et 4) :
« Quand les jours de bourse sont trop peu nombreux pour qu'une estimation
veuille encore dire quelque chose, l'outil la refuse et dit pourquoi ;
quand ils sont seulement peu nombreux, il la donne, et la signale. Un seuil
choisi à la main est signalé comme tel. » Écrire que l'outil n'affiche pas
une estimation dès que les jours manquent serait faux : une estimation
mince est donnée, avec son point `--caveat`. Les règles de §15 valent pour
la page comme pour le reste : rien de prescriptif, aucune note globale,
rien que le moteur ne mesure pas. Elle dit « L'outil décrit : il ne dit
jamais quoi faire. », « The tool describes: it never says what to do. »,
sans nommer les gestes qu'il ne conseille pas : la garde prescriptive des
libellés anglais les refuserait, et elle ne change pas (décision du
2026-10-11).

**Les liens**, dans cet ordre : le code source, sur GitHub ; la
méthodologie du site ; METHODOLOGY.md ; ARCHITECTURE.md ; l'avertissement
(19.6). Un lien vers un document écrit en anglais le dit dans son texte.

**L'auteur.** Une ligne, « Projet personnel de Maxence Champlong, étudiant
à HEC Montréal », suivie de deux liens, GitHub et LinkedIn, sans point
médian entre eux (§12). Le lien GitHub mène au profil
(`github.com/lemaxoux`) ; le dépôt, lui, est dans la liste des liens.
L'adresse LinkedIn est donnée à la 9.4. Aucune adresse électronique, sur
aucune page. En anglais, l'école garde son nom, « HEC Montréal » (19.10).

Le texte français validé le 2026-10-11 est dans `landing-proposition.md`,
§4.2 (document de cadrage, hors dépôt). L'anglais s'écrit en 9.4 depuis ce
texte, avec le glossaire (§15) ; sa partie « How it was built » est celle
du README, mot pour mot. Il passe les gardes de `libelles.test.ts`, dont
la seule retouche est le nom de l'école (19.10) ; toute autre exception se
montre avant d'être posée.

### 19.2 Le registre

Une page de l'outil, pas une page de site marketing (§2). Elle tient §3,
§10 et §12 sans rien de nouveau :

- **Pas de hero.** Le titre est un titre de page, à la taille des autres
  (`--text-lg`). Pas de grand chiffre, pas de bouton d'appel : les entrées
  sont les liens du tableau.
- **Un rapport** (§3.2) : une colonne de lecture, sur la grille de la
  méthodologie et de la liste des portefeuilles. Aucune grille de tuiles ;
  le seul chiffre mis en avant est dans un bloc qui porte ses conditions
  (19.3).
- **Les interdits de §12** : ni ombre, ni dégradé, ni capitales, ni émoji,
  ni flèche accolée à un lien, ni étiquette au-dessus d'un titre, ni
  numérotation.
- **Aucun mouvement** (§10) : ni animation d'entrée, ni fondu d'image.
- **Aucune couleur nouvelle, aucun token nouveau.** Prose en Spectral, à
  la largeur de prose ; libellés et tableau en IBM Plex Sans.
- **Toute la prose à gauche, à toutes les largeurs**, chapeau compris.
  Seule une prose mesurée sous 2,5 est justifiée (§6.3) : celle-ci n'a pas
  été mesurée, et n'a pas de coupures posées au build.

### 19.3 Les chiffres

**Aucun nombre n'est écrit dans le texte de la page**, ni en chiffres ni
en lettres : elle dit « des crises passées », pas leur nombre, et « trop
peu nombreux », pas un seuil. Une garde Vitest lit les libellés de la
page, dans les deux langues, et refuse un chiffre ou un nombre écrit en
lettres ; un texte fautif prouve qu'elle mord. Tout nombre affiché est lu
dans un fichier exporté ou dans `contenu/demo.ts`, et écrit par
`format.ts` :

- la mention : le nombre de portefeuilles et la date (§18.3) ;
- le tableau des portefeuilles : pour chacun, son nom, qui est le lien,
  ses titres et sa valeur, lus dans `<langue>/portfolios.json` ; la
  légende du tableau donne la date de valorisation ;
- le résultat.

**Le résultat est une phrase de l'analyse, pas un texte de la page.**
Celle de la section 5 qui met côte à côte, pour la première crise rejouée,
ce que le comportement de temps ordinaire laissait attendre et ce que le
rejeu donne. Elle est composée par la même fonction
(`phrases.lecturePrediction`) depuis les mêmes champs publiés
(`predicted_return`, `portfolio_return`, `prediction_gap`,
`calm_period_label`), lus dans l'analyse exportée du premier portefeuille,
`<langue>/portfolios/1/analysis.json`. Le client n'écrit ni ne recopie
aucun de ses nombres : la phrase suit l'export. Le premier portefeuille est
celui des résultats du README, et `tests/test_export_demo.py` le tient.

Le bloc a un titre (la crise, rejouée sur le portefeuille), la phrase, puis
ses conditions dans une grille libellé et valeur, comme sous une mesure
(§9.1), lues dans le même fichier : le portefeuille, la date de
valorisation, la fenêtre, la période, la crise et ses dates. Son dernier
élément est un lien vers la section 5 de l'analyse, « Voir cette crise
dans l'analyse », où se lisent la provenance complète et le lien vers la
méthode. C'est le produit qui parle : la page montre un chiffre et ses
conditions comme un seul objet (§1), au lieu de le dire. Le coût est une
requête de plus, après le premier affichage (19.9).

**La couverture, sous la phrase** (décision du 2026-10-11). §11.2 veut la
couverture d'une crise dans le bloc qui en donne la perte, au même poids ;
dans l'analyse, cette phrase se lit dans le bloc de sa crise, sous ses
trois chiffres. Sur la page, une ligne de couverture suit donc la phrase, à
la taille de la phrase : pas dans la grille des conditions, qui est plus
petite. Elle a le libellé et l'écriture de la couverture de la section 5
(« Couverture », la part de la valeur, puis « 6 lignes sur 6 »), par le
même code, lus dans l'objet d'où vient la phrase (`regimes[0].coverage`).
Sous 100 %, elle porte le point `--caveat`, comme en §11.2. Si la
couverture passait sous le seuil, le bloc se comporterait comme celui de la
section 5 : aucune règle nouvelle. Ni les trois chiffres de la crise, qui
seraient le grand chiffre que 19.2 écarte, ni exception à §11.2.

### 19.4 Les images

Deux captures, et elles seules, toutes deux du portefeuille « Démo » :

1. **un bloc de mesure** de la section 2, la valeur à risque historique :
   le chiffre, sa phrase, ses détails. La thèse du produit en une image.
   Prise sur le build de démonstration ;
2. **la page de saisie** de l'application locale, avec la composition de
   « Démo ». Prise sur le build ordinaire, servi sur une copie de la base
   qui ne contient que les portefeuilles de la démonstration
   (`python -m tools.export_demo --garder-les-copies`).

**Une seule depuis le 2026-10-14** (chantier 9.6, décision du 2026-10-13) :
le site a sa propre saisie, et la capture de celle de l'application est
retirée avec sa figure (19.1, point 6). Restent les quatre fichiers du bloc
de mesure, dont un chargé par visite ; ce qui suit sur la saisie décrit la
capture retirée.

Leur cadrage est celui de la proposition (§6.1). Elles sortent de la chaîne
des captures de la phase 8 (`docs/outils/`, hors dépôt : `vitrine.mjs`,
`rogner-png.mjs`, `optimiser-png.mjs`), telles quelles, jamais retouchées.
Chaque image est la fenêtre du navigateur, à 390 px de large, cadrée sur
une zone de la page (2026-10-12) : le bloc de mesure, seul ; pour la
saisie, le tableau, de son sous-titre « Saisir les positions » à sa
dernière rangée, rogné au bord droit de la colonne des quantités
(`rogner-png.mjs`). À 390 px, le cadre du tableau coupe la colonne des noms
en plein mot : sur la page de présentation, cela se lirait comme un défaut.
Aucun mot n'est coupé par le bord de l'image ; elle est plus étroite que
390 px, sa largeur suit les colonnes de chaque langue, et elle n'est jamais
agrandie. Sa légende et son texte alternatif disent ce qu'elle montre : le
tableau de saisie.

- **Quatre versions de chacune** : français et anglais, clair et sombre.
  Huit fichiers, dont deux chargés par visite.
- **La langue** : le composant connaît la langue de la page et choisit le
  fichier. Une capture en anglais sur une page française serait la capture
  d'un autre site.
- **Le thème** : aucun composant ne connaît le thème (§4), et
  `<picture media>` suivrait le système, pas le thème figé au bouton.
  Chaque figure porte donc deux `<img>`, l'une claire, l'autre sombre, et
  la feuille de style du composant montre celle du thème, par les
  sélecteurs mêmes de `tokens.css` (§4). L'image masquée n'a pas de boîte :
  avec `loading="lazy"`, le navigateur ne la demande pas. La 9.4 le
  vérifie dans le journal réseau de Chrome, bascule de thème comprise.
- **Largeur de téléphone** : capturées à 390 px de large, à l'échelle 2,
  et affichées à leur taille, 390 px au plus, jamais agrandies. Une capture
  de 1280 px réduite à la largeur d'un téléphone ne se lirait pas.
- **Dimensions déclarées** : `width` et `height` sur chaque `<img>`.
  Aucune image ne déplace le texte en arrivant.
- **Chargement différé** : `loading="lazy"` et `decoding="async"` sur
  toutes. Aucune dans le premier écran (19.9).
  **Posées une fois la page affichée** (2026-10-12). `loading="lazy"` ne
  retient pas une image proche de la fenêtre : Chrome 153 demandait celle
  de la première figure dès la mise en page, avant la première peinture, à
  chaque passage et aux deux écrans de la mesure, alors qu'elle est hors du
  premier écran. Or le premier écran ne lance aucune requête avant d'être
  peint (19.9, point 2). Le composant ne pose donc ses `<img>` qu'une fois
  la page affichée (`lib/affichage.ts`) ; d'ici là, un emplacement vide de
  mêmes dimensions tient leur place. Pas une `<img>` sans fichier : Chrome
  y dessine l'image manquante et son texte alternatif.
- **Poids** : PNG en palette, 100 ko au plus par image. La 9.4 donne les
  poids réels.
- **Cadre** : une bordure de 1 px (`--border`), `--radius-md`. Ni ombre,
  ni inclinaison, ni cadre d'appareil.
- **Texte alternatif** : ce que montre l'image, sans aucun chiffre, comme
  ceux du README. Une légende visible sous chaque figure.
- **Versionnées**, à côté du client : un dossier d'images que la vue
  importe, pour que Vite leur donne une empreinte. L'image de
  prévisualisation (19.7) suit la même règle.
  **Hors du build ordinaire** (2026-10-12) : Vite émet un fichier importé
  même quand la vue qui l'importe est retirée du bundle. Un greffon du
  build ordinaire retire donc ces images de `dist/`, et échoue si un
  fichier du build en nomme une (`sansLaDemonstration`,
  `api/demoAuBuild.ts`).

### 19.5 La structure

- **Le bandeau** : le bandeau simple des pages sans analyse, tel quel
  (§8.2) : la marque, le portefeuille en vue s'il y en a un, le bouton de
  langue, la bascule de thème. Pas de variante réduite. Comme sur la
  méthodologie, il nomme le dernier portefeuille consulté, s'il existe
  encore.
- **La marque** mène à `/` dans la démonstration, sans changer de dessin :
  même taille, même couleur, soulignée au survol et au focus, avec
  l'anneau (§13). C'est le seul chemin vers la présentation depuis les
  deux pages introuvables, qui n'ont pas de rail. Dans l'application
  locale, elle reste un texte.
- **La liste des pages**, dans la démonstration : « Présentation »,
  « Analyse » si un portefeuille est en vue, « Portefeuilles »,
  « Méthodologie », « Avertissement » (« Overview », « Analysis »,
  « Portfolios », « Methodology », « Disclaimer »). La page n'a pas de
  sections à lister : elle est courte. Sous 900 px, la même liste en tête
  de page. Quand le portefeuille en vue est le portefeuille saisi,
  « Positions et import » suit « Analyse », comme dans l'application
  (chantier 9.6) : sa page des positions existe.
- **« Analyse » sans portefeuille consulté** n'est pas proposée, comme
  ailleurs : sans portefeuille en vue, elle n'a rien à montrer. Le tableau
  de la page est l'entrée. Une fois un portefeuille consulté, le bandeau le
  nomme et « Analyse » y mène.
- **L'adresse `/`** rend la page au lieu de rediriger. Elle n'ouvre plus le
  dernier portefeuille consulté, qui reste mémorisé pour le bandeau et
  pour « Analyse ».
- **La mention** (§18.3) en tête, par `Cadre`, comme sur toute page : elle
  donne la date des valeurs du tableau.
- **Le lien d'évitement et le titre** sont ceux de `Cadre`. Le titre reçoit
  le focus après une navigation décidée ; au premier affichage, rien ne
  bouge (§13).

### 19.6 L'avertissement et sa page

L'écran d'acceptation a été décidé pour quelqu'un qui analyse son propre
portefeuille (§15). La démonstration n'en montre aucun : l'écran n'y est
pas posé, et son texte y reste lisible, à un clic au plus de chaque page.

- **Une page à part**, à l'adresse `/avertissement`. Pas une section de la
  page d'accueil, qui doit se lire en deux minutes : elle dit l'essentiel
  en deux phrases (« L'outil décrit : il ne dit jamais quoi faire. »,
  « Tout y décrit le passé : rien n'y est une prévision. ») et renvoie au
  texte.
- **Deux chemins y mènent.** Un lien à la fin de la mention, « Lire
  l'avertissement » : la mention est posée par `Cadre`, donc sur toutes les
  pages, pages introuvables comprises. Le lien est un libellé à part : la
  phrase de la mention ne change pas. Et la dernière entrée de la liste des
  pages, pour que la liste reste celle de toutes les pages et marque la
  page courante. La mention s'allonge : la 9.4 la mesure avec son lien, à
  390 et à 320 px.
- **Ce que la page montre.** Le titre et les sections de
  `<langue>/disclaimer.json`, tels quels, sans copie dans le client. La
  phrase de confirmation n'est pas affichée : il n'y a ni case ni bouton,
  et une phrase à la première personne sans rien à cocher ne dit rien.
  Sous le titre, une phrase du client dit quand le texte est à accepter :
  « Le site demande d'accepter ce texte avant d'analyser un portefeuille
  que vous saisissez. Les portefeuilles d'exemple se lisent sans
  l'accepter : aucun n'est le vôtre. » (chantier 9.6). Jusque-là, elle
  disait que la démonstration ne le demandait pas. Depuis le même
  chantier, le fichier a une section de plus, celle du site (§20.3) : la
  page la montre.
- **Son titre**, dans la page et dans l'onglet, est celui du fichier,
  seul, comme sur l'écran d'acceptation (§6.3). Bandeau simple, liste des
  pages, mention.
- **Ce que devient l'acceptation.** Plus rien n'attend le texte au
  démarrage. Changer de langue relit la page en place (§8.1), sauf sur les
  deux pages du portefeuille saisi, gardées par l'écran de la langue
  (§20.3). Le titre d'un démarrage qui échoue n'a plus d'occasion de
  s'afficher (§18.5) ; son libellé reste. Depuis le chantier 9.6,
  l'acceptation se mémorise de nouveau, celle du texte du site, par
  langue, sous les clés de l'application.
- **Ce qui ne change pas.** Le rappel en pied de la section 6, qui vient de
  la réponse d'analyse (§15). L'acceptation de l'application locale.

L'acceptation bloquante est revenue avec la saisie du site : elle est posée
devant les deux pages du portefeuille saisi, avant tout envoi (§20.3).

### 19.7 Les métadonnées de partage

`index.html` est un fichier statique, lu sans JavaScript par les robots de
prévisualisation : il n'a qu'une langue. C'est l'anglais, celle du dépôt,
du README et du nom du produit ; un lien partagé se lit hors contexte. La
page, elle, suit la langue du navigateur (§8.1).

- `<title>` : « Portfolio Risk Engine », inchangé.
- `description` et `og:description` : la première phrase du README, à
  valider en 9.4 avec l'anglais de la page.
- `og:title`, `og:type` (« website »), `twitter:card`.
- `og:image` et `og:url` demandent une adresse absolue, celle du site, qui
  se choisit en 9.5. **Aucune adresse n'est écrite en dur** : le greffon du
  build de démonstration les ajoute quand l'origine lui est donnée par une
  variable d'environnement, et ne les écrit pas sinon.
- L'image de prévisualisation : 1200 × 630, une vraie capture cadrée par
  la chaîne (le bloc de mesure, thème clair, en anglais), sans composition
  ajoutée.

**Réalisé le 2026-10-12** (`api/demoAuBuild.ts`). L'origine se donne par la
variable d'environnement `MX_RISK_ORIGINE_DU_SITE` : `https://hôte`, sans
chemin ni barre finale. Toute autre valeur arrête le build de
démonstration. Sans elle, `index.html` reçoit la description, `og:type`,
`og:title`, `og:description`, et `twitter:card` à « summary ». Avec elle
s'ajoutent `og:url` et `og:image`, avec le type, les dimensions et le texte
alternatif de l'image (celui de la première figure, en anglais) ;
`twitter:card` passe à « summary_large_image », et l'image est émise sous
un nom qui porte l'empreinte de son contenu. Aucune page ne la demande.

Ces balises n'entrent que dans `dist-demo/index.html`, par le greffon,
comme `noindex`. `dist/` n'en reçoit aucune. Ce qui ne se vérifie que chez
l'hébergeur attend la 9.5 : l'aperçu dans les outils de partage malgré
`noindex`, les adresses absolues, la compression servie, les types de
contenu, et le LCP remesuré sur le vrai site.

**Constaté le 2026-10-13, chez l'hébergeur** (chantier 9.5). Le site est
servi par Cloudflare Pages, à l'origine
`https://portfolio-risk-engine-lemaxoux.pages.dev`, que le build a reçue par
la variable. Des constats de ce jour, pas des valeurs à tenir :

- *Les adresses absolues* : `og:url` vaut l'origine suivie d'une barre, et
  `og:image` l'adresse de l'image sous cette origine. L'image y est servie
  en `image/png`, à 1200 × 630, pour 37 030 octets.
- *Les adresses du client* : pour toute adresse qui n'est pas un fichier
  (`/methodologie`, `/portefeuilles/1`, `/avertissement`, une adresse
  inconnue), l'hébergeur rend `index.html` avec un 200. Le build n'a pas de
  `404.html`. `/index.html` est redirigée vers `/`. Un fichier de données ou
  du bundle qui n'existe pas arrive donc comme cette page, en `text/html` :
  le cas que §18.5 prévoit.
- *`noindex`* : l'en-tête `X-Robots-Tag: noindex` est sur chaque réponse,
  fichiers de données, images, redirection et repli compris.
- *Les types et la compression* : `application/json`,
  `application/javascript`, `text/css`, `font/woff2`, `image/png`. La page,
  les fichiers JavaScript, les feuilles de style et les fichiers de données
  sont servis compressés (`br`) : le fichier d'entrée passe de 401 750 à
  126 782 octets. Ni les polices ni les images ne le sont.
- *L'aperçu malgré `noindex`* : l'outil de LinkedIn (Post Inspector) lit le
  titre, l'image et la description. Il signale que la description, la
  première phrase du README, est plus courte que ce qu'il attend (« The
  description should be at least 100 characters long »). Laissé ouvert pour
  la 9.6 : la 9.5 ne change pas le greffon.

**La description, depuis le chantier 9.6** (option A, décision du
2026-10-13) : la première phrase du README, une espace, puis un fragment de
sa deuxième phrase, mot pour mot, majuscule et point ajoutés. « Portfolio
Risk Engine measures the risk of a portfolio of US-listed stocks and ETFs.
It shows every figure together with the conditions it was estimated
under. » : 159 caractères, au-dessus des 100 que l'outil de LinkedIn
attend. `api/demoAuBuild.partage.test.ts` la tient contre le README,
fragment compris. Le constat dans l'outil de LinkedIn se refait sur le site
redéployé : au 2026-10-14, il n'est pas refait.

### 19.8 Les états

Le texte de la page est dans le bundle : il s'affiche toujours, et tout de
suite. Seuls deux blocs lisent un fichier : le tableau et le résultat. Des
quatre états de §13 :

- *en cours* : le tableau montre un squelette de sa forme finale, une
  rangée par portefeuille (le nombre vient de `contenu/demo.ts`), et le
  bloc du résultat le sien. La page n'est pas occupée en entier : son titre
  et son focus n'attendent rien. Rien n'est annoncé.
  **Ce qui bouge à leur arrivée** (amendé le 2026-10-12 ; la règle était
  « aucun des deux ne déplace le texte en arrivant »). Le tableau ne
  déplace rien à partir de 900 px, où il est dans le premier écran (à
  1350 × 940) : son squelette est le tableau lui-même sans ses données, sa
  légende, ses en-têtes et ses rangées à leur hauteur, et les titres ne s'y
  coupent pas. Sous 900 px, la liste des titres passe à la ligne après ses
  virgules, pour que les trois colonnes tiennent sur un téléphone : le
  tableau peut alors grandir en arrivant, hors du premier écran (à
  412 × 823 et à 390 px). Le bloc du résultat n'est dans le premier écran à
  aucun des deux écrans de la mesure (19.9) : il a le squelette de sa
  forme, sans hauteur fixée, et peut grandir en arrivant. Une hauteur
  réservée demandait des paliers mesurés, par langue et par largeur, écrits
  en dur dans sa feuille : écartés. La 9.4 vérifie que le bloc reste hors
  du premier écran à ces deux écrans.
- *erreur* : si `<langue>/portfolios.json` manque, le message existant
  prend la place du tableau, avec le nom du fichier et le bouton
  « Recharger la liste » (§18.5). Si l'analyse du premier portefeuille
  manque, le même message, avec son fichier, prend la place du bloc du
  résultat. Le reste de la page se lit, liens compris.
- *vide* et *insuffisant* : pas des états de la démonstration (§18.5).

La page de l'avertissement : un squelette de texte en attendant, le
message du fichier manquant sinon.

### 19.9 Le poids de la page

Le découpage du bundle se décide par une mesure : le LCP de `/` sur le
build de démonstration, Lighthouse en profil mobile par défaut (débit
simulé), cinq passages, la médiane, contre 2,5 s, la limite « bon » publiée
par web.dev. Elle est définie sur des visites réelles ; Lighthouse en donne
une estimation de laboratoire.

**Mesuré le 2026-10-11** (Lighthouse 13.5.0, Chrome 153), un constat de ce
jour : 2 862,6 ms sans découpage, sur un écran de texte seul, celui de
l'acceptation ; 2 416,8 ms sur une sonde où l'analyse et la méthodologie se
chargeaient à la demande. Observable Plot et ses dépendances faisaient
40 % du bundle (278 241 octets sur 695 820), et la page d'accueil ne
dessine aucun graphique. La médiane dépassait le seuil : la 9.4 découpe.

1. Le fichier d'entrée porte ce que `/` affiche, et rien de ce qui dessine
   un graphique. **Seule l'analyse, avec Observable Plot, se charge à la
   demande.** La méthodologie et ses deux textes restent dans le fichier
   d'entrée : l'analyse en lit les titres pour nommer ses liens (§9.1,
   règle 5), et la sonde qui a voulu les en sortir a échoué. Un fichier du
   build de démonstration contenait de nouveau des écritures, et la garde
   du build l'a refusé.
2. Le premier écran de `/` n'attend aucune requête. Aucune image n'y
   figure, aux deux écrans de la mesure (412 × 823 et 1350 × 940).
   **L'élément du LCP est du texte du bundle, le titre ou le chapeau ;
   jamais le tableau ni le bloc du résultat, qui attendent un fichier
   exporté.**
   **Il n'en lance aucune non plus avant d'être peint** (2026-10-12).
   Toute page demande la liste des portefeuilles à son montage ; quand la
   première page est `/`, elle part après le premier affichage, comme
   l'analyse du premier portefeuille (`lib/liste.ts`, `lib/affichage.ts`).
   Demandée au montage, elle partait avant la première peinture : la page
   ne l'attendait pas, mais l'estimation de Lighthouse la comptait. Mesuré
   ce jour-là sur la page sans images, avant ce changement : 2 461,8 ms en
   français et 2 514,8 ms en anglais, au-dessus du seuil. L'application
   locale ne change pas.
   **Le réveil du serveur public part aussi après l'affichage** (chantier
   9.6, §20.10) : un seul `GET /health`, nu, par le même moyen. Rien de ce
   que `/` attend n'en dépend. La mesure est refaite (19.10).
3. Attendre le fichier de l'analyse ne change rien de §13. La page
   attendue garde son squelette (`aria-busy`) ; le focus ne se déplace
   qu'une fois par navigation ; le retour depuis la méthode rend le focus
   au lien suivi, que ce fichier soit chargé ou non.
4. Rien ne se découpe par langue derrière une attente qui remplacerait la
   page : un changement de langue laisse la page en place (§13).
5. La garde du build de démonstration lit chaque fichier émis (§18). Un
   découpage qui ramène une écriture dans l'un d'eux fait échouer le build.
6. La mesure se refait à chaque changement de ce que `/` charge, images
   comprises. Une médiane au-dessus du seuil arrête le lot.

**Le même code, donc le même découpage, dans les deux builds.**
L'application locale n'y gagne rien, elle est servie depuis le poste ; mais
un seul graphe de modules est à vérifier, et elle n'y perd que ce que la
règle interdit déjà.

Ce que le découpage ajoute se joue entre l'adresse et la page : au premier
passage par l'analyse, une page d'attente s'intercale. Sur la sonde, son
onglet disait « Chargement », et après un lien suivi le focus se déplaçait
deux fois, d'abord sur la page d'attente, puis sur le titre visé. Le point
3 l'interdit. Deux moyens, que la 9.4 choisit et prouve : demander le
fichier de l'analyse en tâche de fond une fois `/` affichée, pour que
l'attente devienne rare ; et faire que la page d'attente ne prenne pas le
focus quand la page attendue le prendra.

### 19.10 Ce que la 9.4 vérifie

- **Le LCP** : la mesure de 19.9 refaite sur la vraie page, images
  comprises, dans les deux langues ; la médiane sous 2,5 s en profil
  mobile ; l'élément du LCP est le titre ou le chapeau.
- **Les comportements de §13** sur les deux builds, avant et après le
  découpage : un seul déplacement de focus par navigation, le retour depuis
  la méthode, l'arrivée sur une ancre de la méthodologie, le changement de
  langue en place.
- **Le clavier** : chaque arrêt de `/` et de `/avertissement` a son anneau,
  aucun n'est caché ni rogné ; le lien d'évitement ; le titre focalisé
  après une navigation.
- **390 et 320 px**, et 320 × 225 : aucun défilement horizontal de la page,
  le tableau dans son cadre (§9.3), la mention mesurée avec son lien.
- **Les deux thèmes**, bascule comprise : la bonne capture, et l'autre non
  chargée.
- **Les niveaux de gris** : aucune information perdue (§5.3).
- **Les images** : le cadrage de la proposition, les dimensions déclarées,
  aucun déplacement du texte à leur arrivée, les poids réels.
- **Les états** : en cours et erreur, un fichier oublié par le serveur
  d'essai, dans les deux langues.
- **Les textes** : la ponctuation, aucun tiret cadratin, des libellés
  symétriques, la garde prescriptive, aucun nombre dans la prose.
- **Les deux builds** : `dist/` ne contient ni la page d'accueil, ni les
  métadonnées, ni les images ; la démonstration ne contient toujours ni
  `/api` ni écriture, dans aucun de ses fichiers ; le texte rendu de
  l'application locale est le même avant et après ; le serveur de
  l'application sert un build en plusieurs fichiers.

**Les tests existants que la 9.4 modifie.** Trois cas accordés d'avance le
2026-10-11, un quatrième accordé le 2026-10-12, et eux seuls :

1. `contenu/demo.test.ts` : la liste des pages de la démonstration reçoit
   « Présentation » et « Avertissement ». Une valeur de référence change.
2. `contenu/libelles.test.ts` : des lignes ajoutées à sa table `appels()`,
   pour les libellés à paramètres de la page. Aucune assertion ne change.
3. `contenu/libelles.test.ts`, la garde des accents de l'anglais : elle
   retire « HEC Montréal » avant son contrôle, comme elle retire déjà
   « Démo ». Ce nom propre déclaré, et lui seul : l'école garde son vrai
   nom dans la ligne de l'auteur. Une assertion prouve que la garde refuse
   encore « Montréal » seul, et un mot français accentué.
4. `api/demoAuBuild.test.ts`, « interdit l'indexation » (2026-10-12) : la
   balise `noindex` est la première que le greffon ajoute à `index.html`,
   et non plus la seule. Le greffon y ajoute aussi les balises de partage
   (19.7). L'attente « la seule balise » était accessoire : le but du test
   est que `noindex` soit là.

Les tests de `destinationDe(…, true)` restent intacts : la fonction reçoit
un cas, la page de l'avertissement, et ses cas existants ne changent pas.
Tout autre test existant à modifier arrête le lot.

**Constaté le 2026-10-12**, à la fin de la 9.4 (Chrome 153, Lighthouse
13.5.0, profil mobile, cinq passages, la médiane) :

- *Le LCP de `/`*, images et balises de partage comprises : 2 279,4 ms en
  français et 2 279,6 ms en anglais, l'indice de vitesse que Lighthouse
  donne au poste autour de 3 000. Sur le build final, deux séries où cet
  indice était tombé entre 700 et 1 500, sans cause trouvée : 2 259,8 puis
  2 228,2 ms en français, 2 258,5 puis 2 319,6 ms en anglais. L'élément du
  LCP est le chapeau, à chaque passage.
- *Les images* : le bloc de mesure, de 33 506 à 34 058 octets ; le tableau
  de saisie, de 15 011 à 15 392 octets ; l'image de prévisualisation,
  37 030 octets. Aucune partie de la page ne bouge à leur arrivée, et seule
  l'image du thème est demandée, bascule comprise.
- *La mention avec son lien* (19.6) : deux lignes à 390 px et trois à
  320 px, dans les deux langues ; à 1350 px, deux lignes en français, une
  en anglais. Le lien ne se coupe pas.
- *Le premier écran* : le bloc du résultat commence à 2 454 px du haut de
  la page à 412 × 823, et à 1 956 px en français, 1 936 px en anglais, à
  1350 × 940. Il est hors du premier écran aux deux écrans de la mesure
  (19.8), comme les deux figures.

**Constaté le 2026-10-13, sur le site en ligne** (chantier 9.5 ; Chrome 155,
Lighthouse 13.5.0, profil mobile, cinq passages, la médiane) :

- *Le LCP de `/`* : 1 839,8 ms en français et 1 973,2 ms en anglais. Une
  seconde série, le même jour : 1 883,2 ms et 1 838,7 ms. L'élément du LCP
  est le chapeau, à chaque passage. L'indice de vitesse que Lighthouse donne
  au poste : 1 960 au premier passage, puis entre 2 632 et 3 556.
- *Quatre passages sur vingt dépassent 2,5 s* : 2 591,0 ms en français, puis
  2 624,3 et 2 583,5 ms en anglais, dans la première série ; 2 885,7 ms en
  français dans la seconde. La règle est la médiane (19.9) : elle tient pour
  les quatre médianes. La cause n'est pas établie. Les vingt passages font
  les mêmes requêtes, et la série locale du 2026-10-12 avait un passage de
  ce genre, à 3 563,5 ms.
- *Avant la première peinture*, à chaque passage : la page, le fichier
  d'entrée, sa feuille de style et quatre polices. Ni fichier de données ni
  image (19.9, point 2). Après elle : le fichier de l'analyse et sa feuille,
  les deux fichiers de données de la langue, et une image par figure, celle
  du thème.

**Constaté le 2026-10-14, chantier 9.6** (le build de contrôle, fait avec
l'adresse du serveur public et l'origine du site, servi en local par
`vite preview` ; Chrome 155, Lighthouse 13.5.0, profil mobile, cinq
passages, la médiane ; les requêtes vers le serveur public bloquées par
Lighthouse, pour ne pas le réveiller) :

- *Le LCP de `/`* : au lot 2, 2 259,2 ms en français et 2 303,4 ms en
  anglais ; au lot 3, après les corrections, 2 274,8 ms en français et
  2 275,8 ms en anglais. L'élément du LCP est le chapeau, à chaque
  passage.
- *Le réveil de `/`* part après la première peinture : à 293 ms, la
  première peinture à 88 ms (lot 2, sur le site servi en local, contre le
  serveur public d'essai). Ni cookie, ni référent, ni corps, ni paramètre.

ARCHITECTURE.md décrit ce que le code fait : il change avec lui, en 9.4
(« Two builds », « The client », « Deliberate limits of the current
version »).

---

## 20. La saisie en ligne

**Section du 2026-10-14, chantier 9.6.** Le site analyse aussi un
portefeuille que le visiteur compose : il l'envoie à un serveur public
(`backend/public_api/`), qui le calcule sur une base figée et ne garde
rien. L'application locale ne change pas : les pages du portefeuille saisi
n'y existent pas, et son build ne reçoit rien de ce qui suit
(`ARCHITECTURE.md`, « Two builds »). Comme les §18 et §19, cette section
dit seulement ce qui diffère. La proposition validée et ses décisions sont
dans `saisie-proposition.md` (document de cadrage, hors dépôt).

### 20.1 Ce que le site devient

- **Trois portefeuilles d'exemple et un portefeuille du visiteur.** Les
  exemples sont lus dans des fichiers (§18) ; le portefeuille saisi,
  « Votre portefeuille », est analysé par le serveur public, par les mêmes
  composants.
- **Une base figée.** Celle du serveur s'arrête au 2026-09-09, comme les
  exemples : la mention le dit sur chaque page (§18.3). Elle ne se met pas
  à jour.
- **Une liste de titres fermée** : ceux de la base du serveur, que le site
  lit dans `<langue>/securities.json`. Un titre qui n'y est pas est refusé
  sous son champ (20.6). Aucun titre ne s'ajoute.
- **Le serveur ne garde rien.** La composition part dans le corps d'une
  requête, que rien ne journalise, et aucune route n'écrit. Le portefeuille
  n'est gardé que dans le navigateur du visiteur (20.2).

### 20.2 Les adresses, et le portefeuille saisi

| Adresse | Sur le site | Dans l'application |
|---|---|---|
| `/portefeuilles/saisi` | L'analyse du portefeuille saisi. | « Page introuvable ». |
| `/portefeuilles/saisi/positions` | Sa saisie et son import. | « Page introuvable ». |
| `/portefeuilles/<numéro>/positions` | « Page introuvable » (§18.2). | La saisie. |

- **Un seul portefeuille, sans nom à saisir.** Il s'appelle « Votre
  portefeuille », « Your portfolio », dans la langue de la page (décision
  du 2026-10-13 ; la proposition disait « Mon portefeuille »). Ni
  formulaire, ni nom gardé, ni nom envoyé. Deux libellés de même valeur,
  `saisi.nom` et `saisi.titre`.
- **Gardé dans le navigateur**, sous `mx-risk-portefeuille-saisi` : les
  lignes que le serveur a acceptées, à l'analyse du tableau ou à la lecture
  d'un fichier (ticker, quantité, prix de revient), et la date de leur
  dernière modification, lue à l'horloge du navigateur. Un contenu qui ne se
  lit pas comme attendu est absent (`lib/saisi.ts`).
- **Sans stockage**, quand le navigateur le refuse, le portefeuille vit
  dans la mémoire de la page : la saisie et l'analyse marchent le temps de
  la page, et la page des positions le dit. L'annonce « Positions gardées
  dans ce navigateur… » n'est pas faite : elle serait fausse.
- **L'analyse reçue** est gardée le temps de la page, par composition et
  par langue : la page de l'analyse affiche la réponse même qui a validé
  la saisie, sans second appel. Une autre langue redemande l'analyse.
- **Le dernier portefeuille consulté** (`mx-risk-portefeuille`) peut être
  le portefeuille saisi : le bandeau des autres pages le nomme, et
  « Analyse » y mène. L'effacer (20.8) l'oublie aussi là.

### 20.3 L'acceptation

- **Posée devant les deux pages du portefeuille saisi, et elles seules.**
  Arriver à l'une sans avoir accepté le texte de la langue de la page
  affiche l'écran d'acceptation à sa place : celui de l'application (§15),
  bouton de langue en tête, case, bouton qui dit où il mène (« Ouvrir
  l'analyse », « Ouvrir les positions »). Tout envoi part de ces deux
  pages : aucun n'est possible avant.
- **Par langue.** Changer de langue sur l'une d'elles, vers une langue dont
  le texte n'est pas accepté, remplace la page par l'écran de cette langue,
  la garde des modifications consultée d'abord ; vers une langue acceptée,
  la page reste, et se relit. Ailleurs, le changement de langue reste en
  place (§19.6).
- **Une seconde barrière, dans `client.ts`.** Les deux fonctions qui
  envoient demandent une preuve d'acceptation de la langue de la requête,
  que seul `lib/acceptation.ts` délivre, d'après l'empreinte du texte. Sans
  elle, elles lèvent sans appeler le réseau.
- **Le texte** est `<langue>/disclaimer.json` : celui de l'application,
  avec une section de plus, placée avant « Utilisation à vos risques ».
  « Votre portefeuille est envoyé, il n'est pas enregistré » : « Le
  portefeuille que vous saisissez ou importez sur ce site est envoyé à un
  serveur pour le calcul, et n'y est pas enregistré. » En anglais, « Your
  portfolio is sent, not stored » : « The portfolio that you enter or
  import on this site is sent to a server for the calculation, and is not
  stored there. » L'empreinte acceptée est celle de ce texte ; les clés du
  stockage sont celles de l'application (`mx-risk-acceptation`,
  `mx-risk-acceptation-en`).
- **Le rappel en pied de la section 6** vient de la réponse d'analyse,
  comme dans l'application (§15). Celle du serveur public porte le texte de
  l'application, sans la section du site.
- **Le réveil ne demande rien** : il n'envoie rien (20.7).

### 20.4 L'en-tête de l'analyse

| Élément | Portefeuille d'exemple | Portefeuille saisi |
|---|---|---|
| Nom | Celui du fichier. | « Votre portefeuille ». |
| Fraîcheur des positions | « Positions jamais modifiées depuis l'application » (§18.4). | « Positions modifiées le 2026-10-14 » : la phrase de §8.1, avec la date gardée avec les lignes. |
| Valorisation, fenêtre, valeur | Lues dans la réponse. | Lues dans la réponse du serveur. |

La date des positions est postérieure à la date de valorisation, et c'est
vrai : les positions sont d'aujourd'hui, les cours s'arrêtent au gel. La
mention le dit (§18.3). L'horloge du navigateur date un geste du visiteur,
comme `updated_at` dans l'application ; aucune date de cours n'en vient. Le
bandeau reçoit le nom et la date à part de l'analyse : la réponse publique
n'a pas de champ `portfolio`.

### 20.5 La section 3, sans courbe

La réponse du serveur public n'a pas de série (`CLAUDE.md`, « Aucune série
d'un titre en ligne »). Les six sections sont celles de l'application, à
deux différences près, en section 3 :

- la ligne « Niveaux » des détails du calcul, qui lit deux points de la
  courbe, n'est pas affichée ;
- le sous-titre « Où ce creux s'est produit », la courbe et son tableau
  replié laissent place à une phrase, de la prose comme une introduction,
  avec l'espacement du sous-titre au-dessus d'elle (`--space-6`) : « La
  courbe de valeur et son tableau ne sont affichés que pour les
  portefeuilles d'exemple. Les dates du pic et du creux sont dans les
  détails du calcul, ci-dessus. » Elle dit ce qui est affiché et où lire le
  reste ; elle ne donne aucune raison.

Le pic, le creux et le retour au pic viennent de `risk.drawdown` : ils
restent. Les portefeuilles d'exemple gardent leur section 3 telle quelle.
**L'espacement est corrigé le 2026-10-14** (lot 3) : la phrase collait au
bas du bloc de la perte maximale. Mesuré dans Chrome, 32 px au-dessus
d'elle à 390, 718 et 1 350 px, comme au-dessus du sous-titre d'un
portefeuille d'exemple (`views/SectionAuPire.test.ts`).

### 20.6 La page des positions

`TableauSaisie`, `DepotCsv` et `FormatCsv` sont ceux de l'application. La
page reçoit de `client.ts` ce qui change.

| | Application | Site |
|---|---|---|
| L'univers | `GET /api/securities` | `<langue>/securities.json` |
| Le format du fichier | `GET /api/csv-format` | `<langue>/csv-format.json`, aux bornes du serveur public |
| Le bouton | « Enregistrer les positions » : la base | « Analyser ces positions » : le serveur public, puis le navigateur |
| Le fichier | lu et enregistré en base | lu par le serveur public, qui rend les lignes ; gardées dans le navigateur |
| Les refus | sous chaque champ, par `problems[].line` | les mêmes, par le même code |

- **Le tableau ne se garde qu'en l'analysant** : « Analyser ces positions »
  est son seul bouton. Le serveur valide en calculant. Refusée, rien n'est
  gardé. Acceptée, les lignes sont gardées avec la date du jour, et
  l'analyse s'ouvre, avec la réponse même et l'annonce « Positions gardées
  dans ce navigateur le 14 octobre 2026 : 2 lignes. ».
- **Les phrases du site** : sous l'introduction, la liste fermée, et, sans
  stockage, ce qui sera perdu ; avant le bouton, « Analyser envoie ces
  lignes au serveur, qui fait le calcul sans les enregistrer. » ; au-dessus
  de la zone de dépôt, « Le fichier est envoyé au serveur, qui le lit sans
  l'enregistrer. ».
- **Le fichier** est lu par le serveur, qui rend les lignes : le client les
  garde, recharge le tableau, annonce l'import et montre la provenance
  (« Lu dans le fichier »), comme l'application. L'analyse se demande
  ensuite, à sa page.
- La garde des modifications non gardées, sa question sur place et
  `beforeunload` restent, avec les textes du site.

### 20.7 Les états

Le serveur public s'arrête quand personne ne s'en sert, et redémarre à la
première demande. Avant tout envoi, le client attend qu'il réponde à
`GET /health`. Il dit ce qu'il observe, jamais une durée.

| État | Où | Ce qui s'affiche |
|---|---|---|
| vide | Analyse, positions, bloc de la page des portefeuilles | Les textes de l'application (« « Votre portefeuille » n'a encore aucune position. »), le lien vers la saisie, le format du fichier. |
| réveil | Analyse ; envoi d'une saisie ou d'un fichier | La phrase du réveil, et le squelette de la page attendue. |
| calcul | Les mêmes | « Calcul en cours sur le serveur. », la page occupée. |
| refus, titres | Positions | Sous chaque champ, et la liste au-dessus du bouton : l'écran de l'application. Sur l'analyse, un refus de la composition gardée : ses phrases, et « Revoir les positions ». |
| refus, fichier | Zone de dépôt | Le message du serveur, à la place de celui de l'application. |
| limite, serveur occupé | Là où l'envoi est parti | Le texte du serveur, tel quel, et « Réessayer ». |
| sans réponse | Les mêmes | « Le serveur de calcul n'a pas répondu. Vérifier la connexion, puis réessayer. », et « Réessayer ». Sur l'analyse, le titre devient « Analyse indisponible ». |
| réponse illisible | Les mêmes | « La réponse du serveur de calcul n'a pas pu être lue. Réessayer. » |

- **Le réveil.** Un essai, puis un toutes les 3 s après un échec, chacun
  abandonné à 15 s, pendant 150 s au plus : passé ce délai, « sans
  réponse ». Des seuils choisis, dans `api/client.ts`. Le réveil a pris
  52 s par `curl` le 2026-10-13, jusqu'au premier `/health` en 200, et
  71,6 s depuis un navigateur le 2026-10-14 ; pendant le réveil,
  l'hébergeur retient les requêtes au lieu de les refuser. La durée totale
  était de 90 s jusqu'au lot 3 du chantier. Un envoi est abandonné à 60 s.
- **La phrase du réveil** ne s'affiche qu'après une seconde de silence, ou
  au premier échec, seuil choisi : un serveur éveillé répond avant, et rien
  ne clignote.
- **Une réponse qui n'est pas le JSON du serveur** (la page d'attente de
  l'hébergeur, un 503, une réponse sans en-tête CORS) compte comme « pas
  encore réveillé ». Son contenu n'est ni lu plus loin, ni affiché.
- **Aucun saut de mise en page.** La place de l'état est prise dès
  l'attente, avant que rien ne soit dit, et les deux phrases, réveil et
  calcul, sont posées dans la même case, la plus longue donnant la hauteur
  (`components/EtatDuServeur`).
- **Le focus** suit §13. Il ne se déplace qu'une fois par navigation, au
  titre de la page ; un état qui en remplace un autre sur la même page ne
  le déplace pas, et la région de l'état, `role="status"`, se lit quand
  elle change. Sur la page des positions, un refus porte le focus au
  résumé des refus, comme dans l'application.
- **Ce qu'un écran d'échec ne dit pas** : ni cause devinée (le client ne
  distingue pas un serveur qui démarre d'un serveur en panne), ni durée, ni
  texte de l'hébergeur. Une limite posée par l'hébergeur lui-même arrive
  sans en-tête CORS : le client la voit comme « sans réponse », et ne
  l'appelle pas autrement.

### 20.8 Le bloc « Votre portefeuille »

Sur la page des portefeuilles, sous le tableau des trois exemples, une
section « Votre portefeuille », « Your portfolio » :

- **vide** : « Vous pouvez composer un portefeuille parmi les titres de la
  base et lire son analyse. Il n'est gardé que dans ce navigateur. », et le
  lien « Saisir ou importer votre portefeuille » ;
- **rempli** : « 2 lignes, modifiées le 14 octobre 2026. », les liens
  « Analyse » et « Positions », et « Effacer de ce navigateur ». Effacer
  demande d'abord, sur place, comme une suppression : « Effacer votre
  portefeuille de ce navigateur ? Ses 2 lignes seront perdues. »,
  « Effacer le portefeuille », « Annuler ». Effacé, le portefeuille quitte
  le navigateur et la mémoire du dernier consulté ; « Portefeuille effacé
  de ce navigateur. » est annoncé, et le focus revient au titre de la page.

### 20.9 Les textes, tels que validés

Validés le 2026-10-13 avec la proposition (§10), corrections comprises ;
ils sont dans `contenu/libelles.fr.ts` et `libelles.en.ts`, groupes
`saisi`, `positionsDuSite` et `serveur`. Les libellés de l'application qui
restent vrais sont réemployés (« Positions de … », « Saisir les
positions », « Ajouter une ligne », l'aide du tableau, le format du
fichier, « Revoir les positions », « Annuler »).

| Libellé | Français | Anglais |
|---|---|---|
| `saisi.nom`, `saisi.titre` | Votre portefeuille | Your portfolio |
| `positionsDuSite.listeFermee` | Les titres sont ceux de la base de la démonstration : un titre qui n'y est pas est refusé. | The securities are those of the demonstration's database: a security that is not in it is rejected. |
| `positionsDuSite.tableauEstLePortefeuille` | Le tableau est le portefeuille : l'analyser remplace les positions gardées dans ce navigateur par les lignes affichées. | The table is the portfolio: analyzing it replaces the positions kept in this browser with the lines shown. |
| `positionsDuSite.analyser` | Analyser ces positions | Analyze these positions |
| `positionsDuSite.analyseEnCours` | Analyse en cours… | Analyzing… |
| `positionsDuSite.rienGarde` | Rien n'a été analysé ni gardé : | Nothing was analyzed or kept: |
| `positionsDuSite.nonGardees` | Modifications non gardées. | Changes not kept. |
| `positionsDuSite.quitterLesPerd` | Les modifications du tableau ne sont gardées nulle part. Quitter cette page les perd. | The changes to the table are not kept anywhere. Leaving this page loses them. |
| `positionsDuSite.quitter` | Quitter sans les garder | Leave without keeping them |
| `positionsDuSite.universIllisible` | Les noms des titres n'ont pas pu être lus (…). La saisie reste possible : chaque ticker est vérifié à l'analyse. | The security names could not be read (…). Entry remains possible: each ticker is checked when the portfolio is analyzed. |
| `positionsDuSite.stockageBloque` | Ce navigateur ne garde rien pour ce site : votre portefeuille sera perdu à la fermeture de la page. | This browser keeps nothing for this site: your portfolio will be lost when the page is closed. |
| `serveur.reveil` | Le serveur de calcul ne répond pas encore. Il s'arrête quand personne ne s'en sert et redémarre à la première demande : la vôtre partira dès qu'il répondra. | The calculation server does not answer yet. It stops when no one uses it and restarts at the first request: yours will be sent as soon as it answers. |
| `serveur.calcul` | Calcul en cours sur le serveur. | The server is computing. |
| `serveur.reessayer` | Réessayer | Try again |
| `serveur.indisponible` | Analyse indisponible | Analysis unavailable |

Les autres textes de cette section sont cités où ils servent : la phrase
sans courbe (20.5), les phrases de la page des positions (20.6), les états
(20.7), le bloc (20.8), la section de l'acceptation (20.3), la mention
(§18.3), la page de l'avertissement (§19.6), l'accueil (§19.1). Les refus
et la limite sont les phrases du serveur (`backend/textes/<langue>/
public.py`), affichées telles quelles, comme celles de l'application ; les
erreurs de validation de FastAPI restent en anglais dans les deux langues,
comme dans l'application. Un terme hors du glossaire anglais (§15),
« calculation server », validé avec le reste.

### 20.10 Le poids de la page

La saisie entre dans le fichier d'entrée du site, comme elle est dans celui
de l'application ; seule l'analyse se charge à la demande (§19.9). Sur
`/`, le réveil du serveur public part après l'affichage, par
`lib/affichage.ts`, comme le fichier de l'analyse : un seul `GET /health`,
nu, muet (ni attente, ni message, ni nouvel essai). Le LCP de `/` est
remesuré à chaque lot du chantier (19.10) : la médiane reste sous 2,5 s,
l'élément est le chapeau.

### 20.11 Les tests existants modifiés, et les constats datés

**Les tests existants modifiés**, avec l'accord de Maxence, et eux seuls :
les dix cas de la proposition (§11), un onzième pour la décision 7, un
douzième au lot 3. Le troisième, prévu sous condition, n'a pas servi.

1. `tests/test_export_demo.py`, `FICHIERS_PAR_LANGUE` : sept noms par
   langue, `securities.json` et `csv-format.json` en plus.
2. Même fichier, chaque fichier est une réponse de l'API : les cinq fichiers
   qui sont des réponses locales ; `disclaimer.json` et `csv-format.json`
   ont leurs tests à eux.
3. Même fichier, les langues ne diffèrent par aucun nombre : non modifié.
   `csv-format.json` ne diffère entre les langues que par son exemple, un
   texte.
4. `tests/test_textes_symetriques.py`, la table `CAS` : les lignes des
   textes du serveur public. Aucune assertion modifiée.
5. `contenu/demo.test.ts`, la mention : les quatre chaînes de la nouvelle.
6. `contenu/avertissement.test.ts`, la phrase de la page : les deux
   nouvelles chaînes, et le titre du cas.
7. `api/demoAuBuild.test.ts`, les méthodes d'écriture : un POST seul n'est
   pas une faute, deux le sont ; PUT, DELETE et PATCH le restent.
8. Même fichier, les fichiers attendus : douze chemins pour deux
   portefeuilles, et le fichier de trop s'appelle autrement.
9. `api/demoAuBuild.partage.test.ts`, la description : la première phrase
   du README, puis le fragment de la deuxième, lu dans le README.
10. `contenu/libelles.test.ts`, la table `appels()` : quatre lignes
    ajoutées. Aucune assertion modifiée.
11. `images/presentation/captures.test.ts` : quatre captures au lieu de
    huit (décision 7).
12. `api/client.demo.test.ts` (lot 3) : les deux cas qui supposaient un
    réveil de 90 s avancent leur horloge au-delà de 150 s, et le second
    borne ses essais à 51 au lieu de 31.

**Constaté le 2026-10-14**, dans Chrome 155, sur le site servi en local
contre le serveur public d'essai (`MX_RISK_ORIGINE_DE_DEVELOPPEMENT`) et un
faux relais d'hébergeur endormi, hors dépôt. Des constats de ce jour, pas
des valeurs à tenir :

- *L'acceptation* précède tout envoi : rien ne part avant elle. Depuis la
  page d'accueil, seul le réveil part vers le serveur, à 293 ms, après la
  première peinture (88 ms).
- *Le réveil* : la phrase à 0,5 s derrière une page d'attente sans CORS, à
  1,5 s derrière des requêtes retenues, puis le calcul ; aucun saut de mise
  en page. Au lot 3, un réveil de 100 s, requêtes retenues : six essais, le
  sixième, parti 90 s après le premier, reçoit la réponse, et l'analyse
  s'affiche 96,3 s après l'arrivée sur la page. Avec l'ancien seuil de
  90 s, l'attente aurait fini à 87 s sur « sans réponse », d'après le code.
- *Sans réponse*, au bout de la durée du réveil (90 s au lot 2, 150 s au
  lot 3, dans les captures), puis « Réessayer » ; la limite atteinte (429),
  sa phrase telle quelle et « Réessayer ». Non provoqué : le serveur occupé
  (503), qui suit le chemin de la limite.
- *Les captures du lot 3*, à 390 px, sombre et clair, dans les deux
  langues (hors dépôt) : aucun débordement, aucune page coupée.
- *La langue* : changée sur une page gardée, l'écran de l'autre langue,
  puis l'analyse redemandée dans cette langue ; l'annonce de l'envoi
  retirée (lot 3).
- *La mention avec son lien* : trois lignes à 390 et à 320 px, deux à
  1 350 px, dans les deux langues. La date du tableau de l'accueil est
  dans sa légende, 16 px sous « arrêtée à la date ci-dessous », à 390, 500
  et 1 350 px.
- *L'application locale* : son texte rendu est le même avant et après le
  chantier, octet pour octet, deux langues et quatre variantes.
- *Le réveil vu de Render*, par Cowork, dans Chrome, depuis le site en
  ligne, serveur endormi : trois essais retenus sans réponse puis
  abandonnés, le quatrième en 200 ; jamais la page d'attente de
  l'hébergeur ; 71,6 s en tout.
