/**
 * Section 1 — « Le portefeuille ». DESIGN.md §8.2, §9.3.
 *
 * Ce qu'on analyse, avant ce qu'on en dit : chaque ligne, sa quantité, son
 * prix, sa valeur, son poids. Tout vient de `analysis.valuation` — la MÊME
 * réponse que les mesures, donc le même état de la base.
 *
 * ═══ LA BARRE DE POIDS ═══
 *
 * Une barre dans la cellule, en `--series-1` : une seule série, une seule
 * teinte (§5.4) — le ticker est porté par la ligne, pas par la couleur. Son
 * échelle est FIXE, de 0 à 100 % de la cellule, et non étirée au poids le plus
 * lourd : une ligne à 25 % occupe le quart de sa piste dans tout portefeuille,
 * comme la carte de corrélation se lit sur un domaine fixe. Le chiffre est
 * écrit à côté ; la barre ne fait que le montrer.
 *
 * ═══ AUCUN TOTAL CALCULÉ ═══
 *
 * La ligne de pied porte `valuation.total_value`, publié. La somme des poids
 * n'est pas écrite : elle vaut 100 % par construction, et l'écrire serait soit
 * une affirmation que rien n'a testée, soit une addition faite ici.
 */
import type { Valuation, ValuedPosition } from '../api/types'
import { DataTable, type Colonne } from '../components/DataTable'
import { Provenance } from '../components/Provenance'
import { Section } from '../components/Section'
import commun from '../components/Section.module.css'
import { dateISO, decimal, decimalesDeColonne, pourcentage } from '../lib/format'
import styles from './SectionPortefeuille.module.css'

/** Plafond des décimales d'une quantité : des fractions d'action, au plus. */
const DECIMALES_QUANTITE_MAX = 4

function BarrePoids({ poids }: { poids: number }) {
  return (
    <span className={styles.poids}>
      <span className={styles.piste} aria-hidden="true">
        <span className={styles.barre} style={{ inlineSize: `${poids * 100}%` }} />
      </span>
      <span>{pourcentage(poids, 1)}</span>
    </span>
  )
}

export function colonnesDuPortefeuille(valorisation: Valuation): Colonne<ValuedPosition>[] {
  const devise = valorisation.currency
  const decimalesQuantite = decimalesDeColonne(
    valorisation.positions.map((ligne) => ligne.quantity),
    DECIMALES_QUANTITE_MAX,
  )
  return [
    {
      cle: 'ticker',
      titre: 'Ticker',
      nature: 'texte',
      cellule: (ligne) => ligne.ticker,
      tri: (ligne) => ligne.ticker,
    },
    {
      cle: 'nom',
      titre: 'Nom',
      nature: 'texte',
      cellule: (ligne) => ligne.name,
      tri: (ligne) => ligne.name,
    },
    {
      cle: 'quantite',
      titre: 'Quantité',
      nature: 'nombre',
      cellule: (ligne) => decimal(ligne.quantity, decimalesQuantite),
      tri: (ligne) => ligne.quantity,
    },
    {
      cle: 'prix',
      titre: `Prix (${devise})`,
      nature: 'nombre',
      cellule: (ligne) => decimal(ligne.price, 2),
      tri: (ligne) => ligne.price,
    },
    {
      cle: 'valeur',
      titre: `Valeur (${devise})`,
      nature: 'nombre',
      cellule: (ligne) => decimal(ligne.value, 2),
      tri: (ligne) => ligne.value,
    },
    {
      cle: 'poids',
      titre: 'Poids',
      nature: 'nombre',
      cellule: (ligne) => <BarrePoids poids={ligne.weight} />,
      tri: (ligne) => ligne.weight,
    },
  ]
}

export function SectionPortefeuille({ valorisation }: { valorisation: Valuation }) {
  return (
    <Section ancre="portefeuille" numero={1} titre="Le portefeuille">
      <div className={commun.conditions}>
        <Provenance
          disposition="ligne"
          lignes={[
            { libelle: 'Valorisé au', valeur: dateISO(valorisation.as_of) },
            { libelle: 'Prix', valeur: 'dernière clôture brute, non ajustée' },
            { libelle: 'Devise', valeur: valorisation.currency },
          ]}
        />
      </div>
      <DataTable
        legende="Positions détenues, valorisées à la dernière clôture"
        colonnes={colonnesDuPortefeuille(valorisation)}
        lignes={valorisation.positions}
        cleDeLigne={(ligne) => ligne.ticker}
        triInitial={{ cle: 'poids', sens: 'decroissant' }}
        pied={['Total', null, null, null, decimal(valorisation.total_value, 2), null]}
      />
    </Section>
  )
}
