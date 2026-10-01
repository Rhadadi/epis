---
tier: A
status: draft
updated: 2026-10-01
---

> **In short.** Bread has always nourished you, so you expect the next loaf to nourish you too. Hume asked what reasoning takes you from the first fact to the second, and argued that none can. A priori reasoning cannot show that nature will stay the same, because its changing involves no contradiction. Reasoning from experience cannot show it either, because every such argument already assumes that the future will resemble the past. Hume did not conclude that we should stop expecting bread to nourish us. He concluded that the expectation comes from custom, not reason. Whether that verdict is a fact about psychology or a sceptical judgment about justification is still argued over.

## Re-learn

### Step by step

#### 1. The question

Hume did not doubt that we draw inferences from the observed to the unobserved. He asked what they rest on. "The bread, which I formerly eat, nourished me; that is, a body of such sensible qualities was, at that time, endued with such secret powers: but does it follow, that other bread must also nourish me at another time, and that like sensible qualities must always be attended with like secret powers? The consequence seems nowise necessary." There is, he says, "a process of thought, and an inference, which wants to be explained" [@hume1748, IV.ii].

#### 2. The fork

Hume divides all reasoning into two kinds, about "relations of ideas" and about "matters of fact" [@henderson2024, § 1]. Reasoning of the first kind cannot ground the inference, because "it implies no contradiction that the course of nature may change", and what can be conceived without contradiction "can never be proved false by any demonstrative argument or abstract reasoning _a priori_" [@hume1748, IV.ii].

#### 3. The circle

Reasoning of the second kind cannot ground it either. "All our experimental conclusions proceed upon the supposition that the future will be conformable to the past. To endeavour, therefore, the proof of this last supposition by probable arguments, or arguments regarding existence, must be evidently going in a circle, and taking that for granted, which is the very point in question" [@hume1748, IV.ii]. Philosophers now call that supposition the "Uniformity Principle" [@henderson2024, § 1].

#### 4. Custom, not reason

Hume's own answer is that the step is taken by habit. "This principle is Custom or Habit", a propensity produced "without being impelled by any reasoning or process of the understanding" [@hume1748, V.i]. It is no less effective for that. Hume calls the fit between our habits and the world "a kind of pre-established harmony between the course of nature and the succession of our ideas" [@hume1748, V.ii].

### Common confusions

- **Hume told us to stop reasoning inductively.** He said the opposite: "Nature will always maintain her rights, and prevail in the end over any abstract reasoning whatsoever", and there is "no danger" that our reasonings from experience "will ever be affected by such a discovery" [@hume1748, V.i].
- **"Demonstrative" just means "deductive".** It is often read that way, but on that reading Hume's first premise would be false, since a deductive argument can have a contingent conclusion. Recent commentators argue that in Hume's context the distinction "has little to do with whether or not the argument has a deductive form" [@henderson2024, § 2].
- **The problem is that induction is uncertain.** Settling for probability does not escape it. Russell grants that "probability is all we ought to seek" [@russell1912, ch. VI], but the question remains what makes a high probability reasonable to expect.

## The full story

### How the problem developed

::: timeline From Hume to machine learning
- **1739** · Hume's *Treatise* raises the problem in Book 1, part iii, section 6 [@henderson2024, preamble].
- **1748** · The *Enquiry* gives "a shorter version of the argument" in Section IV [@henderson2024, preamble].
- **1764** · Bayes's essay on inverse probability is published after his death; it may have been written "in direct response to the publication of Hume's Enquiry" [@henderson2024, § 3.3].
- **1781** · Kant argues, in reply to Hume, that synthetic a priori knowledge is possible [@henderson2024, § 3.1].
- **1912** · Russell's chicken, in *The Problems of Philosophy* [@russell1912, ch. VI].
- **1955** · Goodman's "new riddle of induction" asks which regularities to project at all [@henderson2024, § 4.2].
- **1990s** · The "No-Free-Lunch theorems" give Hume's first horn a form in learning theory [@henderson2024, § 3.4].
:::

### Hume's question

Hume introduces the problem while analysing cause and effect. For him causation is the only relation by which "we can go beyond the evidence of our memory and senses" [@henderson2024, § 1]. Suppose gunpowder is in front of you and you expect an explosion. That expectation rests on past experience of a "constant conjunction" between the two. What Hume wants is the reasoning that links the past conjunction to the present expectation: if the inference is made by a "chain of reasoning", he would like to know what that reasoning is [@henderson2024, § 1].

The bread example locates the gap precisely. Experience tells us about "those precise objects only, and that precise period of time, which fell under its cognizance: but why this experience should be extended to future times, and to other objects, which for aught we know, may be only in appearance similar; this is the main question on which I would insist" [@hume1748, IV.ii]. The colour and texture of bread do not reveal its "secret powers" of nourishment. If they did, "we could infer these secret powers from the first appearance of these sensible qualities, without the aid of experience" [@hume1748, IV.ii].

### The argument, premise by premise

The Stanford reconstruction sets the argument out as a dilemma about an inference from "All observed instances of A have been B" to "The next instance of A will be B" [@henderson2024, § 2].

::: argument Hume's dilemma
1. There are only two kinds of arguments: demonstrative and probable.
2. The inductive inference presupposes the Uniformity Principle (UP).
3. A demonstrative argument establishes a conclusion whose negation is a contradiction.
4. The negation of the UP is not a contradiction.
5. So there is no demonstrative argument for the UP.
6. Any probable argument for the UP presupposes the UP.
7. An argument for a principle may not presuppose that principle.
8. So there is no probable argument for the UP, and hence no argument for it at all.
9. So the inductive inference has no chain of reasoning behind it, and is not justified.
:::

[@henderson2024, § 2]. Each premise has been attacked. Premise 3 falls if there is synthetic a priori knowledge, as Kant held [@henderson2024, § 3.1]. Premise 7 falls if some circular arguments are acceptable. Premise 2 falls if inductive inferences rest on many specific assumptions rather than one general principle. And the step to the final line needs a further premise, that an inference without a chain of reasoning behind it is not justified. Some readers deny that Hume ever made that step [@henderson2024, § 2]. The replies are traced in [Responses to Hume](deeper:09-induction-probability-bayes/responses-to-hume).

Hume closes off one more route before the dilemma. Our grounds could be immediate (sensation or intuition) or inferential (demonstration or probable argument). Sensation is ruled out because it "cannot tell us anything about the unobserved, but only the currently observed", and intuition because the principle "is not intuitive" [@qu-radcliffe2026, § 2.3].

::: original Hume, *An Enquiry Concerning Human Understanding*, Section IV, Part II
> My practice, you say, refutes my doubts. But you mistake the purport of my question. As an agent, I am quite satisfied in the point; but as a philosopher, who has some share of curiosity, I will not say scepticism, I want to learn the foundation of this inference. No reading, no enquiry has yet been able to remove my difficulty, or give me satisfaction in a matter of such importance. Can I do better than propose the difficulty to the public, even though, perhaps, I have small hopes of obtaining a solution? We shall at least, by this means, be sensible of our ignorance, if we do not augment our knowledge.

The passage separates two questions the chapter runs together. As an agent, Hume has no doubts and expects none to arise. As a philosopher, he wants "the foundation" of a practice he does not intend to give up. A few paragraphs on he presses the point with a child who, having once been burnt, keeps away from candles: if the child's understanding reached this by argument, "I may justly require you to produce that argument", and the argument cannot be "abstruse", since it is "obvious to the capacity of a mere infant".
:::

[@hume1748, IV.ii]

### Custom and the pre-established harmony

Section V gives Hume's "solution", which is a description rather than a justification. Having found flame and heat, or snow and cold, always joined, "the mind is carried by custom to expect heat or cold". This is "a species of natural instincts, which no reasoning or process of the thought and understanding is able, either to produce, or to prevent" [@henderson2024, § 1].

Hume does not treat the instinct as second best. He suggests it may be less "liable to error and mistake" than "the fallacious deductions of our reason, which is slow in its operations" [@henderson2024, § 2]. Later in the *Treatise* he even offers "rules" and a "logic" for good causal inference, which suggests he did not think induction wholly without rational standards [@henderson2024, § 2].

### What did Hume conclude?

The argument's conclusion is that inductive inference is not "founded on" reason, and that phrase can be read two ways. On one reading it reports "a psychological fact", that reason does not cause the inductive step; on the other "a sceptical one", that reason cannot justify it [@qu-radcliffe2026, § 2.3]. The live debate turns on what Hume meant by "reason".

::: positions What does "not founded on reason" mean?
| Reading | Who | What Hume shows | Difficulty |
|---|---|---|---|
| Descriptive | Garrett, Owen | No reasoning process produces the inductive step; a thesis in cognitive psychology | Hume's argument seems to have normative force, and has nearly always been read so |
| Deductivist | Flew, Stove | Only that induction has no deductive justification | Rejected by most recent commentators (Garrett, Millican) |
| Anti-rationalist | Beauchamp and Rosenberg | That the rationalists were wrong to think some inductions demonstrative | The argument attacks probable arguments too |
| Externalist | Loeb, Cottrell | That induction lacks internalist justification; externalist justification is left open | Has to show Hume had such a distinction |
| Strongly sceptical | Winkler, Millican | That induction has no rational justification of any kind | Sits awkwardly with Hume's own rules for causal inference |
:::

[@qu-radcliffe2026, § 2.3; @henderson2024, § 2]. One may also read the two books differently, finding "the Treatise's argument to be psychological and Enquiry's to be sceptical" [@qu-radcliffe2026, § 2.3]. Whatever Hume intended, "Hume has throughout history been predominantly read as presenting an argument for inductive skepticism" [@henderson2024, § 2].

### Russell's chicken

Russell gave the problem its most quoted image. "The man who has fed the chicken every day throughout its life at last wrings its neck instead, showing that more refined views as to the uniformity of nature would have been useful to the chicken." Our instincts make us believe the sun will rise tomorrow, "but we may be in no better a position than the chicken which unexpectedly has its neck wrung" [@russell1912, ch. VI].

Russell draws Hume's distinction sharply: we must separate "the fact that past uniformities _cause_ expectations as to the future, from the question whether there is any reasonable ground for giving weight to such expectations" [@russell1912, ch. VI]. And he took the stakes to be high. If Hume's problem cannot be solved, he wrote, "there is no intellectual difference between sanity and insanity" [@henderson2024, preamble].

### Why it still matters

The problem has a modern form in machine learning. Learning algorithms work only if they have "inductive bias", built-in assumptions about the domain, and the "No-Free-Lunch theorems" make the point formally. They "can be interpreted as versions of the argument in Hume's first fork since they establish that there can be no contradiction in the algorithm not performing well" [@henderson2024, § 3.4]. If every logically possible future is weighted equally, any learning algorithm "is expected to have a generalisation error of 1/2, and hence to do no better than guessing at random" [@henderson2024, § 3.4].

## Beyond the chapter

### What the chapter leaves out

- **Two books, two framings.** In the *Treatise* the question is explicitly contrastive: whether "we are determin'd by reason to make the transition, or by a certain association and relation of perceptions". The answer there is the imagination [@henderson2024, § 1].
- **A regress instead of a circle.** Sober, Okasha and Norton argue that Hume's argument "rests on a quantifier shift fallacy". Each inductive inference rests on some specific assumption, but no one assumption underlies them all, so the problem becomes "a regress of inductive justifications" rather than a circle [@henderson2024, § 4.2]. See [Responses to Hume](deeper:09-induction-probability-bayes/responses-to-hume).
- **Hume and Bayes.** The probabilistic tradition that the chapter's later sections teach may have started as a reply to Hume [@henderson2024, § 3.3]. See [Bayes' theorem](deeper:09-induction-probability-bayes/bayes-theorem).

### What the chapter simplifies

- **The Uniformity Principle is vague.** "The future only resembles the past in some respects, but not others. Suppose that on all my birthdays so far, I have been under 40 years old. This does not give me a reason to expect that I will be under 40 years old on my next birthday" [@henderson2024, § 4.2]. That gap is what Goodman's riddle exploits; see [Goodman's new riddle](deeper:09-induction-probability-bayes/goodmans-new-riddle-of-induction).
- **The conclusion.** The chapter's numbered argument ends in "no rational justification". That is the normative reading. Descriptive readers take Hume to be advancing "a 'thesis in cognitive psychology', rather than making a normative claim about justification" [@henderson2024, § 2].

### Connections

- [The early modern revolution](deeper:02-history-of-epistemology/the-early-modern-revolution), for Hume in his setting.
- [Skepticism about induction, other minds, and the past](deeper:08-skepticism/skepticism-about-induction-other-minds-and-the-past).
- [Inductivism and its limits](10-science-and-evidence.md#inductivism-and-its-limits) (Chapter 10).

## Sources

### Where to go next

- **Start here, free:** Henderson, "The Problem of Induction", sections 1–2 [@henderson2024].
- **Hume himself:** *An Enquiry Concerning Human Understanding*, Sections IV and V [@hume1748].
- **Interpretation:** Qu and Radcliffe, "David Hume", section 2.3 [@qu-radcliffe2026].
- **The classic restatement:** Russell, *The Problems of Philosophy*, chapter VI [@russell1912].
