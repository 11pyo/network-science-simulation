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
from config.physics_preset import (
    PHYSICS_NODES, PHYSICS_NODE_IDS, PHYSICS_NODE_LABELS, PHYSICS_NODE_COLORS,
    PHYSICS_DEFAULT_WEIGHTS, PHYSICS_NODE_POSITIONS, PHYSICS_NODE_GROUPS,
    PHYSICS_RADAR_NODES, PHYSICS_DAMPING_DEFAULT,
)
from config.geo_preset import (
    GEO_NODES, GEO_NODE_IDS, GEO_NODE_LABELS, GEO_NODE_COLORS,
    GEO_DEFAULT_WEIGHTS, GEO_NODE_POSITIONS, GEO_NODE_GROUPS,
    GEO_RADAR_NODES, GEO_DAMPING_DEFAULT,
)
from config.cyber_preset import (
    CYBER_NODES, CYBER_NODE_IDS, CYBER_NODE_LABELS, CYBER_NODE_COLORS,
    CYBER_DEFAULT_WEIGHTS, CYBER_NODE_POSITIONS, CYBER_NODE_GROUPS,
    CYBER_RADAR_NODES, CYBER_DAMPING_DEFAULT,
)
from config.social_preset import (
    SOCIAL_NODES, SOCIAL_NODE_IDS, SOCIAL_NODE_LABELS, SOCIAL_NODE_COLORS,
    SOCIAL_DEFAULT_WEIGHTS, SOCIAL_NODE_POSITIONS, SOCIAL_NODE_GROUPS,
    SOCIAL_RADAR_NODES, SOCIAL_DAMPING_DEFAULT,
)
from config.health_preset import (
    HEALTH_NODES, HEALTH_NODE_IDS, HEALTH_NODE_LABELS, HEALTH_NODE_COLORS,
    HEALTH_DEFAULT_WEIGHTS, HEALTH_NODE_POSITIONS, HEALTH_NODE_GROUPS,
    HEALTH_RADAR_NODES, HEALTH_DAMPING_DEFAULT,
)
from config.bio_preset import (
    BIO_NODES, BIO_NODE_IDS, BIO_NODE_LABELS, BIO_NODE_COLORS,
    BIO_DEFAULT_WEIGHTS, BIO_NODE_POSITIONS, BIO_NODE_GROUPS,
    BIO_RADAR_NODES, BIO_DAMPING_DEFAULT,
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
    "Complex Physics": {
        "title":           "Complex Systems Physics Simulation",
        "nodes":           PHYSICS_NODES,
        "node_ids":        PHYSICS_NODE_IDS,
        "node_labels":     PHYSICS_NODE_LABELS,
        "node_colors":     PHYSICS_NODE_COLORS,
        "default_weights": PHYSICS_DEFAULT_WEIGHTS,
        "node_positions":  PHYSICS_NODE_POSITIONS,
        "node_groups":     PHYSICS_NODE_GROUPS,
        "radar_nodes":     PHYSICS_RADAR_NODES,
        "damping_default": PHYSICS_DAMPING_DEFAULT,
    },
    "Geopolitical Risk": {
        "title":           "Geopolitical Risk Network Simulation",
        "nodes":           GEO_NODES,
        "node_ids":        GEO_NODE_IDS,
        "node_labels":     GEO_NODE_LABELS,
        "node_colors":     GEO_NODE_COLORS,
        "default_weights": GEO_DEFAULT_WEIGHTS,
        "node_positions":  GEO_NODE_POSITIONS,
        "node_groups":     GEO_NODE_GROUPS,
        "radar_nodes":     GEO_RADAR_NODES,
        "damping_default": GEO_DAMPING_DEFAULT,
    },
    "Cyber Security": {
        "title":           "Cyber Security Threat Propagation",
        "nodes":           CYBER_NODES,
        "node_ids":        CYBER_NODE_IDS,
        "node_labels":     CYBER_NODE_LABELS,
        "node_colors":     CYBER_NODE_COLORS,
        "default_weights": CYBER_DEFAULT_WEIGHTS,
        "node_positions":  CYBER_NODE_POSITIONS,
        "node_groups":     CYBER_NODE_GROUPS,
        "radar_nodes":     CYBER_RADAR_NODES,
        "damping_default": CYBER_DAMPING_DEFAULT,
    },
    "Social Contagion": {
        "title":           "Social Contagion & Information Spread",
        "nodes":           SOCIAL_NODES,
        "node_ids":        SOCIAL_NODE_IDS,
        "node_labels":     SOCIAL_NODE_LABELS,
        "node_colors":     SOCIAL_NODE_COLORS,
        "default_weights": SOCIAL_DEFAULT_WEIGHTS,
        "node_positions":  SOCIAL_NODE_POSITIONS,
        "node_groups":     SOCIAL_NODE_GROUPS,
        "radar_nodes":     SOCIAL_RADAR_NODES,
        "damping_default": SOCIAL_DAMPING_DEFAULT,
    },
    "Global Health": {
        "title":           "Global Health & Pandemic Dynamics",
        "nodes":           HEALTH_NODES,
        "node_ids":        HEALTH_NODE_IDS,
        "node_labels":     HEALTH_NODE_LABELS,
        "node_colors":     HEALTH_NODE_COLORS,
        "default_weights": HEALTH_DEFAULT_WEIGHTS,
        "node_positions":  HEALTH_NODE_POSITIONS,
        "node_groups":     HEALTH_NODE_GROUPS,
        "radar_nodes":     HEALTH_RADAR_NODES,
        "damping_default": HEALTH_DAMPING_DEFAULT,
    },
    "Biogenetics": {
        "title":           "Biogenetics & Molecular Network",
        "nodes":           BIO_NODES,
        "node_ids":        BIO_NODE_IDS,
        "node_labels":     BIO_NODE_LABELS,
        "node_colors":     BIO_NODE_COLORS,
        "default_weights": BIO_DEFAULT_WEIGHTS,
        "node_positions":  BIO_NODE_POSITIONS,
        "node_groups":     BIO_NODE_GROUPS,
        "radar_nodes":     BIO_RADAR_NODES,
        "damping_default": BIO_DAMPING_DEFAULT,
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
