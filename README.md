# OCI Ephemeral Resource Janitor

Safety-first lifecycle enforcement for temporary Oracle Cloud Infrastructure resources.

The janitor is designed for infrastructure that is **supposed to expire**: developer sandboxes, CI workers, QA machines, demos, experiments, short-lived troubleshooting hosts, and other ephemeral workloads. It evaluates explicit lifecycle policy and can report, stop, or terminate resources after their intended lifetime.

> **Current resource support:** OCI Compute instances. The policy and reporting model is intentionally generic so additional ephemeral OCI resource types can be added without turning the project into an indiscriminate "delete old things" script.

## Purpose

The project answers one operational question:

> **Which explicitly managed temporary resources have expired, and what lifecycle action should be taken safely?**

It is not an idle-resource detector and it is not a general-purpose OCI cost optimizer. CPU, network, and other utilization metrics are not currently used to infer whether a resource is safe to remove.

## Safety Model

The defaults are deliberately conservative:

1. **Explicit opt-in is mandatory.** A resource is ignored unless it has `JanitorManaged=true` (configurable key/value).
2. **Dry-run is enabled by default.**
3. **`stop` is the default action**, not termination.
4. **Only 10 resources are selected per run by default** to cap blast radius.
5. **`DoNotCleanup=true` always protects a managed resource** by default.
6. **Termination has a second interlock.** Live termination requires `dry_run=false`, `action=terminate`, and `allow_terminate=true`.
7. **Termination is two-phase by default.** Only already-`STOPPED` instances are eligible for termination unless `termination_requires_stopped=false` is explicitly configured.
8. **Malformed lifecycle tags fail closed.** Invalid TTL or expiration values make a resource ineligible rather than guessing.
9. Every evaluated resource can be emitted in a structured JSON audit report with its eligibility reason.

A typical production pattern is therefore:

```text
JanitorManaged=true
        |
        v
    expiration reached
        |
        v
   report / dry-run
        |
        v
       stop
        |
        v
 terminate on a later run
```

## Lifecycle Tags

Freeform tags provide per-resource policy.

| Tag | Default meaning |
| --- | --- |
| `JanitorManaged=true` | Explicitly opts the resource into janitor management. Required. |
| `DoNotCleanup=true` | Protects the resource from janitor actions. |
| `TTLHours=<number>` | Overrides the global TTL for this resource. |
| `ExpiresAt=<ISO-8601>` | Sets an absolute expiration time and takes precedence over `TTLHours`. |

Examples:

```text
JanitorManaged=true
TTLHours=8
```

A short-lived CI worker expires eight hours after instance creation.

```text
JanitorManaged=true
ExpiresAt=2026-09-08T18:00:00Z
```

A demo instance expires at an explicit deadline.

```text
JanitorManaged=true
TTLHours=24
DoNotCleanup=true
```

The instance remains protected regardless of age until the exclusion tag is removed.

## Eligibility Rules

For each OCI Compute instance in the configured compartment, the janitor:

1. checks whether the lifecycle state is actionable for the configured action;
2. requires the opt-in management tag;
3. checks the exclusion tag;
4. resolves expiration from `ExpiresAt`, then `TTLHours`, then the global threshold;
5. rejects malformed expiration policy;
6. marks the instance eligible only after expiration.

Actionable states differ by lifecycle action:

- `report`: expired `RUNNING` and `STOPPED` managed instances can be surfaced;
- `stop`: only expired `RUNNING` managed instances are eligible;
- `terminate`: only expired `STOPPED` managed instances are eligible by default.

Direct termination of running instances can be enabled, but it requires an explicit policy override in addition to the live-termination interlock.

## Structured Reporting

Each run produces a report containing:

- schema version and generation timestamp;
- action and dry-run state;
- target compartment;
- supported resource types evaluated;
- scanned, eligible, and selected counts;
- whether the run was limited by the action cap;
- counts grouped by decision reason;
- one decision record per evaluated resource.

Typical decision reasons include:

- `expired`
- `not_expired`
- `required_tag_missing`
- `excluded_tag_present`
- `invalid_ttl_tag`
- `invalid_expiration_tag`
- `lifecycle_state_not_actionable`

This makes dry-runs useful as audit output rather than simply logging "would delete" messages.

## Configuration

Configuration can come from environment variables, a JSON policy file, or an OCI Function request payload. Request values override environment values, and environment values override policy-file defaults.

### Primary environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `OCI_COMPARTMENT_ID` | required | OCI compartment to evaluate. |
| `OCI_JANITOR_THRESHOLD_HOURS` | `24` | Global TTL when no resource-specific tag is present. |
| `OCI_JANITOR_DRY_RUN` | `true` | Prevents mutations. |
| `OCI_JANITOR_ACTION` | `stop` | `report`, `stop`, or `terminate`. |
| `OCI_JANITOR_MAX_ACTIONS_PER_RUN` | `10` | Blast-radius cap. |
| `OCI_JANITOR_REQUIRED_TAG_KEY` | `JanitorManaged` | Required opt-in tag key. |
| `OCI_JANITOR_REQUIRED_TAG_VALUE` | `true` | Required opt-in tag value. |
| `OCI_JANITOR_EXCLUDED_TAG_KEY` | `DoNotCleanup` | Protection tag key. |
| `OCI_JANITOR_EXCLUDED_TAG_VALUE` | `true` | Protection tag value. |
| `OCI_JANITOR_TTL_TAG_KEY` | `TTLHours` | Per-resource TTL tag. |
| `OCI_JANITOR_EXPIRES_AT_TAG_KEY` | `ExpiresAt` | Absolute expiration tag. |
| `OCI_JANITOR_ALLOW_TERMINATE` | `false` | Required second interlock for live termination. |
| `OCI_JANITOR_TERMINATION_REQUIRES_STOPPED` | `true` | Enforces two-phase stop-then-terminate behavior. |
| `OCI_JANITOR_REPORT_FILE` | unset | Optional path for the structured JSON report. |
| `OCI_JANITOR_POLICY_FILE` | unset | Optional JSON policy file. |
| `OCI_AUTH_MODE` | `auto` | `auto`, `config`, or `resource_principal`. |
| `OCI_CONFIG_FILE` | OCI SDK default | Local OCI config path. |
| `OCI_CONFIG_PROFILE` | `DEFAULT` | OCI config profile. |
| `LOG_LEVEL` | `INFO` | Python logging level. |

Legacy `OCI_CLEANUP_*` environment variables from the previous project name remain supported where there is a direct equivalent.

## Policy File

See [`examples/policy.json`](examples/policy.json).

```json
{
  "compartment_id": "ocid1.compartment.oc1..exampleuniqueID",
  "threshold_hours": 72,
  "dry_run": true,
  "action": "report",
  "max_actions_per_run": 10,
  "required_tag_key": "JanitorManaged",
  "required_tag_value": "true",
  "excluded_tag_key": "DoNotCleanup",
  "excluded_tag_value": "true",
  "ttl_tag_key": "TTLHours",
  "expires_at_tag_key": "ExpiresAt",
  "allow_terminate": false,
  "termination_requires_stopped": true,
  "auth_mode": "resource_principal"
}
```

## Run Locally

Install dependencies:

```bash
pip install -r function/requirements.txt
```

Start with a report-only dry run:

```bash
export OCI_COMPARTMENT_ID='ocid1.compartment.oc1..exampleuniqueID'
export OCI_JANITOR_ACTION='report'
export OCI_JANITOR_DRY_RUN='true'
python function/cleanup_resources.py
```

Stop expired managed instances:

```bash
export OCI_COMPARTMENT_ID='ocid1.compartment.oc1..exampleuniqueID'
export OCI_JANITOR_ACTION='stop'
export OCI_JANITOR_DRY_RUN='false'
python function/cleanup_resources.py
```

Terminate expired instances that are already stopped:

```bash
export OCI_COMPARTMENT_ID='ocid1.compartment.oc1..exampleuniqueID'
export OCI_JANITOR_ACTION='terminate'
export OCI_JANITOR_DRY_RUN='false'
export OCI_JANITOR_ALLOW_TERMINATE='true'
python function/cleanup_resources.py
```

Direct termination of an expired running instance requires one additional explicit override:

```bash
export OCI_JANITOR_TERMINATION_REQUIRES_STOPPED='false'
```

That mode is intentionally not the default.

## Deploy as an OCI Function

From the `function/` directory:

```bash
fn -v deploy --app <your_fn_app_name>
```

For OCI Functions, resource principals are recommended:

```bash
fn config function <your_fn_app_name> oci-ephemeral-resource-janitor OCI_AUTH_MODE resource_principal
```

Then configure the janitor policy on the Function/application and grant the resource principal the least privilege needed to list instances and perform only the actions you enable.

The function accepts the same lower-case policy fields as a JSON request body, for example:

```json
{
  "compartment_id": "ocid1.compartment.oc1..exampleuniqueID",
  "action": "report",
  "dry_run": true,
  "threshold_hours": 72,
  "max_actions_per_run": 5
}
```

The response includes scanned, eligible, selected, limited, and reason-count summaries.

## Tests

```bash
cd function
python -m unittest discover -v -p 'test_*.py'
```

The test suite covers policy precedence, opt-in safety, exclusion behavior, per-resource TTLs, absolute expiration, malformed-tag fail-closed behavior, action caps, reporting, destructive-action interlocks, two-phase termination, CLI exit semantics, and the OCI Function handler.

## Repository Layout

```text
.github/workflows/test.yml       CI for Python 3.11 and 3.12
examples/policy.json             Safe example policy
function/cleanup_resources.py    Policy engine, OCI discovery, actions, reporting
function/handler.py              OCI Functions entrypoint
function/func.yaml               OCI Functions manifest
function/test_cleanup_resources.py
function/test_handler.py
```

## Current Scope and Roadmap

Today the janitor supports OCI Compute instances. Natural extensions are other resource types that have a defensible ephemeral lifecycle, such as:

- unattached ephemeral block or boot volumes;
- temporary public IPs;
- short-lived snapshots or custom images;
- ephemeral load balancers or test-network resources;
- report publication to Object Storage / OCI Logging;
- Notifications integration for action summaries and failures;
- optional OCI Monitoring signals as an additional safety condition, never as a replacement for explicit ownership policy.

Any additional resource handler should preserve the same design principle: **the janitor only manages resources that have explicitly opted into lifecycle management.**

## License

MIT. See [LICENSE](LICENSE).
