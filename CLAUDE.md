# CLAUDE.md — Portfolio Risk Engine

Moteur de risque de portefeuille (Python), API FastAPI, frontend Vite + React.
Le détail de chaque point ci-dessous est dans `ARCHITECTURE.md` (les
décisions) et `METHODOLOGY.md` (les mesures), en anglais. La spécification
visuelle est `frontend/DESIGN.md` : elle se lit en entier avant tout CSS.

La racine du dépôt est ce dossier, `app/`. Les documents de cadrage, dont la
feuille de route des phases, sont dans le dossier parent. Ils sont hors dépôt
et ne se versionnent pas.

## Conventions non négociables

- **Personne ne calcule hors du moteur.** Ni l'API (`backend/api/`, vérifié
  par `tests/test_api_discipline.py`), ni le frontend. Une donnée qui manque
  s'ajoute au moteur avec son test, puis au schéma. Sérialiser est permis ;
  un nouveau calcul demande l'accord de Maxence.
- **Chaque résultat porte sa provenance** : fenêtre, date `as_of`, méthode,
  nombre d'observations. On n'affirme jamais ce qu'une estimation dégénérée
  ou trop mince ne permet pas d'affirmer. Une estimation signalée comme mince
  n'entre pas dans une conclusion.
- **Le moteur de règles décrit, il ne prescrit pas.** Aucun score global.
- **Un seul formateur de chaque côté.** Tout nombre écrit dans un texte
  publié passe par `backend/typography.py`, et côté client par
  `frontend/src/lib/format.ts`. Les espaces (U+202F, U+00A0) et le signe
  moins (U+2212) sont fixés, jamais laissés à `Intl`. Les nombres du texte
  de méthodologie (`frontend/src/contenu/`) sont écrits dans son fichier de
  contenu et comparés au moteur, écriture comprise, par
  `tests/test_methodologie.py`.
- **Tokens seulement.** Aucune couleur hors de `src/styles/tokens.css`, aucune
  taille de police en `px` hors de `typography.css` (vérifié par
  `tokens.test.ts`).
- **Types de l'API engendrés, jamais écrits à la main** :
  `python -m tools.openapi_schema`, puis `cd frontend; npm run api:types`.
- **Une source de données, choisie au build, dans `client.ts` seulement.**
  `frontend/src/api/client.ts` est le seul module qui sait d'où viennent les
  données, et où part une saisie : l'API ; ou, dans le build de
  démonstration (`npm run build:demo`), les réponses enregistrées par
  `python -m tools.export_demo`, et un serveur public dont l'adresse arrive
  au build (`MX_RISK_SERVEUR_PUBLIC`, obligatoire). Le reste du client ne lit
  `DEMO` que pour quatre choses : masquer ce qui écrit en base, afficher la
  mention, rendre la page d'accueil à l'adresse `/`, et rendre les deux
  pages du portefeuille saisi, les seules devant lesquelles l'écran
  d'acceptation est posé (DESIGN.md §18.1, §19, §20).
  La démonstration n'écrit dans aucune base. La garde de son build refuse
  « /api », toute écriture de l'application et toute seconde adresse de
  serveur : au plus un POST, celui du serveur public, et des origines d'une
  liste fermée. Ses fichiers exportés (`demo/export/`) et `dist-demo/` ne se
  versionnent pas.
- **Le serveur public est une application à part** (`backend/public_api/`),
  sur une base ouverte en lecture seule (`backend/db/lecture_seule.py`),
  sans ingestion ni fournisseur, avec ses propres textes
  (`backend/textes/<langue>/public.py`) ; ni fenêtre ni indice en
  paramètre. Sa base se bâtit par `python -m tools.base_serveur` et ne va
  jamais dans le dépôt (`tests/test_serveur_public.py`,
  `tests/test_serveur_public_frontiere.py`).
- **Aucune série d'un titre en ligne, ni rien qui permette d'en
  reconstruire une.** Le serveur public ne rend aucune liste de points datés
  et n'accepte ni fenêtre ni indice en paramètre ; l'export de la
  démonstration refuse des portefeuilles dont une combinaison isole un titre
  (`tests/test_serveur_public.py`, `tests/test_export_demo.py`).
- **Deux langues, un seul texte par langue.** Une phrase que publie le
  serveur vit dans `backend/textes/fr/` et `backend/textes/en/`, mêmes noms
  et mêmes signatures : elle s'ajoute dans les deux, avec ses cas dans
  `tests/test_textes_symetriques.py`. Sans `?lang`, chaque réponse reste la
  française d'avant le chantier 7D, octet pour octet, au nom du produit près
  (`ARCHITECTURE.md`, « Two languages »).

## Tests

```powershell
.\venv\Scripts\python.exe -m pytest     # backend, depuis app/ ; hors ligne
cd frontend
npm test                                # Vitest
npx tsc --noEmit -p .                   # types
npm run build                           # types puis bundle dans dist/
npm run build:demo                      # la démonstration, dans dist-demo/
```

`build:demo` relit `demo/export/`, que `python -m tools.export_demo` écrit
depuis la base locale, et demande l'adresse du serveur public :
`MX_RISK_SERVEUR_PUBLIC=https://hôte`, sans chemin ni barre finale (pour un
essai, `http://127.0.0.1:<port>`). La base du serveur public se bâtit hors
du dépôt : `python -m tools.base_serveur --sortie <fichier>`.

Tout déploiement de la démonstration part de `main` et refait d'abord les
constats : `HEAD` = `origin/main`, arbre propre, build avec l'origine du site
(`MX_RISK_ORIGINE_DU_SITE`) et l'adresse du serveur public
(`MX_RISK_SERVEUR_PUBLIC`), liste SHA-256 vérifiée, l'adresse du serveur
dans le bundle avec elle (`ARCHITECTURE.md`, « Two builds »).

Tout déploiement du serveur public part d'un commit public vérifié, par le
dépôt privé, à la main : l'arbre `app/` du dépôt privé est celui de ce
commit, ce commit est sur `origin/main`, l'empreinte de la base est
vérifiée, et `GET /health` rend l'empreinte du code que
`python -m tools.base_serveur --empreinte-du-code <commit>` calcule. Un
changement sous `backend/` ou de `requirements-serveur.txt` change cette
empreinte : le serveur est à redéployer. Un changement du client seul ne
redéploie que le site (`ARCHITECTURE.md`, « Two builds »).

Chaque commit laisse les suites vertes et la documentation à jour
(`README.md`, `METHODOLOGY.md`, `ARCHITECTURE.md`), ses nombres datés tenus
par `tests/test_documents_publics.py`.

## La base réelle ne se lit que figée

`data/mx_risk.sqlite` est un fichier vivant. `refresh` y ajoute des séances,
`rebuild` la réécrit. Aucun test ne la lit directement : `tests/conftest.py`
en est le seul accès, par une copie tronquée à `DATE_GEL`. Trois fixtures
servent : `base_figee_partagee` (lecture seule), `base_figee` (propre au
test, pour écrire) et `analyse_reelle`. `tests/test_gel_des_tests.py` échoue
sur toute autre ouverture.

Ne jamais lancer `refresh` ni `rebuild` sur la vraie base sans l'accord de
Maxence. Pour essayer, travailler sur une copie, désignée par
`MX_RISK_DB_PATH`. Le port 8000 est celui de son API : en développement,
utiliser un autre port avec une copie de la base.

## Un test existant ne se modifie pas pour passer

Un test existant ne se modifie qu'après avoir expliqué pourquoi il était
faux, et avec l'accord de Maxence. Il faut aussi s'arrêter et demander si une
consigne contredit `DESIGN.md` ou une convention d'`ARCHITECTURE.md` ou de
`METHODOLOGY.md`, ou si une valeur
de référence d'un test change.

## Pièges connus

- L'outil d'écriture et les scripts passés en heredoc décodent ` `,
  ` ` et `−` en caractères invisibles. Dans les tests, écrire les
  échappements, puis vérifier avec `grep`.
- Fins de ligne : LF dans le dépôt (`.gitattributes`). Un script qui réécrit
  un fichier sous Windows doit écrire des octets, pas du texte.
