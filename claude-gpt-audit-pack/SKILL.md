---
name: claude-gpt-audit-pack
summary: MANUAL-ONLY skill that builds a complete GPT-auditable evidence package on explicit request.
description: >
  MANUAL-ONLY. Invoke ONLY when the user explicitly types /claude-gpt-audit-pack or asks in
  their own words to "build a GPT audit package / 打包给 GPT 审计 / 做一份审计包 / package this
  for external GPT review". Do NOT auto-trigger after ordinary analysis, code, data, or debug
  rounds. When invoked, it builds a complete audit package that lets an external GPT adversarially
  inspect every risky link in the chain: task interpretation, input data, transformations, code
  changes, tests, execution logs, calculations, outputs, assumptions, and final claims — mapping
  every conclusion to primary evidence and shipping an adversarial GPT audit prompt.
---

# Claude → GPT Audit Pack Skill

## Purpose

After Claude completes a meaningful round of work, Claude must produce an **audit package** for external GPT review before treating the result as trusted.

The audit package must make it possible for GPT to audit **every step that could be wrong**, including:

- task interpretation;
- assumptions and definitions;
- data sources, filters, joins, transformations, and validation;
- code changes and unchanged dependency code that affects the result;
- tests, execution commands, logs, and generated outputs;
- numerical calculations, statistical reasoning, charts, tables, and claims;
- final conclusions and recommended next actions.

The core invariant is:

> No conclusion is trusted unless it appears in `CLAIM_LEDGER.md`, is tied to primary evidence, and has been reviewed through the GPT audit prompt.

## Mandatory behavior

Whenever this skill is active, Claude must do the following after each non-trivial work round:

1. Create an audit package directory.
2. Include all files needed to audit the work, not only the final answer.
3. Write a claim ledger listing every conclusion Claude wants the user to believe.
4. Tie every claim to concrete evidence: file paths, line ranges, commands, logs, data artifacts, or calculations.
5. Include exact GPT audit prompts.
6. Mark the work as **not externally audited yet** until the GPT audit response is returned and addressed.

Claude must not present an unaudited result as final. Use this language:

```text
Audit status: NOT_SUBMITTED_TO_GPT
This result has a complete audit package, but it has not yet passed external GPT audit.
```

After GPT audit returns, Claude must classify the state as one of:

```text
GPT_AUDIT_PASS
GPT_AUDIT_PASS_WITH_NOTES
GPT_AUDIT_CONDITIONAL_PASS
GPT_AUDIT_FAIL
PACKAGE_INCOMPLETE
```

If GPT finds a real issue, Claude must fix it or explicitly downgrade the affected claim.

---

# 1. Audit package directory structure

Use this structure unless the project already has a stronger convention:

```text
audit/
  round_XX_<short_slug>/
    00_AUDIT_REQUEST.md
    01_CONTEXT.md
    02_AUDIT_MANIFEST.md
    03_CLAIM_LEDGER.md
    04_EVIDENCE_MAP.md
    05_DATA_AUDIT.md
    06_CODE_AUDIT.md
    07_REPRODUCTION.md
    08_TEST_RESULTS.md
    09_OUTPUT_AUDIT.md
    10_RISK_REGISTER.md
    11_GPT_AUDIT_PROMPT.md
    12_CLAUDE_SELF_CHECK.md
    diffs/
      git_status.txt
      git_diff_stat.txt
      changes.patch
    logs/
      command_log.txt
      test_output.txt
      run_output.txt
    data/
      README.md
      raw_or_sampled_inputs/
      processed_outputs/
      validation_reports/
    outputs/
      final_tables/
      charts/
      generated_files/
    referenced_files/
      README.md
      <copied or excerpted source files when needed>
```

If the task is tiny, Claude may use a compact package, but it must still include:

```text
00_AUDIT_REQUEST.md
01_CONTEXT.md
02_AUDIT_MANIFEST.md
03_CLAIM_LEDGER.md
04_EVIDENCE_MAP.md
07_REPRODUCTION.md
11_GPT_AUDIT_PROMPT.md
diffs/changes.patch     # if code changed
logs/test_output.txt     # if tests or execution occurred
```

---

# 2. What files must be included or referenced

Claude must include the **file closure** of the work: every file that directly or indirectly affects the conclusion.

## 2.1 Always include

Include these in every audit package:

```text
01_CONTEXT.md
02_AUDIT_MANIFEST.md
03_CLAIM_LEDGER.md
04_EVIDENCE_MAP.md
07_REPRODUCTION.md
10_RISK_REGISTER.md
11_GPT_AUDIT_PROMPT.md
12_CLAUDE_SELF_CHECK.md
```

Also include:

```text
diffs/git_status.txt
diffs/git_diff_stat.txt
diffs/changes.patch
logs/command_log.txt
```

If there is no git repository, replace the git files with a manual changed-file list and before/after excerpts.

## 2.2 Files to include for code work

For implementation, debugging, refactoring, or any code-backed claim, include or reference:

1. **Changed files**: every file Claude edited.
2. **Entry points**: scripts, CLI commands, API handlers, notebooks, pipelines, jobs, or functions used to run the work.
3. **Direct dependencies**: files imported or called by the changed files when they affect behavior.
4. **Callers and downstream users**: code that calls the changed function, if behavior compatibility matters.
5. **Tests**: new tests, changed tests, relevant existing tests, fixtures, mocks, snapshots.
6. **Config files**: environment files, config YAML/JSON/TOML, package metadata, lockfiles, Dockerfiles, CI files, Makefiles.
7. **Generated outputs**: files produced by the changed code.
8. **Logs**: stdout/stderr, test logs, benchmark logs, error traces.
9. **Dependency/version evidence**: package manager lockfile, `pip freeze`, `poetry.lock`, `package-lock.json`, `uv.lock`, `requirements.txt`, or equivalent when relevant.

GPT must be able to answer:

```text
What changed? Where is the changed behavior used? How was it tested? What could still be broken?
```

## 2.3 Files to include for data work

For any data-backed conclusion, include or reference:

1. **Raw input data** — ALWAYS, at full size (compressed inside the zip). Size is never an excuse to omit it (see §4.3). Redact only genuinely sensitive fields (secrets/PII).
2. **Data extraction query or script**: SQL, API request, scraping script, loader, notebook cell, or manual source description.
3. **Data schema**: column names, types, units, allowed values, key constraints.
4. **Data dictionary** if available.
5. **Row/column counts** before and after every major transformation.
6. **Checksums or fingerprints** for raw and processed data.
7. **Sampling method** ONLY as a genuine last resort when the full file is unusable on every channel (see §4.3); otherwise ship the full data, not a sample.
8. **Validation report**: missing values, duplicates, invalid keys, outliers, date ranges, units, timezone, encoding, join cardinality.
9. **Transformation code**: scripts/notebooks/functions that clean, filter, join, aggregate, or label the data.
10. **Processed outputs** used in Claude's final claims.

GPT must be able to answer:

```text
Is the data real, correctly loaded, correctly filtered, correctly joined, correctly transformed, and sufficient for the conclusion?
```

## 2.4 Files to include for analytical or numerical claims

For calculations, models, metrics, benchmarks, statistical claims, or charts, include:

1. Formula or method definition.
2. Input table or data slice used for the calculation.
3. Script/notebook that computes the result.
4. Exact command used to run it.
5. Output artifact: table, log, chart, JSON, CSV, or report.
6. Sanity checks and alternative checks, if available.
7. Random seeds, split definitions, train/test boundaries, or benchmark settings.
8. Baseline or comparison method, if the claim is comparative.

GPT must be able to answer:

```text
Do the calculations follow from the data and code? Are the conclusions too strong for the evidence?
```

## 2.5 Files to include for documentation or reasoning-only work

Even if no code changed, include:

1. The original user request or task statement.
2. All source documents used as evidence.
3. Notes or derivations that led to the conclusion.
4. A claim ledger mapping every conclusion to evidence.
5. Uncertainties, assumptions, rejected alternatives, and open questions.

GPT must be able to answer:

```text
Did Claude answer the actual task? Are the assumptions explicit? Are the conclusions supported?
```

---

# 3. Required audit files and templates

## 3.1 `00_AUDIT_REQUEST.md`

```markdown
# Audit Request

Audit status: NOT_SUBMITTED_TO_GPT
Round: round_XX_<short_slug>
Date: <YYYY-MM-DD>
Claude work type: <analysis | code | data | benchmark | mixed>

## What Claude did

<One paragraph summary of the work completed.>

## What must be audited

GPT must audit all of the following:

1. Whether Claude interpreted the task correctly.
2. Whether the included data is valid and sufficient.
3. Whether the transformations and calculations are correct.
4. Whether the code changes are correct and complete.
5. Whether tests and reproduction commands actually support the claims.
6. Whether every claim in `03_CLAIM_LEDGER.md` is supported by primary evidence.
7. Whether there are missing files, missing logs, or untested failure modes.

## Expected GPT output

GPT must return:

- overall verdict;
- blocking issues;
- claim-by-claim audit table;
- data audit findings;
- code audit findings;
- reproduction/test audit findings;
- unsupported or overstated conclusions;
- missing evidence;
- recommended fixes;
- final trust level.
```

## 3.2 `01_CONTEXT.md`

```markdown
# Context

## Original task

<User's exact task or issue summary. Quote exact text when available.>

## Acceptance criteria

- <Criterion 1>
- <Criterion 2>
- <Criterion 3>

## Constraints

- <Known constraints: language, framework, data scope, performance, correctness, compatibility, etc.>

## Claude's final answer or intended conclusion

<The result Claude wants audited. Do not hide uncertainty.>

## Out of scope

<Things Claude intentionally did not handle.>
```

## 3.3 `02_AUDIT_MANIFEST.md`

The manifest is the table of contents GPT uses to know what each file is for.

```markdown
# Audit Manifest

## Package files

| Path | Required? | Purpose | Primary evidence for |
|---|---:|---|---|
| 01_CONTEXT.md | Yes | Task and acceptance criteria | Task interpretation |
| 03_CLAIM_LEDGER.md | Yes | All claims to audit | Final conclusions |
| diffs/changes.patch | If code changed | Exact code changes | Code correctness |
| logs/test_output.txt | If tests ran | Test results | Test claims |
| data/validation_reports/... | If data used | Data quality checks | Data claims |

## Project files referenced or copied

| Path | Included as | Why GPT needs it | Relevant line range |
|---|---|---|---|
| src/... | copied / referenced | changed implementation | Lx-Ly |
| tests/... | copied / referenced | verifies behavior | Lx-Ly |
| config/... | copied / referenced | affects runtime behavior | Lx-Ly |

## Data artifacts

| Path | Type | Rows | Columns | Hash/checksum | Used by claims |
|---|---|---:|---:|---|---|
| data/raw/... | raw input | <n> | <n> | <sha256> | C-... |
| data/processed/... | processed output | <n> | <n> | <sha256> | C-... |

## Commands run

| ID | Command | Working directory | Output file | Exit code |
|---|---|---|---|---:|
| CMD-001 | `<command>` | `<path>` | logs/... | 0 |
```

## 3.4 `03_CLAIM_LEDGER.md`

Every conclusion Claude wants the user to trust must appear here.

```markdown
# Claim Ledger

## Claim table

| Claim ID | Claim | Type | Confidence before GPT audit | Primary evidence | Reproduction/check | What would falsify it? |
|---|---|---|---:|---|---|---|
| C-001 | <Concrete claim> | task/code/data/test/result | 0.xx | <path:line-line or artifact> | <CMD-ID or manual check> | <Specific failure condition> |
| C-002 | <Concrete claim> | code | 0.xx | src/x.py:L10-L40; tests/test_x.py:L5-L30 | CMD-003 | Test fails, edge case not handled, caller contract broken |
| C-003 | <Concrete claim> | data | 0.xx | data/validation_reports/report.md | CMD-004 | Row counts mismatch, duplicate keys, invalid join cardinality |

## Rules

- Do not merge multiple conclusions into one vague claim.
- Do not use `Claude says so` as evidence.
- Prefer primary evidence: source code, raw data, transformation code, logs, test output, generated artifacts.
- A summary file can explain evidence but cannot replace primary evidence.
```

Good claims are specific:

```text
C-014: The implementation now rejects rows with missing `event_time` before joining because `validate_events()` raises `ValueError` when `event_time.isna().any()` is true.
```

Bad claims are vague:

```text
C-014: The data issue is fixed.
```

## 3.5 `04_EVIDENCE_MAP.md`

```markdown
# Evidence Map

## Evidence by claim

| Claim ID | Evidence file | Line range / artifact section | Why this evidence matters | Evidence strength |
|---|---|---|---|---|
| C-001 | src/... | L10-L55 | Shows implemented logic | strong / medium / weak |
| C-001 | tests/... | L20-L80 | Tests expected behavior | strong / medium / weak |
| C-002 | data/validation_reports/... | Section: row counts | Shows data was not silently dropped | strong / medium / weak |

## Evidence gaps

| Claim ID | Missing evidence | Risk |
|---|---|---|
| C-... | <Missing test/log/data/source> | <Why this could invalidate the claim> |
```

## 3.6 `05_DATA_AUDIT.md`

Use this file whenever data affects the result.

```markdown
# Data Audit

## Data lineage

| Stage | Input | Operation | Code/query | Output | Row count | Column count | Notes |
|---|---|---|---|---|---:|---:|---|
| raw | <source> | load | <path> | <path> | <n> | <n> | <notes> |
| clean | <path> | filter/clean | <path> | <path> | <n> | <n> | <notes> |
| join | <path> | join | <path> | <path> | <n> | <n> | join keys, cardinality |
| final | <path> | aggregate/model | <path> | <path> | <n> | <n> | used by claims C-... |

## Required data checks

| Check | Result | Evidence | Risk if wrong |
|---|---|---|---|
| Schema matches expectation | pass/fail/not checked | <path> | Wrong columns/types break conclusions |
| Row counts reconciled between stages | pass/fail/not checked | <path> | Silent data loss or duplication |
| Join cardinality checked | pass/fail/not checked | <path> | Duplicated rows or missing matches |
| Missing values checked | pass/fail/not checked | <path> | Biased or broken outputs |
| Duplicate keys checked | pass/fail/not checked | <path> | Double counting |
| Date/timezone/unit consistency checked | pass/fail/not checked | <path> | Time leakage or misalignment |
| Outliers/range checks done | pass/fail/not checked | <path> | Invalid results |
| Train/test or before/after split valid | pass/fail/not checked | <path> | Leakage or invalid benchmark |

## Known data risks

- <Risk 1>
- <Risk 2>
```

## 3.7 `06_CODE_AUDIT.md`

Use this file whenever code changed or code supports a conclusion.

```markdown
# Code Audit

## Changed files

| File | Change type | Purpose | Key functions/classes | Claims supported |
|---|---|---|---|---|
| src/... | modified | <why changed> | <symbols> | C-... |

## Behavior before vs after

| Area | Before | After | Evidence |
|---|---|---|---|
| <behavior> | <old behavior> | <new behavior> | diffs/changes.patch; tests/... |

## Dependency and call-path notes

| File/function | Relationship to change | Risk |
|---|---|---|
| <caller> | calls changed function | contract may break |
| <dependency> | used by changed logic | version/API assumptions |

## Code risks GPT should inspect

- edge cases;
- error handling;
- off-by-one errors;
- mutation and shared state;
- sorting/order assumptions;
- async/concurrency issues;
- filesystem/path assumptions;
- serialization/deserialization;
- API compatibility;
- untested branches;
- stale caches or generated files;
- performance regressions;
- security or permission-sensitive behavior if relevant.
```

## 3.8 `07_REPRODUCTION.md`

```markdown
# Reproduction

## Environment

| Item | Value |
|---|---|
| OS/container | <value> |
| Language/runtime | <value> |
| Package manager | <value> |
| Dependency lockfile | <path> |
| Working directory | <path> |
| Random seeds | <value> |

## Commands

Run these in order:

```bash
# CMD-001
<command>

# CMD-002
<command>

# CMD-003
<command>
```

## Expected outputs

| Command ID | Expected result | Evidence file |
|---|---|---|
| CMD-001 | <expected> | logs/... |
| CMD-002 | <expected> | outputs/... |

## Reproduction notes

- <Any setup assumptions.>
- <Any nondeterminism.>
- <Any command Claude could not run.>
```

## 3.9 `08_TEST_RESULTS.md`

```markdown
# Test Results

## Tests run

| Command ID | Command | Exit code | Log | What it verifies |
|---|---|---:|---|---|
| CMD-003 | `<test command>` | 0 | logs/test_output.txt | C-... |

## Tests not run

| Test/check | Why not run | Risk |
|---|---|---|
| <test> | <reason> | <risk> |

## Coverage / limitation notes

- <What is tested well.>
- <What remains untested.>
```

## 3.10 `09_OUTPUT_AUDIT.md`

```markdown
# Output Audit

## Generated outputs

| Output | Generated by | Used by claims | How to verify |
|---|---|---|---|
| outputs/... | CMD-... | C-... | compare to logs / rerun command |

## Tables/charts/numbers in final answer

| Final answer item | Source artifact | Calculation path | Risk |
|---|---|---|---|
| <number/table/chart> | <path> | <script/command> | <risk if wrong> |
```

## 3.11 `10_RISK_REGISTER.md`

```markdown
# Risk Register

## Highest-risk failure modes

| Risk ID | Risk | Where it could occur | Related claims | Evidence/check included? | Status |
|---|---|---|---|---|---|
| R-001 | Task was misunderstood | Context / acceptance criteria | C-... | 01_CONTEXT.md | open/pass |
| R-002 | Data rows were duplicated by join | Data transformation | C-... | 05_DATA_AUDIT.md | open/pass |
| R-003 | Test passes but does not cover edge case | Tests | C-... | 08_TEST_RESULTS.md | open/pass |
| R-004 | Conclusion overstates evidence | Final answer | C-... | 03_CLAIM_LEDGER.md | open/pass |

## Standard risks GPT should consider

- wrong task interpretation;
- missing source file;
- stale or wrong data file;
- schema mismatch;
- wrong date/timezone/unit;
- duplicate rows or broken join cardinality;
- leakage between train/test, past/future, or before/after sets;
- silent filtering or unintended row loss;
- NaN/null handling;
- sorting/index alignment bugs;
- hardcoded path or stale cache;
- nondeterministic output;
- untested branch;
- test that checks implementation details but not behavior;
- benchmark not comparable to baseline;
- result depends on environment or library version;
- final conclusion stronger than evidence.
```

## 3.12 `11_GPT_AUDIT_PROMPT.md`

This file must contain the exact prompt the user should paste into GPT with the audit package attached.

Use the template in section 5.

## 3.13 `12_CLAUDE_SELF_CHECK.md`

Before giving the audit package to the user, Claude must complete this checklist.

```markdown
# Claude Self-Check Before GPT Audit

| Check | Pass/Fail | Notes |
|---|---|---|
| Every final conclusion appears in `03_CLAIM_LEDGER.md`. |  |  |
| Every claim has primary evidence, not just narrative support. |  |  |
| Changed code files are included or referenced. |  |  |
| Relevant unchanged dependency/caller files are included or referenced. |  |  |
| Data sources and transformations are included if data was used. |  |  |
| Row counts/checksums/schema checks are included if data was used. |  |  |
| Commands and logs are included for tests/runs. |  |  |
| Generated outputs are tied to generation commands. |  |  |
| Known risks and untested areas are disclosed. |  |  |
| GPT prompt asks for adversarial claim-by-claim audit. |  |  |
| Package status is marked `NOT_SUBMITTED_TO_GPT`. |  |  |

## Package completeness verdict

<COMPLETE / PACKAGE_INCOMPLETE>

## If incomplete, what is missing?

- <missing item>
```

---

# 4. How Claude should cite files inside the audit package

## 4.1 Required citation style

Use this citation style everywhere:

```text
path/to/file.ext:L10-L25
path/to/file.ext:section "Data lineage"
logs/test_output.txt:CMD-003
outputs/result.csv:rows 1-20
```

For files without stable line numbers, use artifact sections or row ranges.

## 4.2 Primary evidence rules

GPT must be able to audit from primary evidence. Therefore Claude must follow these rules:

| Claim type | Primary evidence required | Weak evidence that is not enough |
|---|---|---|
| Code behavior | source code, diff, tests, logs | Claude summary only |
| Data quality | raw data/sample, schema, validation report, transformation code | final chart only |
| Calculation | input data, formula, script, output log | final number only |
| Test success | exact command, full output, exit code | “tests passed” sentence |
| Task compliance | original task, acceptance criteria, final output | Claude memory of task |
| Performance | benchmark script, environment, baseline, repeated results if needed | one unlogged timing number |

## 4.3 Large data files: ship them anyway (never downgrade to checksum/sample)

If a data file matters to the audit, it MUST go in the package at FULL SIZE, no matter how large. Deliver the package as a zip (CSV/JSON compress ~3-5x). Do NOT substitute a checksum, a sample, or a "regenerate it yourself" command for the real data: a checksum only proves the file was not tampered with — it does NOT let GPT inspect the data content, verify the transformations, reconcile row counts, or catch a join / filter / label / sign bug. Silently dropping raw data to save size removes the entire data-audit layer and defeats the package's purpose.

Rules:

1. Any raw input or intermediate dataset that a data-backed claim depends on → include the FULL file in the zip.
2. **Size is never a reason to omit valuable data.** If the zip exceeds the upload channel's limit, split it into volumes or use a higher-capacity channel — but ship the data.
3. **Privacy is the only admissible reason to withhold raw data**, and only for genuinely sensitive fields (secrets, PII). Even then, redact those columns and ship the rest — not a summary of the whole.
4. Still put checksum + schema + row counts in `data/README.md` — as metadata ALONGSIDE the real data, never as a replacement for it.
5. Sample-only is acceptable solely when the full file is provably unusable on every available channel (e.g. multi-GB beyond any limit), AND you state loudly in the prompt that data-layer claims are therefore unverifiable. Last resort, not a default.

(git note: the git repo need not track giant data files — track the audit docs + `data/README.md`; the full data rides in the delivery zip.)

---

# 5. GPT audit prompt templates

## 5.0 The prompt must be SELF-CONTAINED, not an index (critical)

The most common failure of an audit prompt is writing it as a **pointer index** — "see 03_CLAIM_LEDGER.md for the claims, read the scripts for the methods, open the CSVs for the numbers" — and expecting GPT to crawl the attachments and reassemble the task itself. Empirically this yields shallow, rubber-stamp audits: GPT skims, misses cross-file context, and trusts by default.

`11_GPT_AUDIT_PROMPT.md` must instead be a **complete, standalone audit brief**. A reviewer who reads ONLY the prompt — opening zero attached files — must already understand the entire work and be able to start auditing. Inline, in the prompt body:

- full **background**: what the work is, why it matters, what was attempted;
- the **data and conventions**: key columns, units, sign conventions, sanity-check numbers;
- **each method** described concretely (not "see script X") — what it computes and how, including any bug you fixed;
- the **headline result numbers** for every block (don't make GPT open a CSV to learn the result);
- **every claim** from the CLAIM_LEDGER, inlined as: claim text + id + falsifier + where to verify;
- the **core findings'** full argument, especially any spec-level or surprising conclusion.

The attached files then take their proper role: **primary evidence for verification**. GPT reads the self-contained prompt to grasp the whole picture, and opens a file only to check whether a specific number / method / claim is actually true. Keep a short file map (the "Step 0: unzip" section) so GPT knows where to verify — but the map supports verification; it never substitutes for telling GPT what the work is.

Test: if deleting all attachments would leave GPT unable to describe what you did and why, the prompt is an index, not a brief — rewrite it until it stands alone.

**Language: write the audit prompt (`11_GPT_AUDIT_PROMPT.md` and its `prompt.md` copy) entirely in English**, regardless of the project's working language or the language used elsewhere in the audit docs. GPT audits are most reliable in English. Your conversation with the user stays in their language; only the GPT-facing prompt is forced to English.

## 5.1 Main GPT audit prompt

Paste this into GPT with the audit package attached.

```markdown
You are an external adversarial auditor. Your job is to decide whether Claude's work can be trusted.

Assume every link in the chain may be wrong: task interpretation, data, preprocessing, joins, code, tests, execution logs, calculations, charts, and final conclusions.

Do not rubber-stamp the result. Try to falsify it.

## Attached audit package

Use these files first:

- `00_AUDIT_REQUEST.md` — audit task and expected output.
- `01_CONTEXT.md` — original task, acceptance criteria, constraints, Claude's intended conclusion.
- `02_AUDIT_MANIFEST.md` — table of contents, referenced files, commands, data artifacts.
- `03_CLAIM_LEDGER.md` — every claim Claude wants trusted.
- `04_EVIDENCE_MAP.md` — evidence mapped to each claim.
- `05_DATA_AUDIT.md` — data lineage and validation, if data was used.
- `06_CODE_AUDIT.md` — changed files, behavior changes, code risks, if code was involved.
- `07_REPRODUCTION.md` — environment and exact commands.
- `08_TEST_RESULTS.md` — tests run, logs, limitations.
- `09_OUTPUT_AUDIT.md` — generated outputs and final numbers/tables/charts.
- `10_RISK_REGISTER.md` — likely failure modes.
- `diffs/changes.patch` — exact code diff, if present.
- `logs/*` — command outputs, test outputs, run logs.
- `data/*` — raw/sampled/processed data and validation reports, if present.
- `outputs/*` — generated outputs used in final claims.
- `referenced_files/*` — copied or excerpted project files needed for audit.

If any required file is missing, mark the package `PACKAGE_INCOMPLETE` and explain what cannot be audited.

## Audit rules

1. Audit claim by claim. Every row in `03_CLAIM_LEDGER.md` must receive a verdict.
2. Use primary evidence. Do not accept Claude's narrative summary as proof.
3. Cite exact files and line ranges or artifact sections whenever possible.
4. Check whether tests actually verify the claims they are cited for.
5. Check whether data validation is sufficient for data-backed claims.
6. Check whether outputs can be reproduced from commands and inputs.
7. Check whether the final conclusion is stronger than the evidence allows.
8. Identify missing files, missing commands, missing logs, stale outputs, and untested branches.
9. If you cannot verify something, mark it `INSUFFICIENT_EVIDENCE`, not pass.
10. Separate blocking issues from non-blocking notes.

## Audit layers

Audit all layers below:

### A. Task interpretation
- Did Claude solve the actual user request?
- Are acceptance criteria explicit and satisfied?
- Did Claude ignore or invent constraints?

### B. Data audit
- Are raw inputs identified?
- Are schemas, units, timezones, row counts, and keys checked?
- Are filters, joins, aggregations, and transformations auditable?
- Are there risks of duplicate rows, missing rows, leakage, stale data, invalid labels, or silent coercion?

### C. Code audit
- Are changed files and relevant unchanged dependencies included?
- Does the implementation actually do what Claude claims?
- Are edge cases, error paths, backward compatibility, and side effects handled?
- Are there hidden assumptions, hardcoded values, stale caches, or ordering/index bugs?

### D. Test and reproduction audit
- Are exact commands included?
- Do logs show successful execution?
- Do tests cover the important behavior, or only superficial paths?
- Are there tests that should exist but do not?
- Are outputs tied to commands that produced them?

### E. Calculation / analysis audit
- Are formulas and methods explicit?
- Do numbers/tables/charts follow from the provided inputs and code?
- Are comparisons fair and baselines valid?
- Are uncertainty, sample size, and limitations handled correctly?

### F. Conclusion audit
- Is every final claim in the claim ledger?
- Is any claim overstated?
- Which claims are trustworthy, which need downgrading, and which fail?

## Required output format

Return exactly this structure:

# GPT Audit Report

## 1. Overall verdict

Choose one:

- `PASS`: no blocking issues; claims are supported.
- `PASS_WITH_NOTES`: no blocking issues, but there are minor caveats.
- `CONDITIONAL_PASS`: likely acceptable only after specific fixes or evidence additions.
- `FAIL`: one or more core claims are wrong or unsupported.
- `PACKAGE_INCOMPLETE`: missing evidence prevents meaningful audit.

Give a 1-paragraph explanation.

## 2. Blocking issues

| ID | Severity | Issue | Evidence | Affected claims | Required fix |
|---|---|---|---|---|---|

Severity must be one of: `critical`, `high`, `medium`, `low`.

## 3. Claim-by-claim audit

| Claim ID | Verdict | Reason | Evidence checked | Missing evidence | Required change |
|---|---|---|---|---|---|

Verdict must be one of:

- `SUPPORTED`
- `SUPPORTED_WITH_CAVEAT`
- `INSUFFICIENT_EVIDENCE`
- `CONTRADICTED`
- `NOT_AUDITED`

## 4. Data audit findings

State whether data-backed claims are supported. Mention row-count, schema, join, null, duplicate, date/time, unit, leakage, and sampling issues when relevant.

## 5. Code audit findings

State whether code-backed claims are supported. Mention changed files, call paths, edge cases, error handling, tests, and compatibility issues.

## 6. Test/reproduction findings

State whether the commands and logs are enough to reproduce the result. Identify tests that are missing or weak.

## 7. Calculation/output findings

State whether numbers, tables, charts, and generated files are traceable to inputs and commands.

## 8. Overstated or unsupported conclusions

List any conclusions Claude should weaken, remove, or mark as uncertain.

## 9. Missing evidence or missing files

List exact files/logs/data/checks needed to complete the audit.

## 10. Recommended fixes

Prioritize fixes. For each fix, say whether it is required before trust.

## 11. Final trust level

Choose one: `high`, `medium`, `low`, `do_not_trust_yet`.

Explain briefly.
```

## 5.2 Code-focused GPT follow-up prompt

Use this when the main risk is implementation correctness.

```markdown
Focus only on code correctness and test adequacy.

Audit the changed implementation against:

- `diffs/changes.patch`
- `06_CODE_AUDIT.md`
- relevant files in `referenced_files/`
- `08_TEST_RESULTS.md`
- `07_REPRODUCTION.md`
- `03_CLAIM_LEDGER.md`

Please answer:

1. Does the diff actually implement the claimed behavior?
2. Could any caller, dependency, config, fixture, or generated artifact invalidate the change?
3. Are there edge cases not covered by tests?
4. Are tests asserting real behavior or merely checking the implementation shape?
5. What is the most likely bug remaining?
6. Which claims should be downgraded or rejected?

Use file/line citations. Mark unverifiable points as `INSUFFICIENT_EVIDENCE`.
```

## 5.3 Data-focused GPT follow-up prompt

Use this when the main risk is data correctness.

```markdown
Focus only on data validity and data lineage.

Audit the data-backed claims using:

- `05_DATA_AUDIT.md`
- `02_AUDIT_MANIFEST.md`
- files under `data/`
- transformation code in `referenced_files/` or project paths
- `09_OUTPUT_AUDIT.md`
- `03_CLAIM_LEDGER.md`

Please answer:

1. Is the raw data identified and sufficient?
2. Are schema, types, units, date ranges, timezones, and keys validated?
3. Do row counts reconcile across every transformation stage?
4. Could joins duplicate or drop rows?
5. Could filters, missing-value handling, label construction, or aggregation bias the result?
6. Are final numbers/tables/charts traceable to processed data and commands?
7. Which data-backed claims are unsupported or contradicted?

Use file/line/artifact citations. Mark unverifiable points as `INSUFFICIENT_EVIDENCE`.
```

## 5.4 Statistical / analytical GPT follow-up prompt

Use this when the main risk is the reasoning, metric, benchmark, or statistical conclusion.

```markdown
Focus only on analytical validity.

Audit whether the conclusions follow from the methods and evidence. Use:

- `03_CLAIM_LEDGER.md`
- `04_EVIDENCE_MAP.md`
- `05_DATA_AUDIT.md` if data was used
- `09_OUTPUT_AUDIT.md`
- scripts/notebooks in `referenced_files/`
- logs and output artifacts

Please answer:

1. Are the formulas, metrics, baselines, and assumptions explicit?
2. Do the calculations follow from the inputs?
3. Are sample size, uncertainty, variance, multiple comparisons, or confounders relevant?
4. Is any comparison unfair or missing a baseline?
5. Is any conclusion stronger than the evidence supports?
6. What alternative explanation or failure mode could invalidate the conclusion?

Use file/line/artifact citations. Mark unverifiable points as `INSUFFICIENT_EVIDENCE`.
```

## 5.5 Delta audit prompt after Claude fixes issues

Use this after GPT finds issues and Claude produces fixes.

```markdown
You previously audited Claude's work and identified issues. Claude has now provided a delta audit package.

Your job is not to re-audit everything from scratch unless needed. Your job is to verify whether the specific issues were actually fixed and whether the fix introduced new risks.

Use:

- previous GPT audit report;
- `FIX_LOG.md` or `AUDIT_RESPONSE.md`;
- new `03_CLAIM_LEDGER.md`;
- new `diffs/changes.patch`;
- new or changed tests/logs/data validation reports;
- any updated outputs.

Please return:

1. Which previous issues are fully resolved?
2. Which issues remain unresolved?
3. Did Claude merely explain the issue away, or provide primary evidence?
4. Did the fix create new risks?
5. Which claims now pass, fail, or require downgrading?
6. Final verdict: `PASS`, `PASS_WITH_NOTES`, `CONDITIONAL_PASS`, `FAIL`, or `PACKAGE_INCOMPLETE`.

Cite files and line ranges. Mark unverifiable fixes as `INSUFFICIENT_EVIDENCE`.
```

---

# 6. Claude workflow

## 6.1 Before generating the audit package

Claude must identify:

```text
- What did I change or conclude?
- What files did I read?
- What files did I modify?
- What data did I use?
- What commands did I run?
- What outputs did I generate?
- What tests did I run?
- What assumptions did I rely on?
- What could make my conclusion false?
```

## 6.2 Generate evidence files

For code projects, Claude should capture at minimum:

```bash
git status --short > audit/round_XX_<slug>/diffs/git_status.txt
git diff --stat > audit/round_XX_<slug>/diffs/git_diff_stat.txt
git diff > audit/round_XX_<slug>/diffs/changes.patch
```

For command execution, Claude should save logs:

```bash
<command> > audit/round_XX_<slug>/logs/<name>.stdout.txt 2> audit/round_XX_<slug>/logs/<name>.stderr.txt
```

If one combined log is clearer:

```bash
<command> > audit/round_XX_<slug>/logs/<name>.txt 2>&1
```

For data files, Claude should record counts and fingerprints when feasible:

```bash
wc -l <file> >> audit/round_XX_<slug>/data/README.md
sha256sum <file> >> audit/round_XX_<slug>/data/README.md
```

For Python tabular data, include validation reports such as:

```text
- shape;
- columns and dtypes;
- missing value counts;
- duplicate key counts;
- min/max for key numeric/date columns;
- row counts before/after filters and joins;
- sample rows using a fixed random seed.
```

## 6.3 Fill the claim ledger

Claude must convert the final answer into atomic claims.

Examples:

```text
Too broad:
- The pipeline is fixed.

Auditable:
- C-001: `load_events()` now rejects rows with missing `event_time`.
- C-002: The new regression test fails on the old behavior and passes on the new behavior.
- C-003: The processed dataset contains 42,183 rows after filtering, matching the validation log.
- C-004: No duplicate `(user_id, event_time)` keys remain after deduplication.
```

## 6.4 Create GPT prompt with explicit file references

Claude must include a section like this in `11_GPT_AUDIT_PROMPT.md`:

```markdown
## Files you must inspect

### Audit control files
- `01_CONTEXT.md`
- `02_AUDIT_MANIFEST.md`
- `03_CLAIM_LEDGER.md`
- `04_EVIDENCE_MAP.md`

### Code evidence
- `diffs/changes.patch`
- `referenced_files/src/...`
- `referenced_files/tests/...`
- `logs/test_output.txt`

### Data evidence
- `data/README.md`
- `data/raw_or_sampled_inputs/...`
- `data/processed_outputs/...`
- `data/validation_reports/...`

### Output evidence
- `outputs/...`
- `09_OUTPUT_AUDIT.md`
```

The prompt must tell GPT that `03_CLAIM_LEDGER.md` is the authoritative list of claims to audit.

## 6.5 Self-check before handoff

Claude must complete `12_CLAUDE_SELF_CHECK.md`.

If any required evidence is missing, Claude must either add it or explicitly mark the package as:

```text
PACKAGE_INCOMPLETE
```

and explain what GPT will not be able to audit.

---

# 7. Handling GPT audit results

When the user returns GPT's audit report, Claude must create:

```text
AUDIT_RESPONSE.md
FIX_LOG.md          # if fixes are made
```

## 7.1 `AUDIT_RESPONSE.md` template

```markdown
# Claude Response to GPT Audit

## GPT verdict

<PASS / PASS_WITH_NOTES / CONDITIONAL_PASS / FAIL / PACKAGE_INCOMPLETE>

## Issue triage

| GPT issue ID | Claude decision | Reason | Action |
|---|---|---|---|
| I-001 | accepted / rejected / partially accepted | <evidence> | fix / downgrade claim / add evidence / no action |

## Claim updates

| Claim ID | Previous status | New status | Change |
|---|---|---|---|
| C-001 | unsupported | supported / downgraded / removed | <what changed> |

## Remaining uncertainty

- <uncertainty>
```

## 7.2 `FIX_LOG.md` template

```markdown
# Fix Log

| Fix ID | Related GPT issue | Files changed | Tests/data checks rerun | Evidence |
|---|---|---|---|---|
| F-001 | I-001 | src/...; tests/... | CMD-... | logs/... |

## New or changed claims

- <Claim ID and explanation>
```

If fixes are non-trivial, Claude must produce a new audit package or a delta package and use the delta audit prompt.

---

# 8. Quality gates

Claude must not claim `GPT_AUDIT_PASS` unless all of the following are true:

1. GPT returned `PASS` or `PASS_WITH_NOTES`, or all conditional issues were fixed and re-audited.
2. Every claim in `03_CLAIM_LEDGER.md` is `SUPPORTED` or explicitly downgraded/removed.
3. No blocking data, code, reproduction, or task-compliance issue remains.
4. Test and command logs exist for claims that rely on execution.
5. Data-backed claims have sufficient data lineage and validation.
6. The final answer does not exceed what the evidence supports.

If GPT returns `PACKAGE_INCOMPLETE`, Claude must not argue from memory. Claude must add the missing files/evidence or downgrade the claims.

If GPT returns `FAIL`, Claude must either:

- fix the underlying issue and create a delta package; or
- remove/downgrade the affected conclusion.

---

# 9. Final user-facing response after package creation

After producing the audit package, Claude should tell the user:

```markdown
I created the audit package here:

`audit/round_XX_<slug>/`

Audit status: `NOT_SUBMITTED_TO_GPT`

Use this prompt with GPT:

`audit/round_XX_<slug>/11_GPT_AUDIT_PROMPT.md`

Most important files for GPT to inspect:

- `03_CLAIM_LEDGER.md`
- `04_EVIDENCE_MAP.md`
- `diffs/changes.patch` if code changed
- `05_DATA_AUDIT.md` and `data/*` if data was used
- `07_REPRODUCTION.md`
- `08_TEST_RESULTS.md`
- `09_OUTPUT_AUDIT.md`

The result should not be treated as externally audited until GPT returns an audit report and the issues are addressed.
```

Do not bury the audit status. Make it visible.

## 9.1 Delivering the package to ChatGPT (web)

ChatGPT web **cannot accept a folder** and limits how many files you can attach at once, so never tell the user to "drag the folder in". Instead:

1. **Zip the whole package into one archive** (e.g. `round_01_audit.zip`). One upload; GPT unzips it. The prompt's Step 0 must instruct GPT to unzip and read every file. Ship the FULL data inside the zip (see §2.3 / §4.3) — CSV/JSON compress ~3-5x, so even 100MB+ of data usually lands well under typical upload limits.
2. **Build a clean delivery folder** with two plainly-named files — no numbered prefixes, no action-word filenames, no how-to file (the user knows how to upload a zip and paste text):
   - `prompt.md` — a standalone COPY of `11_GPT_AUDIT_PROMPT.md`;
   - `<name>_audit.zip` — the package (full data inside).
3. The user's operation: upload the zip + paste `prompt.md` into the chat. Because the prompt is self-contained (§5.0), pasting it is sufficient; the zip is there for evidence verification.

Keep `prompt.md` and the prompt inside the zip identical — regenerate both whenever you edit either. If the zip ever exceeds the channel limit, split into volumes; do not drop the data to shrink it.

---

# 10. Minimal example of a completed claim ledger

```markdown
# Claim Ledger

| Claim ID | Claim | Type | Confidence before GPT audit | Primary evidence | Reproduction/check | What would falsify it? |
|---|---|---|---:|---|---|---|
| C-001 | The parser now rejects empty `event_time` values before downstream aggregation. | code | 0.82 | diffs/changes.patch; referenced_files/src/parser.py:L41-L58 | CMD-002 | Empty `event_time` reaches aggregation or no error is raised |
| C-002 | The new test covers the missing-time regression case. | test | 0.78 | referenced_files/tests/test_parser.py:L12-L35; logs/test_output.txt | CMD-003 | Test does not fail on old behavior or does not assert the error |
| C-003 | The cleaned dataset has 18,240 rows after filtering invalid timestamps. | data | 0.70 | data/validation_reports/cleaning_report.md; data/processed_outputs/events_clean.parquet | CMD-004 | Row count mismatch or filter script differs from report |
| C-004 | The final chart uses the cleaned dataset, not the raw dataset. | output | 0.74 | referenced_files/scripts/make_chart.py:L20-L35; outputs/final_chart.png; logs/chart_run.txt | CMD-005 | Chart script reads raw input or stale cached output |
```

---

# 11. Minimal example of the GPT prompt with concrete file references

```markdown
You are an external adversarial auditor. Audit Claude's result claim by claim.

The authoritative claim list is `03_CLAIM_LEDGER.md`. Do not audit only the final narrative; audit the evidence chain.

Files to inspect:

- `01_CONTEXT.md` for the original task and acceptance criteria.
- `02_AUDIT_MANIFEST.md` for the complete file list.
- `03_CLAIM_LEDGER.md` for claims C-001 through C-004.
- `04_EVIDENCE_MAP.md` for claim-to-evidence mapping.
- `diffs/changes.patch` for exact code changes.
- `referenced_files/src/parser.py` for implementation.
- `referenced_files/tests/test_parser.py` for regression tests.
- `logs/test_output.txt` for executed test results.
- `05_DATA_AUDIT.md` for data lineage.
- `data/validation_reports/cleaning_report.md` for row counts and missing timestamp checks.
- `referenced_files/scripts/make_chart.py` for output generation.
- `outputs/final_chart.png` and `logs/chart_run.txt` for generated output evidence.

Audit requirements:

1. For every claim C-001 through C-004, return `SUPPORTED`, `SUPPORTED_WITH_CAVEAT`, `INSUFFICIENT_EVIDENCE`, `CONTRADICTED`, or `NOT_AUDITED`.
2. Cite exact files and line ranges or artifact sections.
3. Check whether tests actually prove the claimed behavior.
4. Check whether data row counts and transformations are consistent.
5. Check whether generated outputs are stale or reproducible.
6. Mark missing evidence as `INSUFFICIENT_EVIDENCE`; do not infer trust from Claude's explanation.
7. Give an overall verdict: `PASS`, `PASS_WITH_NOTES`, `CONDITIONAL_PASS`, `FAIL`, or `PACKAGE_INCOMPLETE`.
```

---

# 12. Common audit failures Claude should proactively expose

Claude should not hide weak spots. Add them to `10_RISK_REGISTER.md` and ask GPT to check them.

Common failures include:

- Claude solved a nearby task but not the actual task.
- Final answer includes claims not listed in the claim ledger.
- Code diff is correct but the relevant caller still uses an old path.
- Test passes but does not assert the important behavior.
- Test uses mocked data that cannot catch the real bug.
- Log is from before the latest code change.
- Generated output is stale and was not regenerated.
- Data file is the wrong version.
- Join duplicates rows.
- Filter silently drops important cases.
- Nulls or invalid values are coerced instead of handled.
- Date boundaries are off by one.
- Timezone or unit conversion is wrong.
- Sorting/index alignment changes labels or rows.
- Benchmark is compared against an unfair baseline.
- Statistical conclusion ignores variance or sample size.
- Result is true only for a toy sample but written as general.
- Claude's prose overstates what tests/data prove.

---

# 13. Non-negotiable rule

The final deliverable is not just Claude's answer. The final deliverable is:

```text
Claude answer + audit package + GPT audit report + Claude response to audit
```

Until all four exist, the result is not fully trusted.
