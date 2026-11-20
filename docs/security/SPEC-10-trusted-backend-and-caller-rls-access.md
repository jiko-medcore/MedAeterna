# SPEC-10: Trusted Backend and Caller-RLS Access

**Status:** Execution modes and an authorization reference gate are defined and tested. Import-time credential logging has been removed, and a per-request caller-scoped client pattern is available. PH0-WP-01 (`security/phase-0-db-storage-release` @ `421d28a`, 20 November 2026, local, unmerged) reinforced trusted-backend authorization in several sensitive/admin routes before privileged operations, but existing query call sites have not yet been migrated to caller-scoped RLS or exhaustively inventoried/authorized; those enforcement gaps remain explicit.

## Decision

Every database operation must select one execution mode before it builds or executes its query:

1. **Caller-scoped RLS** when row visibility or writes are meant to be constrained by the authenticated caller's Postgres identity. Validate the bearer token with Supabase Auth, then use a separate, non-shared client initialized with the publishable key and that exact caller JWT as the PostgREST `Authorization` header. Pass that client only through the request handling the verified caller. Do not assume `auth.get_user(jwt)` changes the identity of a separate PostgREST client.
2. **Trusted service-role backend** for a narrowly justified privileged operation that needs to bypass RLS. The backend must first authenticate the caller and independently authorize the exact action against the authoritative target resource and active scope. The service-role credential grants database capability; it does not represent, authenticate, or authorize the caller. Do not use a client-supplied target identifier as proof of membership or ownership.
3. **Background worker** for work without a live human caller. Authenticate the worker/process, allowlist the job purpose, constrain the target and action, and make human-triggered jobs retain their original actor and authorization decision in protected audit metadata where required.

No mode may be inferred from a URL, client parameter, role name alone, successful authentication alone, or possession of the service-role secret.

## Required evidence by mode

| Mode | Required server-established evidence | Database context | Deny when |
| --- | --- | --- | --- |
| Caller RLS | Token verifies; the same caller token is propagated to PostgREST | Publishable API key plus verified caller JWT; database grants and RLS apply | JWT is absent/unverified or not propagated |
| Service role | Caller verifies; application authorization succeeds; authoritative target scope and requested action both pass | Server-only secret/service key; RLS bypass must be expected | Any evidence is missing, stale, or belongs to a different target/action |
| Background worker | Worker identity verifies; job purpose is allowlisted; target scope and action pass | Server-only worker credential with the narrowest available capability | Worker/purpose/scope/action cannot be established |

`backend/app/core/database_execution_policy.py` implements this as a reference evaluator. It accepts trusted evidence and makes no database calls. The evaluator does not itself establish the truth of its inputs; route/service code must produce those inputs from trusted authorization and resource-resolution logic.

## Credential handling

- `SUPABASE_PUBLISHABLE_KEY` is the API key for server-side caller-RLS clients; the verified caller JWT supplies Postgres caller identity.
- `SUPABASE_SECRET_KEY` is server-only. Never put it in frontend code, API responses, exceptions, telemetry, logs, or test snapshots.
- Do not log either key, any key prefix, access/refresh token, or full database URL. Avoid dumping client options or request headers.
- Avoid caller-specific `set_session`/`set_auth` on a process-wide shared client. Concurrent requests must not be able to replace each other's database identity.
- The existing process-wide service client may be used only for individually authorized privileged operations; its existence does not constitute authorization.

## Caller-scoped client construction

`backend/app/core/supabase_client.py:create_caller_scoped_client(verified_access_token)` creates a new Supabase client with:

- the configured publishable key as the `apiKey`;
- `Authorization: Bearer <verified caller token>` for PostgREST;
- automatic token refresh and session persistence disabled.

Call it only after token verification and use the returned client for one request. Do not cache it globally. The project currently has no general request-scoped database dependency that hands this client to every query service, so existing query modules must not be assumed to gain caller RLS merely because `get_current_user` validates a token.

Supabase documents initialization options for Python clients and explains that RLS applies to API roles and caller identity; the installed `supabase-py` 2.27.1 source confirms explicit initialization headers are used for PostgREST. The security behavior therefore depends on both grants and policies, which SPEC-11 covers. See [Python client initialization](https://supabase.com/docs/reference/python/initializing) and [Supabase Row Level Security](https://supabase.com/docs/guides/database/postgres/row-level-security).

## Current implementation findings

Source review for this SPEC found:

- `get_current_user` verifies a bearer token through `supabase.auth.get_user(token)`. It then resolves active role rows using the service-role client. Token verification is authentication only; it does not propagate caller identity into unrelated shared PostgREST clients.
- `supabase` is a process-wide publishable-key client with no caller-specific Authorization set at initialization. Queries using it do not prove they execute under the incoming caller's JWT/RLS context.
- `supabase_admin` is a process-wide service-role client. Operations through it bypass ordinary RLS and therefore need explicit, target-specific application authorization. This SPEC does not certify each existing call site as authorized.
- `supabase_client.py` and `supabase_admin.py` previously printed the project URL and API-key prefixes at import. Those prints have been removed.
- Existing application queries still include both shared-client patterns. Updating every route/service to use one of the modes, auditing each service-role call site, and proving effective hosted grants/RLS remain implementation work. No database schema or hosted project setting was changed for SPEC-10.

### PH0-WP-01 branch progress (20 November 2026, local, unmerged)

Implemented on `security/phase-0-db-storage-release` @ `421d28a` (not pushed):

- `backend/app/core/security.py` consolidated canonical authz contracts and now performs trusted, resource-derived/fail-closed authorization checks (including org-scoped `get_user_permissions`/`authorize_permission`/`require_permission` resolution and encounter/patient access checks) before allowing privileged data access in migrated paths.
- Sensitive/admin routes touched in this slice (medication-request encounter retrieval, selected clinical reads/writes, records/lab/patient/care-team/consent/dashboard/medical-history paths, and admin event/audit/metrics handling) were migrated to require authenticated, explicit per-operation authorization decisions and fail-closed behavior; admin operational surfaces now avoid returning raw event payload/error details.
- These changes improve application-side gating of privileged/service-role-backed operations in scope but do **not** constitute caller-scoped RLS migration, a complete service-role call-site inventory/justification, or proof of effective grants/RLS/hosted behavior. Call sites continue to rely on shared clients unless explicitly migrated; route/runtime and database verification remain required.

### PH0-WP-02 service-boundary progress (20 November 2026, local, unmerged)

The six clinical modules migrated under PH0-WP-02 now require an authorization context at every migrated service entry point. `ensure_authorized_context()` rejects missing contexts and any action, patient, organization, or resource-id mismatch before a service-role query. Encounter-scoped reads resolve the target from stored encounter data in the FastAPI dependency layer, so a denial occurs before the service function is entered. Care-team mutations also emit attributable audit records.

This satisfies the trusted-backend **application gate** requirement for the selected route/service boundary locally. It does not change the client to caller-scoped RLS, prove effective database grants/RLS, complete a repository-wide service-role call-site inventory, or provide hosted verification. Details and test evidence are in the [PH0-WP-02 completion record](PH0-WP-02-completion-record.md).

## Executable policy and tests

`backend/tests/core/test_database_execution_policy.py` checks:

- caller RLS denies when verification or JWT propagation is missing;
- caller RLS accepts only verified and propagated caller identity;
- service-role access denies if authentication, application authorization, target scope, or action authorization is missing;
- service-role evidence does not substitute for caller RLS context;
- background workers require a verified worker, allowlisted purpose, target scope, and authorized action;
- the installed Supabase client places the provided caller JWT in PostgREST Authorization while retaining the API key, without a persistent or automatically refreshed session;
- empty caller tokens are rejected.

These are unit/reference-policy and SDK wiring tests. They do not prove RLS policies, database grants, route dependency enforcement, or authorization correctness for existing service-role call sites. SPEC-11 and route/service remediation must provide that evidence.

## Acceptance criteria

- [x] Caller-RLS, trusted service-role, and background-worker modes are distinguished with explicit evidence requirements.
- [x] Caller JWT verification and PostgREST JWT propagation are separate, explicit steps; no shared mutable per-user session is used.
- [x] Privileged queries require caller authentication, explicit application authorization, authoritative target scope, and action authorization in the reference gate.
- [x] Worker operations have their own identity and purpose/scope/action gate.
- [x] Secret handling forbids logging/exposing credentials; import-time URL/key-prefix prints are removed.
- [x] Unit tests cover allow and deny paths for each mode and the caller JWT header wiring.
- [x] Existing enforcement gaps and verification limits are recorded without claiming routes or database policies are fixed.
- [x] Focused and neighboring security-policy tests pass and are recorded below.

## Verification record

Focused command: `.venv/Scripts/python.exe -m pytest tests/core/test_database_execution_policy.py -q --tb=short -p no:cacheprovider` (run from `backend/`). Result: **17 passed**.

Security-policy regression command: `.venv/Scripts/python.exe -m pytest tests/core/test_database_execution_policy.py tests/core/test_action_authorization.py tests/core/test_role_catalogue.py tests/core/test_system_admin_patient_access.py tests/core/test_organization_admin_patient_access.py tests/core/test_patient_relationship_policy.py tests/core/test_consent_policy.py tests/core/test_patient_access_grants_schema.py tests/core/test_operational_event_policy.py tests/core/test_event_logging.py -q --tb=short -p no:cacheprovider` (run from `backend/`). Result: **390 passed**.

The focused SDK wiring test was run with installed `supabase-py` 2.27.1 and requires no live database. It passed. No database or hosted Supabase credentials were used for this SPEC. Deprecation warnings originate from installed dependencies and the SDK's deprecated PostgREST constructor arguments.
