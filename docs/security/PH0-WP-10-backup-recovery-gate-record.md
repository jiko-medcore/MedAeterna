# PH0-WP-10 Backup, Recovery and Release-Gate Record — Free Plan

**Work package:** PH0-WP-10 production preflight/deployment/verification  
**Controlled procedure:** `backend/MedAeterna_Controlled_Supabase_Database_and_Storage_Release_Guide_v1.0.md`, especially §§8.4–8.5 and §10  
**Project:** MedAeterna / production ref `iyueixtpmzznyffshqon`  
**Record date:** 23 November 2026  
**Status:** **OPEN — backup and recovery gate NOT COMPLETE; production deployment remains BLOCKED; Phase 0 NOT ACCEPTED**

> This record does not contain a database password, connection string, SQL dump content, Storage object content, or patient data. Hosted operations so far were read-only catalog/advisor inspection. No `db push`, `config push`, `apply_migration`, `migration repair`, hosted upload/download/delete, or production deployment has been performed in this workspace.

---

## 1. Current gate status

| Gate | Status | Evidence / note |
|---|---|---|
| Local database verification | PASS | Clean reset, 6 migrations, 36/36 pgTAP tests, 0 WARN advisories. |
| Local Storage verification | PASS | 22/22 effective Storage API checks using synthetic identities/objects. |
| Backend regression tests | PASS | 1,368 passed, 1 skipped, 18 warnings. |
| Release branch merged to `main` | **NOT DONE** | See §7. PR #41 was opened in the wrong direction. |
| Production dry run | **NOT VERIFIED HERE** | The operator reports a passing dry run, but no output or CLI evidence is recorded in this workspace. CLI `whoami` still returns `AccessTokenRequiredError`. |
| Production database backup | **NOT CREATED / NOT VERIFIED** | Manual CLI logical export required on Free plan. |
| Automatic daily backups | **NOT AVAILABLE** | Supabase Free plan. |
| PITR | **NOT AVAILABLE** | Supabase Free plan. |
| Storage object backup | **NOT VERIFIED** | Database dumps do not include Storage file bytes. |
| Restore test | **NOT COMPLETE** | Must be done in a separate disposable target, not production. |
| Recovery owner | **NOT FORMALLY RECORDED** | Primary and backup owner names required. |
| Rollback / forward-fix plan | Draft in §6; approval pending. | Per-migration decision required. |
| Full §8.5 deployment authorization | **INCOMPLETE** | Exact project, commit and migrations were supplied; remaining fields are still missing. |
| Production deployment | **NOT PERFORMED** | Do not run `supabase db push --remote` until all gates close. |
| Phase 0 | **NOT ACCEPTED** | Evidence-backed closure and human acceptance remain outstanding. |

---

## 2. Environment expectations

| Item | Local Supabase | Remote production |
|---|---|---|
| Database backup | Optional; disposable local rebuild is sufficient | **Required** before migration |
| Automatic daily backups | Not necessary | Not included on Free |
| PITR | Not necessary | Not included on Free |
| Restore procedure | Reset/rebuild and test | **Document and test in a separate target** |
| Storage object backup | Optional; normally synthetic files | **Required separately** for real objects |
| Recovery owner | Developer maintaining local environment | **Named person required** |
| Rollback/forward-fix plan | Useful for testing | **Required before deployment** |

A local backup does not protect production, and a production backup does not validate local restore behavior. The controlled guide’s backup gate is specifically about the production project.

---

## 3. Free-plan constraints

| Feature | Free plan status |
|---|---|
| Automatic daily database backups | No |
| PITR | No |
| Manual database export using CLI | Yes |
| Manual restore into another project | Yes |
| Storage objects included in database backup | No |

Paid Pro adds daily backups with seven-day retention; PITR is a separate paid add-on. Pricing should be checked in the Supabase Dashboard before any billing decision. Upgrading solely to close this release checkpoint is **not** required if a carefully managed manual export and tested restore procedure are documented.

---

## 4. Required production database export

The backup directory must be outside the Git repository, encrypted, access-controlled, and copied to secure off-site storage.

### 4.1 Secure input rule

The database connection string and password must **not** be pasted into this conversation, GitHub, a committed file, or a PR body. The operator should enter it only into a temporary local environment variable, for example in PowerShell:

```powershell
$env:PROD_DB_URL = Read-Host "Paste production database connection string"
```

### 4.2 CLI readiness

```powershell
supabase --version
supabase db dump --help
```

Installed CLI in this workspace: `3.2.0`. The installed help is authoritative. `supabase db dump --remote=<ref|branch|url>` supports role-only, schema-only and data-only exports. Docker/PostgreSQL tools must be available locally.

### 4.3 Three required exports

```powershell
supabase db dump `
    --remote="$env:PROD_DB_URL" `
    -f "$backupDir\roles.sql" `
    --role-only
```

```powershell
supabase db dump `
    --remote="$env:PROD_DB_URL" `
    -f "$backupDir\schema.sql"
```

```powershell
supabase db dump `
    --remote="$env:PROD_DB_URL" `
    -f "$backupDir\data.sql" `
    --use-copy `
    --data-only `
    -x "storage.buckets_vectors" `
    -x "storage.vector_indexes"
```

Expected output files:

```text
roles.sql
schema.sql
data.sql
```

The default CLI dump excludes Supabase-managed schemas such as `auth` and `storage`, extension schemas, custom roles and data; the three separate exports cover roles, schema and data. Any failure means the backup is not complete and must be fixed and rerun.

### 4.4 Manifest template

```text
Project: MedAeterna
Environment: Production
Backup timestamp: <timestamp with timezone>
Backup method: Supabase CLI logical export
CLI version: <supabase --version>
Files:
- roles.sql
- schema.sql
- data.sql

Auth schema: Not included in standard CLI dump
Storage objects: Not included in standard CLI dump
PITR: Not available on Free plan
Automatic backups: Not available on Free plan
```

Share only success/failure messages, file sizes, timestamps, and checksums when asking for review. Do not share the connection string, password, or SQL file contents.

---

## 5. Storage object backup

A database dump of `storage.objects` does **not** back up the actual object bytes. For every production bucket that exists:

1. List all objects recursively, including nested folders.
2. Download each object while preserving bucket name and object path.
3. Record MIME type and relevant object metadata.
4. Calculate a checksum for each downloaded file.
5. Store files in encrypted, access-controlled storage.
6. Record total object count and verify downloaded count/checksums.
7. Preserve bucket configuration and access policies separately.

Known buckets from the read-only preflight:

| Bucket | Production status |
|---|---|
| `organization-logos` | Present; public, 2 MiB, JPEG/PNG/WebP |
| `practitioner-photos` | Present; public, but no size limit or MIME allowlist |
| `patient-avatars` | Absent in production; present only in local candidate |

Do not place downloaded patient-related objects in a public GitHub repository or ordinary unencrypted backup folder.

---

## 6. Restore test and rollback/forward-fix strategy

### 6.1 Restore test

Test against a separate disposable target project, never the current production project:

1. Create a new target project.
2. Configure required extensions and database features.
3. Obtain the target database connection string securely.
4. Restore roles, schema and data in the documented order.
5. Reapply anything excluded from the logical dump, including auth/storage configuration and realtime publications where applicable.
6. Verify the restored database against a sanitized catalog/evidence checklist.

Documented restore shape:

```bash
psql \
  --single-transaction \
  --variable ON_ERROR_STOP=1 \
  --file roles.sql \
  --file schema.sql \
  --command 'SET session_replication_role = replica' \
  --file data.sql \
  --dbname [CONNECTION_STRING]
```

This is a recovery procedure for a separate target, not a production command.

### 6.2 Forward-fix preference

A full production restore should not be the normal rollback mechanism for security-policy changes:

| Failure type | Preferred response |
|---|---|
| Incorrect RLS policy | Reviewed corrective policy migration |
| Incorrect grant | Reviewed corrective grant migration |
| Incorrect Storage policy | Corrective `storage.objects` policy migration |
| Unexpected data-loss event | Use documented backup recovery, with explicit approval |
| Partially applied migration | Stop, inspect actual database state, then choose reverse or repair |
| Wrong Storage public/private cutover | Correct configuration/policy in an approved sequence |

Restoring an old dump over a live database can erase legitimate later changes. Forward fixes are normally safer for security-policy mistakes.

---

## 7. GitHub release-state correction

Current GitHub evidence from read-only API inspection:

| Item | Value |
|---|---|
| `main` SHA | `4a5941c859ce6b1197c9cc2689715f08eb2f24ed` |
| Remote `security/phase-0-db-storage-release` SHA | `0066602afac41662eb6c79f877049d0b6fb39ed9` |
| Local branch HEAD | `c0eb6ce5508a4c154ccc2dd66d4c36284df43ccd` |
| Local status | Ahead of remote by 2 commits; not pushed |
| `main...security/phase-0-db-storage-release` | Diverged: security ahead 19, behind 3 |
| PR #41 | `head=main`, `base=docs/phase-0-security-plan-v2-and-backend-ci`; merged 2026-11-22T16:54:24Z |
| PR #41 merge effect | Merged `main` into the docs branch; did **not** merge the release branch into `main` |

Therefore the release branch is **not merged into `main`**. PR #41 must not be treated as the release merge. For the release record, freeze the actual `main` SHA and merged PR details after a correctly oriented PR is created and merged.

---

## 8. Open items before deployment

1. Push local cleanup commits and open a correctly oriented PR: `security/phase-0-db-storage-release` → `main`.
2. Obtain GitHub CI and human review approval on that PR.
3. Record the actual merged `main` SHA and PR number.
4. Create and verify the three production database exports.
5. Create and verify the separate Storage object backup.
6. Perform the restore test in a disposable target.
7. Record primary and backup recovery owners.
8. Approve the per-migration forward-fix plan.
9. Complete the remaining §8.5 authorization fields: PR/approval, Storage changes, expected impact, backup/PITR confirmation, recovery owner, deployment operator, deployment window and approval timestamp.
10. Re-run and record the production dry run and config diff under authenticated CLI conditions.
11. Only then consider a separately authorized production deployment.

---

## 9. Cross-references

- [Controlled Supabase database and storage release guide](../../backend/MedAeterna_Controlled_Supabase_Database_and_Storage_Release_Guide_v1.0.md)
- [SPEC-11/SPEC-12 hosted read-only preflight record](SPEC-11-SPEC-12-hosted-read-only-preflight-record.md)
- [PR body draft](PH0-DB-STORAGE-RELEASE-PR-body.md)
- [PH0-WP-07 completion record](PH0-WP-07-completion-record.md)
