# Policy Administration UI

Owner: Richard

This directory owns the implemented Gate 3 policy administration route in the Next.js application.

The first UI increment supports:

- manually triggering a policy crawl;
- viewing crawl task status;
- listing pending change proposals;
- reviewing the source diff, summary, impact, effective time, and draft pack updates;
- publishing or discarding a proposal;
- viewing published snapshot history.

Publishing remains a human action. Future-effective proposals are visible but not publishable before their effective time in v1.

## Local routes

- `/admin/policy` launches the fixture crawl and shows run, proposal, and snapshot status.
- `/admin/policy/proposals/[proposalId]` shows the proposal summary, source diff, affected pack draft, and publish/discard actions.

Start the FastAPI service first, then run `npm --prefix web run dev` from the repository root and open `http://127.0.0.1:3000/admin/policy`.

This first increment deliberately omits live sources, production identity, durable storage, background queues, and deployment wiring.
