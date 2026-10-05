/**
 * Le tableau éditable des positions — DESIGN.md §8.2, §9.3, §13.
 *
 * Une ligne par titre : ticker, nom, historique, quantité, prix de revient.
 * Le composant ne décide rien : il affiche les lignes qu'on lui donne, les
 * refus rangés à leur cellule, et remonte chaque frappe.
 *
 * ═══ SOUS 900 PX, LA QUANTITÉ D'ABORD ═══
 *
 * À 390 px, le cadre de 342 px ne montrait que le numéro, le ticker, le nom et
 * l'historique : la quantité, le seul autre champ à remplir, était hors de
 * l'écran. Sous 900 px, l'ordre devient ticker, quantité, puis nom,
 * historique, prix de revient — le même mécanisme que la section 1
 * (`useEtroit`), parce que le CSS ne déplace pas une cellule. L'ordre du DOM
 * suit, donc la tabulation aussi : ticker, quantité, prix.
 *
 * ═══ CHAQUE CHAMP EST NOMMÉ ═══
 *
 * Un champ de tableau n'a pas de libellé à côté de lui : c'est l'en-tête de
 * sa colonne et le numéro de sa ligne qui le nomment. `aria-labelledby` les
 * réunit — « Quantité, ligne 3 » —, sans libellé recopié à la main. Un refus
 * s'affiche sous son champ, lui est relié par `aria-describedby`, et le champ
 * porte `aria-invalid` : le contour épaissi n'est jamais le seul signe.
 *
 * ═══ QUAND UN REFUS APPARAÎT ═══
 *
 * À la sortie du champ, pas pendant la frappe : on ne reproche pas un nombre
 * qu'on est en train d'écrire. Il disparaît dès la frappe suivante.
 */
import { Fragment, type ReactNode } from 'react'

import { segmenter } from '../api/client'
import type { Security } from '../api/types'
import { dateISO } from '../lib/format'
import { useEtroit } from '../lib/largeur'
import { Absent } from './Absent'
import type { Champ, LigneSaisie } from '../lib/saisie'
import { titreDe } from '../lib/univers'
import controles from '../styles/controles.module.css'
import styles from './TableauSaisie.module.css'

/** La clé d'un refus : numéro de ligne affiché et champ. */
export function cleDeRefus(ligne: number, champ: Champ): string {
  return `${ligne}:${champ}`
}

type Saisissable = 'ticker' | 'quantite' | 'prixRevient'

/** Les colonnes de données, entre le numéro de ligne et « Retirer ». */
export type ColonneSaisie = 'ticker' | 'nom' | 'historique' | 'quantite' | 'prix'

export const ORDRE_LARGE: readonly ColonneSaisie[] = ['ticker', 'nom', 'historique', 'quantite', 'prix']

/** Sous 900 px : les deux champs à remplir d'abord, le contexte ensuite. */
export const ORDRE_ETROIT: readonly ColonneSaisie[] = ['ticker', 'quantite', 'nom', 'historique', 'prix']

export function ordreDesColonnes(etroit: boolean): readonly ColonneSaisie[] {
  return etroit ? ORDRE_ETROIT : ORDRE_LARGE
}

const CHAMP_DE: Record<Saisissable, Champ> = {
  ticker: 'ticker',
  quantite: 'quantity',
  prixRevient: 'cost_basis',
}

interface Props {
  readonly legende: string
  readonly lignes: readonly LigneSaisie[]
  readonly refus: ReadonlyMap<string, string>
  readonly univers: ReadonlyMap<string, Security> | null
  readonly devise: string
  readonly modifier: (rang: number, champ: Saisissable, valeur: string) => void
  readonly quitter: (rang: number, champ: Saisissable) => void
  readonly retirer: (rang: number) => void
}

export function TableauSaisie({
  legende,
  lignes,
  refus,
  univers,
  devise,
  modifier,
  quitter,
  retirer,
}: Props) {
  const ordre = ordreDesColonnes(useEtroit())
  const champ = (ligne: LigneSaisie, rang: number, cle: Saisissable, colonne: string) => {
    const numero = rang + 1
    const id = `${cle}-${ligne.cle}`
    const message = refus.get(cleDeRefus(numero, CHAMP_DE[cle]))
    const nombre = cle !== 'ticker'
    return (
      <>
        <input
          id={id}
          name={`${cle}-${numero}`}
          className={`${controles.saisie} ${nombre ? styles.saisieNombre : styles.saisieTicker}`}
          value={ligne[cle]}
          aria-labelledby={`${colonne} saisie-rang-${ligne.cle}`}
          aria-invalid={message !== undefined ? true : undefined}
          aria-describedby={message !== undefined ? `${id}-refus` : undefined}
          autoComplete="off"
          spellCheck={false}
          {...(nombre
            ? { inputMode: 'decimal' as const }
            : { list: 'saisie-univers', autoCapitalize: 'characters', maxLength: 20 })}
          onChange={(evenement) => modifier(rang, cle, evenement.target.value)}
          onBlur={() => quitter(rang, cle)}
        />
      </>
    )
  }

  /**
   * Les refus d'une ligne, dans une rangée PLEINE LARGEUR sous elle : un
   * refus du serveur peut être long (« XYZ n'est pas un titre connu. Titres
   * disponibles : … »), et coincé dans sa colonne il étirerait la ligne sur
   * dix. Chaque
   * message garde l'identifiant que son champ cite dans `aria-describedby`.
   * Une commande à lancer sort du texte, en code (§6.1).
   */
  const refusDeLaLigne = (ligne: LigneSaisie, rang: number) => {
    const numero = rang + 1
    const messages = (Object.keys(CHAMP_DE) as Saisissable[]).flatMap((cle) => {
      const message = refus.get(cleDeRefus(numero, CHAMP_DE[cle]))
      return message === undefined ? [] : [{ id: `${cle}-${ligne.cle}-refus`, message }]
    })
    if (messages.length === 0) return null
    return (
      <tr className={styles.rangeeRefus}>
        <td colSpan={7} className={styles.celluleRefus}>
          {messages.map(({ id, message }) => (
            <p key={id} id={id} className={controles.refus}>
              {segmenter(message).map((segment, index) =>
                segment.genre === 'texte' ? (
                  <span key={index}>{segment.contenu}</span>
                ) : (
                  <code key={index} className={styles.commande}>
                    {segment.contenu}
                  </code>
                ),
              )}
            </p>
          ))}
        </td>
      </tr>
    )
  }

  const entete = (cle: ColonneSaisie): ReactNode => {
    switch (cle) {
      case 'ticker':
        return (
          <th key={cle} scope="col" id="saisie-col-ticker" className={styles.entete}>
            Ticker
          </th>
        )
      case 'nom':
        return (
          <th key={cle} scope="col" className={styles.entete}>
            Nom
          </th>
        )
      case 'historique':
        return (
          <th key={cle} scope="col" className={styles.entete}>
            Historique depuis
          </th>
        )
      case 'quantite':
        return (
          <th key={cle} scope="col" id="saisie-col-quantite" className={`${styles.entete} ${styles.nombre}`}>
            Quantité
          </th>
        )
      case 'prix':
        return (
          <th key={cle} scope="col" id="saisie-col-prix" className={`${styles.entete} ${styles.nombre}`}>
            Prix de revient ({devise}), facultatif
          </th>
        )
    }
  }

  return (
    <>
      <div className={styles.cadre}>
        <table className={styles.tableau}>
          <caption className={styles.legende}>{legende}</caption>
          <thead>
            <tr>
              <th scope="col" className={`${styles.entete} ${styles.numero}`}>
                N°
              </th>
              {ordre.map((cle) => entete(cle))}
              <th scope="col" className={styles.entete}>
                <span className="visuellement-cache">Retirer</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {lignes.map((ligne, rang) => {
              const titre = titreDe(univers, ligne.ticker)
              const tape = ligne.ticker.trim() !== ''
              return (
                <Fragment key={ligne.cle}>
                <tr className={styles.rangee}>
                  <th scope="row" id={`saisie-rang-${ligne.cle}`} className={`${styles.cellule} ${styles.numero} ${styles.surLeChamp}`}>
                    <span className="visuellement-cache">ligne </span>
                    {rang + 1}
                  </th>
                  {ordre.map((cle) => {
                    switch (cle) {
                      case 'ticker':
                        return (
                          <td key={cle} className={styles.cellule}>
                            {champ(ligne, rang, 'ticker', 'saisie-col-ticker')}
                          </td>
                        )
                      case 'nom':
                        return (
                          <td key={cle} className={`${styles.cellule} ${styles.nom} ${styles.surLeChamp}`}>
                            {titre !== undefined ? (
                              titre.name
                            ) : tape && univers !== null ? (
                              'Titre inconnu'
                            ) : (
                              <Absent />
                            )}
                          </td>
                        )
                      case 'historique':
                        return (
                          <td key={cle} className={`${styles.cellule} ${styles.date} ${styles.surLeChamp}`}>
                            {titre?.first_price_date != null ? (
                              dateISO(titre.first_price_date)
                            ) : (
                              <Absent />
                            )}
                          </td>
                        )
                      case 'quantite':
                        return (
                          <td key={cle} className={`${styles.cellule} ${styles.nombre}`}>
                            {champ(ligne, rang, 'quantite', 'saisie-col-quantite')}
                          </td>
                        )
                      case 'prix':
                        return (
                          <td key={cle} className={`${styles.cellule} ${styles.nombre}`}>
                            {champ(ligne, rang, 'prixRevient', 'saisie-col-prix')}
                          </td>
                        )
                    }
                  })}
                  <td className={`${styles.cellule} ${styles.surLeChamp}`}>
                    <button type="button" className={controles.discret} onClick={() => retirer(rang)}>
                      Retirer<span className="visuellement-cache"> la ligne {rang + 1}</span>
                    </button>
                  </td>
                </tr>
                {refusDeLaLigne(ligne, rang)}
                </Fragment>
              )
            })}
          </tbody>
        </table>
      </div>
      {univers !== null && (
        <datalist id="saisie-univers">
          {[...univers.values()].map((titre) => (
            <option key={titre.ticker} value={titre.ticker}>
              {titre.name}
            </option>
          ))}
        </datalist>
      )}
    </>
  )
}
