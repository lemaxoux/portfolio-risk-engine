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
 */
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// L'adresse est celle qu'impose `backend/api/__main__.py`, pas une option.
const API = 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: API,
        changeOrigin: false,
      },
    },
  },
  build: {
    // FastAPI sert ce dossier en production (`backend/api/static.py`).
    outDir: 'dist',
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
})
