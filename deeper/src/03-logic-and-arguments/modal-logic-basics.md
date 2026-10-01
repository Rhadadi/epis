---
tier: B
status: published
updated: 2026-10-01
---

> **In short.** Modal logic is the logic of "necessarily" and "possibly", and, by extension, of "ought", "will", "believes" and "knows". It needs something truth tables cannot give: whether "necessarily A" is true does not depend only on whether A is true. Possible worlds supply the missing ingredient. Different readings of the box obey different axioms, and choosing the axioms is where the philosophy happens: the principle that what you know you know you know is one such axiom.

## Re-learn

### Step by step

#### 1. One family, many readings

"A modal is an expression (like ‘necessarily’ or ‘possibly’) that is used to qualify the truth of a judgement." The same machinery covers "logics for belief, for tense and other temporal expressions, for the deontic (moral) expressions such as ‘it is obligatory that’" [@garson2024, preamble]. Epistemic logic writes "x knows that ..." as an operator of the same kind [@garson2024, § 1].

#### 2. Why truth tables are not enough

"The truth value of A does not determine the truth value for □A." When A is "Dogs are dogs", □A is true; when A is "Dogs are pets", □A is false, though both A's are true [@garson2024, § 6]. So modal semantics adds possible worlds: □A is true if A is true in every world relevant to this one [@garson2024, § 6].

#### 3. The box behaves like "all"

"In K, the operators □ and ◇ behave very much like the quantifiers ∀ (all) and ∃ (some)" [@garson2024, § 2]. "Possibly A" is "not necessarily not-A", just as "something is F" is "not everything is not-F". And □A ∨ □B entails □(A ∨ B) but not the reverse, just as for "all" [@garson2024, § 2].

#### 4. Axioms fit readings

The axiom (M), □A → A, "claims that whatever is necessary is the case". It would be wrong "were □ to be read ‘it ought to be that’, or ‘it was the case that’" [@garson2024, § 2]. Read the box as "knows", and (M) says that knowledge implies truth. Read it as "believes", and (M) fails, since beliefs can be false. Adding axiom (4), □A → □□A, gives the system S4 [@garson2024, § 2]. Read epistemically, that is the KK principle, discussed in [Knowing that you know](05-the-nature-of-knowledge.md#knowing-that-you-know).

### Common confusions

- **There is one modal logic.** There is a family. "Many logicians believe that M is still too weak to correctly formalize the logic of necessity and possibility", and S4 and S5 add stronger principles for strings of operators: in S5, "strings containing both boxes and diamonds are equivalent to the last operator in the string" [@garson2024, § 2].

## Beyond the chapter

### What the chapter leaves out

- **Axioms and frames.** Each axiom corresponds to a condition on how worlds are related. Axiom (4) matches a transitive relation, and the axiom "(D): □A → ◇A" matches seriality, the condition that every world has some world related to it [@garson2024, § 7]. So debates about axioms become debates about the structure of the relevant worlds.
- **Quantifying into modal contexts.** "Quine (1953) has famously argued that quantifying into modal contexts is simply incoherent". Garson reports that "Quine's complaints do not carry the weight they once did" [@garson2024, § 16]. A live issue remains: is there one domain of all possible objects, or does each world contain only the objects that exist there [@garson2024, § 16]? That is the formal side of the chapter's *de re*/*de dicto* distinction.

### Connections

- [Necessary and contingent](01-what-is-epistemology.md#necessary-and-contingent) (Chapter 1).
- [Sensitivity and tracking](05-the-nature-of-knowledge.md#sensitivity-and-tracking) and [Safety](05-the-nature-of-knowledge.md#safety), which use nearby possible worlds.
- [Formal fallacies](03-logic-and-arguments.md#formal-fallacies), for the modal fallacy.

## Sources

### Where to go next

- **Start here, free:** Garson, "Modal Logic", sections 1–2 and 6 [@garson2024].
