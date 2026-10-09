/**
 * Grille libellé / valeur — DESIGN.md §9.1 et §12.
 *
 * UNE GRILLE, PAS UNE CHAÎNE DE MÉTA. §12 interdit explicitement
 * « A · B · C » : une suite jointe par des points médians se lit d'un bout à
 * l'autre ou pas du tout, alors qu'une grille se balaye — l'œil descend la
 * colonne des libellés et s'arrête sur celui qu'il cherche.
 *
 * La provenance N'EST JAMAIS MASQUÉE : ni infobulle, ni accordéon, ni « voir
 * les détails ». Elle est dans le flux, en `--text-2` — jamais en
 * `--text-muted`. Il n'existe volontairement pas de troisième niveau de gris
 * pour le texte de contenu, précisément pour qu'on ne puisse pas effacer la
 * provenance en la grisant.
 *
 * ═══ LA DERNIÈRE PAIRE MÈNE À LA MÉTHODE (chantier 7E, §9.1) ═══
 *
 * « Méthodologie », puis un lien par entrée qui explique le bloc, le texte de
 * chacun étant le titre de son entrée, dans la langue de la page
 * (`contenu/methodes.ts`). C'est la seule paire qui ne vienne pas d'un champ
 * publié ; elle suit les lignes publiées, qu'elle ne remplace ni ne replie.
 */
import { Fragment } from 'react'

import { enSuite, titreDeLEntree, type Methode } from '../contenu/methodes'
import { cleDeRetour } from '../lib/focus'
import { useLangue } from '../lib/langue'
import { Lien } from './Lien'
import styles from './Provenance.module.css'

export interface LigneProvenance {
  readonly libelle: string
  readonly valeur: string
}

/** La paire « Méthodologie » : un lien par entrée, la clé de retour sur chacun. */
function PaireMethode({ methode }: { methode: Methode }) {
  const { langue, libelles } = useLangue()
  return (
    <div className={styles.ligne}>
      <dt className={styles.libelle}>{libelles.navigation.pages.methodologie}</dt>
      <dd className={styles.valeur}>
        {methode.ancres.map((ancre, rang) => {
          const titre = titreDeLEntree(ancre, langue)
          return (
            <Fragment key={ancre}>
              {rang > 0 && ', '}
              <Lien vers={`/methodologie#${ancre}`} retour={cleDeRetour(methode.bloc, ancre)}>
                {rang === 0 ? titre : enSuite(titre)}
              </Lien>
            </Fragment>
          )
        })}
      </dd>
    </div>
  )
}

/**
 * `disposition` : `grille` dans un bloc mesure, où les valeurs s'alignent d'un
 * bloc à l'autre ; `ligne` sous le titre d'un graphique, où les paires se
 * suivent comme chez FRED (§9.4). Dans les deux cas, chaque valeur garde son
 * libellé — ce n'est jamais une chaîne « A · B · C ».
 */
export function Provenance({
  lignes,
  disposition = 'grille',
  methode,
}: {
  lignes: readonly LigneProvenance[]
  disposition?: 'grille' | 'ligne'
  /** Le lien du bloc vers sa méthode : la dernière paire. */
  methode?: Methode
}) {
  return (
    <dl className={disposition === 'ligne' ? styles.enLigne : styles.grille}>
      {lignes.map((ligne) => (
        <div key={ligne.libelle} className={styles.ligne}>
          <dt className={styles.libelle}>{ligne.libelle}</dt>
          <dd className={styles.valeur}>{ligne.valeur}</dd>
        </div>
      ))}
      {methode !== undefined && <PaireMethode methode={methode} />}
    </dl>
  )
}
