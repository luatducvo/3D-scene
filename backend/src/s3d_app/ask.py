"""Ground English queries against persisted Objects and stream verified results."""

import json
import os
import re
import time
import uuid
from collections.abc import Iterator
from typing import Any

import numpy as np
from pydantic import ValidationError

from s3d_app.gpu import GPU, InsufficientGpuMemory
from s3d_app.llm import LlmRouter, model_session
from s3d_app.pipeline import artifact_dir
from s3d_app.retrieval import normalize_nouns, similarities
from s3d_app.scene_graph import Relation, serialize_node
from s3d_app.solver import NodeId, ObjectNode, Program, Viewpoint, solve
from s3d_app.storage import database
from s3d_app.vision import annotated_frames, caption, chat_with_images, tiebreak, verified_wording

RELATION_WORDS = {"near", "next", "beside", "on", "under", "above", "below", "left",
                  "right", "front", "behind", "between", "closest", "farthest",
                  "largest", "smallest", "highest", "lowest", "color", "how", "what",
                  "which", "is", "are", "does", "describe", "used"}
ALIASES = {"sofa": "couch", "couches": "couch", "chairs": "chair", "tables": "table",
           "desks": "desk", "beds": "bed", "lamps": "lamp"}
REFERENCE_PATTERN = r"\b(?:this one|that one|it|this(?!\s+room)|that(?!\s+room))\b"


def is_lookup(text: str) -> bool:
    if re.match(r"^(something|anything|a place|a thing) to\b", text.lower().strip()):
        return True
    words = set(re.findall(r"[a-z]+", text.lower()))
    return bool(words) and not bool(words & RELATION_WORDS)


def select_gap(scores: list[float]) -> int:
    """Choose the result count at the largest adjacent similarity drop."""
    if not scores:
        return 0
    if len(scores) == 1:
        return 1
    return max(range(len(scores) - 1), key=lambda index: scores[index] - scores[index + 1]) + 1


def lookup(text: str, objects: list[dict], semantic_scores: dict[int, float] | None = None) -> list[int]:
    query = re.sub(r"^(find|show|the|all|a|an)\s+", "", text.lower().strip())
    colors = {"red", "orange", "yellow", "green", "blue", "purple", "brown", "black", "white", "gray"}
    color = next((word for word in query.split() if word in colors), None)
    if color:
        query = " ".join(word for word in query.split() if word != color)
    query = ALIASES.get(query, query.rstrip("s"))
    scored = []
    for item in objects:
        if color and item.get("color") != color:
            continue
        labels = [item["label"], *item.get("alt_labels", [])]
        match = max((1.0 if query == label.lower() else 0.7 if query in label.lower()
                     or label.lower() in query else 0.0) for label in labels)
        semantic = (semantic_scores or {}).get(item["id"], 0.0)
        if match or semantic > 0.15:
            scored.append((match * item["confidence"] + semantic, item["id"]))
    scored.sort(reverse=True)
    if not scored:
        return []
    values = [score for score, _ in scored]
    count = select_gap(values) if len(values) > 1 else 1
    if len(values) > 1 and values[-1] > 0.5:
        count = len(values)
    return [object_id for _, object_id in scored[:count]]


def _node(item: dict) -> ObjectNode:
    return ObjectNode(item["id"], item["label"], item["confidence"],
                      tuple(item["center"]), tuple(item["size"]), item["color"],
                      tuple(alt for alt in item.get("alt_labels", [])
                            if item.get("label_distribution", {}).get(alt, 1.0) >= 0.1),
                      tuple(item.get("keyframes", [])))


def _load_objects(scene_id: str) -> list[dict]:
    with database() as connection:
        return [json.loads(row["data"]) for row in connection.execute(
            "SELECT data FROM objects WHERE scene_id = ? ORDER BY id", (scene_id,))]


def scene_context(scene_id: str, objects: list[dict]) -> tuple[list[dict], dict | None]:
    path = artifact_dir(scene_id, "S5") / "graph.json"
    if not path.is_file():
        return objects, None
    graph = json.loads(path.read_text())
    geometry_path = artifact_dir(scene_id, "S2") / "geometry.npz"
    if geometry_path.is_file():
        with np.load(geometry_path, allow_pickle=False) as geometry:
            points = geometry["points"]
            lower, upper = points.min(axis=0), points.max(axis=0)
    elif objects:
        lower = np.min([np.asarray(item["center"]) - np.asarray(item["size"]) / 2 for item in objects], axis=0)
        upper = np.max([np.asarray(item["center"]) + np.asarray(item["size"]) / 2 for item in objects], axis=0)
    else:
        lower, upper = np.zeros(3), np.ones(3)
    records = list(objects)
    for node in graph["nodes"]:
        if node["level"] == "object":
            continue
        if node["level"] == "room":
            center, size, label = (lower + upper) / 2, upper - lower, "room"
        elif node["kind"] == "floor":
            center = (lower + upper) / 2
            center[2] = node["offset"]
            size = upper - lower
            size[2] = 0.03
            label = "floor"
        else:
            minimum, maximum = np.asarray(node["min"]), np.asarray(node["max"])
            center, size, label = (minimum + maximum) / 2, maximum - minimum, "wall"
        records.append({"id": node["id"], "label": label, "confidence": 1.0,
                        "center": center.tolist(), "size": size.tolist(), "color": "unknown",
                        "alt_labels": [], "keyframes": [], "level": node["level"]})
    return records, graph


def _session(scene_id: str, session_id: str | None) -> tuple[str, dict | None]:
    if session_id:
        with database() as connection:
            row = connection.execute("SELECT * FROM sessions WHERE id = ? AND scene_id = ?",
                                     (session_id, scene_id)).fetchone()
        if row:
            return session_id, dict(row)
    return uuid.uuid4().hex, None


def _save_session(scene_id: str, session_id: str, last: NodeId | None,
                  pending: list[NodeId] | None = None, context: dict | None = None) -> None:
    with database() as connection:
        connection.execute("INSERT INTO sessions(id, scene_id, last_object_id, pending_targets, pending_context) "
                           "VALUES (?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET "
                           "last_object_id=excluded.last_object_id, "
                           "pending_targets=excluded.pending_targets, pending_context=excluded.pending_context, "
                           "updated_at=CURRENT_TIMESTAMP",
                           (session_id, scene_id, last, json.dumps(pending) if pending else None,
                            json.dumps(context) if context else None))


def _record(scene_id: str, session_id: str, text: str, program: Program | None,
            viewpoint: Viewpoint | None, result: dict, n_solutions: int,
            retry: int, started: float) -> None:
    with database() as connection:
        connection.execute("INSERT INTO queries(scene_id,session_id,text,program,viewpoint,result,"
                           "n_solutions,json_retry,latency_ms,used_tiebreak) VALUES (?,?,?,?,?,?,?,?,?,?)",
                           (scene_id, session_id, text,
                            program.model_dump_json() if program else None,
                            json.dumps(viewpoint.__dict__) if viewpoint else None,
                            json.dumps(result), n_solutions, retry,
                            round((time.monotonic() - started) * 1000, 1),
                            int(result.get("used_tiebreak", False))))


def _program_prompt(question: str, labels: list[str]) -> list[dict]:
    examples = [
        ('the chair next to the desk', '{"intent":"ground","vars":{"t":"chair","a":"desk"},"constraints":[["NEXT_TO","t","a"]],"target":"t","appearance":[]}'),
        ('how many chairs are near the table?', '{"intent":"count","vars":{"t":"chair","a":"table"},"constraints":[["NEAR","t","a"]],"target":"t","appearance":[]}'),
        ('is there a lamp on the desk?', '{"intent":"exists","vars":{"t":"lamp","a":"desk"},"constraints":[["ON","t","a"]],"target":"t","appearance":[]}'),
        ('the red chair', '{"intent":"ground","vars":{"t":"chair"},"constraints":[["COLOR","t","red"]],"target":"t","appearance":["red"]}'),
        ('the chair closest to the door', '{"intent":"ground","vars":{"t":"chair","a":"door"},"constraints":[],"select":["CLOSEST","t","a"],"target":"t","appearance":[]}'),
        ('the largest table', '{"intent":"ground","vars":{"t":"table"},"constraints":[],"select":["LARGEST","t",""],"target":"t","appearance":[]}'),
        ('what color is the couch near the door?', '{"intent":"attribute","vars":{"t":"couch","a":"door"},"constraints":[["NEAR","t","a"]],"target":"t","appearance":[]}'),
        ('what is this room used for?', '{"intent":"open","vars":{"t":"object"},"constraints":[],"target":"t","appearance":[]}'),
    ]
    system = ("Return only a JSON Program. Use vars t,a,b,c,d,w. Every relation anchor must "
              "refer to a declared variable. Keep nouns literally; prefer a matching available label or alias, "
              "but do not replace an absent noun with an unrelated label. Viewpoint must be null. "
              "select is null or an array [operation,subject,anchor]; for size/height operations anchor is an empty string. "
              "highest=HIGHEST, lowest=LOWEST, smallest=SMALLEST, farthest=FARTHEST. Available labels: "
              + ", ".join(labels) + ". Examples:\n" + "\n".join(
                  f"Q: {query}\nA: {answer}" for query, answer in examples))
    return [{"role": "system", "content": system}, {"role": "user", "content": question}]


def generate_program(question: str, labels: list[str], router: LlmRouter) -> tuple[Program | None, int]:
    schema = Program.model_json_schema()
    response_format = {"type": "json_schema", "json_schema": {
        "name": "program", "strict": True, "schema": schema}}
    messages = _program_prompt(question, labels)
    raw = ""
    for retry in range(2):
        try:
            with model_session(router, "qwen3-vl-4b-text", 3200, GPU):
                response = router.chat("qwen3-vl-4b-text", messages,
                                       response_format, max_tokens=400)
            raw = response["choices"][0]["message"]["content"]
            return Program.model_validate_json(raw), retry
        except (ValueError, KeyError, TypeError, ValidationError) as exc:
            messages += [{"role": "assistant", "content": raw},
                         {"role": "user", "content": "Correct this validation error and return only Program JSON: " + str(exc)[:300]}]
            continue
    return None, 1


def repair_program(program: Program, text: str) -> Program:
    lower = text.lower()
    program.viewpoint = None
    if re.search(r"\bhow many\b", lower):
        program.intent = "count"
    elif re.match(r"^(is|are) (there|any)\b", lower):
        program.intent = "exists"
    elif re.search(r"\bwhat colou?r\b", lower):
        program.intent = "attribute"
    elif "room" in lower and ("used for" in lower or "describe" in lower):
        program.intent = "open"
        program.vars = {"t": "object"}
        program.target = "t"
        program.constraints = []
        program.select = None
    elif re.search(r"\bwhat (material|shape|texture)\b|\bmade of\b|^describe\b", lower):
        program.intent = "attribute"
    for appearance in ("wooden", "metallic", "striped", "round", "transparent", "shiny"):
        if appearance in lower and appearance not in program.appearance:
            program.appearance.append(appearance)
    for word, operation in (("largest", "LARGEST"), ("smallest", "SMALLEST"),
                            ("highest", "HIGHEST"), ("lowest", "LOWEST")):
        if word in lower:
            program.select = (operation, program.target, "")
    for words, operation in ((("closest", "nearest"), "CLOSEST"), (("farthest", "furthest"), "FARTHEST")):
        if any(word in lower for word in words):
            anchors = [variable for variable in program.vars if variable != program.target]
            if len(anchors) == 1:
                program.select = (operation, program.target, anchors[0])
                program.constraints = [constraint for constraint in program.constraints
                                       if constraint[0] not in {"NEAR", "FAR"}]
    return program


def apply_explicit_viewpoint(program: Program, text: str, records: list[dict]) -> None:
    directional = next((constraint for constraint in program.constraints
                        if constraint[0] in {"LEFT", "RIGHT", "FRONT", "BEHIND"}), None)
    match = re.search(r"\bfrom (?:the )?([a-z ]+?)(?:['’]s viewpoint)?[?.!]*$", text.lower())
    if directional is None or match is None:
        return
    source_label = match.group(1).strip()
    sources = [item for item in records if source_label == item["label"].lower()
               or source_label in item.get("alt_labels", [])]
    anchor_label = program.vars[directional[2]]
    anchors = [item for item in records if anchor_label == item["label"].lower()]
    if not sources or not anchors:
        return
    source = max(sources, key=lambda item: item["confidence"])
    anchor = max(anchors, key=lambda item: item["confidence"])
    forward = np.asarray(anchor["center"]) - np.asarray(source["center"])
    program.viewpoint = tuple(source["center"] + forward.tolist())


def language_reply(router: LlmRouter, messages: list[dict]) -> str:
    with model_session(router, "qwen3-vl-4b-text", 3200, GPU):
        response = router.chat("qwen3-vl-4b-text", messages)
    return response["choices"][0]["message"]["content"].strip()


def stream_verified_wording(router: LlmRouter, fact: str, identifiers: set[int],
                            numbers: set[int]) -> Iterator[str]:
    messages = [{"role": "system", "content":
        "Rephrase this verified Solver fact in one short natural sentence. Keep its exact count and "
        "Object IDs. Add no facts or quantities. Fact: " + fact}]
    with model_session(router, "qwen3-vl-4b-text", 3200, GPU):
        buffered = ""
        accepted = ""
        for chunk in router.stream_chat("qwen3-vl-4b-text", messages):
            buffered += chunk
            while re.search(r"\s", buffered):
                match = re.search(r"\s+", buffered)
                piece, buffered = buffered[:match.end()], buffered[match.end():]
                if verified_wording(accepted + piece, "", identifiers, numbers) == "":
                    raise ValueError("LLM wording added an unverified ID or quantity")
                accepted += piece
                yield piece
        if buffered:
            if verified_wording(accepted + buffered, "", identifiers, numbers) == "":
                raise ValueError("LLM wording added an unverified ID or quantity")
            yield buffered


def _answer_events(scene_id: str, body: dict[str, Any],
                  router: LlmRouter | None = None) -> Iterator[tuple[str, dict]]:
    started = time.monotonic()
    text = str(body.get("text", "")).strip()
    direct_reference = text.lower() in {"it", "that", "this", "this one", "that one"}
    if not text and body.get("program") is None and body.get("selected_object_id") is None and body.get("choice_id") is None:
        yield "clarify", {"message": "Enter an English question."}
        return
    objects = _load_objects(scene_id)
    records, graph = scene_context(scene_id, objects)
    by_id = {item["id"]: item for item in records}
    session_id, session = _session(scene_id, body.get("session_id"))
    viewpoint = Viewpoint(**body["viewpoint"]) if body.get("viewpoint") else None
    used_viewpoint = viewpoint
    selected_id = body.get("selected_object_id")
    choice_id = body.get("choice_id", selected_id if not text else None)
    program = None
    debug_program = body.get("program") is not None
    chosen_id = None
    retry = 0
    used_tiebreak = False
    related_ids: list[NodeId] = []
    active_router = router or LlmRouter()
    reference_id = selected_id if selected_id in by_id else session["last_object_id"] if session else None
    had_reference = bool(re.search(REFERENCE_PATTERN, text.lower()))
    if not direct_reference and reference_id in by_id and had_reference:
        text = re.sub(REFERENCE_PATTERN, by_id[reference_id]["label"], text,
                      flags=re.IGNORECASE)
    targets: list[NodeId]
    if choice_id is not None and session and session["pending_targets"]:
        pending = json.loads(session["pending_targets"])
        if choice_id not in pending or choice_id not in by_id:
            yield "clarify", {"message": "Choose one of the shown candidates.", "candidates": pending,
                              "session_id": session_id}
            return
        targets = [choice_id]
        chosen_id = choice_id
        if session.get("pending_context"):
            context = json.loads(session["pending_context"])
            program = Program.model_validate(context["program"])
            text = context["text"]
            debug_program = context.get("debug", False)
            viewpoint = Viewpoint(**context["viewpoint"]) if context.get("viewpoint") else viewpoint
    elif direct_reference:
        recent = reference_id
        if recent not in by_id and session and session["pending_targets"]:
            pending = [identifier for identifier in json.loads(session["pending_targets"]) if identifier in by_id]
            yield "clarify", {"message": "Choose which Object you mean.", "session_id": session_id,
                "candidates": [{"id": identifier, "label": by_id[identifier]["label"],
                                "color": by_id[identifier]["color"], "size": by_id[identifier]["size"]}
                               for identifier in pending[:8]]}
            return
        targets = [recent] if recent in by_id else []
    elif body.get("program") is not None:
        if os.getenv("S3D_DEBUG_PROGRAM") != "1":
            yield "clarify", {"message": "Program debug mode is disabled."}
            return
        try:
            program = Program.model_validate(body["program"])
        except ValidationError as exc:
            yield "clarify", {"message": str(exc)}
            return
        targets = []
    elif is_lookup(text):
        plain = text.lower().strip().removeprefix("the ").rstrip("s")
        if plain in {"room", "floor", "wall"}:
            targets = lookup(text, [item for item in records if isinstance(item["id"], str)])
        else:
            targets = lookup(text, objects, similarities(scene_id, text))
    else:
        try:
            program, retry = generate_program(text, sorted({item["label"] for item in records}),
                                              active_router)
        except (InsufficientGpuMemory, OSError) as exc:
            yield "clarify", {"message": str(exc), "session_id": session_id}
            return
        if program is None:
            yield "clarify", {"message": "Please rephrase the question.", "session_id": session_id,
                              "json_retry": retry}
            return
        targets = []

    if program:
        if not debug_program:
            program = repair_program(program, text)
        program.vars = normalize_nouns(program.vars, records)
        if not debug_program:
            apply_explicit_viewpoint(program, text, records)
        for color in program.appearance:
            if color in {"red", "orange", "yellow", "green", "blue", "purple", "brown", "black", "white", "gray"}:
                constraint = ("COLOR", program.target, color)
                if constraint not in program.constraints:
                    program.constraints.append(constraint)
        yield "program", program.model_dump()
        if program.intent == "open":
            relations = [Relation(**item) for item in (graph or {}).get("relations", [])
                         if item["predicate"] != "FAR"]
            words = set(re.findall(r"[a-z]+", text.lower()))
            relevant = [item for item in objects if words.intersection(item["label"].lower().split())]
            if relevant:
                relevant_ids = {str(item["id"]) for item in relevant}
                neighbor_ids = {edge.anchor for edge in relations if edge.subject in relevant_ids}
                context_objects = [item for item in objects if str(item["id"]) in relevant_ids | neighbor_ids]
            else:
                context_objects = objects
            summary = "Room → floor/walls → Objects\n" + "\n".join(
                serialize_node(_node(item), relations) for item in sorted(
                    context_objects, key=lambda item: item.get("vertices", 0), reverse=True))
            summary = summary[:9000]
            if not active_router.managed:
                summary = "Available labels: " + ", ".join(sorted({item["label"] for item in records}))
            try:
                proposed = language_reply(active_router, [{"role": "system", "content":
                    "Answer from the measured Scene Object summary. Mark uncertain room purpose as an inference. "
                    "Do not invent IDs or counts.\n" + summary}, {"role": "user", "content": text}])
                answer = verified_wording(proposed, "The Scene contains " + ", ".join(
                    sorted({item["label"] for item in objects})[:15]) + ".", set(), set())
            except (OSError, InsufficientGpuMemory) as exc:
                answer = str(exc)
            payload = {"answer": answer, "targets": [], "related": [],
                       "target_ids": [], "program": program.model_dump(),
                       "evidence": {"frames": [], "n_solutions": 0, "tiebreak": False},
                       "session_id": session_id,
                       "latency_ms": round((time.monotonic() - started) * 1000, 1)}
            payload.update(json_retry=retry, n_solutions=0)
            for word in answer.split():
                yield "token", {"text": word + " "}
            yield "final", payload
            return
        semantic = {variable: similarities(scene_id, phrase) for variable, phrase in program.vars.items()
                    if phrase not in {"object", "thing", "any", "wall", "floor", "room"}}
        result = solve(program, [_node(item) for item in records], viewpoint, graph, semantic)
        used_viewpoint = result.viewpoint
        if had_reference and reference_id in by_id and program.vars[program.target] == by_id[reference_id]["label"]:
            result.solutions = [solution for solution in result.solutions
                                if solution[program.target] == reference_id]
        if chosen_id is not None:
            result.solutions = [solution for solution in result.solutions
                                if solution[program.target] == chosen_id]
        targets = list(dict.fromkeys(solution[program.target] for solution in result.solutions))
        yield "candidates", {"targets": targets, "count": result.count,
                              "relaxed": result.relaxed}
        if len(targets) > 1 and program.appearance:
            yield "tiebreak", {"status": "checking", "targets": targets[:6]}
            try:
                chosen, _frames = tiebreak(scene_id, text, records, targets[:6], active_router)
                if chosen is not None:
                    targets = [chosen]
                    result.solutions = [solution for solution in result.solutions
                                        if solution[program.target] == chosen]
                    used_tiebreak = True
            except (OSError, InsufficientGpuMemory, ValueError):
                yield "tiebreak", {"status": "unavailable"}
        if program.intent == "count":
            answer = f"I found {result.count}."
        elif program.intent == "exists":
            answer = "Yes." if result.exists else "No."
        elif len(targets) > 1:
            candidates = [{"id": item_id, "label": by_id[item_id]["label"],
                           "color": by_id[item_id]["color"],
                           "size": by_id[item_id]["size"], "center": by_id[item_id]["center"]}
                          for item_id in targets[:8]]
            _save_session(scene_id, session_id, None, targets,
                          {"program": program.model_dump(), "text": text,
                           "viewpoint": viewpoint.__dict__ if viewpoint else None,
                           "debug": debug_program})
            payload = {"message": "Several Objects match. Choose one.",
                       "candidates": candidates, "session_id": session_id}
            payload.update(json_retry=retry, n_solutions=len(result.solutions))
            yield "clarify", payload
            return
        elif targets:
            item = by_id[targets[0]]
            if program.intent == "attribute":
                if "color" in text.lower():
                    answer = f"The {item['label']} is {item['color']}."
                else:
                    try:
                        if "describe" in text.lower() or "caption" in text.lower():
                            proposed = caption(scene_id, item, active_router)
                        else:
                            frames = annotated_frames(scene_id, objects, targets)
                            proposed = chat_with_images(active_router, text,
                                                        [frame["url"] for frame in frames])
                        answer = verified_wording(proposed, "I could not verify that attribute.",
                                                  set(targets), set())
                    except (OSError, ValueError, InsufficientGpuMemory) as exc:
                        answer = str(exc)
            else:
                answer = f"I found the {item['label']} (Object {item['id']})."
        else:
            answer = "I could not find a matching Object."
        if result.relaxed:
            answer += f" I relaxed {result.relaxed}."
        n_solutions = len(result.solutions)
        related_ids = sorted({identifier for solution in result.solutions
                              for variable, identifier in solution.items()
                              if variable != program.target and identifier not in targets}, key=str)
    else:
        yield "candidates", {"targets": targets}
        if not targets:
            answer = "I could not find a matching Object."
        elif len(targets) == 1:
            item = by_id[targets[0]]
            answer = f"I found the {item['label']} (Object {item['id']})."
        else:
            answer = f"I found {len(targets)} matching Objects."
        n_solutions = len(targets)
    evidence = [{"object_id": item_id, "frame_id": by_id[item_id]["keyframes"][0]}
                for item_id in targets if by_id[item_id].get("keyframes")]
    streamed = False
    if program and program.intent in {"ground", "count", "exists"} and not debug_program and active_router.managed:
        fallback = answer
        chunks = []
        try:
            for chunk in stream_verified_wording(active_router, fallback, set(targets),
                                                  {result.count}):
                chunks.append(chunk)
                yield "token", {"text": chunk}
            answer = "".join(chunks).strip() or fallback
            streamed = bool(chunks)
        except (OSError, ValueError, InsufficientGpuMemory):
            answer = fallback
            yield "reset", {"text": fallback}
            streamed = True
    evidence_payload = {"frames": evidence, "n_solutions": n_solutions,
                        "tiebreak": used_tiebreak,
                        "viewpoint": "program" if program and program.viewpoint else "camera" if viewpoint == used_viewpoint and viewpoint else "room",
                        "keyframe": f"/v1/scenes/{scene_id}/frames/{evidence[0]['frame_id']}.jpg" if evidence else None}
    payload = {"answer": answer, "target_ids": targets,
               "targets": [{"id": identifier, "label": by_id[identifier]["label"],
                            "confidence": by_id[identifier]["confidence"],
                            "bbox": {"center": by_id[identifier]["center"],
                                     "size": by_id[identifier]["size"]}} for identifier in targets],
               "related": [{"id": identifier, "label": by_id[identifier]["label"]}
                           for identifier in related_ids],
               "program": program.model_dump() if program else None,
               "evidence": evidence_payload, "session_id": session_id,
               "viewpoint": used_viewpoint.__dict__ if used_viewpoint else None,
               "used_tiebreak": used_tiebreak,
               "json_retry": retry, "n_solutions": n_solutions,
               "latency_ms": round((time.monotonic() - started) * 1000, 1)}
    _save_session(scene_id, session_id, targets[0] if len(targets) == 1 else None,
                  targets if len(targets) > 1 else None)
    if not streamed:
        for word in answer.split():
            yield "token", {"text": word + " "}
    yield "final", payload


def answer_events(scene_id: str, body: dict[str, Any],
                  router: LlmRouter | None = None) -> Iterator[tuple[str, dict]]:
    started = time.monotonic()
    program = None
    outcome = {"message": "The query was interrupted."}
    try:
        for event, payload in _answer_events(scene_id, body, router):
            if event == "program":
                program = Program.model_validate(payload)
            if event in {"final", "clarify", "error"}:
                outcome = payload
            if event == "final":
                records, _ = scene_context(scene_id, _load_objects(scene_id))
                valid_ids = {item["id"] for item in records}
                if any(identifier not in valid_ids for identifier in payload.get("target_ids", [])):
                    raise ValueError("Answer references an Object outside this Scene")
            yield event, payload
    except (OSError, ValueError, RuntimeError) as exc:
        outcome = {"message": str(exc)}
        yield "error", outcome
    finally:
        viewpoint = (Viewpoint(**outcome["viewpoint"]) if outcome.get("viewpoint") else
                     Viewpoint(program.viewpoint[:3], program.viewpoint[3:])
                     if program and program.viewpoint else
                     Viewpoint(**body["viewpoint"]) if body.get("viewpoint") else None)
        _record(scene_id, outcome.get("session_id") or body.get("session_id") or uuid.uuid4().hex,
                str(body.get("text", "")), program, viewpoint, outcome,
                outcome.get("n_solutions", 0), outcome.get("json_retry", 0), started)
