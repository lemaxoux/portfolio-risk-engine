# Methodology

Mx Risk MGT measures the risk of a portfolio of US-listed stocks and ETFs.
This document states how each figure is obtained: the data, the conventions,
every measure with its formula, assumptions, limitations, and the point where
the tool refuses to give a figure, then the crisis replays, the rules engine,
and four dated results from the project.

It is written for a reader who knows the quantitative vocabulary. The
methodology page of the application explains the same rules to a reader who
starts from zero:
[frontend/src/contenu/methodologie.en.md](frontend/src/contenu/methodologie.en.md).
The design decisions behind the code are in [ARCHITECTURE.md](ARCHITECTURE.md).

## Reading this document

- **Fractions and losses.** The engine computes fractions of the portfolio's
  value. VaR and CVaR are positive losses: a VaR of $x$ reads as a loss of at
  least $x$.
- **Sessions.** A session is a trading day of the US market. Windows are
  counted in sessions, never in calendar days.
- **Numbers.** Every constant cited here is read from the code by the test
  suite. Figures from a portfolio appear only in “Dated results”, where the
  test suite recomputes them on a copy of the database frozen at
  September 9, 2026. Figures that change with the data are shown by the
  application, with their window and date.
- **Code names.** Names in `code` refer to the Python modules under
  `backend/`, whose comments are in French.

## Data

### Prices and adjustments

The prices come from Tiingo: for each security and each session, the raw
close, at which one can trade, and the adjusted close, corrected for splits
and dividends. Returns use the adjusted close (`adj_close`): dividends count
as reinvested, and a split is not a loss. The value of the portfolio uses the
raw close of each holding's last session (`close`), a price at which the
position could change hands, not an index rebased at each dividend.

The valuation date (`as_of`) is the earliest of the holdings' last closes: up
to that date, the valuation holds for every holding. It is never the date of
the calculation.

All prices are in US dollars (USD). This is an assumption of the scope, not a
field read from the provider: no conversion is made anywhere.

### An anchored history

The history starts on a fixed date, January 1, 2005 (`BACKFILL_START`), not at
a sliding distance from today. A sliding depth, such as “the past five years”,
eventually stops covering a crisis without any change in the code, and the
replay of that crisis disappears silently. A fixed start can only extend the
coverage. A security listed after that date comes in with the history that
exists.

The long history serves the crisis replays only. A volatility or a VaR
estimated over the whole history would be dominated by the 2008 Financial
Crisis and would describe a market regime that is over, not the risk of
today.

### Data traps: splits and dividends

When a security goes ex-dividend or splits, the provider recalculates every
earlier adjusted close: the whole adjusted history moves to a new basis. A
refresh that wrote only the missing sessions mixed two bases. The last stored
session came back on the new basis while the session before it stayed on the
old one, and the return between them counted the adjustment as a loss. The
dated result “A false return at a dividend reload” shows the defect on KO.

The fix: when a fetched session carries a dividend (`divCash` different from
zero) or a split (`splitFactor` different from one), `refresh` reloads the
whole history of the security and replaces it in one block, so that its series
rests on a single basis. A database written before the fix is repaired by an
explicit command, `rebuild`, described in [ARCHITECTURE.md](ARCHITECTURE.md).

### The benchmark

The market is represented by the S&P 500, an index of 500 large US companies,
through SPY, the listed fund that tracks it. SPY enters the same aligned panel
as the holdings: loaded on its own, its returns would rest on its own
sessions, and a beta would compare different intervals without any warning.

## Return conventions

### Simple across holdings, log over time

The return of a session is computed on the adjusted price:

$$r_{t} = P_{t} / P_{t−1} − 1$$

The portfolio's return is the weighted average of its holdings' simple
returns:

$$r_{p,t} = w_{1} r_{1,t} + w_{2} r_{2,t} + … + w_{N} r_{N,t}$$

because the value of a portfolio is the sum of the values of its holdings, and
that additivity carries over to simple returns, not to log returns:

$$ln(w_{1}(1 + r_{1}) + … + w_{N}(1 + r_{N})) ≠ w_{1} ln(1 + r_{1}) + … + w_{N} ln(1 + r_{N})$$

Over time, simple returns compound: the value is multiplied by $(1 + r)$
session after session, which amounts to adding log returns, $ln(1 + r)$. The
two are close for small changes and drift apart for large ones, which are the
changes that matter for risk.

### Constant weights

Every measure of ordinary times applies today's weights, each holding's share
of the current market value, to every session of the window. Applying today's
weights to every past session amounts to rebalancing the portfolio to its
current composition at the end of each session. The question answered is what
risk the allocation held today carries, not what the portfolio has done since
it was built. The crisis replays follow another convention, set out below.

### Aligned dates

Series are matched by date, never by position in an array, and only the
sessions on which every holding has a price are kept. A missing session on one
holding would otherwise shift its whole series by one row, and the calculation
would go on without any warning.

The intersection has a cost: a recently listed holding brings every measure
down to its own history. The engine names that holding (`limiting_positions`)
only when it is proven to be the cause, its first available session being
exactly the first session of the aligned panel. When the truncation comes from
a gap elsewhere, or when the window is full, no holding is named.

A short history truncates the window: the current version keeps every holding
and describes the whole portfolio over a shorter period. Setting a holding
aside and reweighting the others is reserved for the crisis replays, where the
coverage is declared.

### The estimation window

The measures of ordinary times use the most recent 504 sessions by default
(`DEFAULT_WINDOW`), about two years: enough sessions for stable estimates,
recent enough to describe the current regime. Each result carries the window
actually used: the number of sessions requested, the number obtained, and the
first and last dates. A volatility estimated over a long window and one
estimated over a few sessions are not the same statement, and nothing in the
number alone says which it is.

The period that a sentence of the application reads, such as “the past two
years”, describes the sessions obtained, never the window requested
(`engine.period_label`).

### One degrees-of-freedom convention

Every estimate of dispersion (standard deviation, variance, covariance, beta)
divides by $n − 1$ (`config.DDOF`). numpy is not consistent with itself:
`np.cov` divides by $n − 1$ by default, `np.std` and `np.var` by $n$. With a
single convention, the volatility obtained from the covariance matrix,
$√(w^{T} Σ w)$, equals the standard deviation of the portfolio's own series
exactly: an algebraic identity, which a test holds to floating-point
tolerance. With two conventions, the variances would differ by the factor
$n / (n − 1)$, and the volatilities by its square root: small enough to pass
for rounding, real enough to be an inconsistency.

Dispersion is computed on shifted data (each series minus its first value),
which leaves it unchanged and removes catastrophic cancellation. Computed
directly, a constant series has a tiny positive standard deviation rather
than zero, and a Sharpe ratio divided by that dust becomes astronomical
instead of undefined.

### Sign conventions

VaR and CVaR are positive losses throughout, and a negative value means a gain
at that confidence level, not an error. The other convention, the return at
the quantile, coexists in the literature, and mixing the two is the classic
source of sign errors: both produce plausible numbers that contradict each
other only in inequalities.

One field keeps the other convention: the threshold published with the CVaR
is the raw quantile of returns, negative, and its description says so. The
API publishes it as the engine computes it, since changing its sign would be
arithmetic outside the engine.

## Measures

Each entry gives the formula, the assumptions, the limitations, and what
happens when the data cannot support the figure: a refusal (the figure is
replaced by its reason) or a flag (the figure is given and marked). Each
threshold says whether it is proven, the same for every portfolio, or chosen
by hand.

### Volatility

$$σ_{year} = σ_{day} × √252$$

where $σ_{day}$ is the standard deviation of the daily returns, with $n − 1$
in the denominator (`measures.annualised_volatility`). The application also
gives the volatility of the S&P 500 over the same sessions, by the same
method, as a reference.

- **Assumptions.** Scaling by √252 assumes independent and identically
  distributed returns: the variance of a sum equals the sum of the variances
  only without covariances.
- **Limitations.** Autocorrelation biases the scaling in one direction or the
  other, and volatility clustering makes volatility itself vary over time.
  Volatility says nothing about direction.
- **Flag (chosen by hand).** Below 30 sessions, the figure is marked
  “Small-sample estimate”. It is not refused: it moves with the data.

The engine also computes an exponentially weighted volatility, in the
RiskMetrics convention (`measures.ewma_volatility`):

$$σ^{2}_{t} = λ σ^{2}_{t−1} + (1 − λ) r^{2}_{t−1}$$

with $λ = 0.94$. Returns are not centered: the daily mean is an order of
magnitude below the daily standard deviation, and estimating it adds more
noise than it removes bias. The recursion starts from the mean of the squared
returns of the window, and the value is the variance after the last return: a
forecast for the next session rather than a description of the window. On a
constant non-zero series, it gives $|r| × √252$ where the standard deviation
gives zero. It carries the same flag below 30 sessions.

### Historical VaR

$$VaR_{α} = −q_{1−α}(r)$$

where $q_{1−α}(r)$ is the empirical quantile of the daily returns at $1 − α$,
taken with the “lower” interpolation: the quantile is always an observed
return, the worse of the two that bracket it (`var.historical_var`).

- **Assumptions.** None on the distribution: the fat tails and the asymmetry
  actually observed are in the figure.
- **Limitations.** It describes the window and says nothing about a shock
  worse than its worst session: it is not a ceiling. At 99%, it rests on a
  handful of sessions.
- **Refusal (proven).** The tail beyond the quantile counts $n × (1 − α)$
  sessions. Below one, no session falls into it, and the “lower” quantile is
  the worst return of the window whatever α: no longer the announced measure.
  Hence $n ≥ 1 / (1 − α)$, that is 20 sessions at 95% and 100 sessions at 99%
  (`config.historical_var_min_observations`).

### Parametric VaR

$$VaR_{α} = z_{α} × σ_{p}$$

$$σ_{p} = √(w^{T} Σ w)$$

where $z_{α}$ is the quantile of the normal distribution, 1.645 at 95% and
2.326 at 99%, read from `scipy.stats.norm` rather than written in the code,
and the mean return is taken to be zero, $μ = 0$ (`var.parametric_var`). Over
504 sessions, the standard error of the mean is of the same order as the mean
itself: the drift is not measured, its noise is, and leaving it out is the
conservative choice at a one-session horizon.

- **Assumptions.** Normal returns.
- **Limitations.** The normal distribution makes extreme sessions very rare;
  the gap with the Student's t VaR shows how much this assumption matters.
- **Flag (chosen by hand).** Below 30 sessions, marked “Small-sample
  estimate”.

### CVaR (expected shortfall)

CVaR, also called expected shortfall, is the average loss on the sessions that
reach the historical VaR threshold (`var.expected_shortfall`):

$$CVaR_{α} = −(r_{(1)} + r_{(2)} + … + r_{(k)}) / k$$

where $r_{(1)}$ is the worst return and $k$ the number of sessions in the
tail, published with the figure. By construction, CVaR is at least the VaR of
the same level. It answers the question that VaR leaves open, how much is lost
on average beyond the threshold, which is why banking regulation (the Basel
Committee's FRTB) moved from VaR to expected shortfall: two portfolios can
share a VaR and have very different tails.

- **Assumptions.** None on the distribution.
- **Limitations.** An average of few sessions; at 99%, of a handful, each
  weighing heavily. The tool attaches a permanent caveat to the 99% CVaR rather
  than a threshold that would fire at every calculation.
- **Refusal (proven).** Refused with the historical VaR of the same level,
  below $1 / (1 − α)$ sessions: it would average an empty tail.

### Monte Carlo cross-check

Each parametric VaR is recomputed by simulation (`var.monte_carlo_var`). The
covariance matrix is factored by Cholesky, $Σ = L L^{T}$, and independent
normal draws multiplied by $L$ acquire the estimated correlation structure:
100,000 draws, with a fixed seed, since a risk figure that changed at each run
could be neither audited nor compared with the previous day's.

The simulation is a cross-check, not a third measure: under normality, it
converges to the closed form, and a persistent gap would reveal an error in
one of the two implementations.

- **Unavailable** when the covariance matrix is not positive definite. The
  check uses the eigenvalues, with a threshold relative to the largest, before
  the factorization: on an exactly singular matrix, the Cholesky routine of
  numpy does not fail but returns a degenerate factor. A window of $n$
  sessions gives a covariance of rank at most $n − 1$, singular as soon as the
  window has no more sessions than the portfolio has holdings; the reason then
  says so in plain words.

### Student's t VaR

The normal Monte Carlo converges to the parametric VaR by construction: it
validates the factorization, not the model. Drawing from a multivariate
Student's t-distribution gives the simulation a reason to exist: the gap
between the two puts a price on the normality assumption.

- **ν by maximum likelihood**, on the portfolio's own series: under a
  multivariate Student's t with a common ν, every linear combination is a
  Student's t with the same ν. The data are standardized by their median and
  their median absolute deviation, ν is parameterized by its logarithm (so that
  a fit with $ν ≤ 2$ is reported, not hidden by a bound), and Nelder-Mead runs
  from several starting values, keeping the best likelihood
  (`var.fit_student_t`).
- **Not the method of moments.** The relation $ν = 6/κ + 4$, with κ the excess
  kurtosis, is defined only for $ν > 4$ and can never return a lower value: the
  estimator would fail exactly where the tails are fattest.
- **Not `scipy.stats.t.fit` as it stands.** On the series of the demonstration
  portfolio, its default optimization stops far below the maximum (see
  “A misestimated ν looks reassuring”).
- **The scale trap.** A multivariate Student's t with scale matrix $S$ has
  covariance $S × ν / (ν − 2)$, not $S$. Passing the empirical covariance as the
  scale would make the simulations more volatile by a factor
  $√(ν / (ν − 2))$, 29% at $ν = 5$, and would inflate the VaR for a reason
  unrelated to the tails. Hence $S = Σ × (ν − 2) / ν$: the simulated covariance
  equals $Σ$, and the gap with the normal Monte Carlo measures the shape of the
  tails and nothing else (`var.student_scale_matrix`). A draw is
  $X = Z × √(ν / W)$, with $Z$ normal with covariance $S$ and $W$ chi-squared
  with ν degrees of freedom, the same $W$ for every holding of the draw: the
  holdings live their extreme sessions together, as in a real crisis.
- **Closed form.** $VaR_{α} = t_{ν,α} × √((ν − 2) / ν) × σ_{p}$
  (`var.student_t_var`), the target of the Student's t Monte Carlo.
- **Expected geometry.** At equal variance, a leptokurtic distribution has
  thinner shoulders and heavier extremes. The 95% quantile is a shoulder: the
  Student's t VaR is usually below the normal one there. The 99% quantile is
  already in the tail: it is usually above. Near $ν = 2$, the variance
  adjustment crushes the moderate quantiles toward zero, and both VaRs fall far
  below the normal one: a ν barely above that bound is first the probable
  symptom of a failed fit.
- **Refusals.** Below 30 sessions, no fit (chosen by hand: the likelihood
  rests on the tail, and 30 sessions hold one or two beyond the 95% quantile).
  With $ν ≤ 2$, refused: the distribution has no finite variance. With
  $ν > 30$, refused (chosen by hand): the Student's t can no longer be
  distinguished from the normal. At equal variance, its VaR departs from the
  normal one by at most 2.05% at 99% and by at most 0.31% at 95%, in relative
  terms, far less than the standard error of a sample standard deviation,
  about $1/√(2n)$ under normality, 9% over 60 sessions. The engine refuses
  rather than caps: a bound inside the optimizer would publish “ν = 30” as if
  it had been estimated (`engine.student_fit`). On short windows without
  extreme sessions, the likelihood pushes ν toward infinity and the optimizer
  stops at astronomically large values; the refusal keeps such a number out of
  the published provenance.

### Maximum drawdown

$$maximum drawdown = min_{t} (V_{t} / M_{t} − 1)$$

where $V_{t}$ is the value curve, a dollar invested at the start of the window
with today's weights, and $M_{t}$ the highest value reached up to and
including session $t$ (`measures.max_drawdown`). The high is a running one: a
high reached after the trough would measure a loss that no one could have
suffered. The curve starts at 1 on the session before the first return:
without that starting point, a fall on the first session would escape the
measure. The recovery is the first session after the trough at which the value
gets back to the peak, if it happens before the end of the window.

- **Assumptions.** Today's weights, as for every measure of ordinary times.
- **Limitations.** It is the worst fall of this window only.

### Sharpe and Sortino ratios

The engine computes both and the API publishes them; the analysis page does
not show them.

$$Sharpe = √252 × mean(r − r_{f}) / σ(r − r_{f})$$

Numerator and denominator use the same series of excess returns, and the
annualization applies once, to the daily ratio. The risk-free rate is the
yield of the 13-week US Treasury bill, 3.90%, observed on September 9, 2026,
in its coupon-equivalent form (`config.DEFAULT_RISK_FREE_RATE`). The discount
rate published for the same bill relates the discount to the face value over a
360-day year: lower than the actual yield, it would inflate the excess returns,
and the Sharpe ratio, without any calculation being wrong. The annual rate
becomes a daily one geometrically, $(1 + r_{f})^{1/252} − 1$, not by
division. The observation date travels with the result: a rate set through the
environment (`MX_RISK_FREE_RATE`) comes out with no date, since the engine
does not know where it comes from.

$$Sortino = √252 × mean(r − τ) / DD$$

where τ is the daily target, zero by default, and $DD$ the downside deviation:
the root mean square of the shortfalls below τ, the mean being taken over all
the sessions of the window, not over the sessions below the target. Dividing
by that count would turn the measure into the average size of the falls and
flatter the portfolios that fall rarely but hard. When no return falls below
the target, the ratio is undefined: the engine returns no value and a reason,
never infinity.

### Concentration and effective holdings

$$N_{value} = 1 / (w_{1}^{2} + … + w_{N}^{2})$$

The sum of the squared weights is the Herfindahl-Hirschman index, which lies
between $1/N$, with equal weights, and one, with everything on one holding;
its inverse is the number of equal-sized holdings that would give the same
concentration (`measures.herfindahl_index`). By risk, the same formula applies
to the contributions to variance $c_{i}$ of the next entry:

$$N_{risk} = 1 / (c_{1}^{2} + … + c_{N}^{2})$$

(`covariance.effective_risk_positions`). The gap between the two says that the
risk is not spread like the money.

- **Assumptions.** Long positions only: the index comes from industrial
  economics, where market shares are positive. A negative weight would count
  positively in the square, and a hedged long-short portfolio would look
  concentrated. The engine raises an error on a negative weight rather than
  returning an uninterpretable number; the API refuses a zero or negative
  quantity at entry, so the case does not reach the engine.
- **Limitations.** By risk, the number can fall below one when a holding has a
  negative contribution; reading it as a number of holdings is then an
  approximation. It never exceeds $N$.
- **Refusal (proven).** By risk, refused below 3 sessions, like the
  contributions it rests on.

### Contribution to variance

$$c_{i} = w_{i} (Σ w)_{i} / (w^{T} Σ w)$$

This is the Euler decomposition of the variance
(`covariance.variance_contributions`). It accounts for the weight and for the
covariance of the holding with the rest of the portfolio: of two holdings
with the same weight, the one that moves with the others contributes more.
The contributions add up to exactly one, a property that a test holds to
floating-point tolerance. A negative contribution marks a holding that moved,
on average over the window, against the rest of the portfolio.

- **Assumptions.** The covariances of the estimation window, with today's
  weights.
- **Limitations.** A contribution is an amplitude, not a direction: it says how
  much a holding moves the portfolio, never whether it gains or loses (see
  “Concentration cuts both ways”).
- **Refusal (proven) and flag (chosen by hand).** Refused below 3 sessions;
  given and flagged below 60 sessions, the threshold chosen for a regression.

### Covariance and correlation

Covariance and correlation are estimated on complete observations only, never
pair by pair (`covariance.covariance_matrix`). Estimated over different
sessions for each pair, the blocks of the matrix would describe different
periods, and the matrix could stop being positive semidefinite, which breaks
the Cholesky factorization far from where the problem began. The correlation
is derived from the covariance, $ρ = D^{−1} Σ D^{−1}$ with $D$ the diagonal
matrix of standard deviations, so that both stay consistent cell by cell; the
diagonal is set to one and the other cells are bounded to the interval from
−1 to +1, by definition (`covariance.correlation_matrix`).

- **Assumptions.** A linear link, stable over the window: the Pearson
  correlation of daily returns.
- **Limitations.** A link measured in ordinary times can become stronger in a
  crisis (see “Calm and crisis regimes”).
- **Refusal (proven).** The correlation is refused below 3 sessions (see “Two
  sample-size regimes”). The covariance stays published: $w^{T} Σ w$ is the
  variance of the portfolio's series, estimable from two sessions, and it
  carries the parametric volatility and VaR.

### Beta and R²

$$β = cov(r_{p}, r_{m}) / var(r_{m})$$

$$R^{2} = β^{2} × var(r_{m}) / var(r_{p})$$

on the daily returns of the portfolio and of SPY (`covariance.beta`). The
regression uses raw returns, not excess returns: at a daily horizon, the
risk-free rate is a near-constant two orders of magnitude below the daily
volatility, and subtracting a near-constant from both sides barely moves the
slope. R² is the share of the portfolio's variance explained by the market:
the systematic share, which adding other US stocks does not dilute. The rest is
specific to the holdings. The standard error of the slope is
$√(var(r_{p}) × (1 − R^{2}) / ((n − 2) × var(r_{m})))$.

- **Assumptions.** A linear link, stable over each period.
- **Refusal (proven) and flag (chosen by hand).** Refused below 3 sessions:
  the slope and the R² are both withheld, since with two observations the line
  passes exactly through the points and has no standard error. Flagged below
  60 sessions.

## Crisis replays

### Peak-to-trough windows

The tool replays three crises on the current portfolio. Each window runs from
a closing peak of the S&P 500 to its closing low (`scenarios.SCENARIOS`), not
by calendar year: a window cut at the start of a year would begin after the
peak and miss part of the fall.

| Crisis | Window | Length | S&P 500 (SPY) over the window |
|---|---|---|---|
| 2008 Financial Crisis | October 9, 2007, to March 9, 2009 | 355 sessions | −55.2% |
| COVID Crash | February 19, 2020, to March 23, 2020 | 23 sessions | −33.7% |
| 2022 Monetary Tightening | January 3, 2022, to October 12, 2022 | 195 sessions | −24.5% |

The falls and the session counts are recomputed by the test suite on the
frozen copy of the database. Other tests check the bounds against the
history: the start is the highest close of SPY, and the end its lowest, each
over a window widened by three months on both sides. Checking the peak
inside the window alone would prove nothing, since the running peak of the
first session is that session itself: only the widened check tells a true peak
from a start placed in the middle of a fall.

### Replaying today's portfolio

On the first session of the window, each holding carries its weight of today;
the quantities that follow from it are then frozen until the end:

$$q_{i} = w_{i} / P_{i,0}$$

$$V_{t} = q_{1} P_{1,t} + … + q_{N} P_{N,t}$$

on adjusted prices, so dividends count as reinvested
(`stress.held_quantities`). Applying today's quantities to the prices of the
time would be wrong: the holdings have followed very different paths since,
and the portfolio that entered the crisis would be nobody's.

This departs from the constant weights of ordinary times, on purpose. Over
several months, constant weights would mean rebalancing every day, selling
what held up best to buy what had just fallen, which a holder who trades
nothing does not do. Over a single session, the two conventions give the same
figure. The tool does not measure what a replay under constant weights would
have given.

### Three figures per crisis

- **At the market low**: $V_{end} / V_{start} − 1$, the value on the last
  session, when the S&P 500 reaches its low, relative to the first
  (`stress.end_to_end_return`). The replay stops there and says nothing about
  the recovery that followed.
- **Worst point along the way**: the maximum drawdown of the replayed
  trajectory, measured from the highest point reached during the crisis; it can
  be deeper than the first figure. It is the fall of the portfolio, never the
  sum of the worst points of each holding, which would compose a crisis in
  which every holding hits its low on the same session.
- **Coverage**: the share of today's value that the replayed holdings
  represent.

The three are displayed at the same size. Only the first receives an amount in
dollars, on today's value of the replayed holdings: the second is measured from
a high that can exceed the starting value, and multiplying it by that value
would give no real loss.

### Coverage

A holding is replayed if its first session in the database is on or before the
start of the crisis and its last session on or after the end. Otherwise it is
set aside
and named, the others are reweighted to 100% of the replayed value, and the
coverage states the share of today's value they represent: in value, not in
number of holdings, since setting aside a small holding and a large one are not
the same statement. Two other treatments were possible and were not retained:
failing the whole crisis, too fragile, or assuming that the missing holdings
stayed flat, which would dilute the loss in a value that was not replayed. The
figure then describes only the replayed part: the loss of the whole may have
been different, in one direction or the other, and the tool does not measure
it.

Below 80% of the value, the replayed part no longer represents the whole well
enough: the rules engine gives no figure for the portfolio, and no sentence
presents the loss as the portfolio's. The threshold is chosen by hand, and its
justification bounds the error: even if the excluded part had lost twice as
much as the covered part, the loss of the whole would exceed the displayed
figure by only a fifth, compared with a half at 50%. With no holding
replayed, no figure is given.

### Contributions by holding

Each holding's contribution is its change in value relative to the replayed
value on the first session (`stress.position_contributions`):

$$contribution_{i} = (V_{i,end} − V_{i,start}) / V_{start}$$

The contributions add up exactly to the figure at the market low. They
separate the holding's own return from its weight in the result: a small
holding can collapse without weighing much.

## Calm and crisis regimes

### Three quantities

For each crisis, the engine compares the beta of ordinary times, estimated
over the window of 504 sessions, with what happened in the crisis
(`engine.compare_regimes`):

| Quantity | Definition | Nature |
|---|---|---|
| Amplification ratio | $ln(1 + R_{p}) / ln(1 + R_{m})$ over the crisis window | a ratio of two cumulative returns: no regression, no residual, no standard error |
| Crisis beta | the slope of the daily returns of the replayed trajectory on those of SPY, within the window | an estimate, with its R², standard error, and number of sessions |
| Return implied by the calm beta | $exp(β_{calm} × ln(1 + R_{m})) − 1$ | what the beta of ordinary times implied, given the change in the S&P 500 |

The ratio and the implied return go through logarithms because they scale a
return spanning several months: log returns add up over time, simple returns
do not. The ratio is deliberately not called a crisis beta: the name would
imply an estimate that did not take place. The gap between the replayed
return and the implied return is the result: it measures what the sensitivity
of ordinary times missed.

The ratio and the crisis beta can diverge, and that is a result, not an
anomaly: the regression measures the daily co-movement around the means, while
a drift specific to the portfolio during the episode changes the cumulative
return without changing the slope.

### Thin crisis samples

A crisis beta estimated on fewer than 60 sessions is flagged. The threshold
is chosen by hand: about three months; below that, a few extreme sessions
dictate the slope on their own. The 23 sessions of the COVID Crash fall below
it: the figure is given, and it enters no conclusion. A figure just judged
fragile cannot then serve as evidence.

### The systematic share

The R² of a crisis minus the R² of ordinary times (`systematic_share_change`)
is the most direct reading of the loss of diversification: the share of the
variance that follows the market, which no spreading across holdings removes.
It says more than the beta, which mixes the strength of the co-movement with the
ratio of the volatilities. Under partial coverage, the loss, the ratio, the
crisis beta, and the calm beta all cover the same replayed holdings, so that
the gap does not mix a coverage effect with a regime effect. See “Calm beta and
crisis losses”.

## The rules engine

### Describe, never prescribe

The rules engine puts figures already calculated into sentences: it reads the
results of the engine and recomputes nothing, and a test checks that it
imports no calculation module. Its findings describe properties, never
actions. “This holding carries a large share of the fluctuations” is a
verifiable fact; “you should reduce it” is investment advice, which nothing in
this project allows the tool to give. The tool knows neither the investment
horizon, nor the objectives, nor the tax situation, nor the rest of the
investor's wealth.

There is no overall rating. It would compress quantities that cannot be
compared (a concentration, a systematic share, the coverage of a crisis) into
one number whose scale means nothing, with a weighting that nothing justifies,
and it would invite the very reading the tool declines. The result is a list
of findings and nothing else. A lexical guard checks that no finding contains a
prescriptive phrasing; it is a net, not a proof.

### The six rules

| Rule (`rule`) | Label in the application | What it describes | Thresholds |
|---|---|---|---|
| `effective_concentration` | How many holdings, really | effective holdings by value and by risk, and the gap between them | none in normal conditions; for the half by risk, 3 sessions (proven) and 60 sessions (chosen) |
| `variance_contribution` | Weight in the fluctuations | each holding's share of the variance against its share of the value, and its contribution in each replayed crisis | reference: the holding's share of the value; 3 sessions (proven) and 60 sessions (chosen) |
| `apparent_diversification` | Holdings that move together | the pairs whose correlation reaches 0.70, or else the most correlated pair | 0.70 (chosen); reference: the correlation of the most correlated pair; 3 sessions (proven) and 60 sessions (chosen) |
| `systematic_share` | Share that follows the market | the R² of ordinary times | none in normal conditions; 3 sessions (proven) and 60 sessions (chosen) |
| `crisis_degradation` | The portfolio in a crisis | the systematic share in ordinary times against each replayed crisis; only the crises estimated on enough sessions enter the conclusion | 60 sessions (chosen) |
| `scenario_coverage` | Crisis partly replayed | the reach of an incomplete replay; below the threshold, no figure for the portfolio | 80% (chosen) |

### Thresholds and references

Thresholds are the weak point of any rules engine: a round number set by hand
quickly takes on the appearance of a truth. They are handled explicitly, from
the most to the least defensible:

- no threshold at all, when the measure speaks for itself;
- a threshold derived from a calculated reference, or proven from the algebra
  of the estimator;
- a reference relative to the portfolio itself;
- as a last resort only, a round number chosen by hand.

Each finding carries its thresholds and their origin, and the API publishes
them in a form a machine can read: a `kind` (chosen, derived, or relative to
the portfolio) and a `role`. A threshold is a boundary set in advance, the same
for every portfolio; a reference is a value calculated from this portfolio, to
which a measure is compared. The application writes “Threshold” or “Reference”
from that field, never from the wording.

**The five thresholds chosen by hand.** There are five in the whole tool, and
their scarcity is a result.

- “strong correlation = 0.70”: a usual convention for calling a correlation
  strong.
- “minimum coverage of a scenario = 80%”: justified by the error bound of
  “Coverage”.
- “minimum sessions for a regression = 60”: about three months.
- “maximum ν of a Student's t-distribution = 30”: beyond it, the Student's t is
  no longer distinguishable from the normal.
- “minimum sessions to estimate a distribution = 30”: the usual “large sample”
  convention. With 30 sessions, under normality, the sample standard deviation
  already varies by about 13% from one window to the next.

Two of them are applied by the engine and read by no rule: the ceiling on ν,
and the minimum sample for a distribution, below which the volatility and the
normal VaR are marked as small-sample estimates.

**The three proven thresholds.** They are not chosen: they follow from the
definition of the estimator, and they are the same for every portfolio.

- “minimum estimable sessions = 3” (see “Two sample-size regimes”).
- “minimum sessions for a historical VaR at 95% = 20” and “minimum sessions for
  a historical VaR at 99% = 100”: below $1 / (1 − α)$ sessions, the tail
  beyond the quantile is empty (see “Historical VaR”).

**References.** A holding's share of the value, against which its share of the
variance is compared, and the correlation of the most correlated pair, cited
when no pair reaches the strong-correlation threshold. Their line says
“calculated from this portfolio”.

### Two sample-size regimes

The four rules that rest on the covariance matrix read the number of sessions
actually used (`window.observations`), never the window requested.

**Below 3 sessions, the measure is refused.** With two observations, centering
leaves a single direction: the two deviations from the mean are $±δ/2$, where
δ is the difference between the two returns, and everything computed on the
centered sample is a function of that δ alone. Each measure then degenerates
in its own way:

| Measure | What degenerates | Why |
|---|---|---|
| correlation | the coefficient is +1 or −1, whatever the data | two centered points are collinear |
| beta | the slope has no standard error and can take any value | a regression with a constant has $n − 2$ residual degrees of freedom, none at $n = 2$ |
| contributions | Σ has rank 1, and each holding's share is $w_{i}δ_{i} / (w^{T}δ)$ | a sample covariance has rank at most $n − 1$, centering removing one dimension |

These are not noisy estimates but arithmetic identities, and no mention of a
thin sample repairs a sentence that states an identity as if it described the
portfolio. The reason published with each refusal states only what is true of
its own measure.

**From 3 sessions up to 60 sessions, the threshold chosen for a regression,
the figure is given and flagged.** It says something, poorly.

The singularity of Σ when the window has no more sessions than the portfolio
has holdings creates no third regime: the contributions need only
$w^{T} Σ w > 0$, never an inverse, and each covariance in them keeps its
$n − 1$ degrees of freedom. A simulation on a one-factor model with a known
truth, run while the rule was written, showed no break when Σ becomes
invertible; the only break is at $n = 2$, and it is exact.

The check sits on the sessions actually used because a floor on the requested
window does not protect: the aligned panel shrinks to the intersection of
dates, and a single recently listed holding can bring a request of 504
sessions down to a few dozen without any parameter changing.

### Where refusal stops

The tool refuses a figure that no longer depends on the data, or that is no
longer the announced measure; it gives, with a flag, a figure that depends on
the data poorly. A volatility over two sessions is a bad figure, not a false
one: change the data and it changes. A correlation over two sessions is +1 or
−1 whatever the data: it measures nothing.

| Case | With two sessions | Treatment |
|---|---|---|
| correlation, beta, contributions | arithmetic identities: the value no longer moves with the data | refused, with a reason |
| historical VaR and CVaR, below $1 / (1 − α)$ sessions | no longer the announced measure: the quantile is only the minimum of the window | refused, with a reason |
| covariance, volatility, normal VaR, drawdown | estimates with one degree of freedom: very poor, but they move | published |
| volatility and normal VaR, below 30 sessions | small-sample estimates | published and flagged |

The flagged estimates enter no conclusion: a test replaces every volatility
and every VaR of a report by a trap that raises at the first read, and the six
rules still evaluate.

The 99% CVaR carries a permanent caveat rather than a rule: at 99%, the tail
holds 1% of the window by construction, and a threshold on its size would fire
at every calculation; an alert that is always on informs no one.

## How figures are worded

The sentences of the application follow a few rules, which the test suites
check where they can:

- A VaR is a threshold that the loss reaches or exceeds on the worst sessions,
  not an average: it reads as a loss of at least that percentage. The average
  beyond it is the CVaR.
- The past is replayed on today's composition, which the portfolio did not
  necessarily have: the sentences use the conditional, “would have lost”.
- An amount in dollars is a change of scale, not a loss suffered: it applies a
  percentage to today's value, which the portfolio did not have on the day of
  the loss. The worst point of a crisis receives no amount.
- No conclusion is drawn from a thin estimate.
- No sentence states what the engine does not measure. For a partially covered
  crisis, the tool says only that the loss of the whole may have been
  different.
- A frequency comes from a table, not from a division: “one trading day in
  twenty, roughly once a month” is associated with 95%, not derived from it.

## What the tool does not do

- **The flags of the first specification.** It planned simple flags, one
  holding above a fixed share of the value, one sector above another. They gave
  way to the effective holdings, which need no threshold, and to the
  contributions to variance, each compared with the holding's own share of the
  value. The database keeps a `sector` column that no rule reads.
- **A volatility flag against the benchmark.** The same specification planned
  a flag for a volatility abnormally high against the benchmark. The tool gives
  the volatility of the S&P 500 over the same sessions as a reference, with no
  rule.
- **Measures published but not shown.** The Sharpe and Sortino ratios, the
  EWMA volatility, and the Herfindahl-Hirschman index are in the API response,
  not on the analysis page.
- **The scope of the current version.** US stocks and ETFs, prices in US
  dollars only, one user on one machine, a portfolio entered by hand or
  imported from a CSV file. A short history truncates the window. The
  histogram of daily returns uses the same bins of 0.25 points for every
  portfolio.

## Dated results

Four results from the project, each tied to a portfolio, a valuation date, and
a window. The test suite recomputes every figure of this section on a copy of
the local database frozen at September 9, 2026
(`tests/test_documents_publics.py`). The first three use the demonstration
portfolio of the tests.

### Calm beta and crisis losses

<!-- dated: calm-beta -->
Portfolio: AAPL 40, MSFT 25, JPM 60, JNJ 50, XOM 80, KO 120 (shares), valued on
September 9, 2026. Ordinary times: 504 sessions, from September 5, 2024, to
September 9, 2026; beta 0.57 ± 0.03, R² 0.49. Each beta is given ± one
standard error of the slope, not a confidence interval (formula in “Beta and
R²”).

| Crisis | Sessions | Crisis beta ± one standard error | R² | Replayed | Implied by the calm beta | Gap | S&P 500 |
|---|---|---|---|---|---|---|---|
| 2008 Financial Crisis | 355 | 0.96 ± 0.02 | 0.86 | −44.0% | −36.6% | −7.4 points | −55.2% |
| COVID Crash | 23 | 1.07 ± 0.03 | 0.98 | −35.8% | −20.8% | −15.0 points | −33.7% |
| 2022 Monetary Tightening | 195 | 0.73 ± 0.03 | 0.79 | −8.7% | −14.7% | +6.0 points | −24.5% |

The share of the variance that follows the market rises from 0.49 in ordinary
times to 0.86 in the 2008 Financial Crisis and 0.79 in the 2022 Monetary
Tightening, the two crises estimated on enough sessions. The COVID Crash points
the same way (0.98), but on 23 sessions, too few to conclude. The beta of
ordinary times understated the replayed loss in the 2008 Financial Crisis and
the COVID Crash, and overstated it in the 2022 Monetary Tightening: the crises
are replayed, not extrapolated from the statistics of ordinary times.
<!-- /dated -->

### Concentration cuts both ways

<!-- dated: concentration-2022 -->
Portfolio: AAPL 40, MSFT 25, JPM 60, JNJ 50, XOM 80, KO 120 (shares), valued on
September 9, 2026. Ordinary times: 504 sessions, from September 5, 2024, to
September 9, 2026.

XOM is 15.8% of the portfolio's value and 13.9% of its variance. In the replay
of the 2022 Monetary Tightening, its own return is +59.7% and its contribution
+9.4 points, while the replayed portfolio ends at −8.7% and the S&P 500 at
−24.5%. JPM, at 25.6% of the value and 35.4% of the variance, cost the
portfolio in every replayed crisis, from 16.6 points in the 2008 Financial
Crisis to 8.7 points in the 2022 Monetary Tightening.

A share of the variance is an amplitude, not a direction: the variance that
makes a holding weigh in the fluctuations can lift the portfolio as well as
sink it. The rules engine says both, and gives each holding's path through the
replayed crises next to its share of the variance.
<!-- /dated -->

### A misestimated ν looks reassuring

<!-- dated: student-nu -->
Portfolio: AAPL 40, MSFT 25, JPM 60, JNJ 50, XOM 80, KO 120 (shares), valued on
September 9, 2026. Series: 504 sessions, from September 5, 2024, to
September 9, 2026.

Maximum likelihood gives ν = 4.07. `scipy.stats.t.fit`, with its default
settings (SciPy 1.18.1), stops at ν = 2.01, 13 units of log-likelihood below.
The failure crashes nothing: it produces a reassuring figure. With ν = 2.01,
the variance-matched Student's t VaR at 99% would be 0.45%, against 1.95% for
the normal distribution and 2.22% for the Student's t at ν = 4.07. A model
meant to be more faithful to the tails would have shown less risk, and no
invariant test catches it; a non-regression test now checks that the
estimator never does worse than scipy on this series.

At ν = 4.07, the expected geometry holds: the Student's t VaR is below the
normal one at 95% (1.27% against 1.38%) and above it at 99% (2.22% against
1.95%).
<!-- /dated -->

### A false return at a dividend reload

<!-- dated: ko-dividend -->
Security: KO alone. Session: September 9, 2026, the return since
September 8, 2026.

The true return of KO on that session is −0.92%, the same from raw and from
adjusted closes in the frozen copy. The database stored −1.51% before the fix,
as read in the backup taken before the repair, on September 28, 2026. The
provider re-adjusts the whole history at each dividend. The refresh of the
tool rewrote that session on the new basis, already re-adjusted for a later
dividend, but not the session before it: in the tool's database, the session
before stayed on the old basis, because the refresh had not rewritten it, and
the return of the junction session counted the adjustment as a loss. The false
return sat in the window of every analysis of a portfolio holding KO until the
repair. Since the fix, a dividend or a split triggers a full reload of the
history of the security (see “Data traps: splits and dividends”).
<!-- /dated -->
