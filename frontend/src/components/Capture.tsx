/**
 * Une capture d'écran du produit, et sa légende — DESIGN.md §19.4.
 *
 * ═══ DEUX IMAGES, UNE SEULE CHARGÉE ═══
 *
 * Aucun composant ne connaît le thème (§4), et `<picture media>` suivrait le
 * système, pas le thème figé au bouton. La figure porte donc deux `<img>`,
 * l'une claire, l'autre sombre, et la feuille de style montre celle du
 * thème, par les sélecteurs mêmes de `tokens.css`. L'image masquée n'a pas
 * de boîte : avec `loading="lazy"`, le navigateur ne la demande pas.
 *
 * ═══ RIEN NE BOUGE QUAND ELLE ARRIVE ═══
 *
 * `width` et `height` sont la taille d'affichage : la place est prise avant
 * le fichier. L'image s'affiche à cette taille, ou plus petite dans une
 * colonne plus étroite ; jamais agrandie.
 *
 * ═══ AUCUN FICHIER DEMANDÉ AVANT QUE LA PAGE SOIT PEINTE ═══
 *
 * `loading="lazy"` ne suffit pas : un navigateur demande une image différée
 * dès la mise en page quand elle est à moins d'un ou deux écrans de la
 * fenêtre, donc avant la première peinture, même hors du premier écran. Or
 * le premier écran ne lance aucune requête avant d'être peint (§19.9). Les
 * `<img>` ne sont donc posées qu'une fois la page affichée (`lib/affichage`).
 * D'ici là, un emplacement vide tient leur place : mêmes dimensions, même
 * feuille, donc la même boîte. Pas une `<img>` sans fichier : un navigateur
 * y dessine l'image manquante et son texte alternatif, ou ne lui garde pas
 * sa place.
 *
 * Le texte alternatif dit ce que montre l'image, sans chiffre. Les deux
 * `<img>` le portent : une seule est rendue, donc une seule est lue.
 */
import { useEffect, useState } from 'react'

import { apresLAffichage } from '../lib/affichage'
import styles from './Capture.module.css'

interface Props {
  /** Le fichier du thème clair. */
  readonly claire: string
  /** Le fichier du thème sombre. */
  readonly sombre: string
  /** La taille d'affichage, en pixels CSS. */
  readonly largeur: number
  readonly hauteur: number
  /** Ce que montre l'image. */
  readonly alternative: string
  /** La légende visible, sous l'image. */
  readonly legende: string
}

export function Capture({ claire, sombre, largeur, hauteur, alternative, legende }: Props) {
  const [affichee, setAffichee] = useState(false)
  useEffect(() => apresLAffichage(() => setAffichee(true)), [])

  const image = (fichier: string, theme: string | undefined) =>
    affichee ? (
      <img
        className={`${styles.image} ${theme}`}
        src={fichier}
        alt={alternative}
        width={largeur}
        height={hauteur}
        loading="lazy"
        decoding="async"
      />
    ) : (
      <svg
        className={`${styles.image} ${theme}`}
        width={largeur}
        height={hauteur}
        viewBox={`0 0 ${largeur} ${hauteur}`}
        aria-hidden="true"
      />
    )
  return (
    <figure className={styles.capture}>
      {image(claire, styles.claire)}
      {image(sombre, styles.sombre)}
      <figcaption className={styles.legende}>{legende}</figcaption>
    </figure>
  )
}
