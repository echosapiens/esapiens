"""Cost simulation route — POST /api/v1/simulate-cost."""

from fastapi import APIRouter, Depends, Request
from app.models import CostSimulationRequest, CostEstimate
from app.openrouter import OpenRouterClient
from app.config import settings
from app.limiter import limiter
from app.security import get_current_user

router = APIRouter()

_openrouter_client: OpenRouterClient | None = None


def _get_client() -> OpenRouterClient:
    global _openrouter_client
    if _openrouter_client is None:
        _openrouter_client = OpenRouterClient()
    return _openrouter_client


@router.post("/simulate-cost")
@limiter.limit("20/minute")
async def simulate_cost(request: Request, body: CostSimulationRequest, user: dict = Depends(get_current_user)):
    """
    Quick cost estimation without full pipeline execution.
    Uses LLM to estimate compute requirements, applies tier markup.
    """
    client = _get_client()

    # Use LLM to estimate compute requirements
    system_prompt = (
        "You are a cloud cost estimator for bioinformatics pipelines. "
        "Given a user's request, estimate the compute cost in USD and time in minutes. "
        "Respond with a JSON object containing:\n"
        "- raw_compute_cost_usd: the raw compute cost estimate in USD\n"
        "- estimated_minutes: estimated execution time in minutes\n\n"
        "Base your estimates on typical AWS/GCP pricing for CPU compute (~$0.10/hour per vCPU). "
        "Be conservative in your estimates."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Estimate cost for: {body.user_prompt}"},
    ]

    result = client.chat_completion(
        messages, response_format={"type": "json_object"}
    )

    if "error" in result:
        return CostEstimate(
            raw_compute_cost_usd=5.00,
            platform_markup_usd=1.75,
            total_cost_usd=6.75,
            estimated_minutes=30,
        )

    raw_cost = result.get("raw_compute_cost_usd", 5.00)
    estimated_minutes = result.get("estimated_minutes", 30)

    # Apply tier markup
    if body.tier == "premium":
        markup = settings.PREMIUM_TIER_MARKUP
    else:
        markup = settings.FREE_TIER_MARKUP

    platform_markup = round(raw_cost * markup, 2)
    total_cost = round(raw_cost + platform_markup, 2)

    return CostEstimate(
        raw_compute_cost_usd=raw_cost,
        platform_markup_usd=platform_markup,
        total_cost_usd=total_cost,
        estimated_minutes=estimated_minutes,
    )