"""
Node definitions, default weights, and simulation parameter boundaries.
"""

# Node definitions: (id, Korean label, English label, color)
NODES = [
    ("ai", "AI", "AI", "#FF6B6B"),
    ("economy", "경제", "Economy", "#4ECDC4"),
    ("finance", "금융", "Finance", "#45B7D1"),
    ("supply_chain", "공급망", "Supply Chain", "#96CEB4"),
    ("internet", "인터넷", "Internet", "#FFEAA7"),
    ("politics", "정치", "Politics", "#DDA0DD"),
    ("diplomacy", "외교", "Diplomacy", "#98D8C8"),
    ("energy", "에너지", "Energy", "#F7DC6F"),
    ("environment", "환경", "Environment", "#82E0AA"),
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
    "political": ["politics", "diplomacy", "economy", "ai"],
    "market": ["economy", "finance", "supply_chain"],
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
