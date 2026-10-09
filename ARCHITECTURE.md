# Architecture

This document is for a developer who opens the code. It records the
decisions behind the structure and the reason for each, and names what
verifies it: a test, or nothing when the decision rests on convention. It does
not repeat what the code shows.

The code, its comments and docstrings, the tests, `CLAUDE.md`, and
`frontend/DESIGN.md` (the visual specification) are written in French. This
document, [README.md](README.md), and [METHODOLOGY.md](METHODOLOGY.md) are the
English reference. The measures themselves, their formulas and their limits,
are in METHODOLOGY.md.

## Stack

| Component | Choice | Why |
|---|---|---|
| Language | Python 3.12 | the quantitative ecosystem: numpy, pandas, scipy |
| API | FastAPI and uvicorn | light and typed, with an OpenAPI schema generated from the response models |
| Database | SQLite | a single-user, local tool: no server to run |
| Market data | Tiingo, behind one adapter | a long adjusted daily history; a change of provider rewrites one module |
| Client | Vite, React, TypeScript | read-mostly views with no server rendering and no search indexing: a meta-framework would add a toolchain for nothing |
| Styles | CSS Modules and CSS variables | a small set of tokens (DESIGN.md), which a utility framework would erode |
| Charts | Observable Plot | declarative marks, no imposed look, fixed domains |
| API types | openapi-typescript | generated from a committed schema, never written by hand |
| Tests | pytest, Vitest | the risk engine first |

Versions are pinned on both sides (`requirements.txt`, `requirements-dev.txt`,
`frontend/package-lock.json`).

## Module boundaries

| Module | Responsibility | What verifies it |
|---|---|---|
| `backend/data_provider` | the only module that talks to the price provider: addresses, JSON fields, retries | `tests/test_frontiere_fournisseur.py` |
| `backend/ingestion` | backfill, refresh, single additions, status, rebuild; writes prices and computes no risk | `tests/test_ingestion.py`, on doubles of the provider |
| `backend/risk_engine` | pure functions in `measures`, `covariance`, `var`, `returns`, `stress`, `regime`; `portfolio` reads SQLite; `engine` composes and attaches its window to every result | tests on synthetic data with known results, and identities held to floating-point tolerance |
| `backend/rules` | reads the results of the engine and turns them into findings; imports no calculation module | `test_le_moteur_de_regles_n_importe_aucun_module_de_calcul` |
| `backend/textes` | writes every published sentence, one module per language and per domain; the engine and the rules decide which sentence; may read the constants and pure helpers of `risk_engine.config`, nothing else from the engine | `tests/test_textes_symetriques.py` |
| `backend/api` | HTTP only: no arithmetic, no SQL, no `asdict`, no `exclude_none`; imports only types from the calculation modules | `tests/test_api_discipline.py` |
| `backend/db` | schema, initialization, explicit migrations, writes of user data | `tests/test_db_schema.py`, `tests/test_db_migration.py` |
| `backend/typography.py`, `frontend/src/lib/format.ts` | the only places that write a number | `tests/test_nombres_publies.py`, `tests/test_typographie_partagee.py` |
| `frontend/src` | composes the page from published fields and computes no measure | convention, no test; colors and font sizes: `tokens.test.ts` |

## The API computes nothing

Every number in a response comes from an attribute, a property, or a method of
the engine, which has its own tests. A missing value is added to the engine
with its test, then to the schema.

`tests/test_api_discipline.py` reads the syntax tree of every module under
`backend/api/` and fails on the four operations, the power, the modulo, the
augmented assignments, `round()`, `abs()`, and the negation of a value. The
negation matters: `-result.value` is exactly the sign change that turns a VaR,
a positive loss, into a negative return that reads as a gain, and no test of
values would notice. The same file refuses SQL in the API layer,
`dataclasses.asdict()`, which silently drops properties and methods (the gap
between a crisis and the calm beta, the caveat of the 99% CVaR), and
`response_model_exclude_none`, which would remove exactly the field that
explains a blank. The detection is a function exercised on samples that it
catches and samples that it leaves alone: a guard never seen failing proves
nothing.

A rule written in a document is bypassed without noise; a test is not.

## Provenance

Every result carries its window (sessions requested, sessions obtained, first
and last session), its valuation date, its method, and its number of
observations. There is no window at the level of the document: each measure
keeps its own, and only the requested window appears at the top, under
`parameters`. The banner reads `estimation_window`, the window of the panel of
ordinary times, published under its own name, so that the client never
promotes the window of one measure to the whole page.

- `as_of` is never invented. In `/api/meta`, it is the last session in the
  database; in an analysis, the earliest of the holdings' last closes. Neither
  is the date of the request.
- Thresholds are readable by a machine: `kind` (`chosen`, `derived`,
  `portfolio_relative`) and `role` (`threshold`, `reference`). The client marks
  a threshold chosen by hand from these fields, without searching the wording.
- The refusal lives in the measure, not only in a sentence. Below 3 sessions,
  the correlation matrix, the beta, and the contributions to variance are
  `null`, each with its reason. A rules engine that declined to comment on
  values still published would protect nothing: the charts read the values,
  not the sentences.
- An undefined value says so: `null` and a reason, never a missing field.
- No NaN and no Infinity: the schemas refuse them at construction, naming the
  field, and a test rereads the bytes of a real response with a strict parser.
- Matrices carry their labels, `tickers` and `values`, and the same list orders
  the weights and the contributions: the alignment cannot be missed.
- The CVaR keeps two sign conventions on purpose: `value` is a positive loss,
  `threshold` the raw quantile of returns, negative. The OpenAPI description
  says so, and a test holds the threshold equal to the opposite of the
  historical VaR of the same level. Changing the sign in the API would be
  arithmetic.
- `limiting_positions` names the holding that shortens the window only when its
  first session is exactly the first session of the aligned panel; otherwise
  the list is empty, rather than blaming the wrong holding.
- A crisis is three required fields of one object: the figure at the market
  low, the worst point along the way, and the coverage.

Checked by `tests/test_api_analysis.py`, `tests/test_series_publiees.py`, and
`tests/test_valorisation_publiee.py`.

## Two sample-size regimes

The check reads `window.observations`, the sessions actually used, in the
engine and in the rules, never the requested window. The API sets a floor of
60 sessions on the requested window (`MIN_REGRESSION_OBSERVATIONS`), but the
floor is not the protection: the aligned panel shrinks to the intersection of
dates, and one recently listed holding brings a request of 504 sessions down to
a few dozen. Below 3 sessions, the identities are refused; up to 60 sessions,
the figures are given and flagged; below 30 sessions, the volatility and the
normal VaR carry a caveat. The algebra is in METHODOLOGY.md, “Two sample-size
regimes” and “Where refusal stops”.

The normal Monte Carlo and the Student's t part are computed separately, each
with its own reason (`monte_carlo_unavailable_reason`,
`student_unavailable_reason`): a singular covariance and a short series are two
facts, and one does not hide the other.

Checked by `tests/test_rules.py`, `tests/test_risk_engine.py`, and
`tests/test_api_analysis.py`.

## One analysis, one response

The risk report, the crisis replays, the regime comparisons, the findings, and
the acceptance text come from one call, `GET /api/portfolios/{id}/analysis`.
Two calls separated by a refresh of the database would describe two states,
each correct and the whole wrong, and nothing in the responses would say so.
One response gives one `as_of` for the page. The simulations are cheap enough
on a portfolio of a few holdings that splitting the call would gain nothing.

## Errors and refusals

- 404: the portfolio does not exist, which is checked by an explicit read,
  never by searching a message.
- 409: it exists but cannot be analyzed in its present state: no position, no
  price for a holding, no benchmark, too short a common history. It is a state
  of the database, not a fault of the request.
- 422: the request itself is refused: an unknown ticker, a negative quantity, a
  duplicate, an unreadable file, a parameter out of range.

The engine's messages are relayed word for word: `PortfolioError` already
carries the command to run, and a generic server error would replace an
instruction with an admission of helplessness. A refusal always has the same
body, FastAPI's validation errors included: `detail`, then `problems`, each
with the line number the user sees (`line`). Nothing is written until
everything is valid: the problems are gathered and returned together, since an
import applied halfway would give a plausible and false valuation. An error is
written where it is caught: the errors that a successful response can publish
as a reason carry the name of their text function and its arguments, and the
route writes them in the language of the response.

Checked by `tests/test_api_portfolios.py` and `tests/test_api_csv.py`.

## CSV import

- The file is the portfolio: an import replaces every position, like
  `PUT /api/portfolios/{id}/positions`. An import that added positions would
  double the quantities at each upload of the same file.
- “A CSV file” is not a format. The reader deduces the encoding, the field
  separator, and the decimal separator from the bytes, and returns what it
  observed as provenance (`source`), not what it would have accepted.
- A number follows a grammar, not `float()`: an optional sign, digits, at most
  one decimal separator followed by digits. The client's reader applies the
  same expression, and one shared list of cases
  (`frontend/src/lib/nombres-saisis.json`) is read by both test suites.
- A non-empty column beyond the header is refused, never ignored: with a comma
  as field separator, a decimal comma cuts a number in two.
- The format shown on screen is published by the reader itself
  (`GET /api/csv-format`): a copy in the client would become the displayed
  format the day the reader changed.

Checked by `tests/test_api_csv.py` and `tests/test_nombres_saisis.py`.

## Two languages

Every route that publishes text takes `?lang=fr` or `?lang=en`. Without it, or
with `lang=fr`, each response is the French of before the English version, byte
for byte; any other value is refused. There is no `Accept-Language`: the
browser sends it on its own, and a response would change language without
anyone asking.

The server's sentences live in `backend/textes/fr/` and `backend/textes/en/`,
one module per domain, with the same names and the same signatures. The
engine, the rules, and the API layer decide (which variant, which sign); these
modules write. A sentence is added in both languages, with its cases in
`tests/test_textes_symetriques.py`. A translation loses, adds, or changes no
number: every text function, threshold line, and finding says the same numbers
in both languages once they are brought to a common writing.

The English acceptance text has its own fingerprint: a visitor who switches to
English accepts it once, and the French acceptance stays valid. The English is
American English with Chicago punctuation and no contraction; a sentence about
the replayed past says “would have” unless it carries its own frame, such as
“Over the past two years”.

Checked by `tests/test_textes_symetriques.py`, `tests/test_langue_api.py`, and
`tests/test_reponses_anglaises.py`.

### What stays in French

Declared, and checked by `tests/test_reponses_anglaises.py`
(`MODULES_RESTES_EN_FRANCAIS`):

- the internal guards of the engine, which the API triggers only on a corrupted
  database, keep their French message in both languages: those of `measures`,
  `covariance`, `stress`, `returns`, `regime`, `config`, `engine`, and
  `scenarios`, and the refusals of `var` that no response publishes;
- the internal message of the CSV reader, always caught and never published;
- the validation errors of FastAPI, written by pydantic, stay in English in
  both languages;
- the repository itself: the code, its comments and docstrings, the tests,
  `CLAUDE.md`, and `frontend/DESIGN.md`.

## One formatter on each side

Every number in a text published by the server goes through
`backend/typography.py`, and every number the client writes through
`frontend/src/lib/format.ts`. A component that formats a number on its own is
a bug waiting to happen.

- The characters are fixed, not left to `Intl`: the output of
  `Intl.NumberFormat` for French changed spaces between ICU versions, and Node
  and the browser ship different ones, so a test written against `Intl` would
  pass without proving anything. French uses a narrow no-break space (`U+202F`)
  for thousands and before the percent sign, a no-break space (`U+00A0`)
  between a number and what it counts, and the minus sign (`U+2212`); English
  uses a decimal point, a comma for thousands, nothing before the percent sign,
  and the same minus sign.
- One table of cases (`frontend/src/lib/typographie-partagee.json`) is read by
  `tests/test_typographie_partagee.py` and by `format.test.ts`: both halves
  write the same string for every case and every language. The Python suite
  holds it, because the server is the half that changes most.
- Published prose is composed once, at publication (`typography.prose`):
  no-break spaces before the high punctuation and inside quotation marks in
  French, and a word joiner (`U+2060`) after the dash of a pair and inside an
  ISO date, so that a line never breaks there. Data fields stay bare.
- No em dash in the interface, on either side (`tests/test_textes_publies.py`,
  `src/lib/ponctuation.test.ts`). No Greek letter outside the provenance of a
  measure: the serif face of the sentences has no Greek glyphs. A one-glyph
  font face (`tools/espace_fine.py`) draws the narrow no-break space that the
  serif face claims and lacks (DESIGN.md §6.3).

## Generated API types

`frontend/src/api/openapi.json` is committed, and `tests/test_openapi_schema.py`
compares it byte for byte with the schema that the application publishes: a
field added to a response model without regeneration fails the Python suite,
on the side that changed. `npm run api:types` derives `src/api/schema.ts` from
that file, not from a running server, so a build depends neither on a live
uvicorn nor on a fresh database, and a commit says which schema the client
compiled. The client never writes an API type by hand.

## Tests on a frozen database

`data/mx_risk.sqlite` is a living file: `refresh` adds sessions to it, and
`rebuild` rewrites it. A test that read it would check the state of the file,
not the code, and would fail the day after a refresh with no line changed.

- `tests/conftest.py` is the only access. It copies the database and truncates
  the copy at `DATE_GEL`, September 9, 2026. Three fixtures serve it: a
  read-only copy shared by the whole session, a copy of its own for a test that
  writes, and the analysis of the demonstration portfolio, computed once per
  session.
- `tests/test_gel_des_tests.py` reads the syntax tree of every test file and
  fails on any other opening of the real database. It is exercised by samples
  in both directions.
- The tests that need real prices are skipped when no local database exists.
  The others run offline: the HTTP session and the provider are replaced by
  doubles, and the test client of FastAPI talks to the application in memory.
- Every guard proves that it can fail: the discipline of the API layer, the
  text guards (`tests/gardes_texte.py`, exercised by
  `tests/test_gardes_texte.py`), and the closed lists of numbers of the
  methodology page (`tests/test_methodologie.py`) and of the public documents
  (`tests/test_documents_publics.py`).
- In the public documents, every number is a constant read from the code, a
  market fact of the crisis catalogue recomputed on the frozen copy, a declared
  fragment with its reason, or a figure of a dated result, inside its block. A
  figure that changes with the code or the data, such as a count of tests, a
  bundle size, or a VaR, has no place in them.

## Ingestion and the local database

- One adapter (`backend/data_provider/tiingo.py`) knows the provider:
  addresses, JSON fields, retries with backoff, `Retry-After` first. A failed
  security does not stop the others; an exhausted quota stops the run. The
  token goes in a header, never in an address.
- The history is anchored at a fixed date (METHODOLOGY.md, “An anchored
  history”), and `status` shows the coverage obtained for each security,
  without a network call.
- `refresh` catches up from the last stored session, which it rewrites, to the
  current day: the machine can stay off for days without leaving a gap. A
  fetched session that carries a dividend or a split triggers a full reload of
  the security. A failure gives a nonzero exit code, for a scheduler to see.
- There is no daemon: `refresh` is a command for the Windows Task Scheduler or
  for a person. A process kept alive on a laptop would cost more than the
  problem it solves.
- `rebuild` repairs a database written before the dividend fix, by an explicit
  command and never as a side effect. It checks the budget first (one call per
  security, nothing started above the provider's hourly limit,
  `HOURLY_CALL_BUDGET`), copies the database with the backup API of SQLite to a
  dated file that is never overwritten, then reloads and replaces the history
  of each security. Only the `prices` table is rewritten, which a test checks
  through the authorizer of SQLite (`test_rebuild_n_ecrit_que_dans_prices`).
- Four tables (`backend/db/schema.sql`): `securities`, `prices`, `portfolios`,
  `positions`. `adj_close` is the only column used for returns; the key
  `(ticker, date)` makes ingestion idempotent; `portfolios.updated_at` dates the
  positions, not the record, and `NULL` reads “never changed in the
  application”; dates are ISO text, whose lexicographic order is the
  chronological order.
- Schema changes are explicit, idempotent migrations
  (`python -m backend.db.migrate`). The API refuses to start on a database that
  is not migrated, naming the command, rather than failing at its first
  request.
- One SQLite connection per request, opened and closed by a dependency and
  never used by two threads at once. It is opened with
  `check_same_thread=False`, because FastAPI opens it, runs the route, and
  closes it on threads that can differ; without that, concurrent requests
  failed at random (`tests/test_api_dependencies.py`).

## Serving the application

`python -m backend.api` binds to the local loopback address, written in the
entry point rather than left to an option: the application has no
authentication and no notion of user, and a default that one argument can
contradict ends up contradicted. The interactive documentation of the API is
at `/docs`.

| Method | Path | Role |
|---|---|---|
| GET | `/api/meta` | the last session in the database, the size of the universe |
| GET | `/api/disclaimer` | the acceptance text, read before any portfolio exists |
| GET | `/api/csv-format` | the format that the CSV reader accepts |
| GET | `/api/securities` | the universe: ticker, name, sector, dates of the first and last price |
| POST, GET | `/api/portfolios` | create a portfolio; list the portfolios |
| GET, DELETE | `/api/portfolios/{id}` | read one portfolio; delete it with its positions |
| PUT | `/api/portfolios/{id}/positions` | replace every position |
| POST | `/api/portfolios/{id}/positions/csv` | import a CSV file |
| GET | `/api/portfolios/{id}/analysis` | the whole analysis, in one response |

In development, two processes: Vite serves the page and forwards `/api` to the
API. In production, FastAPI serves `frontend/dist`. In both cases the browser
sees a single origin, and the server has no CORS middleware: a permission that
production never uses is a permission that ends up widened. Without
`frontend/dist`, the application starts and serves the API alone, so the
Python suite runs on a machine without Node. The fallback to `index.html`
never masks the API: an unknown path under `/api` returns a JSON 404, not the
page (`tests/test_api_static.py`).

## The client

- Composing is not computing. The sentences under each measure cite only
  published fields (amounts, recovery date, worst session, benchmark
  volatility, period label, coverage verdict) and choose their wording only
  from the sign of a published field. A frequency (“one trading day in
  twenty”) comes from a table, not from a division (`src/lib/phrases.ts`,
  `phrases.test.ts`).
- Real addresses, read without a routing library (`src/lib/route.ts`); the
  fragments stay for the anchors. Internal links are real `<a href>` elements,
  so a middle click opens a tab.
- The list of portfolios is loaded once and reread after each write; each page
  learns there what it knows about a portfolio before any other call.
- One status region announces what an action just did; the focus follows the
  page; a guard keeps unsaved changes from being lost silently, and asks its
  question on the page itself.
- The input table is the portfolio: saving sends a `PUT` that replaces every
  position. The only local check is syntactic (does a typed number read?), and
  the server refuses the rest, line by line.
- The analysis has four states: empty, insufficient (for the page or for one
  measure), loading, and error (DESIGN.md §13).
- The acceptance screen is a full page, not a modal window. Its text comes from
  `GET /api/disclaimer`, and the acceptance is remembered under the fingerprint
  of the text, once per language: a reworded limitation brings the screen
  back.

## The methodology page

- A text of its own, written for a reader who starts from zero, not these
  documents rendered: one content file per language
  (`frontend/src/contenu/methodologie.fr.md`, `methodologie.en.md`), with the
  same anchors.
- A restricted Markdown, read by an in-house reader (`src/lib/contenu.ts`):
  headings with fixed anchors, paragraphs, lists, formulas, links to an anchor,
  and three entities. Anything else is an error, with its line. No dependency,
  and no injected HTML.
- Every number of the text is recomputed from the engine and compared, writing
  included (`tests/test_methodologie.py`). The characters are checked against a
  list established from the tables of the fonts (`methodologie.test.ts`), since
  the repository has no font reader.
- Hyphenation points are inserted at build time by a Vite plugin from the TeX
  patterns (`src/contenu/coupuresAuBuild.ts`). The sources stay unchanged, and
  neither the package nor the patterns reach the bundle.
- Each measure and each chart of the analysis links to its entry
  (`src/contenu/methodes.ts`). Coming back from the methodology gives the focus
  to the link followed, found by a key rather than by a scroll position.

## Accessibility

- The target is WCAG level AA (DESIGN.md §13).
- The provenance of a figure is never hidden: no tooltip, no accordion. The
  values of each chart are also given as a collapsed table, made of the
  published values in their published order, with no calculation and no
  selection (`valeurs.test.ts`).
- The keyboard reaches everything, and the focus is always visible, never
  hidden under the sticky banner: the page reserves the banner's height for
  what it scrolls. The banner sticks only above the layout breakpoint, since at
  high zoom it would cover the window. An anchor gives the focus to the heading
  it targets.
- Color never carries information alone: the analysis was captured in
  grayscale, and every value is also written. Contrast ratios are computed, not
  estimated (DESIGN.md §5).
- Text is justified only where a measurement showed that no line opens wide
  gaps, with or without a hyphenation dictionary (DESIGN.md §6.3).
- Still to be checked by people: a screen reader on the analysis and its
  collapsed tables, a real phone, and the copy and paste of the hyphenated
  methodology.

## Deliberate limits of the current version

- One user, on one machine, with no authentication.
- A short history truncates the window of every measure; excluding the holding
  and reweighting the others, with a declared coverage, is left for a later
  version.
- The bundle is not split; both methodology texts ship in it.
- No preview of an import: the API has no read without a write.
- One boundary rests on convention, not on a test: the client computes no
  measure.
