"""
Operations / Market time-series visualization.
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from config.constants import NODE_LABELS_KO, NODE_COLORS, NODE_IDS, NODE_GROUPS
from models.simulation import ShockSimulator
from utils.helpers import format_percentage


def render_market_view(network, simulation_results=None, preset=None):
    """Render operations time series analysis view."""

    # Use preset data if provided, else fall back to SAP defaults
    node_labels  = preset["node_labels"]               if preset else NODE_LABELS_KO
    node_colors  = preset["node_colors"]               if preset else NODE_COLORS
    # [SECURE] core_ops sourced from preset whitelist only (Category 1)
    market_nodes = preset["node_groups"]["core_ops"]   if preset else NODE_GROUPS["core_ops"]

    st.header("Operations Time Series Analysis")

    all_nodes = network.get_nodes()

    if simulation_results is not None:
        max_step = ShockSimulator.get_max_step(simulation_results)

        # --- Time Series Chart ---
        st.subheader("Core Operations Time Series")

        fig_ts = go.Figure()

        for n in all_nodes:
            ts         = ShockSimulator.get_node_timeseries(simulation_results, n)
            is_market  = n in market_nodes

            fig_ts.add_trace(go.Scatter(
                x=ts["step"],
                y=ts["value"],
                mode="lines+markers" if is_market else "lines",
                name=node_labels.get(n, n),
                line=dict(
                    width=3 if is_market else 1,
                    color=node_colors.get(n, "#888"),
                    dash=None if is_market else "dot",
                ),
                marker=dict(size=6 if is_market else 0),
                opacity=1.0 if is_market else 0.4,
            ))

        fig_ts.update_layout(
            xaxis_title="Simulation Step",
            yaxis_title="Impact Value",
            height=450,
            margin=dict(l=20, r=20, t=20, b=40),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            yaxis=dict(range=[-1.1, 1.1]),
        )
        st.plotly_chart(fig_ts, width="stretch")

        # --- Cumulative Impact Bar ---
        st.subheader("Cumulative Operations Impact")

        final_impacts = ShockSimulator.get_final_impacts(simulation_results)

        market_data = []
        for n in market_nodes:
            if n not in all_nodes:
                continue  # [SECURE] Null check - skip node not in network (Category 5)
            market_data.append({
                "node":   node_labels.get(n, n),
                "impact": final_impacts.get(n, 0.0),
            })

        market_df = pd.DataFrame(market_data)

        fig_cum = go.Figure(data=go.Bar(
            x=market_df["node"],
            y=market_df["impact"],
            marker_color=[node_colors.get(n, "#888") for n in market_nodes if n in all_nodes],
            text=[format_percentage(v) for v in market_df["impact"]],
            textposition="auto",
        ))
        fig_cum.update_layout(
            yaxis_title="Final Impact",
            height=350,
            margin=dict(l=20, r=20, t=20, b=40),
            yaxis=dict(range=[-1.1, 1.1]),
        )
        st.plotly_chart(fig_cum, width="stretch")

        # --- Core Ops Correlation Subset ---
        st.subheader("Core Operations Correlations")

        adj      = network.get_adjacency_dict()
        # [SECURE] Only render nodes present in network (Category 5)
        valid_market = [n for n in market_nodes if n in all_nodes]
        m_labels = [node_labels.get(n, n) for n in valid_market]
        m_matrix = []
        for a in valid_market:
            row = []
            for b in valid_market:
                if a == b:
                    row.append(1.0)
                else:
                    row.append(adj.get(a, {}).get(b, 0.0))
            m_matrix.append(row)

        fig_hm = go.Figure(data=go.Heatmap(
            z=m_matrix,
            x=m_labels,
            y=m_labels,
            colorscale="RdBu_r",
            zmid=0,
            text=[[f"{v:.2f}" for v in row] for row in m_matrix],
            texttemplate="%{text}",
        ))
        fig_hm.update_layout(
            height=300,
            margin=dict(l=20, r=20, t=20, b=20),
        )
        st.plotly_chart(fig_hm, width="stretch")

        # --- Summary Metrics ---
        st.subheader("Operations Summary")
        valid_for_metrics = [n for n in market_nodes if n in all_nodes]
        cols = st.columns(max(len(valid_for_metrics), 1))
        for i, n in enumerate(valid_for_metrics):
            impact = final_impacts.get(n, 0.0)
            cols[i].metric(
                node_labels.get(n, n),
                format_percentage(impact),
                delta=format_percentage(impact),
                delta_color="inverse" if impact < 0 else "normal",
            )

    else:
        st.info("Run a simulation to see operations time series analysis.")

        # Show static core ops correlations
        st.subheader("Core Operations Connections (Static)")
        adj = network.get_adjacency_dict()
        for n in market_nodes:
            if n not in all_nodes:
                continue  # [SECURE] Null check (Category 5)
            label  = node_labels.get(n, n)
            conns  = adj.get(n, {})
            conn_str = ", ".join(
                f"{node_labels.get(m, m)}: {w:.2f}" for m, w in conns.items()
            )
            st.write(f"**{label}**: {conn_str}")


# --------------------------------------------------
# Security Checklist
# Applied:
#   - Null check: simulation_results checked before use (Category 5)
#   - Null check: preset checked before use with fallback (Category 5)
#   - Null check: market nodes validated against all_nodes before rendering (Category 5)
#   - Whitelist: core_ops sourced from preset registry (Category 1)
#   - Encapsulation: adj from get_adjacency_dict returns copy (Category 6)
# Not Applied:
#   - [WARN] SQL Injection: Not applicable - no database
#   - [WARN] Authentication: Not applicable - read-only visualization
# --------------------------------------------------
