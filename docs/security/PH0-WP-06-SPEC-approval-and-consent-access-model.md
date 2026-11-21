# PH0-WP-06 Policy Approval Record — SPEC-01–SPEC-10 and Consent/Access Model

**Work package:** PH0-WP-06 / backend plan execution order 5  
**Exit condition:** `No policy guessing`  
**Branch:** `security/phase-0-db-storage-release`  
**Review date:** 21 November 2026  
**Policy approval:** Approved for implementation by the designated MedAeterna technical/security owner for the decisions already written in SPEC-01–SPEC-10.  
**Status:** **Policy/design approved for documented decisions — NOT IMPLEMENTED, NOT ACCEPTED, NOT PRODUCTION-APPROVED**

> This record completes the policy/approval portion of execution order 5. It does not create a database migration, change application query paths, deploy anything, or claim Phase 0 acceptance. Undocumented decisions remain denied by default. Local remediation is not production remediation.

---

## 1. Scope and control basis

Backend plan execution order 5 requires: `Approve SPEC-01–SPEC-10 and complete consent/access model`, with exit condition `No policy guessing`. The governing rule is: unresolved policy choices must not be silently guessed; deny by default.

The release guide's Gate A requires a traceable requirement, an approved security policy with named actors, explicit operations and boundaries, default-deny behavior, documented scope and expected behavior, risk/recovery review, and approval by the designated MedAeterna technical/security owner. The user issuing this work order confirmed they are that owner and approved the documented decisions in SPEC-01–SPEC-10. Implementation approval and production deployment approval remain separate; no production approval is recorded here.

The documentation plan's immediate order 6 — implementing patient-access grants and the consent schema/lifecycle — remains implementation work and is not claimed by this record.

Supabase guidance and the local Supabase/Postgres skills were used. The Supabase changelog was reviewed on 21 November 2026. The relevant current breaking changes are CLI v3 being local by default and Data API exposure no longer being automatic; neither blocks this documentation-only policy order. No Supabase feature change was implemented in this order.

---

## 2. Gate A result for documented policies

| Gate A item | Result |
|---|---|
| Traceable requirement | Pass — backend plan order 5, PH0-WP-06, SPEC-01–SPEC-10 and the two baseline plans identify the policies and findings. |
| Intended actors named | Pass — anon, authenticated, patient, practitioner, organization administrator, system administrator, worker, service role and caller-RLS modes are named in the SPEC documents. |
| Allowed operations explicit | Pass — SPEC-03 defines six actions over fourteen resource families; SPEC-09 separates read and retry; SPEC-10 defines execution modes. |
| Organization, patient, owner, resource and purpose boundaries explicit | Pass for documented decisions — SPEC-04, SPEC-05, SPEC-07 and SPEC-08 define the boundaries; unspecified mappings remain denied. |
| Deny by default | Pass — no missing policy is inferred. All unresolved items in section 5 are fail-closed. |
| Scope and expected behavior documented | Pass — each SPEC records its decision, acceptance criteria, verification boundary and deferred work. |
| Risk and recovery approach reviewed | Pass for this order — no schema, route, data or deployment change was made. Production risk is unchanged. |
| Owner approval | Pass — recorded approval by the designated MedAeterna technical/security owner for documented decisions only. |
| Production deployment approval | Not granted — no `--remote` operation, migration, deployment or hosted verification was performed. |

---

## 3. Approved policy decisions by SPEC

| SPEC | Approved for implementation | Remaining fail-closed decisions |
|---|---|---|
| SPEC-01 | Four-category role classification; deterministic scoped resolution from all active assignments; no first-role selection; system-admin and org-admin separation. | Legacy `admin` mapping, malformed-assignment repair, dual approval and action privileges are not inferred. |
| SPEC-02 | Role assignment lifecycle, active/revoked states, no self-assignment, delegated assignment matrix, trusted role-change path and local least-privilege follow-up. | Dual approver, hosted effective privileges and production concurrency evidence remain open. |
| SPEC-03 | Six actions / fourteen resource-family action matrix with fail-closed evaluator; consent remains a separate gate. | Full route adoption and runtime consent integration are not assumed from the reference evaluator. |
| SPEC-04 | Active treatment assignment or explicitly scoped patient grant for reads; treatment assignment required for create/update; lab writes require exact order/specimen evidence; grants never replace consent. | No canonical treatment-assignment table is selected; incompatible relationship sources are not silently reconciled. |
| SPEC-05 | Consent-required decisions must come from a trusted identified policy; one record must match patient, organization, recipient, resource family, canonical purpose, consent type, action, authority and lifecycle; finite expiry and immediate revocation; latest decision wins. | No purpose code, requirement-policy identifier, recipient-kind storage, resource-scope storage or grant/revoke provenance is invented. Runtime enforcement remains deferred. |
| SPEC-06 | `public.patient_access_grants` is the sole canonical explicit patient-approved grant table; `patient_access` is rejected as an authorization source; grants are read-only, explicitly scoped and lifecycle-bound; no `assigned` or `emergency` grant. | Migration, cutover, legacy-row promotion and canonical treatment-source selection remain open. No migration was created or applied by this order. |
| SPEC-07 | Organization-admin patient access is limited to explicit administrative data/purpose; clinical/sensitive fields, broad profiles, FHIR/timeline access and post-query filtering are denied. | Logical field-to-column mapping, route/view enforcement and hosted role evidence remain open. |
| SPEC-08 | System-administrator patient clinical access and break-glass are prohibited in current Phase 0. | Any future emergency workflow requires a separate approved specification. |
| SPEC-09 | Event visibility and retry are separate; system-admin purposes, redaction, audit-before-access, state limits, single-event replay and retry-safety gating are approved. | Org-admin event visibility needs a trusted resolver; retry allowlist remains empty; transactional replay, hosted audit and mounted-route evidence remain open. |
| SPEC-10 | Three explicit execution modes; service-role use requires caller verification, application authorization, target-scope verification and action authorization; caller-scoped client requires caller JWT propagation. | No query site is assumed to be caller-RLS merely because a client pattern exists; full call-site migration and hosted proof remain open. |

---

## 4. Completed consent/access policy model

The approved model is conjunctive, not substitutive. Every sensitive clinical decision must separately satisfy applicable role/action authority (SPEC-03), patient relationship evidence (SPEC-04), consent (SPEC-05), organization/system boundary (SPEC-07/08), and the selected database execution mode (SPEC-10). A grant, care-team row, consent row or role assignment does not by itself authorize an action that another gate denies.

### 4.1 Canonical explicit patient grants

- `public.patient_access_grants` is the only approved table for explicit patient-approved practitioner grants.
- Approved grants are read-only, patient/practitioner/organization/resource-scoped, time-bounded, attributable to grantor and revoker, and terminal on revocation or expiry.
- `patient_access`, `assigned`, `emergency`, nullable/global scope and ambiguous legacy rows are not authorization sources.
- Treatment relationships remain separate evidence under SPEC-04; no treatment table is canonically selected by this order.

### 4.2 Consent

- Consent is required only when a trusted, identified policy says it is required for the exact resource family, action, purpose and context. Unknown or missing requirement decisions deny.
- One consent record must cover the whole request. Separate rows cannot be combined.
- Exact patient, organization, recipient, resource family, canonical purpose, allowed consent type and action level must match.
- Only active, unrevoked, effective, finite-expiry decisions authorize. Latest decision wins; ties and ambiguous evidence deny.
- Emergency consent does not authorize access under the current SPEC-08 prohibition.
- Existing storage and routes do not yet provide the trusted recipient-kind, resource-scope and authority evidence required by this model; therefore they are not treated as enforcing SPEC-05.

### 4.3 Default-deny rules

- No role, action, purpose, recipient, resource scope, organization or relationship is inferred from missing or malformed data.
- No patient or clinical access is granted by a SOCIAL/historical labeling convention, by an unmapped legacy role, or by an unapproved emergency flag.
- No client INSERT/UPDATE path is assumed to enforce the grant or consent lifecycle.
- No service-role query is treated as caller-RLS.
- No legacy row is auto-promoted to canonical grant or consent status.

---

## 5. Explicit “No policy guessing” inventory

These items are intentionally not decided by this record. They remain denied or deferred until a separate approved decision and implementation evidence exist:

1. Legacy `admin` category mapping and repair of malformed role assignments.
2. Dual approver for high-impact role delegation.
3. Canonical active-treatment/care-team assignment table.
4. Consent-required policy identifiers, canonical purpose codes and recipient-kind storage.
5. Consent resource-family storage and trusted grant/revoke provenance in the current table/API.
6. Canonical patient-grant migration, legacy reconciliation and application cutover.
7. Organization-admin field-to-column mapping and route/view implementation.
8. Trusted event-to-organization resolver and manual-retry handler allowlist.
9. Caller-scoped RLS migration and exhaustive service-role call-site authorization.
10. Hosted/staging RLS, grants, Storage effective access and persistent audit evidence.
11. Public patient-avatar retrieval decision and creation of the private `patient-documents` bucket.
12. Production deployment of any local remediation.

---

## 6. Verification evidence

All evidence below is local unless explicitly stated otherwise. No hosted project was mutated.

| Evidence ID | Check | Command / source | Result |
|---|---|---|---|
| E-WP06-01 | Supabase changelog review | `https://supabase.com/changelog.md` | Reviewed 21 Nov 2026; no breaking change blocks this documentation-only order. |
| E-WP06-02 | Supabase CLI | `supabase --version` | **3.2.0** |
| E-WP06-03 | Local database pgTAP | `supabase test db` from `backend/` | **PASS — 3 files, 28 tests** |
| E-WP06-04 | Local migration history | `supabase migration list` | Five local migrations match local history. |
| E-WP06-05 | Full backend regression | `.venv/Scripts/python.exe -m pytest -q --tb=no -p no:cacheprovider` | **1,334 passed, 1 skipped, 18 warnings** |
| E-WP06-06 | SPEC-01–SPEC-10 focused regression | `.venv/Scripts/python.exe -m pytest tests/core/test_role_catalogue.py tests/core/test_action_authorization.py tests/core/test_patient_relationship_policy.py tests/core/test_consent_policy.py tests/core/test_patient_access_grants_schema.py tests/core/test_organization_admin_patient_access.py tests/core/test_system_admin_patient_access.py tests/core/test_database_execution_policy.py tests/core/test_operational_event_policy.py tests/api/admin/test_spec09_event_authorization.py -q --tb=short -p no:cacheprovider` | **422 passed** |
| E-WP06-07 | Patch sanity | `git diff --check` | Clean at commit time. |

The focused suite covers role catalogue, action authorization, patient relationships, consent evaluation, canonical grant reference model, organization-admin boundary, system-admin prohibition, database execution policy, operational events and hardened admin event routes. These are local implementation/reference tests; they do not prove hosted behavior, deployed RLS, persistent audit durability, or production acceptance.

---

## 7. Open implementation work

This record approves the model; it does not complete PH0-WP-06 implementation acceptance. The following remain required before that acceptance can be claimed:

- create and test the canonical `patient_access_grants` migration and append-only audit storage;
- add trusted, validated recipient/resource scope and non-null lifecycle/authority requirements for consent;
- secure grant/revoke/list routes and prevent direct authenticated writes from bypassing validation;
- integrate deterministic consent evaluation with SPEC-03, SPEC-04 and the approved resource workflow;
- migrate or explicitly contain privileged/caller-RLS query paths under SPEC-10;
- add route, pgTAP and hosted effective-access evidence;
- reconcile SEC findings only against evidence-backed dispositions.

---

## 8. Decision

**Order 5 exit condition:** met for policy/design approval of documented decisions; all undocumented decisions are explicitly fail-closed.  
**PH0-WP-06 implementation acceptance:** not claimed.  
**Phase 0 acceptance:** **NOT ACCEPTED**.  
**Production deployment:** not approved; no hosted change was made.

---

## 9. Cross-references

- [Backend plan — execution order 5](../backend/MedAeterna_Phase_0_Backend_Security_Baseline_and_Remediation_Plan_v2.0.md)
- [Baseline plan — policy specifications and acceptance criteria](PHASE-0-BACKEND-SECURITY-BASELINE-AND-REMEDIATION-PLAN-v2.0.md)
- [Release guide — Gate A and production gates](../backend/MedAeterna_Controlled_Supabase_Database_and_Storage_Release_Guide_v1.0.md)
- [SPEC-01](SPEC-01-role-catalogue-and-scopes.md), [SPEC-02](SPEC-02-role-assignment-lifecycle-and-delegation.md), [SPEC-03](SPEC-03-action-level-authorization-matrix.md), [SPEC-04](SPEC-04-patient-relationship-access-policy.md), [SPEC-05](SPEC-05-consent-evaluation-policy.md), [SPEC-06](SPEC-06-canonical-patient-access-grants.md), [SPEC-07](SPEC-07-organization-admin-patient-data-boundary.md), [SPEC-08](SPEC-08-system-admin-patient-data-and-break-glass.md), [SPEC-09](SPEC-09-operational-event-visibility-and-retry.md), [SPEC-10](SPEC-10-trusted-backend-and-caller-rls-access.md)
