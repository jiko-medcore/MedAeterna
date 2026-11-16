# MedAeterna Frontend API Catalog

This catalog is derived from the checked-in Flutter patient app and FastAPI routers. It distinguishes endpoints the app currently calls from backend endpoints that exist but are not currently called by that app. The OpenAPI document at `/docs` remains the runtime source of truth for complete schemas.

## API server and conventions

- Current Flutter base URL: `https://medcore-0qgd.onrender.com` (defined in `frontend/patient_app/lib/core/services/api_service.dart`). Make this environment-configurable before shipping multiple environments.
- Authentication: bearer access token for protected routes. Signup and login are unauthenticated.
- JSON routes use `application/json`; login submits form fields (`username`, `password`).
- IDs in paths must be URL encoded. Dates are ISO 8601 unless otherwise documented by the response schema.
- Protected endpoint responses and error formats should be confirmed against the running OpenAPI schema; the app currently relies on decoded JSON maps.

## Calls made by the patient Flutter app

| Method | Path | Auth | Purpose / caller |
|---|---|---|---|
| `POST` | `/auth/signup` | No | Create an account; `AuthService.signup` sends `{email, password}`. |
| `POST` | `/auth/login` | No | Sign in; `AuthService.login` sends form fields `username` (email) and `password`; response must contain `access_token` and `user.id`, `user.email`. |
| `GET` | `/patients/me` | Bearer | Fetch or initialize the signed-in patient's patient record; `ProfileRepository.fetchProfile`. |
| `PUT` | `/patients/profile/me` | Bearer | Update the signed-in patient's profile; `ProfileRepository.updateProfile` sends profile fields. |
| `GET` | `/api/v1/user/summary` | Bearer | Home dashboard summary; `DashboardRepository.fetchSummary`. |
| `GET` | `/api/v1/medical-history` | Bearer | Current user's history; response expected as `{ "data": [...] }`; `HistoryRepository.fetchMedicalHistory`. |
| `GET` | `/api/v1/lab-results/{lab_id}` | Bearer | Lab detail by ID; `LabRepository.fetchLabResult`. |

The app also stores local history and caches profile/history for offline display. Those local operations do not call backend routes.

## Backend routes available but not called by the patient app

These are present in the current FastAPI routers and may be relevant to the provider/admin frontend or future patient features. They are not evidence of a frontend integration yet.

| Method | Path | Router / use |
|---|---|---|
| `GET` | `/auth/me` | Current authenticated user. |
| `GET` | `/patients/medical-id` | Signed-in patient's medical ID. |
| `GET` | `/patients/profile/me` | Alternate patient profile read route (currently app reads `/patients/me`). |
| `GET` | `/patients/mine` | Patients assigned to clinician. |
| `GET` | `/patients/{patient_id}/fhir` | Patient FHIR bundle, subject to access checks. |
| `GET` | `/patients/{patient_id}/qr` | Patient QR image, subject to access checks. |
| `GET` | `/patients/{patient_id}/summary` | Patient summary for authorized staff. |
| `GET` | `/patients/{patient_id}/timeline` | Patient timeline for authorized staff. |
| `POST` | `/patients/{patient_id}/assign` | Assign clinician to patient. |
| `POST` | `/patients/profile/upload-avatar` | Upload patient avatar (`multipart/form-data`, field `file`). |
| `POST`, `GET`, `PATCH` | `/appointments/` and `/appointments/{appointment_id}` | Create/list/update appointments; list routes are scoped by patient or practitioner ID. |
| `POST`, `GET`, `PATCH` | `/conditions/`, `/conditions/patient/{patient_id}`, `/conditions/encounter/{encounter_id}`, `/conditions/{condition_id}` | Clinical conditions. |
| `POST`, `GET`, `PATCH` | `/observations/`, `/observations/patient/{patient_id}`, `/observations/encounter/{encounter_id}`, `/observations/{observation_id}` | Clinical observations/vitals. |
| `POST`, `GET`, `PATCH` | `/medication-requests/`, `/medication-requests/patient/{patient_id}`, `/medication-requests/encounter/{encounter_id}`, `/medication-requests/{medication_request_id}` | Medication requests. |
| `POST`, `GET`, `PATCH` | `/encounters/`, `/encounters/patient/{patient_id}`, `/encounters/{encounter_id}` | Clinical encounters. |
| `POST` | `/records/observations`, `/records/conditions`, `/records/medications` | Record creation convenience endpoints. |
| `PATCH` | `/records/conditions/{record_id}/resolve` | Resolve a condition record. |
| `POST` | `/consents/grant`, `/consents/revoke`; `GET /consents/me` | Patient access consents. |
| `POST`, `GET`, `PATCH` | `/care-teams/`, `/care-teams/{care_team_id}/participants`, `/care-teams/patient/{patient_id}`, `/care-teams/participants/{participant_id}`, `/care-teams/assign` | Care team management. |
| `POST`, `GET`, `PATCH` | `/practitioners/`, `/practitioners/me`, `/practitioners/me/photo` | Practitioner profile. |
| `POST`, `GET`, `PATCH` | `/practitioner-roles/`, `/practitioner-roles/me`, `/practitioner-roles/organization/{organization_id}`, `/practitioner-roles/{role_id}` | Practitioner roles. |
| `POST`, `GET`, `PUT`, `PATCH`, `DELETE` | `/organizations/register`, `/organizations/me`, `/organizations/upload-logo`, `/organizations/update`, `/organizations/{org_id}/assign-role`, `/organizations/{org_id}/invite`, `/organizations/accept-invite`, `/organizations/profile`, `/organizations/{organization_id}/departments...`, `/organizations/{organization_id}/healthcare-services...`, `/organizations/{organization_id}/operating-hours...`, `/organizations/{organization_id}/branding...` | Organization registration/profile/invites and nested department, service, hours, branding management. Consult `/docs` for each nested method and request schema. |
| `GET` | `/terminology/{system}` | Terminology lookup. |
| `GET` | `/` and `/health` | Root and health checks. |

## Contract gaps to resolve before frontend integration

1. `BACKEND_API_SPECS.md` proposes payloads for dashboard, history, and labs, but examples are not a substitute for validated schemas. Align those examples with actual Pydantic response models and OpenAPI.
2. The Flutter profile repository calls `/patients/me`, while the proposed contract describes a `/user/summary` profile object. Keep one documented canonical profile shape or explain the distinct responsibilities.
3. Treat the runtime `/docs` output as canonical when adding new routes or changing nested organization routes; router-level prefixes compose together.
4. Publish pagination, filtering, error envelopes, token expiry/refresh behavior, and upload size/content validation in the contract.
5. Add Flutter integration for endpoints before labeling them as consumed. Current app usage is the seven routes in the first table.

## Security audit follow-up

The Phase 0 audit named in the handoff was not available at its supplied `G:\Other computers\...` location in this workspace, and no matching audit document was found in the repository search. Audit recommendations are findings to evaluate against the code, not instructions to execute blindly. Attach the Markdown file in this chat or put it in the workspace so each finding can be mapped to code, severity, remediation, and verification criteria.
