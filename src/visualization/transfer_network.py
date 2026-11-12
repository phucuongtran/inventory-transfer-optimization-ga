"""
Turn a transfer plan into a store-to-store network.

Outputs (in the visualizations folder):
- ``store_transfer_network.graphml`` - open in Gephi / yEd / Cytoscape
- ``network_analysis_summary.txt``   - top stores and routes
- PNG charts (see ``network_plots.py``)

Run standalone on an existing ``results/best_transfer_plan.csv``:
    python -m src.visualization.transfer_network
"""

from __future__ import annotations

import sys
from pathlib import Path

import networkx as nx
import pandas as pd

from src.config import RESULTS_DIR, VISUALIZATIONS_DIR
from src.utils.logger import get_logger

logger = get_logger(__name__)

GRAPHML_FILE = "store_transfer_network.graphml"
SUMMARY_FILE = "network_analysis_summary.txt"


def _join_unique(values) -> str:
    return ", ".join(sorted(set(values)))


def build_transfer_graph(plan: pd.DataFrame) -> nx.DiGraph:
    """Directed graph: node = store, edge = all units shipped from one store to another.

    ``plan`` needs the columns added by ``add_readable_names``
    (``from_store_name``, ``to_store_name``, ``product_name``).
    """
    graph = nx.DiGraph()

    sent = plan.groupby("from_store_name").agg(
        store_id=("from_store_id", "first"), units=("units", "sum"), products=("product_name", list)
    )
    received = plan.groupby("to_store_name").agg(
        store_id=("to_store_id", "first"), units=("units", "sum"), products=("product_name", list)
    )
    for store in sorted(set(sent.index) | set(received.index)):
        out_units = int(sent.at[store, "units"]) if store in sent.index else 0
        in_units = int(received.at[store, "units"]) if store in received.index else 0
        products_sent = sent.at[store, "products"] if store in sent.index else []
        products_received = received.at[store, "products"] if store in received.index else []
        store_id = sent.at[store, "store_id"] if store in sent.index else received.at[store, "store_id"]
        graph.add_node(
            store,
            store_name=store,
            store_id=int(store_id),
            total_units_in=in_units,
            total_units_out=out_units,
            total_units=in_units + out_units,
            products_sent_count=len(set(products_sent)),
            products_received_count=len(set(products_received)),
            products_sent_list=_join_unique(products_sent),
            products_received_list=_join_unique(products_received),
        )

    routes = plan.groupby(["from_store_name", "to_store_name"]).agg(
        units=("units", "sum"),
        products=("product_name", list),
        cost=("transport_cost", "sum"),
        distance=("distance_km", "mean"),
    )
    for (from_store, to_store), route in routes.iterrows():
        graph.add_edge(
            from_store,
            to_store,
            units_transferred=int(route["units"]),
            number_of_products=len(set(route["products"])),
            product_list=_join_unique(route["products"]),
            total_transport_cost=round(float(route["cost"]), 2),
            avg_distance_km=round(float(route["distance"]), 2),
            weight=int(route["units"]),
        )
    return graph


def write_network_summary(graph: nx.DiGraph, path: Path) -> None:
    nodes = sorted(graph.nodes(data=True), key=lambda n: n[1]["total_units"], reverse=True)
    edges = sorted(graph.edges(data=True), key=lambda e: e[2]["units_transferred"], reverse=True)
    avg_degree = sum(d for _, d in graph.degree()) / max(graph.number_of_nodes(), 1)

    lines = [
        "STORE TRANSFER NETWORK ANALYSIS SUMMARY",
        "=" * 50,
        "",
        "Network Overview:",
        f"- Total Stores: {graph.number_of_nodes()}",
        f"- Total Store-to-Store Routes: {graph.number_of_edges()}",
        f"- Network Density: {nx.density(graph):.4f}",
        f"- Average Degree: {avg_degree:.2f}",
        "",
        "Top 10 Stores by Total Transfer Volume:",
    ]
    for i, (store, d) in enumerate(nodes[:10], 1):
        lines.append(
            f"{i:2d}. {store:<30} | Total: {d['total_units']:>6,} units "
            f"(In: {d['total_units_in']:>6,}, Out: {d['total_units_out']:>6,})"
        )

    lines += ["", "Top 10 Stores by Outgoing Units:"]
    for i, (store, d) in enumerate(sorted(nodes, key=lambda n: n[1]["total_units_out"], reverse=True)[:10], 1):
        lines.append(f"{i:2d}. {store:<30} | Outgoing: {d['total_units_out']:>6,} units")

    lines += ["", "Top 10 Stores by Incoming Units:"]
    for i, (store, d) in enumerate(sorted(nodes, key=lambda n: n[1]["total_units_in"], reverse=True)[:10], 1):
        lines.append(f"{i:2d}. {store:<30} | Incoming: {d['total_units_in']:>6,} units")

    lines += ["", "Top 15 Store-to-Store Routes:"]
    for i, (u, v, d) in enumerate(edges[:15], 1):
        route = f"{u} -> {v}"
        lines.append(
            f"{i:2d}. {route:<50} | {d['units_transferred']:>6,} units ({d['number_of_products']} products)"
        )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def export_network(plan: pd.DataFrame, output_dir: Path = VISUALIZATIONS_DIR, with_plots: bool = True) -> nx.DiGraph:
    """Write the GraphML file, the text summary and (optionally) the PNG charts."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    graph = build_transfer_graph(plan)
    nx.write_graphml(graph, output_dir / GRAPHML_FILE, encoding="utf-8", prettyprint=True)
    write_network_summary(graph, output_dir / SUMMARY_FILE)
    logger.info(
        "Network: %d stores, %d routes -> %s",
        graph.number_of_nodes(),
        graph.number_of_edges(),
        output_dir / GRAPHML_FILE,
    )

    if with_plots:
        from src.visualization.network_plots import create_all_plots

        create_all_plots(graph, output_dir)
    return graph


if __name__ == "__main__":
    plan_path = RESULTS_DIR / "best_transfer_plan.csv"
    if not plan_path.exists():
        logger.error("%s not found. Run `python src/main.py --all` first.", plan_path)
        sys.exit(1)
    export_network(pd.read_csv(plan_path))
