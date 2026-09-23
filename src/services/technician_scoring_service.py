"""AgentCore Platform v1.0 — SVC-C2-016"""

# Service layer: deterministic technician scoring (skill x proximity x availability).
# This is the "Tool" half of the Agent-vs-Tool split (see the framework's architecture guidance):
# a pure computation with no State, no side effects, no credentials.
# Must NOT contain agenticstar imports or business orchestration logic.

from __future__ import annotations

import math
from typing import Any


def _distance_km(a: dict[str, Any], b: dict[str, Any]) -> float:
    """Great-circle distance (haversine) between two {lat, lng} points, in km."""
    lat1, lon1 = float(a.get("lat", 0.0) or 0.0), float(a.get("lng", 0.0) or 0.0)
    lat2, lon2 = float(b.get("lat", 0.0) or 0.0), float(b.get("lng", 0.0) or 0.0)
    earth_radius_km = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    hav = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * earth_radius_km * math.asin(min(1.0, math.sqrt(max(0.0, hav))))


def score_technicians(
    required_skills: list[str],
    customer_location: dict[str, Any],
    roster: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Score each roster technician by skill-match x proximity x availability.

    Weights: skill_ratio 0.5, proximity 0.3, availability 0.2. Returns the
    roster re-ranked descending by `score` (highest first).
    """
    required = set(required_skills or [])
    scored: list[dict[str, Any]] = []
    for tech in roster:
        skills = set(tech.get("skills") or [])
        skill_ratio = (len(skills & required) / len(required)) if required else 1.0
        distance_km = _distance_km(customer_location or {}, tech.get("location") or {})
        proximity_score = max(0.0, 1.0 - min(distance_km, 100.0) / 100.0)
        availability_score = 1.0 if tech.get("available", False) else 0.0
        total = round(skill_ratio * 0.5 + proximity_score * 0.3 + availability_score * 0.2, 4)
        scored.append(
            {
                "technician_id": tech.get("technician_id"),
                "name": tech.get("name"),
                "skill_ratio": round(skill_ratio, 4),
                "distance_km": round(distance_km, 2),
                "proximity_score": round(proximity_score, 4),
                "availability_score": availability_score,
                "score": total,
            }
        )
    scored.sort(key=lambda t: t["score"], reverse=True)
    return scored
