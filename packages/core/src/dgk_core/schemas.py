from __future__ import annotations

from pydantic import BaseModel


class GraphNode(BaseModel):
    id: str
    label: str
    name: str
    path: str
    line: int = 1
    properties: dict = {}


class GraphRelationship(BaseModel):
    type: str
    source_id: str
    target_id: str
    properties: dict = {}


class ScanResult(BaseModel):
    file: str
    nodes: list[GraphNode]
    relationships: list[GraphRelationship]
