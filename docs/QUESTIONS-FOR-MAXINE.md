# Questions waiting on you

Written while working unattended on 2026-08-29. Nothing here blocks anything
already committed — each item is a choice I could not make for you, with what I
did in the meantime so you are never waiting on an answer to use the product.

Newest last. Delete an entry once it is answered, or turn it into a decision in
[`decisions.md`](decisions.md).

---

## Q-1 · Firestore cannot be verified on this machine, so I have not written it

`CLAUDE.md` names Firestore as the store. It is not enabled on the project, and
this machine has **no Java, no Docker, no `gcloud` on the shell PATH, and no
`google-cloud-firestore` installed**, so neither the real service nor the
emulator can run. I could write the adapter, but I could not execute a single
line of it, and an adapter that has never run is a guess with type annotations.

**What I did instead:** `store/sqlite.py` (D-045), behind the identical ports,
plus `tests/test_store_conformance.py` — 26 assertions that both backends pass.
A Firestore adapter is now a much smaller job than it was: implement the ports,
run that file, done.

**What I need from you:** either enable Firestore on the project and say so, or
confirm SQLite is fine for the demo and Firestore waits. If you want it written
blind anyway, say so explicitly — I will do it, but the changelog will record
that it was never executed.

---

## Q-2 · The Veo teaser is behind a flag and I cannot turn it on

`FLAG_VEO_TEASER` is off and `core/teaser.py` reports `needs_human` rather than
inventing a video, which is correct. Turning it on needs Veo access on the
project, which I cannot grant myself.

**What I need from you:** whether the teaser matters for the demo at all. It is
listed as T-A7 and is the one product feature with no path to a real result
here. If it does not matter, I would rather record it as out of scope than
leave it looking half-finished.

---

## Q-3 · Only one filing company exists, and its name is 待补充

The demo registry ships empty on purpose — no institution is invented — and the
Administration page loads one placeholder company whose name, licence number and
capital are all placeholders or round numbers.

**What I need from you:** whether you have (or can get) one real licensed
company's public details to use in the demo. A reviewer screen showing 待补充 as
a company name is honest but reads as unfinished to anyone watching. If real
details are not available, the alternative is an obviously-fictional name like
"演示影视公司（示例）", which at least does not look like a bug — but that is
inventing an entity, which the ground rules forbid without your say-so.

---

## Q-4 · A stale project can now be re-decided — should it be automatic?

When a policy change lands, a project is marked stale and its creator is told.
For a threshold change the tier is recalculated automatically. For a *subject*
rule change it is not, deliberately (D-050): re-deciding a subject match needs
the full chain and a human.

I have added a re-classification the creator triggers themselves, so a stale
project is no longer a dead end.

**What I need from you:** whether that should ever happen without the creator
asking. My instinct is no — a classification that changes under someone without
them looking is exactly the kind of silent movement the evidence rules exist to
prevent — but it is your product decision, and "why is my project suddenly
Class 1" is a worse surprise than an unread notification.

---

## Q-5 · A boundary-subject decision is written but never shown

When the subject check lands on a boundary, the chain writes a finding carrying
an `Alert`: a risk reason, the department that would decide, and two or three
options — modify the scenes, keep them and accept co-review, escalate to the
authority — each with its own impact. `POST /findings/{id}/action` records the
choice.

**No screen renders any of it.** The copy exists (`alert.option.*`,
`alert.impact.*`), the route exists, the finding is stored. A creator whose
project sits on a boundary simply never learns there was a choice.

**What I need from you:** whether this belongs in the demo. It is the one place
the product asks a creator to make a judgement rather than reporting one, which
makes it either the most interesting screen to show or a distraction from the
straight-through story. I did not build it unasked because it is a new
user-facing surface with real wording implications, not a fix.

---

## Q-6 · Targeted video checking — your idea, and what it needs

Your proposal: instead of analysing a whole video, use the script pre-check to
find the passages worth attention and look only at those. That is a better
design than the one the non-goal was written against, and it removes the cost
objection — four scenes rather than four hours.

**Half of it is built.** Findings carry an episode and a scene, so a finished
project now gets a numbered list of exactly where to look, with the script's
own line. That needed no new capability.

**The other half needs two things I cannot give myself:**

1. A change to `CLAUDE.md`'s "no video-frame analysis" non-goal. I could not
   find the reasoning behind it — the TDD it cites is not in the repo, only
   `docs/technical/policy-loop-v1-tdd.md`, whose section 11 is about
   `policy.updated` consumption. So I have no original argument to weigh your
   idea against, only a guess that it was about cost and scope.
2. A vision model on the project. The Veo flag is generation, not analysis.

**What I need from you:** whether to change that non-goal. If yes I will write
the superseding decision and say plainly that the reasoning for the original
could not be found.

