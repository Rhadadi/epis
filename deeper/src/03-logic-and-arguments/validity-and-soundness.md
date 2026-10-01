---
tier: A
status: published
updated: 2026-10-01
---

> **In short.** A valid argument is one where the premises cannot all be true while the conclusion is false; a sound argument is a valid one whose premises are true. That much is in every textbook. Underneath lies a hard question: *why* can't they? Not because of any fact about the world, logicians say, but because of the argument's form. Saying what "form" means, and which kind of "cannot" is in play, turned out to be one of the central problems of twentieth-century logic, and the answers still divide logicians over whether a contradiction really implies everything.

## Re-learn

### Step by step

#### 1. Validity is about the link, not the parts

"A deductive argument is said to be valid if and only if it takes a form that makes it impossible for the premises to be true and the conclusion nevertheless to be false" [@val-snd-iep]. The premises need not be true. "All toasters are items made of gold. All items made of gold are time-travel devices. Therefore, all toasters are time-travel devices" is valid: "if they were true, their truth would logically guarantee the conclusion's truth" [@val-snd-iep].

#### 2. Form decides

"According to the dominant understanding among logicians, the validity or invalidity of an argument is determined entirely by its logical form." The form is "that which remains of it when one abstracts away from the specific content", leaving words like "all", "and", "not" and "some" [@val-snd-iep]. "All tigers are mammals; no mammals are creatures with scales; so no tigers are creatures with scales" and "All spider monkeys are elephants; no elephants are animals; so no spider monkeys are animals" share one valid form; only the first is sound [@val-snd-iep].

#### 3. Soundness adds truth

"A deductive argument is sound if and only if it is both valid, and all of its premises are actually true" [@val-snd-iep]. Sound arguments "always end with true conclusions". But "both invalid, as well as valid but unsound, arguments can nevertheless have true conclusions", so "One cannot reject the conclusion of an argument simply by discovering a given argument for that conclusion to be flawed" [@val-snd-iep].

#### 4. Invalidity is shown by counterexample

"The model-centered approach to logical consequence takes the validity of an argument to be absence of counterexample." There are two kinds: "an argument of the same form for which the premises are clearly true and the conclusion is clearly false", or "a circumstance in which the premises are true and the conclusion is false" [@beall-sagi2026, § 3.1].

### Common confusions

- **True premises and a true conclusion make a valid argument.** "All popes reside at the Vatican. John Paul II resides at the Vatican. Therefore, John Paul II is a pope." Everything in it is true, but "the conclusion's truth isn't guaranteed by the premises' truth": it has the same form as "All basketballs are round. The Earth is round. Therefore, the Earth is a basketball" [@val-snd-iep].
- **The grammar shows the form.** "Tony is a ferocious tiger" lets you infer that Tony is a tiger; "Clinton is a lame duck" does not let you infer that Clinton is a duck. "The logical form of a statement is not always as easy to discern as one might expect" [@val-snd-iep].
- **"Sound" means one thing.** In mathematical logic, a whole proof system "is said to be sound if and only if all theorems derivable from the axioms of the logical calculus are semantically valid" [@val-snd-iep]. That is a property of a system, not of an argument; its partner, completeness, says that "an argument is valid only if it is derivable" [@shapiro-kissel2026, preamble].

## The full story

### How the idea developed

::: timeline From Aristotle to models
- **4th century BCE** · Aristotle defines a deduction as speech in which, certain things being supposed, something different "results of necessity because of their being so", and proves invalidity by counterexample [@smith2022, § 3; @smith2022, § 5.3].
- **3rd century BCE** · Chrysippus: an argument is valid if the conditional from its premises to its conclusion is true; it is "true", that is sound, if it is also valid with true premises [@durand-baltzly2023, § 3.4].
- **1930** · Gödel proves the completeness of first-order logic: every valid argument is derivable [@shapiro-kissel2026, § 5].
- **1936** · Tarski gives the model-theoretic definition of logical consequence [@beall-sagi2026, § 3.1].
- **20th century** · Proof systems multiply, "from so-called Hilbert proofs, with simple rules and complex axioms, to natural deduction systems" [@beall-sagi2026, § 3.2].
:::

The two ancient definitions already differ in an instructive way. Aristotle requires the conclusion to be "different from what is supposed", which rules out an argument whose conclusion repeats a premise; "Modern notions of validity regard such arguments as valid, though trivially so" [@smith2022, § 3.2]. Some ancient readers took his wording to exclude one-premise arguments, and some to exclude arguments whose premises are irrelevant to the conclusion [@smith2022, § 3.2]. Those two exclusions return, two thousand years later, in the dispute over explosion below.

### What kind of "cannot"?

Beall, Restall and Sagi put the starting point plainly: in a deductively valid argument, the truth of the premises is "necessarily sufficient" for the truth of the conclusion [@beall-sagi2026, § 1]. But necessity comes in several kinds, and each candidate fails in an instructive way.

::: positions Which necessity makes an argument valid?
| Kind of necessity | The idea | The problem |
|---|---|---|
| Metaphysical | No possible world has true premises and a false conclusion | Too broad: "x is water. Therefore, x is H₂O" preserves truth necessarily, yet it took empirical discovery |
| Conceptual or analytic | The conclusion is contained in the meanings of the premises | Quine doubted the analytic/synthetic line; and "Peter is Greg's mother's brother's son, so Peter is Greg's cousin" is analytic but not formal |
| A priori | Validity can be known without experience | Rules out the water case, but still lets in the cousin case |
| Formal | Truth is preserved in virtue of form alone | Needs an account of what form is |
:::

[@beall-sagi2026, § 1; @beall-sagi2026, § 2]. The water argument is the clearest case. If water is necessarily H₂O, then "x is water. Therefore, x is H₂O" can never take you from truth to falsehood, "but it seems a long way from being deductively valid". "It was a genuine discovery that water is H₂O, one that required significant empirical investigation" [@beall-sagi2026, § 1]. Valid arguments, by contrast, should be recognisable without experiment.

So "The strongest and most widespread proposal for finding a narrower criterion for logical consequence is the appeal to formality" [@beall-sagi2026, § 2]. The cousin argument fails this test: it is "a material consequence and not a formal one, because to make the step from the premise to the conclusion we need more than the structure or form of the claims involved" [@beall-sagi2026, § 2].

### What is form?

Every presentation of logic relies on schemes, of which "Aristotle's syllogistic is a proud example", such as *Ferio*: No F is G; some H is G; so some H is not F [@beall-sagi2026, § 2]. Perhaps an argument is formally valid when it falls under a scheme every instance of which is valid. But that is not enough, because the cousin argument also falls under such a scheme ("x is y's mother's brother's son. Therefore, x is y's cousin"), every instance of which is valid [@beall-sagi2026, § 2]. We need to say why some schemes count as properly formal. Beall, Restall and Sagi distinguish three proposals [@beall-sagi2026, § 2]:

- **Total generality.** Tarski proposed that an operation counts as logical "if it was invariant under permutations of objects". Identity passes this test, but "the mother-of relation is not". Negation passes; "‘JC believes that’ fails".
- **Abstractness.** Connectives and quantifiers "do not add new semantic content to expressions, but instead add only ways to combine and structure semantic content". "Mother" and "cousin" add content.
- **Norms for any thought.** Whatever we think about, "it makes sense to conjoin, disjoin and negate our thoughts". On this picture, the norms of valid argument "apply to thought irrespective of the particular content of that thought".

The IEP's anonymous entry adds a reminder that the boundary is still contested. "My table is circular. Therefore, it is not square shaped." "Juan is a bachelor. Therefore, he is not married." It seems "impossible for the premises to be true while the conclusion is false", yet the surface form, "x is F; Therefore, x is not G", is invalid [@val-snd-iep]. Logicians respond in three ways: the arguments have implicit premises ("Nothing is both circular and square shaped"), the necessity is not logical necessity, or the real form of "bachelor" is "adult unmarried male" [@val-snd-iep]. The first response is the same move as [natural language deductivism](deeper:03-logic-and-arguments/the-toulmin-model).

### Models and proofs

Twentieth-century logic made validity precise in two ways [@beall-sagi2026, § 3].

**Models.** A model assigns a domain of objects and meanings to the non-logical words. "An argument is valid if in any model in which the premises are true ..., the conclusion is true too." The definition "traces back to Tarski (1936)" and is "one of the most successful mathematical explications of a philosophical concept to date": it captures necessity by looking at all models and formality by letting the non-logical vocabulary mean anything [@beall-sagi2026, § 3.1]. The worry, raised by Etchemendy, is that models "are just sets, which are merely mathematical objects". Why should truth in all of them guarantee truth in every possible circumstance [@beall-sagi2026, § 3.1]?

**Proofs.** On the proof-centred approach, validity "amounts to there being a proof of the conclusions from the premises". This highlights the epistemic side: "if a reasoner has grounds for the premises of an argument, and they infer the conclusion via a series of applications of valid inference rules, they thereby obtain grounds for the conclusion" [@beall-sagi2026, § 3.2]. Pushed further, it becomes inferentialism, the view that the meaning of a logical word is fixed by its rules, and the necessity of validity becomes, in Prawitz's phrase, "necessity of thought" [@beall-sagi2026, § 3.2].

For first-order logic the two approaches agree. A deductive system can be "sound", deriving only valid arguments, and "complete", deriving all of them, as Gödel proved [@shapiro-kissel2026, preamble; @shapiro-kissel2026, § 5].

### Explosion: does a contradiction imply everything?

On the classical definition, an argument with inconsistent premises is valid whatever its conclusion, because there is no circumstance in which all the premises are true. The principle that from a contradiction anything follows is "sometimes colorfully called “explosion”" [@shapiro-kissel2026, § Relevance and paraconsistency].

::: argument Why classical validity "explodes"
1. An argument is valid if there is no case in which all its premises are true and its conclusion false.
2. There is no case in which both "P" and "not-P" are true.
3. So there is no case in which the premises "P" and "not-P" are true and an arbitrary conclusion Q is false.
4. So "P, not-P, therefore Q" is valid, for any Q.
:::

Logics that reject explosion are called paraconsistent, and they have two kinds of defenders [@shapiro-kissel2026, § Relevance and paraconsistency]. Relevance logicians insist "that in a valid argument, the premises must be relevant to the conclusion"; they reject premise 1 as an account of validity. Dialetheists hold "that some contradictions ... are true", the liar being a candidate; for them premise 2 fails, and since "any true contradiction would entail every sentence" under explosion, their logic must be paraconsistent [@shapiro-kissel2026, § Relevance and paraconsistency]. Intuitionists object from another direction, rejecting the law of excluded middle as a law of logic [@shapiro-kissel2026, § 6.3].

### One validity or many?

This leaves a question that Beall, Restall and Sagi close with. "The orthodoxy, logical monism", says there is "one relation of deductive consequence, and different formal systems do a better or worse job of modelling that relation" [@beall-sagi2026, § 5]. The logical contextualist says that validity depends on the subject matter: excluded middle may be valid in a classical mathematics textbook but not in an intuitionistic one, "or in a context where we reason about fiction or vague matters". The pluralist says that even for one argument in one context, "there are sometimes different things one should say with respect to its validity" [@beall-sagi2026, § 5]. The argument from a contradiction to an unrelated conclusion is the pluralist's example: valid in one precise sense, since its form rules out true premises with an untrue conclusion, and invalid in another, since the form does not ensure that "the truth of the premises leads to the truth of the conclusion" [@beall-sagi2026, § 5].

### Validity is not enough

A valid argument with true premises can still prove nothing. Biro's example: "All members of the committee are old Etonians; Fortesque is a member of the committee; Fortesque is an old Etonian." Given the second premise, the first "cannot be known to be true unless the conclusion is known to be true". On Biro and Siegel's epistemic approach, the argument "despite the fact that it is valid, is non-serious, it begs the question, and it is a fallacy" [@hansen2024b, § 3.5]. If there were an independent way to know the first premise, such as a bylaw that only old Etonians may sit on the committee, the argument would be serious [@hansen2024b, § 3.5].

So a good deductive argument needs three things: valid form, true premises, and premises that can be known independently of the conclusion and are more acceptable than it [@hansen2024b, § 3.5]. That is the logic behind the chapter's fourth fact, that "Validity is not the same as persuasiveness".

## Beyond the chapter

### What the chapter leaves out

- **Validity in Indian logic.** Indian logicians assessed an inference by the "three forms" (*tri-rūpa*) that a reason must satisfy. In Dharmakīrti's statement: the reason definitely exists in the subject, exists only in things like the subject, and does not exist at all in things unlike the subject. "Specious reasons" are classified by which form they fail [@gillon2024, § 4.2]. Dharmakīrti saw the problem of induction lurking here: never having met something with the reason but without the property is "no guarantee" that no such thing exists [@gillon2024, § 4.2].
- **Inductive validity.** Some logicians call inductively strong arguments "inductively valid": their premises are "very likely (but not necessarily) sufficient for the truth of the conclusion" [@beall-sagi2026, § 1]. See [Strength and cogency](deeper:03-logic-and-arguments/strength-and-cogency).

### What the chapter simplifies

- **"Validity is about form, not content."** This is the dominant view, but "there is some dissent", and arguments like "Juan is a bachelor. Therefore, he is not married" show why [@val-snd-iep]. Whether such arguments are formally valid depends on what counts as form, which is an open question [@beall-sagi2026, § 2].
- **"It is impossible for all its premises to be true and its conclusion false."** Which impossibility? Metaphysical impossibility makes "x is water. Therefore, x is H₂O" valid, and most logicians do not accept that [@beall-sagi2026, § 1].

### Connections

- [The method of counterexample](03-logic-and-arguments.md#the-method-of-counterexample), Aristotle's method and the model theorist's.
- [The fallacy fallacy](15-fallacies.md#the-fallacy-fallacy), for why a bad argument does not refute its conclusion.
- [Reason and the a priori](07-sources-of-knowledge.md#reason-and-the-a-priori), for how validity can be known without experience.

## Sources

### Where to go next

- **Start here, free:** "Validity and Soundness" in the *Internet Encyclopedia of Philosophy* [@val-snd-iep].
- **The deep question:** Beall, Restall and Sagi, "Logical Consequence", sections 1–3 and 5 [@beall-sagi2026].
- **Rival logics:** Shapiro and Kissel, "Classical Logic", section 6 [@shapiro-kissel2026].
- **History:** Smith, "Aristotle's Logic", section 3 [@smith2022]; Durand, Shogry and Baltzly, "Stoicism", section 3.4 [@durand-baltzly2023].
- **When validity is not enough:** Hansen, "Fallacies", section 3.5 [@hansen2024b].
