# Babelbetes Output Screening

*Validation plan for the Babelbetes standardized output — method note and first-pass evidence.*
*Draft for review, 5 September 2026.*

One automated screen over the standardized Parquet output, one decision boundary per check, one
adjudication log. This is the method we are going to run — and the first-pass evidence from running
it over all nine datasets.

---

## The decision

**A single screening pass over the output, not a second research project.**

Everything Babelbetes needs is computable from the standardized event streams alone. One engine
reduces the store to a `(study, patient, day)` metric table; a short declarative bounds list turns
each metric into a **hard** (fix-or-approve) or **soft** (investigate) flag; every flag that fires is
adjudicated once and recorded with a cause and a disposition. Five figures and three tables come out
of it.

Nothing in this screen requires resampling, IOB/COB reconstruction, or any part of the AIDIF model.
That is a scope boundary, not a shortcut — see §3.

---

## 1. Where we stand

Four approaches have been on the table. They are not competitors; they are the same argument at four
levels of ambition, and each one contributed a piece we keep.

- **The per-study analysis notebooks.** Face validation, already performed while building each
  parser — daily traces inspected by eye, TDD compared against reported values, distributions
  sanity-checked. This is the foundation. It exists. It only needs to be written down.
- **The snapshot system** (`compute / snapshot / diff`, SPL Mar 2026). Its real contribution is
  *regression control*: prove that a code change moved only what it was supposed to move. Keep it for
  exactly that, not as the validation argument.
- **The four activities in the paper draft** — range checks, correlation, outcome matching, sample
  testing. Correct shape. What was missing were the decision boundaries and what happens after a
  check fires.
- **The V&V outline** (27 Jul 2026). This is the one to read again, because §0.2 already settles the
  argument: the posture is *descriptive, face-validation-first, minimize net-new work*, tiered
  **T1 already done · T2 cheap corroboration · T3 defer**. T2 is spelled out as "automated hard-bound
  sanity checks + TDD reconciliation + determinism — run once over the Parquet outputs."

> The heavy machinery — exhaustive unit-test batteries, formal challenge-set curation, matrix
> profiles, IOB~EGV correlation structure — is already classified T3 in that document: "build only if
> a reviewer asks — not required for the sufficiency argument."

So the disagreement is smaller than it feels. What follows is T2, made concrete and made to produce
figures.

---

## 2. What the screen is actually for

The claim at the end is deliberately narrow, and it is the honest one:

> Every physiologically impossible value and every structurally suspicious patient in the Babelbetes
> output was found by a documented, reproducible screen, inspected, and given a cause. The defects we
> found were fixed; the rest are real — real physiology or real artifacts of the source records — and
> are retained on purpose.

That last clause is not a hedge, it is the point. AIDIF simulates reality, and reality contains
imperfect device data. A patient whose insulin requirement doubles mid-study turned out to be
pregnant. Implausibly large pen doses turned out to be priming. A controller that meets those in
silico is being tested honestly. The screen's job is therefore to **separate defect from phenomenon**,
not to clean the data.

---

## 3. The scope line, and how to defend it

Every metric in this screen is computed from the Babelbetes output *as it is defined*: irregular
event streams, local time, no resampling. Nothing derived by a model enters.

**IOB, COB, rate-of-change against IOB, matrix profiles and the geometric-mean/SD envelopes belong to
AIDIF, not here.** They require a 5-minute grid, an insulin PK model, and parameter choices that are
themselves AIDIF artifacts. Validating Babelbetes with them would validate the AIDIF model on
Babelbetes data — the wrong direction, and it would break the interim-sub-V&V roll-up, which requires
that each transform be verifiable on its own terms before the next consumes it.

The one thing we lose is the IOB~EGV plausibility view. It is replaced by cheaper evidence for the
same property: the circadian CGM/insulin profile (local time is right), TDD reconciliation against
reported values (insulin magnitude is right), and basal/bolus split (insulin composition is right).
Where the AIDIF chunking V&V does compute IOB, that check lands there.

---

## 4. The engine

Five stages, one direction, no loops. Stages 1–2 are automated and rerun in under a minute; stage 3
is where the human time goes.

| Stage | What | How |
|---|---|---|
| 1 · reduce | Daily metric table | One row per study × patient × day, ~35 columns. 510,672 rows, 49 s, 37 MB. |
| 2 · decide | Bounds → flags | A declarative list of `(metric, H/S, predicate, rule)`. Every check carries an action; no bare thresholds. |
| 3 · adjudicate | Challenge set | All hard hits plus the top-N per soft rule. Each is drawn as a patient-day trace and given a cause. |
| 4 · dispose | Disposition log | One row per case: cause, class, action, resolved. Defects go back into the parser; the rest are documented. |
| 5 · report | Figures & tables | F1–F5 and T1–T3 regenerate from the same table after any fix, with a before/after delta. |

Why one intermediate table matters: it is the artifact that makes the screen reproducible and cheap
to rerun. Fix a parser, rerun the pipeline, rebuild the table, and every number, flag and figure in
the paper updates — including the delta against the previous snapshot. That is where the existing
snapshot/diff system plugs back in.

---

## 5. The check catalog

Twenty checks in five families. Sixteen are one line each against the daily table; four are the
external reality anchors. **HARD** means a physiologic or device impossibility — tolerance zero,
every hit is fixed or formally approved. **SOFT** means suspicious but possible — the hit does not
fail anything, it enters the challenge set.

### T1 — Check catalog

| ID | Check | Boundary | Type | Grain |
|---|---|---|---|---|
| **A · Conformance** — does the output obey its own schema and the device envelope? ||||
| CF-1 | CGM value inside the sensor range, integer-valued | [40, 400] mg/dL | HARD | point |
| CF-2 | No nulls in `cgm`, `bolus`, `basal_rate`; timestamps present and sorted | 0 | HARD | point |
| CF-3 | Bolus dose within the pump envelope | [0, 30] U | HARD | point |
| CF-4 | Basal rate within the pump envelope | [0, 35] U/h | HARD | point |
| CF-5 | Extended-bolus duration valid | 0 or (0, 8] h | HARD | point |
| CF-6 | Announced carbs per entry (Loop, ReplaceBG) | [0, 300] g | HARD | point |
| **B · Completeness** — is anything silently missing, and would we know? ||||
| CP-1 | CGM uptime per day (5-min bins occupied) | < 70 % | SOFT | day |
| CP-2 | Largest intraday CGM gap | > 6 h | SOFT | day |
| CP-3 | **CGM present, insulin entirely absent** — the undetectable-gap case | any day | HARD | day |
| CP-4 | A patient is missing a whole stream (CGM, bolus or basal) | any patient | HARD | patient |
| CP-5 | Stream alignment: basal/bolus start & end vs. CGM | abs(Δ) > 7 d | SOFT | patient |
| CP-6 | Longest run of consecutive days with no data of any type | > 7 d | SOFT | patient |
| **C · Plausibility, aggregate** — is the reconstructed insulin the right size and shape? ||||
| PL-1 | **TDD = 0 on a day that has CGM data** | any day | HARD | day |
| PL-2 | Daily TDD outside the physiologic band | < 5 or > 150 U | SOFT | day |
| PL-3 | Basal share of TDD | outside [0.2, 0.8] | SOFT | patient |
| PL-4 | A day's basal dose carried by a single segment longer than a day — terminal-record / gap ambiguity | > 24 h | SOFT | day |
| PL-5 | Daily CGM mean / CV outside the plausible envelope | mean ∉ [80,300]; CV ∉ [0.10, 0.50] | SOFT | day |
| PL-6 | Temporal duplicate boluses — equal dose ≥ 0.5 U within 5 min | rate vs. study norm | SOFT | patient |
| **D · Plausibility, temporal** — does time behave? ||||
| TM-1 | Circadian profile present with correct phase (meal peaks, overnight AID drop) — evidence local time reconstructed correctly | visual, per study | FIGURE | study |
| TM-2 | **Therapy regime shift**: step in the 14-day rolling median TDD | > 50 % | SOFT | patient |
| TM-3 | CGM rate of change between consecutive samples | > 6 mg/dL/min | SOFT | day |
| **E · Reality anchors** — the only external references we have ||||
| OM-1 | Patient count and study duration vs. published | exact / near | HARD | study |
| OM-2 | Mean TDD vs. reported, where reported | ± 5 % (Loop, ReplaceBG); ± 10 % other | HARD | study |
| OM-3 | TIR / TBR / TAR vs. published, where reported | ± 5 pp | SOFT | study |
| OM-4 | Determinism: rerun the pipeline, compare the daily table | identical | HARD | store |

---

## 6. Why the soft numbers do not need to be right

This is the question that has been blocking the section, and it dissolves once the two kinds of
boundary are kept apart.

**Hard boundaries are derived, not chosen.** They come from the sensor range, the pump envelope, and
arithmetic — a negative dose, a rate no pump can deliver, a CGM value the sensor cannot report,
insulin that is zero on a day the patient was clearly alive and wearing a sensor. There is no
acceptance rate to argue about because the tolerance is zero. Every hit is either corrected in the
parser or formally approved with a written mechanism.

**Soft boundaries are sampling instruments.** Their job is to rank patients by how much they deserve
a look, and to make the ranking reproducible and disclosed. A soft boundary is set so the tail it
selects is a workable number of cases — a few dozen per rule — and it is reported together with the
resulting *N*, so a reader can see the sampling intensity rather than guess at it. Nothing passes or
fails on a soft boundary.

That is the answer to the draft's open "5 % acceptance rate?" question: **there is no global
acceptance rate, because soft checks are not accept/reject gates.** What we report instead is: for
each rule, the boundary, how many patient-days and patients it selected, how many were inspected, and
what they turned out to be.

This also protects against the failure mode the draft and DATA-CARE both warn about — over-cleaning.
Nothing is ever dropped because a soft boundary fired. High variability is the signal we want to
preserve.

---

## 7. What happens to a finding

Every case that enters the challenge set leaves it with one of four labels. The distribution of
labels is the result of the whole exercise — and the reason the exercise is worth doing is that only
one of the four is a defect.

| Class | Meaning |
|---|---|
| **P — Physiology** | Real and explainable — pregnancy, honeymoon phase, illness, a genuine regimen change. Retained unchanged; the case is written up as evidence the screen distinguishes signal from fault. |
| **A — Source artifact** | Real in the study record but not in the patient — pen priming logged as a dose, a device export duplicated upstream, a sensor sentinel value. Retained and documented; optionally annotated with a quality flag. This is the class AIDIF *wants* to keep. |
| **D — Babelbetes defect** | The reconstruction was wrong. Fixed in the parser, unit test added, pipeline rerun, and the before/after delta on the affected aggregates reported. These are the cases that carry the credibility of the whole section. |
| **O — Open** | Could not be resolved with the information available. Named explicitly in the limitations subsection with its bound — never left silent. |

### The log

One table, one row per case:
`case_id · study · patient · check_id · value · boundary · figure · cause · class (P/A/D/O) · action · resolved`.

It is **T3** of the paper and the audit trail underneath the closing claim. Roughly one paragraph of
writing per case, and a dozen or two worked cases is plenty — the argument is made by the systematic
coverage, not by the case count.

---

## 8. First pass — what the screen found

The engine and checks A–C ran over all nine datasets: **510,672 patient-days**, 2,572 patients. These
are raw hits, not adjudicated cases — the point is that the screen is discriminating, and that its
first output is already a work list rather than a green light.

| Check | Count | Finding |
|---|---|---|
| CF-1 | 1,628 | patient-days in **T1DEXI / T1DEXIP** carry CGM values of exactly **39 or 401** — a different out-of-range sentinel convention from the seven studies clamped to [40, 400]. A conformance break against our own documented CGM model. |
| CF-4 | 578 | patient-days with a basal rate above **35 U/h** (Loop 265, IOBP2 208, T1DEXI 103, T1DEXIP 2). The largest is **11,160 U/h** in T1DEXI — a unit or magic-number problem, not a therapy. |
| CP-3 | 15.8 % | of **Loop** CGM-days carry **no insulin data at all** — no bolus, no basal. Also T1DEXI 6.7 %, T1DEXIP 4.0 %, ReplaceBG 2.0 %. Exactly the silent gap that must not reach a simulator undeclared. |
| CP-5 | −154 d | median offset between the start of the **DCLP5** basal stream and its CGM stream; 88 of 100 patients are misaligned by more than a week, up to 331 days. Pump history predating the CGM record. |
| CP-4 | 13 / 99 | **DCLP3** has 13 of 125 patients with no CGM whatsoever; **T1DEXI** has 99 of 497 patients with no bolus data and T1DEXIP 46 of 247. |
| PL-1 | 1.33 % | of **DCLP5** patient-days reconstruct to a TDD of exactly zero while data is present — the zero-TDD case, now counted rather than suspected. |
| PL-4 | 7,400 | **Flair** patient-days whose basal dose is carried by a single segment longer than 24 h (Loop 4,425). The terminal-record ambiguity described in §3.4 of the paper, quantified for the first time. |
| CF-3/5 | 14 | **Loop** patient-days above the 30 U bolus envelope (max 46 U) and 11 with an extended-bolus duration beyond 8 h. Small enough to adjudicate individually — the pen-priming candidates. |

One check needs recalibrating before it is useful: PL-6 as written flags a mean of 37 duplicate
boluses per day in Flair, because AID micro-boluses legitimately repeat identical doses within
minutes. The ≥ 0.5 U floor in T1 is the fix — a good illustration of why the boundaries get set
against the data rather than in advance.

### Stream availability by study

Fraction of each study's patient-days carrying each combination of streams. Composition, not just
coverage — a study that is 99 % "CGM only" is not 99 % complete.

| Study | all three | CGM + partial insulin | CGM only | insulin only | patient-days |
|---|---|---|---|---|---|
| DCLP3 | 86.5 % | 0.2 % | 0.1 % | 13.3 % | 23,559 |
| DCLP5 | 96.9 % | 0.0 % | 0.0 % | 3.1 % | 20,692 |
| Flair | 77.9 % | 13.0 % | 0.2 % | 8.9 % | 24,352 |
| IOBP2 | 99.1 % | 0.1 % | 0.0 % | 0.8 % | 30,504 |
| Loop | 79.2 % | 1.9 % | 15.2 % | 3.7 % | 325,171 |
| PEDAP | 99.6 % | 0.2 % | 0.0 % | 0.2 % | 23,814 |
| ReplaceBG | 92.4 % | 1.7 % | 1.9 % | 4.0 % | 46,390 |
| T1DEXI | 76.2 % | 16.1 % | 6.6 % | 1.1 % | 13,675 |
| T1DEXIP | 79.9 % | 15.1 % | 4.0 % | 1.0 % | 2,515 |

![F1 — Stream availability per patient-day](assets/F1_coverage.png)

**F1 — Stream availability per patient-day.** One row per patient, one column per day since that
patient's first record, sorted by record length. This single figure carries most of the completeness
argument: DCLP3's and Flair's insulin-only run-in periods, DCLP5's pump history preceding the CGM
record, Loop's CGM-only stripes, T1DEXI's patients without bolus data, and IOBP2's clean protocol
boundary at day 95 are all visible without a table.

---

## 9. What goes in the paper

### T2 — Figure and table set for the V&V section

| ID | What | Which claim it carries | Status |
|---|---|---|---|
| F1 | Stream-availability matrix, 9 panels | Completeness: gaps, overlaps and stream composition are known and bounded | DONE |
| F2 | Check × study heatmap: % of patient-days flagged, hard vs soft | The screen ran on everything; nothing was cherry-picked | open |
| F3 | TDD panel: per-study distribution, basal/bolus split, reported-TDD anchor | Insulin reconstruction is the right magnitude and composition | open |
| F4 | Circadian profile: mean CGM and insulin by time of day, per study | Local-time reconstruction is correct; physiology behaves as expected | open |
| F5 | Two or three adjudicated cases as annotated patient-day traces | Flags were actually inspected, and defect was separated from phenomenon | open |
| T1 | Check catalog (§5 of this document) | Every check has a boundary, a type and an action | DONE |
| T2 | Results per check per study: boundary, N selected, N inspected, disposition | OHDSI DQD-style reporting, extended with hard/soft | open |
| T3 | Disposition log | The audit trail under the closing claim | open |

---

## 10. Plan

| Day | Focus | Items |
|---|---|---|
| 1 — done | Engine | Daily metric table over all nine studies · F1 stream-availability matrix · first-pass hit counts (§8) |
| 2 | Checks & figures | Bounds list and evaluation · calibrate soft boundaries against the observed tails · F2, F3, F4 |
| 3 | Adjudication | Challenge set: all hard hits, top-N per soft rule · patient-day traces · fill T2 and the T3 disposition log; F5 |
| 4 | Write-up | V&V section against the 27 Jul outline's structure · limitations: the O-class cases, named with bounds · rerun everything once; report the before/after delta |

If a day is lost, Day 3 shrinks, not Day 2. A screen that ran everywhere with a dozen adjudicated
cases is a complete argument; a screen with fifty cases and no coverage is not.

---

*Structure follows the V&V section outline of 27 July 2026 (§0.2 posture, §V&V.4 decision boundaries,
tier T2) and the Kahn conformance / completeness / plausibility taxonomy, reported in the Book of
OHDSI Ch. 15 table format.*
