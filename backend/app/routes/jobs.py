"""Jobs routes — GET/DELETE /api/v1/jobs."""

from fastapi import APIRouter, HTTPException, Depends, Request
from app import database
from app.limiter import limiter
from app.security import get_current_user

router = APIRouter()


@router.get("/jobs")
@limiter.limit("60/minute")
async def list_jobs(request: Request, limit: int = 20, user: dict = Depends(get_current_user)):
    """List recent jobs, ordered by creation time descending."""
    return database.list_jobs(limit)


@router.get("/jobs/{job_id}")
@limiter.limit("60/minute")
async def get_job(request: Request, job_id: str, user: dict = Depends(get_current_user)):
    """Get a single job by ID."""
    job = database.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.delete("/jobs/{job_id}")
async def delete_job(request: Request, job_id: str, user: dict = Depends(get_current_user)):
    """Delete a job by ID."""
    job = database.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    database.delete_job(job_id)
    return {"status": "deleted"}