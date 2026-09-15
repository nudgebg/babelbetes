# Babelbetes Output Verification

*Verification plan for the Babelbetes standardized output.*
*Draft for review, September 2026.*

Exhaustive metric computation over all patients in all studies, followed by targeted inspection of
the extremes. This document defines the metrics, how outliers are identified, and how findings are
classified and resolved.

---

## 1. Scope and verification target

Babelbetes brings datasets from several high-quality clinical trials into a common schema. The source
data is already of high quality and has been used in regulatory submissions; what has to be
established is that the **reconstruction of the original event series is accurate**. That is not
trivial: formats and sources vary, much of the encoding is device-specific, and the interpretation
leaves considerable room for human error.

Formal validation as described in V&V 40 for CM&S is specific to a context of use, and risk
management depends on the context of use in mind. Babelbetes provides a standardized view of the data
through transformation and will be used across many different contexts of use. Formal validation and
risk management without a specific context of use therefore do not apply.

What this document describes is consequently **verification, not validation**. Validation asks
whether the output is fit for an intended use; with no context of use there is none to ask about. The
question that remains — does the output state what actually happened? — is a verification question.

*A note on vocabulary.* Kahn et al. use the two terms on a different axis, where verification means
expectations derived internally and validation means comparison against an external gold standard. On
that axis this work is also predominantly verification; the one exception is outcome matching against
published study results.

We instead define the verification target as **reconstructing reality as closely as possible**,
established in four steps:

1. **Exhaustive investigation** — per-dataset notebooks documenting every decision and finding.
2. **Code verification** — formal schema validation and unit tests for the transformation logic.
3. **Face validation** — plotting the data and inspecting it for expected trends and distributions.
4. **Output screening and sample inspection** — exhaustive metric computation over all patients,
   followed by targeted inspection of the extremes. This document.

Steps 1–3 are already in place and documented in the repository — the per-dataset notebooks, the
schema validation and unit tests, and the plots produced while building each parser. This document
covers step 4.

> Physiologically impossible value and structurally suspicious data in the Babelbetes output 
> were systematically searched and inspected and if deemed to be erroneous either fixed or excluded.


---

## 2. Process

1. **Compute** — every metric, for every patient, in every study.
2. **Identify** — hard violations and soft outliers, per study.
3. **Select** — the cases to inspect.
4. **Inspect and record** — each case receives a source-fidelity judgement, an explanation and a
   decision.
5. **Resolve and repeat** — corrections go back into the parsers; the screen is re-run and compared
   against the previous run.

Metrics are computed once and stored, so every figure and table regenerates after a correction. The
comparison against the previous run is what shows that a fix moved what it was supposed to move, and
nothing else.

---

## 3. Face validation

Before any metric was defined, the data was looked at. While building each parser, distributions were
plotted and compared — glucose and dose distributions, daily patterns, circadian rhythms — within a
study and across studies, and checked against what is clinically expected.

The question at this stage is whether anything looks wrong, and it is answered by eye. Circadian
rhythms are checked for the expected patterns arising from daily glucose and insulin demands; their
absence points to an unresolved time-shift or timezone problem. Where studies differ drastically, the
difference has to be traced and explained by the device, the protocol or the population. A pediatric
study with much lower daily totals is expected; a study whose basal distribution sits far from the
others is not, and is investigated until the difference is understood or the reconstruction is
corrected.

Face validation is qualitative and open-ended, which is both its strength and its limit: it catches
things no metric was written for, but it does not scale to every patient and leaves no record of what
was covered. Output screening is its systematic continuation — the same comparisons, computed for
every patient, with an explicit rule for what counts as surprising.

---

## 4. Metrics

The metric set is motivated by the failure modes encountered while building the parsers. Those
specific defects are documented and largely fixed; the metrics are not there to re-find them, but to
detect the **effects that similar problems would produce**. Most of the complexity sits in insulin and
in time reconstruction, which is why most metrics are targeted at these.

All metrics are computed directly from the standardized event streams. Every metric is computed for
all patients in all studies. The screen then inspects the **extremes**; how outliers are identified
and how many of them are selected for inspection is defined in the next section.

| Observable effect | Example failure mode |
|---|---|
| **Too much insulin** | temporal duplicates · priming doses · MDI injections · temp-basal percentages not applied or applied twice · basal reported during AutoMode micro-bolus periods · missing suspends · extended boluses reported twice |
| **Too little insulin** | basal stream never imported or stopping mid-record · data gaps · a single rate carried across a long interval · terminal records of undefined duration |
| **Incomplete or misaligned coverage** | streams imported from different sources or periods · data beyond the study duration imported for individual data types · carb records split across files |
| **Signal shifts, unexpected temporal patterns** | local time reconstructed from incomplete timezone information · streams spliced from several sources · sampling cadence departing from the device interval |

### Two challenge sets

Findings are collected into two sets with different pass criteria. The distinction is not one of
severity, but of whether a reference value exists.

The **hard set** collects observations that are physiologically or technically impossible, or very
nearly so: values outside the device reporting range, magic numbers used to encode sensor failures,
doses no pump can deliver, exact duplicates, a day with no insulin at all. Nothing here needs
calibration — a reference value exists and the observation violates it. The pass criterion is that
the set is empty: every entry is either corrected, or explicitly approved with a documented
mechanism.

The **soft set** collects outliers in trends and distributions — patients whose totals, variability,
coverage or composition sit far from the rest of their study. These may be extreme but genuine
therapy, or they may point to a data error; the metric itself cannot tell. There is no reference
value, only a distribution, which differs by study, device and population, so detection is relative
to the patient's own study. The pass criterion is not emptiness — there is always a most extreme
patient — but that every entry has been inspected and explained.

### A · Schema conformance

Babelbetes validates the output schema as part of the pipeline. These metrics check once more, on the
written output, whether anything was missed. Point level, all hard; the expected value of every one
of them is zero.

| Metric | Definition | Unit | Examples |
|---|---|---|---|
| CGM bounds | share of samples below the sensor minimum, above the sensor maximum, and not integer-valued | % of samples (3 values) | magic numbers encoding sensor failures — e.g. 39 and 401 where the reporting range is 40–400 |
| Bolus bounds | share of doses below 0 and above the device maximum | % of boluses (2 values) | doses beyond what the pump can deliver — e.g. a 46 U bolus on a pump capped at 30 U |
| Basal rate bounds | share of events below 0 and above the device maximum | % of events (2 values) | unit and encoding errors — e.g. a rate of 11 160 U/h |
| Carb bounds | share of entries below 0 and above the physiologic maximum | % of entries (2 values) | implausible entries — e.g. a negative amount, or a single 3 000 g meal |
| Overlapping boluses | share of boluses whose delivery interval extends past the start of the next | % of boluses | the same extended bolus written twice, once at start and once at completion |

### B · Data coverage

Defined over the **mandatory streams** — CGM, bolus and basal. Carbs are reported as coverage only,
since they exist in two datasets. For a stream *s*, let *first(s)* and *last(s)* be the first and last
day carrying data.

**Union span\*** — the full extent of the patient's record:

```
union_span = max( last(cgm), last(bolus), last(basal) )
           - min( first(cgm), first(bolus), first(basal) ) + 1
```

**Core span\*** — the window bounded by all three streams, clamped at zero:

```
core_span  = max( 0,  min( last(cgm),  last(bolus),  last(basal)  )
                    - max( first(cgm), first(bolus), first(basal) ) + 1 )
```

| Metric | Definition | Unit | Examples |
|---|---|---|---|
| Span efficiency | core_span\* ÷ union_span\* | ratio, 0–1 | streams that do not start and stop together — e.g. pump history imported for months before the CGM record begins |
| Core completeness | days inside core_span\* carrying all mandatory streams ÷ core_span\* | ratio, 0–1 | holes inside the covered window — e.g. a week in which only CGM was recorded |
| Core coverage per stream | days inside core_span\* carrying that stream ÷ core_span\* | ratio, 0–1 (3 values, 4 where carbs exist) | a stream that is thin throughout — e.g. carb records split across two files with a gap between them |
| Gap size | geometric mean and geometric SD of intervals between consecutive events of a stream, inside core_span\* | hours; SD dimensionless (2 values per stream) | long intervals between events of one type — e.g. a basal rate carried unchanged for three weeks |

**Span efficiency and core completeness are independent by construction**: the first describes the
edges of the record, the second its interior. Read together they separate two different problems. A
patient at 0.98 / 0.55 has clean edges and a shredded interior — an import problem. One at
0.40 / 1.00 has intact data with an overhanging import, and is a candidate for clipping rather than
correction.

### C · Plausibility

Daily totals are the substrate; every metric reports one value per patient.

| Metric | Definition | Unit | Type | Examples |
|---|---|---|---|---|
| Zero-dose days | days with TDD < 1 U | count, and % of core days | hard | basal never imported, or a stream stopping mid-record |
| TDD μ\* | robust geometric mean of daily totals | U/day | soft | a record shifted in level — e.g. a standard basal rate profile counted on top of Loop micro-bolusing, leaving a patient with an extremely high total for their study; or temp-basal percentages never applied |
| TDD σ\* | robust geometric SD of daily totals | ratio, ≥ 1 | soft | widespread instability — e.g. a therapy change mid-study, or systematically incomplete days |
| TDD max multiple | highest daily total ÷ μ\*, with the date | ratio, ≥ 1 | soft | a single extreme day — e.g. a priming dose recorded as a 40 U bolus |
| TDD min multiple | μ\* ÷ lowest daily total over days ≥ 1 U, with the date | ratio, ≥ 1 | soft | partial under-delivery — e.g. a day on which only half the basal was imported |
| Basal share | basal dose ÷ TDD | ratio, 0–1 | soft | basal rates missing or incorrectly transformed — e.g. incorrectly derived from MDI injections, or double-counted during AutoMode. A share near zero is correct for MDI patients |
| Duplicate count | near-identical doses ≥ 0.5 U within one minute | count, and % of boluses | soft | the same bolus recorded twice, with or without a rounding difference |
| CGM rate of change | largest absolute change per minute between consecutive samples | mg/dL per minute | soft | discontinuities where segments with different time offsets were spliced — e.g. glucose jumping 120 mg/dL between two five-minute samples |

μ\* and σ\* are estimated robustly, from the median and MAD of the log daily totals. This keeps them
insensitive to single extreme days, so that σ\* responds to *widespread* deviation while the max and
min multiples respond to *single* events — the two therefore carry different information.

The min multiple is computed only over days that pass the zero-dose check, so that it measures
partial under-delivery rather than restating a hard metric.

---

## 5. Outlier identification

For sample inspection we focus on outliers. Outliers are defined relative to the study population,
because expected values depend on the study's device, protocol and population — frequent basal rate
change intervals are normal in one study and alarming in another. Sampling each study separately also
keeps the inspection from collapsing onto the single most extreme study.

Hard metrics need no selection: a reference value exists, and any violation enters the hard set. Soft
metrics come in two kinds:

| Metrics | Reference | An outlier is |
|---|---|---|
| Span efficiency, core completeness, duplicate count, zero-dose days | a constant — 1 or 0 | a large distance from it |
| TDD μ\*, TDD σ\*, min and max multiple, basal share, gap sizes, CGM rate of change | the study population | a large deviation from its center |

Population parameters are estimated **robustly**, from the median and MAD. Classical estimates are
pulled toward the extremes they are meant to find, so correcting those patients shifts the center and
declares a new set of ordinary patients extreme — a cascade that never ends.

Two separate decisions then follow. An **outlier** is a surprising finding, for example more than
three robust standard deviations from the population center; the size of that set is reported, not
capped. **Inspection** covers *n* of them, which reflects available time rather than the data. Both
are reported together: *41 outliers, 5 inspected*.

A **case** is a patient, not a metric hit — one cause typically trips several metrics at once, and
they are inspected together. Counting metric hits would give studies × metrics × *n* cases; counting
patients gives studies × *n*. Per study we therefore take *n* patients, plus — for any metric whose
outliers are not already represented among those *n* — its most extreme patient, so that no metric
goes unexamined. Where a metric carries a date (TDD max and min multiple), inspection starts at that
day.

> **TBD** — the deviation that defines an outlier (start: 3 robust SD), *n* (start: 5 per study), and
> whether the *n* are the most extreme or a random draw from the set.

---

## 6. Case handling

Every inspected case is recorded with three independent pieces of information.

**1 — Is it faithful to the source?**
Whether the output correctly reflects the source record under the documented reconstruction rules.
*Yes · No · Unclear.* A *no* is a Babelbetes defect. *Unclear* covers a source that is ambiguous,
where the reconstruction rests on a documented assumption.

**2 — Is it explainable?**
The cause in plain words: physiology (pregnancy, illness, regimen change), priming dose, MDI therapy,
duplicated export, missing suspend, temp-basal conversion, import gap — or *none found*.

**3 — Is it an error, and does it need a change?**
An error means the output states something that did not happen. The decision follows:

- **Accept** — kept and documented
- **Correct** — fixed in the parser
- **Exclude** — removed from the output

Every decision carries a written rationale.

The three are independent, and that is the point: a value can be faithful to the source and still not
represent what was delivered.

| Faithful | Explanation | Error | Typical decision |
|---|---|---|---|
| yes | physiology | no | accept |
| yes | MDI therapy | no | accept |
| yes | priming dose | yes | accept or exclude |
| yes | none found | unclear | accept, documented |
| no | temp-basal conversion | yes | correct |
| unclear | ambiguous source, documented assumption | unclear | accept, documented |

Priming is the awkward case, and deliberately so. The dose really was delivered by the pump; it
simply did not reach the patient. Whether that counts as an error depends on what the data is used
for — a simulator arguably wants it, because real algorithms will meet it; a cohort analysis does
not. The default is **Accept**; see Open items.

All inspected cases are kept in a log, which remains as the report behind the closing claim and is
the source the reporting tables are aggregated from.

---

## 7. Reporting

For every study the screen produces the fitted population and the outlier set for each metric
together with their sizes, the cases selected for inspection — each with its patient, the metric that
selected it and, where the metric carries one, the date — and the case log once they have been
inspected.

The figures are the same comparisons as in face validation, now with the population fit drawn in and
the outliers marked: metric distributions per study, pairs of metrics that belong together shown
jointly, stream availability per patient-day, and the inspected cases as annotated patient traces. A
metric × study heatmap of outlier counts summarises where the work sits.

Outlier count and inspected count are always reported together, so that sampling intensity is visible
rather than implied.

---

## 8. Phases

| Phase | Work |
|---|---|
| 1 · Implement | metric computation over all nine datasets, reproducible and re-runnable |
| 2 · Screen | population fits per study, outlier sets, selection of cases for inspection |
| 3 · Inspect | work through the selected cases and fill the case log |
| 4 · Resolve | corrections into the parsers, re-run, compare against the previous run |
| 5 · Report | figures, tables and the write-up |

Phases 3–5 repeat until the stop criterion is met.

### Stopping

The screen stops when two conditions hold.

**No open hard cases.** Every violation has been corrected, or explicitly approved with a documented
mechanism. This is absolute: a hard case is an impossibility, and there is nothing to weigh.

**Soft cases at our discretion.** There is no threshold here, because there is always a most extreme
patient. What is weighed is how many of the newly inspected cases turned out to require a fix. If
that share is low enough to accept, the screen stops; if it is not, the corrections are made and the
screen is repeated. The number is reported either way, so the judgement is visible rather than
implied.

A case that has already been inspected and decided is not inspected again in a later round — it is
re-checked: a corrected case must be gone, an accepted case must be unchanged. A fix that moves a
case previously accepted as correct is a warning sign.

---

## 9. Open items

Marked **TBD** in the text and collected here.

| Item | Section |
|---|---|
| The deviation that defines an outlier — start: 3 robust SD | §5 |
| Number of cases inspected per study — start: 5 | §5 |
| Whether the inspected cases are the most extreme or a random draw | §5 |
| Device and physiologic limits per study: CGM reporting range, bolus and basal maxima, carb maximum | §4 |
| Whether source-faithful artifacts such as priming doses count as errors — depends on downstream use, to be decided per use case | §6 |
