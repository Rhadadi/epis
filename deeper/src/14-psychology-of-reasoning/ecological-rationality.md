---
tier: B
status: published
updated: 2026-10-02
---

> **In short.** Ecological rationality assesses a decision procedure in relation to its environment. A simple rule can exploit a useful regularity and fail when that regularity changes. More computation is not automatically better if the information or estimates are poor. The procedure’s search, stopping, and decision rules should be explicit. Its success needs comparison on relevant cases under an appropriate standard.

## Re-learn

### A rule and the world it uses

Imagine a fictional warehouse where packages of one shape usually contain fragile goods. Workers use the shape to decide which packages need extra protection. That rule may be useful while the correlation holds. If suppliers change their packaging, the same cue can become misleading without any change in the workers’ reasoning ability.

Wheeler explains ecological rationality as a concern with features of environments that help or hinder decision procedures. He stresses the relation between behavioural constraints and environmental structure, while noting that drawing the boundary between them can be theoretically difficult. [@wheeler2024, § 3, 3.1]

The assessment therefore asks more than whether the worker ignored information. Which information was available? What did it cost to obtain? What did the cue predict? What errors mattered? Those questions identify the actual problem the rule was meant to handle.

### Make the algorithm inspectable

Fast-and-frugal heuristics are specified through search, stopping, and decision rules. Wheeler’s account describes procedures such as Take-the-Best and tallying, which simplify the use of cues in different ways. Their limitations become visible because the omitted information is specified. [@wheeler2024, § 5.2]

For the warehouse, the rule might be: inspect the package shape, stop if it matches the fragile class, and add protection. Its weakness is that it treats other evidence as unnecessary. A broken seal or a revised supplier specification might defeat that assumption.

## Beyond the chapter

### Simplicity and prediction

Wheeler’s bias–variance discussion explains why a complicated model can fit noise and perform poorly on new cases. A simpler model can sometimes reduce total error by constraining that fit. The trade-off depends on the loss measure, so it cannot become a universal proof that less information is better. [@wheeler2024, § 3.5]

In the fictional warehouse, recording many unreliable features could create a complicated but poor classifier. Yet ignoring a reliable new label could also produce avoidable damage. The procedure should be compared with alternatives using suitable information and future cases, rather than rewarded merely for being simple.

### Rationality does not mean whatever happens

An ecological account still needs a criterion of success. Saving inspection time while damaging expensive contents may fail the relevant task. A rule can be understandable under constraints without being optimal or morally permissible. Descriptive explanation, normative evaluation, and practical advice remain separate projects. [@wheeler2024, § 1.5]

Nor must a heuristic be unconscious. Wheeler contrasts Gigerenzer’s algorithmic approach with classifying heuristics as necessarily System 1 thinking. A worker can deliberately apply a simplified rule. The complexity of a rule and the manner of its execution are different dimensions. [@wheeler2024, § 5.2]

Read [heuristics and biases](deeper:14-psychology-of-reasoning/heuristics-and-biases) for competing research questions and [dual-process theories](deeper:14-psychology-of-reasoning/dual-process-theories) for processing distinctions. The useful question is which procedure works under which conditions, and how one can detect when the fit has changed.

## Sources

### Where to go next

Wheeler’s entry supplies the secondary account of environmental fit, resource limits, specific algorithms, and prediction trade-offs used here. Read the qualifications with the examples. The warehouse illustration is invented; it does not establish a measured superiority of one workplace procedure. [@wheeler2024, § 1.5, 3, 3.1, 3.5, 5.2]
