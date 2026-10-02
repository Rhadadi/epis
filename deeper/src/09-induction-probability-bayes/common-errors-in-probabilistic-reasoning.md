---
tier: B
status: published
updated: 2026-10-01
---

> **In short.** Probability mistakes often begin with a changed comparison group. A result's reliability is confused with the probability of its explanation, or a detailed story is treated as more probable than one of its parts. Random sequences are expected to compensate for recent outcomes. Changes in an aggregate are interpreted without inspecting its component groups. Correcting the arithmetic requires first making the assumed process clear.

## Re-learn

### Reversing a condition and forgetting the base rate

P(E | H) and P(H | E) have different denominators. In an invented population of 1,000 devices, suppose 10 are faulty, a detector catches nine of those, and 99 functioning devices also trigger it. The probability of fault among triggers is 9/108, about 8.3%, despite 90% sensitivity. The numbers show why the probability of an explanation needs the competing routes to the result. [@joyce2021, § 1]

Wheeler discusses experiments interpreted as base-rate neglect, but also reviews criticisms concerning task interpretation and sampling. A participant's answer can depend on how the testimony or selection procedure is understood. That qualification does not change Bayes' theorem; it warns against diagnosing someone's reasoning before specifying the problem they were answering. [@wheeler2024, § 5.1]

### Adding detail cannot increase a conjunction's probability

An invented story says that a candidate is a lawyer, lives beside a canal, and collects maps. The conjunction cannot be more probable than the claim that the candidate is a lawyer: every case satisfying the longer story satisfies that part. A vivid description can make the conjunction feel representative, but representativeness does not change set inclusion. [@hajek2023, § 1]

Wheeler's account of the conjunction-fallacy literature notes that frequency formulations and learning through sampling can change responses. The experimental phenomenon should therefore not be described as an invariant inability to understand probability. The mathematical inequality is clear; how people interpret a particular verbal task is an additional empirical question. [@wheeler2024, § 5.1]

### Independent trials do not owe compensation

If coin tosses are stipulated fair and independent, five heads leave the next toss's chance of tails at one half. Expecting tails to become due is the gambler's fallacy. The IEP entry also supplies the essential qualification: without the fairness assumption, a run of heads can be evidence about the coin's bias. Learning about an uncertain process differs from expecting a known independent process to balance its recent history. [@fallacy-iep, § Gambler’s]

Likewise, an extreme measurement followed by a less extreme one need not reveal an intervention's effect. In an invented model, a worker's stable performance is measured with independent, mean-zero noise. Selecting the worst observed day selects an unusually negative error as well as any stable performance difference. A later measurement can be less extreme without a change in ability. The IEP identifies mistaken causal interpretation of regression toward the mean as a fallacy. [@fallacy-iep, § Regression]

## Beyond the chapter

### Aggregation can reverse a comparison

Simpson's paradox occurs when an association reverses after cases are partitioned by background factors. For illustration, one treatment may be used disproportionately on severe cases, making its aggregate outcomes worse despite better outcomes within both severity groups. Hitchcock explains how such reversals complicate probability-raising accounts of causation. They do not show that one should always prefer the grouped comparison. [@hitchcock2026, § 2.4]

Which factors to hold fixed is a causal question. Controlling for an intermediary through which a treatment works can remove the effect one wanted to assess. Hitchcock uses this point to show why a rule to control every available variable is inadequate. Both the aggregate and subgroup numbers need an account of how the groups arose. [@hitchcock2026, § 2.4]

Read [Bayes](deeper:09-induction-probability-bayes/bayes-theorem) for denominators and dependence, and the narrated [science chapter](10-science-and-evidence.md#causation-and-causal-inference) for the gap between association and intervention. [Scoring rules](deeper:09-induction-probability-bayes/calibration-and-scoring-rules) assess forecasts across cases, rather than judge confidence by one dramatic outcome.

## Sources

### Where to go next

Joyce explains inverse probabilities; Wheeler qualifies the psychological evidence; the IEP isolates gambler's and regression errors; Hitchcock places aggregation in a causal model. Hájek supplies the probability rules behind the conjunction comparison. [@joyce2021, § 1; @wheeler2024, § 5.1; @fallacy-iep, § Gambler’s, Regression; @hitchcock2026, § 2.4; @hajek2023, § 1]
