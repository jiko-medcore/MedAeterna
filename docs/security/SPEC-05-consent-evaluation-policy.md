# SPEC-05: Consent Evaluation Policy

**Status:** Consent requirement, scope, lifecycle, precedence, and an executable reference evaluator are defined and tested. Current consent routes and database storage do not yet enforce this policy; implementation and live behavior remain remediation work.

**Order 5 approval (21 November 2026):** Approved for implementation by the designated MedAeterna technical/security owner for the documented decisions only; not production acceptance. No migration, runtime integration or unapproved purpose/recipient/resource choice is implied. See [PH0-WP-06 policy approval record](PH0-WP-06-SPEC-approval-and-consent-access-model.md).

## Purpose and boundaries

SPEC-05 defines when patient consent satisfies the consent gate referenced by SPEC-03. It applies to practitioner clinical use of clinical history, encounters, observations, conditions, prescriptions, laboratory results, and clinical documents.

Consent is one authorization input. It does not authenticate the caller, assign a role, create a patient relationship, prove organization membership, authorize a workflow, or grant an action missing from SPEC-03. SPEC-04 relationship checks, role and action checks, organization scope, purpose/workflow controls, and database grants/RLS remain independent. All applicable gates must pass.

The patient may review, grant, and revoke their own consent through patient-authorized workflows. This practitioner-use evaluator is not used to restrict the patient from accessing their own records. A guardian/proxy may grant or revoke only after a separate trusted process verifies legal authority; this SPEC does not accept unverified representatives.

## Consent requirement decision

- A trusted server policy must decide whether consent is required for the exact resource family, action, purpose, and legal/policy context. This decision is not inferred from a role, a consent row, or a client-supplied flag.
- The policy result must include a stable policy identifier and a canonical purpose code. Unknown, missing, contradictory, or unverified requirement decisions deny.
- If the trusted policy says consent is not required, the consent gate passes with the recorded policy identifier and purpose. This does not grant access: SPEC-03, SPEC-04, workflow, and database controls must still pass.
- A decision that consent is not required does not erase a separate patient objection, opt-out, or legal restriction. Those must be represented and evaluated by the applicable policy; a revoked grant alone is not treated as a universal denial of every independent legal basis.
- The `legal_basis` field is explanatory evidence. It cannot turn a consent-required request into a consent-not-required request; only the trusted policy decision can do that.

## Required consent match

When consent is required, one patient-authorized consent record must cover the entire requested context. Separate rows cannot be combined to construct missing scope.

The record must match all of the following:

| Dimension | Required decision |
|---|---|
| Grant/revocation authority | The latest consent decision was made by the authenticated patient identity mapped to the subject, or a separately verified representative. `granted_by` alone is not proof until linked to that identity; revocation authority must also be verified and audited. |
| Patient | Exact patient subject for the protected resource. |
| Organization | Exact organization context validated from the resource and caller scope. Missing organization is not a wildcard. |
| Recipient | Either the exact practitioner identity or an explicitly recorded organization recipient. A null practitioner ID does not imply organization-wide consent. |
| Resource | The exact requested clinical resource family is explicitly in scope. Missing or unparsed scope denies. |
| Purpose | Exact canonical purpose code matches the server policy and record. A broad label or a purpose for another workflow does not match. |
| Consent type | The trusted policy's allowlist for this purpose includes the record's consent type. `emergency` is excluded here and break-glass is prohibited by SPEC-08 for the current Phase 0 policy. |
| Action | The access level covers the requested action according to the table below. Consent does not supply SPEC-03 permission. |
| Lifecycle | The latest applicable consent decision is active, authorized, effective now, unrevoked, and unexpired. |

Consent for an organization is allowed only when the organization is explicitly identified as the recipient. Every practitioner using organization-scoped consent must independently pass SPEC-01/02 role scope and SPEC-04 patient relationship checks.

### Access-level interpretation

| Stored access level | Consent gate covers | Never covers |
|---|---|---|
| `read` | `read` | create, update, delete, administer, retry |
| `write` | `create`, `update` | read, delete, administer, retry |
| `full` | `read`, `create`, `update` | delete, administer, retry |

`full` means full clinical read/write scope within the consent's explicit resource, patient, recipient, organization, and purpose bounds. It is not unrestricted database access. Under SPEC-04, a read grant still cannot replace an active treating assignment for create/update.

## Lifecycle and precedence

- Only status `active` can authorize. `draft` is not patient approval and does not supersede a previous active decision. `revoked`, `rejected`, `expired`, malformed, or unknown statuses do not authorize.
- A consent must have a timezone-aware `granted_at` and a finite timezone-aware `expires_at`. Null expiry does not authorize a consent-required use. Expiry is exclusive: at `now >= expires_at`, the consent is expired.
- This SPEC deliberately requires a finite expiry. Existing indefinite consent records must be reviewed and renewed with an expiry; they are not silently backfilled as valid indefinitely.
- If `effective_from` is absent, it is treated as `granted_at`. A consent cannot authorize use before it was granted, even if a stored effective date is earlier. A future effective date denies until it begins. Expiry must be after the effective start.
- Revocation takes effect immediately. A revoked status or non-null `revoked_at` denies; `revoked_at` is not ignored just because status remains `active`.
- For records that match the same request context (patient, recipient, organization, purpose, resource, and permitted consent type), the latest decision event wins. A revocation event time is `revoked_at`; otherwise the event time is `granted_at`. The latest row determines action scope as well as status, so an earlier broader `full` grant cannot override a later `read`-only record.
- Equal latest event times are ambiguous and deny. A latest revoked, rejected, expired, future, or otherwise invalid decision does not fall back to an older grant. A later, explicit active grant may reauthorize the same scope.
- Patient, recipient, organization, type, purpose, resource scope, and access level are immutable after a grant is issued. A change requires revoking the old grant and creating a new, audited consent record; a revoked record is never reactivated.
- Draft rows are ignored because they have not become an authorized consent decision. Unrelated resources, purposes, patients, recipients, or organizations do not supersede each other.
- A patient must revoke an existing broad grant before replacing it with a narrower grant. A new narrow grant does not implicitly revoke older consent for other resources that the broad grant still covers.
- `otp_verified` may record an additional identity step, but it is not a substitute for verified patient authority and explicit consent scope. This SPEC does not impose OTP as a universal requirement; a stricter workflow can require it through a separate trusted policy.
- Emergency access is not authorized by `emergency_access=true` or `consent_type=emergency`. SPEC-08 prohibits system-administrator access and break-glass in the current Phase 0 policy; any future clinical emergency workflow requires a separate approved specification.

## Current storage and local database inspection

The application currently writes `public.consent_records`. Its schema has patient, organization, practitioner, grantor, type, access level, purpose, status, emergency flag, OTP flag, grant/effective/expiry/revocation timestamps, metadata, and a FHIR JSON field. The local catalog confirms that `patient_id` references `profiles(id)`, while practitioner and grantor IDs reference `practitioners(id)` and `profiles(id)` respectively. It has no normalized `recipient_kind` or resource-family scope column, and no `revoked_by` column. Important values besides `patient_id` and `id` are nullable, including organization, practitioner, grantor, access level, purpose, status, effective time, expiry, and grant time. The API also currently accepts optional practitioner, purpose, effective date, and expiry. The current service passes the authenticated user's ID as `patient_id` but does not populate `granted_by`; revocation updates status/time but does not record a revoking actor. Those operations do not yet provide the trusted grant/revoke authority evidence required here.

Without a trusted migration/resolver that establishes recipient kind, explicit resource scope, patient grant/revoke authority, and finite expiry, existing rows missing any required dimension cannot satisfy this policy. Do not treat arbitrary `metadata` or FHIR JSON as authorization evidence without a trusted, validated mapping.

Read-only local Supabase catalog inspection on 2026-11-19 found RLS enabled but not forced on `consent_records`, no policies on that table, and effective `SELECT`, `INSERT`, `UPDATE`, `DELETE`, and `TRUNCATE` privileges for `anon`, `authenticated`, and `service_role`. This is recorded as a local enforcement gap; no database change was made during the SPEC milestone. RLS and table grants are independent controls, and RLS does not remove excessive table privileges ([Supabase RLS guide](https://supabase.com/docs/guides/database/postgres/row-level-security)).

## Executable policy and tests

The pure evaluator is `backend/app/core/consent_policy.py`. It evaluates only the consent gate from normalized trusted policy and consent evidence. It does not query Supabase, prove grantor identity, establish patient relationship, determine legal consent requirements, or protect a route by itself.

Focused tests are in `backend/tests/core/test_consent_policy.py`. They cover exact subject/recipient/organization/resource/purpose matching; patient grant authority; recipient scope; consent types and access-level semantics; inactive, revoked, rejected, emergency, future, expired, and unscoped records; no-consent-required policy evidence; latest-decision precedence and regrant; tie denial; identity mismatches; and unsupported actions/roles.

## Acceptance criteria

- [x] The consent gate is separate from role/action permission and patient relationship.
- [x] Consent-required versus not-required decisions must come from a verified, identified policy; unknown requirement denies.
- [x] Subject, grantor authority, recipient, organization, purpose, resource, consent type, and action scope are checked independently.
- [x] `read`, `write`, and `full` have explicit boundaries; no level grants delete, administer, or retry.
- [x] Active status, finite expiry, effective time, immediate revocation, and ambiguous/multiple-record precedence are defined.
- [x] The evaluator treats revocation as terminal and only a separate later active record can regrant the same scope.
- [x] Consent rows cannot be combined to manufacture missing scope; a newer decision cannot fall back to older broader consent.
- [x] Patient grants do not replace SPEC-04 relationship checks; emergency consent is denied under SPEC-08's current prohibition on break-glass.
- [x] Current schema deficiencies and local RLS/grant findings are recorded without applying an unapproved schema change.
- [x] Focused consent-policy tests pass for positive, negative, cross-patient, cross-recipient, cross-organization, expiry, revocation, precedence, and privilege-escalation cases.

## Verification record

Command: `.venv/Scripts/python.exe -m pytest tests/core/test_consent_policy.py -q -p no:cacheprovider` (run from `backend/`).

Result: **43 passed**. The interpreter reported 12 dependency deprecation warnings from installed `pyiceberg`/Pydantic packages; there were no test failures.

Regression command: `.venv/Scripts/python.exe -m pytest tests/core/test_consent_policy.py tests/core/test_patient_relationship_policy.py tests/core/test_action_authorization.py -q -p no:cacheprovider` (run from `backend/`).

Result: **86 passed** (43 SPEC-05 cases, 30 SPEC-04 cases, and 13 SPEC-03 cases); the same 12 dependency deprecation warnings were reported.

Local database checks were catalog-only/read-only on 2026-11-19. They inspected the `consent_records` columns, RLS state, policies, and effective privileges; no patient consent data was read and no schema or row was changed.

These are policy unit tests and read-only catalog checks. Route-level grant/revoke/authorization tests, migration constraints, runtime RLS behavior under JWT identities, and deployment verification remain open. Phase 0 security findings are not closed by this SPEC.

## Deferred enforcement work

- Add a structured, validated recipient/resource scope and non-null lifecycle/authority requirements through an approved migration.
- Secure grant/revoke/list routes so only the patient or a verified representative can manage consent and every change is audited.
- Enforce consent-scope immutability and revoke/regrant transitions in the consent service and database boundary.
- Add table-by-table grants and RLS policies plus pgTAP tests; include authorization when backend code uses a privileged client.
- Integrate consent evaluation with SPEC-03 action, SPEC-04 relationship, role scope, and the approved resource workflow.
- Emergency consent and break-glass remain denied under SPEC-08; a future clinical emergency workflow requires a separate approved specification.
