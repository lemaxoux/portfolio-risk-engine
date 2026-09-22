/**
 * Point d'entrée.
 *
 * L'ORDRE DES IMPORTS DE STYLE EST L'ORDRE DE LA CASCADE, et il est
 * intentionnel : les tokens d'abord, puisque tout le reste les lit ; la remise
 * à zéro ensuite, qui s'en sert déjà pour le fond du corps ; la typographie
 * enfin, qui charge les polices.
 */
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import './styles/tokens.css'
import './styles/reset.css'
import './styles/typography.css'

import { App } from './App'

const racine = document.getElementById('root')
if (racine === null) throw new Error("L'élément #root est absent de index.html.")

createRoot(racine).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
