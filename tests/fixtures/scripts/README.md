# Synthetic scripts

Made-up scenes used to exercise the C1-a harness itself. **Not** golden samples:
nobody with authority has reviewed them, so they prove the harness runs, not
that its verdicts are correct. Expert-reviewed material goes in `tests/golden/`
with its provenance recorded.

| File | Owner | Purpose |
|---|---|---|
| `clean-romance.txt`, `public-security.txt` | A | Minimal one-line-per-scene scripts for the harness unit tests |
| `e2e-10min-clean-baseline.md` | B | ~10 min, one episode, no rule hits expected |
| `e2e-30min-public-security.md` | B | ~30 min, one episode, at least 5 deterministic hits expected |
| `e2e-30min-public-security-en.md` | B | Complete English counterpart; semantic-review demo input, not a deterministic clean baseline |
| `e2e-70min-judicial-long-context.md` | B | ~70 min, 7 episodes, 28 scenes; long-context and per-scene location |
| `e2e-70min-judicial-long-context-en.md` | B | Complete English counterpart; long-context semantic-review demo input |

Each `.md` fixture states its own expectations near the top. The Chinese files
carry deterministic governed-trigger contracts. The English files deliberately
expect no Chinese-trigger hits: with no semantic backend they stay `pending`,
while a configured LLM may retain only findings whose exact quoted evidence can
be located in a reviewable scene. Tests assert these boundaries so a fixture
and the reviewer cannot drift apart silently.

Both heading styles are supported: `第一集 场景二` on one line, and a markdown
`### 第N集` heading followed by `**内景·…**` slug lines. Blockquotes, front
matter above the first episode, and appendix sections are not reviewed — they
are commentary about a script, not the script.
