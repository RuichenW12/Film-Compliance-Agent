# Sample uploads

Files for walking the flow locally. **Synthetic** — made up for testing, not
real project material and not evidence about anything.

| File | Upload as kind | Use it for |
|---|---|---|
| `synopsis.txt` | `synopsis` | satisfies the required card `mat_synopsis` |
| `script.txt` | `script` | satisfies `mat_script`; produces **no** findings |
| `script-flagged.txt` | `script` | produces two `public_security` findings, so the pre-check has something to show |

Only two cards are required by the v2 snapshot — `mat_synopsis` and
`mat_script`. The other four are optional and can be left pending or waived.

To reach a frozen form you must upload both, attach each to its card, and
validate it. Materials block the D3 gate, which is new: before the snapshot
carried real cards, that step did nothing.

You also need five facts confirmed on the form: `title`, `episode_count`,
`episode_minutes`, `investment_amount_rmb`, `applicant_entity`.

Use `script-flagged.txt` if you want to see findings, then switch to
`script.txt` and re-review to watch the flagged scenes close as `self_fixed`.
