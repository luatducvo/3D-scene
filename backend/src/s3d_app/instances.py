"""Model-independent interface for proposals over source mesh vertices."""

from dataclasses import dataclass

import numpy as np


def dominant_component(points: np.ndarray, mask: np.ndarray, cell_m: float = 0.15) -> np.ndarray:
    """Remove isolated predicted fragments before deriving an Object bbox."""
    indices = np.flatnonzero(mask)
    if not len(indices):
        return mask.copy()
    cells: dict[tuple[int, int, int], list[int]] = {}
    for vertex, coordinate in zip(indices, np.floor(points[indices] / cell_m).astype(np.int32)):
        cells.setdefault(tuple(int(value) for value in coordinate), []).append(int(vertex))
    neighbors = [(x, y, z) for x in (-1, 0, 1) for y in (-1, 0, 1) for z in (-1, 0, 1)
                 if (x, y, z) != (0, 0, 0)]
    remaining = set(cells)
    largest: list[int] = []
    while remaining:
        start = min(remaining)
        remaining.remove(start)
        pending = [start]
        component = []
        while pending:
            cell = pending.pop()
            component.extend(cells[cell])
            for delta in neighbors:
                adjacent = tuple(cell[axis] + delta[axis] for axis in range(3))
                if adjacent in remaining:
                    remaining.remove(adjacent)
                    pending.append(adjacent)
        if len(component) > len(largest):
            largest = component
    cleaned = np.zeros(len(mask), dtype=bool)
    cleaned[largest] = True
    return cleaned


@dataclass(frozen=True)
class InstanceProposal:
    mask: np.ndarray
    label_id: int
    confidence: float
    source: str


def select_proposals(proposals: list[InstanceProposal], vertex_count: int,
                     *, min_vertices: int = 100,
                     nms_iou: float = 0.5) -> tuple[np.ndarray, list[dict]]:
    """Apply mask NMS and give overlapping vertices to the strongest proposal."""
    accepted: list[InstanceProposal] = []
    for proposal in sorted(proposals, key=lambda item: item.confidence, reverse=True):
        if proposal.mask.dtype != np.bool_ or len(proposal.mask) != vertex_count:
            raise ValueError("An Instance proposal must have one boolean value per source vertex")
        if int(proposal.mask.sum()) < min_vertices:
            continue
        if any(np.count_nonzero(proposal.mask & other.mask) /
               max(1, np.count_nonzero(proposal.mask | other.mask)) > nms_iou
               for other in accepted):
            continue
        accepted.append(proposal)
    instance_ids = np.full(vertex_count, -1, dtype=np.int32)
    rows = []
    for instance_id, proposal in enumerate(accepted):
        instance_ids[proposal.mask & (instance_ids == -1)] = instance_id
    final_ids = np.full(vertex_count, -1, dtype=np.int32)
    for instance_id, proposal in enumerate(accepted):
        owned = instance_ids == instance_id
        if int(owned.sum()) < min_vertices:
            continue
        identifier = len(rows)
        final_ids[owned] = identifier
        rows.append({"id": identifier, "label_id": proposal.label_id,
                     "confidence": round(proposal.confidence, 5),
                     "vertices": int(owned.sum()), "source": proposal.source})
    return final_ids, rows
