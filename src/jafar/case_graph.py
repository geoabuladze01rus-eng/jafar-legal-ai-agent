from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class GraphNode:
    node_id: str
    node_type: str
    label: str
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class GraphEdge:
    source: str
    relation: str
    target: str
    evidence_ids: tuple[str, ...] = ()


class CaseGraph:
    """Evidence-aware graph linking cases, people, entities, documents and events."""

    def __init__(self) -> None:
        self.nodes: dict[str, GraphNode] = {}
        self.edges: list[GraphEdge] = []

    def add_node(self, node: GraphNode) -> None:
        self.nodes[node.node_id] = node

    def link(self, source: str, relation: str, target: str, evidence_ids: tuple[str, ...] = ()) -> None:
        if source not in self.nodes or target not in self.nodes:
            raise KeyError("Both graph nodes must exist before linking them")
        self.edges.append(GraphEdge(source, relation, target, evidence_ids))

    def neighbors(self, node_id: str, relation: str | None = None) -> list[GraphNode]:
        targets = [e.target for e in self.edges if e.source == node_id and (relation is None or e.relation == relation)]
        return [self.nodes[node_id] for node_id in targets]

    def export(self) -> dict[str, Any]:
        return {
            "nodes": [node.__dict__ for node in self.nodes.values()],
            "edges": [edge.__dict__ for edge in self.edges],
        }
