"""AgentCore Platform v1.0 — SVC-C2-016"""

# Service layer: deterministic route/ETA estimate for the selected technician.
# Pure computation (Tool half of the Agent-vs-Tool split) — no State, no side
# effects, no agenticstar imports.

from __future__ import annotations

from typing import Any

DEFAULT_AVG_SPEED_KMH = 35.0


def optimize_route(
    technician: dict[str, Any],
    customer_location: dict[str, Any],
    avg_speed_kmh: float = DEFAULT_AVG_SPEED_KMH,
) -> dict[str, Any]:
    """Build a simple direct-route ETA estimate for the selected technician.

    `technician` is a scored-technician dict (from technician_scoring_service)
    that already carries `distance_km`.
    """
    distance_km = float(technician.get("distance_km", 0.0) or 0.0)
    eta_minutes = round((distance_km / avg_speed_kmh) * 60, 1) if avg_speed_kmh else None
    return {
        "technician_id": technician.get("technician_id"),
        "distance_km": distance_km,
        "eta_minutes": eta_minutes,
        "route_summary": f"Direct route to customer location, ~{distance_km} km, ETA {eta_minutes} min",
    }
