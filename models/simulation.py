"""
ShockSimulator - shock propagation (diffusion) engine.
"""

import logging
import pandas as pd
import numpy as np

from config.constants import MAX_SIMULATION_STEPS, CONVERGENCE_THRESHOLD
from utils.validators import (
    validate_node_id,
    validate_shock_intensity,
    validate_simulation_steps,
    validate_damping,
)

logger = logging.getLogger(__name__)


class ShockSimulator:
    """Simulates shock propagation through a weighted network."""

    def __init__(self, network, damping: float = 0.5,
                 max_steps: int = 10, threshold: float = CONVERGENCE_THRESHOLD):
        """
        Args:
            network: A NetworkModel instance.
            damping: Attenuation factor per propagation step.
            max_steps: Maximum number of simulation steps.
            threshold: Convergence threshold for early stopping.
        """
        self._network = network
        # [SECURE] Validate and cap simulation parameters (Category 3)
        self._damping = validate_damping(damping)
        self._max_steps = validate_simulation_steps(max_steps)
        self._threshold = threshold

    def simulate(self, shock_node: str, shock_intensity: float) -> pd.DataFrame:
        """
        Run shock propagation simulation.

        Args:
            shock_node: Node ID to apply shock to.
            shock_intensity: Magnitude of the initial shock [-1.0, 1.0].

        Returns:
            DataFrame with columns [step, node_id, value].
        """
        # [SECURE] Validate inputs (Category 1)
        shock_node = validate_node_id(shock_node)
        shock_intensity = validate_shock_intensity(shock_intensity)

        nodes = self._network.get_nodes()
        adj = self._network.get_adjacency_dict()

        # Initialize state
        state = {n: 0.0 for n in nodes}
        state[shock_node] = shock_intensity

        history = []
        for n in nodes:
            history.append({"step": 0, "node_id": n, "value": state[n]})

        # [SECURE] Max iteration cap - prevents infinite loop (Category 3)
        for step in range(1, self._max_steps + 1):
            new_state = dict(state)
            max_delta = 0.0

            for n in nodes:
                neighbors = adj.get(n, {})
                effect = 0.0
                for m, weight in neighbors.items():
                    effect += weight * state[m] * self._damping

                new_state[n] = state[n] + effect
                # [SECURE] Clamp values to prevent runaway (Category 1)
                new_state[n] = max(-1.0, min(1.0, new_state[n]))

                delta = abs(new_state[n] - state[n])
                if delta > max_delta:
                    max_delta = delta

            state = new_state
            for n in nodes:
                history.append({"step": step, "node_id": n, "value": state[n]})

            # Early termination on convergence
            if max_delta < self._threshold:
                logger.info("Simulation converged at step %d (delta=%.6f)", step, max_delta)
                break

        return pd.DataFrame(history)

    @staticmethod
    def get_step_data(results: pd.DataFrame, step: int) -> dict:
        """Extract a single time step's data."""
        # [SECURE] Null check before use (Category 5)
        if results is None or results.empty:
            return {}
        step_df = results[results["step"] == step]
        return dict(zip(step_df["node_id"], step_df["value"]))

    @staticmethod
    def get_node_timeseries(results: pd.DataFrame, node_id: str) -> pd.DataFrame:
        """Extract one node's full time series."""
        # [SECURE] Validate node_id (Category 1)
        validate_node_id(node_id)
        # [SECURE] Null check (Category 5)
        if results is None or results.empty:
            return pd.DataFrame(columns=["step", "value"])
        node_df = results[results["node_id"] == node_id][["step", "value"]].copy()
        return node_df

    @staticmethod
    def get_max_step(results: pd.DataFrame) -> int:
        """Return the last simulation step number."""
        if results is None or results.empty:
            return 0
        return int(results["step"].max())

    @staticmethod
    def get_final_impacts(results: pd.DataFrame) -> dict:
        """Return final impact values for all nodes."""
        if results is None or results.empty:
            return {}
        max_step = int(results["step"].max())
        final = results[results["step"] == max_step]
        return dict(zip(final["node_id"], final["value"]))


# --------------------------------------------------
# Security Checklist
# Applied:
#   - Input validation: shock_node and shock_intensity validated (Category 1)
#   - Infinite loop prevention: max_steps capped at MAX_SIMULATION_STEPS (Category 3)
#   - Value clamping: State values clamped to [-1.0, 1.0] every step (Category 1)
#   - Error handling: Convergence logged server-side (Category 4)
#   - Null check: All static methods check for None/empty DataFrames (Category 5)
#   - Encapsulation: Returns copies via .copy() (Category 6)
# Not Applied:
#   - [WARN] SQL Injection: Not applicable - no database
#   - [WARN] Authentication: Not applicable - simulation engine only
# --------------------------------------------------
