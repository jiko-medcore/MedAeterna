# Supabase database tests

These pgTAP tests cover the SPEC-02 role-assignment lifecycle migration. Run them against a **local** Supabase stack built from the checked-in schema baseline and migrations; they are designed to roll back their fixture data.

From the `backend` directory, with the Supabase CLI and Docker runtime available:

```powershell
supabase start
supabase db reset
supabase test db
```

`db reset` is destructive to the local Supabase database. Do not run it with `--remote` against staging or production. The test files are executed by `supabase test db`; the lifecycle test checks database grants, policy structure, RPC authorization, assignment/revocation transitions, audit events, scope validation, and the final-system-admin guard.

The SQL migration in `supabase/migrations/20261117150000_role_assignment_lifecycle.sql` mirrors the application-facing migration at `../../sql/Security/role_assignment_lifecycle.sql` so the Supabase CLI can replay it after the staged schema baseline. Keep both copies synchronized if the migration is edited before it is consolidated into the repository's single migration workflow.
