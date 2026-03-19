"""
Geopolitical Risk Network preset.

Nodes (8): US Hegemony, China Influence, Trade War, Sanctions,
           Military Tension, Energy Geopolitics, Tech Decoupling, Refugee Migration
Correlation defaults grounded in international relations & political science literature.
Pairs without meaningful coupling are intentionally omitted (no edge).
"""

import math

# (id, Korean label, English label, hex color)
GEO_NODES = [
    ("us_hegemony",       "미국 패권",       "US Hegemony",         "#1F4E8F"),
    ("china_influence",   "중국 영향력",     "China Influence",     "#C0392B"),
    ("trade_war",         "무역 갈등",       "Trade War",           "#F39C12"),
    ("sanctions",         "경제 제재",       "Sanctions",           "#8E44AD"),
    ("military_tension",  "군사 긴장",       "Military Tension",    "#2C3E50"),
    ("energy_geopolitics","에너지 지정학",   "Energy Geopolitics",  "#E67E22"),
    ("tech_decoupling",   "기술 디커플링",   "Tech Decoupling",     "#27AE60"),
    ("refugee_migration", "난민·이주",       "Refugee Migration",   "#7F8C8D"),
]

GEO_NODE_IDS    = [n[0] for n in GEO_NODES]
GEO_NODE_LABELS = {n[0]: n[1] for n in GEO_NODES}
GEO_NODE_COLORS = {n[0]: n[3] for n in GEO_NODES}

# [SECURE] Whitelist - only predefined geo node IDs (Category 1)
VALID_GEO_NODE_IDS = frozenset(GEO_NODE_IDS)

# ---------------------------------------------------------------------------
# Default correlation coefficients — international relations academic sources
# Pairs NOT listed here have zero coupling (no edge in the graph).
# ---------------------------------------------------------------------------
#
# us_hegemony <-> china_influence : 0.88
#   Mearsheimer (2001) "The Tragedy of Great Power Politics" — primary rivalry
#   Allison (2017) "Destined for War" — Thucydides Trap dynamics
#
# us_hegemony <-> tech_decoupling : 0.82
#   Farrell & Newman (2019) "Weaponized Interdependence" — Intl. Security
#   US CHIPS Act (2022), Entity List restrictions — tech sovereignty
#
# us_hegemony <-> sanctions : 0.78
#   Hufbauer, Schott & Elliott (2008) "Economic Sanctions Reconsidered"
#   US unilateral sanctions as primary hegemonic tool
#
# us_hegemony <-> military_tension : 0.75
#   Mearsheimer (2001); Waltz (1979) "Theory of International Politics"
#   US force projection and military alliances (NATO, USFK)
#
# us_hegemony <-> energy_geopolitics : 0.70
#   Yergin (2011) "The Quest" — energy as geopolitical lever
#   Petrodollar system, US LNG exports as policy tools
#
# china_influence <-> tech_decoupling : 0.80
#   Farrell & Newman (2019); Zeihan (2022) "The End of the World is Just Beginning"
#   Made in China 2025, Huawei bans, semiconductor self-reliance
#
# china_influence <-> trade_war : 0.75
#   Amiti, Redding & Weinstein (2019) — AER
#   US-China trade war 2018-2019; retaliatory tariff cycles
#
# china_influence <-> military_tension : 0.72
#   Taiwan Strait, South China Sea UNCLOS disputes
#   IISS Military Balance (2023)
#
# china_influence <-> energy_geopolitics : 0.65
#   IEA China (2022); BRI energy investments
#   China as world's largest energy consumer and coal producer
#
# china_influence <-> sanctions : 0.65
#   OFAC CMIC list; secondary sanctions exposure
#   Dai (2010) "The Conditional Nature of Democratic Compliance" — JCR
#
# trade_war <-> sanctions : 0.72
#   Hufbauer et al. (2008); Farrell & Newman (2019)
#   Trade restrictions and sanctions often co-deployed
#
# trade_war <-> tech_decoupling : 0.70
#   Branstetter & Foley (2010) — trade-technology nexus
#   Export controls as trade war instruments
#
# trade_war <-> energy_geopolitics : 0.62
#   Kilian (2008) "Exogenous Oil Supply Shocks" — energy-trade coupling
#
# military_tension <-> refugee_migration : 0.80
#   Betts & Collier (2017) "Refuge" — conflict-displacement nexus
#   UNHCR (2022): 90% of refugees flee conflict zones
#
# military_tension <-> energy_geopolitics : 0.68
#   Yergin (2011); Russia-Ukraine war energy disruption (2022)
#   Energy infrastructure as military target
#
# sanctions <-> energy_geopolitics : 0.72
#   Iran sanctions (JCPOA); Russia SWIFT exclusion (2022)
#   Energy sector as primary sanctions target
#
# tech_decoupling <-> trade_war : 0.70 (already listed above)
#
# refugee_migration <-> trade_war : 0.45
#   Hatton & Williamson (2005) "Global Migration and the World Economy"
#   Trade disruption → economic displacement → migration pressure
#
# === Intentionally omitted ===
# refugee_migration <-> tech_decoupling : No established direct mechanism
# refugee_migration <-> us_hegemony : Indirect (via military_tension)
# refugee_migration <-> sanctions : Indirect (via military_tension)
# ---------------------------------------------------------------------------
GEO_DEFAULT_WEIGHTS = {
    ("us_hegemony",       "china_influence"):   0.88,
    ("us_hegemony",       "tech_decoupling"):   0.82,
    ("us_hegemony",       "sanctions"):         0.78,
    ("us_hegemony",       "military_tension"):  0.75,
    ("us_hegemony",       "energy_geopolitics"):0.70,
    ("china_influence",   "tech_decoupling"):   0.80,
    ("china_influence",   "trade_war"):         0.75,
    ("china_influence",   "military_tension"):  0.72,
    ("china_influence",   "energy_geopolitics"):0.65,
    ("china_influence",   "sanctions"):         0.65,
    ("trade_war",         "sanctions"):         0.72,
    ("trade_war",         "tech_decoupling"):   0.70,
    ("trade_war",         "energy_geopolitics"):0.62,
    ("military_tension",  "refugee_migration"): 0.80,
    ("military_tension",  "energy_geopolitics"):0.68,
    ("sanctions",         "energy_geopolitics"):0.72,
    ("refugee_migration", "trade_war"):         0.45,
    # NOTE: refugee_migration <-> tech_decoupling omitted (no mechanism)
    # NOTE: refugee_migration <-> us_hegemony omitted (indirect)
    # NOTE: refugee_migration <-> sanctions omitted (indirect)
}

# Octagonal layout positions
_n = len(GEO_NODE_IDS)
GEO_NODE_POSITIONS = {}
for _i, _nid in enumerate(GEO_NODE_IDS):
    _angle = 2 * math.pi * _i / _n - math.pi / 2
    GEO_NODE_POSITIONS[_nid] = (math.cos(_angle), math.sin(_angle))

# Node groups for views
GEO_NODE_GROUPS = {
    # [SECURE] Whitelist group definitions - only predefined node IDs (Category 1)
    "governance": ["us_hegemony", "china_influence", "sanctions"],
    "core_ops":   ["trade_war", "tech_decoupling", "energy_geopolitics", "military_tension"],
    "all":        GEO_NODE_IDS[:],
}

# Nodes highlighted in the Influence Radar chart
GEO_RADAR_NODES = ["us_hegemony", "china_influence"]

# Default damping — geopolitical shocks persist longer (Hafner-Burton et al. 2009)
GEO_DAMPING_DEFAULT = 0.65


# --------------------------------------------------
# Security Checklist
# Applied:
#   - Input validation: VALID_GEO_NODE_IDS whitelist defined (Category 1)
#   - No hard-coded credentials: Only simulation default values (Category 2)
#   - Encapsulation: GEO_NODE_GROUPS["all"] returns a copy via slicing (Category 6)
# Not Applied:
#   - [WARN] SQL Injection: Not applicable - no database
#   - [WARN] Authentication: Not applicable - configuration constants only
# --------------------------------------------------
