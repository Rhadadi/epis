---
tier: B
status: published
updated: 2026-10-01
---

> **In short.** Propositional logic studies how the truth of compound sentences depends on the truth of their parts, joined by "not", "and", "or" and "if". Its strength is that whether a conclusion follows should not depend on what the words "man" or "mortal" mean, only on the connectives. Its weak point is "if": the logician's material conditional is clean and useful, but whether it captures what ordinary "if" means is one of the oldest disputes in logic, and the dispute is still open.

## Re-learn

### Step by step

#### 1. What the subject is

Propositional logic is the study of the meanings and inferential relations of sentences "based on the role that a specific class of logical operators called the propositional connectives have in determining those sentences' truth or assertability conditions" [@franks2024, preamble]. Whether "Socrates is mortal" follows from "All men are mortal, and Socrates is a man" "ought not depend, it is thought, on what words like “mortal” or “man” mean" [@franks2024, preamble].

#### 2. Truth tables are a decision procedure

Classical propositional logic is decidable. For any formula, list every combination of truth values for its atoms and compute the result. A formula with *n* atoms has a truth table with exactly 2*ⁿ* rows, so "Completing the truth table is therefore a finite determinate task" [@franks2024, § 2.1.5]. A formula with ten atoms needs 1,024 rows; that is why the method is certain but quickly impractical.

#### 3. "If" is the problem

The material conditional is false only when the antecedent is true and the consequent false, so it is equivalent to "not-A or B" [@franks2024, § 2.1.4]. Treating it as the meaning of English "if ... then" is, in Franks's word, "controversial", and treating it as "implies" is an outright error [@franks2024, § 2.1.4]. Implication is about all conditions, not just the actual truth values: "B could be true but, for all that, not be implied by A because under some other situation A could be true while B is false" [@franks2024, § 2.1.4].

### Common confusions

- **"If A then B" is true means A implies B.** No. The material conditional "does not express any implication relation between A and B". What does express implication is the claim that the conditional is a logical validity: B follows from A exactly when "A ⊃ B" is true in every row of the truth table [@franks2024, § 2.1.4].

## Beyond the chapter

### What the chapter leaves out

- **An ancient debate.** The view that ordinary conditionals are truth-functional "is apparently ancient": it is attributed to the Greek logician Philo, and Chrysippus refers to it in his early systematization of propositional logic. In modern times Peirce, Grice and Jackson defended it, "But its detractors have been many" [@franks2024, § 2.1.4].
- **Frege's own doubts.** Frege put the material conditional at the centre of his logic, yet he denied that it expressed the conditional of ordinary language: "the causal connection implicit in the word ‘if’ …is not expressed by our symbols" [@franks2024, § 2.1.4]. He chose it for "its role internal to logical theory" [@franks2024, § 2.1.4].
- **Conditionals as conditional probabilities.** Ramsey suggested that "If A, then B" is best understood through the probability of B given A. In 1976 Lewis proved that conditionals so understood "not only fail to be truth-functional but in fact are not even propositions" [@franks2024, § 2.1.4].
- **Logics that repair "if".** Relevance logicians trace the oddities of the material conditional to conditionals "whose antecedents are irrelevant to their consequents" and require the antecedent and consequent to share content. Connexive logicians require that the negation of the consequent be incompatible with the antecedent [@franks2024, § 3.3]. Many-valued logics, such as Kleene's three-valued logics, drop the assumption that every sentence is simply true or false [@franks2024, § 3.1].

### What the chapter simplifies

- **"These are the paradoxes of material implication."** Strictly, the material conditional is not an implication at all [@franks2024, § 2.1.4]; the paradoxes show the gap between it and ordinary "if".
- **"The simplest modern logic."** It is, but its history is long. "As early as Aristotle it was observed that propositional connectives have a logical significance", though propositional logic as a subject "did not emerge until the nineteenth century" [@franks2024, preamble].

### Connections

- [Valid argument forms](03-logic-and-arguments.md#valid-argument-forms) and [Formal fallacies](03-logic-and-arguments.md#formal-fallacies), which apply these rules.
- [Necessary and sufficient conditions and their limits](04-language-concepts-and-definitions.md#necessary-and-sufficient-conditions-and-their-limits) (Chapter 4).

## Sources

### Where to go next

- **Start here, free:** Franks, "Propositional Logic", sections 1–2.1.4 [@franks2024].
- **Beyond classical logic:** Franks, "Propositional Logic", section 3 [@franks2024].
