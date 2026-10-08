# Token ledger

Tokens the generator model spent per stage, as measured so far. One row per stage and idea; nothing here is an estimate.

- Generator: `gpt-5.6-terra` through the project's Azure deployment. Langfuse off.
- **The judge was the fake judge in every slice 2 measurement** (no `JUDGE_*` configured), so judge tokens are **not** counted anywhere in this file. When the real judge is configured they will need their own rows.
- A row is the sum over all calls of that stage in one run; "calls" is the number of LLM calls (one per row plus any retry; there were no retries in these runs, so calls = rows).
- Input grows with context: `patterns` and `canvas` read the upstream artifacts, and `patterns` grows with the number of segments.
- Prompt versions: `brief` 1, `empathy_map` 2, `customer_scenario` 2, `ideation` 1, `patterns` 1, `canvas` 1.
- Ukrainian costs more input and output than English for the same structure (see the `beer (UK)` rows).

## Measured per stage, slice 1 and slice 2 stages (2026-10-08, `scripts/slice2_dry_run.py`)

The four slice 1 stages were measured again in the same runs as the two slice 2 stages, because the reports of PR #6 and PR #7 only gave totals per run (next section), not per stage.

| stage | prompt version | idea | calls | input | output | total | date |
|---|---|---|---|---|---|---|---|
| brief | 1 | farm (EN) | 1 | 616 | 144 | 760 | 2026-10-08 |
| brief | 1 | beer (UK) | 1 | 632 | 246 | 878 | 2026-10-08 |
| brief | 1 | music (EN) | 1 | 629 | 214 | 843 | 2026-10-08 |
| brief | 1 | split (EN) | 1 | 632 | 218 | 850 | 2026-10-08 |
| brief | 1 | photo (EN) | 1 | 613 | 145 | 758 | 2026-10-08 |
| empathy_map | 2 | farm (EN) | 1 | 1,078 | 866 | 1,944 | 2026-10-08 |
| empathy_map | 2 | beer (UK) | 1 | 1,188 | 1,539 | 2,727 | 2026-10-08 |
| empathy_map | 2 | music (EN) | 3 | 3,461 | 3,006 | 6,467 | 2026-10-08 |
| empathy_map | 2 | split (EN) | 2 | 2,306 | 1,739 | 4,045 | 2026-10-08 |
| empathy_map | 2 | photo (EN) | 2 | 2,150 | 1,899 | 4,049 | 2026-10-08 |
| customer_scenario | 2 | farm (EN) | 1 | 2,102 | 357 | 2,459 | 2026-10-08 |
| customer_scenario | 2 | beer (UK) | 1 | 2,887 | 625 | 3,512 | 2026-10-08 |
| customer_scenario | 2 | music (EN) | 3 | 7,003 | 1,155 | 8,158 | 2026-10-08 |
| customer_scenario | 2 | split (EN) | 2 | 4,363 | 741 | 5,104 | 2026-10-08 |
| customer_scenario | 2 | photo (EN) | 2 | 4,375 | 865 | 5,240 | 2026-10-08 |
| ideation | 1 | farm (EN) | 1 | 2,068 | 397 | 2,465 | 2026-10-08 |
| ideation | 1 | beer (UK) | 1 | 2,844 | 537 | 3,381 | 2026-10-08 |
| ideation | 1 | music (EN) | 3 | 6,829 | 1,217 | 8,046 | 2026-10-08 |
| ideation | 1 | split (EN) | 2 | 4,273 | 688 | 4,961 | 2026-10-08 |
| ideation | 1 | photo (EN) | 2 | 4,293 | 736 | 5,029 | 2026-10-08 |
| patterns | 1 | farm (EN) | 1 | 3,199 | 35 | 3,234 | 2026-10-08 |
| patterns | 1 | beer (UK) | 1 | 3,666 | 35 | 3,701 | 2026-10-08 |
| patterns | 1 | music (EN) | 1 | 4,808 | 469 | 5,277 | 2026-10-08 |
| patterns | 1 | split (EN) | 1 | 3,873 | 207 | 4,080 | 2026-10-08 |
| patterns | 1 | photo (EN) | 1 | 4,022 | 195 | 4,217 | 2026-10-08 |
| canvas | 1 | farm (EN) | 1 | 3,596 | 532 | 4,128 | 2026-10-08 |
| canvas | 1 | beer (UK) | 1 | 4,304 | 884 | 5,188 | 2026-10-08 |
| canvas | 1 | music (EN) | 1 | 6,035 | 933 | 6,968 | 2026-10-08 |
| canvas | 1 | split (EN) | 1 | 4,605 | 642 | 5,247 | 2026-10-08 |
| canvas | 1 | photo (EN) | 1 | 4,867 | 641 | 5,508 | 2026-10-08 |

### Mean tokens per call (all five ideas pooled; mixes one Ukrainian run, so treat as indicative)

| stage | prompt version | calls | input | output | total |
|---|---|---|---|---|---|
| brief | 1 | 5 | 624 | 193 | 817 |
| empathy_map | 2 | 9 | 1,131 | 1,005 | 2,136 |
| customer_scenario | 2 | 9 | 2,303 | 415 | 2,719 |
| ideation | 1 | 9 | 2,256 | 397 | 2,653 |
| patterns | 1 | 5 | 3,913 | 188 | 4,101 |
| canvas | 1 | 5 | 4,681 | 726 | 5,407 |

### Whole run through canvas (all six stages)

| idea | description | calls | input | output | total |
|---|---|---|---|---|---|
| farm (EN) | single segment: farm produce boxes for city parents | 6 | 12,659 | 2,331 | 14,990 |
| beer (UK) | single segment: monthly home-brewing kit subscription | 6 | 15,521 | 3,866 | 19,387 |
| music (EN) | 3-sided platform: bands, venues, fans | 12 | 28,765 | 6,994 | 35,759 |
| split (EN) | two unrelated business lines: standing desks + laser cutting | 9 | 20,052 | 4,235 | 24,287 |
| photo (EN) | 2-sided marketplace: photographers and studio owners | 9 | 20,320 | 4,481 | 24,801 |

## Slice 3: `swot_errc_cycle` (2026-10-08, `scripts/slice2_dry_run.py`, three of the five earlier ideas)

Generator `gpt-5.6-terra`, fake judge (no `JUDGE_*` configured, so judge tokens are not counted), Langfuse off, no retries of any kind in these three runs. The cycle row makes `SwotGenerated` and `ErrcGenerated` calls inside one message; they are listed apart. "Mean per call" is input / output.

| call | prompt version | idea | calls | input | output | total | mean per call | date |
|---|---|---|---|---|---|---|---|---|
| swot (in the cycle row) | swot=1 | farm (EN) | 5 | 14,161 | 9,952 | 24,113 | 2,832 / 1,990 | 2026-10-08 |
| errc (in the cycle row) | errc=1 | farm (EN) | 4 | 12,526 | 2,943 | 15,469 | 3,131 / 735 | 2026-10-08 |
| swot (in the cycle row) | swot=1 | photo (EN) | 3 | 8,649 | 6,740 | 15,389 | 2,883 / 2,246 | 2026-10-08 |
| errc (in the cycle row) | errc=1 | photo (EN) | 2 | 6,748 | 1,731 | 8,479 | 3,374 / 865 | 2026-10-08 |
| swot (in the cycle row) | swot=1 | split (EN) | 3 | 8,818 | 7,746 | 16,564 | 2,939 / 2,582 | 2026-10-08 |
| errc (in the cycle row) | errc=1 | split (EN) | 2 | 7,291 | 1,682 | 8,973 | 3,645 / 841 | 2026-10-08 |

### The cycle row, per idea

| idea | description | iterations | score series | final version | calls | input | output | total | wall-clock of the row | whole run through the cycle (all stages) |
|---|---|---|---|---|---|---|---|---|---|---|
| farm | single segment | 5 | [199.0, 82.0, 79.0, 76.0, 78.0] | 4 | 9 | 26,687 | 12,895 | 39,582 | 129 s | 54,688 |
| photo | 2-sided marketplace | 3 | [116.0, 79.0, 86.0] | 2 | 5 | 15,397 | 8,471 | 23,868 | 87 s | 48,514 |
| split | two unrelated lines | 3 | [212.0, 197.0, 203.0] | 2 | 5 | 16,109 | 9,428 | 25,537 | 92 s | 50,845 |

Wall-clock of the cycle row against the message lock renewal (`lock_renewal_seconds`, 900 s): 87 s to 129 s, i.e. at most 14 % of it, for 3 to 5 iterations of a single canvas. A project split into several canvases has one cycle row (one message) per canvas.

## Reported earlier: slice 1 run totals (no per-stage split was recorded)

From the reports of PR #6 and PR #7 (slice 1 stages only: `brief`, `empathy_map`, `customer_scenario`, `ideation`). Ideas as described there; the exact texts were not kept in the repository.

| source | idea | rows | input / output | total |
|---|---|---|---|---|
| PR #6 | single segment, English (prompts v1) | 4 | 5,800 / 1,983 | 7,783 |
| PR #6 | Ukrainian, app for parents (prompts v1) | 4 | 7,167 / 3,061 | 10,228 |
| PR #6 | 3-sided marketplace, English (prompts v1) | 10 | 16,788 / 5,658 | 22,446 |
| PR #7 | single segment, English, mean of 3 runs, v1 -> v2 prompts | 4 | | 7,835 -> 7,757 |
| PR #7 | single segment, Ukrainian, mean of 3 runs, v1 -> v2 | 4 | | 10,328 -> 10,046 |
| PR #7 | 3-sided marketplace, English, mean of 2 -> 3 runs, v1 -> v2 | 10 | | 23,422 -> 22,857 |
