# PH0-WP-01 — Canonical Authorization Decision Record

**Status:** Decision baseline established for the first local implementation slice  
**Repository baseline:** `main` at `39a8fbf384ba674507afe1bedd8fe9e38c808da2`  
**Implementation branch:** `security/ph0-wp01-auth-org-foundation`  
**Scope:** Local source and test changes only. No production database, Storage, configuration, or deployment operation is authorized by this record.

This record settles the four architectural decisions required before the remaining patient, practitioner, and clinical route remediation. It is based on the approved SPEC-01, SPEC-02, SPEC-03, and SPEC-10 policy documents and the current source inspection.

## Decision 1 — Organization membership

**Decision:** For the current MVP, an active, recognized, correctly scoped organization role assignment is the interim authoritative evidence of membership. A separate membership table is not introduced in this slice.

Membership is distinct from organization-administrator authority:

- A recognized active `practitioner`-category assignment in organization A establishes membership in organization A only.
- A recognized active `organization_administrator` assignment in organization A establishes membership in organization A and separately establishes administrator authority in organization A.
- System roles, patient roles, unmapped roles, inactive assignments, inactive role definitions, malformed scopes, and assignments for another organization do not establish membership.
- Membership does not itself grant access to organization configuration.
- Under SPEC-03, organization configuration read/write is restricted to an organization administrator for the exact organization unless a separate organization-read rule is explicitly approved.
- A user with multiple organization assignments must provide or resolve the exact organization context. A self-scoped route without an organization identifier must fail closed unless exactly one qualifying organization-admin assignment exists.

**Rationale:** The current schema and approved SPEC-01/02 role lifecycle already provide an active assignment with exact organization scope. No authoritative standalone membership relation is currently defined. Introducing one now would require a new data model and migration decision. The interim rule is therefore explicit, narrow, and replaceable without conflating membership with administrative authority.

**Future requirement:** If the product needs membership independent of practitioner or administrator roles, introduce a dedicated membership model through a separately reviewed schema and lifecycle decision. Do not infer it from profile existence or client-provided organization IDs.

## Decision 2 — Canonical patient relationship evaluator

**Decision:** `app.core.patient_relationship_policy.evaluate_patient_relationship()` is the canonical pure policy evaluator for patient/practitioner relationship evidence.

`app.core.security.authorize_patient_access()` remains the trusted data-loading and orchestration boundary. It must resolve the patient and organization from stored data, resolve the practitioner identity, load relationship and consent evidence from trusted sources, and delegate the decision to the canonical policy evaluator. It must not maintain a second independent set of relationship rules.

The policy evaluator must remain pure: it evaluates supplied evidence and makes no database calls. The adapter is responsible for establishing that evidence. Missing, stale, malformed, cross-organization, or unverified evidence denies access.

**Scope note:** This decision is settled now, but patient authorization code is not changed in the first implementation slice. It will be implemented after authentication and organization scope are stable, with SPEC-04/05/06 reconciliation and route/service tests.

## Decision 3 — Canonical practitioner dependency

**Decision:** `app.core.security.require_practitioner` is the single canonical practitioner identity/role dependency.

The module-local `app.modules.practitioners.dependencies.require_practitioner` must not evolve as a separate authorization implementation. Because the current static call-site inspection found no production callers of the module-local implementation, it should be removed after a final repository-wide reference check, or temporarily retained only as a thin compatibility wrapper delegating to the core implementation. It must not have weaker or different role/profile semantics.

Practitioner organization authority remains a separate exact-organization check. A practitioner profile alone is not organization membership or permission to access another organization's resources.

**Scope note:** Practitioner dependency consolidation is deferred until the first authentication/organization slice is verified.

## Decision 4 — Sensitive service authorization context

**Decision:** Every sensitive clinical service entry point must require a server-created, verified authorization context and validate its action, patient, organization, and resource scope before privileged data access or mutation.

Route-level authorization remains mandatory but is not sufficient on its own. A service must reject a missing or mismatched context even when invoked directly by another route, task, or internal caller.

The context must be created by trusted authorization code after resolving target resources and relationships from authoritative data. It must never be constructed from request payload claims or caller-supplied booleans.

A non-human background worker is not exempt: it requires a separately defined worker identity, allowlisted purpose, target scope, and action context. No generic service-role bypass is implied.

**Scope note:** Apply this contract to the sensitive service inventory in a later slice. Existing PH0-WP-02 coverage is retained; no patient/practitioner/clinical service is modified in this first slice.

## First implementation slice — authentication and organization boundaries

The first implementation slice on `security/ph0-wp01-auth-org-foundation` is limited to:

1. `get_current_user()`
   - Verify the supplied bearer token through Supabase Auth.
   - Return 401 only for recognized invalid/expired/missing-user credentials.
   - Return a controlled 503 when Auth infrastructure or trusted role-resolution infrastructure cannot establish identity/authorization state.
   - Load only active role assignments and active role definitions.
   - Preserve unmapped assignments for diagnostics, but require at least one recognized SPEC-01 category before returning an authenticated application context.
   - Derive `organization_ids` only from valid, active practitioner or organization-administrator assignments.
   - Preserve the existing response fields for compatibility; authorization decisions must use normalized `roles` and exact scope, not scalar booleans.

2. Organization membership and authority
   - Check membership/authority from the verified authorization context before any privileged organization-row lookup.
   - Check organization-administrator authority against the exact requested organization before any privileged organization-row lookup.
   - Keep membership and administrator checks as separate predicates.
   - Make organization-configuration read dependencies consistent with SPEC-03.
   - Resolve self-scoped organization configuration routes from exactly one trusted organization-admin assignment; deny zero or multiple matches.
   - Remove or retire the unsafe single-row `get_user_organization_id(user_id)` lookup and its shared publishable-client use.
   - Add the missing organization gate to department list/get routes.

3. Tests
   - Add direct tests for successful and denied `get_current_user()` role resolution, invalid credentials, infrastructure failures, all-unmapped assignments, inactive role definitions, and multiple organization assignments.
   - Add tests proving unauthorized membership/admin checks happen before `get_organization()` is called.
   - Add route tests for self-scoped organization configuration and department reads.

## Explicit exclusions

- No patient relationship implementation in this slice.
- No practitioner dependency consolidation in this slice.
- No service-wide authorization-context migration in this slice.
- No database schema or migration changes.
- No production Supabase, Storage, or deployment operations.
- No SEC finding or issue closure.
- No Phase 0 acceptance claim.

## Acceptance evidence required

- Focused authentication and organization dependency tests pass.
- Existing organization/profile/department/branding/healthcare-service/operating-hours tests pass or are deliberately updated to the approved policy.
- Full backend test suite passes.
- OpenAPI security contract remains valid.
- Diff review confirms no unrelated route or service changes.
- A separate independent human review is still required before merge; the current owner aliases are not independent reviewers.
