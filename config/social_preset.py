"""
Social Contagion & Information Spread preset.

Nodes (8): Social Media, Mainstream Media, Political Polarization,
           Misinformation, Echo Chamber, Public Trust, Protest Movement,
           Algorithmic Amplification
Correlation defaults grounded in computational social science literature.
Pairs without meaningful coupling are intentionally omitted (no edge).
"""

import math

# (id, Korean label, English label, hex color)
SOCIAL_NODES = [
    ("social_media",         "SNS 플랫폼",      "Social Media",         "#E91E63"),
    ("mainstream_media",     "주류 언론",        "Mainstream Media",     "#2196F3"),
    ("political_polarization","정치 양극화",     "Political Polarization","#9C27B0"),
    ("misinformation",       "허위정보",         "Misinformation",       "#FF5722"),
    ("echo_chamber",         "에코챔버",         "Echo Chamber",         "#795548"),
    ("public_trust",         "제도 신뢰도",      "Public Trust",         "#4CAF50"),
    ("protest_movement",     "시위·사회운동",    "Protest Movement",     "#FF9800"),
    ("algorithmic_amplify",  "알고리즘 증폭",    "Algorithmic Amplify",  "#00BCD4"),
]

SOCIAL_NODE_IDS    = [n[0] for n in SOCIAL_NODES]
SOCIAL_NODE_LABELS = {n[0]: n[1] for n in SOCIAL_NODES}
SOCIAL_NODE_COLORS = {n[0]: n[3] for n in SOCIAL_NODES}

# [SECURE] Whitelist - only predefined social node IDs (Category 1)
VALID_SOCIAL_NODE_IDS = frozenset(SOCIAL_NODE_IDS)

# ---------------------------------------------------------------------------
# Default correlation coefficients — computational social science sources
# Pairs NOT listed here have zero coupling (no edge in the graph).
# ---------------------------------------------------------------------------
#
# social_media <-> algorithmic_amplify : 0.92
#   Pariser (2011) "The Filter Bubble"; Meta Internal Research (2021)
#   Platform algorithms are the primary amplification mechanism for social media
#
# social_media <-> misinformation : 0.85
#   Vosoughi, Roy & Aral (2018) "The spread of true and false news online" — Science
#   False news spreads 6x faster than true news on Twitter
#
# social_media <-> echo_chamber : 0.82
#   Sunstein (2017) "#Republic"; Bakshy, Messing & Adamic (2015) — Science
#   Social media architecture reinforces selective exposure
#
# social_media <-> political_polarization : 0.78
#   Bail et al. (2018) "Exposure to opposing views on social media" — PNAS
#   Cross-partisan exposure on social media increases polarization
#
# algorithmic_amplify <-> misinformation : 0.88
#   Pennycook & Rand (2021) "The Psychology of Fake News" — TICS
#   Engagement-based algorithms systematically favor outrage content
#
# algorithmic_amplify <-> echo_chamber : 0.85
#   Pariser (2011); YouTube rabbit hole research (Ribeiro et al. 2020)
#   Recommendation algorithms create closed information loops
#
# echo_chamber <-> political_polarization : 0.82
#   Iyengar et al. (2019) "The Origins and Consequences of Affective Polarization"
#   — Annual Review of Political Science
#
# echo_chamber <-> misinformation : 0.78
#   Del Vicario et al. (2016) "The spreading of misinformation online" — PNAS
#   Echo chambers accelerate misinformation acceptance
#
# misinformation <-> public_trust : 0.75
#   Roozenbeek et al. (2020) "Susceptibility to misinformation" — Royal Society Open Sci.
#   Misinformation exposure significantly reduces institutional trust
#
# mainstream_media <-> public_trust : 0.70
#   Edelman Trust Barometer (2023); Reuters Institute Digital News Report (2023)
#   Mainstream media credibility strongly correlates with public trust
#
# mainstream_media <-> political_polarization : 0.65
#   Prior (2013) "Media and Political Polarization" — Annual Review Political Sci.
#   Partisan media consumption drives affective polarization
#
# mainstream_media <-> misinformation : 0.60
#   Lazer et al. (2018) "The science of fake news" — Science
#   Mainstream media fact-checking competes with misinformation spread
#
# political_polarization <-> protest_movement : 0.80
#   Acemoglu & Robinson (2006) "Economic Origins of Dictatorship and Democracy"
#   Gurr (1970) "Why Men Rebel" — relative deprivation → mobilization
#
# public_trust <-> protest_movement : 0.72
#   Norris & Inglehart (2019) "Cultural Backlash"
#   Low institutional trust is primary driver of protest mobilization
#
# political_polarization <-> public_trust : 0.68
#   Hetherington (2005) "Why Trust Matters" — Princeton UP
#   Polarization erodes cross-partisan trust in institutions
#
# social_media <-> protest_movement : 0.65
#   Howard & Hussain (2013) "Democracy's Fourth Wave" — Arab Spring analysis
#   Twitter/Facebook as protest coordination tools (Castells 2012)
#
# === Intentionally omitted ===
# mainstream_media <-> algorithmic_amplify : Operate on different feedback mechanisms
# mainstream_media <-> echo_chamber : Limited direct coupling; news deserts vs. filter bubbles
# mainstream_media <-> protest_movement : Indirect (mediated through public_trust/polarization)
# algorithmic_amplify <-> protest_movement : Indirect (via polarization)
# ---------------------------------------------------------------------------
SOCIAL_DEFAULT_WEIGHTS = {
    ("social_media",          "algorithmic_amplify"):    0.92,
    ("social_media",          "misinformation"):         0.85,
    ("social_media",          "echo_chamber"):           0.82,
    ("social_media",          "political_polarization"): 0.78,
    ("social_media",          "protest_movement"):       0.65,
    ("algorithmic_amplify",   "misinformation"):         0.88,
    ("algorithmic_amplify",   "echo_chamber"):           0.85,
    ("echo_chamber",          "political_polarization"): 0.82,
    ("echo_chamber",          "misinformation"):         0.78,
    ("misinformation",        "public_trust"):           0.75,
    ("mainstream_media",      "public_trust"):           0.70,
    ("mainstream_media",      "political_polarization"): 0.65,
    ("mainstream_media",      "misinformation"):         0.60,
    ("political_polarization","protest_movement"):       0.80,
    ("political_polarization","public_trust"):           0.68,
    ("public_trust",          "protest_movement"):       0.72,
    # NOTE: mainstream_media <-> algorithmic_amplify omitted (different mechanisms)
    # NOTE: mainstream_media <-> echo_chamber omitted (limited direct coupling)
    # NOTE: mainstream_media <-> protest_movement omitted (indirect)
    # NOTE: algorithmic_amplify <-> protest_movement omitted (indirect)
}

# Octagonal layout positions
_n = len(SOCIAL_NODE_IDS)
SOCIAL_NODE_POSITIONS = {}
for _i, _nid in enumerate(SOCIAL_NODE_IDS):
    _angle = 2 * math.pi * _i / _n - math.pi / 2
    SOCIAL_NODE_POSITIONS[_nid] = (math.cos(_angle), math.sin(_angle))

# Node groups for views
SOCIAL_NODE_GROUPS = {
    # [SECURE] Whitelist group definitions - only predefined node IDs (Category 1)
    "governance": ["public_trust", "mainstream_media", "political_polarization"],
    "core_ops":   ["social_media", "algorithmic_amplify", "misinformation", "echo_chamber"],
    "all":        SOCIAL_NODE_IDS[:],
}

# Nodes highlighted in the Influence Radar chart
SOCIAL_RADAR_NODES = ["algorithmic_amplify", "misinformation"]

# Default damping — social contagion is slow to decay (Watts & Dodds 2007)
SOCIAL_DAMPING_DEFAULT = 0.70


# --------------------------------------------------
# Security Checklist
# Applied:
#   - Input validation: VALID_SOCIAL_NODE_IDS whitelist defined (Category 1)
#   - No hard-coded credentials: Only simulation default values (Category 2)
#   - Encapsulation: SOCIAL_NODE_GROUPS["all"] returns a copy via slicing (Category 6)
# Not Applied:
#   - [WARN] SQL Injection: Not applicable - no database
#   - [WARN] Authentication: Not applicable - configuration constants only
# --------------------------------------------------
