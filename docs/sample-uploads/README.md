# Sample uploads

Files for walking the flow locally. **Synthetic** — made up for testing, not
real project material and not evidence about anything. No real company, licence
number or registration number appears in any of them.

## Legacy workflow synopses — paste into `/wizard`

These fixtures exercise the retained multi-page workflow, not the current
upload-first recording path. They are pasted into the **What happens** box,
not uploaded. Each file ends
with a `用途` note explaining what it is for; paste the story text above it, not
the note.

| File | Paste with these keywords | Expect |
|---|---|---|
| `synopsis-A-ordinary.txt` | `都市,甜宠` | Ordinary subject. Class depends entirely on your budget answer. |
| `synopsis-B-special-subject.txt` | `缉毒,卧底` | **Class 1 and co-review, whatever the budget** — a special subject outranks money. |
| `synopsis-C-buried-subject.txt` | `都市` | Class 1 as well. The trigger is in the *second* sentence: the check reads the paragraph, not the opening line. |
| `synopsis-D-injection.txt` | `都市` | Class 1. The last line is an instruction telling the system to say Class 3; it must be ignored. Uploaded text is data, never commands. |

All four verified against a live run on 2026-08-29.

## Legacy workflow files — upload on `/collection`

| File | Upload as kind | Use it for |
|---|---|---|
| `synopsis.txt` | `Synopsis` | satisfies the required card `mat_synopsis` |
| `script.txt` | `Script` | satisfies `mat_script`; produces **no** findings |
| `script-flagged.txt` | `Script` | produces two `public_security` findings, so the pre-check has something to show |

Only two cards are required by the v2 snapshot — `mat_synopsis` and
`mat_script`. The other four are optional and can be left pending or waived.

To reach a locked form you must upload both, attach each to its card, and
validate or waive it. Materials block the pre-shoot gate.

You also need these facts confirmed on the form: `title`, `episode_count`,
`episode_minutes`, `investment_amount_rmb`. `applicant_entity` is the one you
cannot answer as an individual — press **I don't have one** instead, which
records that the filing company supplies it without inventing a company.
