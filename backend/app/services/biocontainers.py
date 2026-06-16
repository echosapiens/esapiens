"""BioContainers TRS API registry service.

Async singleton that resolves bioinformatics tool names to their latest
Docker image references via the BioContainers GA4GH TRS v2 API
(https://api.biocontainers.pro/ga4gh/trs/v2/).

On startup it populates an in-memory cache from a curated list of popular
tools.  If the API is unreachable the hard-coded fallback entries from
agent.py are used instead.  Uncached tool names trigger a real-time API
lookup.

Public API
----------
get_tool_image(tool_name) -> str | None
get_tool_info(tool_name) -> dict | None
list_tools() -> list[str]
initialize()            -> None   # call once at app startup
"""

from __future__ import annotations

import asyncio
import logging
import time

import httpx

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

TRS_BASE = "https://api.biocontainers.pro/ga4gh/trs/v2"
QUAY_API_BASE = "https://quay.io/api/v1"
_REQUEST_TIMEOUT = 15.0  # seconds
_CACHE_TTL = 6 * 3600  # 6 hours in seconds

# ── Hard-coded fallback (from agent.py BIOCONTAINER_REGISTRY) ────────────────

_FALLBACK_REGISTRY: dict[str, dict[str, str]] = {
    "bwa-mem2": {
        "image": "quay.io/biocontainers/bwa-mem2:2.2.1--h7d8f6ac_2",
        "description": "BWA-MEM2 alignment algorithm",
        "version": "2.2.1",
    },
    "samtools-sort": {
        "image": "quay.io/biocontainers/samtools:1.19--h50ea8bc_2",
        "description": "Sort SAM/BAM files",
        "version": "1.19",
    },
    "samtools-index": {
        "image": "quay.io/biocontainers/samtools:1.19--h50ea8bc_2",
        "description": "Index SAM/BAM files",
        "version": "1.19",
    },
    "gatk4-haplotypecaller": {
        "image": "quay.io/biocontainers/gatk4:4.5.0.0--py312h6e2a037_0",
        "description": "GATK4 HaplotypeCaller variant caller",
        "version": "4.5.0.0",
    },
    "gatk4-markduplicates": {
        "image": "quay.io/biocontainers/gatk4:4.5.0.0--py312h6e2a037_0",
        "description": "GATK4 MarkDuplicates",
        "version": "4.5.0.0",
    },
    "fastqc": {
        "image": "quay.io/biocontainers/fastqc:0.12.1--hdfd78af_0",
        "description": "FastQC quality control tool",
        "version": "0.12.1",
    },
    "bcftools": {
        "image": "quay.io/biocontainers/bcftools:1.19--h6e2a037_0",
        "description": "BCFtools variant calling & manipulation",
        "version": "1.19",
    },
    "star-align": {
        "image": "quay.io/biocontainers/star:2.7.11a--h6e2a037_0",
        "description": "STAR RNA-seq aligner",
        "version": "2.7.11a",
    },
    "hisat2": {
        "image": "quay.io/biocontainers/hisat2:2.2.1--h7d8f6ac_2",
        "description": "HISAT2 graph-based aligner",
        "version": "2.2.1",
    },
    "picard-markduplicates": {
        "image": "quay.io/biocontainers/picard:3.1.1--h5eeb5cd_0",
        "description": "Picard MarkDuplicates",
        "version": "3.1.1",
    },
    "multiqc": {
        "image": "quay.io/biocontainers/multiqc:1.21--py312h7d8f6ac_0",
        "description": "MultiQC aggregate quality reports",
        "version": "1.21",
    },
}

# ── Curated list of tools to pre-populate on startup ─────────────────────────

_CURATED_TOOLS: list[str] = [
    "fastqc",
    "bwa-mem2",
    "samtools-sort",
    "samtools-index",
    "gatk4-haplotypecaller",
    "gatk4-markduplicates",
    "bcftools",
    "star-align",
    "hisat2",
    "picard-markduplicates",
    "multiqc",
    "salmon",
    "kallisto",
    "bowtie2",
    "sra-toolkit",
    "trimmomatic",
    "cutadapt",
    "macs2",
    "deeptools",
    "snpeff",
    "vep",
    "igv",
    "freebayes",
    "varscan",
    "spades",
    "megahit",
    "kraken2",
    "kraken2-build",
    "bracken",
    "prokka",
    "ariba",
]

# ── Singleton ────────────────────────────────────────────────────────────────


class BioContainersRegistry:
    """Async singleton that manages the BioContainers tool registry.

    Call :meth:`initialize` once at app startup.  Afterwards use the
    module-level convenience functions.
    """

    _instance: BioContainersRegistry | None = None

    def __init__(self) -> None:
        self._cache: dict[str, dict[str, str]] = {}
        self._cache_times: dict[str, float] = {}
        self._initialized = False
        self._client: httpx.AsyncClient | None = None

    # ── Public helpers ────────────────────────────────────────────

    @classmethod
    def get_instance(cls) -> BioContainersRegistry:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset singleton (useful for testing)."""
        cls._instance = None

    # ── Lifecycle ──────────────────────────────────────────────────

    async def initialize(self) -> None:
        """Populate the cache from the TRS API, falling back to hard-coded
        defaults when the API is unreachable."""
        if self._initialized:
            return

        self._client = httpx.AsyncClient(timeout=_REQUEST_TIMEOUT)

        # Seed with fallback so we always have *something*
        self._cache.update(_FALLBACK_REGISTRY)

        # Try to refresh from the live API
        try:
            await self._populate_from_api()
        except Exception:
            logger.exception(
                "BioContainers API unreachable — using hard-coded fallbacks"
            )

        self._initialized = True
        logger.info(
            "BioContainers registry ready: %d tools cached", len(self._cache)
        )

    async def shutdown(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        self._initialized = False

    # ── Public query interface ─────────────────────────────────────

    def get_tool_image(self, tool_name: str) -> str | None:
        """Return the Docker image reference for *tool_name*, or None."""
        info = self.get_tool_info(tool_name)
        return info["image"] if info else None

    def get_tool_info(self, tool_name: str) -> dict[str, str] | None:
        """Return {image, description, version} for *tool_name*, or None.

        Triggers a live API lookup for uncached tools.
        """
        entry = self._cache.get(tool_name)
        if entry is not None:
            # Refresh stale entries asynchronously (fire-and-forget)
            if time.monotonic() - self._cache_times.get(tool_name, 0) > _CACHE_TTL:
                asyncio.create_task(self._refresh_tool(tool_name))
            return dict(entry)

        # Not cached — try a synchronous-ish lookup via the running loop
        if self._initialized and self._client is not None:
            try:
                # We're in an async context already; schedule & await
                loop = asyncio.get_running_loop()
                task = loop.create_task(self._resolve_tool(tool_name))
                # We can't await here (caller may be sync), so fire & forget
                # and return None for now; next call will hit the cache.
                task.add_done_callback(self._on_resolve_done)
            except RuntimeError:
                pass

        return None

    def list_tools(self) -> list[str]:
        """Return sorted list of cached tool names."""
        return sorted(self._cache.keys())

    # ── Internal API interaction ───────────────────────────────────

    async def _populate_from_api(self) -> None:
        """Resolve each curated tool via the TRS API and update cache."""
        tasks = [self._resolve_tool(name) for name in _CURATED_TOOLS]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        resolved = 0
        for name, result in zip(_CURATED_TOOLS, results):
            if isinstance(result, Exception):
                logger.warning("Failed to resolve '%s': %s", name, result)
                continue
            if result is not None:
                self._cache[name] = result
                self._cache_times[name] = time.monotonic()
                resolved += 1

        logger.info(
            "Resolved %d/%d curated tools from BioContainers TRS API",
            resolved,
            len(_CURATED_TOOLS),
        )

    async def _resolve_tool(self, tool_name: str) -> dict[str, str] | None:
        """Look up a single tool via the TRS API.

        Returns a dict with keys ``image``, ``description``, ``version``
        or None when the tool cannot be found.
        """
        assert self._client is not None

        # Step 1: Search for the tool by name
        search_resp = await self._client.get(
            f"{TRS_BASE}/tools",
            params={"name": tool_name, "limit": 10},
        )
        if search_resp.status_code != 200:
            logger.debug(
                "TRS search for '%s' returned HTTP %d",
                tool_name,
                search_resp.status_code,
            )
            return None

        tools = search_resp.json()
        if not tools:
            logger.debug("TRS search for '%s' returned no results", tool_name)
            return None

        # Pick the best match — prefer exact ID match
        tool_id: str | None = None
        for t in tools:
            # TRS tool IDs often look like "biocontainers/fastqc" or just "fastqc"
            tid = t.get("id", "")
            # Normalise: strip "biocontainers/" prefix for comparison
            bare_id = tid.removeprefix("biocontainers/")
            if bare_id == tool_name:
                tool_id = tid
                break
        if tool_id is None:
            # Fall back to the first result
            tool_id = tools[0].get("id")

        if not tool_id:
            return None

        # Step 2: Get tool detail for description
        tool_resp = await self._client.get(f"{TRS_BASE}/tools/{tool_id}")
        description = ""
        if tool_resp.status_code == 200:
            tool_data = tool_resp.json()
            description = tool_data.get("description", "") or ""

        # Step 3: Get versions, pick the latest
        versions_resp = await self._client.get(
            f"{TRS_BASE}/tools/{tool_id}/versions"
        )
        if versions_resp.status_code != 200:
            logger.debug(
                "TRS versions for '%s' returned HTTP %d",
                tool_id,
                versions_resp.status_code,
            )
            return None

        versions = versions_resp.json()
        if not versions:
            return None

        # Versions are usually newest-first, but sort by meta.version just in case
        latest_version = versions[0]
        version_id = latest_version.get("id", "")
        # The version meta may contain a human-readable version string
        version_meta = latest_version.get("meta_version") or latest_version.get(
            "meta_version", ""
        )

        # Step 4: Get version detail (contains image references)
        ver_detail_resp = await self._client.get(
            f"{TRS_BASE}/tools/{tool_id}/versions/{version_id}"
        )
        if ver_detail_resp.status_code != 200:
            logger.debug(
                "TRS version detail for '%s/%s' returned HTTP %d",
                tool_id,
                version_id,
                ver_detail_resp.status_code,
            )
            return None

        ver_data = ver_detail_resp.json()
        images = ver_data.get("images", [])

        # Find the Docker image entry
        docker_image_name: str | None = None
        for img in images:
            if img.get("image_type") == "Docker":
                docker_image_name = img.get("image_name", "")
                break

        if not docker_image_name:
            # Try Singularity image_name as a fallback — it often contains
            # a tag we can turn into a quay.io Docker reference.
            for img in images:
                if img.get("image_type") == "Singularity":
                    docker_image_name = img.get("image_name", "")
                    break

        if not docker_image_name:
            logger.debug("No Docker image found for '%s'", tool_id)
            return None

        # Extract version from image tag if meta_version is empty
        if not version_meta and ":" in docker_image_name:
            tag = docker_image_name.rsplit(":", 1)[-1]
            # Tags like "0.12.1--hdfd78af_0" — take the part before "--"
            version_meta = tag.split("--")[0] if "--" in tag else tag

        return {
            "image": docker_image_name,
            "description": description or f"Bioinformatics tool: {tool_name}",
            "version": version_meta or "latest",
        }

    async def _refresh_tool(self, tool_name: str) -> None:
        """Background refresh of a stale cache entry."""
        try:
            result = await self._resolve_tool(tool_name)
            if result is not None:
                self._cache[tool_name] = result
                self._cache_times[tool_name] = time.monotonic()
                logger.debug("Refreshed cache for '%s'", tool_name)
        except Exception:
            logger.debug("Background refresh failed for '%s'", tool_name, exc_info=True)

    @staticmethod
    def _on_resolve_done(task: asyncio.Task) -> None:  # noqa: ANN205
        """Callback for fire-and-forget resolve tasks."""
        if task.exception():
            logger.debug("Async resolve failed: %s", task.exception())

    # ── Quay.io digest helper (best-effort) ────────────────────────

    async def _try_get_quay_digest(self, image_ref: str) -> str | None:
        """Best-effort attempt to retrieve the SHA256 digest from quay.io.

        Returns the digest string (e.g. ``sha256:abc123…``) or None.
        """
        assert self._client is not None
        try:
            # image_ref like "quay.io/biocontainers/fastqc:0.12.1--hdfd78af_0"
            if not image_ref.startswith("quay.io/"):
                return None
            # Strip quay.io/ → "biocontainers/fastqc:0.12.1--hdfd78af_0"
            path = image_ref[len("quay.io/"):]
            repo, _, tag = path.partition(":")
            if not tag:
                tag = "latest"
            resp = await self._client.get(
                f"{QUAY_API_BASE}/repository/{repo}/image/",
                params={"tag": tag},
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            images = data.get("images", [])
            if images:
                return images[0].get("digest")
        except Exception:
            logger.debug("Quay digest lookup failed for %s", image_ref, exc_info=True)
        return None


# ── Module-level convenience functions ───────────────────────────────────────

_registry = BioContainersRegistry.get_instance


async def initialize() -> None:
    """Initialize the registry singleton (call once at app startup)."""
    reg = _registry()
    await reg.initialize()


async def shutdown() -> None:
    """Shut down the registry (call at app shutdown)."""
    reg = _registry()
    await reg.shutdown()


def get_tool_image(tool_name: str) -> str | None:
    """Return the Docker image reference for *tool_name*, or None."""
    return _registry().get_tool_image(tool_name)


def get_tool_info(tool_name: str) -> dict[str, str] | None:
    """Return {image, description, version} for *tool_name*, or None."""
    return _registry().get_tool_info(tool_name)


def list_tools() -> list[str]:
    """Return sorted list of cached tool names."""
    return _registry().list_tools()


def get_registry_dict() -> dict[str, dict[str, str]]:
    """Return the full registry as a plain dict (compatible with the old
    BIOCONTAINER_REGISTRY interface used in agent.py).
    Returns fallback entries when the cache is empty (before startup).
    """
    cache = dict(_registry()._cache)
    return cache if cache else dict(_FALLBACK_REGISTRY)