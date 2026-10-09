/**
 * Les types de ce que le build emploie du paquet `hyphen` (dépendance de
 * développement, `coupuresAuBuild.ts`). Le paquet n'en publie pas ; une
 * dépendance de types en plus n'aurait servi qu'à ces trois déclarations.
 */
declare module 'hyphen' {
  interface OptionsDeCoupure {
    /** Le caractère posé à chaque coupure ; U+00AD par défaut. */
    readonly hyphenChar?: string
    /** Les coupures données à la main, en forme `ar-ranged`. */
    readonly exceptions?: readonly string[]
    /** Un mot plus court ne se coupe pas ; 5 par défaut. */
    readonly minWordLength?: number
    /** Sauter les balises HTML ; `true` par défaut. */
    readonly html?: boolean
  }

  /** Rend la fonction, synchrone, qui coupe un texte selon les motifs donnés. */
  export default function creerCoupeur(motifs: unknown, options?: OptionsDeCoupure): (texte: string) => string
}

declare module 'hyphen/patterns/fr' {
  const motifs: unknown
  export default motifs
}

declare module 'hyphen/patterns/en-us' {
  const motifs: unknown
  export default motifs
}
