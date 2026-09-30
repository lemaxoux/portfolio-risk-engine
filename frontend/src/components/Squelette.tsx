/**
 * État EN COURS — la forme de ce qui arrive, pas un rond qui tourne (§13).
 *
 * Sans animation : §10 interdit tout mouvement au chargement, et une pulsation
 * sur des blocs vides est le marqueur d'interface générée le plus
 * reconnaissable. Masqué aux lecteurs d'écran : la page porte `aria-busy`, et
 * des blocs vides n'ont rien à dire.
 */
import styles from './Squelette.module.css'

/** Des rangées de tableau, à leur hauteur de 36 px (§9.3). */
export function SqueletteTableau({ rangees = 4 }: { rangees?: number }) {
  return (
    <div className={styles.squelette} aria-hidden="true">
      <span className={styles.titre} />
      <div className={styles.tableau}>
        <span className={styles.entete} />
        {Array.from({ length: rangees }, (_, rang) => (
          <span key={rang} className={styles.rangee} />
        ))}
      </div>
    </div>
  )
}

/** Un titre de section et deux blocs mesure. */
export function SqueletteAnalyse() {
  return (
    <div className={styles.squelette} aria-hidden="true">
      <span className={styles.titre} />
      <div className={styles.blocs}>
        <span className={styles.bloc} />
        <span className={styles.bloc} />
      </div>
    </div>
  )
}
