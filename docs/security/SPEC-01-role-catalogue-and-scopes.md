# SPEC-01: Role Catalogue and Scopes

**Status:** Implemented as the Phase 0 role classification baseline. This specification classifies assignments into the four authorization categories; it does not define the resource/action authorization matrix.

**Order 5 approval (21 November 2026):** Approved for implementation by the designated MedAeterna technical/security owner for the documented decisions only; not production acceptance. Undocumented choices remain fail-closed. See [PH0-WP-06 policy approval record](PH0-WP-06-SPEC-approval-and-consent-access-model.md).

## Reconciliation of plan versions

The original plan's four personas, contextual authorization model, modular-monolith constraint, deny-by-default rule, and resource/organization boundaries remain in force. Version 2 clarifies that the original authorization matrix is only partially specified: broad system-administrator entries are conditional on explicit platform purpose and must not imply clinical-care access; organization-administrator clinical access and operational visibility also remain conditional or pending. Accordingly, a role category in this SPEC-01 catalogue identifies the kind of assignment only. It does not turn the original matrix's `authorized` wording into blanket permission, nor resolve the decisions that v2 lists as SPEC-02 through SPEC-12. Pending rules remain denied.

## Principles

- A role assignment is the pair of a role and its scope. A role name alone grants no authority.
- System assignments have `role_type = system` and no organization ID on either the role or assignment.
- Organization assignments have `role_type = organization`; the role's organization ID and the assignment's organization ID must both be present and equal.
- Organization authority applies only when that ID matches the organization associated with the requested resource.
- Unknown names, missing scope, and scope/name mismatches classify as `unmapped` and grant no category authority.
- A role definition must be active (`roles.is_active = true`) before it can be classified. The current `user_roles` schema has no assignment status; SPEC-02 must define revocation/expiry and the enforceable active-assignment representation.
- A user can hold multiple assignments. Authorization evaluates the applicable assignment; there is no selected primary role and no cross-scope privilege inheritance.
- Classification is not permission. Every operation still requires the action-level rule and resource relationship checks specified in later SPECs.

## Catalogue

| Stored role name | Required stored scope | Authorization category | Boundary |
|---|---|---|---|
| `patient` | System, no organization | Patient | Identity category only; patient clinical access remains limited to the caller's own records and later resource rules. |
| `practitioner` | Organization, matching organization ID | Practitioner | Applies only in that organization. |
| `doctor`, `clinician`, `nurse`, `laboratory scientist`, `lab-tech` | Organization, matching organization ID | Practitioner | Legacy profession labels normalize to the practitioner category; they do not imply equal clinical permissions. SPEC-03 must define operation-specific permissions. |
| `org_admin` | Organization, matching organization ID | Organization administrator | Administration is limited to that organization. |
| `admin` | None accepted pending inventory | Unmapped | Ambiguous legacy label. Do not infer system or organization authority from this name or from a permission row. Inventory existing role definitions and assignments, then migrate intentionally to `org_admin` or `super_admin` through the separately authorized, audited role-management process. |
| `super_admin` | System, no organization | System administrator | Category is platform-scoped; it does not itself grant access to patient clinical data or bypass resource-specific rules. Sensitive system operations require audit. |
| Other names, including `staff` until specified | No accepted mapping | Unmapped | Deny by default; do not infer a category from a permission row or display label. |

## Scope mismatch behavior

- `patient` assigned to an organization, or `super_admin` assigned to an organization: unmapped.
- `practitioner`, `doctor`, `clinician`, `nurse`, `laboratory scientist`, `lab-tech`, or `org_admin` assigned globally: unmapped.
- `admin` at any scope: unmapped until its legacy assignments are inventoried and migrated.
- Missing/unknown `role_type`, or mismatch between the role definition's organization and the user's assignment: unmapped.
- Organization assignment for Organization A cannot authorize a request for Organization B.
- A system-administrator category is not a universal clinical-care relationship.

## Implementation

- `backend/app/core/role_catalogue.py` contains the canonical name/scope map and scoped-category predicate. The ambiguous legacy `admin` role intentionally has no mapping.
- `get_current_user` returns all assignments with a normalized `category`. Only active role definitions can be classified. It no longer selects the first assignment as the user's primary role. The legacy scalar `role` is populated only when there is exactly one assignment and it is recognized; authorization code must use `roles` and the requested scope.
- Organization-admin checks use the requested organization's ID and require an `organization_administrator` assignment for that exact organization.
- `is_admin` now means system administrator only. `is_org_admin` is separately exposed for the presence of any organization-admin assignment; it must not be used as a substitute for an organization-specific check.

## Focused verification

The focused authorization checks passed:

- `python -m pytest tests/core/test_role_catalogue.py -q` — 19 passed. Covers valid category/scope mappings, inactive role definitions, ambiguous `admin`, wrong or missing scope, role-definition/assignment organization mismatch, exact organization matching, and system-admin separation from organization-admin access.
- `python -m pytest tests/organizations/test_dependencies.py -q -p no:cacheprovider` — 9 passed. Confirms existing organization membership behavior remains intact after the admin guard change.

These are unit-level authorization checks; they do not verify live Supabase grants/RLS or assignment revocation. Assignment lifecycle remains SPEC-02.

## Deferred decisions

SPEC-01 does not settle assignment active/revoked status, role assignment lifecycle, who may delegate each role, dual approval, database constraints, or action-level privileges. The backend can currently check whether the referenced role definition is active, but cannot establish whether a `user_roles` assignment itself is active because the schema has no status field. Those remaining decisions are SPEC-02/03 and must be addressed before role writes or permission-matrix work is considered complete. Existing `admin` role rows should be inventoried before migration; malformed and ambiguous assignments currently remain visible as `unmapped` and must not be repaired automatically. Because this change stops treating `admin` as an organization-administrator alias, affected legacy assignments may lose organization-admin access until their data is reviewed and deliberately migrated.
