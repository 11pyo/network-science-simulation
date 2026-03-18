"""
Shared formatting and color mapping utilities.
"""

from config.constants import NODE_LABELS_KO, NODE_LABELS_EN, VALID_NODE_IDS
from utils.validators import validate_node_id


def get_node_label(node_id: str, lang: str = "ko") -> str:
    """Return display label for a node."""
    # [SECURE] Whitelist validation - prevents arbitrary node ID (Category 1)
    validate_node_id(node_id)
    if lang == "en":
        return NODE_LABELS_EN.get(node_id, node_id)
    return NODE_LABELS_KO.get(node_id, node_id)


def weight_to_color(weight: float) -> str:
    """Map correlation coefficient to a color (red=negative, blue=positive, gray=zero)."""
    if weight > 0.05:
        intensity = min(int(abs(weight) * 255), 255)
        return f"rgba(41, 128, 185, {abs(weight):.2f})"
    elif weight < -0.05:
        intensity = min(int(abs(weight) * 255), 255)
        return f"rgba(231, 76, 60, {abs(weight):.2f})"
    else:
        return "rgba(149, 165, 166, 0.3)"


def weight_to_width(weight: float) -> float:
    """Map absolute weight to edge line width."""
    return max(0.5, abs(weight) * 5.0)


def format_percentage(value: float) -> str:
    """Format a float as a display percentage."""
    return f"{value * 100:+.1f}%"


def impact_to_color(value: float) -> str:
    """Map impact value to color for node visualization."""
    if value > 0.01:
        return f"rgba(231, 76, 60, {min(abs(value), 1.0):.2f})"
    elif value < -0.01:
        return f"rgba(41, 128, 185, {min(abs(value), 1.0):.2f})"
    else:
        return "rgba(149, 165, 166, 0.5)"


# --------------------------------------------------
# Security Checklist
# Applied:
#   - Input validation: node_id validated via whitelist (Category 1)
# Not Applied:
#   - [WARN] SQL Injection: Not applicable - no database
#   - [WARN] Authentication: Not applicable - formatting utilities only
# --------------------------------------------------
