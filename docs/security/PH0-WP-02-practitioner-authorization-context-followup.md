# PH0-WP-02 Follow-up — Practitioner Authorization and Service Context Contract

**Workstream:** PH0-WP-02 follow-up  
**Branch:** `security/ph0-wp02-practitioner-context-contract`  
**Starting commit:** `bd1b6893157acb12e59d57c0c8b4f0d07a4ee2b6` (PR #47 head)  
**Base dependency:** PR #47, `security: integrate authoritative patient treatment relationships`  
**Status:** **KICKED OFF — implementation and verification pending**  
**Environment:** Repository/local code only. No database, Storage, deployment, or production operation is in scope.

> This branch is intentionally stacked on PR #47 because the authoritative `patient_care_team` treatment relationship and token-classification changes are not yet merged. It must not be retargeted to `main` or merged independently of that dependency. PR #47 remains open and unmerged at the time of this record.

## 1. Objective

Complete the next application-authorization slice without broadening clinical access:

1. Consolidate practitioner identity, organization-scope, and actor-binding decisions behind one shared authorization contract.
2. Make the service-layer authorization-context contract consistent across sensitive clinical services, including direct-call denial before privileged queries or writes.
3. Preserve the separation between treatment relationship, role/action authorization, workflow, and consent.
4. Keep SPEC-05 consent evaluation fail-closed until a trusted, purpose/resource/recipient-aware evaluator is implemented from the approved policy.
5. Keep SPEC-06 patient-approved read grants separate; do not query or infer the existence of a deployed grant table as part of this work.

## 2. Confirmed starting-point observations

The following are repository observations at the starting commit, not acceptance claims:

- `backend/app/core/clinical_authorization.py` already provides `practitioner_actor_id()`, `practitioner_organization_id()`, `authorize_patient_list_access()`, `authorize_practitioner_schedule_access()`, and `ensure_authorized_context()`.
- Practitioner schedule routing still combines the shared actor resolver with a second `security.require_practitioner` dependency. The route separately derives an organization from `organization_ids`; this is a candidate for consolidation into the shared role-scope contract.
- `ensure_authorized_context()` currently checks resource/action and optional patient/organization/resource identifiers, but accepts a fallback user id from the unqualified context `id`. The follow-up must decide and test a stricter, explicit context shape rather than silently accepting partially populated contexts.
- The PH0-WP-02 completion record describes six migrated routers and context checks in their services, but its own exclusions include practitioner-role administration, consent routes, and other protected surfaces.
- Current `patients/router.py` contains patient self-service routes that still call services without the shared `authorized_context` contract. These require route-by-route classification; not every profile operation is a clinical-record operation, so the follow-up must not indiscriminately impose a clinical context on unrelated self-profile workflows.
- Current `records/service.py` retains a legacy medical-record path using `require_patient_access` and service functions without the newer `authorized_context` parameter. Its callers and resource semantics must be mapped before migration.
- The service-context contract must not treat the presence of a treatment relationship as proof that consent was evaluated.

## 3. Required implementation sequence

### A. Practitioner authorization consolidation

- Inventory every practitioner-specific dependency, identity lookup, organization selection, actor binding, schedule/list path, and clinical write path.
- Make authenticated user → practitioner profile resolution single-sourced and fail closed on missing or ambiguous `practitioners.profile_id` links.
- Derive permissible organization scopes from active, validated practitioner role assignments; a client-selected organization may select among those scopes but must not create one.
- Bind practitioner IDs on writes from the verified actor context; reject forged or mismatched client values.
- Remove duplicate lookups/dependencies only after equivalent scope and denial behavior is covered by tests.

### B. Service authorization-context contract

- Inventory all sensitive routes and service functions that read or mutate patient, encounter, appointment, care-team, clinical-record, medication, observation, condition, laboratory, prescription, consent, or patient-list data.
- Classify each service operation by resource family, action, patient scope, organization scope, and resource identifier.
- Require a complete explicit authorization context for sensitive service operations; validate every applicable scope before any service-role query or mutation.
- Resolve stored resource context before authorization for ID-based operations. Do not accept request-body patient/practitioner/organization values as relationship evidence.
- Keep non-clinical patient profile/self-service workflows separately classified and document why they do or do not require this contract.
- Add direct-service tests proving missing, wrong-user, wrong-resource, wrong-action, wrong-patient, wrong-organization, and wrong-resource-id contexts fail before data access.

### C. Consent boundary

- Do not add `consent_if_required` to verified conditions as a shortcut.
- Do not let `patient_care_team`, practitioner role, organization membership, patient self-identity, or a patient read grant imply consent.
- Do not implement consent scope from undocumented fields or guess purpose/recipient semantics.
- If SPEC-05 is not fully implementable from the approved specification and current trusted schema, leave practitioner clinical actions fail-closed and record the exact missing policy/schema decisions.
- Keep SPEC-06 patient-approved grants separate from treatment assignments and consent.

## 4. Acceptance criteria

- [ ] One authoritative practitioner actor resolver is used by all migrated practitioner-sensitive routes and services.
- [ ] Organization selection is validated against the actor's active practitioner role scopes; ambiguous or absent scope denies.
- [ ] Client-supplied practitioner identifiers cannot override the verified actor.
- [ ] Every in-scope sensitive service operation validates a complete explicit authorization context before privileged data access.
- [ ] Direct service calls without context, or with mismatched actor/resource/action/patient/organization/resource ID, deny before queries or writes.
- [ ] Each route is classified as clinical, administrative, or patient self-service; no blanket widening or accidental breakage of profile workflows.
- [ ] Consent remains an independent gate. No treatment relationship is represented as consent evaluation.
- [ ] SPEC-06 patient read grants remain separate and are not assumed installed or integrated.
- [ ] Focused tests and the full backend suite pass on the exact branch head.
- [ ] Documentation records exact changed surfaces, exclusions, tests, and residual limitations.

## 5. Explicit non-goals and stop controls

- No production or hosted Supabase reads/writes, migrations, Storage mutations, configuration changes, or deployment.
- No SEC finding closure or risk acceptance.
- No Phase 0 acceptance or Gate G claim.
- No consent-policy shortcuts, emergency/break-glass access, legacy relationship fallback, or inferred grant semantics.
- No merge of PR #47 or this follow-up without explicit merge authorization.

## 6. Initial verification baseline

The dependency PR #47 head `bd1b6893157acb12e59d57c0c8b4f0d07a4ee2b6` has GitHub Actions run `45688886287` — **SUCCESS** (1,495 passed, 1 skipped, 6 warnings; compile step passed). This is the baseline for the dependency commit only; it is not verification of this follow-up branch.

## 7. Next execution step

Complete the route/service inventory and focused design review before broad edits. The first implementation change should consolidate the duplicate practitioner schedule resolution and strengthen the explicit context validator, with regression tests, before migrating additional service families.


## 8. First-pass route/service inventory (25 November 2026)

A first-pass source inspection was completed against the stacked branch. This is an inventory for implementation planning, not a claim that all routes have been runtime-verified.

| Service family | Current service-boundary evidence | Follow-up disposition |
|---|---|---|
| Encounters | `ensure_authorized_context()` on create/read/update. Create binds patient and organization; patient list binds patient; update binds resource id. | Review organization/resource linkage on read/update and keep direct-call tests. |
| Observations | Context checks on create, patient read, encounter read, update. Encounter read/update use resource id; create binds patient/org. | Review patient/org binding for ID-based operations and stored encounter linkage. |
| Conditions | Context checks on create, patient read, encounter read, update. | Review patient/org binding for ID-based operations and stored encounter linkage. |
| Medication requests | Context checks on create, patient read, encounter read, update. | Review patient/org binding for ID-based operations and stored encounter linkage. |
| Appointments | Context checks on create, patient read, practitioner schedule read, update. | Practitioner schedule was missing an organization filter in its service query; the initial slice now requires explicit authorized organization context and filters by that exact organization. |
| Care teams | Context checks on create, participant add/update, patient read, assignment. | Review participant and care-team parent linkage before finalizing the common contract. |
| Patient list | `get_my_patients()` requires a `PATIENT_LIST/read` context and then filters active `patient_care_team` rows by practitioner and organization. | Retain as a distinct organization-scoped list operation; ensure actor/org fields remain mandatory. |
| Patient self-service and profile | Several patient service operations are still invoked without the shared context contract. | Classify each route by resource/action; do not automatically treat all profile operations as clinical history. |
| Legacy medical records | `records/service.py` exposes create/fetch paths without `authorized_context`; condition resolution uses the older `require_patient_access` pattern. | Migrate only after mapping every caller and distinguishing the legacy `medical_records` resource from the newer clinical tables. |
| Laboratory | `laboratory/service.py` performs a minimal scope lookup and then uses `require_patient_access`; it does not use the explicit service context contract. | Map lab order/specimen relationship requirements before migration; a general treatment assignment alone is insufficient for lab writes under SPEC-04. |
| Consents | Consent service operations use actor provenance but do not use the shared clinical context contract. | Keep separate from this generic migration; implement only under the approved SPEC-05 policy and consent-specific actor/subject authorization. |
| Prescriptions and reminders | Service functions exist without the shared context contract. | Inspect their route callers and classify sensitivity/action before deciding whether they are in scope. |

### 8.1 Initial implementation delivered on this branch

- `practitioner_organization_ids()` and `resolve_practitioner_organization_id()` now derive permissible organizations from the authenticated practitioner's canonical role assignments. An explicit organization parameter can select only an existing role scope; `organization_ids` alone cannot create scope.
- The practitioner appointment schedule route no longer invokes a second practitioner dependency lookup. It passes the requested practitioner id to the shared schedule authorization helper, which resolves and compares the authenticated actor.
- `ensure_authorized_context()` now requires explicit `authorized_user_id`; the ordinary context `id` is no longer accepted as a fallback authorization binding.
- `get_practitioner_appointments()` now requires an explicit authorized organization and adds an exact `organization_id` filter to its service-role query. This closes the observed risk that a practitioner with multiple organization assignments could receive schedule rows across those organizations.
- Focused tests cover organization-scope selection, mismatch/ambiguity denial, actor binding, explicit context requirements, and schedule query organization isolation.

### 8.2 Verification constraint

The repository workflow `.github/workflows/backend-ci.yml` is configured for `pull_request.branches: [main]` and `push.branches: [main]`. Because this PR is deliberately stacked on PR #47's feature branch, GitHub Actions does not automatically run the configured Backend CI workflow for PR #48 at this stage. No successful test run is claimed for this follow-up commit. Once PR #47 is merged and this PR is retargeted to `main` with the dependency resolved, the exact resulting head must receive a successful Backend verification run before review/merge.

The initial slice is not complete acceptance of the workstream. The remaining service families above require route/caller mapping, implementation, and negative direct-call tests.
