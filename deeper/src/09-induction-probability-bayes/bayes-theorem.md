---
tier: A
status: published
updated: 2026-10-01
---

> **In short.** Bayes' theorem connects the chance of evidence given a hypothesis with the chance of the hypothesis given that evidence. Those are different quantities because the evidence may have other causes. A positive result can greatly raise a rare hypothesis's probability while leaving it less likely than its alternatives. The theorem makes the role of prior probabilities and competing explanations explicit. It gives a mathematical relation; using it as a rule for changing belief requires further assumptions about what was learned.

## Re-learn

### Read the condition first

P(E | H) asks: among the cases in which H holds, how common is E? P(H | E) asks: among the cases in which E holds, how common is H? Reversing the condition changes the comparison group. A machine that often sounds an alarm when it is defective need not usually be defective when its alarm sounds. There may be many functioning machines, and some may sound false alarms. Joyce begins his account with exactly this distinction between direct and inverse conditional probabilities. [@joyce2021, § 1]

### An invented alarm example

Suppose 1% of machines in a particular setting are defective. The alarm sounds on 90% of defective machines and 5% of functioning ones. These are invented assumptions, not measured performance claims. In a notional group of 10,000 machines, there are 100 defective machines and 9,900 functioning ones. We expect 90 true alarms and 495 false alarms. Among the 585 alarms, the defective proportion is 90/585, approximately 15.4%.

The 90% sensitivity is therefore not a 90% probability of defect after an alarm. The alarm raises the probability from 1% to about 15.4%, a substantial change, but functioning machines still account for most alarms. This is the structure of Joyce's diagnostic use of Bayes' theorem, illustrated with different numbers. [@joyce2021, § 1]

### The equation preserves both routes to the evidence

For a hypothesis H and evidence E with P(E) > 0:

$$P(H\mid E)=\frac{P(E\mid H)P(H)}{P(E)}.$$

For the two exhaustive possibilities H and not-H:

$$P(H\mid E)=\frac{P(E\mid H)P(H)}{P(E\mid H)P(H)+P(E\mid\neg H)P(\neg H)}.$$

The numerator is the route to an alarm through a defect. The denominator adds the route through a functioning machine. Both quantities refer to the same background information. The equation cannot tell us whether the assumed defect rate or alarm rates apply to the machine actually being assessed. [@joyce2021, § 1]

## The full story

### A relation derived from shared probability

Conditional probability is defined, in the elementary treatment used here, by P(H | E) = P(H and E)/P(E), when P(E) is positive. Similarly, P(E | H) = P(H and E)/P(H), when P(H) is positive. These fractions share the same joint event. Multiplying the second fraction by P(H), then dividing by P(E), yields the theorem. Nothing about that derivation requires the probabilities to be someone's beliefs. [@joyce2021, § 1]

::: argument Where the theorem comes from
1. P(H and E) = P(E | H)P(H).
2. P(H | E) = P(H and E)/P(E), provided P(E) > 0.
3. Substituting premise 1 into premise 2 gives P(H | E) = P(E | H)P(H)/P(E).
:::
[@joyce2021, § 1]. This derivation uses positive conditioning probabilities. More advanced treatments of conditional probability handle situations outside this elementary ratio presentation; they are not needed for the finite examples on this page.

The theorem's mathematical status should be separated from the philosophical program called Bayesian epistemology. The theorem relates probabilities within a probability assignment. Bayesian epistemology uses probabilistic credences and proposes norms governing how those credences should fit together and change. Agreement with the equation alone does not settle those normative proposals. [@joyce2021, § 3; @lin2024, § 1.4, 1.5]

Joyce connects the theorem's history to Bayes's posthumously published essay. This page uses Joyce's account of that essay rather than quoting Bayes's original text. A later primary source, Laplace's essay on probability, states a broad ambition for using calculation to discipline judgment. That ambition helps explain the appeal of making implicit assumptions explicit. [@joyce2021, § 1; @laplace1902, p. 196]

::: original Laplace on calculation and judgment
> It is seen in this essay that the theory of probabilities is at bottom only common sense reduced to calculus; it makes us appreciate with exactitude that which exact minds feel by a sort of instinct without being able ofttimes to give a reason for it.
:::
[@laplace1902, p. 196]. Calculation makes relationships precise. It does not make the input assumptions accurate just because the arithmetic is exact. Laplace's statement expresses a program for probabilistic reasoning; it is not a guarantee that every numerical judgment is warranted.

### Four quantities, four jobs

The **prior**, P(H), is the probability assigned before incorporating the particular evidence E. It can already reflect extensive background knowledge. Calling it prior does not mean it is an uninformed guess or an opinion formed before every observation. It identifies its place relative to a particular update. The **posterior**, P(H | E), is the probability conditional on that evidence. [@joyce2021, § 1, 3]

The **likelihood**, P(E | H), measures how probable the evidence is on the hypothesis. Viewed as a function of candidate hypotheses for fixed evidence, it need not be a probability distribution over those hypotheses. In the alarm example, 0.90 and 0.05 describe two routes to an alarm. They do not have to sum to one: they condition on different groups. This follows from the distinction Joyce draws between likelihood and the inverse conditional probability. [@joyce2021, § 1]

The **marginal probability of the evidence**, P(E), measures how probable E is before learning it. In an exhaustive two-way partition it is the weighted sum of the two routes. If more than two competing hypotheses are used, the corresponding denominator sums their weighted likelihoods. That sum requires alternatives that are mutually exclusive and collectively exhaustive within the model. [@joyce2021, § 1]

An invented fault diagnosis illustrates the last requirement. A warning might arise from a sensor defect, a wiring defect, or a software defect. If machines can have more than one fault at once, those labels are not mutually exclusive. Adding their probabilities as though they formed a partition counts some machines twice. One could instead use disjoint combinations of faults, or construct a joint model that accounts for their overlap. The theorem does not repair a mistaken partition automatically.

### Why the base rate matters

Return to the notional 10,000 machines. Multiplying each group size by its alarm rate is a way to display the joint probabilities as counts. The 90 true alarms and 495 false alarms are the numerator and competing contribution to the denominator. Dividing by the total number of alarms answers the posterior question because that is now the group under examination. [@joyce2021, § 1]

| Route to the alarm | Machines | Alarm rate | Expected alarms |
|---|---:|---:|---:|
| Defective | 100 | 90% | 90 |
| Functioning | 9,900 | 5% | 495 |
| Total | 10,000 | — | 585 |

These figures illustrate assumed rates in a large notional group. They do not say that every actual group of 10,000 must contain exactly these numbers. The probability calculation is the central point: 0.009 divided by 0.0585 gives approximately 0.154. A frequency picture makes the denominator visible without turning expected counts into a promise about one observed sample.

Now change only the prior defect probability to 50%. The same likelihoods give 0.45/(0.45 + 0.025), approximately 94.7%. An identical alarm can therefore produce different posterior probabilities in different background settings. It is neither correct to ignore the test performance nor correct to ignore the starting prevalence. Joyce's second form of the theorem displays their joint contribution. [@joyce2021, § 1]

For an actual machine, the relevant prior might depend on age, maintenance, operating temperature, and the way it was selected for inspection. A population average is not automatically the appropriate prior for a machine sent to a workshop because it already showed other symptoms. This is a modeling issue. The numerical example is useful precisely because it keeps the assumptions visible rather than suggesting that any single prevalence figure transfers to every case.

### Odds show the evidential multiplier

Probability and odds express the same assessment on different scales. A probability p corresponds to odds p/(1 − p). Probability 0.20 means odds 1 to 4; probability 0.80 means odds 4 to 1. Odds compare H with its negation, whereas probability compares H with the whole space of possibilities. Joyce explains why this alternate expression is useful for evidence. [@joyce2021, § 2]

Bayes' theorem can be written:

$$\text{posterior odds}=\text{prior odds}\times\frac{P(E\mid H)}{P(E\mid\neg H)}.$$

The fraction is the **likelihood ratio**. In our invented alarm case it is 0.90/0.05 = 18. Prior odds of 1 to 99 become posterior odds of 18 to 99, or 2 to 11. Converting back gives 2/(2 + 11) = 2/13, approximately 15.4%. Evidence can multiply odds by a large factor without making H more probable than not-H. [@joyce2021, § 2]

The likelihood ratio asks whether this evidence is more expected under H than under its alternative. A feature that is common under both can be weak evidence even if H strongly predicts it. Suppose an invented fault produces a humming sound in 80% of cases, while functioning machines hum in 75%. The hum's likelihood ratio is only 0.80/0.75, about 1.07. Saying a fault would often cause a hum leaves out the fact that a hum is almost as common without the fault.

For two particular rival hypotheses H and H*, posterior relative probabilities equal prior relative probabilities multiplied by P(E | H)/P(E | H*). Joyce presents this as the general form involving a Bayes factor. Comparing two rivals does not show that those rivals exhaust every possible explanation. Their relative standing can improve even while both remain unlikely in a wider model. [@joyce2021, § 2]

### Confirmation is a change, not a finishing line

On a standard Bayesian account of incremental confirmation, E confirms H when P(H | E) exceeds P(H). This relation is different from H having a high posterior probability. Our alarm confirms a defect in that sense: 15.4% exceeds 1%. It does not make defect the more probable of the two exhaustive alternatives. Confusing those claims makes weakly probable explanations sound established. [@joyce2021, § 3]

Conversely, evidence can lower confidence in a hypothesis that remains very probable. An invented assessment falling from 0.99 to 0.95 has been disconfirmed incrementally, despite retaining high probability. Evidence's direction, evidence's magnitude, and the resulting level of confidence are separate questions. Joyce distinguishes incremental support from total support for just this reason. [@joyce2021, § 3]

Surprising evidence is not automatically favorable evidence. If a rare alarm pattern is even rarer under the fault hypothesis than under its alternative, it counts against the fault. What matters is the relevant comparison, not surprise in isolation. Joyce qualifies the familiar claim that unexpected evidence has greater confirmatory force: it requires holding relevant predictive probabilities fixed. [@joyce2021, § 3]

### Updating is an additional rule

Suppose you begin with a probability assignment P, then learn E with certainty and acquire no other relevant information. Standard conditionalization recommends a new credence P-new(H) = P-old(H | E). The theorem helps calculate the conditional quantity; the norm says to make it your new unconditional credence. Those are different statements, one mathematical and one about rational learning. [@lin2024, § 1.2]

The distinction matters when an observation is uncertain. Looking at a cloudy sky can increase confidence that a racetrack is muddy without making mud certain. Lin describes Jeffrey conditionalization as a rule that can accommodate this kind of learning: it changes the weights of evidence alternatives while preserving specified conditional credences. It is not simply substituting an uncertain impression for certain E in the usual rule. [@lin2024, § 5.3]

It also matters when new information changes the model. Discovering that an alarm is produced by a firmware bug may alter both likelihoods and the set of rival explanations. That differs from receiving one more alarm under a model assumed fixed. Separating model revision from straightforward conditionalization prevents a mechanically applied equation from disguising what was really learned.

### Repeated evidence and dependence

A second result can provide further evidence, but its likelihood must be assessed conditional on the first result and the background information. The joint likelihood is P(E1 and E2 | H) = P(E1 | H)P(E2 | H and E1). Replacing the second factor by P(E2 | H) requires conditional independence given H; the analogous replacement for the alternative requires conditional independence given that alternative. This is a direct application of conditional probability. [@joyce2021, § 1]

Consider a second report that merely copies the first alarm report. Given the first report, the copied report supplies no independent measurement. Multiplying the initial likelihood ratio by itself would count the same information twice. Two genuinely separate instruments may also share a failure cause. An assertion that they are independent needs a model of that shared cause, rather than a count of how many screens display the result.

With valid conditional independence assumptions, successive likelihood ratios multiply, and the updated odds can become the next stage's prior odds. Without them, the correct calculation uses the joint evidence likelihoods. The theorem still applies; the shortcut fails. This difference is useful whenever apparent corroboration may originate in a common source.

### Which priors are permissible?

Bayesian epistemology contains a substantial disagreement about priors. Subjective Bayesians permit coherent priors; objective Bayesians propose additional constraints, such as principles intended to avoid bias. Lin explains that coherence and conditionalization alone can support both inductive and counter-inductive assignments. The theorem does not resolve that disagreement because it relates inputs rather than selects them. [@lin2024, § 1.5, 4.1, 4.2]

In practice, an invented workshop comparison might calculate posteriors across a range of plausible defect rates. If its conclusion is stable across that range, the disagreement matters less for that conclusion. If it changes sharply, the report should expose the sensitivity. This is an illustrative use of the equation, not a claim that sensitivity analysis provides a universal philosophical solution to the problem of priors.

Probability assignments of zero also need care. Under ordinary ratio conditionalization, a discrete hypothesis initially assigned zero cannot gain positive probability through evidence with positive probability. But in continuous models, an individual parameter value may have probability zero without being logically impossible. Lin's discussion of regularity uses a uniformly distributed coin bias to show why zero and impossibility must not be identified without qualification. [@lin2024, § 3.3]

## Beyond the chapter

### Probability and action answer different questions

A posterior does not by itself say whether to shut a machine down. That decision also depends on the consequences of a fault, the cost of inspection, and the cost of interrupting production. Two workshops can share a posterior and rationally choose different actions because those consequences differ. The theorem should be used to state the probability question accurately before the decision question is addressed.

Nor does it make a probability of a hypothesis equal to a statistical p-value. A p-value evaluates a tail probability under a specified null model; a posterior evaluates a hypothesis conditional on data and background assumptions. Read [statistics and significance](deeper:09-induction-probability-bayes/statistics-and-significance) before transferring language from one framework to the other. [@romeijn2025, § 3.1.1, 3.2.1]

### What the theorem leaves open

The formula cannot select the hypothesis space, establish the measurement reliability, or guarantee that a population rate fits a selected case. It makes these dependencies easier to inspect. Its value is therefore partly diagnostic: an apparent dispute about arithmetic may actually be a dispute about the prior, the alternatives, or the route by which the evidence was obtained.

Continue with [Bayesian epistemology](deeper:09-induction-probability-bayes/bayesian-epistemology) for coherence and learning norms, [common errors](deeper:09-induction-probability-bayes/common-errors-in-probabilistic-reasoning) for misleading reversals, and [responses to Hume](deeper:09-induction-probability-bayes/responses-to-hume) for the limits of a probabilistic answer to induction.

## Sources

### Where to go next

Joyce's first two sections develop the conditional-probability and odds forms; section 3 explains evidential support. Lin separates the theorem from the norms and disputes of Bayesian epistemology. Laplace's concluding discussion supplies the primary quotation, read here directly in the public-domain translation. Romeijn places statistical significance in its own inferential framework. [@joyce2021, § 1, 2, 3; @lin2024, § 1.5, 5.3; @laplace1902, p. 196; @romeijn2025, § 3.1.1, 3.2.1]
