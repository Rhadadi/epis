---
tier: B
status: published
updated: 2026-10-01
---

> **In short.** Probability describes how an assessment is distributed over possibilities. Its rules govern relationships between assessments, while its interpretation says what the numbers mean. A chance, an observed frequency, and a person's credence are related but distinct. Combining events requires attention to overlap and dependence. Conditioning changes the group or information relative to which a probability is assessed.

## Re-learn

### Begin with a space of possibilities

For an invented finite example, suppose a fair spinner has four equally sized sectors numbered 1 to 4. The possibilities are its four landing outcomes. An event can include several outcomes: landing on an even number includes 2 and 4. The probability is 1/2 under the stipulated equal-outcome model. Fairness supplies the equal weights; having four named possibilities alone would not do so. Hájek distinguishes the probability calculus from the interpretation that guides initial assignments. [@hajek2023, § 1, 3.1]

In the standard finite calculus, probabilities are nonnegative, the whole possibility space has probability one, and probabilities of mutually exclusive events add. A complement therefore has probability 1 − P(A). These requirements specify consistency relations among numbers, rather than measure a spinner's physical performance. [@hajek2023, § 1]

### Addition requires checking overlap

Let A be landing on an even number and B be landing above two. A contains 2 and 4; B contains 3 and 4. Simply adding their probabilities counts 4 twice. The general rule is P(A or B) = P(A) + P(B) − P(A and B). Here the union contains three outcomes, so its probability is 3/4. The rule follows by separating overlapping events into disjoint parts, to which additivity applies. [@hajek2023, § 1]

An event contained in another cannot have higher probability than the containing event. Thus landing on 4 and above two cannot be more probable than landing above two. Elaborating a description with another condition does not create additional probability space.

### Multiplication requires checking dependence

The general product rule is P(A and B) = P(A)P(B | A), with a positive conditioning probability in the elementary ratio treatment. If A and B are independent, learning A leaves B's probability unchanged, and the expression becomes P(A)P(B). Independence is a property to establish or assume; it is not a permission to multiply every pair of percentages. [@joyce2021, § 1]

Mutual exclusion and independence are different. Two distinct single outcomes of one spin cannot both occur. But learning that the spinner landed on 1 rules out its landing on 2, so those positive-probability events are not independent. In contrast, two stipulated independent spins can both land on 1 without either outcome changing the other's chance.

## Beyond the chapter

### What does the number represent?

Hájek surveys several interpretations. Classical probability uses equally possible cases. Frequency interpretations identify probabilities with relative frequencies in suitable classes or sequences. Subjective interpretations treat them as suitable agents' degrees of belief. Propensity interpretations appeal to tendencies of physical setups. These accounts have different difficulties, and no single everyday sentence settles all of them. [@hajek2023, § 3.1, 3.3.1, 3.4, 3.5]

A measured fraction of nine heads in ten tosses is an observed frequency. It need not imply that the coin's chance of heads is 0.9. Hájek uses small samples to explain this gap between a frequency and the probability it is intended to measure. Confidence about the coin's bias is another assessment again, supported by the observations and background information. [@hajek2023, § 3.4]

Probability zero also needs qualification. In a continuous uniform model over an interval, any exact point has zero probability although some point is realized. Zero-probability events therefore cannot always be treated as logical impossibilities. Lin illustrates the issue with a continuously distributed coin bias. [@lin2024, § 3.3]

Read [Bayes' theorem](deeper:09-induction-probability-bayes/bayes-theorem) for reversing a condition, and [common errors](deeper:09-induction-probability-bayes/common-errors-in-probabilistic-reasoning) for mistakes caused by losing the relevant comparison group.

## Sources

### Where to go next

Hájek introduces the calculus before separating its interpretations. Joyce develops conditional probability. Lin's discussion of regularity provides the important caution about zero in continuous models. [@hajek2023, § 1, 3.4; @joyce2021, § 1; @lin2024, § 3.3]
