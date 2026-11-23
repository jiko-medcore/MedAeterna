# SPEC-09: Operational-Event Visibility and Retry

**Status:** Event visibility and manual-retry policy are defined in a reference evaluator, with safe metadata projection, scoped reads, retry gates, and event-log redaction tests. Initial admin-route enforcement landed on `security/phase-0-db-storage-release` @ `421d28a`; PH0-WP-05 then added data-layer projections, retry-safety gating, compare-and-set replay, and route-level integration tests in the same branch in implementation commit `9977b88`, followed by the focused authorization-order negative matrix in commit `3901101` (21 November 2026, local, committed, not pushed). Trusted organization resolution, handler retry-safety approval, full transactional atomicity, persistent/hosted audit evidence, and staging/production effective-access verification remain remediation work. See the [PH0-WP-05 completion record](PH0-WP-05-completion-record.md).

**Order 5 approval (21 November 2026):** Approved for implementation by the designated MedAeterna technical/security owner for the documented decisions only; not production acceptance. Undocumented visibility and retry choices remain fail-closed. See [PH0-WP-06 policy approval record](PH0-WP-06-SPEC-approval-and-consent-access-model.md).

## Decision

Operational-event reads and retries are separate permissions. Patients and practitioners have no access to administrative event queues. Organization administrators may read only approved organization-configuration event metadata for their own organization; they cannot retry events. System administrators may read approved global operational metadata and may retry one eligible event at a time, only for an allowlisted purpose and with verified retry authority and audit. Neither role receives event payloads or raw failure text.

## Read visibility and field boundaries

### Organization administrator

An org admin may read one event metadata row only when:

- The event type and aggregate type are in the fixed organization-event allowlist.
- Trusted backend resolution maps the event's authoritative aggregate to the exact organization in the active `org_admin` assignment. An `organization_id` inside event payload, request parameter, or client-supplied filter is not sufficient. If the owning organization cannot be resolved, deny.
- The server purpose is `organization_operations` and event visibility is approved.
- The payload is filtered server-side and the access is audited.

Patient aggregate events and patient onboarding-email events are never visible to org admins. Org admins cannot list/export all events across organizations, read dead-letter payloads, view event logs/audit payloads, or use any retry route.

### System administrator

A `super_admin` may access event status summaries and event metadata only for a server-selected `platform_health` or `security_incident` purpose, with approved visibility, audit, payload redaction, and SPEC-08 patient-data redaction. A separately scoped organization or practitioner assignment remains an independent role path; system-admin authority does not enlarge it.

For ordinary organization/configuration events, the maximum metadata projection is:

- `event_reference` (opaque event identifier)
- static, allowlisted `event_type`
- `status`
- `created_at` and `processed_at`
- `retry_count`
- `normalized_error_code` from a fixed safe code set

The only normalized error codes are `DEPENDENCY_TIMEOUT`, `DEPENDENCY_UNAVAILABLE`, `EVENT_HANDLER_NOT_FOUND`, `INVALID_EVENT`, and `PROCESSING_FAILED`. Raw exception text is never a normalized code and must not be stored in a field exposed to operators.

For a patient aggregate or patient-onboarding event, omit `event_type` and all aggregate identifiers. Only an opaque event reference, status/timestamps, retry count, and normalized error code may be returned after trusted redaction. The opaque reference must not be resolvable through an unguarded detail endpoint.

`payload`, `aggregate_id`, patient or organization IDs in raw event data, `last_error`, `failure_reason`, exception text, email, phone, names, arbitrary metadata, and raw headers are never returned. If a normalized error code cannot be produced, omit it. Status summaries may include only aggregate counts (`total`, `pending`, `processing`, `processed`, `failed`, `dead`, `success_rate`); no patient or event-type breakdown is returned to the system admin.

All list endpoints use bounded pagination with a maximum page size of 100. A detail endpoint applies the same role, purpose, redaction, and projection rules as a list result. UI hiding is not a security control.

## Manual retry

Only a system administrator may initiate a manual retry, for `event_recovery` or `security_incident`. The request is for one opaque event reference and requires a bounded non-empty reason that contains no patient data. The backend independently verifies the current persisted state, registered event handler, and a handler retry-safety review.

Eligible state rules:

- `failed`: retry count is below the configured maximum (currently 3).
- `dead`: the dead-letter row has not already been replayed; the replay creates one pending event and records the source as replayed.
- `pending`, `processing`, `processed`, unknown states, exhausted failed rows, and previously replayed dead-letter rows: deny.

No manual bulk retry is permitted. Retire or disable `/events/retry-failed` as an administrator operation; background retries are a separate service-worker responsibility with bounded attempts and no human actor authority.

Retry authorization and state transition must be atomic or compare-and-set so concurrent operators cannot duplicate retries. The retry worker consumes the private original event payload server-side; the operator receives only an opaque reference and a queued/result status. Require idempotent or otherwise retry-safe handler behavior before enabling its event type for manual retry.

Every retry writes a protected audit record with actor, approved purpose, reason, event reference, event type, state before/after, attempt count, timestamp, and outcome. Do not include event payload or raw exception text in the audit record. Audit failure means the retry must not proceed.

## Audit and application logs

Sensitive event reads and retries are themselves audited. Log records must not include event payloads, patient/aggregate identifiers, email addresses, raw failure/exception text, access tokens, secret keys, or secret-key prefixes. Use a normalized error code and opaque request/event reference where needed for troubleshooting.

The SPEC-09 change removes credential-prefix and aggregate/event identifier logging from event emission, dispatch, and inspected patient/organization event handlers, and maps exceptions to a fixed safe error code rather than persisting or logging exception messages. This is a logging hygiene control; it does not secure event API routes or replace audit records.

## Current implementation findings

Read-only source review (baseline) found:

- `backend/app/core/events/monitoring.py` uses `select('*')` for event and dead-letter lists/details. This can return payloads, raw error text, and aggregate identifiers.
- `backend/app/core/events/router.py` exposed read and retry endpoints without authentication dependencies, including `POST /events/retry-failed` (bulk retry).
- `backend/app/api/admin/events_router.py` used `get_current_user` but had no demonstrated role/purpose gate and returned monitoring-service output. `backend/app/api/admin/event_replay_router.py` similarly depended only on current-user authentication.
- `EventService.retry_event` sets any matching event back to pending without a status predicate or audit record. `backend/app/core/events/replay.py` checks replay state and inserts/marks replay in separate operations; that transition is also not atomic. Its audit call does not include a required reason or all state details from this SPEC.
- The checked-in migration snapshot enables RLS on `events` and `events_dead_letter` but grants broad table operations to `anon` and `authenticated`. This is source evidence, not verification of effective hosted grants or runtime exposure.
- Event rows do not contain a normalized `organization_id` column. Organization-scoped access needs a trusted owner resolver or a reviewed schema migration; do not scope from client input or a raw payload alone.
- The event registry and event types require a reviewed retry-safety mapping before any event type can be manually retried.

### PH0-WP-01 branch remediation progress (20 November 2026, local, unmerged)

Implemented on `security/phase-0-db-storage-release` @ `421d28a` (not pushed, no schema/Storage changes):

- **Admin event routes (`backend/app/api/admin/events_router.py`)**: restricted to authenticated system administrators with an approved purpose, bounded pagination/limits, explicit safe metadata projections (no raw payload/raw error text), policy-gated visibility/summary evaluation, and audit-before-access with fail-closed behavior. Dead-letter replay is single-event only, requires approved retry purpose and bounded reason, evaluates retry eligibility via `operational_event_policy`, and performs audit-before-retry with fail-closed behavior; operators receive only an opaque/status-safe queued result.
- **Duplicate/unsafe surfaces**: `backend/app/api/admin/event_replay_router.py` replay behavior neutralized (consolidated under admin events replay), and legacy unauthenticated `/events/*` operational read/retry/bulk-retry endpoints in `backend/app/core/events/router.py` disabled (404).
- **Admin audit/metrics (`backend/app/api/admin/audit_router.py`, `backend/app/api/admin/metrics_router.py`)**: hardened to system-admin + approved purpose with safe projections/fail-closed access and audit-before-read for audit access; onboarding event breakdown metrics denied as not a safe SPEC-09 projection.
- **Logging hygiene**: `backend/app/core/events/dead_letter.py` corrected to avoid unsafe/undefined audit logging and to avoid emitting sensitive details.

**Status of these gaps at PH0-WP-05:** the `select('*')` calls in `backend/app/core/events/monitoring.py` have been replaced with explicit metadata projections; `replay_dead_event` now uses a compare-and-set claim; generic service retry requires failed state and a retry count below the limit; a retry-safety allowlist hook exists but is intentionally empty; and route-level integration/negative tests have been added. These changes are local and do not close the SPEC.

**Remaining gaps (not closed):** trusted event-to-organization resolution and normalized `organization_id` are still absent, so organization-administrator scoped event reads remain disabled; no event handler is approved for manual retry; replay claim plus queue insertion is not one database transaction; audit assertions use fakes rather than hosted audit-table verification; the hardened admin router is not mounted by `main.py`; and local catalog checks do not prove hosted/staging RLS, grants, or effective access.

No local or hosted database schema or data was changed for either work item. The reference policy and branch hardening do not claim hosted grants, RLS, audit persistence guarantees, or full transaction semantics are proven.

### PH0-WP-05 branch remediation progress (21 November 2026, local, unmerged)

Implemented on `security/phase-0-db-storage-release` in commit `9977b88`; the authorization-order negative matrix and dead-letter projection correction were added in commit `3901101`:

- **Safe projections:** `backend/app/core/events/monitoring.py` and every admin event route now select fixed metadata fields only. Raw `failure_reason`/`last_error` text is normalized server-side to the fixed code set or omitted; payloads and aggregate identifiers are never returned.
- **Purpose separation:** reads require `platform_health` or `security_incident`; replay requires `event_recovery` or `security_incident`. Free-text retry reasons are bounded and rejected when they contain obvious contact data.
- **Retry-safety gate:** `MANUAL_RETRY_SAFE_EVENT_TYPES` plus `is_manual_retry_safe()` require both an explicit review allowlist and current handler registration. The allowlist is empty by design; registered handlers have side effects that are not proven idempotent.
- **Replay claim:** dead-letter replay performs a compare-and-set on `replayed = false` before inserting one pending event, with a compensating claim reset if insertion fails. This prevents duplicate claims but does not provide a single database transaction.
- **State-scoped service retry:** `EventService.retry_event()` now requires `status = failed` and `retry_count < 3`.
- **Route-level tests:** `backend/tests/api/admin/test_spec09_event_authorization.py` mounts the hardened router on an isolated app and verifies 401/403/400/422 denials, no query before authorization across all seven routes, route dependency introspection, safe projections, audit failure denial, retry-safety denial, contact-data rejection, CAS duplicate prevention, disabled legacy routes, and exact safe internal monitoring projections.
- **Local catalog evidence:** both event tables are RLS-enabled and forced with zero policies; anon/authenticated have no SELECT/INSERT/UPDATE/DELETE privilege; service_role retains those privileges; no `normalized_error_code` or `organization_id` column exists. The local CLI pgTAP suite later passed all three database test files, including SPEC-11 table privileges/policies and SPEC-12 Storage bucket policy.

The hardened admin router is intentionally not mounted by `main.py` in this slice. SEC-09 remains open; see the [PH0-WP-05 completion record](PH0-WP-05-completion-record.md) for the full evidence and limitations.

**Order 8 follow-up (23 November 2026, local):** the seven disabled legacy `/events/*` routes are now hidden from OpenAPI while continuing to return 404, and a contract test asserts that no `/events` path is published. `mark_failed()` now loads the full event scope before dead-lettering, so worker dead-letter rows retain id, type, aggregate, payload and a non-empty audit resource id (regression test added). The hardened admin router is still not mounted, the manual-retry allowlist is still empty, and no hosted verification is claimed. See the [PH0-WP-08/WP-09 privileged-path review record](PH0-WP-08-WP-09-privileged-path-review-record.md).

## Supabase/database enforcement

The future route/service implementation must use an explicit safe projection and trusted organization resolver. Database grants and RLS must independently block direct client reads/writes of event and dead-letter tables. Privileged service-role queries bypass ordinary RLS protections, so they must still apply the same server-side authorization and projection. Supabase's current RLS guide treats grants and policies as separate checks for exposed tables ([RLS guide](https://supabase.com/docs/guides/database/postgres/row-level-security)). SPEC-11 tracks the table-by-table grants and RLS implementation/tests.

## Executable policy and tests

`backend/app/core/operational_event_policy.py` defines event-type/aggregate allowlists, field projections, org-admin scoping, system-admin purposes and redaction, aggregate-only summaries, and single-event retry eligibility. It delegates role/action decisions to `backend/app/core/action_authorization.py`. Inputs such as organization resolution, payload redaction, approved visibility, handler retry safety, and audit completion are trusted server evidence; the reference policy does not perform those operations.

Focused tests are in `backend/tests/core/test_operational_event_policy.py`, `backend/tests/core/test_event_logging.py`, and `backend/tests/core/test_action_authorization.py`. They cover role boundaries, cross-organization denial, event and field allowlists, patient-event redaction, summary bounds, retries and invalid states, retry-safe handlers, audit/redaction gates, and safe event logs.

Route-level tests are in `backend/tests/api/admin/test_spec09_event_authorization.py`. They mount the hardened router on an isolated app and cover authentication, role denial before privileged queries, read/retry purpose allowlists on every route, empty-reason rejection, safe projections, audit failure on every read route and on replay, retry-safety denial, contact-data rejection, compare-and-set replay, disabled legacy routes, and exact internal monitoring selections. They do not prove hosted behavior or approve any handler for production retry.

## Acceptance criteria

- [x] Event read and retry are separate actions with explicit role boundaries.
- [x] Org admins are limited to approved organization events, exact organization scope, safe metadata, and no retry.
- [x] System-admin event visibility uses a short purpose allowlist and patient-data redaction; patient event types and aggregate identifiers are not exposed.
- [x] Event API access by patient/practitioner roles and event payload/raw-error visibility through these policies are denied.
- [x] Retry is system-admin-only, single-event, purpose-bound, audited, state-limited, and retry-safe; implementation is required to use an atomic/compare-and-set state transition.
- [x] Bulk manual retry is denied; background retry is separated from human authorization.
- [x] Existing API and database implementation gaps are recorded without implying they are remediated by the reference policy.
- [x] Focused and neighboring security-policy tests pass and are recorded below.
- [x] Event-emission and processing logs omit credentials, event/patient identifiers, and raw exception messages.

The checkboxes above describe the evaluated policy model and local implementation state, not closure of SEC-09. Manual retry remains fail-closed because no handler has an approved retry-safety decision, and org-admin event reads remain fail-closed because no trusted organization resolver exists.

## Verification record

Focused command: `.venv/Scripts/python.exe -m pytest tests/core/test_operational_event_policy.py tests/core/test_event_logging.py -q --tb=short -p no:cacheprovider` (run from `backend/`). Result: **35 passed**.

Security-policy regression command: `.venv/Scripts/python.exe -m pytest tests/core/test_operational_event_policy.py tests/core/test_event_logging.py tests/core/test_action_authorization.py tests/core/test_role_catalogue.py tests/core/test_system_admin_patient_access.py tests/core/test_organization_admin_patient_access.py tests/core/test_patient_relationship_policy.py tests/core/test_consent_policy.py tests/core/test_patient_access_grants_schema.py -q --tb=short -p no:cacheprovider` (run from `backend/`). Result: **373 passed**. Both runs reported 12 dependency deprecation warnings from installed `pyiceberg`/Pydantic packages; no tests failed.

`git diff --check` is clean. These baseline tests verify the pure policy and log output only. Route authentication/authorization, actual query projection, organization resolver, hosted grants/RLS, persistent audit, and full transactional retry evidence remain required before SEC-09 can be closed.

**PH0-WP-01 branch verification (20 November 2026, local, unmerged, commit `421d28a`, not independently rerun for this document update):** focused `.venv\Scripts\python.exe -m pytest tests/core/test_security_phase0_wp01.py tests/core/test_event_logging.py tests/core/test_operational_event_policy.py tests/core/test_action_authorization.py tests/organizations/test_router.py -q --tb=short` → **86 passed**; focused role-assignment regression `.venv\Scripts\python.exe -m pytest tests/auth/test_role_assignment_policy.py tests/auth/test_role_assignment_service.py -q --tb=short` → **15 passed**; OpenAPI generation `from main import app; app.openapi()` → **ok**; full backend suite `.venv\Scripts\python.exe -m pytest -q --tb=short` → **1,281 passed, 1 skipped, 18 warnings**. These runs provide supporting regression evidence for the branch hardening but do not substitute for route-level SPEC-09 integration tests, database/grant/RLS verification, or hosted/staging effective-access evidence.

**PH0-WP-05 branch verification (21 November 2026, local, committed as `9977b88` and `3901101`, not pushed):** route suite `.venv\Scripts\python.exe -m pytest tests/api/admin/test_spec09_event_authorization.py -q --tb=short -p no:cacheprovider` → **36 passed**; combined focused regression `.venv\Scripts\python.exe -m pytest tests/api/admin/test_spec09_event_authorization.py tests/core/test_operational_event_policy.py tests/core/test_event_logging.py tests/core/test_security_phase0_wp01.py -q --tb=no -p no:cacheprovider` → **80 passed**; full backend suite `.venv\Scripts\python.exe -m pytest -q --tb=no -p no:cacheprovider` → **1,334 passed, 1 skipped, 18 warnings**; OpenAPI generation → **81 paths**, unchanged; `git diff --check` → **clean**. Read-only Supabase MCP catalog queries confirmed forced RLS with zero policies, no anon/authenticated table privileges, service_role-only DML, and the expected projected columns on both event tables in the local database. These are local implementation and regression results only; they do not prove hosted/staging behavior, persistent audit protection, handler retry-safety approval, or SEC-09 closure. Local Supabase CLI v3.2.0 checks were subsequently run from `backend/supabase` against the local stack only: `supabase db query --read-only` succeeded, `supabase test db` passed **3 files / 28 tests** (including SPEC-11 and SPEC-12), `supabase migration list` showed all five local migrations matched local history, and `supabase db advisors --type security --level warn --fail-on none` completed with known local WARN advisories and no remediation. These CLI checks close the local tooling gap but do not prove hosted/staging behavior. Full evidence is in the [PH0-WP-05 completion record](PH0-WP-05-completion-record.md).
