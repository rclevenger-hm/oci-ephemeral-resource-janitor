# Observability contract

The janitor is destructive-capable automation, so its telemetry should answer three questions quickly: **what did it evaluate, what did it intend to change, and did the run remain inside policy?** The existing structured report is the source contract for those signals.

## Run-level signals

Emit one completion event for every invocation, including dry runs. Derive these fields directly from the report returned by `run_janitor`:

| Signal | Source | Operational meaning |
| --- | --- | --- |
| `janitor.scanned` | `scanned_count` | Resources evaluated in the target compartment. |
| `janitor.candidates` | `candidate_count` | Expired resources that passed policy checks. |
| `janitor.selected` | `selected_count` | Resources selected after the action cap. |
| `janitor.limited` | `limited` | Whether blast-radius limiting suppressed eligible actions. |
| `janitor.action` | `action` | `report`, `stop`, or `terminate`. |
| `janitor.dry_run` | `dry_run` | Whether mutation was disabled. |
| `janitor.reason.<reason>` | `reason_counts` | Distribution of eligibility and rejection decisions. |

Do not use resource display names, OCIDs, policy-file contents, or request bodies as metric labels. Those values create high cardinality and can expose infrastructure identifiers. Keep per-resource detail in the bounded JSON report and logs instead.

## Required completion log

A successful invocation should produce a structured or consistently parseable completion record containing:

```text
scanned=<count> eligible=<count> selected=<count> action=<action> dry_run=<true|false> limited=<true|false>
```

A failed invocation should include a stable failure category such as `configuration`, `authentication`, `discovery`, or `mutation`, while retaining the exception detail only in the protected runtime log. Client-facing OCI Function responses should remain bounded and must not echo SDK exceptions, credentials, request bodies, or policy-file content.

## Alerts

Recommended initial alerts are intentionally small and actionable:

1. **Run failure:** any scheduled invocation exits unsuccessfully.
2. **Unexpected live mutation:** `dry_run=false` outside the approved schedule/environment.
3. **Termination enabled:** `action=terminate` outside a reviewed maintenance window.
4. **Blast-radius cap reached:** `limited=true`; review why more resources expired than the configured action budget permits.
5. **Discovery collapse:** `scanned_count` drops unexpectedly to zero or materially below its normal range; treat this as an auth/discovery signal, not evidence that nothing requires cleanup.
6. **Policy rejection spike:** sudden growth in `invalid_ttl_tag` or `invalid_expiration_tag` decisions indicates malformed ownership/lifecycle metadata.

Do not page merely because `candidate_count > 0`; discovering expired managed resources is the normal purpose of the janitor.

## Suggested service objectives

For a scheduled janitor, useful reliability objectives are about execution rather than deletion volume:

- **Scheduled-run success:** at least 99% of expected runs complete successfully over 30 days.
- **Audit completeness:** every successful run emits exactly one report with `schema_version`, `generated_at`, action state, aggregate counts, reason counts, and decisions.
- **Mutation accountability:** every live selected resource has a corresponding decision record from the same run.
- **Duplicate scheduling:** overlapping invocations should be detectable operationally before extending the janitor to resource types where concurrent mutations can conflict.

These objectives intentionally avoid treating a high deletion count as success.

## Dashboard view

A compact operational dashboard should show:

- scheduled runs and failures over time;
- scanned / candidates / selected as separate series;
- dry-run versus live runs;
- report / stop / terminate counts;
- `limited=true` occurrences;
- decision reasons, especially protection and malformed-policy reasons;
- most recent successful run timestamp.

A healthy graph can legitimately show many scanned resources and zero selected actions.

## Incident triage

When a run behaves unexpectedly:

1. stop the schedule or force `dry_run=true` before changing policy;
2. preserve the structured report from the affected run;
3. compare `reason_counts`, selected resources, action, and policy inputs with the previous known-good run;
4. follow [`RECOVERY.md`](RECOVERY.md) if a stop or termination was incorrect;
5. correct policy/tests before restoring live execution.

The observability contract should evolve with the report schema. A schema change that renames or removes these fields is an operational API change and should receive explicit review.
