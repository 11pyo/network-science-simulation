"""
Network topology visualization using Plotly.
"""

import streamlit as st
import plotly.graph_objects as go

from config.constants import NODE_LABELS_KO, NODE_COLORS, NODE_IDS
from config.defaults import NODE_POSITIONS
from models.simulation import ShockSimulator
from utils.helpers import weight_to_color, weight_to_width, format_percentage


def render_network_view(network, simulation_results=None, preset=None):
    """Render the interactive network graph."""

    # Use preset data if provided, else fall back to SAP defaults
    node_labels   = preset["node_labels"]   if preset else NODE_LABELS_KO
    node_colors   = preset["node_colors"]   if preset else NODE_COLORS
    node_positions = preset["node_positions"] if preset else NODE_POSITIONS
    header_title  = (preset["title"] + " — Topology") if preset else "SAP System Topology"

    st.header(header_title)

    # Centrality method selector
    centrality_method = st.selectbox(
        "Centrality Metric",
        options=["degree", "betweenness", "eigenvector"],
        index=0,
        key="centrality_method",
    )

    centrality    = network.get_centrality(centrality_method)
    edge_weights  = network.get_edge_weights()
    nodes         = network.get_nodes()

    # Time step control if simulation ran
    current_step = 0
    step_data    = {}
    if simulation_results is not None:
        max_step = ShockSimulator.get_max_step(simulation_results)
        if max_step > 0:
            current_step = st.slider(
                "Time Step", 0, max_step, value=0, key="network_step"
            )
            step_data = ShockSimulator.get_step_data(simulation_results, current_step)

    # Build figure
    fig = go.Figure()

    # Draw edges
    for (a, b), w in edge_weights.items():
        x0, y0 = node_positions.get(a, (0, 0))
        x1, y1 = node_positions.get(b, (0, 0))

        fig.add_trace(go.Scatter(
            x=[x0, x1, None],
            y=[y0, y1, None],
            mode="lines",
            line=dict(
                width=weight_to_width(w),
                color=weight_to_color(w),
            ),
            hoverinfo="text",
            text=f"{node_labels.get(a, a)} - {node_labels.get(b, b)}: {w:.2f}",
            showlegend=False,
        ))

    # Draw nodes
    node_x             = []
    node_y             = []
    node_text          = []
    node_sizes         = []
    node_colors_list   = []

    for n in nodes:
        x, y = node_positions.get(n, (0, 0))
        node_x.append(x)
        node_y.append(y)

        c      = centrality.get(n, 0.0)
        impact = step_data.get(n, 0.0)

        label = node_labels.get(n, n)
        hover = f"<b>{label}</b><br>Centrality: {c:.3f}"
        if step_data:
            hover += f"<br>Impact: {format_percentage(impact)}"
        node_text.append(hover)

        # Size based on centrality
        node_sizes.append(25 + c * 40)

        # Color: base color or impact-tinted
        if step_data and abs(impact) > 0.01:
            if impact > 0:
                r, g, b_val = 231, 76, 60
            else:
                r, g, b_val = 41, 128, 185
            alpha = min(abs(impact) * 0.8 + 0.2, 1.0)
            node_colors_list.append(f"rgba({r},{g},{b_val},{alpha})")
        else:
            node_colors_list.append(node_colors.get(n, "#888888"))

    fig.add_trace(go.Scatter(
        x=node_x,
        y=node_y,
        mode="markers+text",
        marker=dict(
            size=node_sizes,
            color=node_colors_list,
            line=dict(width=2, color="white"),
        ),
        text=[node_labels.get(n, n) for n in nodes],
        textposition="top center",
        textfont=dict(size=12),
        hoverinfo="text",
        hovertext=node_text,
        showlegend=False,
    ))

    fig.update_layout(
        showlegend=False,
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        margin=dict(l=20, r=20, t=20, b=20),
        height=550,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )

    st.plotly_chart(fig, width="stretch")

    # Network statistics
    stats = network.get_network_stats()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Nodes", stats["num_nodes"])
    col2.metric("Edges", stats["num_edges"])
    col3.metric("Density", f"{stats['density']:.3f}")
    if stats["avg_path_length"] != float("inf"):
        col4.metric("Avg Path Length", f"{stats['avg_path_length']:.2f}")
    else:
        col4.metric("Avg Path Length", "N/A (disconnected)")


# --------------------------------------------------
# Security Checklist
# Applied:
#   - Input validation: Centrality method via selectbox whitelist (Category 1)
#   - Null check: step_data checked before use (Category 5)
#   - Null check: preset checked before use with fallback (Category 5)
# Not Applied:
#   - [WARN] SQL Injection: Not applicable - no database
#   - [WARN] XSS: Plotly escapes hover text internally
# --------------------------------------------------
