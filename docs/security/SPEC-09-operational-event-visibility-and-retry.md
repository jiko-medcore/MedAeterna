# SPEC-09: Operational-Event Visibility and Retry

**Status:** Event visibility and manual-retry policy are defined in a reference evaluator, with safe metadata projection, scoped reads, retry gates, and event-log redaction tests. Existing route and database enforcement remain remediation work.

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

Read-only source review found:

- `backend/app/core/events/monitoring.py` uses `select('*')` for event and dead-letter lists/details. This can return payloads, raw error text, and aggregate identifiers.
- `backend/app/core/events/router.py` exposes read and retry endpoints without authentication dependencies, including `POST /events/retry-failed` (bulk retry). This is an existing SEC-09 implementation gap.
- `backend/app/api/admin/events_router.py` uses `get_current_user` but has no demonstrated role/purpose gate and returns monitoring-service output. `backend/app/api/admin/event_replay_router.py` similarly depends only on current-user authentication.
- `EventService.retry_event` sets any matching event back to pending without a status predicate or audit record. `backend/app/core/events/replay.py` checks replay state and inserts/marks replay in separate operations; that transition is also not atomic. Its audit call does not include a required reason or all state details from this SPEC.
- The checked-in migration snapshot enables RLS on `events` and `events_dead_letter` but grants broad table operations to `anon` and `authenticated`. This is source evidence, not verification of effective hosted grants or runtime exposure.
- Event rows do not contain a normalized `organization_id` column. Organization-scoped access needs a trusted owner resolver or a reviewed schema migration; do not scope from client input or a raw payload alone.
- The event registry and event types require a reviewed retry-safety mapping before any event type can be manually retried.

The new reference policy and log sanitization do not claim the existing routes, event queries, grants, RLS, audit writes, or retry transactions are fixed. No local or hosted database schema or data was changed for this SPEC.

## Supabase/database enforcement

The future route/service implementation must use an explicit safe projection and trusted organization resolver. Database grants and RLS must independently block direct client reads/writes of event and dead-letter tables. Privileged service-role queries bypass ordinary RLS protections, so they must still apply the same server-side authorization and projection. Supabase's current RLS guide treats grants and policies as separate checks for exposed tables ([RLS guide](https://supabase.com/docs/guides/database/postgres/row-level-security)). SPEC-11 tracks the table-by-table grants and RLS implementation/tests.

## Executable policy and tests

`backend/app/core/operational_event_policy.py` defines event-type/aggregate allowlists, field projections, org-admin scoping, system-admin purposes and redaction, aggregate-only summaries, and single-event retry eligibility. It delegates role/action decisions to `backend/app/core/action_authorization.py`. Inputs such as organization resolution, payload redaction, approved visibility, handler retry safety, and audit completion are trusted server evidence; the reference policy does not perform those operations.

Focused tests are in `backend/tests/core/test_operational_event_policy.py`, `backend/tests/core/test_event_logging.py`, and `backend/tests/core/test_action_authorization.py`. They cover role boundaries, cross-organization denial, event and field allowlists, patient-event redaction, summary bounds, retries and invalid states, retry-safe handlers, audit/redaction gates, and safe event logs.

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

## Verification record

Focused command: `.venv/Scripts/python.exe -m pytest tests/core/test_operational_event_policy.py tests/core/test_event_logging.py -q --tb=short -p no:cacheprovider` (run from `backend/`). Result: **35 passed**.

Security-policy regression command: `.venv/Scripts/python.exe -m pytest tests/core/test_operational_event_policy.py tests/core/test_event_logging.py tests/core/test_action_authorization.py tests/core/test_role_catalogue.py tests/core/test_system_admin_patient_access.py tests/core/test_organization_admin_patient_access.py tests/core/test_patient_relationship_policy.py tests/core/test_consent_policy.py tests/core/test_patient_access_grants_schema.py -q --tb=short -p no:cacheprovider` (run from `backend/`). Result: **373 passed**. Both runs reported 12 dependency deprecation warnings from installed `pyiceberg`/Pydantic packages; no tests failed.

`git diff --check` is clean. Tests verify the pure policy and log output only. Route authentication/authorization, actual query projection, organization resolver, grants/RLS, persistent audit, and transactional retry tests remain required remediation evidence before SEC-09 can be closed.
