# PH0-WP-02 Follow-up — Legacy Medical Records and Laboratory Service Boundaries

**Branch:** `security/ph0-wp02-legacy-record-lab-context`  
**Starting commit:** `bcb1c51839e8bd34df3674bd18258a013b293733` (PR #48 merge commit)  
**Target integration base:** `main` at `3e9283833fb715ec340e2ea24e0d04c4674877b8`  
**Status:** **IMPLEMENTATION IN PROGRESS — CI/acceptance pending**  
**Scope:** Repository code and tests only. No hosted or production database, Storage, configuration, migration, or deployment work.

## 1. Merge-state verification

At workstream start:
- PR #47 was merged into `main` as `3e9283833fb715ec340e2ea24e0d04c4674877b8`. Its exact-head Backend CI run `45688886287` succeeded (1,495 passed, 1 skipped, 6 warnings).
- PR #48 was marked merged as `bcb1c51839e8bd34df3674bd18258a013b293733`, but its base was `security/ph0-wp01-patient-relationship-integration`, not `main`. Its merge commit is the tip of that feature branch; it is not an ancestor of the observed `main` head. Therefore PR #48's implementation is not yet integrated into `main`.
- The push-triggered Backend CI run `45694151400` succeeded on the `main` head that includes PR #47. This does not verify PR #48 or this follow-up.

This branch starts from PR #48's merge commit so it carries those changes forward. Its eventual PR must target `main`; the resulting diff will include PR #48's not-yet-main changes plus this workstream. Do not claim PR #48 is part of `main` until a later integration commit proves it.

## 2. Source-derived caller and resource map

### Legacy `medical_records`

Current schema evidence from `backend/sql/Records/records.sql`:
- `id`, `patient_id`, `clinician_id`, `record_type`, `recorded_at`, `clinical_data`, `created_at`, `updated_by`, `updated_at`.
- No `organization_id`, `facility_name`, `provider_name`, or `summary` columns in the reviewed migration schema. Organization scope must be resolved from the persisted patient row; do not add or assume an organization field on this legacy table without a separate schema decision/migration.
- The history projection is therefore restricted to the persisted `id, created_at, record_type` columns. Existing presentation keys for facility/provider/description remain empty until a separately approved data-model change supplies those fields.

Callers and operations:
- `POST /records/observations` — legacy clinical-record create.
- `POST /records/conditions` — legacy clinical-record create.
- `POST /records/medications` — legacy medication request represented in `medical_records`.
- `PATCH /records/conditions/{record_id}/resolve` — ID-based condition update; must resolve the stored row before authorizing the patient, organization, record type and resource ID.
- `GET /api/v1/medical-history` — authenticated patient's history; patient identity is derived from the authenticated actor.
- `GET /patients/{patient_id}/fhir`, `GET /patients/{patient_id}/summary`, and `GET /patients/{patient_id}/timeline` — additional patient-facing reads that query `medical_records` through patient services.

The previous service functions accepted no explicit authorization context. The medical-history formatter called `fetch_medical_records(patient_id)`; the patient summary/FHIR/timeline services also queried `medical_records` without validating the route decision at the service boundary.

### Laboratory result

Current schema evidence from `backend/sql/Laboratory/create_lab_file_storage.sql`:
- `id`, `patient_id`, `clinician_id`, `test_name`, `status`, `result_data`, `file_url`, `performed_at`, `created_at`.
- No organization, order, specimen, or assignment foreign-key column is present in this reviewed schema file.

Mounted route:
- `GET /api/v1/lab-results/{lab_id}` — one result-detail read. There are no laboratory create/update routes in the reviewed module.

SPEC-04 permits practitioner laboratory-result reads only through a qualifying read relationship plus the independent SPEC-03/SPEC-05 gates. Laboratory result create/update requires an active assignment bound to the exact laboratory order/specimen; a general treatment assignment is insufficient. The reviewed lab schema and mounted module do not expose the order/specimen assignment needed to authorize writes. This work therefore adds no lab write route and does not invent an assignment from `clinician_id`.

## 3. Implementation delivered in this branch (verification pending)

### Shared authorization mapping
- Added `medical_records` and `lab_results` to the stored-resource authorization table map using minimal scope projections.
- Added an explicit relationship-resource-family parameter to the shared clinical authorization path. The laboratory route now asks SPEC-04 to evaluate `lab_result`, rather than silently treating every table as generic clinical history.
- The organization for both legacy tables is derived from the stored patient row where required; the table schemas are not represented as having an `organization_id` column.

### Legacy medical records
- `create_record()`, `resolve_condition_record()`, and `fetch_medical_records()` now require an explicit service authorization context before their data operations.
- Record creation derives `clinician_id` from `authorized_user_id`; it no longer accepts an independent clinician identity argument.
- Condition resolution now receives the stored-resource authorization context, checks its record ID, patient ID and `record_type=condition`, then constrains both the clinical read and update by ID, patient ID and record type.
- The condition route uses the stored-resource authorization helper instead of performing its own privileged lookup and then separately authorizing.
- Patient medical-history, FHIR, summary and timeline reads now use the shared clinical action authorization and pass the resulting context into their services. Patient self-read remains available only through verified patient identity.

### Laboratory result
- The route resolves only the stored row's minimal authorization fields through `authorize_table_access()`, then passes the resulting context to the detail service.
- The detail service requires matching `clinical_record/read`, patient and resource-ID context before fetching clinical display fields.
- The detail query is constrained by both `lab_id` and the patient ID resolved before authorization. No `raw` or wildcard projection is returned.

## 4. Consent and workflow boundary

- Practitioner clinical-record create/update remains fail-closed because the SPEC-03 action matrix requires trusted `consent_if_required` and `clinical_workflow` conditions. This implementation does not fabricate either condition.
- Practitioner clinical-record and lab-result reads remain fail-closed when SPEC-05's required consent evidence is not supplied. An active treatment relationship is not consent.
- Patient self-read remains subject to verified patient identity and the permitted resource scope.
- SPEC-06 patient-approved grants are not loaded or assumed installed.
- Laboratory writes remain out of scope until an approved schema/source provides a verifiable exact order/specimen assignment and the required role/action, workflow, and consent checks.

## 5. Focused regression coverage added (CI pending)

`backend/tests/core/test_f5_clinical_authorization_order.py` now covers:
- missing service context denial before lab detail or legacy record queries;
- lab detail resource-ID and patient filters, reviewed field projection and absence of `raw`;
- condition resolution context binding to stored record ID, patient ID and record type;
- condition read/update filters and actor provenance;
- legacy record create context requirement and clinician actor binding;
- minimal medical-history projection;
- patient summary/FHIR/timeline service denial before data access when context is missing.

Exact branch head verified: `62b3ffd6f07c4934f3ec8762ac2fcf53f8b6910a`.

GitHub Actions run `45697746429` — **SUCCESS**:
- Backend compile step passed.
- Backend test suite: **1,523 passed, 1 skipped, 6 warnings**.
- No test failures.

An earlier run failed because a patient-role test fixture incorrectly assigned an organization scope to the patient role; the fixture was corrected to match the role catalogue's global patient-role semantics. The final exact-head run above passed.

## 6. Explicit exclusions and stop controls

- No SPEC-05 consent evaluator implementation.
- No SPEC-06 grant table integration or migration.
- No lab result create/update support or invented order/specimen assignment.
- No broad migration of unrelated patient profile/self-service operations.
- No production or hosted Supabase reads/writes, migrations, Storage mutation, config change, or deployment.
- SEC-01–SEC-24 remain open; Phase 0 remains STOP / NOT ACCEPTED; Gate G is not met.
