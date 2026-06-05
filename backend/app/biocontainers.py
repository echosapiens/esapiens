"""BioContainers Registry API client — kept for future dynamic resolution."""

import httpx
from typing import Optional


BIOCONTAINERS_API = "https://api.biocontainers.pro/ga4gh/trs/v2"


def resolve_tool_image(tool_name: str) -> str:
    """
    Resolve a verified BioContainer image for the given tool name via the API.
    Returns empty string if not found.
    """
    try:
        resp = httpx.get(
            f"{BIOCONTAINERS_API}/tools",
            params={"toolClass": "Tool", "q": tool_name},
            timeout=5.0,
        )
        resp.raise_for_status()
        tools = resp.json()
        if not isinstance(tools, list) or not tools:
            return ""

        tool_id = tools[0].get("id", "")
        if not tool_id:
            return ""

        resp2 = httpx.get(
            f"{BIOCONTAINERS_API}/tools/{tool_id}/versions",
            timeout=5.0,
        )
        resp2.raise_for_status()
        versions = resp2.json()
        if not isinstance(versions, list) or not versions:
            return ""

        latest = versions[-1]
        version_id = latest.get("id", "")
        if not version_id:
            return ""

        resp3 = httpx.get(
            f"{BIOCONTAINERS_API}/tools/{tool_id}/versions/{version_id}",
            timeout=5.0,
        )
        resp3.raise_for_status()
        detail = resp3.json()

        images = detail.get("images", [])
        for img in images:
            image_url = img.get("image", {}).get("image", "")
            if image_url:
                return image_url

        return ""

    except Exception:
        return ""