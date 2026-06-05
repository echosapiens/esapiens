"""Web-search module for fetching real documentation for bioinformatics tools.

Uses Brave Search API to find actual tool documentation, tutorials, and examples.
Returns structured findings that the research agent uses to generate correct commands.
"""

import os
import re
import urllib.parse
import httpx


# Contextual search terms for tools with ambiguous names
# (avoids "star" returning astronomy results, "muscle" returning fitness, etc.)
_TOOL_SEARCH_CONTEXT = {
    "star": "STAR aligner RNA-seq splice",
    "muscle": "MUSCLE alignment bioinformatics",
    "salmon": "Salmon quantifier transcript RNA-seq",
    "bwa": "BWA burrows-wheeler aligner",
    "blast": "BLAST nucleotide sequence search NCBI",
}


def search_tool_docs(tool_name: str, user_prompt: str) -> dict:
    """Fetch real documentation for a bioinformatics tool via Brave Search API.

    Searches for official docs, tutorials, and command-line examples.
    Returns a structured dict with findings and a concatenated usage summary.
    """
    api_key = os.getenv("BRAVE_SEARCH_API_KEY")
    if not api_key:
        return {
            "tool_name": tool_name,
            "queries_used": [],
            "findings": [],
            "usage_summary": "",
            "error": "BRAVE_SEARCH_API_KEY not configured",
        }

    # Build targeted search queries with disambiguation
    context = _TOOL_SEARCH_CONTEXT.get(tool_name, "bioinformatics")
    queries = [
        f"biocontainers {tool_name} usage examples command line",
        f"{tool_name} {context} tutorial command line flags",
        f"{tool_name} {' '.join(user_prompt.split()[:6])}",
    ]

    all_findings = []
    seen_urls = set()
    import time

    for i, query in enumerate(queries):
        # Rate limit: 1 query/second on Brave free tier
        if i > 0:
            time.sleep(1.2)
        try:
            encoded = urllib.parse.quote(query)
            url = f"https://api.search.brave.com/res/v1/web/search?q={encoded}&count=5&extra_snippets=true"

            resp = httpx.get(
                url,
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip",
                    "X-Subscription-Token": api_key,
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

            for r in data.get("web", {}).get("results", []):
                rurl = r.get("url", "")
                if rurl in seen_urls:
                    continue
                seen_urls.add(rurl)

                # Prefer extra_snippets (deeper content), fall back to description
                snippet = ""
                for s in r.get("extra_snippets", [])[:1]:
                    snippet = re.sub(r"<[^>]+>", "", s)
                if not snippet:
                    snippet = re.sub(r"<[^>]+>", "", r.get("description", ""))

                if snippet:
                    all_findings.append({
                        "title": r.get("title", ""),
                        "url": rurl,
                        "snippet": snippet[:500],
                    })
        except Exception:
            continue  # Skip failed queries, proceed with what we have

    # Build usage summary from top findings (max 2000 chars)
    parts = []
    total_len = 0
    for f in all_findings[:5]:
        entry = f"[{f['title']}]\n{f['snippet']}\n"
        if total_len + len(entry) > 2000:
            break
        parts.append(entry)
        total_len += len(entry)

    usage_summary = "\n".join(parts)

    return {
        "tool_name": tool_name,
        "queries_used": queries,
        "findings": all_findings[:5],
        "usage_summary": usage_summary,
    }