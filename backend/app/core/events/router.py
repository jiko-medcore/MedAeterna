from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/events", tags=["Events"])


@router.get("/", include_in_schema=False)
def get_events():
    raise HTTPException(status_code=404, detail="Not found")


@router.get("/failed", include_in_schema=False)
def get_failed_events():
    raise HTTPException(status_code=404, detail="Not found")


@router.get("/metrics/summary", include_in_schema=False)
def event_metrics():
    raise HTTPException(status_code=404, detail="Not found")


@router.get("/onboarding", include_in_schema=False)
def onboarding_events():
    raise HTTPException(status_code=404, detail="Not found")


@router.post("/retry-failed", include_in_schema=False)
def retry_failed_events():
    raise HTTPException(status_code=404, detail="Not found")


@router.get("/{event_id}", include_in_schema=False)
def get_event(event_id: str):
    raise HTTPException(status_code=404, detail="Not found")


@router.post("/{event_id}/retry", include_in_schema=False)
def retry_event(event_id: str):
    raise HTTPException(status_code=404, detail="Not found")
