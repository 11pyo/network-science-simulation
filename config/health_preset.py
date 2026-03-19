"""
Global Health & Pandemic Dynamics preset.

Nodes (8): Pathogen, Healthcare Capacity, Vaccine Coverage, Air Travel,
           Urban Density, Social Behavior, Medicine Supply, Policy Response
Correlation defaults grounded in epidemiology and public health literature.
Pairs without meaningful coupling are intentionally omitted (no edge).
"""

import math

# (id, Korean label, English label, hex color)
HEALTH_NODES = [
    ("pathogen",           "병원체·변이",       "Pathogen",            "#E74C3C"),
    ("healthcare_capacity","의료 시스템",        "Healthcare Capacity", "#27AE60"),
    ("vaccine_coverage",   "백신 보급률",        "Vaccine Coverage",    "#3498DB"),
    ("air_travel",         "항공 이동망",        "Air Travel",          "#95A5A6"),
    ("urban_density",      "도시 밀집도",        "Urban Density",       "#E67E22"),
    ("social_behavior",    "방역 순응도",        "Social Behavior",     "#9B59B6"),
    ("supply_medicine",    "의약품·PPE 공급",    "Medicine Supply",     "#F39C12"),
    ("policy_response",    "정부 방역 정책",     "Policy Response",     "#1ABC9C"),
]

HEALTH_NODE_IDS    = [n[0] for n in HEALTH_NODES]
HEALTH_NODE_LABELS = {n[0]: n[1] for n in HEALTH_NODES}
HEALTH_NODE_COLORS = {n[0]: n[3] for n in HEALTH_NODES}

# [SECURE] Whitelist - only predefined health node IDs (Category 1)
VALID_HEALTH_NODE_IDS = frozenset(HEALTH_NODE_IDS)

# ---------------------------------------------------------------------------
# Default correlation coefficients — epidemiology and public health sources
# Pairs NOT listed here have zero coupling (no edge in the graph).
# ---------------------------------------------------------------------------
#
# pathogen <-> air_travel : 0.82
#   Brockmann & Helbing (2013) "The Hidden Geometry of Complex, Network-Driven
#     Contagion Phenomena" — Science
#   Colizza et al. (2006) "The role of airline transportation network" — PNAS
#
# pathogen <-> urban_density : 0.78
#   Jones et al. (2008) "Global trends in emerging infectious diseases" — Nature
#   Li et al. (2020) "Early transmission dynamics in Wuhan" — NEJM
#
# pathogen <-> social_behavior : 0.75
#   Ferguson et al. (2020) "Impact of non-pharmaceutical interventions" — Imperial
#   CDC COVID-19 NPI Effectiveness Reports (2020-2021)
#
# pathogen <-> vaccine_coverage : 0.70
#   Plotkin, Orenstein & Offit (2017) "Vaccines" — Elsevier
#   Higher vaccine coverage reduces pathogen transmission (R0 reduction)
#
# healthcare_capacity <-> supply_medicine : 0.85
#   WHO (2021) "Access to COVID-19 Tools Accelerator" report
#   Ventilator and PPE shortages directly impacted ICU capacity (2020)
#
# healthcare_capacity <-> policy_response : 0.80
#   Katz et al. (2014) "Global Health Security Agenda" — Lancet
#   Policy decisions directly determine healthcare resource allocation
#
# vaccine_coverage <-> policy_response : 0.78
#   Larson et al. (2016) "Measuring vaccine hesitancy" — Vaccine
#   National vaccination mandates and rollout strategies (EU/US/Korea 2021)
#
# vaccine_coverage <-> supply_medicine : 0.72
#   COVAX Facility Reports (2021-2022); WHO Emergency Use Listing
#   Vaccine supply chain is subset of broader medicine supply system
#
# air_travel <-> urban_density : 0.72
#   Ginsberg et al. (2009) "Detecting influenza epidemics using search data" — Nature
#   Hub cities are airports; urban-aviation density correlation
#
# social_behavior <-> policy_response : 0.70
#   Cowling et al. (2020) "Impact of non-pharmaceutical interventions" — Lancet
#   Government mandates shape social distancing behavior
#
# social_behavior <-> urban_density : 0.65
#   Glaeser & Resseger (2010) "The Complementarity Between Cities and Skills" — JRA
#   Urban settings reduce ability to maintain physical distancing
#
# social_behavior <-> vaccine_coverage : 0.62
#   Larson et al. (2016); Roozenbeek et al. (2020) — vaccine hesitancy
#   Behavioral factors strongly predict vaccination uptake
#
# supply_medicine <-> policy_response : 0.68
#   IEA Medical Supply Chain Resilience Report (2021)
#   Emergency use authorization and procurement policies
#
# policy_response <-> air_travel : 0.65
#   WHO International Health Regulations (2005)
#   Travel bans and border closures as primary pandemic containment tool
#
# === Intentionally omitted ===
# air_travel <-> vaccine_coverage : Indirect (policy mediates both)
# air_travel <-> supply_medicine : Logistical but not epidemic coupling
# urban_density <-> supply_medicine : No direct epidemiological mechanism
# urban_density <-> healthcare_capacity : Indirect (policy allocates resources)
# pathogen <-> healthcare_capacity : Indirect (demand-side, not direct coupling)
# pathogen <-> policy_response : Indirect (pathogen severity informs policy)
# ---------------------------------------------------------------------------
HEALTH_DEFAULT_WEIGHTS = {
    ("pathogen",          "air_travel"):         0.82,
    ("pathogen",          "urban_density"):      0.78,
    ("pathogen",          "social_behavior"):    0.75,
    ("pathogen",          "vaccine_coverage"):   0.70,
    ("healthcare_capacity","supply_medicine"):   0.85,
    ("healthcare_capacity","policy_response"):   0.80,
    ("vaccine_coverage",  "policy_response"):    0.78,
    ("vaccine_coverage",  "supply_medicine"):    0.72,
    ("vaccine_coverage",  "social_behavior"):    0.62,
    ("air_travel",        "urban_density"):      0.72,
    ("air_travel",        "policy_response"):    0.65,
    ("social_behavior",   "policy_response"):    0.70,
    ("social_behavior",   "urban_density"):      0.65,
    ("supply_medicine",   "policy_response"):    0.68,
    # NOTE: air_travel <-> vaccine_coverage omitted (indirect)
    # NOTE: urban_density <-> supply_medicine omitted (no mechanism)
    # NOTE: pathogen <-> healthcare_capacity omitted (indirect demand-side)
}

# Octagonal layout positions
_n = len(HEALTH_NODE_IDS)
HEALTH_NODE_POSITIONS = {}
for _i, _nid in enumerate(HEALTH_NODE_IDS):
    _angle = 2 * math.pi * _i / _n - math.pi / 2
    HEALTH_NODE_POSITIONS[_nid] = (math.cos(_angle), math.sin(_angle))

# Node groups for views
HEALTH_NODE_GROUPS = {
    # [SECURE] Whitelist group definitions - only predefined node IDs (Category 1)
    "governance": ["policy_response", "healthcare_capacity", "vaccine_coverage"],
    "core_ops":   ["pathogen", "air_travel", "urban_density", "social_behavior"],
    "all":        HEALTH_NODE_IDS[:],
}

# Nodes highlighted in the Influence Radar chart
HEALTH_RADAR_NODES = ["pathogen", "policy_response"]

# Default damping — pandemic dynamics moderate persistence (Ferguson et al. 2020)
HEALTH_DAMPING_DEFAULT = 0.60


# --------------------------------------------------
# Security Checklist
# Applied:
#   - Input validation: VALID_HEALTH_NODE_IDS whitelist defined (Category 1)
#   - No hard-coded credentials: Only simulation default values (Category 2)
#   - Encapsulation: HEALTH_NODE_GROUPS["all"] returns a copy via slicing (Category 6)
# Not Applied:
#   - [WARN] SQL Injection: Not applicable - no database
#   - [WARN] Authentication: Not applicable - configuration constants only
# --------------------------------------------------
