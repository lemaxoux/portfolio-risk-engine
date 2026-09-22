/**
 * Un refus de l'API, rendu tel qu'il a été écrit — DESIGN.md §13, §15.
 *
 * « Une erreur ne s'excuse pas et n'est jamais vague. » Le composant n'ajoute
 * ni « Oups », ni « Une erreur est survenue », ni icône d'alerte : le message
 * du moteur dit déjà ce qui a échoué ET l'action suivante, ce qu'aucune
 * formule d'excuse ne remplace.
 *
 * La seule mise en forme est typographique : la commande sort du texte courant
 * pour aller dans un bloc de code, où elle se sélectionne d'un geste et ne se
 * coupe pas en fin de ligne. C'est le seul endroit de l'interface où le
 * monospace est autorisé — du contenu réellement code (§6.1).
 */
import type { ApiErreur } from '../api/client'
import styles from './MessageErreur.module.css'

export function MessageErreur({ erreur }: { erreur: ApiErreur }) {
  return (
    <div className={styles.bloc} role="alert">
      <p className={styles.phrase}>
        {erreur.segments.map((segment, index) =>
          segment.genre === 'commande' ? (
            <code key={index} className={styles.commande}>
              {segment.contenu}
            </code>
          ) : (
            <span key={index}>{segment.contenu}</span>
          ),
        )}
      </p>

      {erreur.problems.length > 0 && (
        <ul className={styles.problemes}>
          {erreur.problems.map((probleme, index) => (
            <li key={index}>
              {probleme.line !== null && `Ligne ${probleme.line} — `}
              {probleme.field !== null && `${probleme.field} : `}
              {probleme.problem}
              {probleme.value !== null && ` (« ${probleme.value} »)`}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
