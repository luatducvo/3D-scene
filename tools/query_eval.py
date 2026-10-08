"""Local-only comparison of natural questions with hand-authored Solver Programs."""

import argparse
import json
import time
import urllib.request
from pathlib import Path

from s3d_app.ask import _node, scene_context
from s3d_app.retrieval import similarities
from s3d_app.solver import Program, Viewpoint, solve


def case(question, label="object", intent="ground", predicate=None, anchor=None, select=None):
    variables = {"t": label}
    constraints = []
    if anchor:
        variables["a"] = anchor
    if predicate:
        constraints.append([predicate, "t", "a"])
    return question, {"intent": intent, "vars": variables, "constraints": constraints,
                      "select": [select, "t", "a" if anchor else ""] if select else None,
                      "target": "t", "appearance": []}


CASES = [
    case("the stool next to the desk", "stool", predicate="NEXT_TO", anchor="desk"),
    case("the bed near the desk", "bed", predicate="NEAR", anchor="desk"),
    case("the lamp on the table", "lamp", predicate="ON", anchor="table"),
    case("the cabinet behind the stool", "cabinet", predicate="BEHIND", anchor="stool"),
    case("the pillow under the blanket", "pillow", predicate="UNDER", anchor="blanket"),
    case("the couch near the window", "couch", predicate="NEAR", anchor="window"),
    case("the nearest stool to the door", "stool", anchor="door", select="CLOSEST"),
    case("the largest table", "table", select="LARGEST"),
    case("the smallest lamp", "lamp", select="SMALLEST"),
    case("the highest shelf", "shelf", select="HIGHEST"),
    case("the lowest cabinet", "cabinet", select="LOWEST"),
    case("How many stools?", "stool", "count"),
    case("How many tables?", "table", "count"),
    case("How many pillows are on the bed?", "pillow", "count", "ON", "bed"),
    case("How many cabinets are near the desk?", "cabinet", "count", "NEAR", "desk"),
    case("Is there a lamp on the table?", "lamp", "exists", "ON", "table"),
    case("Is there a stool next to the window?", "stool", "exists", "NEXT_TO", "window"),
    case("Is there a pillow on the bed?", "pillow", "exists", "ON", "bed"),
    case("the desk to the left of the bed", "desk", predicate="LEFT", anchor="bed"),
    case("the cabinet to the right of the desk", "cabinet", predicate="RIGHT", anchor="desk"),
    case("the stool in front of the couch", "stool", predicate="FRONT", anchor="couch"),
    case("the table farthest from the window", "table", anchor="window", select="FARTHEST"),
    case("the stool closest to the desk", "stool", anchor="desk", select="CLOSEST"),
    case("the cabinet above the table", "cabinet", predicate="ABOVE", anchor="table"),
    case("the pillow below the shelf", "pillow", predicate="BELOW", anchor="shelf"),
    case("What color is the couch near the door?", "couch", "attribute", "NEAR", "door"),
    case("What color is the largest cabinet?", "cabinet", "attribute", select="LARGEST"),
    case("What color is the bed?", "bed", "attribute"),
    case("What is this room used for?", "object", "open"),
    case("Describe the furniture in this room.", "object", "open"),
]
VIEWPOINT = {"position": [0, -10, 2], "forward": [0, 1, 0]}


def request(url: str, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as response:
        return response.read().decode()


def events(raw: str):
    parsed = []
    for block in raw.split("\n\n"):
        lines = block.splitlines()
        event = next((line[7:] for line in lines if line.startswith("event: ")), None)
        data = next((line[6:] for line in lines if line.startswith("data: ")), None)
        if event and data:
            parsed.append((event, json.loads(data)))
    return parsed


def run(base_url: str, scene: str) -> dict:
    objects = json.loads(request(f"{base_url}/v1/scenes/{scene}/objects"))
    records, graph = scene_context(scene, objects)
    nodes = [_node(item) for item in records]
    def evaluate(program):
        semantic = {variable: similarities(scene, phrase) for variable, phrase in program.vars.items()
                    if phrase not in {"object", "thing", "any", "wall", "floor", "room"}}
        return solve(program, nodes, Viewpoint(**VIEWPOINT), graph=graph, semantic_scores=semantic)
    rows = []
    for index, (question, expected_json) in enumerate(CASES):
        started = time.monotonic()
        expected_program = Program.model_validate(expected_json)
        expected = evaluate(expected_program)
        expected_targets = {solution[expected_program.target] for solution in expected.solutions}
        row = {"question": question, "expected_program": expected_json}
        try:
            received = events(request(f"{base_url}/v1/scenes/{scene}/ask",
                                      {"text": question, "viewpoint": VIEWPOINT}))
            generated = next((data for name, data in received if name == "program"), None)
            program = Program.model_validate(generated) if generated else None
            row["program_valid"] = program is not None
            row["program"] = generated
            row["intent_correct"] = program is not None and program.intent == expected_program.intent
            row["events"] = [name for name, _ in received if name != "token"]
            if expected_program.intent == "open":
                row["solution_correct"] = None
            elif program is not None and program.intent != "open":
                actual = evaluate(program)
                targets = {solution[program.target] for solution in actual.solutions}
                row.update(expected_targets=sorted(expected_targets, key=str), actual_targets=sorted(targets, key=str),
                           solution_correct=(program.intent == expected_program.intent and
                                             targets == expected_targets))
            else:
                row["solution_correct"] = False
            if index < 10:
                manual = events(request(f"{base_url}/v1/scenes/{scene}/ask",
                                         {"program": expected_json, "viewpoint": VIEWPOINT}))
                candidates = next((data for name, data in manual if name == "candidates"), {})
                row["manual_program_pass"] = set(candidates.get("targets", [])) == expected_targets
        except (OSError, ValueError, StopIteration) as exc:
            row.update(error=str(exc), program_valid=False, solution_correct=False)
        row["seconds"] = round(time.monotonic() - started, 2)
        rows.append(row)
        if (index + 1) % 5 == 0:
            print(f"Evaluated {index + 1}/{len(CASES)} questions", flush=True)
    semantic = [row for row in rows if row.get("solution_correct") is not None]
    return {"scene": scene, "cases": len(rows),
            "program_valid": sum(row["program_valid"] for row in rows),
            "solution_correct": sum(row.get("solution_correct", False) for row in semantic),
            "solution_cases": len(semantic),
            "manual_program_pass": sum(row.get("manual_program_pass", False) for row in rows),
            "manual_cases": 10, "method": "Compare target sets with hand-authored Programs on the same measured Objects; this is not a ground-truth ScanRefer score.",
            "results": rows}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--scene", default="scene0000_00")
    parser.add_argument("--out", type=Path, default=Path("docs/spikes/query-eval.json"))
    args = parser.parse_args()
    report = run(args.base_url, args.scene)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2))
    print(json.dumps({key: value for key, value in report.items() if key != "results"}))
