"""
Matplotlib charts of the store transfer network.

- ``network_overview.png``   : whole network; node size = volume, colour = net flow
- ``hub_analysis.png``       : the 10 most connected stores and their routes
- ``flow_intensity_map.png`` : circular layout, edge colour/width = units shipped
"""

from __future__ import annotations

from pathlib import Path
from typing import List

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import networkx as nx

from src.utils.logger import get_logger

logger = get_logger(__name__)

TOP_HUBS = 10


def create_all_plots(graph: nx.DiGraph, output_dir: Path) -> None:
    output_dir = Path(output_dir)
    for plot in (plot_network_overview, plot_hub_analysis, plot_flow_intensity):
        path = plot(graph, output_dir)
        logger.info("Saved chart: %s", path.name)


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _scale(values: List[float], low: float, high: float) -> List[float]:
    """Linearly map ``values`` onto [low, high] (midpoint if all values are equal)."""
    smallest, largest = min(values, default=0), max(values, default=0)
    if largest == smallest:
        return [(low + high) / 2] * len(values)
    return [low + (high - low) * (v - smallest) / (largest - smallest) for v in values]


def _wrap_label(name: str) -> str:
    """Put each word of a store name on its own line."""
    return name.replace(" - ", "\n").replace(" ", "\n")


def _save(path: Path) -> Path:
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(path, dpi=300, bbox_inches="tight")
    plt.close()
    return path


# ----------------------------------------------------------------------
# Charts
# ----------------------------------------------------------------------
def plot_network_overview(graph: nx.DiGraph, output_dir: Path) -> Path:
    plt.figure(figsize=(20, 16))
    pos = nx.spring_layout(graph, k=3, iterations=50, seed=42)

    volumes = [graph.nodes[n]["total_units"] for n in graph.nodes]
    edge_units = [graph.edges[e]["units_transferred"] for e in graph.edges]
    net_flows = [graph.nodes[n]["total_units_in"] - graph.nodes[n]["total_units_out"] for n in graph.nodes]
    colors = ["lightcoral" if f < 0 else "lightblue" if f > 0 else "lightgray" for f in net_flows]

    nx.draw_networkx_nodes(
        graph, pos, node_size=_scale(volumes, 300, 3000), node_color=colors,
        alpha=0.8, edgecolors="black", linewidths=1,
    )
    nx.draw_networkx_edges(
        graph, pos, width=_scale(edge_units, 0.5, 5.0), alpha=0.6, edge_color="gray",
        arrows=True, arrowsize=20, arrowstyle="->", min_target_margin=15,
    )
    nx.draw_networkx_labels(graph, pos, {n: _wrap_label(n) for n in graph.nodes}, font_size=8, font_weight="bold")

    plt.title(
        "Store Transfer Network Overview\n"
        "Node size = total transfer volume | Node colour = net flow direction\n"
        "Edge thickness = units transferred",
        fontsize=16, fontweight="bold", pad=20,
    )
    plt.legend(
        handles=[
            mpatches.Patch(color="lightcoral", label="Net outflow (supplier stores)"),
            mpatches.Patch(color="lightblue", label="Net inflow (receiver stores)"),
            mpatches.Patch(color="lightgray", label="Balanced flow"),
        ],
        loc="upper left", fontsize=12,
    )
    avg_units = sum(edge_units) / len(edge_units) if edge_units else 0
    plt.text(
        0.02, 0.85,
        f"Stores: {graph.number_of_nodes()}\nRoutes: {graph.number_of_edges()}\n"
        f"Density: {nx.density(graph):.3f}\nAvg units/route: {avg_units:.1f}",
        transform=plt.gca().transAxes, fontsize=10, verticalalignment="top",
        bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.8),
    )
    return _save(output_dir / "network_overview.png")


def plot_hub_analysis(graph: nx.DiGraph, output_dir: Path) -> Path:
    centrality = nx.degree_centrality(graph)
    hubs = sorted(centrality, key=centrality.get, reverse=True)[:TOP_HUBS]
    hub_set = set(hubs)
    subgraph = graph.edge_subgraph([(u, v) for u, v in graph.edges if u in hub_set or v in hub_set])

    plt.figure(figsize=(18, 14))
    pos = nx.spring_layout(subgraph, k=2, iterations=50, seed=42)
    nx.draw_networkx_nodes(
        subgraph, pos,
        node_size=[2000 if n in hub_set else 1000 for n in subgraph.nodes],
        node_color=["gold" if n in hub_set else "lightsteelblue" for n in subgraph.nodes],
        alpha=0.8, edgecolors="black", linewidths=2,
    )
    edge_units = [subgraph.edges[e]["units_transferred"] for e in subgraph.edges]
    nx.draw_networkx_edges(
        subgraph, pos, width=_scale(edge_units, 0.5, 4.5), alpha=0.6, edge_color="darkgray",
        arrows=True, arrowsize=15, arrowstyle="->",
    )
    nx.draw_networkx_labels(subgraph, pos, {n: _wrap_label(n) for n in subgraph.nodes}, font_size=9, font_weight="bold")

    plt.title(
        f"Hub Store Analysis - Top {TOP_HUBS} Most Connected Stores\n"
        "Gold = hub store | Blue = connected store",
        fontsize=16, fontweight="bold", pad=20,
    )
    plt.text(
        0.02, 0.98,
        "Top hubs (by connections):\n" + "\n".join(f"{i}. {hub}" for i, hub in enumerate(hubs, 1)),
        transform=plt.gca().transAxes, fontsize=9, verticalalignment="top",
        bbox=dict(boxstyle="round", facecolor="lightyellow", alpha=0.9),
    )
    return _save(output_dir / "hub_analysis.png")


def plot_flow_intensity(graph: nx.DiGraph, output_dir: Path) -> Path:
    plt.figure(figsize=(16, 12))
    pos = nx.circular_layout(graph)

    volumes = [graph.nodes[n]["total_units"] for n in graph.nodes]
    max_volume = max(volumes, default=1) or 1
    edges = list(graph.edges)
    edge_units = [graph.edges[e]["units_transferred"] for e in edges]
    max_units = max(edge_units, default=1) or 1

    nx.draw_networkx_nodes(
        graph, pos,
        node_size=[500 + 2000 * v / max_volume for v in volumes],
        node_color=[plt.cm.Blues(0.3 + 0.7 * v / max_volume) for v in volumes],
        alpha=0.8, edgecolors="black", linewidths=1,
    )
    nx.draw_networkx_edges(
        graph, pos, edgelist=edges,
        width=[0.5 + 6 * u / max_units for u in edge_units],
        edge_color=[plt.cm.Reds(0.3 + 0.7 * u / max_units) for u in edge_units],
        alpha=0.8, arrows=True, arrowsize=12, arrowstyle="->",
    )
    nx.draw_networkx_labels(graph, pos, {n: n.replace(" ", "\n", 1) for n in graph.nodes}, font_size=7, font_weight="bold")

    plt.title(
        "Transfer Flow Intensity Map\n"
        "Node colour/size = total volume | Edge colour/thickness = units shipped",
        fontsize=16, fontweight="bold", pad=20,
    )
    colorbar = plt.cm.ScalarMappable(cmap=plt.cm.Blues, norm=plt.Normalize(min(volumes, default=0), max_volume))
    plt.colorbar(colorbar, ax=plt.gca(), shrink=0.6, pad=0.1, aspect=20).set_label(
        "Total store volume (units)", fontsize=10
    )
    return _save(output_dir / "flow_intensity_map.png")
