"""
NetworkModel class wrapping networkx graph with centrality calculations.
"""

import logging
import networkx as nx
import numpy as np

from config.constants import VALID_NODE_IDS, WEIGHT_MIN, WEIGHT_MAX
from utils.validators import validate_node_id, validate_weight, validate_centrality_method

logger = logging.getLogger(__name__)


class NetworkModel:
    """Weighted undirected graph representing interconnected domains."""

    def __init__(self, node_ids: list, weights: dict):
        """
        Build the network from node IDs and edge weights.

        Args:
            node_ids: List of valid node identifier strings.
            weights: Dict mapping (node_a, node_b) tuples to float weights.
        """
        self._graph = nx.Graph()

        # [SECURE] Whitelist validation for all node IDs (Category 1)
        for nid in node_ids:
            validate_node_id(nid)
            self._graph.add_node(nid)

        for (a, b), w in weights.items():
            # [SECURE] Validate both node IDs and weight range (Category 1)
            validate_node_id(a)
            validate_node_id(b)
            w = validate_weight(w)
            self._graph.add_edge(a, b, weight=w)

    def get_adjacency_matrix(self) -> np.ndarray:
        """Return a copy of the adjacency matrix as numpy array."""
        # [SECURE] Return copy - prevents private data direct exposure (Category 6)
        node_list = sorted(self._graph.nodes())
        return nx.to_numpy_array(self._graph, nodelist=node_list).copy()

    def get_adjacency_dict(self) -> dict:
        """Return adjacency as nested dict {node: {neighbor: weight}}."""
        # [SECURE] Return copy - prevents private data direct exposure (Category 6)
        adj = {}
        for node in self._graph.nodes():
            adj[node] = {}
            for neighbor in self._graph.neighbors(node):
                adj[node][neighbor] = self._graph[node][neighbor].get("weight", 0.0)
        return adj

    def get_centrality(self, method: str = "degree") -> dict:
        """Compute node centrality scores."""
        # [SECURE] Whitelist validation - prevents code injection (Category 1)
        method = validate_centrality_method(method)

        if method == "degree":
            return dict(nx.degree_centrality(self._graph))
        elif method == "betweenness":
            return dict(nx.betweenness_centrality(self._graph, weight="weight"))
        elif method == "eigenvector":
            try:
                return dict(nx.eigenvector_centrality(
                    self._graph, weight="weight", max_iter=100
                ))
            except nx.PowerIterationFailedConvergence:
                # [SECURE] Log error server-side, return fallback (Category 4)
                logger.warning("Eigenvector centrality failed to converge, falling back to degree.")
                return dict(nx.degree_centrality(self._graph))

        return dict(nx.degree_centrality(self._graph))

    def get_edge_weights(self) -> dict:
        """Return all edge weights as {(a, b): weight}."""
        # [SECURE] Return copy (Category 6)
        result = {}
        for a, b, data in self._graph.edges(data=True):
            result[(a, b)] = data.get("weight", 0.0)
        return result

    def update_weight(self, node_a: str, node_b: str, weight: float) -> None:
        """Update a single edge weight."""
        # [SECURE] Validate inputs (Category 1)
        validate_node_id(node_a)
        validate_node_id(node_b)
        weight = validate_weight(weight)
        self._graph.add_edge(node_a, node_b, weight=weight)

    def get_neighbors(self, node_id: str) -> list:
        """Return neighbor list for a node."""
        # [SECURE] Whitelist validation (Category 1)
        validate_node_id(node_id)
        return list(self._graph.neighbors(node_id))

    def get_nodes(self) -> list:
        """Return sorted list of node IDs."""
        return sorted(self._graph.nodes())

    def get_graph(self) -> nx.Graph:
        """Return a copy of the internal graph."""
        # [SECURE] Return copy - prevents direct mutation of internal state (Category 6)
        return self._graph.copy()

    def get_network_stats(self) -> dict:
        """Calculate global network statistics."""
        g = self._graph
        stats = {
            "density": nx.density(g),
            "num_nodes": g.number_of_nodes(),
            "num_edges": g.number_of_edges(),
        }
        if nx.is_connected(g):
            stats["avg_path_length"] = nx.average_shortest_path_length(g)
            stats["avg_clustering"] = nx.average_clustering(g, weight="weight")
        else:
            stats["avg_path_length"] = float("inf")
            stats["avg_clustering"] = 0.0
        return stats


# --------------------------------------------------
# Security Checklist
# Applied:
#   - Input validation: All node IDs and weights validated (Category 1)
#   - Encapsulation: All getters return copies (Category 6)
#   - Error handling: eigenvector convergence failure handled (Category 4)
#   - Null check: Weight defaults via .get() (Category 5)
# Not Applied:
#   - [WARN] SQL Injection: Not applicable - no database
#   - [WARN] Authentication: Not applicable - in-memory model only
# --------------------------------------------------
