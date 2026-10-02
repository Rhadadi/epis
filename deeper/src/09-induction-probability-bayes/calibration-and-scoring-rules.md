---
tier: B
status: published
updated: 2026-10-01
---

> **In short.** A probabilistic forecast should be assessed across outcomes rather than branded wrong whenever a less probable result occurs. Calibration compares stated probabilities with outcome frequencies in groups of predictions. A scoring rule gives a numerical assessment of each probability and outcome. A strictly proper rule rewards reporting one's actual probability in expectation. Calibration and a good score still need scrutiny of the cases, the comparison, and the information available when predicting.

## Re-learn

### Calibration asks about a collection

Suppose, in an invented example, a forecaster makes 100 predictions of rain, each at probability 0.7, and rain occurs on 70 of those days. That group is empirically calibrated at the stated level: the observed frequency matches the prediction. A single dry day does not contradict a forecast of 0.7. The forecast already assigns dry weather probability 0.3.

Now suppose the days include 50 from a wet season and 50 from a dry season, with 45 and 25 rainy days respectively. The overall rate is still 70%, but the subgroup rates are 90% and 50%. Aggregate calibration can hide opportunities to make more informative predictions if the season was known in advance. This is an arithmetic example, not a report of a weather study.

Calibration is therefore one question about predictive performance. A constant forecast matching an overall rate may be calibrated while ignoring useful distinctions. Comparing more informative forecasts requires a way to assess probability assignments against the outcomes they predict. Pettigrew's discussion connects accuracy and calibration while developing scoring rules as measures of epistemic value. [@pettigrew2024, § 5.1]

### The Brier loss makes confidence count

For a binary outcome y, with y = 1 when the event occurs and y = 0 otherwise, use the squared-error loss (p − y)². A forecast of 0.8 incurs loss 0.04 if the event occurs and 0.64 if it does not. A forecast of 0.5 incurs 0.25 either way. Greater confidence earns a smaller loss when accurate and a larger loss when inaccurate. [@pettigrew2024, § 5.1]

Average the losses over a fixed set of resolved forecasts to obtain the binary mean Brier loss. Smaller is better under this convention. Pettigrew presents the negative quadratic score as utility and sums it over an agenda of propositions: higher is better there. The sign and aggregation convention must be stated before comparing numerical scores. Scoring both an event and its complement also doubles the single-event squared loss. [@pettigrew2024, § 5.1]

### Properness concerns an expectation

Suppose your actual probability is q but you report p. Expected squared loss is q(1 − p)² + (1 − q)p². This equals (p − q)² + q(1 − q), and is uniquely minimized at p = q. That calculation shows why the quadratic loss is **strictly proper**: by your own probability assessment, an honest report uniquely minimizes expected loss. Pettigrew explains the corresponding property for scores expressed as utilities. [@pettigrew2024, § 5.1]

The guarantee is about expectation under the forecaster's assessment. An exaggerated report can happen to score better on one realized outcome. Properness does not establish that the forecaster's actual probability was itself supported by good evidence.

## Beyond the chapter

### A comparison needs a shared task

Two average scores from unrelated prediction sets are hard to compare. Someone predicting mostly obvious outcomes can obtain a lower loss than someone tackling difficult ones. Record which events were forecast, when the probabilities were recorded, and how outcomes were resolved. An invented comparison of two forecasters is interpretable when both predict the same events with the same information deadline.

Pettigrew also discusses varying importance across propositions as an objection to treating every item in an agenda alike. A numerical measure embodies choices about what is being valued. It should not silently substitute for every practical or epistemic goal of forecasting. [@pettigrew2024, § 5.1.1]

Read [Bayesian epistemology](deeper:09-induction-probability-bayes/bayesian-epistemology) for accuracy arguments defending coherence, and [full belief](deeper:09-induction-probability-bayes/full-belief-and-degrees-of-belief) for why high confidence is not simply a categorical verdict.

## Sources

### Where to go next

Pettigrew's section 5.1 defines the quadratic score, strict propriety, and competing rationales for accuracy measures. Section 5.1.1 asks whether propositions should receive equal importance. These are foundations for evaluating forecasts, rather than a guarantee that every well-scored forecaster knows the truth. [@pettigrew2024, § 5.1, 5.1.1]
