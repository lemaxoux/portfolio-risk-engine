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
import { cheminDe } from '../lib/route'
import { BoutonLangue } from './BoutonLangue'
import { Lien } from './Lien'
import { ThemeToggle } from './ThemeToggle'
import styles from './Bandeau.module.css'

/**
 * La marque, et le portefeuille en vue quand il y en a un.
 *
 * Le choix du portefeuille est une PAGE (`/portefeuilles`), et non un menu
 * déroulant qui changerait de page à la sélection : un tel menu déplace
 * l'utilisateur au moindre coup de flèche (WCAG 3.2.2). Le lien le dit en
 * toutes lettres, sous le nom.
 */
function Identite({ nom, navigation = true }: { nom: string | null; navigation?: boolean }) {
  return (
    <div className={styles.identite}>
      <span className={styles.marque}>Mx Risk MGT</span>
      {nom !== null && <span className={styles.portefeuille}>{nom}</span>}
      {navigation && (
        <Lien vers={cheminDe({ vue: 'portefeuilles' })} className={styles.changer}>
          {nom === null ? 'Portefeuilles' : 'Changer de portefeuille'}
        </Lien>
      )}
    </div>
  )
}

/**
 * Le bandeau des pages sans analyse — liste, saisie. Ni date de
 * valorisation, ni fenêtre d'estimation : aucun chiffre de ces pages n'en
 * dépend, et les afficher ferait croire le contraire. La marque, le
 * portefeuille en vue, le bouton de langue et la bascule de thème.
 *
 * `navigation` vaut `false` avant l'acceptation : rien ne mène ailleurs tant
 * que le bandeau d'acceptation n'a pas été traversé (§15).
 */
export function BandeauSimple({
  portefeuille,
  navigation = true,
}: {
  portefeuille: string | null
  navigation?: boolean
}) {
  const bandeau = useHauteurPubliee()
  return (
    <header ref={bandeau} className={styles.bandeau}>
      <Identite nom={portefeuille} navigation={navigation} />
      <div className={styles.total}>
        <BoutonLangue />
        <ThemeToggle />
      </div>
    </header>
  )
}

/**
 * La hauteur du bandeau, publiée en variable CSS (`--hauteur-bandeau`) pour
 * que les ancres de section s'arrêtent SOUS lui. Elle suit son contenu —
 * deux, trois ou quatre lignes, et bien davantage à 390 px — : une marge
 * écrite en dur laisserait le titre de la section sous le bandeau collant.
 */
export function useHauteurPubliee() {
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
      <Identite nom={analyse.portfolio.name} />

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

      {/* La valeur, puis les deux réglages. À 390 px, la ligne de la valeur et
          du thème est pleine : le bouton de langue passe sous la valeur, à
          côté du thème, et le bandeau ne gagne pas en hauteur (§8.1). */}
      <div className={`${styles.total} ${styles.avecMontant}`}>
        <span className={styles.montant}>
          {montant(analyse.total_value, analyse.valuation.currency)}
        </span>
        <span className={styles.langue}>
          <BoutonLangue />
        </span>
        <span className={styles.theme}>
          <ThemeToggle />
        </span>
      </div>
    </header>
  )
}
