/**
 * Configuration Vite — développement et build.
 *
 * ═══ LE PROXY REMPLACE CORS ═══
 *
 * En développement, le navigateur charge la page depuis Vite (port 5173) et
 * l'API écoute sur 127.0.0.1:8000 : deux origines, donc une requête bloquée
 * par la politique de même origine. Deux réponses possibles, et une seule est
 * bonne ici.
 *
 * Ouvrir CORS dans FastAPI ferait porter au BACKEND une permission qui n'a de
 * sens qu'en développement, sur une API délibérément liée à 127.0.0.1 et sans
 * authentification (voir `backend/api/app.py`). Elle resterait en production,
 * où le frontend est servi par FastAPI lui-même — donc à la même origine, donc
 * sans le moindre besoin de CORS. Un middleware qui ne sert jamais est un
 * middleware qu'on finit par élargir.
 *
 * Le proxy garde la permission du côté qui en a besoin, et seulement là : Vite
 * relaie `/api/*` vers l'API, le navigateur ne voit qu'une origine, et il n'y a
 * rien à retirer le jour du déploiement.
 *
 * ═══ LES COUPURES DE LA MÉTHODOLOGIE, AU BUILD ═══
 *
 * Le texte livré de la méthodologie porte ses coupures conditionnelles
 * (U+00AD), posées au build seulement : la prose justifiée ne dépend plus du
 * dictionnaire de césure du navigateur (DESIGN.md §6.3,
 * `src/contenu/coupuresAuBuild.ts`).
 *
 * ═══ DEUX BUILDS ═══
 *
 * `npm run build` écrit `dist/`, l'application que sert FastAPI. `npm run
 * build:demo` (mode `demo`) écrit `dist-demo/`, un site statique sans
 * serveur : `src/api/client.ts` y lit des réponses de l'API enregistrées, et
 * le greffon de `src/api/demoAuBuild.ts` y ajoute ces fichiers, l'interdiction
 * d'indexer, les balises de partage (les adresses absolues seulement si
 * `MX_RISK_ORIGINE_DU_SITE` donne l'origine du site), et la garde qui refuse
 * un bundle où resterait une écriture. Ce
 * greffon n'est chargé que dans ce mode : rien de la démonstration n'entre
 * dans `dist/`. Le build ordinaire charge l'autre, `sansLaDemonstration`,
 * qui en retire les captures de la page de présentation.
 */
import { fileURLToPath } from 'node:url'

import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

import {
  demonstration,
  lireLOrigine,
  sansLaDemonstration,
  VARIABLE_DE_L_ORIGINE,
} from './src/api/demoAuBuild'
import { coupuresDeLaMethodologie } from './src/contenu/coupuresAuBuild'

// L'adresse est celle qu'impose `backend/api/__main__.py`, pas une option.
const API = 'http://127.0.0.1:8000'

// Ce qu'écrit `python -m tools.export_demo`, à la racine du dépôt.
const EXPORT_DE_LA_DEMO = fileURLToPath(new URL('../demo/export', import.meta.url))

// L'image de prévisualisation des liens partagés (DESIGN.md §19.7).
const APERCU = fileURLToPath(new URL('./src/images/presentation/apercu.png', import.meta.url))

export default defineConfig(({ mode }) => {
  const demo = mode === 'demo'
  return {
    plugins: [
      react(),
      coupuresDeLaMethodologie(),
      demo
        ? demonstration(EXPORT_DE_LA_DEMO, {
            origine: lireLOrigine(process.env[VARIABLE_DE_L_ORIGINE]),
            apercu: APERCU,
          })
        : sansLaDemonstration(),
    ],
    server: {
      proxy: {
        '/api': {
          target: API,
          changeOrigin: false,
        },
      },
    },
    build: {
      // FastAPI sert `dist` en production (`backend/api/static.py`) ;
      // `dist-demo` part chez un hébergeur statique.
      outDir: demo ? 'dist-demo' : 'dist',
      emptyOutDir: true,
    },
    test: {
      // Environnement Node : ce qui est testé ici est du code pur — formatage
      // des nombres, empreinte du texte d'acceptation, lecture des fichiers de
      // style. Rien qui ait besoin d'un DOM simulé. Ce qui tient au rendu se
      // vérifie dans un vrai navigateur, pas dans une imitation.
      environment: 'node',
      include: ['src/**/*.test.ts'],
    },
  }
})
