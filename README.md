# Mx Risk MGT

A portfolio risk engine for US-listed stocks and ETFs, with an API and a web
interface, in English and in French, that shows every figure together with the
conditions it was estimated under: the window, the valuation date, the method,
and the number of trading days behind it.

It is written for two readers: an individual investor who starts from zero, for
whom the interface explains each measure in plain words, and a reader who wants
to check the calculation, for whom [METHODOLOGY.md](METHODOLOGY.md) gives every
formula. The code, its comments and docstrings, the tests, `CLAUDE.md`, and
`frontend/DESIGN.md` are written in French; README.md, METHODOLOGY.md, and
ARCHITECTURE.md are the English reference.

## What it does

For a portfolio entered by hand or imported from a CSV file, the analysis page
answers five questions, in order:

- **An ordinary day.** Historical and parametric value at risk (VaR) at 95% and
  99%, the average loss beyond it (CVaR), the volatility, a Student's t VaR next
  to the normal one, and the chart of daily returns.
- **At worst.** The maximum drawdown of the window, its dates, and the
  recovery.
- **What carries the risk.** Each holding's share of the variance against its
  share of the value, the effective number of holdings, and the correlation
  map.
- **In a crisis.** Three historical crises replayed on today's portfolio, each
  from the S&P 500's closing peak to its closing low, with the share of the
  value they cover, and the beta of ordinary times against the one measured in
  each crisis.
- **What the engine says.** Findings written by a rules engine from figures
  already calculated, each with its thresholds and where they come from.

Every figure carries its window (504 trading days by default, about two years),
its valuation date, its method, and its number of observations, in plain view.
Prices come from a local SQLite database that goes back to January 1, 2005. A
methodology page explains each measure to a reader who starts from zero.

The current version covers US stocks and ETFs, for one user, on one machine.

## What it refuses to do

- **No overall rating.** Folding a concentration, the share of the variance
  that follows the market, and the coverage of a crisis into one number would
  take a weighting that nothing justifies, and the number would look like
  advice without being advice.
- **It describes and never prescribes.** It knows neither the investment
  horizon, nor the objectives, nor the tax situation, nor the rest of the
  investor's wealth. It never tells anyone to buy, sell, or rebalance a holding.
  A lexical guard checks every published sentence.
- **It refuses a figure that no longer means what it says.** With two trading
  days, a correlation is +1 or −1 whatever the data: the tool withholds it and
  says why. Below 100 trading days, a historical VaR at 99% would only be the
  worst day of the window: withheld too. A figure that depends on the data
  poorly is given, and flagged.
- **It is not advice.** The figures describe the past and predict nothing.

## Results from the project

Four results, each tied to a portfolio, a valuation date, and a window, and
recomputed by the test suite on a copy of the database frozen at
September 9, 2026. The details are in
[METHODOLOGY.md](METHODOLOGY.md#dated-results).

<!-- dated: calm-beta -->
**The beta of ordinary times misses the crises.** Demonstration portfolio (AAPL
40, MSFT 25, JPM 60, JNJ 50, XOM 80, KO 120), valued on September 9, 2026, over
504 trading days, from September 5, 2024, to September 9, 2026: beta
0.57 ± 0.03. Replayed, the portfolio ends the 2008 Financial Crisis at −44.0%
where that beta implied −36.6%, the COVID Crash at −35.8% against −20.8%, and
the 2022 Monetary Tightening at −8.7% against −14.7%. The share of the variance
that follows the market rises from 0.49 to 0.86 and 0.79 in the two crises long
enough to conclude.
<!-- /dated -->

<!-- dated: concentration-2022 -->
**Concentration cuts both ways.** The same portfolio (AAPL 40, MSFT 25, JPM 60,
JNJ 50, XOM 80, KO 120), valued on September 9, 2026, over 504 trading days,
from September 5, 2024, to September 9, 2026: XOM is 15.8% of the value and
13.9% of the variance. In the 2022 Monetary Tightening, it adds +9.4 points
while the replayed portfolio ends at −8.7% and the S&P 500 at −24.5%.
<!-- /dated -->

<!-- dated: student-nu -->
**A misestimated ν looks reassuring.** The same portfolio (AAPL 40, MSFT 25,
JPM 60, JNJ 50, XOM 80, KO 120), valued on September 9, 2026, over 504 trading
days, from September 5, 2024, to September 9, 2026: maximum likelihood gives
ν = 4.07, while `scipy.stats.t.fit` with its default settings (SciPy 1.18.1)
stops at ν = 2.01, where the Student's t VaR at 99% would be 0.45%, against
1.95% under the normal distribution. A failed fit does not crash: it reassures.
<!-- /dated -->

<!-- dated: ko-dividend -->
**A false return at a dividend reload.** Security: KO alone, session of
September 9, 2026, the return since September 8, 2026. The true return is
−0.92%; the database stored −1.51% before the fix (backup of
September 28, 2026), because the provider had re-adjusted one close for a later
dividend and not the one before it. A dividend or a split now triggers a full
reload of the security's history.
<!-- /dated -->

<!-- screenshots -->

## Getting started

Prerequisites: Python 3.12, Node.js 24, and an API key from Tiingo for the
market data.

On Windows, in PowerShell, from the repository root:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-dev.txt     # the test suite only
copy .env.example .env                  # then set TIINGO_API_KEY in .env
python -m backend.db.init_db            # creates data/mx_risk.sqlite
python -m backend.ingestion backfill    # loads the development universe
cd frontend
npm ci
npm run build
cd ..
python -m backend.api                   # then open http://127.0.0.1:8000
```

On macOS or Linux, only two lines change:

```bash
source venv/bin/activate
cp .env.example .env
```

The backfill loads the 14 securities of the development universe, SPY
included, from January 1, 2005. Then, day to day:

```powershell
python -m backend.ingestion refresh     # catch up to the last session
python -m backend.ingestion add TSLA    # a security outside the universe
python -m backend.ingestion status      # what the database holds, offline
python -m backend.ingestion rebuild     # reload every history, after a backup
```

For development, `npm run dev` in `frontend/` serves the page with live reload
and forwards `/api` to the API running on the same machine.

## Tests

```powershell
python -m pytest              # from the repository root, offline
cd frontend
npm test                      # Vitest
npx tsc --noEmit -p .         # types
```

No test goes on the network: the provider and the HTTP session are replaced by
doubles. The tests that read real prices work on a copy of the local database
truncated at September 9, 2026, and are skipped when no local database exists.
Guards prove what the documentation claims: the API layer computes nothing,
every number of the methodology page and of these documents is recomputed from
the engine, and no published sentence prescribes.

## Project layout

```
backend/
  data_provider/   the only module that talks to the price provider
  ingestion/       backfill, refresh, rebuild, and the development universe
  risk_engine/     the measures, the crisis replays, the regime comparisons
  rules/           the rules engine: findings, thresholds, acceptance text
  textes/          every published sentence, in French and in English
  api/             FastAPI: serializes, computes nothing
  db/              SQLite schema, migrations, writes of user data
  typography.py    the only writer of numbers on the server
frontend/
  DESIGN.md        the visual specification, in French
  src/api/         the committed OpenAPI schema and the generated types
  src/lib/         format.ts, the only writer of numbers in the client
  src/contenu/     the methodology page, one file per language
  src/components/  the measure block, the provenance, the charts
  src/views/       the pages
tests/             pytest, on synthetic data and on a frozen copy of the database
tools/             the OpenAPI export and a one-glyph font generator
```

## Documentation

- [METHODOLOGY.md](METHODOLOGY.md): every measure with its formula, its
  assumptions, and its limitations, then the dated results; for the
  quantitative reader.
- [ARCHITECTURE.md](ARCHITECTURE.md): the design decisions and what verifies
  them; for the developer.
- The methodology page of the application, written for a reader who starts
  from zero:
  [frontend/src/contenu/methodologie.en.md](frontend/src/contenu/methodologie.en.md),
  which GitHub renders as it stands, or the `/methodologie` page of a local
  installation.
- [frontend/DESIGN.md](frontend/DESIGN.md): the visual specification, in
  French.

## How it was built

Built with Claude Code, Anthropic's coding agent, which wrote the code, the
tests, and most of this documentation. The author set the scope and the
methodological conventions, decided each trade-off, and had every phase
verified independently in a separate Claude session: test suites re-run on a
clean copy, published figures recomputed from raw prices. Commits carry a
Co-Authored-By trailer.

## Credits

- Data sourced by Tiingo.
- Typefaces: IBM Plex Sans, IBM Plex Mono, and Spectral, under the SIL Open
  Font License 1.1, through the `@fontsource` packages.
- The hyphenation points of the methodology page are computed at build time by
  the npm package `hyphen` (Yevhen Tiurin, ISC license), a development
  dependency, from the TeX hyphenation patterns of the hyph-utf8 project.
  Neither the package nor the patterns ship in the bundle; only the points do.
  - French, “Hyphenation patterns for French”: Copyright (C) 1994-2002 Daniel
    Flipo, Bernard Gaulle, 2016 Arthur Reutenauer. MIT license.
  - American English, “Hyphenation patterns for American English”: Copyright
    (C) 1990, 2004, 2005 Gerard D.C. Kuiken. Its notice, reproduced as it
    requests:

    > Copying and distribution of this file, with or without modification,
    > are permitted in any medium without royalty provided the copyright
    > notice and this notice are preserved.

## License

The code and the documentation of this repository are released under the MIT
License: see [LICENSE](LICENSE). The market data are not part of the
repository.

## Disclaimer

Mx Risk MGT is an informational tool. It describes statistical properties of a
portfolio; it is not investment advice and not a recommendation to buy, sell,
or hold a security. The market data come from a third party and can contain
errors, delays, or omissions, and the calculations rest on statistical
assumptions, stated with their limits in METHODOLOGY.md. The figures describe
the past and predict nothing. The application shows its full acceptance text
before first use.
