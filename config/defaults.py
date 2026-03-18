"""
Default adjacency matrix and node layout positions.
"""

# Default correlation coefficients between node pairs.
# Values reflect plausible real-world interdependencies.
DEFAULT_WEIGHTS = {
    # AI connections
    ("ai", "economy"): 0.70,
    ("ai", "finance"): 0.55,
    ("ai", "supply_chain"): 0.50,
    ("ai", "internet"): 0.85,
    ("ai", "politics"): 0.35,
    ("ai", "diplomacy"): 0.20,
    ("ai", "energy"): 0.45,
    ("ai", "environment"): 0.30,
    # Economy connections
    ("economy", "finance"): 0.85,
    ("economy", "supply_chain"): 0.75,
    ("economy", "internet"): 0.55,
    ("economy", "politics"): 0.65,
    ("economy", "diplomacy"): 0.50,
    ("economy", "energy"): 0.70,
    ("economy", "environment"): -0.40,
    # Finance connections
    ("finance", "supply_chain"): 0.60,
    ("finance", "internet"): 0.50,
    ("finance", "politics"): 0.55,
    ("finance", "diplomacy"): 0.40,
    ("finance", "energy"): 0.50,
    ("finance", "environment"): -0.30,
    # Supply chain connections
    ("supply_chain", "internet"): 0.60,
    ("supply_chain", "politics"): 0.45,
    ("supply_chain", "diplomacy"): 0.55,
    ("supply_chain", "energy"): 0.65,
    ("supply_chain", "environment"): -0.35,
    # Internet connections
    ("internet", "politics"): 0.40,
    ("internet", "diplomacy"): 0.30,
    ("internet", "energy"): 0.35,
    ("internet", "environment"): 0.15,
    # Politics connections
    ("politics", "diplomacy"): 0.80,
    ("politics", "energy"): 0.50,
    ("politics", "environment"): 0.45,
    # Diplomacy connections
    ("diplomacy", "energy"): 0.45,
    ("diplomacy", "environment"): 0.40,
    # Energy connections
    ("energy", "environment"): -0.60,
}

# Fixed node positions for consistent layout (circular arrangement)
import math

_n_nodes = 9
NODE_POSITIONS = {}
for i, node_id in enumerate([
    "ai", "economy", "finance", "supply_chain", "internet",
    "politics", "diplomacy", "energy", "environment"
]):
    angle = 2 * math.pi * i / _n_nodes - math.pi / 2
    NODE_POSITIONS[node_id] = (math.cos(angle), math.sin(angle))


# --------------------------------------------------
# Security Checklist
# Applied:
#   - No hard-coded credentials: Only simulation default values
# Not Applied:
#   - [WARN] SQL Injection: Not applicable - no database
#   - [WARN] Authentication: Not applicable - default data only
# --------------------------------------------------
