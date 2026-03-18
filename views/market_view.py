"""
Market fluctuation time-series visualization.
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from config.constants import NODE_LABELS_KO, NODE_COLORS, NODE_IDS, NODE_GROUPS
from models.simulation import ShockSimulator
from utils.helpers import format_percentage


def render_market_view(network, simulation_results=None):
    """Render operations time series analysis view."""

    st.header("Operations Time Series Analysis")

    market_nodes = NODE_GROUPS["core_ops"]
    all_nodes = network.get_nodes()

    if simulation_results is not None:
        max_step = ShockSimulator.get_max_step(simulation_results)

        # --- Time Series Chart ---
        st.subheader("Core Operations Time Series")

        fig_ts = go.Figure()

        for n in all_nodes:
            ts = ShockSimulator.get_node_timeseries(simulation_results, n)
            is_market = n in market_nodes

            fig_ts.add_trace(go.Scatter(
                x=ts["step"],
                y=ts["value"],
                mode="lines+markers" if is_market else "lines",
                name=NODE_LABELS_KO.get(n, n),
                line=dict(
                    width=3 if is_market else 1,
                    color=NODE_COLORS.get(n, "#888"),
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
        st.plotly_chart(fig_ts, use_container_width=True)

        # --- Cumulative Impact Bar ---
        st.subheader("Cumulative Operations Impact")

        final_impacts = ShockSimulator.get_final_impacts(simulation_results)

        # Focus on market nodes
        market_data = []
        for n in market_nodes:
            market_data.append({
                "node": NODE_LABELS_KO.get(n, n),
                "impact": final_impacts.get(n, 0.0),
            })

        market_df = pd.DataFrame(market_data)

        fig_cum = go.Figure(data=go.Bar(
            x=market_df["node"],
            y=market_df["impact"],
            marker_color=[NODE_COLORS.get(n, "#888") for n in market_nodes],
            text=[format_percentage(v) for v in market_df["impact"]],
            textposition="auto",
        ))
        fig_cum.update_layout(
            yaxis_title="Final Impact",
            height=350,
            margin=dict(l=20, r=20, t=20, b=40),
            yaxis=dict(range=[-1.1, 1.1]),
        )
        st.plotly_chart(fig_cum, use_container_width=True)

        # --- Core Ops Correlation Subset ---
        st.subheader("Core Operations Correlations")

        adj = network.get_adjacency_dict()
        m_labels = [NODE_LABELS_KO.get(n, n) for n in market_nodes]
        m_matrix = []
        for a in market_nodes:
            row = []
            for b in market_nodes:
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
        st.plotly_chart(fig_hm, use_container_width=True)

        # --- Summary Metrics ---
        st.subheader("Operations Summary")
        cols = st.columns(len(market_nodes))
        for i, n in enumerate(market_nodes):
            impact = final_impacts.get(n, 0.0)
            cols[i].metric(
                NODE_LABELS_KO.get(n, n),
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
            label = NODE_LABELS_KO.get(n, n)
            conns = adj.get(n, {})
            conn_str = ", ".join(
                f"{NODE_LABELS_KO.get(m, m)}: {w:.2f}" for m, w in conns.items()
            )
            st.write(f"**{label}**: {conn_str}")


# --------------------------------------------------
# Security Checklist
# Applied:
#   - Null check: simulation_results checked before use (Category 5)
#   - Encapsulation: adj from get_adjacency_dict returns copy (Category 6)
# Not Applied:
#   - [WARN] SQL Injection: Not applicable - no database
#   - [WARN] Authentication: Not applicable - read-only visualization
# --------------------------------------------------
