from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/events", tags=["Events"])


@router.get("/")
def get_events():
    raise HTTPException(status_code=404, detail="Not found")


@router.get("/failed")
def get_failed_events():
    raise HTTPException(status_code=404, detail="Not found")


@router.get("/metrics/summary")
def event_metrics():
    raise HTTPException(status_code=404, detail="Not found")


@router.get("/onboarding")
def onboarding_events():
    raise HTTPException(status_code=404, detail="Not found")


@router.post("/retry-failed")
def retry_failed_events():
    raise HTTPException(status_code=404, detail="Not found")


@router.get("/{event_id}")
def get_event(event_id: str):
    raise HTTPException(status_code=404, detail="Not found")


@router.post("/{event_id}/retry")
def retry_event(event_id: str):
    raise HTTPException(status_code=404, detail="Not found")
