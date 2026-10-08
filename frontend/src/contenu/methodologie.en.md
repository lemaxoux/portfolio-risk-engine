# Methodology

This page explains how the tool obtains each figure in the analysis: where the data comes from, which conventions the calculation follows, what each measure calculates, what it assumes, and where it stops. It follows the order of the analysis page. The analysis says what a figure means for your portfolio; this page says how it is obtained. Each formula is first stated in words, and no figure from your portfolio appears here: only the rules of the calculation, the same for everyone.

## What the tool does {#principes}

The tool describes your portfolio as you hold it today: how its value would have changed, what it could have lost, which holdings, that is, which of the securities you hold, carry its fluctuations, and what major past crises would have done to it. It never says what to do with it: it does not know your investment horizon, your objectives, your tax situation, or the rest of your wealth.

Its measures describe the past and predict nothing: the future may depart from it sharply, especially during a crisis.

Each figure is an estimate under conditions, and it carries them with it: under “Calculation details”, its method, the number of trading days it rests on, and its period; in the banner, at the top of the page, the valuation date, that of the prices used. Volatility, which measures the usual size of the fluctuations, does not say the same thing when estimated over two years or over seven days.

**Why there is no overall rating.** The tool never sums up the risk in a single rating, out of a hundred, in letters, or in colors. Such a rating would add up, with a weighting that nothing justifies, quantities that cannot be compared: the concentration of the portfolio on a few holdings, the share of its fluctuations that follows the market, the share of its value that a replayed crisis could cover. It would hide the trade-offs that the page exists to show, and would look like advice without being advice.

## The data {#donnees}

**Prices.** They come from Tiingo, a market data provider: the closing price, the last of each trading day, of stocks and funds listed in the United States, in US dollars (USD). For each day, the database keeps two prices: the raw price, at which one could trade, and the adjusted price, corrected for stock splits (one share cut into several) and for dividends.

**Two prices, two uses.** The value of your portfolio is calculated at the raw price, a real price; returns, that is, the changes from one trading day to the next, at the adjusted price. On the day a stock goes ex-dividend or splits, its raw price falls without its holder becoming poorer: the calculation would see a loss there that is not one. At the adjusted price, dividends count as reinvested. When a dividend or a split is added, the update reloads the security's entire history, so that its series rests on a single basis.

**Depth of history.** Prices go back to January&nbsp;1,&nbsp;2005, a fixed date: a sliding period, such as “the past five years”, would one day push a crisis out of the history with nothing to signal it. This date covers the three crises that the tool replays; a security listed later comes in with the history that exists.

**The benchmark index.** The market is represented by the S&P 500, an index of 500 large US companies, through SPY, the listed fund that tracks it.

**The valuation date.** The “Valued as of” date is the earliest of the last closes of your holdings: up to that date, the value is true for all of them. It dates the prices, not the quantities: the date your positions were changed is given separately, in the banner.

## The conventions {#conventions}

**Today's composition, replayed over the past.** The measures apply today's weights, each holding's share of the current value, to every past day, as if the portfolio had been reset each evening to its current composition. They say what risk is carried by what you hold now, not what your portfolio has done since you built it: hence the conditional in the sentences, “would have lost”. An amount in dollars represents a share of today's value; it does not say what was lost on that day.

**Returns.** A day's return is the change in the adjusted price since the previous trading day; the portfolio's return, the average of its holdings' returns, weighted by their current weights.

$$r_{t} = P_{t} / P_{t−1} − 1$$

$$r_{p,t} = w_{1} r_{1,t} + w_{2} r_{2,t} + … + w_{N} r_{N,t}$$

Here, $P$ is the adjusted price, $w_{i}$ the current weight of holding $i$, and $N$ the number of holdings.

**Simple across holdings, compounded over time.** Across holdings, these simple returns are averaged, because the value of a portfolio is the sum of the values of its holdings. Over time, they compound: the value is multiplied by $(1 + r)$ day after day, which amounts to adding up logarithmic returns, $ln(1 + r)$. The two are not interchangeable, and the gap grows with large changes, the ones that matter for risk.

**The estimation window.** The measures of ordinary times cover the most recent 504&nbsp;trading days, about two years, which the sentences call “the past two&nbsp;years”: enough days for stable estimates, recent enough to describe today's markets. Older prices serve only to replay the crises: a volatility calculated over the whole history would be dominated by the 2008 Financial Crisis.

**The same days for all holdings.** The series are aligned by date, and only the days on which all your holdings have a price are kept. A recently listed holding therefore brings all the measures down to its history: the banner says so, with the number of days obtained out of the 504&nbsp;trading days requested, and names the holding responsible when this is proven: its first listing is the day from which all your holdings have a price. Each measure gives, in its calculation details, the number of days actually used.

## The portfolio {#portefeuille}

### Value and weight {#valeur-et-poids}

Section 1 gives, for each holding, the quantity, the last raw price, the value, and the weight.

$$V = q_{1} P_{1} + … + q_{N} P_{N}$$

$$w_{i} = q_{i} P_{i} / V$$

Here, $q_{i}$ is the quantity of holding $i$, $P_{i}$ its last raw price, and $V$ the value of the portfolio. The weight is a share of the value, not of the number of shares.

**Assumptions.** Long positions, securities that you own: a zero or negative quantity is refused at entry.

**Limitations.** A cost basis you enter, the price at which you bought, plays no part in any risk calculation.

## An ordinary day {#jour-ordinaire}

### Historical VaR {#var-historique}

VaR, or value at risk, is a loss threshold: at 95%, the one that the worst 5% of days in the window reach or exceed; at 99%, the worst 1%. The historical version reads it from the observed days: returns are ranked from worst to best, and VaR is the loss of the return that marks that rank.

$$VaR_{α} = −q_{1−α}(r)$$

Here, $q_{1−α}(r)$ is the empirical quantile of daily returns, the return below which the share $1 − α$ of the observed days falls, and $α$ the confidence level, 95% or 99%. VaR is written as a loss and reads as a loss of at least that percentage; if negative, it would be a gain. The quantile is always an observed return: between two days, the tool takes the worse one, with no averaging (“'lower' interpolation”).

**Assumptions.** No distribution is assumed: the observed fluctuations, extremes included, are in the figure.

**Limitations.** The figure describes the window, and holds for other days only if they resemble it. It is not a ceiling: it says nothing about losses beyond the threshold (see [CVaR](#cvar), the average loss on the worst days), nor about a shock more violent than the worst day in the window, cited under the 95% VaR. At 99%, it rests on only a few days. Below 20&nbsp;trading days at 95%, and below 100&nbsp;trading days at 99%, it is not computed: no day would fall in the worst share.

### The chart of changes {#histogramme}

The chart counts the trading days of the window in bins of 0.25&nbsp;points, that is, a change of 0.25%. The bins are the same for every portfolio, and zero is always one of their edges: a fall and a rise never share a bar, and two portfolios are compared on the same grid. The lines mark the thresholds of the historical VaRs, the shaded area the days beyond the 95% threshold. The width of the bins changes the look of the drawing, never a figure.

### Parametric VaR {#var-parametrique}

The same question, put to a curve rather than to the observed days: the normal distribution, the bell curve of statistics, or Student's t-distribution, a bell with thicker edges, which leaves more room for extreme days. The curve is fitted to the daily volatility of the portfolio.

$$VaR_{α} = z_{α} × σ_{p}$$

$$σ_{p} = √(w^{T} Σ w)$$

Here, $σ_{p}$ is the daily volatility of the portfolio, its daily standard deviation: the standard deviation measures how far returns usually stray from their average. The tool derives it from the covariances of your holdings, arranged in a table written $Σ$ (the covariance of two holdings measures how much they vary together), and from their weights $w$: it is the same number as the standard deviation of the portfolio's series, obtained by another path. For the normal distribution, $z_{α}$, its quantile, is 1.645 at 95% and 2.326 at 99%. The average return is taken to be zero (“$μ = 0$”): over two years, the trend of a day is measured less well than its dispersion.

Student's t-distribution has one more parameter, the number of degrees of freedom, written $ν$ (the Greek letter nu): the smaller it is, the more frequent extreme days are. The tool estimates it from your portfolio's returns, by maximum likelihood: the value of $ν$ that makes the observed returns most probable. It then gives the curve the same variance as the normal distribution, the variance being the square of the standard deviation: between the two VaRs, only the shape of the tails changes, those ends of the curve where the extreme days lie.

$$VaR_{α} = t_{ν,α} × √((ν − 2) / ν) × σ_{p}$$

Here, $t_{ν,α}$ is the quantile of Student's t-distribution. At equal variance, it counts more very calm days and more extreme days, and fewer average days: its VaR is usually lower at 95% and higher at 99%.

**Cross-check.** Each parametric VaR is redone by simulation (“Monte Carlo” in the calculation details): 100,000&nbsp;draws at random from the same distribution, with a fixed seed, the starting point of the randomness, so that the figure does not change from one calculation to the next. It is not a third measure: the result, on the “Cross-check” line of the calculation details, matches the formula up to the randomness of the draws, and a gap would signal an error. It is missing in particular when the window has no more trading days than the portfolio has holdings: the simulation is then impossible, and the page says why.

**Assumptions.** The fluctuations follow the shape of the curve: the normal distribution makes very bad days very rare, while Student's t-distribution leaves them more room.

**Limitations.** Each figure is only as good as the assumed shape; the gap between the two curves shows how much this choice matters. Below 30&nbsp;trading days, Student's t-distribution is not fitted, and the normal VaR is marked “Small-sample estimate”. With 2&nbsp;degrees of freedom or fewer, Student's t-distribution has no finite variance; above 30&nbsp;degrees of freedom, it can no longer be distinguished from the normal distribution. In both cases, it is not computed.

### Volatility {#volatilite}

Volatility measures the usual size of the fluctuations, up as well as down: the standard deviation of the window's daily returns, scaled to a year of 252&nbsp;trading days.

$$σ_{year} = σ_{day} × √252$$

Here, $σ_{day}$ is the standard deviation of the $n$ daily returns, with $n − 1$ in the denominator, the convention of the whole calculation; the calculation details also give it. For comparison, the page cites that of the S&P 500, measured over the same days and in the same way.

**Assumptions.** Multiplying by $√252$ assumes days that are independent and follow the same distribution.

**Limitations.** When a day tends to extend or to correct the day before, or when large changes follow one another, the rule is wrong. Volatility does not say in which direction the value goes. Below 30&nbsp;trading days, it is marked “Small-sample estimate”, and the tool draws no conclusion from it.

### CVaR {#cvar}

CVaR answers the question that VaR leaves open: on the days the threshold is crossed, how much is lost on average? It is the average of the returns that reach the historical VaR threshold, written as a loss.

$$CVaR_{α} = −(r_{(1)} + r_{(2)} + … + r_{(k)}) / k$$

Here, $r_{(1)}$ is the worst return, $r_{(2)}$ the next, and $k$ the number of days that reach the threshold, given in the calculation details (“Sessions in the tail”).

**Assumptions.** No distribution is assumed, as for historical VaR.

**Limitations.** It is an average of few days, and at 99% of only a handful: each one weighs heavily, and the tool says so permanently under the 99% CVaR. It is refused along with the historical VaR of the same level. A future bad day can be harder than this average.

## At worst {#au-pire}

### Maximum drawdown {#perte-maximale}

The maximum drawdown is the worst fall in the window, from a high to the low that follows it: each day, the gap between the value and the highest point reached so far, then the largest of these gaps.

$$maximum drawdown = min_{t} (V_{t} / M_{t} − 1)$$

Here, $M_{t}$ is the highest point reached up to and including day $t$. This high is a running one: never a high reached after the fall, which would measure a loss that no one could have suffered. The recovery to the peak is the first day, after the trough, on which the value gets back to that high; if it has not happened before the end of the window, the page says so.

**Assumptions.** Today's weights, applied every day, as for all the measures of ordinary times.

**Limitations.** It is the worst fall of this window only; a future one can be steeper. Older crises are replayed separately, in section 5.

### The value curve {#courbe-de-valeur}

The curve follows one dollar invested at the start of the window, with today's weights. It starts at 1 on the day before the first return used: without this starting point, a fall on the very first day would escape the maximum drawdown.

$$V_{t} = V_{t−1} × (1 + r_{p,t})$$

## What carries the risk {#qui-porte}

### Effective holdings {#lignes-effectives}

By value, the number of effective holdings is the number of equal-sized holdings that would give the same concentration. By risk, the same formula applies to the shares of the fluctuations $c_{i}$, presented just after.

$$N_{value} = 1 / (w_{1}^{2} + … + w_{N}^{2})$$

$$N_{risk} = 1 / (c_{1}^{2} + … + c_{N}^{2})$$

With $N$ equal-sized holdings, the first equals $N$; the more a few holdings dominate, the lower it is: two holdings of 90% and 10% of the value weigh like 1.2&nbsp;equal-sized holdings. The gap between the two says that the risk is not spread like the money.

**Assumptions.** Long positions: the measure comes from the Herfindahl index, the sum of the squared weights, defined for positive shares.

**Limitations.** By risk, the number can fall below one when a holding has a negative share: reading it as a number of holdings is then only an approximation, and the page points this out. Below 3&nbsp;trading days, it is not computed.

### The share of the fluctuations {#part-des-variations}

A holding's share of the fluctuations, or contribution to variance, takes into account its weight and the way it moves with the others: of two holdings with the same weight and the same volatility, the one that follows the rest of the portfolio weighs more.

$$c_{i} = w_{i} (Σw)_{i} / (w^{T} Σ w)$$

Here, $(Σw)_{i}$ is the covariance of holding $i$ with the portfolio. The shares add up to 100%. The gap, in points, is the share of the fluctuations minus the share of the value.

**Assumptions.** The covariances of the estimation window, with today's weights.

**Limitations.** A share says how much a holding moves the portfolio, never in which direction: a holding can weigh heavily in the fluctuations and gain in a crisis, as the table of contributions shows (see [the three figures of a crisis](#trois-chiffres)). A negative share signals a holding that has moved against the rest and that dampens the fluctuations of the whole. Below 3&nbsp;trading days, the shares are not computed.

### Correlation {#correlation}

Correlation measures the link between the changes of two holdings, from −1 to +1: +1 if they always move together, in the same direction and in proportion, 0 with no link of this kind, −1 always in opposite directions.

$$ρ_{ij} = σ_{ij} / (σ_{i} σ_{j})$$

Here, $σ_{ij}$ is the covariance of the two holdings, $σ_{i}$ and $σ_{j}$ their standard deviations, all taken from the same table, over the same days: estimated pair by pair, over different days, the correlations could form an inconsistent table. The map colors them on a fixed scale, the same for every portfolio, and writes each value.

**Assumptions.** A linear link, that is, a proportional one, stable over the window.

**Limitations.** A link measured in ordinary times can become stronger in a crisis. Below 3&nbsp;trading days, correlation is not computed: with two days, it would be +1 or −1 whatever the holdings.

## In a crisis {#en-crise}

### The replay {#rejeu}

Section 5 replays three major crises on your current portfolio: the 2008 Financial Crisis, the COVID Crash, and the 2022 Monetary Tightening. Each runs from the S&P 500's closing peak to its closing low; tests check these dates against the history in the database.

On the first day, each holding carries its weight of today; the quantities that follow from it are then frozen. Nothing is bought or sold: the weights drift with the prices, as for a holder who touches nothing, and dividends count, reinvested.

$$q_{i} = w_{i} / P_{i,0}$$

$$V_{t} = q_{1} P_{1,t} + … + q_{N} P_{N,t}$$

This is a different convention from that of the other sections: over several months, constant weights would mean moving money every day from the holdings that held up best to those that have just fallen. Over a single day, the two conventions give the same figure.

### The three figures of a crisis {#trois-chiffres}

- **At the market low**: the replayed value on the last day, when the S&P 500 hits its low, relative to that of the first, $V_{end} / V_{start} − 1$. The replay stops there: it says nothing about the recovery that followed.
- **Worst point along the way**: the largest fall during the crisis, from the highest point reached during the crisis, like the maximum drawdown of section 3. It can be deeper than the first figure. It is the fall of the whole portfolio, never the sum of the worst points of each holding.
- **Coverage**: the share of today's value that the replayed holdings represent.

The three are displayed at the same size. Only the first receives an amount, on today's value of the replayed holdings: the second is measured from a high that can exceed the starting point, and multiplying it by the starting value would give no real loss.

A holding's contribution, in the table of section 4, is its change in value relative to the replayed value on the first day; the contributions add up to the first figure.

$$contribution_{i} = (V_{i,end} − V_{i,start}) / V_{start}$$

### Coverage {#couverture}

A holding is replayed if it was listed throughout the crisis. Otherwise, the tool does not assume it stayed stable, which would dilute the loss in a value that was not replayed: it sets the holding aside and names it, replays the others, reweighted to 100%, and states the share of the value covered. A dot marks the coverage as soon as it is incomplete. The figure then describes only the replayed part: the loss of the whole may have been different, in one direction or the other, and the tool does not measure it.

Below 80% of the value, the replayed part no longer represents the whole well enough: its figures remain displayed next to their coverage, but no sentence presents them as the loss of your portfolio. With no holding replayed, no figure is given.

### Market sensitivity {#sensibilite}

Beta is the sensitivity of your portfolio to the market: how much it would have moved on average when the S&P 500 moved by 1%, that is, the slope of the line that links their returns, day by day. R² is the share of its fluctuations that follows the market; diversification, which spreads the value across several holdings, acts only on the rest.

$$β = cov(r_{p}, r_{m}) / var(r_{m})$$

$$R^{2} = β^{2} × var(r_{m}) / var(r_{p})$$

Here, $r_{p}$ and $r_{m}$ are the daily returns of the portfolio and of the S&P 500. The table of each crisis gives beta and R² in ordinary times, over the estimation window, and in a crisis, over the days of the crisis and the replayed value: never averaged. After “±” comes the standard error of the slope, its uncertainty, which grows when the line rests on few days or when the points stray from it.

**Assumptions.** A linear link, stable over each period. Returns are taken raw, without subtracting that of a risk-free investment: subtracting a roughly constant rate on both sides barely moves the slope.

**Limitations.** Below 60&nbsp;trading days, a crisis sensitivity is given, but the tool draws no conclusion from it. With partial coverage, the two sensitivities cover the same replayed holdings.

### What the sensitivity implied {#attendu}

The tool compares the replay with what the ordinary-times sensitivity implied, given the change in the S&P 500 during the crisis.

$$expected = exp(β × ln(1 + R_{m})) − 1$$

Here, $R_{m}$ is the change in the S&P 500 over the crisis. The calculation goes through logarithms because it scales a change spanning several months: multiplying the index's fall by beta would give a different figure. The gap between the expected and the replayed change is the result. The expected change assumes a sensitivity unchanged in a crisis: that is precisely what the comparison puts to the test.

## What the engine says {#moteur}

### Findings {#constats}

The findings of section 6 are written by the rules engine, the part of the tool that puts the figures into sentences, from figures already calculated: it calculates nothing more. They describe without ever saying what to do, and each one states the thresholds it rests on and where they come from. Two findings, “How many holdings, really” and “Share that follows the market”, have none as long as the window has enough days: their measure speaks for itself.

A threshold is a boundary set in advance, the same for every portfolio; a reference is a value calculated from your portfolio, to which a measure is compared. Each threshold line says where its value comes from: “chosen by hand (not derived from the data)”, “proven (the same for every portfolio)”, or “calculated from this portfolio”. A colored dot precedes the thresholds chosen by hand.

### The five thresholds chosen by hand {#seuils-choisis}

There are five in the whole tool, and their scarcity is deliberate: a round number chosen by hand is only a last resort.

- “strong correlation = 0.70”: a usual convention for calling a correlation strong; no calculation on your portfolio produces it. When no pair reaches it, the finding cites the most correlated pair.
- “minimum coverage of a scenario = 80%”, a scenario being a replayed crisis: at 80%, even if the missing part had lost twice as much as the replayed part, the loss of the whole would exceed the displayed figure by only a fifth, compared with a half at 50%.
- “minimum sessions for a regression = 60”: a regression calculates a slope, like that of the market sensitivity. These days make up about three months; below that, a few extreme days dictate the slope on their own. Figures that rest on fewer days are given and flagged, and a crisis estimated this way enters no conclusion.
- “maximum $ν$ of a Student's t-distribution = 30”: above it, Student's t-distribution can no longer be distinguished from the normal distribution. At equal variance, its 99% VaR departs from that of the normal distribution by at most 2.05% of its value, far less than the uncertainty of the estimate itself: the tool does not publish a number of degrees of freedom that no longer measures anything.
- “minimum sessions to estimate a distribution = 30”: a usual convention, known as the “large sample” convention, the sample being the set of observed days; no calculation on your portfolio produces it. With 30&nbsp;trading days, if the fluctuations follow a normal distribution, the standard deviation already varies by about 13% from one period to the next, and a Student's t-distribution would rest on one or two extreme days. Below that, Student's t-distribution is not fitted, volatility and the normal VaR are marked “Small-sample estimate”, and no rule reads them.

### The proven thresholds {#seuils-demontres}

- “minimum estimable sessions = 3”: with two days, a correlation is +1 or −1 whatever the holdings, a slope passes exactly through the two points, and the shares of the fluctuations describe only a single gap between two days. These are no longer measures but identities, values that the calculation imposes whatever the data.
- “minimum sessions for a historical VaR at 95% = 20” and “minimum sessions for a historical VaR at 99% = 100”: the worst share of the days counts $n × (1 − α)$ of them. When this count is less than one, no day falls into it, and the figure would be only the worst day of the window, not a quantile. The CVaR of the same level, which averages this share, falls with it.

$$n ≥ 1 / (1 − α)$$

### References {#references}

A holding's share of the portfolio's value, to which its share of the fluctuations is compared; the correlation of the most correlated pair, cited when no pair reaches 0.70. Their line says “calculated from this portfolio”: their value changes with it.

### When the tool refuses a figure {#refus}

The tool refuses a figure when it no longer depends on the data, or when it is no longer the announced measure; it gives the figure with a flag when it depends on the data only poorly. A refused figure leaves its place to a short dash, which screen readers read as “not available”, and to its reason, in plain words.

- Below 3&nbsp;trading days: correlation, market sensitivity, shares of the fluctuations, and effective holdings by risk.
- Below 20&nbsp;trading days at 95%, and below 100&nbsp;trading days at 99%: historical VaR and the CVaR of that level.
- Below 30&nbsp;trading days, or with 2&nbsp;degrees of freedom or fewer, or more than 30&nbsp;degrees of freedom: Student's t VaR.
- A crisis that no holding covers: all its figures. Below 80% of the value covered: no loss is given for the whole.

An estimate flagged as a small-sample estimate enters no conclusion: a figure just judged fragile cannot then serve as evidence.
