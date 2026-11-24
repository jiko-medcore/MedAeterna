# PH0-WP-02 / Order 9 — Route-by-Route Clinical Authorization Record

**Work package:** PH0-WP-02 / GitHub #35, recommended execution order 9

**Branch:** `security/phase-0-db-storage-release`

**Review base:** local commit `cf9c769` plus the uncommitted changes described in this record

**Review date:** 24 November 2026

**Status:** **LOCAL ORDER 9 EVIDENCE COMPLETE — PH0-WP-02 NOT CLOSED — PHASE 0 NOT ACCEPTED**

**Policy references:** [SPEC-03](SPEC-03-action-level-authorization-matrix.md), [SPEC-04](SPEC-04-patient-relationship-access-policy.md), [SPEC-05](SPEC-05-consent-evaluation-policy.md), [SPEC-06](SPEC-06-canonical-patient-access-grants.md), [SPEC-07](SPEC-07-organization-admin-patient-data-boundary.md), [SPEC-08](SPEC-08-system-admin-patient-data-and-break-glass.md), [SPEC-10](SPEC-10-trusted-backend-and-caller-rls-access.md)

> This record supplies the local route-by-route authorization map, service-boundary evidence, and positive/negative regression evidence required by the local portion of PH0-WP-02 and recommended order 9. It does **not** claim staging/runtime verification, hosted RLS/grant effectiveness, full SPEC-05 consent lifecycle enforcement, SEC closure, or Phase 0 acceptance. No hosted mutation was performed; only the two read-only checks in section 6 were run.

---

## 1. Scope and result

The mounted application exposes **45 sensitive clinical/patient routes**. Every route in the map in section 3 now has:

- authentication through `get_current_user` (or an equivalent bearer dependency);
- an explicit patient, resource, practitioner, organization, or self-actor gate before the data operation;
- a reviewed, narrow response projection where the route returns patient or clinical data;
- a service-boundary check where the order 8/9 authorization context is carried into a service;
- route-level negative evidence for unauthenticated, wrong-role, cross-patient, cross-organization, forged-actor, and no-service-call cases where applicable.

The local order 9 exit condition — route map plus guarded domain boundary plus passing local positive/negative tests — is met. The broader PH0-WP-02 exit condition is **not** met because hosted/staging effective-access evidence, full consent/grant lifecycle, complete audit coverage, and SEC disposition remain open.

---

## 2. Changes completed in this order

| Change | Files | Effect |
|---|---|---|
| Actor binding | `backend/app/core/clinical_authorization.py` | `bind_clinical_actor()` copies a clinical create payload, rejects a forged/mismatched `practitioner_id`, and fills an omitted value from the already-authorized practitioner context. `practitioner_organization_id()` resolves exactly one practitioner organization or denies. |
| Closed patient-list context | `backend/app/core/clinical_authorization.py`, `backend/app/modules/patients/router.py`, `backend/app/modules/patients/service.py` | `GET /patients/mine` derives practitioner identity and organization from trusted role state, passes a closed `patient_list` authorization context, and the service refuses direct calls without it. Results come only from active organization-scoped `patient_care_team` rows. |
| QR overfetch removed | `backend/app/modules/patients/router.py` | `GET /patients/{patient_id}/qr` no longer loads full patient/clinical rows; it encodes only the already-authorized patient identifier. |
| Reviewed projections | `patients`, `encounters`, `observations`, `conditions`, `medications`, `appointments`, `care_team`, `consents`, `records`, `prescriptions`, `reminders`, `laboratory` services | All `select("*")` and wildcard nested projections on the touched clinical/patient read paths were replaced with explicit field lists. |
| Real local schema columns | `backend/app/modules/laboratory/service.py`, `backend/app/modules/reminders/service.py` | Lab detail uses `result_data`, `performed_at`, and `clinician_id`; reminders use `reminder_date` instead of the nonexistent `scheduled_at`. |
| Dashboard repair | `backend/app/modules/dashboard/service.py` | `build_user_summary()` now calls `get_or_create_patient(id, email)`, unwraps the documented result, and uses reviewed patient field names. |
| Focused evidence | `backend/tests/core/test_order09_clinical_route_authorization.py` | 44 tests cover the exact mounted route set, missing/invalid tokens, role/org/patient denials, forged practitioner IDs, no-service-call assertions, a trusted care-team positive case, attributable audit, and projection/schema guards. |
| Existing test adjustment | `backend/tests/core/test_f5_clinical_authorization_order.py` | Synthetic lab fixture now matches the real reviewed projection. |

No hardened admin event/audit/metrics router was mounted. No database migration, hosted mutation, object upload/delete, SEC closure, or Phase 0 acceptance was performed.

---

## 3. Per-route authorization map

“Service boundary” below means the handler cannot call the data service without the route-derived context, or the service itself rechecks the closed context before the privileged query.

| # | Route | Principal and pre-query gate | Resource decision / service boundary |
|---:|---|---|---|
| 1 | `GET /patients/medical-id` | Bearer, `is_patient` | Actor self only; `get_patient_medical_id(current_user["id"])`. |
| 2 | `GET /patients/me` | Bearer, `is_patient` | Actor self only; `get_or_create_patient(id, email)` returns the documented `{patient, created}` shape. |
| 3 | `GET /patients/profile/me` | Bearer, `is_patient` | Actor self only; reviewed `PATIENT_PROFILE_SELECT`. |
| 4 | `GET /patients/mine` | Bearer; `authorize_patient_list_access()` requires a practitioner role, a resolvable practitioner profile, and exactly one practitioner organization | Closed `patient_list` context; service requires it and reads only active `patient_care_team` rows in that organization, then constrains patients to the same organization. |
| 5 | `PUT /patients/profile/me` | Bearer, `is_patient` | Actor self only; mutable fields constrained by `PatientUpdate`. |
| 6 | `GET /patients/{patient_id}/fhir` | Bearer, `authorize_patient_access()` | Patient self or verified relationship; export uses `id, fhir_metadata` only. |
| 7 | `GET /patients/{patient_id}/qr` | Bearer, `authorize_patient_access()` | Authorized patient id only; no patient/clinical row fetch. |
| 8 | `GET /patients/{patient_id}/summary` | Bearer, `authorize_patient_access()` | Authorized patient scope; reviewed patient and record summary projections. |
| 9 | `GET /patients/{patient_id}/timeline` | Bearer, `authorize_patient_access()` | Authorized patient scope; reviewed timeline projection. |
| 10 | `POST /patients/{patient_id}/assign` | Org-scoped `require_permission("assign_patient")`, then `authorize_patient_access()` with the authorized organization | Patient/org boundary checked before assignment write. |
| 11 | `POST /patients/profile/upload-avatar` | Bearer, `is_patient` | Storage path derived from actor id; validated MIME/size; no caller path input. |
| 12 | `POST /records/observations` | Bearer, `authorize_patient_access()` plus `authorize_permission("create_observation")` in resolved organization | Actor/rule write; no patient id from the caller is trusted as relationship evidence. |
| 13 | `POST /records/conditions` | Bearer, `authorize_patient_access()` plus `authorize_permission("create_condition")` | Actor/rule write in resolved organization. |
| 14 | `POST /records/medications` | Bearer, `authorize_patient_access()` plus `authorize_permission("create_medication")` | Actor/rule write in resolved organization. |
| 15 | `PATCH /records/conditions/{record_id}/resolve` | Bearer; minimal stored condition row, then `authorize_patient_access()` plus `authorize_permission("resolve_condition")` | Service reauthorizes and constrains the read/update by id, patient, and record type. The safe-column lookup still precedes authorization; the 404-vs-403 disclosure residual from order 8 §7 remains open. |
| 16 | `POST /care-teams/` | Bearer, SPEC-03 `care_team.create`; org admin only, exact patient/org boundary, audit condition | `ensure_authorized_context()` before service; service emits attributable audit. |
| 17 | `POST /care-teams/{care_team_id}/participants` | Stored team supplies patient/org; org admin exact org; target must be an active practitioner in that org | Context rechecked before service; self/foreign-org targets denied. |
| 18 | `GET /care-teams/patient/{patient_id}` | `require_patient_clinical(CARE_TEAM, read)`; practitioner needs active care-team membership, org admin needs exact org care authority | Context rechecked before service; reviewed nested projections. |
| 19 | `PATCH /care-teams/participants/{participant_id}` | Stored participant/team supplies patient/org; org admin exact org | Context rechecked before constrained service update. |
| 20 | `POST /care-teams/assign` | Bearer, org admin exact org; no self-assignment; target active practitioner in exact org | Context rechecked before service; audit emitted. |
| 21 | `POST /consents/grant` | Bearer, `is_patient` | Patient id is the actor id, not a client claim. |
| 22 | `POST /consents/revoke` | Bearer, `is_patient` | Patient id is the actor id; service constrains revocation by patient and consent id. |
| 23 | `GET /consents/me` | Bearer, `is_patient` | Actor self only; reviewed `CONSENT_SAFE_SELECT`. |
| 24 | `POST /encounters/` | Bearer; appointment linkage resolved from stored appointment, then clinical create authorization | `bind_clinical_actor()`; service requires the action context. |
| 25 | `GET /encounters/patient/{patient_id}` | `require_patient_clinical(CLINICAL_RECORD, read)` | Context rechecked before service; reviewed `ENCOUNTER_LIST_SELECT`. |
| 26 | `PATCH /encounters/{encounter_id}` | `require_table_clinical("encounters", update)` using stored row; update schema excludes identity fields | Context rechecked before service; no client-supplied patient/org reassignment. |
| 27 | `POST /observations/` | Bearer; encounter linkage resolved from stored encounter, then clinical create authorization | `bind_clinical_actor()`; service requires context. |
| 28 | `GET /observations/patient/{patient_id}` | `require_patient_clinical(CLINICAL_RECORD, read)` | Context rechecked; reviewed list projection. |
| 29 | `GET /observations/encounter/{encounter_id}` | `require_encounter_clinical(CLINICAL_RECORD, read)` resolves patient/org from stored encounter | Context rechecked; reviewed detail projection. |
| 30 | `PATCH /observations/{observation_id}` | `require_table_clinical("observations", update)` using stored row; update schema excludes identity fields | Context rechecked before service. |
| 31 | `POST /conditions/` | Bearer; encounter linkage resolved from stored encounter, then clinical create authorization | `bind_clinical_actor()`; service requires context. |
| 32 | `GET /conditions/patient/{patient_id}` | `require_patient_clinical(CLINICAL_RECORD, read)` | Context rechecked; reviewed list projection. |
| 33 | `GET /conditions/encounter/{encounter_id}` | `require_encounter_clinical(CLINICAL_RECORD, read)` | Context rechecked; reviewed detail projection. |
| 34 | `PATCH /conditions/{condition_id}` | `require_table_clinical("conditions", update)` using stored row; update schema excludes identity fields | Context rechecked before service. |
| 35 | `POST /medication-requests/` | Bearer; encounter linkage resolved from stored encounter, then clinical create authorization | `bind_clinical_actor()`; service requires context. |
| 36 | `GET /medication-requests/patient/{patient_id}` | `require_patient_clinical(CLINICAL_RECORD, read)` | Context rechecked; reviewed list projection. |
| 37 | `GET /medication-requests/encounter/{encounter_id}` | `require_encounter_clinical(CLINICAL_RECORD, read)` resolves patient/org from stored encounter | Context rechecked; reviewed detail projection. |
| 38 | `PATCH /medication-requests/{medication_request_id}` | `require_table_clinical("medication_requests", update)` using stored row; update schema excludes identity fields | Context rechecked before service. |
| 39 | `POST /appointments/` | Bearer; `practitioner_actor_id()` and payload practitioner id must match, then appointment create authorization | Actor id bound into payload; service requires context. |
| 40 | `GET /appointments/patient/{patient_id}` | `require_patient_clinical(APPOINTMENT, read)` | Context rechecked; reviewed appointment projection. |
| 41 | `GET /appointments/practitioner/{practitioner_id}` | Bearer plus `require_practitioner`; organization must be explicit and in-role or uniquely resolved; `authorize_practitioner_schedule_access()` enforces self-only schedule access | Context rechecked; foreign practitioner ids denied. |
| 42 | `PATCH /appointments/{appointment_id}` | Bearer; `authorize_table_access()` resolves patient/org/practitioner from stored appointment; reassignment denied | Context rechecked; reviewed update projection and field-limited schema. |
| 43 | `GET /api/v1/medical-history` | Bearer, `is_patient` | Actor self only; service reads history for `current_user["id"]`. |
| 44 | `GET /api/v1/lab-results/{lab_id}` | Bearer; minimal `id, patient_id` scope read, then `require_patient_access()` | Approved detail columns only after authorization; no `raw` full row. |
| 45 | `GET /api/v1/user/summary` | Bearer, `is_patient` | Actor self only; reviewed patient/prescription/reminder projections. |

The route-set assertion in `test_mounted_sensitive_routes_match_authorization_map` compares the live FastAPI router table with this exact 45-route set, so the map cannot silently drift when a route is added or removed.

---

## 4. Negative and positive test evidence

`backend/tests/core/test_order09_clinical_route_authorization.py` contains 44 local tests:

| Scenario | Evidence |
|---|---|
| Missing bearer token on representative patient, clinical, care-team, consent, lab, and dashboard routes | 13 parameterized cases expect 401. |
| Invalid/expired token simulation | 3 parameterized cases patch the auth client to raise and expect 401 without any hosted call. |
| Wrong patient / cross-patient read | 9 parameterized cases expect 403/404 and assert the downstream service was not entered. |
| Wrong role or wrong organization | Practitioner in another organization, org admin in another organization, and system administrator cases all deny before service execution. |
| Read role used for clinical write | Patient-role create attempts on encounters, observations, conditions, and medication requests deny before service execution. |
| Forged practitioner id | Four clinical create routes deny a mismatched `practitioner_id` before the service is entered. |
| Omitted practitioner id | Encounter create binds the authenticated practitioner id from the authorization context. |
| Ambiguous clinician organization | `/patients/mine` denies a practitioner with two organizations before the service is entered. |
| Trusted care-team positive case | `/patients/mine` returns only the synthetic patient linked by an active, organization-scoped care-team row. |
| Direct service denial | `get_my_patients()` without a valid context raises 403 and performs no database call. |
| Attributable audit | Care-team create emits actor, action, resource, patient, and organization metadata; `log_audit_event` is patched so no hosted write occurs. |
| Projection/schema guards | Source assertions reject wildcard selects in touched clinical services and require the real lab/reminder columns. |

All fakes are local. Tests patch the module-level `supabase_admin`, the `app.core.audit.service.log_audit_event` function, and the auth client as needed. No patient data, production credential, connection string, token, SQL dump, or Storage object content is used or emitted.

---

## 5. Verification commands and results

All Python commands ran from `backend/` with `.venv/Scripts/python.exe`. Supabase CLI commands used the local stack and did not pass `--remote`.

| ID | Command | Result |
|---|---|---|
| E-09-01 | Order 9 focused suite plus prior focused security suites (`test_order09_clinical_route_authorization.py`, `test_security_phase0_wp02.py`, `test_f5_clinical_authorization_order.py`, `test_security_phase0_wp01.py`, `test_avatar_upload.py`, `test_consent_trusted_path.py`, `test_openapi_security_contract.py`, `test_f4_organization_profile_authorization.py`, `test_practitioner_role_authorization.py`) | **107 passed** |
| E-09-02 | Full backend regression: `pytest -q --tb=short -p no:cacheprovider` | **1,438 passed, 1 skipped, 18 warnings** |
| E-09-03 | `supabase test db` | **3 files, 36 tests, PASS** |
| E-09-04 | `supabase db advisors --type all --level warn` | **No issues found** |
| E-09-05 | OpenAPI generation and contract test | **74 paths / 89 operations / 83 secured / 6 intentionally public**; no `/events` path |
| E-09-06 | `git diff --check --ignore-cr-at-eol` | Clean |
| E-09-07 | Read-only hosted audit check | Only the two previously disclosed synthetic role-audit rows remain; no new row from this order |
| E-09-08 | Read-only hosted migration-history check | Still only `20261118135846`; no migration was applied remotely |

The full-suite count increased from the order 8 record’s 1,394 passing tests by the 44 new order 9 tests.

---

## 6. Hosted read-only recheck

Two read-only MCP SQL queries were run against hosted production:

1. `audit_logs` aggregate for the synthetic test actor, grouped by action. Result: `PRACTITIONER_ROLE_ASSIGNED` = 1 row at `2026-11-23 15:52:31.856152+00`; `PRACTITIONER_ROLE_UPDATED` = 1 row at `2026-11-23 15:52:33.519817+00`. This is unchanged from [order 8 §11](PH0-WP-08-WP-09-privileged-path-review-record.md#11-test-isolation-incident--hosted-production); the owner previously decided to leave both rows in place and document only.
2. `supabase_migrations.schema_migrations` latest ten versions. Result: only `20261118135846`, unchanged. No deployment or migration repair was attempted.

The hosted audit/event grant drift and missing local migrations documented in the order 8 and SPEC-11/SPEC-12 preflight records therefore remain unchanged.

---

## 7. Residual gaps and closure blockers

| Gap | Disposition |
|---|---|
| F-3 anon data-plane operations | Still open. Some touched patient services use the shared publishable client; caller-scoped migration or justified service-role gating remains SPEC-10 work. |
| F-8 post-write audit compensation | Still open. Care-team audit remains after the privileged write; no transactional audit guarantee is claimed. |
| F-9 raw-SQL bootstrap utility | Still open. `scripts/init_db.py` is excluded from this order. |
| Consent/grant lifecycle | Full SPEC-05 purpose, recipient, resource-family, expiry, revocation provenance, and SPEC-06 canonical grants remain open. |
| Records resolve ordering | The minimal condition lookup still precedes authorization; the 404-vs-403 existence residual remains documented. |
| Invite/departments ordering | Order 8 gaps remain open; no policy was guessed. |
| Worker identity and hardened admin routers | No dedicated worker identity evidence; hardened event/audit/metrics routers remain unmounted. |
| Hosted and staging evidence | No hosted staging branch exists; no effective anon/authenticated/service-role or Storage access test was run. Hosted catalog drift remains blocking. |
| Backups, restore, and §8.5 authorization | Database exports, Storage object backup, restore test, owners, deployment window, exact impact, and full approval remain incomplete. |
| SEC / Phase 0 status | No SEC finding is closed by this record. Phase 0 remains **NOT ACCEPTED**. |

---

## 8. Outcome

Order 9’s **local** deliverables are complete: the 45-route map is recorded and asserted in tests, clinical create payloads are bound to the authorized actor, the patient-list path is closed at the service boundary, overbroad projections and invalid schema columns were corrected, and local positive/negative tests pass.

This record does not convert local evidence into hosted proof. Production code/schema are unchanged, nothing was pushed or deployed, no hosted mutation was performed, no SEC finding was closed, and Phase 0 remains **NOT ACCEPTED**.

---

## 9. Cross-references

- [Phase 0 plan — PH0-WP-02 exit criteria and order 9](PHASE-0-BACKEND-SECURITY-BASELINE-AND-REMEDIATION-PLAN-v2.0.md)
- [PH0-WP-02 completion record](PH0-WP-02-completion-record.md)
- [Order 8 audit and privileged-path review](PH0-WP-08-WP-09-privileged-path-review-record.md)
- [SPEC-11/SPEC-12 hosted read-only preflight](SPEC-11-SPEC-12-hosted-read-only-preflight-record.md)
- [Controlled Supabase database and Storage release guide](../../backend/MedAeterna_Controlled_Supabase_Database_and_Storage_Release_Guide_v1.0.md)
- Focused tests: `backend/tests/core/test_order09_clinical_route_authorization.py`
