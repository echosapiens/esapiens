"""Jobs routes — GET/DELETE /api/v1/jobs."""

from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import PlainTextResponse
from app import database
from app.limiter import limiter
from app.security import get_current_user

router = APIRouter()


@router.get("/jobs")
@limiter.limit("60/minute")
async def list_jobs(
    request: Request,
    limit: int = 20,
    status: Optional[str] = None,
    q: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    """List jobs with optional filtering by status and text search."""
    if status or q:
        return database.search_jobs(limit=limit, status=status, query=q)
    return database.list_jobs(limit)


@router.get("/jobs/{job_id}/download")
@limiter.limit("60/minute")
async def download_job_results(request: Request, job_id: str, user: dict = Depends(get_current_user)):
    """Download job stdout/stderr as a .txt file."""
    job = database.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    content = f"Job: {job['id']}\n"
    content += f"Prompt: {job['user_prompt']}\n"
    content += f"Status: {job['status']}\n"
    content += f"Created: {job['created_at']}\n"
    if job.get('completed_at'):
        content += f"Completed: {job['completed_at']}\n"
    content += "\n" + "=" * 60 + "\n\n"

    if job.get('stdout'):
        content += "STDOUT:\n" + job['stdout'] + "\n\n"
    if job.get('stderr'):
        content += "STDERR:\n" + job['stderr'] + "\n\n"
    if job.get('error'):
        content += "ERROR:\n" + job['error'] + "\n"

    return PlainTextResponse(
        content=content,
        media_type="text/plain",
        headers={"Content-Disposition": f"attachment; filename=job-{job_id}.txt"},
    )


@router.get("/jobs/{job_id}")
@limiter.limit("60/minute")
async def get_job(request: Request, job_id: str, user: dict = Depends(get_current_user)):
    """Get a single job by ID."""
    job = database.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.delete("/jobs/cleanup")
async def cleanup_old_jobs(older_than_days: int = 30, user: dict = Depends(get_current_user)):
    """Delete jobs older than the specified number of days."""
    from datetime import datetime, timezone, timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=older_than_days)).isoformat()
    conn = database._get_connection()
    try:
        deleted = conn.execute(
            "DELETE FROM jobs WHERE created_at < ?", (cutoff,)
        ).rowcount
        conn.commit()
        return {"deleted": deleted, "older_than_days": older_than_days}
    finally:
        conn.close()


@router.delete("/jobs/{job_id}")
async def delete_job(request: Request, job_id: str, user: dict = Depends(get_current_user)):
    """Delete a job by ID."""
    job = database.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    database.delete_job(job_id)
    return {"status": "deleted"}
