"""Validated constraint Programs and deterministic geometric solving."""

import math
import time
from dataclasses import dataclass, field
from typing import Literal, Self, get_args

from pydantic import BaseModel, ConfigDict, model_validator

Variable = Literal["t", "a", "b", "c", "d", "w"]
NodeId = int | str
Predicate = Literal[
    "ON", "UNDER", "SUPPORTS", "ABOVE", "BELOW", "IN", "CONTAINS", "NEAR", "FAR",
    "NEXT_TO", "LEFT", "RIGHT", "FRONT", "BEHIND", "BETWEEN", "COLOR", "NOT",
    "AGAINST_WALL", "ON_FLOOR", "IN_CORNER",
]
Select = Literal["CLOSEST", "FARTHEST", "LARGEST", "SMALLEST", "HIGHEST", "LOWEST"]
SelectionAnchor = Literal["t", "a", "b", "c", "d", "w", ""]
Intent = Literal["ground", "count", "exists", "attribute", "open"]


class Program(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    intent: Intent
    vars: dict[Variable, str]
    constraints: list[tuple[Predicate, Variable, str]] = []
    select: tuple[Select, Variable, SelectionAnchor] | None = None
    target: Variable
    appearance: list[str] = []
    viewpoint: tuple[float, float, float, float, float, float] | None = None

    @model_validator(mode="after")
    def valid_references(self) -> Self:
        if self.target not in self.vars:
            raise ValueError("Target is not a declared variable")
        for predicate, subject, anchor in self.constraints:
            if subject not in self.vars:
                raise ValueError(f"Undeclared variable: {subject}")
            if predicate == "NOT" and ":" in anchor:
                negated, literal = anchor.split(":", 1)
                if negated not in get_args(Predicate) or negated == "NOT":
                    raise ValueError("Unsupported negated predicate")
                if negated != "COLOR" and literal not in self.vars:
                    raise ValueError("Undeclared negated anchor")
            if predicate in {"COLOR", "NOT"}:
                continue
            anchors = anchor.split(",") if predicate == "BETWEEN" else [anchor]
            if predicate == "BETWEEN" and len(anchors) != 2:
                raise ValueError("BETWEEN needs two comma-separated anchor variables")
            if any(item not in self.vars for item in anchors):
                raise ValueError(f"Undeclared anchor variable: {anchor}")
        if self.select is not None:
            operation, subject, anchor = self.select
            if subject not in self.vars:
                raise ValueError(f"Undeclared selected variable: {subject}")
            if operation in {"CLOSEST", "FARTHEST"} and anchor not in self.vars:
                raise ValueError(f"Undeclared selection anchor: {anchor}")
        return self


@dataclass(frozen=True)
class ObjectNode:
    id: NodeId
    label: str
    confidence: float
    center: tuple[float, float, float]
    size: tuple[float, float, float]
    color: str = "unknown"
    alt_labels: tuple[str, ...] = ()
    keyframes: tuple[int, ...] = ()

    def bounds(self) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
        return (tuple(c - s / 2 for c, s in zip(self.center, self.size)),
                tuple(c + s / 2 for c, s in zip(self.center, self.size)))


@dataclass(frozen=True)
class Viewpoint:
    position: tuple[float, float, float]
    forward: tuple[float, float, float]


@dataclass
class SolveResult:
    solutions: list[dict[str, NodeId]] = field(default_factory=list)
    relaxed: str | None = None
    target: str = "t"
    viewpoint: Viewpoint | None = None

    @property
    def count(self) -> int:
        return len({solution[self.target] for solution in self.solutions if self.target in solution})

    @property
    def exists(self) -> bool:
        return bool(self.solutions)


def _label_matches(wanted: str, node: ObjectNode, *, alternatives: bool = True) -> bool:
    wanted = wanted.lower().strip().rstrip("s")
    labels = (node.label, *node.alt_labels) if alternatives else (node.label,)
    if wanted in {"object", "thing", "any", ""}:
        return True
    return any(wanted in label.lower() or label.lower() in wanted for label in labels)


def _overlap(a0: float, a1: float, b0: float, b1: float) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


def _distance(a: ObjectNode, b: ObjectNode) -> float:
    a_min, a_max = a.bounds()
    b_min, b_max = b.bounds()
    return math.sqrt(sum(max(0.0, b_min[i] - a_max[i], a_min[i] - b_max[i]) ** 2
                         for i in range(3)))


def _horizontal_overlap(a: ObjectNode, b: ObjectNode) -> float:
    a_min, a_max = a.bounds()
    b_min, b_max = b.bounds()
    return _overlap(a_min[0], a_max[0], b_min[0], b_max[0]) * _overlap(
        a_min[1], a_max[1], b_min[1], b_max[1]
    )


def _view_axes(viewpoint: Viewpoint) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    fx, fy, _ = viewpoint.forward
    length = math.hypot(fx, fy)
    if length < 1e-6:
        return (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)
    forward = (fx / length, fy / length, 0.0)
    right = (forward[1], -forward[0], 0.0)
    return right, forward


def _resolved_viewpoint(anchor: ObjectNode, camera: Viewpoint | None,
                        room_center: tuple[float, float, float]) -> Viewpoint:
    low, high = anchor.bounds()
    if camera is not None and not all(low[i] <= camera.position[i] <= high[i] for i in range(3)):
        return camera
    forward = tuple(anchor.center[i] - room_center[i] for i in range(3))
    if math.hypot(forward[0], forward[1]) < 1e-6:
        forward = (0.0, 1.0, 0.0)
    return Viewpoint(room_center, forward)


def predicate_holds(predicate: str, subject: ObjectNode, anchor: ObjectNode | None,
                    viewpoint: Viewpoint | None = None,
                    second_anchor: ObjectNode | None = None, *,
                    contact_m: float = 0.25, near_m: float = 1.0) -> bool:
    if predicate in {"COLOR", "NOT"}:
        raise ValueError("COLOR and NOT use literals and are handled by the Program solver")
    if anchor is None:
        return False
    if predicate in {"AGAINST_WALL", "ON_FLOOR", "IN_CORNER"}:
        return False  # These are read from the measured Structure graph by solve().
    s_min, s_max = subject.bounds()
    a_min, a_max = anchor.bounds()
    xy = _horizontal_overlap(subject, anchor)
    if predicate == "ON":
        return abs(s_min[2] - a_max[2]) <= contact_m and xy > 0.02
    if predicate == "UNDER":
        return s_max[2] <= a_min[2] + contact_m and xy > 0.02
    if predicate == "SUPPORTS":
        return predicate_holds("ON", anchor, subject, contact_m=contact_m)
    if predicate == "ABOVE":
        return subject.center[2] > anchor.center[2] + 0.15 and xy > 0.02
    if predicate == "BELOW":
        return predicate_holds("ABOVE", anchor, subject)
    if predicate == "IN":
        return all(s_min[i] >= a_min[i] - 0.1 and s_max[i] <= a_max[i] + 0.1
                   for i in range(3))
    if predicate == "CONTAINS":
        return predicate_holds("IN", anchor, subject)
    if predicate == "NEAR":
        return _distance(subject, anchor) <= near_m
    if predicate == "FAR":
        return _distance(subject, anchor) >= near_m * 2
    if predicate == "NEXT_TO":
        return (_distance(subject, anchor) <= near_m * 0.6 and xy < 0.02
                and _overlap(s_min[2], s_max[2], a_min[2], a_max[2]) > 0.1)
    if predicate == "BETWEEN":
        if second_anchor is None:
            return False
        ax, ay, _ = anchor.center
        bx, by, _ = second_anchor.center
        px, py, _ = subject.center
        dx, dy = bx - ax, by - ay
        length_squared = dx * dx + dy * dy
        if length_squared < 1e-6:
            return False
        t = ((px - ax) * dx + (py - ay) * dy) / length_squared
        return 0.05 < t < 0.95 and abs((px - ax) * dy - (py - ay) * dx) / math.sqrt(
            length_squared
        ) < 0.6
    if predicate in {"LEFT", "RIGHT", "FRONT", "BEHIND"}:
        if viewpoint is None:
            viewpoint = Viewpoint(position=(0.0, 0.0, 0.0),
                                  forward=tuple(anchor.center[i] for i in range(3)))
        right, forward = _view_axes(viewpoint)
        delta = tuple(subject.center[i] - anchor.center[i] for i in range(3))
        horizontal = sum(delta[i] * right[i] for i in range(3))
        depth = sum(delta[i] * forward[i] for i in range(3))
        return {"LEFT": horizontal < -0.1, "RIGHT": horizontal > 0.1,
                "FRONT": depth < -0.1, "BEHIND": depth > 0.1}[predicate]
    raise ValueError(f"Unsupported predicate: {predicate}")


def _select(solutions: list[dict[str, NodeId]], program: Program,
            objects: dict[NodeId, ObjectNode]) -> list[dict[str, NodeId]]:
    if program.select is None or not solutions:
        return solutions
    operation, subject, anchor = program.select

    def metric(solution: dict[str, NodeId]) -> float:
        node = objects[solution[subject]]
        if operation in {"CLOSEST", "FARTHEST"}:
            return _distance(node, objects[solution[anchor]])
        if operation in {"LARGEST", "SMALLEST"}:
            return math.prod(node.size)
        return node.center[2]

    values = [metric(solution) for solution in solutions]
    best = (min(values) if operation in {"CLOSEST", "SMALLEST", "LOWEST"}
            else max(values))
    return [solution for solution, value in zip(solutions, values) if abs(value - best) < 1e-5]


def solve(program: Program, nodes: list[ObjectNode],
          viewpoint: Viewpoint | None = None, graph: dict | None = None,
          semantic_scores: dict[str, dict[int, float]] | None = None) -> SolveResult:
    if program.viewpoint is not None:
        viewpoint = Viewpoint(program.viewpoint[:3], program.viewpoint[3:])
    deadline = time.monotonic() + 2.0
    objects = {node.id: node for node in nodes}
    if nodes:
        room_center = tuple((min(node.bounds()[0][axis] for node in nodes)
                             + max(node.bounds()[1][axis] for node in nodes)) / 2
                            for axis in range(3))
    else:
        room_center = (0.0, 0.0, 0.0)
    candidates = {}
    for variable, label in program.vars.items():
        primary = [node for node in nodes if _label_matches(label, node, alternatives=False)
                   and (label not in {"object", "thing", "any", ""} or isinstance(node.id, int))]
        structural = [node for node in primary if isinstance(node.id, str)]
        candidates[variable] = (structural if label in {"wall", "floor", "room"} and structural
                                else primary or [node for node in nodes if _label_matches(label, node)])
        # Preserve precise labels; semantic retrieval grounds functional descriptions
        # only when labels and strong alternatives cannot ground the variable.
        if not candidates[variable] and semantic_scores:
            scores = semantic_scores.get(variable, {})
            ranked = sorted((node for node in nodes if scores.get(node.id, 0) > 0.15),
                            key=lambda node: scores.get(node.id, 0), reverse=True)
            if ranked:
                gaps = [scores[ranked[i].id] - scores[ranked[i + 1].id] for i in range(len(ranked) - 1)]
                count = max(range(len(gaps)), key=gaps.__getitem__) + 1 if gaps else 1
                candidates[variable] = ranked[:count]
    edges = {(item["predicate"], str(item["subject"]), str(item["anchor"]))
             for item in (graph or {}).get("relations", [])}
    stored_predicates = {"ON", "UNDER", "SUPPORTS", "IN", "CONTAINS", "NEAR", "FAR",
                         "NEXT_TO", "AGAINST_WALL", "ON_FLOOR", "IN_CORNER"}

    def relation_holds(predicate: str, subject: ObjectNode, anchor: ObjectNode) -> bool:
        if graph is not None and predicate in stored_predicates:
            actual = "ON_FLOOR" if predicate == "ON" and anchor.label == "floor" else predicate
            if actual == "IN_CORNER":
                return any(item[0] == actual and item[1] == str(subject.id)
                           and str(anchor.id) in item[2].split(",") for item in edges)
            return (actual, str(subject.id), str(anchor.id)) in edges
        return predicate_holds(predicate, subject, anchor,
                               _resolved_viewpoint(anchor, viewpoint, room_center))

    def search(constraints: list[tuple[Predicate, Variable, str]]) -> list[dict[str, NodeId]]:
        assignments: list[dict[str, NodeId]] = []
        variables = sorted(candidates, key=lambda item: len(candidates[item]))

        def visit(index: int, assignment: dict[str, NodeId]) -> None:
            if time.monotonic() > deadline or len(assignments) > 10_000:
                raise RuntimeError("The query is too broad. Add a label or a relation and try again.")
            if index == len(variables):
                assignments.append(assignment.copy())
                return
            variable = variables[index]
            for candidate in candidates[variable]:
                if candidate.id in assignment.values():
                    continue
                assignment[variable] = candidate.id
                valid = True
                for predicate, subject, anchor in constraints:
                    if subject not in assignment:
                        continue
                    target = objects[assignment[subject]]
                    if predicate == "COLOR":
                        valid = target.color.lower() == anchor.lower()
                    elif predicate == "NOT":
                        if ":" in anchor:
                            negated, literal = anchor.split(":", 1)
                            if negated == "COLOR":
                                valid = target.color.lower() != literal.lower()
                            elif literal in assignment:
                                valid = not relation_holds(negated, target, objects[assignment[literal]])
                        elif anchor.lower() in {"red", "orange", "yellow", "green", "blue", "purple", "brown", "black", "white", "gray"}:
                            valid = target.color.lower() != anchor.lower()
                        else:
                            valid = not _label_matches(anchor, target)
                    elif predicate == "BETWEEN":
                        first, second = anchor.split(",")
                        if first in assignment and second in assignment:
                            first_node = objects[assignment[first]]
                            valid = predicate_holds(predicate, target, objects[assignment[first]],
                                                    _resolved_viewpoint(first_node, viewpoint,
                                                                        room_center),
                                                    objects[assignment[second]])
                    elif anchor in assignment:
                        anchor_node = objects[assignment[anchor]]
                        valid = relation_holds(predicate, target, anchor_node)
                    if not valid:
                        break
                if valid:
                    visit(index + 1, assignment)
                del assignment[variable]

        visit(0, {})
        return _select(assignments, program, objects)

    solutions = search(program.constraints)
    relaxed = None
    if not solutions and program.constraints:
        weights = {"NEAR": 0.1, "FAR": 0.2, "NEXT_TO": 0.2, "ABOVE": 0.3,
                   "BELOW": 0.3, "LEFT": 0.4, "RIGHT": 0.4}
        weakest = min(range(len(program.constraints)),
                      key=lambda index: weights.get(program.constraints[index][0], 1.0))
        relaxed = str(program.constraints[weakest])
        solutions = search([item for index, item in enumerate(program.constraints)
                            if index != weakest])
    def rank(assignment: dict[str, NodeId]) -> float:
        confidence = math.prod(objects[object_id].confidence for object_id in assignment.values())
        identifiers = list(assignment.values())
        distances = [_distance(objects[identifiers[i]], objects[identifiers[j]])
                     for i in range(len(identifiers)) for j in range(i + 1, len(identifiers))]
        return confidence - (sum(distances) / len(distances) * 0.02 if distances else 0)

    solutions.sort(key=lambda assignment: -rank(assignment))
    used_viewpoint = viewpoint or Viewpoint(room_center, (0.0, 1.0, 0.0))
    if solutions:
        for predicate, _, anchor in program.constraints:
            first_anchor = anchor.split(",")[0]
            if predicate not in {"COLOR", "NOT"} and first_anchor in solutions[0]:
                used_viewpoint = _resolved_viewpoint(objects[solutions[0][first_anchor]], viewpoint, room_center)
                break
    return SolveResult(solutions=solutions, relaxed=relaxed, target=program.target,
                       viewpoint=used_viewpoint)
