"""Jobs routes — GET/DELETE /api/v1/jobs."""

from fastapi import APIRouter, HTTPException
from app import database

router = APIRouter()


@router.get("/jobs")
async def list_jobs(limit: int = 20):
    """List recent jobs, ordered by creation time descending."""
    return database.list_jobs(limit)


@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    """Get a single job by ID."""
    job = database.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    """Delete a job by ID."""
    job = database.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    database.delete_job(job_id)
    return {"status": "deleted"}