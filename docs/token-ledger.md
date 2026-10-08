# Token ledger

Tokens the generator model spent per stage, as measured so far. One row per stage and idea; nothing here is an estimate.

- Generator: `gpt-5.6-terra` through the project's Azure deployment. Langfuse off.
- **The judge was the fake judge in every slice 2 measurement** (no `JUDGE_*` configured), so judge tokens are **not** counted anywhere in this file. When the real judge is configured they will need their own rows.
- A row is the sum over all calls of that stage in one run; "calls" is the number of LLM calls (one per row plus any retry; there were no retries in these runs, so calls = rows).
- Input grows with context: `patterns` and `canvas` read the upstream artifacts, and `patterns` grows with the number of segments.
- Prompt versions: `brief` 1, `empathy_map` 2, `customer_scenario` 2, `ideation` 1, `patterns` 1, `canvas` 1 (the slice 4 stages are in their own section below).
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

## Slice 3 follow-up: ERRC prompt v2 and SWOT prompt v2 (2026-10-08, n = 3 runs per idea and condition)

Two changes, recorded together:
- **ERRC v2** (domain 0.17.0): `reduce` and `raise` replace the card's text with `new_text`; the prompt states the field rule per action and forbids repeating a move on a card marked by the previous step unless the new text goes further.
- **SWOT v2**: the 1-5 scores of opportunities and threats are anchored (1 = no evidence of this in the canvas, 3 = plausible but not visible, 5 = already visible) and the model is told to use the full range. The stop criterion and the domain scales are unchanged.

**Design of the comparison.** "before" = the commit with ERRC v2 and **SWOT v1**; "after" = ERRC v2 and **SWOT v2**, so the difference is the SWOT change only (the old ERRC cannot run on domain 0.17.0). Same three ideas (`docs/dry-run-ideas.md`), generator `gpt-5.6-terra`, fake judge, Langfuse off; every run regenerates all stages, so the canvases evaluated differ between runs. **The sample is small (3 runs per idea and condition, 18 runs, 9 per condition): these are indications, not significance.** Nothing was tuned afterwards.

### Threat scores and iterations

Histogram = number of threat ratings with score 1 / 2 / 3 / 4 / 5 over all Swots of the three runs (21 ratings per Swot).

| idea | condition | threat ratings | share >= 3 | histogram 1 / 2 / 3 / 4 / 5 | iterations per run | final version per run | cycle tokens (in / out, 3 runs) | wall-clock of the cycle row |
|---|---|---|---|---|---|---|---|---|
| farm produce boxes (1 segment) | before | 189 | 96.8 % | 0 / 6 / 38 / 108 / 37 | [3, 2, 4] | [2, 1, 3] | 46,834 / 27,744 | 55-129 s |
| farm produce boxes (1 segment) | after | 210 | 87.6 % | 7 / 19 / 65 / 96 / 23 | [3, 2, 5] | [2, 1, 5] | 53,820 / 30,631 | 52-167 s |
| photographers and studios (2-sided) | before | 126 | 97.6 % | 0 / 3 / 29 / 77 / 17 | [2, 2, 2] | [1, 1, 1] | 27,879 / 16,161 | 53-55 s |
| photographers and studios (2-sided) | after | 231 | 90.9 % | 9 / 12 / 69 / 124 / 17 | [5, 3, 3] | [4, 2, 2] | 62,836 / 35,889 | 81-164 s |
| standing desks + laser cutting | before | 147 | 93.9 % | 0 / 9 / 46 / 92 / 0 | [2, 2, 3] | [1, 1, 2] | 35,533 / 21,217 | 59-97 s |
| standing desks + laser cutting | after | 168 | 86.3 % | 5 / 18 / 70 / 75 / 0 | [3, 2, 3] | [2, 1, 2] | 43,017 / 25,746 | 59-100 s |

All ideas pooled:

| condition | runs | Swots (iterations) | threat ratings | share >= 3 | histogram 1 / 2 / 3 / 4 / 5 | cycle tokens (in / out) |
|---|---|---|---|---|---|---|
| before | 9 | 22 | 462 | 96.1 % | 0 / 18 / 113 / 277 / 54 | 110,246 / 65,122 |
| after | 9 | 29 | 609 | 88.5 % | 21 / 49 / 204 / 295 / 40 | 159,673 / 92,266 |

### Score series per run (weighted weakness + threat score, version order)

| idea | condition | run | scores | final version |
|---|---|---|---|---|
| farm produce boxes (1 segment) | before | 1 | [284, 101, 128] | 2 |
| farm produce boxes (1 segment) | before | 2 | [88, 130] | 1 |
| farm produce boxes (1 segment) | before | 3 | [120, 97, 78, 132] | 3 |
| farm produce boxes (1 segment) | after | 1 | [170, 77, 123] | 2 |
| farm produce boxes (1 segment) | after | 2 | [68, 175] | 1 |
| farm produce boxes (1 segment) | after | 3 | [236, 183, 106, 90, 74] | 5 |
| photographers and studios (2-sided) | before | 1 | [79, 157] | 1 |
| photographers and studios (2-sided) | before | 2 | [84, 182] | 1 |
| photographers and studios (2-sided) | before | 3 | [87, 133] | 1 |
| photographers and studios (2-sided) | after | 1 | [139, 110, 75, 72, 82] | 4 |
| photographers and studios (2-sided) | after | 2 | [83, 78, 78] | 2 |
| photographers and studios (2-sided) | after | 3 | [167, 72, 81] | 2 |
| standing desks + laser cutting | before | 1 | [98, 177] | 1 |
| standing desks + laser cutting | before | 2 | [193, 194] | 1 |
| standing desks + laser cutting | before | 3 | [166, 155, 168] | 2 |
| standing desks + laser cutting | after | 1 | [211, 164, 171] | 2 |
| standing desks + laser cutting | after | 2 | [95, 175] | 1 |
| standing desks + laser cutting | after | 3 | [187, 145, 171] | 2 |

### ERRC v2 in the same 18 runs

No move broke the field rule of an action (`new_text` / `target_card_text` per action) and no conversion or structure retry of any kind happened: **0 field-rule retries and 0 conversion retries in 18 runs** (the retry path, whose message names the action and the field, e.g. "new_text must be provided when action is RAISE.", is covered by tests only). No `eliminate` move was proposed in any of the 18 runs (before: 29 raise, 13 reduce, 16 create; after: 39 raise, 18 reduce, 23 create). In iterations 2 and later, a reduce/raise targeted a card marked by the previous step in 1 of 11 cases (before) and 1 of 30 (after); in the earlier slice 3 runs (ERRC v1, text unchanged) the same card was raised in four consecutive iterations.

## Slice 4: `storytelling`, `future_scenario`, `pitch` (2026-10-08, `scripts/slice2_dry_run.py`, three of the five earlier ideas, one run each)

Whole pipeline through `pitch` against the fake backend, real generator, **fake judge** (no `JUDGE_*` configured), so judge tokens are not counted. Prompt versions: `storytelling` 1, `future_scenario` 1, `pitch` 1; `swot` 2 and `errc` 2 as in the follow-up above. No optional stage enabled; `project_status` on the fake backend reached `completed` in all three runs. **0 retries of any kind** (0 consistency, 0 field-rule, 0 conversion/structure) in all three runs.

| stage | prompt version | idea | calls | input | output | total | wall-clock |
|---|---|---|---|---|---|---|---|
| storytelling | 1 | farm (EN) | 1 | 2,332 | 735 | 3,067 | 6.7 s |
| storytelling | 1 | photo (EN) | 1 | 3,202 | 702 | 3,904 | 6.4 s |
| storytelling | 1 | split (EN) | 1 | 3,130 | 714 | 3,844 | 6.9 s |
| future_scenario | 1 | farm (EN) | 1 | 3,231 | 866 | 4,097 | 9.4 s |
| future_scenario | 1 | photo (EN) | 1 | 3,348 | 1,039 | 4,387 | 11.4 s |
| future_scenario | 1 | split (EN) | 1 | 3,310 | 1,023 | 4,333 | 12.0 s |
| pitch | 1 | farm (EN) | 1 | 2,493 | 711 | 3,204 | 7.6 s |
| pitch | 1 | photo (EN) | 1 | 2,670 | 839 | 3,509 | 9.1 s |
| pitch | 1 | split (EN) | 1 | 2,644 | 830 | 3,474 | 8.3 s |

Whole run (all stages, the earlier ones included):

| idea | rows | LLM calls | total tokens | cycle: scores, final version |
|---|---|---|---|---|
| farm (EN) | 10 | 12 | 40,759 | [84, 154], 1 |
| photo (EN) | 13 | 15 | 53,709 | [77, 103], 1 |
| split (EN) | 13 | 17 | 63,523 | [113, 90, 183], 2 |

The three new stages cost about 10.4k (farm), 11.8k (photo) and 11.7k (split) tokens, 18 to 25 % of a run; the cycle is still the largest single row (15.0k, 15.8k, 26.3k). The longest row is the cycle (54 s, 60 s, 94 s against a lock renewal of 900 s); storytelling, future_scenario and pitch take 6 to 12 s each. These are one run per idea, not an average: the earlier stages are generated again in every run, so the totals differ between runs of the same idea.

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
