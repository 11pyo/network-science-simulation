"""
Centralized input validation functions.
"""

import html
import logging

from config.constants import (
    VALID_NODE_IDS,
    VALID_CENTRALITY_METHODS,
    WEIGHT_MIN,
    WEIGHT_MAX,
    SHOCK_MIN,
    SHOCK_MAX,
    MAX_SIMULATION_STEPS,
)

logger = logging.getLogger(__name__)


# [SECURE] Whitelist validation - prevents arbitrary node ID injection (Category 1)
def validate_node_id(node_id: str) -> str:
    if node_id not in VALID_NODE_IDS:
        logger.warning("Invalid node_id attempted: %s", node_id)
        raise ValueError("Invalid node selection.")
    return node_id


# [SECURE] Range validation - prevents out-of-bounds weight values (Category 1)
def validate_weight(value: float) -> float:
    if not isinstance(value, (int, float)):
        logger.warning("Non-numeric weight value: %s", type(value))
        raise ValueError("Weight must be a number.")
    clamped = max(WEIGHT_MIN, min(WEIGHT_MAX, float(value)))
    return clamped


# [SECURE] Range validation - prevents out-of-bounds shock values (Category 1)
def validate_shock_intensity(value: float) -> float:
    if not isinstance(value, (int, float)):
        logger.warning("Non-numeric shock value: %s", type(value))
        raise ValueError("Shock intensity must be a number.")
    clamped = max(SHOCK_MIN, min(SHOCK_MAX, float(value)))
    return clamped


# [SECURE] Whitelist validation - prevents arbitrary method injection (Category 1)
def validate_centrality_method(method: str) -> str:
    if method not in VALID_CENTRALITY_METHODS:
        logger.warning("Invalid centrality method: %s", method)
        raise ValueError("Invalid centrality method.")
    return method


# [SECURE] Range validation with max cap - prevents infinite loop (Category 3)
def validate_simulation_steps(steps: int) -> int:
    if not isinstance(steps, int):
        steps = int(steps)
    if steps < 1:
        steps = 1
    if steps > MAX_SIMULATION_STEPS:
        steps = MAX_SIMULATION_STEPS
    return steps


# [SECURE] Range validation for damping factor
def validate_damping(value: float) -> float:
    if not isinstance(value, (int, float)):
        raise ValueError("Damping factor must be a number.")
    return max(0.01, min(0.99, float(value)))


# [SECURE] HTML escape - prevents XSS via user-provided text (Category 1)
def sanitize_label(text: str) -> str:
    if not isinstance(text, str):
        text = str(text)
    return html.escape(text, quote=True)


# --------------------------------------------------
# Security Checklist
# Applied:
#   - Input validation: All functions use whitelist or range checks (Category 1)
#   - Infinite loop prevention: validate_simulation_steps caps at MAX_SIMULATION_STEPS (Category 3)
#   - Error message exposure prevention: Generic messages to caller, details logged server-side (Category 4)
#   - XSS prevention: sanitize_label uses html.escape (Category 1)
#   - Null check: Type checks before processing (Category 5)
# Not Applied:
#   - [WARN] SQL Injection: Not applicable - no database
#   - [WARN] Authentication: Not applicable - validation utilities only
# --------------------------------------------------
