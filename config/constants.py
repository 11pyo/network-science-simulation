"""
Node definitions, default weights, and simulation parameter boundaries.
SAP BC / Middleware / SAP Operations context.
"""

# Node definitions: (id, Korean label, English label, color)
NODES = [
    ("sap_basis", "SAP Basis", "SAP Basis", "#FF6B6B"),
    ("sap_abap", "SAP ABAP", "SAP ABAP", "#4ECDC4"),
    ("fi_co", "FI/CO", "FI/CO", "#45B7D1"),
    ("mm_sd", "MM/SD", "MM/SD", "#96CEB4"),
    ("middleware", "미들웨어", "Middleware", "#FFEAA7"),
    ("auth_mgmt", "권한관리", "Auth Mgmt", "#DDA0DD"),
    ("external", "외부연계", "External", "#98D8C8"),
    ("db_hana", "DB/HANA", "DB/HANA", "#F7DC6F"),
    ("infra_os", "Infra/OS", "Infra/OS", "#82E0AA"),
]

NODE_IDS = [n[0] for n in NODES]
NODE_LABELS_KO = {n[0]: n[1] for n in NODES}
NODE_LABELS_EN = {n[0]: n[2] for n in NODES}
NODE_COLORS = {n[0]: n[3] for n in NODES}

# [SECURE] Whitelist for input validation - prevents arbitrary node ID injection (Category 1)
VALID_NODE_IDS = frozenset(NODE_IDS)

# Weight boundaries
WEIGHT_MIN = -1.0
WEIGHT_MAX = 1.0
WEIGHT_STEP = 0.05

# Shock boundaries
SHOCK_MIN = -1.0
SHOCK_MAX = 1.0

# [SECURE] Max iteration cap - prevents infinite loop (Category 3)
MAX_SIMULATION_STEPS = 20
DEFAULT_SIMULATION_STEPS = 10

DAMPING_FACTOR = 0.5
CONVERGENCE_THRESHOLD = 0.001

# Node groups for views
NODE_GROUPS = {
    # [SECURE] Whitelist group definitions - only predefined node IDs (Category 1)
    "governance": ["auth_mgmt", "external", "sap_basis", "sap_abap"],
    "core_ops": ["sap_basis", "db_hana", "middleware"],
    "business": ["fi_co", "mm_sd", "sap_abap"],
    "all": NODE_IDS[:],
}

# [SECURE] Whitelist for centrality methods - prevents code injection (Category 1)
VALID_CENTRALITY_METHODS = frozenset({"degree", "betweenness", "eigenvector"})


# --------------------------------------------------
# Security Checklist
# Applied:
#   - Input validation: VALID_NODE_IDS and VALID_CENTRALITY_METHODS whitelists defined
#   - Infinite loop prevention: MAX_SIMULATION_STEPS = 20
#   - Encapsulation: NODE_GROUPS["all"] returns a copy via slicing
# Not Applied:
#   - [WARN] SQL Injection: Not applicable - no database
#   - [WARN] Authentication: Not applicable - configuration constants only
# --------------------------------------------------
