"""
Political/diplomatic impact visualization.
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np

from config.constants import NODE_LABELS_KO, NODE_COLORS, NODE_IDS, NODE_GROUPS
from models.simulation import ShockSimulator
from utils.helpers import format_percentage


def render_political_view(network, simulation_results=None):
    """Render governance & impact analysis view."""

    st.header("Governance & Impact Analysis")

    governance_nodes = NODE_GROUPS["governance"]

    # --- Correlation Heatmap ---
    st.subheader("System Correlation Matrix")

    adj = network.get_adjacency_dict()
    all_nodes = network.get_nodes()

    # Build matrix for all nodes with political focus
    matrix_data = []
    for n in all_nodes:
        row = []
        for m in all_nodes:
            if n == m:
                row.append(1.0)
            else:
                w = adj.get(n, {}).get(m, 0.0)
                row.append(w)
        matrix_data.append(row)

    labels = [NODE_LABELS_KO.get(n, n) for n in all_nodes]

    fig_heatmap = go.Figure(data=go.Heatmap(
        z=matrix_data,
        x=labels,
        y=labels,
        colorscale="RdBu_r",
        zmid=0,
        text=[[f"{v:.2f}" for v in row] for row in matrix_data],
        texttemplate="%{text}",
        hovertemplate="%{y} - %{x}: %{z:.2f}<extra></extra>",
    ))
    fig_heatmap.update_layout(
        height=450,
        margin=dict(l=20, r=20, t=20, b=20),
    )
    st.plotly_chart(fig_heatmap, width="stretch")

    if simulation_results is not None:
        max_step = ShockSimulator.get_max_step(simulation_results)
        final_impacts = ShockSimulator.get_final_impacts(simulation_results)

        st.subheader("Shock Impact by Node")

        # Bar chart of final impacts
        impact_df = pd.DataFrame([
            {
                "node": NODE_LABELS_KO.get(n, n),
                "impact": final_impacts.get(n, 0.0),
                "color": NODE_COLORS.get(n, "#888"),
            }
            for n in all_nodes
        ])
        impact_df = impact_df.sort_values("impact", ascending=True)

        fig_bar = go.Figure(data=go.Bar(
            x=impact_df["impact"],
            y=impact_df["node"],
            orientation="h",
            marker_color=[
                "rgba(231,76,60,0.8)" if v > 0 else "rgba(41,128,185,0.8)"
                for v in impact_df["impact"]
            ],
            text=[format_percentage(v) for v in impact_df["impact"]],
            textposition="auto",
        ))
        fig_bar.update_layout(
            xaxis_title="Impact",
            yaxis_title="",
            height=400,
            margin=dict(l=20, r=20, t=20, b=40),
        )
        st.plotly_chart(fig_bar, width="stretch")

        # Radar chart: core system influence reach
        st.subheader("Core System Influence Radar")

        categories = [NODE_LABELS_KO.get(n, n) for n in all_nodes]

        fig_radar = go.Figure()

        for pol_node in ["sap_basis", "db_hana"]:
            # Get weight connections from this political node to all others
            vals = []
            for n in all_nodes:
                w = adj.get(pol_node, {}).get(n, 0.0)
                if n == pol_node:
                    w = 1.0
                vals.append(abs(w))

            fig_radar.add_trace(go.Scatterpolar(
                r=vals + [vals[0]],  # close the polygon
                theta=categories + [categories[0]],
                fill="toself",
                name=NODE_LABELS_KO.get(pol_node, pol_node),
                opacity=0.6,
            ))

        fig_radar.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
            height=450,
            margin=dict(l=40, r=40, t=40, b=40),
        )
        st.plotly_chart(fig_radar, width="stretch")

    else:
        st.info("Run a simulation to see governance & impact analysis.")


# --------------------------------------------------
# Security Checklist
# Applied:
#   - Null check: simulation_results checked before use (Category 5)
#   - Encapsulation: adj from get_adjacency_dict returns copy (Category 6)
# Not Applied:
#   - [WARN] SQL Injection: Not applicable - no database
#   - [WARN] Authentication: Not applicable - read-only visualization
# --------------------------------------------------
