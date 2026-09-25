/**
 * Bandeau permanent — DESIGN.md §8.1.
 *
 * Quelques informations s'appliquent à TOUS les chiffres de la page : la date
 * de valorisation, la fenêtre d'estimation, la valeur du portefeuille, la
 * fraîcheur des positions. Elles ne défilent donc jamais. C'est la traduction
 * visuelle directe de la discipline du backend : on voit sous quelles
 * conditions on lit avant de lire.
 *
 * ═══ « FENÊTRE D'ESTIMATION » — LE MOT EST CHOISI ═══
 *
 * Le nombre vient de `analysis.estimation_window`, la fenêtre du panel de
 * régime courant, publiée telle quelle par l'API. Il n'est PAS déduit d'une
 * mesure : `risk.volatility.window` porte le même nombre aujourd'hui, et l'y
 * lire promouvrait une mesure particulière en fenêtre du document par
 * convention silencieuse — exactement ce que `AnalysisOut` refuse de faire.
 *
 * Le mot « estimation » borne la portée : les scénarios ont leurs propres
 * périodes, et le bandeau ne parle pas pour eux. Chaque bloc `<Measure>`
 * continue d'afficher la sienne ; le bandeau ne dispense de rien.
 */
import { useEffect, useRef } from 'react'

import type { Analysis } from '../api/types'
import { dateISO, montant, seances } from '../lib/format'
import { phraseFenetreReduite, phraseFraicheurPositions } from '../lib/phrases'
import { ThemeToggle } from './ThemeToggle'
import styles from './Bandeau.module.css'

/**
 * La hauteur du bandeau, publiée en variable CSS (`--hauteur-bandeau`) pour
 * que les ancres de section s'arrêtent SOUS lui. Elle suit son contenu —
 * deux, trois ou quatre lignes, et bien davantage à 390 px — : une marge
 * écrite en dur laisserait le titre de la section sous le bandeau collant.
 */
function useHauteurPubliee() {
  const bandeau = useRef<HTMLElement>(null)
  useEffect(() => {
    const noeud = bandeau.current
    if (noeud === null) return
    const racine = document.documentElement
    const observateur = new ResizeObserver(([entree]) => {
      if (entree) {
        racine.style.setProperty(
          '--hauteur-bandeau',
          `${Math.ceil(entree.borderBoxSize[0]?.blockSize ?? noeud.offsetHeight)}px`,
        )
      }
    })
    observateur.observe(noeud)
    return () => {
      observateur.disconnect()
      racine.style.removeProperty('--hauteur-bandeau')
    }
  }, [])
  return bandeau
}

export function Bandeau({ analyse }: { analyse: Analysis }) {
  const reduite = phraseFenetreReduite(
    analyse.estimation_window,
    analyse.limiting_positions,
  )
  const bandeau = useHauteurPubliee()

  return (
    <header ref={bandeau} className={styles.bandeau}>
      <div className={styles.identite}>
        <span className={styles.marque}>Mx Risk MGT</span>
        <span className={styles.portefeuille}>{analyse.portfolio.name}</span>
      </div>

      <div className={styles.conditions}>
        {/* Chaque condition est une PAIRE insécable : un libellé ne se sépare
            jamais de sa valeur, et « Fenêtre d'estimation » ne se coupe pas
            en deux. Le séparateur est dessiné par la feuille de style entre
            deux paires, et disparaît quand elles s'empilent. */}
        <p className={styles.ligne}>
          <span className={styles.paire}>
            <span className={styles.libelle}>Valorisé au</span>{' '}
            <span className={styles.valeur}>{dateISO(analyse.as_of)}</span>
          </span>
          <span className={styles.paire}>
            <span className={styles.libelle}>Fenêtre d'estimation</span>{' '}
            <span className={styles.valeur}>
              {seances(analyse.estimation_window.observations)}
            </span>
          </span>
        </p>
        <p className={styles.ligne}>
          {phraseFraicheurPositions(analyse.portfolio.updated_at)}
        </p>
        {reduite !== null && (
          <p className={styles.reduite}>
            {/* Point de réserve : un ÉLÉMENT, pas une couleur de texte, pour
                qu'il survive à une capture en niveaux de gris (§5.3). */}
            <span className={styles.point} aria-hidden="true" />
            {reduite}
          </p>
        )}
      </div>

      <div className={styles.total}>
        <span className={styles.montant}>
          {montant(analyse.total_value, analyse.valuation.currency)}
        </span>
        <ThemeToggle />
      </div>
    </header>
  )
}
