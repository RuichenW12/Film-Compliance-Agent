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
