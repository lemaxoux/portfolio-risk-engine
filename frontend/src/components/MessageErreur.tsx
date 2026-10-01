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
import type { ReactNode } from 'react'

import { segmenter, type ApiErreur } from '../api/client'
import styles from './MessageErreur.module.css'

/**
 * Un message du backend, découpé : la commande en bloc, à recopier ; un
 * littéral cité (« le séparateur `,` ») en code dans la ligne ; le reste en
 * texte.
 */
function Segments({ message }: { message: string }) {
  return (
    <>
      {segmenter(message).map((segment, index) =>
        segment.genre === 'commande' ? (
          <code key={index} className={styles.commande}>
            {segment.contenu}
          </code>
        ) : segment.genre === 'litteral' ? (
          <code key={index} className={styles.litteral}>
            {segment.contenu}
          </code>
        ) : (
          <span key={index}>{segment.contenu}</span>
        ),
      )}
    </>
  )
}

/**
 * `action` est l'ACTION SUIVANTE, quand l'interface en a une à offrir :
 * « Recharger » après un chargement échoué. Un message qui dit ce qui a
 * échoué sans dire quoi faire ensuite ne tient que la moitié de §13.
 *
 * UN REFUS UNIQUE NE S'ÉCRIT QU'UNE FOIS. L'API reprend alors le refus comme
 * détail (`_resume`) : la phrase porte son numéro de ligne, et la liste, qui
 * le répéterait, n'est pas affichée.
 */
export function MessageErreur({
  erreur,
  action,
}: {
  erreur: ApiErreur
  action?: ReactNode
}) {
  const [premier] = erreur.problems
  const unique =
    erreur.problems.length === 1 && premier !== undefined && premier.problem === erreur.detail
  return (
    <div className={styles.bloc} role="alert">
      <p className={styles.phrase}>
        {unique && premier.line !== null && `Ligne ${premier.line} — `}
        <Segments message={erreur.detail} />
      </p>

      {erreur.problems.length > 0 && !unique && (
        <ul className={styles.problemes}>
          {erreur.problems.map((probleme, index) => (
            <li key={index}>
              {probleme.line !== null && `Ligne ${probleme.line} — `}
              <Segments message={probleme.problem} />
            </li>
          ))}
        </ul>
      )}

      {action !== undefined && <div className={styles.action}>{action}</div>}
    </div>
  )
}
