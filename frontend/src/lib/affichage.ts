/**
 * Ce qui attend que la page soit affichée — DESIGN.md §19.9 (chantier 9.4).
 *
 * Le premier écran n'attend que ses propres requêtes. Ce qui peut venir
 * ensuite, comme le fichier de l'analyse demandé en tâche de fond, part une
 * fois la page chargée ET peinte : après `load`, deux images, puis un temps
 * mort. Une demande partie plus tôt disputerait le débit à ce que le premier
 * écran affiche.
 *
 * Dans un onglet en arrière-plan, aucune image n'est peinte et rien ne part :
 * la demande se fera à la navigation, comme sans cette avance.
 */

/** Le temps mort après la seconde image, en millisecondes. */
const TEMPS_MORT = 200

/** Lance `action` une fois la page affichée. Rend de quoi y renoncer. */
export function apresLAffichage(action: () => void): () => void {
  let renonce = false
  let image = 0
  let delai: number | undefined

  const partir = () => {
    image = requestAnimationFrame(() => {
      image = requestAnimationFrame(() => {
        delai = window.setTimeout(() => {
          if (!renonce) action()
        }, TEMPS_MORT)
      })
    })
  }

  if (document.readyState === 'complete') partir()
  else window.addEventListener('load', partir, { once: true })

  return () => {
    renonce = true
    window.removeEventListener('load', partir)
    cancelAnimationFrame(image)
    window.clearTimeout(delai)
  }
}
