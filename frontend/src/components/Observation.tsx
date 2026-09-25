/**
 * `<Observation>` — ce que le moteur de règles affirme. DESIGN.md §9.2.
 *
 * « Les trois cas à distinguer visuellement — c'est le point le plus important
 * de tout ce document » :
 *
 * 1. Seuil DÉRIVÉ d'une référence calculée (ou relatif au portefeuille) — la
 *    ligne de seuil, sans point.
 * 2. Seuil CHOISI à la main — la même ligne, précédée du point `--caveat` et
 *    écrite en `--caveat`. La mention « choisi » reste dans la phrase, parce
 *    que c'est le backend qui l'y a mise.
 * 3. AUCUN seuil — AUCUNE ligne de seuil. Pas de « seuil : n/a » : ce serait
 *    effacer exactement la qualité qu'on veut rendre visible, une mesure qui
 *    parle d'elle-même.
 *
 * ═══ LE TEXTE EST CELUI DU BACKEND ═══
 *
 * `statement`, `threshold.rendered` et `provenance` sont affichés tels quels,
 * sans être reformulés : ce sont des phrases du moteur, composées en serif
 * pour les distinguer de ce que l'interface a mesuré (§6.1). Et la décision
 * d'afficher le point repose sur `kind`, un champ MACHINE — jamais sur la
 * présence du mot « CHOISI » dans le texte.
 */
import type { Observation as ObservationApi } from '../api/types'
import { Provenance } from './Provenance'
import styles from './Observation.module.css'

export function Observation({ observation }: { observation: ObservationApi }) {
  return (
    <article className={styles.observation}>
      <p className={styles.regle}>
        {observation.rule_label}
        <span className={styles.sujet}>{observation.subject}</span>
      </p>
      <p className={styles.phrase}>{observation.statement}</p>

      {observation.thresholds.map((seuil) => {
        const choisi = seuil.kind === 'chosen'
        return (
          <p
            key={seuil.name}
            className={choisi ? `${styles.seuil} ${styles.choisi}` : styles.seuil}
            data-seuil={seuil.kind}
          >
            {choisi && <span className={styles.point} aria-hidden="true" />}
            <span>
              <span className={styles.etiquette}>Seuil : </span>
              {seuil.rendered}
            </span>
          </p>
        )
      })}

      <Provenance lignes={[{ libelle: 'Provenance', valeur: observation.provenance }]} />
    </article>
  )
}
