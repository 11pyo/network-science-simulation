"""
Network Science Simulation - Main Streamlit Application
"""

import sys
import os
import logging

# Add project root to path for module imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st

from models.network import NetworkModel
from models.simulation import ShockSimulator
from views.sidebar import render_sidebar
from views.network_view import render_network_view
from views.political_view import render_political_view
from views.market_view import render_market_view

# [SECURE] Server-side logging only - no stack traces to users (Category 4)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    st.set_page_config(
        page_title="SAP System Impact Simulation",
        page_icon="",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Initialize session state
    if "simulation_results" not in st.session_state:
        st.session_state.simulation_results = None

    try:
        # Render sidebar and get user configuration
        config = render_sidebar()

        # Build network model from current preset node IDs and weights
        network = NetworkModel(config["preset"]["node_ids"], config["weights"])

        # Run simulation if requested
        if config["run_simulation"]:
            try:
                simulator = ShockSimulator(
                    network=network,
                    damping=config["damping"],
                    max_steps=config["steps"],
                )
                results = simulator.simulate(
                    shock_node=config["shock_node"],
                    shock_intensity=config["shock_intensity"],
                )
                st.session_state.simulation_results = results
                st.toast("Simulation complete!")
            except ValueError as e:
                # [SECURE] Generic error to user, detail logged server-side (Category 4)
                logger.error("Simulation error: %s", e)
                st.error("Simulation could not be completed. Please check your inputs.")
            except Exception as e:
                logger.error("Unexpected simulation error: %s", e, exc_info=True)
                st.error("An unexpected error occurred. Please try again.")

        results = st.session_state.simulation_results
        preset  = config["preset"]

        # Render views in tabs
        tab1, tab2, tab3 = st.tabs([
            "System Topology",
            "Governance & Impact",
            "Operations Time Series",
        ])

        with tab1:
            render_network_view(network, results, preset=preset)

        with tab2:
            render_political_view(network, results, preset=preset)

        with tab3:
            render_market_view(network, results, preset=preset)

    except Exception as e:
        # [SECURE] Global error handler - log details, show generic message (Category 4)
        logger.error("Application error: %s", e, exc_info=True)
        st.error("An error occurred while running the application. Please reload the page.")


if __name__ == "__main__":
    main()


# --------------------------------------------------
# Security Checklist
# Applied:
#   - Error message exposure prevention: Generic messages to user, full logs server-side (Category 4)
#   - Proper exception handling: No empty except blocks, all exceptions logged (Category 4)
#   - Input validation: All user inputs flow through validators via sidebar/models (Category 1)
#   - Infinite loop prevention: Simulation capped at MAX_SIMULATION_STEPS (Category 3)
#   - No hard-coded credentials: No secrets in source (Category 2)
# Not Applied:
#   - [WARN] SQL Injection: Not applicable - no database
#   - [WARN] CSRF: Not applicable - Streamlit manages internally
#   - [WARN] Authentication: Not applicable - local simulation tool
#   - [WARN] File upload: Not applicable - no file upload feature
# --------------------------------------------------
