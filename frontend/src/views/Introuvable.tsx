/**
 * Les adresses qui ne mènent à rien — DESIGN.md §13 (état d'erreur).
 *
 * Ce qui a échoué et l'action suivante, dans la voix de l'interface : pas
 * d'excuse, pas de « oups ». Un portefeuille introuvable est reconnu à la
 * LISTE — il n'y figure pas —, sans attendre le 404 d'un appel d'analyse.
 */
import { BandeauSimple } from '../components/Bandeau'
import { Cadre } from '../components/Cadre'
import { Lien } from '../components/Lien'
import { cite } from '../lib/phrases'
import { cheminDe } from '../lib/route'
import styles from './Pages.module.css'

export function PageInconnue({ chemin }: { chemin: string }) {
  return (
    <Cadre titre="Page introuvable" page={chemin} entete={<BandeauSimple portefeuille={null} />}>
      <div className={styles.vide}>
        <h1 tabIndex={-1} className={styles.titre}>
          Aucune page à cette adresse
        </h1>
        <p className={styles.texte}>{cite(chemin)} ne correspond à aucune page de l'application.</p>
        <Lien vers={cheminDe({ vue: 'portefeuilles' })}>Voir les portefeuilles</Lien>
      </div>
    </Cadre>
  )
}

export function PortefeuilleIntrouvable({ id, page }: { id: number; page: string }) {
  return (
    <Cadre titre="Portefeuille introuvable" page={page} entete={<BandeauSimple portefeuille={null} />}>
      <div className={styles.vide}>
        <h1 tabIndex={-1} className={styles.titre}>
          Portefeuille introuvable
        </h1>
        <p className={styles.texte}>
          Aucun portefeuille ne porte le numéro {id}&nbsp;: il a peut-être été supprimé.
        </p>
        <Lien vers={cheminDe({ vue: 'portefeuilles' })}>Voir les portefeuilles</Lien>
      </div>
    </Cadre>
  )
}
