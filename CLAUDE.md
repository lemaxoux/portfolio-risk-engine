# CLAUDE.md — Mx Risk MGT

Moteur de risque de portefeuille (Python), API FastAPI, frontend Vite + React.
Le détail de chaque point ci-dessous est dans `README.md`. La spécification
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
  moins (U+2212) sont fixés, jamais laissés à `Intl`.
- **Tokens seulement.** Aucune couleur hors de `src/styles/tokens.css`, aucune
  taille de police en `px` hors de `typography.css` (vérifié par
  `tokens.test.ts`).
- **Types de l'API engendrés, jamais écrits à la main** :
  `python -m tools.openapi_schema`, puis `cd frontend; npm run api:types`.

## Tests

```powershell
.\venv\Scripts\python.exe -m pytest     # backend, depuis app/ ; hors ligne
cd frontend
npm test                                # Vitest
npx tsc --noEmit -p .                   # types
npm run build                           # types puis bundle dans dist/
```

Chaque commit laisse les suites vertes et le README à jour.

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
consigne contredit `DESIGN.md` ou une convention du README, ou si une valeur
de référence d'un test change.

## Pièges connus

- L'outil d'écriture et les scripts passés en heredoc décodent ` `,
  ` ` et `−` en caractères invisibles. Dans les tests, écrire les
  échappements, puis vérifier avec `grep`.
- Fins de ligne : LF dans le dépôt (`.gitattributes`). Un script qui réécrit
  un fichier sous Windows doit écrire des octets, pas du texte.
