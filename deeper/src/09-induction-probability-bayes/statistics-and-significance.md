---
tier: B
status: published
updated: 2026-10-01
---

> **In short.** Statistical significance evaluates data through a specified testing procedure. A p-value is not the probability that the tested hypothesis is true or that the finding will replicate. Error rates describe how procedures behave under assumptions, while effect estimates address the size of a relationship. Selective analysis and selective publication can change what a significant result tells us. Interpreting a result requires its design and uncertainty, not just a threshold label.

## Re-learn

### Ask which probability was calculated

A null model specifies a distribution of possible data, together with other modeling assumptions. In a familiar testing setup, the p-value is the probability under that model of a result at least as extreme as the observed statistic, using the test's definition of extreme. Romeijn develops its relation to rejection regions and significance levels. A small value identifies tension with the specified model; it does not assign a posterior probability to that model. [@romeijn2025, § 3.1.1, 3.2.1]

The significance level alpha is a procedure's false-rejection rate under the null, or a bound on it. A type-I error rejects a true null. Power concerns rejection under a specified alternative; a type-II error fails to reject under that alternative. The p-value is calculated after observing the data and is different from a preselected significance level. [@romeijn2025, § 3.1.1]

### Why five percent does not mean five percent false

Use an invented collection of 1,000 tested hypotheses. Suppose 100 concern real effects and 900 do not. Assume power 80% for the real effects and false-positive rate 5% for the null cases. Expected positives comprise 80 true positives and 45 false positives. Under these assumptions, the false share among positive results is 45/125 = 36%, not 5%.

This is a calculation about selected positive results across the assumed collection. It is not a posterior for a particular study, and the invented rates are not measurements of any field. Ioannidis's model explains why pre-study odds, power, and bias affect the reliability of claimed findings. His title is a model-based warning, not an empirical count proving that a fixed majority of every field's papers is false. [@ioannidis2005, Modeling the Framework for False Positive Findings]

### Size and uncertainty need their own reports

A significance label does not state how large an effect is or whether it matters for a decision. Report an estimate and its uncertainty, while explaining what the interval means. A frequentist 95% confidence procedure has a coverage property across repeated samples under its assumptions. It does not automatically assign 95% posterior probability to the parameter's lying in the single interval already calculated. Romeijn emphasizes that the guarantee belongs to the procedure. [@romeijn2025, § 3.1.3]

Failure to reject also does not demonstrate the absence of an effect. A low-powered test can fail to detect effects it was meant to investigate. The interpretation needs the relevant alternatives and the procedure's sensitivity, rather than treating nonsignificance as equality. [@romeijn2025, § 3.1.1]

## Beyond the chapter

### The route to publication matters

Fidler and Wilcox describe p-hacking practices such as inspecting significance before choosing a stopping point or a model, and cherry-picking which outcomes to report. Those practices can inflate false-positive rates when the final analysis is treated as though it had been fixed in advance. Exploring data is useful; presenting selected exploratory findings as a preplanned test misdescribes the evidential procedure. [@fidler-wilcox2026, § 2.3]

Publication bias creates another selection layer when significant findings are more likely to appear than nonsignificant ones. A reader then encounters a filtered set of outcomes rather than the full set of tests. Fidler and Wilcox connect this problem with low power and distorted research summaries. Their discussion does not imply that every significant finding is unreliable. [@fidler-wilcox2026, § 2.2]

Changing the threshold alone cannot correct every selection practice or answer every evidential question. The literature also debates how significance, estimation, and other approaches should be used. Read [Bayes' theorem](deeper:09-induction-probability-bayes/bayes-theorem) before substituting posterior language for a p-value. [@fidler-wilcox2026, § 2.4; @romeijn2025, § 3.2.1]

## Sources

### Where to go next

Romeijn explains testing, confidence intervals, and their contested relation to belief. Fidler and Wilcox describe research and publication practices. Ioannidis supplies the primary model connecting power, pre-study odds, and the reliability of positive findings. [@romeijn2025, § 3.1.1, 3.1.3, 3.2.1; @fidler-wilcox2026, § 2.2, 2.3; @ioannidis2005, Modeling the Framework for False Positive Findings]
