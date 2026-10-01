---
tier: B
status: published
updated: 2026-10-01
---

> **In short.** Predicate logic looks inside sentences. It splits them into names, predicates and the quantifiers "every" and "some", and so it can show why "everyone loves someone" does not imply "someone is loved by everyone". Frege's great step was to treat a verb like "loves" as a function of two arguments, which let one rule handle inferences that Aristotle's logic treated as unrelated. The result became the standard logic of mathematics and philosophy, though whether it is the one correct logic is still argued.

## Re-learn

### Step by step

#### 1. What Frege changed

In Aristotelian logic, the subject of a sentence and the object of its verb "are not on a logical par". The inference from "John loves Mary" to "Something loves Mary" and the inference to "John loves something" were governed by different rules: "In Aristotelian logic, these inferences have nothing in common" [@zalta2026, § 2.2.3]. Frege treated "loves" as a function of two arguments, so "a single rule governs both" [@zalta2026, § 2.2.3]. This "freed him from the limitations of the ‘subject-predicate’ analysis of ordinary language sentences" [@zalta2026, § 2.2.3].

#### 2. Quantifiers bind variables

In modern notation, ∀ ("every") and ∃ ("some") "are called the ‘universal’ and ‘existential’ quantifier, respectively", and the variable after them is "bound by the quantifier" [@zalta2026, § 2.2.2]. Once quantifiers are written out, their order is visible, and "everyone has a mother" can be seen not to imply "someone is everyone's mother".

#### 3. A formal language and a natural one

How does a formula relate to the English sentence it translates? One view is that sentences "have underlying logical forms and that these forms are displayed by formulas of a formal language". Another, "held at least in part by Gottlob Frege and Wilhelm Leibniz", is that natural languages are "fraught with vagueness and ambiguity" and should be replaced by formal ones. A third treats a formal language as a model, which "displays certain features of natural languages, or idealizations thereof, while ignoring or simplifying other features" [@shapiro-kissel2026, § 1].

### Common confusions

- **The formula is what the sentence really means.** That is only one of the views above. On the modelling view, translating "All that glitters is not gold" into logic is a choice between readings, not a discovery of the hidden one [@shapiro-kissel2026, § 1].

## Beyond the chapter

### What the chapter leaves out

- **Proof and completeness.** First-order logic has a deductive system that is sound and complete: an argument is derivable only if valid, and "an argument is valid only if it is derivable" (Gödel, 1930) [@shapiro-kissel2026, preamble; @shapiro-kissel2026, § 5].
- **Is it the One True Logic?** Some philosophers hold that classical first-order logic is "uniquely correct, as the One True Logic", among them Quine and Williamson [@shapiro-kissel2026, § 6]. Critics point to its expressive limits: notions like "finitude, countability, minimal closure, natural number" cannot be expressed in it [@shapiro-kissel2026, § 6]. The alternatives are a different single logic, logical pluralism ("a variety of different logical all qualify as correct"), or logical nihilism [@shapiro-kissel2026, § 6].
- **Peirce.** Frege was not alone. Peirce invented "a quantifier-and-variable syntax that (except for its specific symbols) is identical to the much later Russell-Whitehead syntax" [@burch2024, § 13].

### What the chapter simplifies

- **"Invented by Frege in 1879."** Frege's *Begriffsschrift* (1879) contains the principal elements of his system, but it "was neither widely understood nor well-received"; his mature statement came in the *Grundgesetze* (1893/1903) [@zalta2026, § 1; @zalta2026, § 2.1]. Modern predicate logic is also "a descendant of Frege's system" rather than the system itself: it takes predication as basic, where Frege analysed it in terms of functions [@zalta2026, § 2.1.2].

### Connections

- [Categorical logic and syllogisms](03-logic-and-arguments.md#categorical-logic-and-syllogisms), the logic Frege replaced.
- [Sense and reference](04-language-concepts-and-definitions.md#sense-and-reference), Frege's other great contribution.
- [Formal fallacies](03-logic-and-arguments.md#formal-fallacies), for the quantifier-shift fallacy.

## Sources

### Where to go next

- **Start here, free:** Zalta, "Gottlob Frege", section 2.2 [@zalta2026].
- **The logic itself:** Shapiro and Kissel, "Classical Logic", sections 1–2 and 6 [@shapiro-kissel2026].
