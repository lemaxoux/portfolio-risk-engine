/**
 * Un lien vers une page de l'application — un VRAI `<a href>`.
 *
 * Le clic ordinaire change de page sans recharger (`naviguer`), et passe donc
 * par la garde des modifications non enregistrées. Tout le reste est laissé
 * au navigateur : clic du milieu, Ctrl ou Cmd + clic, Maj + clic ouvrent un
 * onglet ou une fenêtre, comme sur n'importe quel lien. Un bouton déguisé en
 * lien perdrait tout cela, et l'adresse ne s'afficherait plus au survol.
 */
import type { AnchorHTMLAttributes, MouseEvent } from 'react'

import { naviguer } from '../lib/route'

interface Props extends Omit<AnchorHTMLAttributes<HTMLAnchorElement>, 'href'> {
  readonly vers: string
}

export function Lien({ vers, onClick, children, ...reste }: Props) {
  const surClic = (evenement: MouseEvent<HTMLAnchorElement>) => {
    onClick?.(evenement)
    if (
      evenement.defaultPrevented ||
      evenement.button !== 0 ||
      evenement.metaKey ||
      evenement.ctrlKey ||
      evenement.shiftKey ||
      evenement.altKey
    ) {
      return
    }
    evenement.preventDefault()
    naviguer(vers)
  }

  return (
    <a href={vers} onClick={surClic} {...reste}>
      {children}
    </a>
  )
}
