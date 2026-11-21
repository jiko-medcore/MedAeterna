# PH0-WP-05 Completion Record — Administrative Events and Operational Authorization

**Work package:** PH0-WP-05 / finding SEC-09 / policy SPEC-09

**Plan order:** `PHASE-0-BACKEND-SECURITY-BASELINE-AND-REMEDIATION-PLAN-v2.0.md` order 3 and `backend/MedAeterna_Phase_0_Backend_Security_Baseline_and_Remediation_Plan_v2.0.md` order 4

**Branch:** `security/phase-0-db-storage-release`

**Implementation commit:** `9977b88ecc5e20188af2a1ccb9e5c5c8e39f5cc7` (local, committed, not pushed)

**Execution-order base:** `dfaa0684feb9c618f5b3e3a6335c5ea15fd65451`; the baseline plan was restored read-only in `0602037ad788fa833ed1833dca33cd1e5656ee90` before this implementation commit.

**Review date:** 21 November 2026

**Status:** **Implemented and locally verified — NOT CLOSED, NOT ACCEPTED**

**Finding disposition:** SEC-09 is **partially mitigated locally**. It is not closed.

> This record documents the completed local implementation order only. It does not claim staging or production verification, hosted RLS/grant effectiveness, persistent audit verification, handler retry-safety approval, or Phase 0 acceptance. No production configuration or data was changed.

---

## 1. Scope completed

This order covered administrative event reads, dead-letter visibility, single-event replay, internal event query helpers, and the legacy operational-event entry points.

| Surface | Local outcome |
|---|---|
| `backend/app/api/admin/events_router.py` | Seven system-admin-only routes now use approved purposes, explicit projections, policy evaluation, audit-before-access, bounded limits, and fail-closed behavior. |
| `backend/app/api/admin/event_replay_router.py` | Duplicate replay surface remains neutralized; the consolidated route is `POST /admin/events/dead/{dead_event_id}/replay`. |
| `backend/app/core/events/router.py` | Legacy unauthenticated `/events/*` read/retry/bulk-retry routes remain disabled and return 404. |
| `backend/app/core/events/monitoring.py` | All `select('*')` calls were replaced with explicit metadata projections. Payloads, aggregate identifiers, and raw failure text are not returned by these helpers. |
| `backend/app/core/events/replay.py` | Dead-letter replay now uses a compare-and-set claim on `replayed = false`, fetches only the fields needed for the state transition, and leaves outcome auditing to the route. |
| `backend/app/core/events/service.py` | Generic event retry now requires `status = failed` and `retry_count < 3`. |
| `backend/app/core/operational_event_policy.py` | Adds a reviewed retry-safety allowlist hook and fixed-code normalization of stored failure text. The allowlist is intentionally empty. |
| `backend/tests/api/admin/test_spec09_event_authorization.py` | New route-level positive/negative suite mounted on an isolated FastAPI app. |

The hardened admin event router is **not mounted by `backend/main.py`** in this phase, so this order does not expand the deployed HTTP surface. The mounted legacy `/events/*` router remains disabled.

---

## 2. Authorization decisions applied

| Decision | Applied behavior |
|---|---|
| Authentication | All administrative event routes depend on `get_current_user()`; missing credentials return 401. |
| Patient / practitioner / org admin | Denied with 403 before any event query or audit write. Org-admin event reads remain fail-closed because no trusted event-to-organization resolver exists. |
| System-admin read | Allowed only with `platform_health` or `security_incident`; summaries remain aggregate counts only. |
| System-admin retry | Allowed only with `event_recovery` or `security_incident`, one opaque event reference, and a bounded reason. `platform_health` is not accepted as a retry purpose. |
| Field projection | Patient/onboarding events omit `event_type` and identifiers. All responses omit payload, aggregate ID, raw `failure_reason`, and `last_error`. Stored failure text is mapped to a fixed code or omitted. |
| Retry state | Dead-letter rows must be unreplayed. Generic failed-event retry requires `failed` status and `retry_count < 3`. Pending, processing, processed, exhausted, already-replayed, and unknown states are denied. |
| Bulk retry | No mounted bulk retry exists; `/events/retry-failed` remains 404. |
| Audit | Sensitive reads write one audit record before the query. Replay writes an `EVENT_REPLAY_ATTEMPTED` record before the CAS transition, then `EVENT_REPLAYED` or `EVENT_REPLAY_DENIED` with the actual outcome. Pre-transition audit failure denies the operation; no record contains payload or raw error text. |
| Retry reason | Email-like and long digit-sequence patterns are rejected before any query or audit write. The stored reason is bounded to 500 characters and contains no event payload. |

### 2.1 Retry-safety decision

`MANUAL_RETRY_SAFE_EVENT_TYPES` is intentionally empty. Source review found that registered handlers are not proven retry-safe: several send email, emit follow-on events, or otherwise create duplicate side effects when retried. Registration in `EVENT_HANDLERS` is therefore not treated as retry-safety evidence.

Consequently, **no event type is currently eligible for a production manual retry**. The route test temporarily supplies an allowlisted handler only to exercise the authorization/CAS/audit machinery; that test is not a production approval of any handler.

### 2.2 Compare-and-set behavior

Replay now claims the dead-letter row with `replayed = false` before inserting the replacement pending event. A second operator with a stale read cannot create a duplicate queue event. If queue insertion fails after the claim, a compensating update clears the claim. This prevents duplicate claims but is not a single database transaction; full transactional atomicity still requires a reviewed database function and remains separate remediation work.

---

## 3. Local Supabase catalog evidence

The Supabase MCP endpoint `http://127.0.0.1:58561/mcp` was used in read-only mode through `execute_sql`. No migration was applied and no local or hosted data was changed. The local endpoint reported PostgreSQL 17.6 with `current_database() = postgres`.

| Assertion | Local result |
|---|---|
| `events` RLS enabled / forced / policy count | `true` / `true` / `0` |
| `events_dead_letter` RLS enabled / forced / policy count | `true` / `true` / `0` |
| `anon` and `authenticated` SELECT/INSERT/UPDATE/DELETE on both tables | All `false` |
| `service_role` SELECT/INSERT/UPDATE/DELETE on both tables | All `true` |
| `postgres` SELECT/INSERT/UPDATE/DELETE on both tables | All `true` |
| `normalized_error_code` / `organization_id` columns on either table | Absent |
| `payload`, `failure_reason`, `last_error` columns | Present on `events`; `payload` and `failure_reason` present on `events_dead_letter`; selected only server-side for normalization/replay and never returned by the hardened projections |

No policies exist on the two event tables. With forced RLS and no client-role grants, direct anon/authenticated Data API access is blocked locally. Privileged service-role access remains necessary for backend operations and is why application authorization and safe projections remain mandatory.

The `supabase` CLI was not installed in the execution environment, so `supabase test db` was not run. The existing `backend/supabase/tests/database/spec11_table_privileges_and_policies.test.sql` already asserts the reviewed RLS/grant inventory for both event tables; the MCP queries above provide the local catalog result for this record.

---

## 4. Verification evidence

All test commands were run from `backend/` on Windows using `.venv/Scripts/python.exe`.

| Evidence ID | Check | Command | Result |
|---|---|---|---|
| E-WP05-01 | Route-level SPEC-09 suite | `.venv/Scripts/python.exe -m pytest tests/api/admin/test_spec09_event_authorization.py -q --tb=short -p no:cacheprovider` | **16 passed** |
| E-WP05-02 | Focused policy/log/WP-01 regression | `.venv/Scripts/python.exe -m pytest tests/api/admin/test_spec09_event_authorization.py tests/core/test_operational_event_policy.py tests/core/test_event_logging.py tests/core/test_security_phase0_wp01.py -q --tb=no -p no:cacheprovider` | **60 passed** |
| E-WP05-03 | Full backend regression | `.venv/Scripts/python.exe -m pytest -q --tb=no -p no:cacheprovider` | **1,314 passed, 1 skipped, 18 warnings** |
| E-WP05-04 | Local database catalog | Read-only MCP `execute_sql` assertions listed in section 3 | Pass |
| E-WP05-05 | Patch sanity | `git diff --check` | Clean |

The route suite covers:

- 401 for all seven administrative event routes without credentials.
- 403 with no service query or audit write for patient, practitioner, and organization-admin identities on every administrative route.
- 400 for disallowed read/retry purposes before any privileged query.
- Safe projection of event and dead-letter rows, including patient-event redaction and fixed error-code normalization.
- Shared list/detail projection behavior.
- Replay denial when no handler is retry-safe.
- Rejection of contact data in a retry reason.
- Denial when audit persistence fails.
- Compare-and-set claim against a stale concurrent read; only one insert and no duplicate replay.
- Attempt, final success and final denial audit records without payload or raw error text.
- Legacy `/events/*` routes remaining disabled.
- Internal monitoring helpers not selecting payload or raw error fields.
- Generic retry requiring failed state and a retry count below the limit.

---

## 5. Evidence limits and open work

The following remain explicitly open. This work package is **not** sufficient to close SEC-09:

1. **Organization-admin visibility.** No trusted event-to-organization resolver or normalized `organization_id` exists. Org-admin event reads remain denied; this is safe but does not satisfy the allowed-visibility path in SPEC-09.
2. **Handler retry-safety approval.** The allowlist is empty. A documented review of each handler’s idempotency and side effects is required before any manual retry is enabled.
3. **Full replay transaction.** CAS prevents duplicate claims, but claim plus insert is not one database transaction. A reviewed function with transactional semantics is still required.
4. **Persistent audit verification.** Tests assert that `log_audit_event()` is called before sensitive operations with safe metadata. They do not prove hosted audit-table protection or persistence under real role contexts.
5. **Local versus hosted database.** The MCP catalog evidence is from the local Supabase stack only. Staging and production grants, RLS, policies, and effective-access behavior remain unverified.
6. **Deployment surface.** The hardened admin event router is not mounted by `main.py`; no admin event HTTP route was deployed by this order. Mounting it requires a separate reviewed API change.
7. **Runtime role evidence.** Tests use dependency overrides and fake clients; no hosted anon, patient, practitioner, org-admin, or system-admin identity was exercised.
8. **CLI verification.** `supabase test db` was not run because the CLI is unavailable in this environment.

---

## 6. Acceptance handoff

Before SEC-09 can be closed:

- approve and implement a trusted event-to-organization resolver, or formally narrow the policy to system-admin-only visibility;
- review and allowlist retry-safe handlers, or keep manual retry disabled with an explicit disposition;
- move replay claim and queue insertion into a reviewed transactional database function if single-transaction atomicity is required by the final design;
- mount the hardened admin router through a reviewed API change and rerun route tests against the mounted surface;
- verify audit persistence and protection in staging;
- run local `supabase test db` when the CLI is available;
- repeat catalog and effective-access checks in staging and production with distinct role identities;
- obtain reviewer acceptance and link evidence to both plans’ traceability registers.

**Current decision: NOT ACCEPTED.**

---

## 7. Cross-references

- [Phase 0 plan — WP-05 / order 3](PHASE-0-BACKEND-SECURITY-BASELINE-AND-REMEDIATION-PLAN-v2.0.md)
- [Backend plan — PH0-WP-05 / order 4](../backend/MedAeterna_Phase_0_Backend_Security_Baseline_and_Remediation_Plan_v2.0.md)
- [SPEC-09 — operational-event visibility and retry](SPEC-09-operational-event-visibility-and-retry.md)
- [Release guide](../backend/MedAeterna_Controlled_Supabase_Database_and_Storage_Release_Guide_v1.0.md)
- Focused tests: `backend/tests/api/admin/test_spec09_event_authorization.py`
