-- Mx Risk MGT — schéma SQLite (v1)
--
-- Conventions :
--   * les dates sont stockées en TEXT au format ISO-8601 'YYYY-MM-DD'.
--     SQLite n'a pas de type date natif ; l'ordre lexicographique de ce
--     format est l'ordre chronologique, les comparaisons restent donc justes.
--   * les montants sont des REAL (précision suffisante pour du calcul de
--     risque ; ce n'est pas un livre comptable).

PRAGMA foreign_keys = ON;

-- Univers de titres suivis (actions / ETF cotés US en v1).
--
-- sector est nullable à dessein : le secteur n'est pas toujours disponible au
-- moment de l'insertion d'un titre, et l'ingestion des prix ne doit pas échouer
-- pour une donnée descriptive manquante. Il sert au flag de concentration
-- sectorielle (Phase 6), qui devra donc traiter le cas NULL explicitement
-- plutôt que de supposer la colonne renseignée.
-- NOT NULL sur ticker n'est pas redondant avec PRIMARY KEY : SQLite accepte
-- NULL dans une clé primaire non-INTEGER (bug historique conservé pour
-- compatibilité). Sans cette contrainte, un ticker manquant à l'ingestion
-- s'insérerait silencieusement au lieu d'échouer.
CREATE TABLE IF NOT EXISTS securities (
    ticker TEXT PRIMARY KEY NOT NULL,
    name   TEXT NOT NULL,
    sector TEXT
);

-- Historique quotidien. adj_close est ajusté des splits ET des dividendes :
-- c'est la seule colonne à utiliser pour calculer des rendements, close brut
-- fausserait les séries à chaque détachement.
CREATE TABLE IF NOT EXISTS prices (
    ticker    TEXT    NOT NULL,
    date      TEXT    NOT NULL,
    open      REAL,
    high      REAL,
    low       REAL,
    close     REAL    NOT NULL,
    adj_close REAL    NOT NULL,
    volume    INTEGER,
    PRIMARY KEY (ticker, date),
    FOREIGN KEY (ticker) REFERENCES securities(ticker) ON DELETE CASCADE
);

-- La clé primaire (ticker, date) rend l'ingestion idempotente : un
-- INSERT OR REPLACE re-joue un backfill sans créer de doublons.
CREATE INDEX IF NOT EXISTS idx_prices_date ON prices(date);

-- Un portefeuille = un ensemble de positions appartenant à quelqu'un.
--
-- `name` est le libellé affiché ; `owner` reste l'identité du propriétaire et ne
-- doit pas être détourné pour tenir lieu de nom — l'application est
-- mono-utilisateur en v1 ('local'), elle ne le sera pas forcément toujours.
--
-- `updated_at` date le dernier REMPLACEMENT DES POSITIONS, pas la création de
-- l'enregistrement : c'est la fraîcheur des positions qui informe, pas l'âge de
-- la ligne. Il reste NULL tant que les positions n'ont pas été écrites par
-- l'application, ce qui se lit « jamais modifié depuis » — et non une date de
-- modification qu'on ne connaît pas.
--
-- L'ordre des colonnes reproduit celui qu'obtient une base migrée (ALTER TABLE
-- ADD COLUMN ajoute en fin de table) : une base neuve et une base migrée doivent
-- être indiscernables, sinon les tests ne valident pas la base réellement
-- utilisée. Voir backend/db/migrate.py.
CREATE TABLE IF NOT EXISTS portfolios (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    owner      TEXT    NOT NULL,
    name       TEXT    NOT NULL DEFAULT 'Portefeuille',
    updated_at TEXT
);

-- cost_basis est le prix de revient unitaire, optionnel : il ne sert pas au
-- calcul du risque (qui ne dépend que des poids et des rendements), seulement
-- à afficher une P&L si la donnée est disponible.
CREATE TABLE IF NOT EXISTS positions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id INTEGER NOT NULL,
    ticker       TEXT    NOT NULL,
    quantity     REAL    NOT NULL,
    cost_basis   REAL,
    UNIQUE (portfolio_id, ticker),
    FOREIGN KEY (portfolio_id) REFERENCES portfolios(id) ON DELETE CASCADE,
    FOREIGN KEY (ticker)       REFERENCES securities(ticker)
);
