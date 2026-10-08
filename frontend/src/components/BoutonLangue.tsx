/**
 * Le bouton de langue (chantier 7D) — DESIGN.md §8.1 et §15.
 *
 * COMME LA BASCULE DE THÈME, IL DIT CE QUE LE CLIC FAIT : « English » sur la
 * page française, « Français » sur la page anglaise, chaque nom dans sa
 * propre langue. Pas d'état sous le libellé : la page elle-même dit dans
 * quelle langue on est.
 *
 * L'attribut `lang` du bouton est celui de la langue visée, pour qu'un
 * lecteur d'écran prononce juste « English ». Le nom accessible commence par
 * le libellé visible (WCAG 2.5.3) et le complète, dans la langue de la page :
 * « English (le site passe en anglais) ». Le complément est du texte caché,
 * pas un `aria-label`, parce qu'un `aria-label` ne peut pas changer de langue
 * en cours de route.
 */
import { NOMS_DES_LANGUES } from '../contenu/libelles'
import { ATTRIBUT_LANG, autreLangue, useLangue } from '../lib/langue'
import styles from './BoutonLangue.module.css'

export function BoutonLangue() {
  const { langue, changerLangue, libelles } = useLangue()
  const cible = autreLangue(langue)
  return (
    <button
      type="button"
      className={styles.bouton}
      lang={ATTRIBUT_LANG[cible]}
      onClick={() => changerLangue(cible)}
    >
      {NOMS_DES_LANGUES[cible]}
      <span className="visuellement-cache" lang={ATTRIBUT_LANG[langue]}>
        {` ${libelles.langue.explication}`}
      </span>
    </button>
  )
}
