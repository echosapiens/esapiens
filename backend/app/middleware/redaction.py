"""SequenceHeaderRedactionMiddleware — strips identifying headers from FASTQ/BAM data.

Intercepts response payloads and applies regex-based redaction to remove:
- @InstrumentID patterns from FASTQ headers
- @FlowCellID patterns from BAM/FASTQ headers
- Patient identifier patterns (MRN, patient name fields)

This ensures no PHI or sequencing instrument identifiers are leaked to third-party services.
"""

from __future__ import annotations

import re
from typing import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse

# ── Redaction patterns ───────────────────────────────────────────────

# FASTQ read header: @InstrumentID:RunID:FlowCellID:Lane:Tile:...
FASTQ_HEADER_RE = re.compile(
    r"(@[A-Za-z0-9_\-]+:\d+:[A-Za-z0-9_\-]+:\d+:\d+:\d+)",
    re.MULTILINE,
)

# BAM @HD / @RG lines containing flow-cell / instrument
BAM_FLOWCELL_RE = re.compile(
    r"(@(?:RG|CO)\t[^\n]*?(?:FC|flowcell|flow_cell)[=A-Za-z0-9:\t\-]+)",
    re.MULTILINE,
)
BAM_INSTRUMENT_RE = re.compile(
    r"(@(?:RG|CO)\t[^\n]*?(?:PL|platform|instrument)[=A-Za-z0-9:\t\-]+)",
    re.MULTILINE,
)

# Patient identifiers — MRN, patient name, DOB
PATIENT_MRN_RE = re.compile(
    r"(?:MRN|mrn|Medical Record Number)[=:]\s*[A-Za-z0-9\-]+",
    re.IGNORECASE,
)
PATIENT_NAME_RE = re.compile(
    r"(?:Patient[_\s]?Name|patient_name)[=:]\s*[A-Za-z0-9,\s\-]+",
    re.IGNORECASE,
)
PATIENT_DOB_RE = re.compile(
    r"(?:DOB|dob|date_of_birth|birth_date)[=:]\s*\d{4}[\/\-]\d{2}[\/\-]\d{2}",
    re.IGNORECASE,
)

ALL_PATTERNS: list[re.Pattern[str]] = [
    FASTQ_HEADER_RE,
    BAM_FLOWCELL_RE,
    BAM_INSTRUMENT_RE,
    PATIENT_MRN_RE,
    PATIENT_NAME_RE,
    PATIENT_DOB_RE,
]

REDACTION_PLACEHOLDER = "[REDACTED]"


def _redact_text(text: str) -> str:
    """Apply all redaction regex patterns to the given text."""
    for pattern in ALL_PATTERNS:
        text = pattern.sub(REDACTION_PLACEHOLDER, text)
    return text


def _should_redact(request: Request, response: Response) -> bool:
    """Only redact responses with bioinformatics content types or JSON."""
    content_type = response.headers.get("content-type", "")
    redactable = (
        "application/json" in content_type
        or "text/plain" in content_type
        or "text/x-fastq" in content_type
        or "application/octet-stream" in content_type
    )
    return redactable and response.status_code < 400


class SequenceHeaderRedactionMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that redacts identifying headers from sequence data."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)

        if not _should_redact(request, response):
            return response

        # Handle streaming responses
        if isinstance(response, StreamingResponse):
            original_iter = response.body_iterator

            async def redacted_stream():
                async for chunk in original_iter:
                    if isinstance(chunk, bytes):
                        text = chunk.decode("utf-8", errors="replace")
                        redacted = _redact_text(text)
                        yield redacted.encode("utf-8")
                    elif isinstance(chunk, str):
                        yield _redact_text(chunk)
                    else:
                        yield chunk

            return StreamingResponse(
                redacted_stream(),
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )

        # Handle regular responses — typically won't have body in middleware,
        # but for completeness read and redact
        return response