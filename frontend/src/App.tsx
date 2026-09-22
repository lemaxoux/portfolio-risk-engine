/**
 * Coquille de l'application.
 *
 * Elle ne montre que ce qui est construit : ni section vide, ni texte
 * provisoire. Une section apparaît quand elle a quelque chose à dire.
 */
import { ThemeToggle } from './components/ThemeToggle'
import styles from './App.module.css'

export function App() {
  return (
    <>
      <a className={styles.evitement} href="#contenu">
        Aller au contenu
      </a>
      <header className={styles.bandeau}>
        <span className={styles.marque}>Mx Risk MGT</span>
        <ThemeToggle />
      </header>
      <main id="contenu" className={styles.contenu} />
    </>
  )
}
