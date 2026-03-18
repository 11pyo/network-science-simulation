"""
Default adjacency matrix and node layout positions.
SAP BC / Middleware / SAP Operations context.
"""

# Default correlation coefficients between node pairs.
# Values reflect SAP system interdependencies.
DEFAULT_WEIGHTS = {
    # SAP Basis connections - core infrastructure hub
    ("sap_basis", "sap_abap"): 0.80,
    ("sap_basis", "fi_co"): 0.60,
    ("sap_basis", "mm_sd"): 0.55,
    ("sap_basis", "middleware"): 0.80,
    ("sap_basis", "auth_mgmt"): 0.70,
    ("sap_basis", "external"): 0.40,
    ("sap_basis", "db_hana"): 0.90,
    ("sap_basis", "infra_os"): 0.85,
    # SAP ABAP connections - development & custom code
    ("sap_abap", "fi_co"): 0.65,
    ("sap_abap", "mm_sd"): 0.60,
    ("sap_abap", "middleware"): 0.50,
    ("sap_abap", "auth_mgmt"): 0.45,
    ("sap_abap", "external"): 0.30,
    ("sap_abap", "db_hana"): 0.70,
    ("sap_abap", "infra_os"): -0.20,
    # FI/CO connections - financial module
    ("fi_co", "mm_sd"): 0.75,
    ("fi_co", "middleware"): 0.55,
    ("fi_co", "auth_mgmt"): 0.60,
    ("fi_co", "external"): 0.45,
    ("fi_co", "db_hana"): 0.50,
    ("fi_co", "infra_os"): 0.20,
    # MM/SD connections - logistics module
    ("mm_sd", "middleware"): 0.65,
    ("mm_sd", "auth_mgmt"): 0.40,
    ("mm_sd", "external"): 0.55,
    ("mm_sd", "db_hana"): 0.45,
    ("mm_sd", "infra_os"): 0.20,
    # Middleware connections - RFC/PI/PO/API
    ("middleware", "auth_mgmt"): 0.35,
    ("middleware", "external"): 0.75,
    ("middleware", "db_hana"): 0.40,
    ("middleware", "infra_os"): 0.50,
    # Auth Management connections
    ("auth_mgmt", "external"): 0.50,
    ("auth_mgmt", "db_hana"): 0.25,
    ("auth_mgmt", "infra_os"): 0.15,
    # External interface connections
    ("external", "db_hana"): 0.20,
    ("external", "infra_os"): 0.25,
    # DB/HANA connections
    ("db_hana", "infra_os"): 0.80,
}

# Fixed node positions for consistent layout (circular arrangement)
import math

_n_nodes = 9
NODE_POSITIONS = {}
for i, node_id in enumerate([
    "sap_basis", "sap_abap", "fi_co", "mm_sd", "middleware",
    "auth_mgmt", "external", "db_hana", "infra_os"
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
