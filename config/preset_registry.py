"""
Preset registry — bundles all simulation presets into a unified format.

Each preset exposes:
  title           : display name
  nodes           : list of (id, ko_label, en_label, color)
  node_ids        : list of node ID strings
  node_labels     : dict {id: Korean label}
  node_colors     : dict {id: hex color}
  default_weights : dict {(id, id): float}
  node_positions  : dict {id: (x, y)}
  node_groups     : dict with keys 'governance', 'core_ops', 'all'
  radar_nodes     : list of node IDs shown in radar chart
  damping_default : float — preset-specific default damping factor
"""

from config.constants import (
    NODES, NODE_IDS, NODE_LABELS_KO, NODE_COLORS, NODE_GROUPS,
    DAMPING_FACTOR,
)
from config.defaults import DEFAULT_WEIGHTS, NODE_POSITIONS
from config.macro_preset import (
    MACRO_NODES, MACRO_NODE_IDS, MACRO_NODE_LABELS, MACRO_NODE_COLORS,
    MACRO_DEFAULT_WEIGHTS, MACRO_NODE_POSITIONS, MACRO_NODE_GROUPS,
    MACRO_RADAR_NODES, MACRO_DAMPING_DEFAULT,
)

PRESETS = {
    "SAP Impact": {
        "title":           "SAP System Impact Simulation",
        "nodes":           NODES,
        "node_ids":        NODE_IDS,
        "node_labels":     NODE_LABELS_KO,
        "node_colors":     NODE_COLORS,
        "default_weights": DEFAULT_WEIGHTS,
        "node_positions":  NODE_POSITIONS,
        "node_groups":     NODE_GROUPS,
        "radar_nodes":     ["sap_basis", "db_hana"],
        "damping_default": DAMPING_FACTOR,
    },
    "Macro System": {
        "title":           "Macro System Shock Simulation",
        "nodes":           MACRO_NODES,
        "node_ids":        MACRO_NODE_IDS,
        "node_labels":     MACRO_NODE_LABELS,
        "node_colors":     MACRO_NODE_COLORS,
        "default_weights": MACRO_DEFAULT_WEIGHTS,
        "node_positions":  MACRO_NODE_POSITIONS,
        "node_groups":     MACRO_NODE_GROUPS,
        "radar_nodes":     MACRO_RADAR_NODES,
        "damping_default": MACRO_DAMPING_DEFAULT,
    },
}

# [SECURE] Whitelist of valid preset names - prevents arbitrary preset injection (Category 1)
PRESET_NAMES = list(PRESETS.keys())


# --------------------------------------------------
# Security Checklist
# Applied:
#   - Input validation: PRESET_NAMES whitelist defined (Category 1)
#   - No hard-coded credentials: Registry contains only structural config (Category 2)
# Not Applied:
#   - [WARN] SQL Injection: Not applicable - no database
#   - [WARN] Authentication: Not applicable - read-only registry
# --------------------------------------------------
