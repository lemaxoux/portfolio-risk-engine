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
 * ═══ L'ORDRE DES COLONNES SUIT LA LARGEUR ═══
 *
 * En large, l'ordre de DESIGN.md §8.2 : ticker, nom, quantité, prix, valeur,
 * poids — la valeur se lit comme quantité × prix, le poids comme sa part.
 * Sous 900 px, le tableau défile dans son cadre, et cet ordre rejetait hors de
 * l'écran les deux colonnes les plus utiles : à 390 px, dans un cadre de
 * 342 px, Valeur commençait à 339 px et Poids à 428. L'ordre devient donc
 * ticker, valeur, poids, puis nom, quantité, prix. Les trois premières
 * tiennent en 304 px, sans défilement. Les trois autres ne sont pas masquées :
 * le cadre les fait défiler, la colonne du ticker restant en place.
 *
 * ═══ AUCUN TOTAL CALCULÉ ═══
 *
 * La ligne de pied porte `valuation.total_value`, publié. La somme des poids
 * n'est pas écrite : elle vaut 100 % par construction, et l'écrire serait soit
 * une affirmation que rien n'a testée, soit une addition faite ici.
 */
import type { Valuation, ValuedPosition } from '../api/types'
import { LIBELLES } from '../contenu/libelles'
import { DataTable, type Colonne } from '../components/DataTable'
import { Provenance } from '../components/Provenance'
import { Section } from '../components/Section'
import commun from '../components/Section.module.css'
import { METHODES } from '../contenu/methodes'
import { dateISO, decimal, decimalesDeColonne, pourcentage } from '../lib/format'
import { useLangue, type Langue } from '../lib/langue'
import { useEtroit } from '../lib/largeur'
import styles from './SectionPortefeuille.module.css'

/** Plafond des décimales d'une quantité : des fractions d'action, au plus. */
const DECIMALES_QUANTITE_MAX = 4

function BarrePoids({ poids, langue }: { poids: number; langue: Langue }) {
  return (
    <span className={styles.poids}>
      <span className={styles.piste} aria-hidden="true">
        <span className={styles.barre} style={{ inlineSize: `${poids * 100}%` }} />
      </span>
      <span>{pourcentage(poids, 1, langue)}</span>
    </span>
  )
}

/** Ordre des colonnes sous 900 px : ce qui compte d'abord, le détail ensuite. */
export const ORDRE_ETROIT = ['ticker', 'valeur', 'poids', 'nom', 'quantite', 'prix'] as const

export function colonnesDuPortefeuille(
  valorisation: Valuation,
  etroit = false,
  langue: Langue = 'fr',
): Colonne<ValuedPosition>[] {
  const titres = LIBELLES[langue].portefeuille.colonnes
  const devise = valorisation.currency
  const decimalesQuantite = decimalesDeColonne(
    valorisation.positions.map((ligne) => ligne.quantity),
    DECIMALES_QUANTITE_MAX,
  )
  const colonnes: Colonne<ValuedPosition>[] = [
    {
      cle: 'ticker',
      titre: titres.ticker,
      nature: 'texte',
      cellule: (ligne) => ligne.ticker,
      tri: (ligne) => ligne.ticker,
    },
    {
      cle: 'nom',
      titre: titres.nom,
      nature: 'texte',
      cellule: (ligne) => <span className={styles.nom}>{ligne.name}</span>,
      tri: (ligne) => ligne.name,
    },
    {
      cle: 'quantite',
      titre: titres.quantite,
      nature: 'nombre',
      cellule: (ligne) => decimal(ligne.quantity, decimalesQuantite, langue),
      tri: (ligne) => ligne.quantity,
    },
    {
      cle: 'prix',
      titre: titres.prix(devise),
      nature: 'nombre',
      cellule: (ligne) => decimal(ligne.price, 2, langue),
      tri: (ligne) => ligne.price,
    },
    {
      cle: 'valeur',
      titre: titres.valeur(devise),
      nature: 'nombre',
      cellule: (ligne) => decimal(ligne.value, 2, langue),
      tri: (ligne) => ligne.value,
    },
    {
      cle: 'poids',
      titre: titres.poids,
      nature: 'nombre',
      cellule: (ligne) => <BarrePoids poids={ligne.weight} langue={langue} />,
      tri: (ligne) => ligne.weight,
    },
  ]
  if (!etroit) return colonnes
  return ORDRE_ETROIT.map((cle) => colonnes.find((colonne) => colonne.cle === cle)!)
}

/** Le pied suit l'ordre des colonnes : « Total » sous le ticker, la valeur publiée sous la valeur. */
function piedDu(colonnes: Colonne<ValuedPosition>[], valorisation: Valuation, langue: Langue) {
  return colonnes.map((colonne) =>
    colonne.cle === 'ticker'
      ? LIBELLES[langue].portefeuille.total
      : colonne.cle === 'valeur'
        ? decimal(valorisation.total_value, 2, langue)
        : null,
  )
}

export function SectionPortefeuille({ valorisation }: { valorisation: Valuation }) {
  const { langue, libelles, phrases } = useLangue()
  const l = libelles.portefeuille
  const colonnes = colonnesDuPortefeuille(valorisation, useEtroit(), langue)
  const introduction = phrases.introPortefeuille(valorisation.as_of)
  return (
    <Section ancre="portefeuille" numero={1} titre={libelles.sections[0]} introduction={introduction}>
      <div className={commun.conditions}>
        <Provenance
          disposition="ligne"
          lignes={[
            { libelle: libelles.provenance.valoriseAu, valeur: dateISO(valorisation.as_of) },
            { libelle: l.prix, valeur: l.prixLu },
            { libelle: l.devise, valeur: valorisation.currency },
          ]}
          methode={{ bloc: 'portefeuille', ancres: METHODES.portefeuille }}
        />
      </div>
      <DataTable
        legende={l.legende}
        colonnes={colonnes}
        lignes={valorisation.positions}
        cleDeLigne={(ligne) => ligne.ticker}
        triInitial={{ cle: 'poids', sens: 'decroissant' }}
        pied={piedDu(colonnes, valorisation, langue)}
      />
    </Section>
  )
}
