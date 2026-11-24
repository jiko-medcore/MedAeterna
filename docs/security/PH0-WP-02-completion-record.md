# PH0-WP-02 Completion Record — Clinical Resource and Relationship Authorization

**Work package:** PH0-WP-02 / GitHub #35

**Title:** Clinical resources, relationships, appointments, consent enforcement

**Branch:** `security/phase-0-db-storage-release` (local working tree at time of writing; not committed or pushed for this record)

**Review date:** 20 November 2026

**Status:** **Implemented and locally verified — NOT CLOSED, NOT ACCEPTED**

**Policy references:** [SPEC-03](SPEC-03-action-level-authorization-matrix.md), [SPEC-04](SPEC-04-patient-relationship-access-policy.md), [SPEC-05](SPEC-05-consent-evaluation-policy.md), [SPEC-06](SPEC-06-canonical-patient-access-grants.md), [SPEC-07](SPEC-07-organization-admin-patient-data-boundary.md), [SPEC-08](SPEC-08-system-admin-patient-data-and-break-glass.md), [SPEC-09](SPEC-09-operational-event-visibility-and-retry.md), [SPEC-10](SPEC-10-trusted-backend-and-caller-rls-access.md)

**Finding disposition:** SEC-08, SEC-11, SEC-12, SEC-14, SEC-15 and SEC-16 are **partially mitigated locally**. None is closed by this record.

> This record documents the completed local implementation order only. It does not claim staging or production verification, RLS/grant effectiveness, full consent enforcement, or Phase 0 acceptance. See the [Phase 0 plan](PHASE-0-BACKEND-SECURITY-BASELINE-AND-REMEDIATION-PLAN-v2.0.md) for the evidence-discipline rules.

---

## 1. Scope completed

The following six routers were migrated end to end. All 24 declared endpoints now obtain an authorization decision before any service-layer query:

| Module | Router file | Endpoints | Resource family |
|---|---|---:|---|
| Medication requests | `backend/app/modules/medications/router.py` | 4 | `clinical_record` |
| Encounters | `backend/app/modules/encounters/router.py` | 3 | `clinical_record` |
| Appointments | `backend/app/modules/appointments/router.py` | 4 | `appointment` |
| Observations | `backend/app/modules/observations/router.py` | 4 | `clinical_record` |
| Conditions | `backend/app/modules/conditions/router.py` | 4 | `clinical_record` |
| Care teams | `backend/app/modules/care_team/router.py` | 5 | `care_team` |

The named entry point for this order — `GET /medication-requests/encounter/{encounter_id}` — is included in that migration.

**Not included in this local slice:** practitioner-role administration, consent grant/revoke/list routes, canonical `patient_access_grants` integration, clinical-table RLS/grant reconciliation, and hosted/staging evidence. These remain separate remediation work and are not marked complete here.

---

## 2. Delivered implementation

### 2.1 Shared clinical authorization contract

New file: `backend/app/core/clinical_authorization.py`

| Helper | Purpose |
|---|---|
| `authorize_clinical_access()` | Binds a verified identity to a patient-scoped resource, combines SPEC-04 relationship evidence with SPEC-03 `evaluate_action()`, and returns an explicit authorization context. |
| `authorize_patient_scoped_access()` | Adds patient-list/read workflow and care-team-membership checks. |
| `authorize_table_access()` | Loads a stored resource by id, derives patient/organization/practitioner context from that row, and authorizes before returning. |
| `authorize_practitioner_schedule_access()` | Enforces self-only practitioner appointment lists with explicit organization context. |
| `require_patient_clinical()` / `require_encounter_clinical()` / `require_table_clinical()` | Declarative FastAPI dependencies used by the migrated routers. |
| `ensure_authorized_context()` | Service-boundary check that rejects missing, wrong-action, wrong-patient, wrong-organization, or wrong-resource contexts. |
| `audit_clinical_write()` | Writes attributable care-team mutation audit records. |

`backend/app/core/security.py` now exposes narrow public aliases for trusted resource lookup, practitioner-id resolution, active care-team access, and active consent access. The canonical patient/encounter authorization contracts remain in `security.py`; no duplicate dependency contract was introduced.

### 2.2 Router and service changes

Each migrated service function now requires the authorization context returned by its route and validates it with `ensure_authorized_context()`. A direct service call with no context, or with a context for a different patient, organization, action, or resource id, fails closed before the service-role query.

Encounter-scoped medication, observation, and condition reads resolve `patient_id` and `organization_id` from the stored encounter in the dependency layer. Encounter-to-patient linkage is also checked before medication, observation, and condition writes.

---

## 3. Authorization decisions applied

| Resource / action | Applied decision |
|---|---|
| `clinical_record` read by patient | Patient self only; verified owner, permitted resource scope. |
| `clinical_record` create/update by patient | Denied. |
| `clinical_record` read/create/update by practitioner | Exact organization scope, active organization-bound relationship through the canonical patient-access path, clinical workflow evidence, and SPEC-03 action decision. |
| `clinical_record` by organization administrator | Denied. Care-team administration does not grant clinical-record access. |
| `clinical_record` by system administrator | Denied under SPEC-08. |
| `appointment` read by patient | Patient self only. |
| `appointment` practitioner schedule read | Active practitioner profile, exact authenticated practitioner id, explicit in-scope organization, and `appointment_assigned_to_actor`. |
| `appointment` create by practitioner | Practitioner id is bound to the authenticated actor; patient and organization relationship plus workflow evidence required. |
| `appointment` update by practitioner | Patient/organization resolved from stored appointment; practitioner reassignment rejected. |
| `care_team` read | Practitioner requires active care-team membership; organization administrator requires exact organization scope and patient-organization boundary. |
| `care_team` create/update/administer | Organization administrator only, with exact organization scope, patient-organization boundary, and audit evidence. |
| Care-team practitioner target | Must hold an active practitioner role in the exact organization. Self-assignment is denied. |

### 3.1 Medication-request encounter retrieval

For `GET /medication-requests/encounter/{encounter_id}` the order is:

1. Authenticate with `get_current_user`.
2. Load the encounter from trusted server-side storage.
3. Resolve the encounter’s patient and organization from that row.
4. Run `authorize_patient_scoped_access()` (SPEC-04 relationship evidence plus SPEC-03 action decision).
5. Return an authorization context containing the authorized patient, organization, action, resource, user, and encounter id.
6. Only then call the medication service, which rechecks the context before its service-role query.

Denials at steps 1–4 occur before the service function is entered. Focused route tests assert that the service was not called on 401/403 outcomes.

---

## 4. Audit behavior

Care-team create, participant add, participant update, and assignment service writes emit `log_audit_event()` records with:

- actor id from the authorization context;
- action such as `care_team.create`, `care_team.add_participant`, `care_team_participant.update`, or `patient_care_team.assign`;
- resource type and resource id;
- patient and organization metadata from the verified context.

This is direct application audit coverage for sensitive care-team mutations only. It is not a claim of complete audit coverage for every clinical read, appointment mutation, or operational event.

---

## 5. Verification evidence

All commands were run from `backend/` on Windows using `.venv/Scripts/python.exe`.

| Check | Command | Result |
|---|---|---|
| WP-02 focused tests | `.venv/Scripts/python.exe -m pytest tests/core/test_security_phase0_wp02.py -q --tb=short -p no:cacheprovider` | **17 passed** |
| Core security suite | `.venv/Scripts/python.exe -m pytest tests/core -q --tb=short -p no:cacheprovider` | **530 passed** |
| Full backend suite | `.venv/Scripts/python.exe -m pytest -q --tb=short -p no:cacheprovider` | **1,298 passed, 1 skipped** |
| API schema generation | `.venv/Scripts/python.exe -c "from main import app; spec=app.openapi(); print('paths',len(spec['paths']))"` | **81 paths** |
| Whitespace/patch sanity | `git diff --check --ignore-cr-at-eol` | Clean |

The focused suite uses an in-memory fake `supabase_admin`; no hosted database, patient data, or production credential was used. It covers:

- patient self-read allowance and patient clinical-write denial;
- practitioner relationship allowance and missing-relationship denial;
- cross-organization and cross-patient practitioner denial;
- system-administrator clinical-record denial;
- organization-admin care-team allowance in-org and denial out-of-org;
- appointment assignment checks and self-only schedule denial;
- service-boundary rejection of missing/mismatched contexts;
- unauthenticated and denied medication-request encounter retrieval with proof that no service call occurred;
- cross-patient observation encounter retrieval denial before service call;
- patient care-team creation denial before service call.

---

## 6. Evidence limits and open work

The following remain explicitly open. This work package is **not** sufficient to close the related SEC findings:

1. **Hosted RLS and grants.** All migrated modules still execute through trusted backend clients. Application authorization now precedes those queries, but database policies, grants, and effective service-role behavior have not been verified in staging or production (SEC-07, SEC-17, SEC-18, SEC-20).
2. **Clinical-table reconciliation.** The reviewed SPEC-11 inventory does not yet include all clinical relations used by these routes (SEC-17).
3. **Consent.** Full SPEC-05 purpose, recipient, resource-family, lifecycle, and provenance evaluation is not implemented in this slice. The SPEC-03 `consent_if_required` condition is currently satisfied through the canonical patient-access path, which accepts an active organization-bound care-team relationship or an active consent record; it is **not** a full consent-policy decision. SEC-19 remains open.
4. **Workflow completeness.** Appointment status transitions and complete field-level allowlists for clinical updates are not fully specified or tested.
5. **Audit completeness.** Only care-team mutations are audited by this slice. Other sensitive reads/writes and event retry audit evidence remain open (SEC-09, Audit #16).
6. **Practitioner-role administration and consent routes.** These were listed under the broader WP-02 scope but are unchanged here.
7. **Runtime/staging evidence.** No deployed configuration was changed or verified by this record.

---

## 7. Acceptance handoff

Before the parent work package or related SEC findings can be closed:

- integrate full SPEC-05 consent evaluation and complete SPEC-06 grant lifecycle;
- reconcile clinical tables into the SPEC-11 inventory and verify hosted RLS/grants under real role contexts;
- complete appointment status-transition and field-level workflow rules;
- extend audit coverage to all sensitive assignments/mutations/retries;
- rerun route-level positive/negative tests against staging and record effective-access evidence;
- obtain reviewer acceptance and link that evidence to the traceability register.

---

## 8. Cross-references

- [Phase 0 plan — WP-02 progress and traceability](PHASE-0-BACKEND-SECURITY-BASELINE-AND-REMEDIATION-PLAN-v2.0.md)
- [SPEC-03 — action-level authorization matrix](SPEC-03-action-level-authorization-matrix.md)
- [SPEC-04 — patient relationship access policy](SPEC-04-patient-relationship-access-policy.md)
- [SPEC-10 — trusted backend and caller-RLS access](SPEC-10-trusted-backend-and-caller-rls-access.md)
- Focused tests: `backend/tests/core/test_security_phase0_wp02.py`

---

## 9. Order 9 route-by-route extension (24 November 2026)

The earlier six-router scope was extended by the [Order 9 route-by-route record](PH0-WP-02-route-authorization-order-9-record.md). That record maps all **45 mounted sensitive clinical/patient routes**, adds forged-practitioner-id binding, closes the `/patients/mine` service boundary, removes overbroad projections, and records 44 new local route-level tests. The local order 9 evidence is complete; hosted/staging verification, full consent/grant lifecycle, audit completeness, and SEC closure remain open. This record does not change the status above: PH0-WP-02 is **NOT CLOSED** and Phase 0 is **NOT ACCEPTED**.
