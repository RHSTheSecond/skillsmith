# Promotion tests — canonical candidates

The ladder has five rungs and **one test per rung**. This file is the calibration
set: five candidates whose right rung is not obvious, each worked through the test
that actually decides it. It doubles as a regression fixture — a skillsmith run
that classifies these differently, without a stated reason, is drifting.

Rungs, and the test each one applies (the same table the skill carries):

| Rung | Promotion test — all of it, for that rung |
|---|---|
| **vocabulary / rule** | the user has corrected toward it more than once |
| **skill** | recurs *on request* across ≥3 distinct sessions, and the procedure is stable enough to write down |
| **script** | zero mid-loop judgment · nameable inputs and outputs · failure is loud |
| **workflow** | multi-step and orchestrated but still human-triggered · each step's outcome is verifiable |
| **agent** | recurs on a clock/external trigger · no mid-loop judgment (an escalation point is a **named surface**, not a promise) · verifiable outcome · **bounded cost of being wrong** |

**The bounded-cost clause.** An agent whose output is undeletable or irreversible
passes only if *all three* hold: the content class is low-stakes, the output
template was human-approved, and a kill switch exists. Anything that spends money,
contacts a customer, or writes to a system of record fails this clause no matter
how routine it looks.

---

## 1. "Always call it X, not Y" — a naming correction, said three times

**Rung: vocabulary / rule.** It fails the skill test on the second clause, not the
first: there is no procedure to write down. Frequency is not what promotes something
— shape is. Writing a "naming skill" produces a file that never gets invoked, because
nobody says "run the naming skill"; they just want the assistant to already know.

## 2. "Summarize this recording and give me the action items"

**Rung: skill.** Recurs on request (five sessions in three weeks), and the procedure
is stable: transcribe, summarize, extract owners and dates, format. It fails the
*script* test on the first clause — every step needs judgment about what matters —
so a deterministic implementation would be worse than the prose one, not better.

## 3. "Rename these files by date and move them into the right folders"

**Rung: script.** Zero mid-loop judgment once the rule is stated; inputs and outputs
are nameable; a wrong path fails loudly rather than silently doing the wrong thing.
This is the rung most often over-promoted: it *feels* like a skill because a human
described it in prose, but an LLM executing fixed steps adds cost and variance for
nothing. Write the code; add a thin skill wrapper only if a natural-language entry
point genuinely helps.

## 4. "Pull the numbers from three systems, reconcile them, and write the report"

**Rung: workflow.** Multi-step and orchestrated, each step verifiable — but a human
still starts it, and should: the reconciliation step's *output* is checkable while
its *inputs* change meaning as the business does. It fails the agent test on the
trigger clause (it recurs when someone needs it, not on a clock) — and, if someone
proposes putting it on a monthly timer, on the bounded-cost clause too, because a
wrong reconciled number is acted on before anyone re-derives it.

## 5. "Post the daily status card to the team channel at 6am"

**Rung: agent — but only through the bounded-cost clause, and this is the worked
boundary case.** Trigger: a clock ✓. Mid-loop judgment: none, if the card is
generated from fixed fields ✓. Verifiable outcome: the post either landed or it
didn't ✓. Cost of being wrong: a chat post is *undeletable by the agent*, so the
clause applies — it passes only because the content class is low-stakes, the card
template was human-approved, and the timer can be disabled.

Change one fact and it fails: if the card includes a number a human would act on
without checking, "low-stakes" is gone. If the template is generated fresh each run
rather than approved once, "approved template" is gone. If it emails customers
instead of posting internally, it fails outright — no clause rescues it.

---

## How to use this file

Read it before classifying a real candidate, then apply the rung's test to that
candidate explicitly and say which clause decided it. "It felt like a skill" is not
a classification. Disagreeing with a verdict here is fine — say why, in terms of the
test, and the disagreement is the useful part.
