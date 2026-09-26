"""Hand-written parts of the narration scripts.

INTROS replace each chapter's "In this chapter" list with a spoken roadmap.
OUTROS replace the "Further reading" list with a wrap-up and a look ahead.
TABLES say how a table is read aloud, keyed by chapter and first header cell
(or "|" plus the second header cell when the first is empty). A value is either
a template, with {0}, {1}... for the cells of each row, {h0}, {h1}... for the
headers and ":l" to lower-case the first letter, or a list of lines to read
instead of the table.
REPLACE lists (source, spoken) pairs applied to a chapter's markdown before
conversion, for formulas and other passages that need rewording for the ear.
"""

WELCOME = """
Welcome to Mastering Epistemology, the audio edition of a complete guide to knowledge, evidence, and critical thinking.
This recording follows the written guide closely. A few things change for the ear: diagrams are left out, tables are read row by row, links become plain words, and each chapter ends with a spoken quiz, with time for you to think.
The narration is generated with a synthetic voice.
@pause 1.0
"""

INTROS = {
"01": """
Here's the plan. We'll start with a dinner-table argument about a diet, and find six separate epistemological problems hiding inside it.
Then we'll meet the big questions of the field, three different kinds of knowing, and the difference between believing something, being fairly confident of it, and merely accepting it for the sake of argument.
After that come three great distinctions that philosophers have argued over for centuries, a billionaire who offers to pay you to believe that the moon is made of cheese, and a map of the whole field. We'll finish by reading a single news headline through twelve different epistemic lenses.
""",
"02": """
This chapter tells the story of how people have tried to answer the question "How do you know?" over two and a half thousand years.
We'll begin in ancient Greece, with Socrates asking awkward questions and Plato and Aristotle trying to answer them. Then we'll travel to India, the Islamic world, and China, where thinkers built sophisticated theories of knowledge of their own.
Back in Europe, we'll watch Descartes try to rebuild knowledge from the ground up, and see Locke, Hume, Reid, and Kant take up the challenge. Then we'll follow the story through the nineteenth and twentieth centuries to today.
As you listen, watch for the patterns. The same few problems keep coming back in new clothes.
""",
"03": """
This chapter is your workshop. You'll learn to take an argument apart: to find its premises and its conclusion, to tell deduction from induction and abduction, and to see the difference between an argument that is valid and one that is sound.
We'll go through the handful of argument forms you can always trust, and the look-alikes that fool people every day. Then we'll practise on real arguments: filling in hidden premises, reading opponents charitably, and mapping the structure of a debate.
One note for listeners. The written chapter uses some logical symbols and a truth table. In this recording I'll say them in plain words.
""",
"04": """
Many disagreements aren't really about the facts. They're about words. In this chapter we'll look at how language can sharpen thinking, or quietly sabotage it.
We'll cover the difference between what words mean and what they refer to, the kinds of definition and how to judge them, ambiguity and vagueness, and verbal disputes, where two people argue past each other without noticing.
Then we'll turn to the rhetoric of words: loaded language, framing, and concepts that are contested by their very nature. Finally, we'll look at the gap between facts and values, and at the philosopher's favourite tool, the thought experiment.
""",
"05": """
Here's a question that sounds simple. What's the difference between knowing something and just happening to believe it truly?
For more than two thousand years, a tidy answer seemed to work: knowledge is justified true belief. Then, in 1963, a three-page paper by Edmund Gettier broke it. In this chapter we'll see exactly how, and follow the many attempts to repair the damage: reliability, sensitivity, safety, virtue, and the radical idea that knowledge can't be analyzed at all.
Along the way we'll ask why knowledge is worth more than a lucky guess, and what understanding and wisdom add to it.
""",
"06": """
A belief can be true by luck. What makes a belief reasonable is something else: justification. This chapter is about the structure of good reasons.
We'll start with defeaters, the considerations that can undercut a reason you thought you had. Then comes an ancient puzzle. If every belief needs a reason, and every reason needs another reason, where does it stop? The main answers, foundationalism, coherentism, infinitism, and their hybrids, each paint a different picture of how our beliefs hang together.
After that we'll look at the great debate between internalists and externalists, and we'll end with fallibilism: the idea that you can know things without being certain of them.
""",
"07": """
Where does knowledge come from? Mostly from five places: perception, memory, introspection, reason, and the word of other people.
In this chapter we'll take each in turn, asking how it works, why we're entitled to rely on it, and, just as important, how it fails. You'll hear about illusions and false memories, about how little we can see of our own minds, and about why almost everything you know depends on trusting someone else.
We'll finish with knowledge by presence, from the Islamic philosophical tradition, and with a practical question: when should you trust your intuition?
""",
"08": """
Can you know that you're not dreaming right now? Can you rule out that your brain is floating in a vat, wired to a computer that feeds you a perfect illusion? If you can't, the skeptic says, then you don't really know that you have hands, or that you're listening to this recording.
In this chapter we'll take the skeptic seriously. We'll meet the ancient Pyrrhonists, Descartes and his evil demon, and the modern brain in a vat. Then we'll work through the best replies: Moore's defence of common sense, contextualism, hinge epistemology, and more.
We'll finish by separating healthy skepticism, which every critical thinker needs, from the corrosive kind that dissolves all trust.
""",
"09": """
Every day you reason from what you've seen to what you haven't. The sun has always risen, so it will rise tomorrow. But why is that reasonable? David Hume argued that it can't be justified without going in a circle. We'll start with his problem, and with some famous puzzles that make it even harder.
Then we'll get practical. You'll learn the basics of probability and Bayes' theorem, the single most useful tool for thinking about evidence, and we'll work through examples, including a medical test result that most people, and many doctors, misread.
Finally we'll tour the classic errors of probabilistic reasoning, from base-rate neglect to the Monty Hall problem, and see what statistical significance does and doesn't tell you. Don't worry about the numbers. I'll talk you through them slowly.
""",
"10": """
Science is our most successful way of finding things out. But what exactly makes it work?
In this chapter we'll meet the philosophers who tried to answer that question: Popper and falsification, Kuhn and his paradigms, Lakatos, Feyerabend, and others. We'll ask what makes one explanation better than another, whether we should believe in things we can't observe, and how to get from correlation to causation.
Then we'll look at science as a human institution: the role of values, what a scientific consensus is worth, the replication crisis, and how to tell science from pseudoscience.
""",
"11": """
What is truth, and does it matter? In this chapter we'll look at the main theories of truth, from the idea that truth is correspondence with the facts to the view that there's much less to truth than philosophers once thought. We'll meet the liar paradox, a sentence that seems to be true if and only if it's false.
Then we'll take on relativism, the claim that truth is relative to cultures or to individuals. We'll separate the versions that are plausible from the ones that defeat themselves, look at what social construction really means, and end with post-truth politics, and with what the philosopher Harry Frankfurt called bullshit.
""",
"12": """
Almost everything you know, you know because someone told you. This chapter is about knowing together.
We'll ask when it's rational to trust others, how a non-expert can choose between experts, and what to do when a thoughtful person disagrees with you. We'll look at epistemic injustice, at echo chambers and information cascades, at the wisdom and the madness of crowds, and at misinformation, propaganda, and conspiracy theories.
We'll finish with the institutions that let a whole society know things, and with a new question: what happens to our knowledge when we rely on artificial intelligence?
""",
"13": """
Can a belief be wrong in a moral sense? In 1877 the mathematician William Clifford said yes: it is wrong always, everywhere, and for anyone, to believe anything upon insufficient evidence. William James replied that sometimes we have the right to believe ahead of the evidence. We'll start with that famous debate.
Then we'll turn from rules to character: the intellectual virtues, like curiosity, humility, and courage, and the vices that undermine good thinking. We'll ask whether the stakes of a situation can change what you know, and we'll end with faith and reason.
""",
"14": """
So far we've mostly asked how we ought to reason. This chapter asks how we actually do.
Psychology has discovered a great deal about the shortcuts our minds take, and the systematic ways they go wrong. We'll look at fast and slow thinking, at heuristics and biases, and at the tendency that matters most in arguments: our habit of seeking and favouring evidence for what we already believe. We'll see why intelligence doesn't protect you, and can even make things worse.
But we'll hear the other side too. Some biases make sense in the right environment, and some famous findings haven't held up. We'll finish with what actually helps: the scout mindset, and the habits of the best forecasters.
""",
"15": """
Like a guide to birds, this chapter helps you recognize what you're looking at: more than forty fallacies and rhetorical tricks, grouped into families.
For each one you'll hear what it looks like, why it's tempting, how to respond, and its legitimate cousin: the good form of reasoning it imitates. Not every appeal to authority is a fallacy, and not every slippery slope is imaginary.
At the end there's a practice round, where you can test yourself on realistic examples.
""",
"16": """
This is where everything comes together. In this final chapter you'll learn a seven-step method for analyzing any discussion: understand before you evaluate, identify the kind of disagreement, map the argument, evaluate the premises and the evidence, find the crux, and weigh it all up.
Then we'll turn it around: how to frame an argument of your own, who carries the burden of proof, and a set of philosophical razors for cutting through nonsense. We'll talk about the ethics of discussion, and work through five case studies, from an herbal cold remedy to an argument on social media.
We'll finish with checklists and daily habits to keep your thinking sharp.
""",
}

OUTROS = {
"01": """
That's the end of chapter one. You now have the basic vocabulary: knowledge and belief, credence and acceptance, evidence and justification, and three great distinctions. Every written chapter also ends with suggestions for further reading, if you want to go deeper.
Next, in chapter two, we'll see where these ideas came from, with a tour of two and a half thousand years of thinking about knowledge, from Greece, India, China, and the Islamic world to the present day.
""",
"02": """
That's the end of chapter two. Next, we'll build the most basic tool a critical thinker has: the ability to take an argument apart and see whether it holds up. Chapter three is about logic, and the anatomy of arguments.
""",
"03": """
That's the end of chapter three. You now have the tools to dissect an argument. But arguments are made of words, and words can mislead. In chapter four we'll look at language, concepts, and definitions.
""",
"04": """
That's the end of chapter four, and of the foundations. In chapter five we reach the heart of epistemology, with a question that sounds easy and turns out to be extraordinarily hard: what is knowledge?
""",
"05": """
That's the end of chapter five. We've seen that knowledge takes more than true belief, and that saying exactly what more is surprisingly hard. In chapter six we'll look closely at one of the ingredients: justification, and the structure of good reasons.
""",
"06": """
That's the end of chapter six. We've looked at how reasons fit together. In chapter seven we'll look at where they come from: perception, memory, introspection, reason, and testimony.
""",
"07": """
That's the end of chapter seven. Every source we looked at can fail. That raises an unsettling question: how do you know they aren't failing all the time? In chapter eight we meet the skeptic.
""",
"08": """
That's the end of chapter eight. Next we turn from certainty to probability: how to reason well when you can't be sure. Chapter nine covers the problem of induction, and the power of Bayes' theorem.
""",
"09": """
That's the end of chapter nine. If you'd like to see the formulas and worked examples on the page, the written chapter has them all. In chapter ten we'll put these ideas to work in the most successful knowledge-producing enterprise we have: science.
""",
"10": """
That's the end of chapter ten. Science aims at the truth. But what is truth? Is it objective, or relative to cultures and individuals? That's the subject of chapter eleven.
""",
"11": """
That's the end of chapter eleven. In chapter twelve we'll look at knowledge as a social achievement: trust, expertise, disagreement, and the ways communities come to know things, or fail to.
""",
"12": """
That's the end of chapter twelve. We've seen how much knowledge depends on communities. In chapter thirteen we turn to the character of the individual thinker, with intellectual virtue and the ethics of belief.
""",
"13": """
That's the end of chapter thirteen. We've looked at how we ought to think. In chapter fourteen we'll see what psychology tells us about how we actually think, and how it goes wrong.
""",
"14": """
That's the end of chapter fourteen. In chapter fifteen we'll turn this knowledge into a practical skill, with a field guide to the fallacies and rhetorical tricks you'll meet in everyday arguments.
""",
"15": """
That's the end of chapter fifteen. The written chapter also has a quick-reference table of every fallacy covered, which is worth bookmarking. In the final chapter, we'll bring everything together into a practical toolkit for analyzing discussions and building arguments of your own.
""",
"16": """
That's the end of chapter sixteen, and the end of the audio edition of Mastering Epistemology. Thank you for listening.
The written guide goes further, with a glossary of two hundred terms, a reading list, and a twelve-week study plan.
The best way to make these ideas your own is to use them. In your next argument, ask what exactly is being claimed, what would support it, and what would change your mind. Including your own.
""",
}

TABLES = {
    "01": {
        "Question": "{0} That's {1:l}, in {2}.",
        "Ethics": "In ethics, {0:l}. In epistemology, {1:l}.",
    },
    "02": {
        "Date": "{0}: {1}. {2}",
    },
    "03": {
        "Connective": "{0}: {2}, which is true when {3}.",
        "P": [
            "@aside Reading the table row by row would be tedious, so here is what it shows.",
            "Not P flips the truth value of P.",
            "P and Q is true only when both are true.",
            "P or Q is false only when both are false.",
            "If P then Q is false in just one case: when P is true and Q is false.",
            "And P if and only if Q is true exactly when P and Q have the same truth value.",
        ],
        "Statement": "{0} Form: {1}. Equivalent to the original? {2}",
        "Example": "{0}. Necessary? {1}. Sufficient? {2}",
        "Type": "{0}: {1}. For example: {2}",
        "|Premises all true": [
            "A valid argument with all its premises true is sound, so its conclusion is guaranteed to be true.",
            "A valid argument with at least one false premise is unsound: its conclusion may be true or false.",
            "And an invalid argument is unsound either way, whether its premises are true or not: its conclusion may be true or false.",
        ],
    },
    "04": {
        "Word": "{0}. Sense one: {1}. Sense two: {2}. The typical confusion: {3}",
    },
    "05": {
        "Theory": "{0}. The key condition: {1:l}. Handles Gettier's cases? {2}. Handles fake barns? {3}. Main problem: {4:l}",
    },
    "06": {
        "Horn of the trilemma": "{0}: that's {1:l}. {2}",
    },
    "09": {
        "Likelihood ratio": "A likelihood ratio of {0}: {1}",
    },
    "10": {
        "Explanation": "{0}: {2}",
    },
    "14": {
        "System 1 (Type 1)": "{0} versus {1:l}.",
        "Bias": "{0}. {1} For example: {2}",
    },
    "15": {
        "Fallacy": [
            "@aside The written chapter has a quick-reference table here, listing every fallacy with its pattern and the key question to ask. It's a page worth bookmarking.",
        ],
    },
    "16": {
        "Level": "{0}: {1}. For example: {2}",
        "Term": "{0}: {1}.",
    },
}

REPLACE = {
    "16": [
        ("3. *(Hidden)* So ColdAway", "3. Hidden premise: so ColdAway"),
        ("4. *(Hidden)* What worked", "4. Hidden premise: what worked"),
    ],
    "09": [
        ("0.9¹⁰ ≈ 0.35", "0.9 to the power of 10, which is about 0.35"),
        ("(low P(E | not-H))", "(that is, if P(E | not-H) is low)"),
    ],
    "03": [
        ("assume √2 = a/b in lowest terms; then a² = 2b², so *a* is even, so *a* = 2k, so 4k² = 2b², so b² = 2k², so *b* is even; but then a/b was not in lowest terms, a contradiction.",
         "assume the square root of 2 is a fraction, a over b, in lowest terms. Then a squared equals 2 b squared, so a is even. Write a as 2 k. Then 4 k squared equals 2 b squared, so b squared equals 2 k squared, so b is even too. But then a over b was not in lowest terms: a contradiction."),
        ("> P. Q. So P and Q. / P and Q. So P. / P. So P or Q.",
         "> P. Q. So P and Q.\n> P and Q. So P.\n> P. So P or Q."),
        ("But the A/E/I/O forms", "But the A, E, I, and O forms"),
        ('"All humans are mortal": ∀x (Human(x) → Mortal(x))\n"Some birds cannot fly": ∃x (Bird(x) ∧ ¬Flies(x))\n"Everyone loves someone": ∀x ∃y Loves(x, y)\n"Someone is loved by everyone": ∃y ∀x Loves(x, y)',
         '- "All humans are mortal" becomes: for every x, if x is human, then x is mortal.\n- "Some birds cannot fly" becomes: there is some x such that x is a bird and x does not fly.\n- "Everyone loves someone" becomes: for every x, there is some y such that x loves y.\n- "Someone is loved by everyone" becomes: there is some y such that, for every x, x loves y.'),
        ("Does it mean *nobody* passed (∀x ¬Passed(x)) or *not everybody* passed (¬∀x Passed(x))?",
         "Does it mean *nobody* passed, or *not everybody* passed?"),
        ('"Necessarily, the number of planets > 7."', '"Necessarily, the number of planets is greater than 7."'),
        ("- ¬(P ∧ Q) ≡ ¬P ∨ ¬Q: \"It's not true that both P and Q\" means \"Either not P or not Q.\"",
         "- Not both P and Q is equivalent to not P or not Q: \"It's not true that both P and Q\" means \"Either not P or not Q.\""),
        ("- ¬(P ∨ Q) ≡ ¬P ∧ ¬Q: \"Neither P nor Q\" means \"Not P and not Q.\"",
         "- Not either P or Q is equivalent to not P and not Q: \"Neither P nor Q\" means \"Not P and not Q.\""),
        ("> ∀x ∃y (y is x's mother) ⊢ ∃y ∀x (y is x's mother). Invalid.",
         "> In symbols: for every x there is some y who is x's mother. That does not entail that there is some y who, for every x, is x's mother. Invalid."),
        ("from □(K → P) and K, only P follows, not □P.",
         "from \"necessarily, if K then P\" and K, only P follows, not \"necessarily P\"."),
        ("- ¬∀x P(x) ≡ ∃x ¬P(x): \"Not everything is P\" = \"Something is not P.\"",
         "- \"Not everything is P\" is equivalent to \"Something is not P.\""),
        ("- ¬∃x P(x) ≡ ∀x ¬P(x): \"Nothing is P\" = \"Everything is not P.\"",
         "- \"Nothing is P\" is equivalent to \"Everything is not P.\""),
        ("- □P ≡ ¬◇¬P: \"necessarily P\" = \"not possibly not P\"",
         "- \"Necessarily P\" is equivalent to \"not possibly not P\""),
    ],
}
