/**
 * L'adresse du serveur public, que le build de démonstration reçoit de
 * `MX_RISK_SERVEUR_PUBLIC` (chantier 9.6, `vite.config.ts`). Vite la pose à la
 * place de `import.meta.env.MX_RISK_SERVEUR_PUBLIC` ; hors de ce build, elle
 * n'existe pas. `client.ts` est le seul module qui la lit.
 */
interface ImportMetaEnv {
  readonly MX_RISK_SERVEUR_PUBLIC?: string
}
