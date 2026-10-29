import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.supabase_client import supabase
from app.core.events import bootstrap
from app.core.events.router import router as events_router
from app.core.exception_handlers import register_exception_handlers
from app.modules.auth.router import router as auth_router
from app.modules.patients.router import router as patients_router
from app.modules.records.router import router as records_router
from app.modules.dashboard.router import router as dashboard_router
from app.modules.medical_history.router import router as medical_history_router
from app.modules.laboratory.router import router as laboratory_router
from app.modules.organizations.router import router as org_router
from app.modules.care_team.router import router as care_team_router
from app.modules.consents.router import router as consents_router
from app.modules.practitioner_roles.router import router as practitioner_roles_router
from app.modules.practitioners.router import router as practitioners_router
from app.modules.encounters.router import router as encounter_router
from app.modules.observations.router import router as observations_router
from app.modules.conditions.router import router as conditions_router
from app.modules.medications.router import router as medications_router
from app.modules.appointments.router import router as appointments_router


# ===== Initialize FastAPI Application =====
app = FastAPI(title="MedAeterna API", version="1.0.0", description="API for Electronic Medical History System")


# # ===== CORS Middleware Configuration =====
# # Example env var on Render:
# # ALLOWED_ORIGINS= https://your-frontend.com,http://localhost:3000
# allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "")
# allowed_origins = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]

# # For local/dev convenience (optional):
# if os.getenv("ENV", "development") == "development":
#     allowed_origins += [
#         "http://localhost:3000",
#         "http://localhost:5173",
#         "http://127.0.0.1:3000",
#         "http://127.0.0.1:5173",
#     ]

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=allowed_origins if allowed_origins else ["*"],  # Avoid "*" in production if possible
#     allow_credentials=True,  # Needed if using cookies; okay with auth headers too
#     allow_methods=["*"],
#     allow_headers=["*"],
# )



# ===== Include Routers =====


#  ===== Core Modules =====
# Auth Router
app.include_router(auth_router)
# Patients Router
app.include_router(patients_router)
# Records Router
app.include_router(records_router)
# Organization Router
app.include_router(org_router)
# Practitioners Router
app.include_router(practitioners_router)
# Practitioners Roles Router
app.include_router(practitioner_roles_router)
# Care Teams Router
app.include_router(care_team_router)
# Consents Router
app.include_router(consents_router)
# Encounters Router
app.include_router(encounter_router)
# Observations Router
app.include_router(observations_router)
# Conditions Router
app.include_router(conditions_router)
# Medications Router
app.include_router(medications_router)
# Appointments Router
app.include_router(appointments_router)

# ===== Feature Modules =====
# Medical History Router
app.include_router(medical_history_router)
# Laboratory Router
app.include_router(laboratory_router)


# ===== Aggregation Layer =====
app.include_router(dashboard_router)
app.include_router(events_router)


# ===== Event Hanlder Register =====
register_exception_handlers(app)


# ===== Root Endpoint =====
@app.get("/")
def root():
    return {
        "message": "MedCore API is running 🚀",
        "docs": "/docs"
    }

# ----- Health Check Endpoint -----
@app.get("/health")
def health():
    return {"status": "ok"}
