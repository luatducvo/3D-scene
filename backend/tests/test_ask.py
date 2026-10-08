import json

from s3d_app.ask import answer_events, is_lookup, lookup, select_gap
from s3d_app.storage import database


def test_lookup_router_and_gap():
    assert is_lookup("chairs")
    assert not is_lookup("the chair next to the desk")
    assert select_gap([0.94, 0.91, 0.42, 0.4]) == 2
    objects = [{"id": 1, "label": "chair", "alt_labels": [], "confidence": 0.9},
               {"id": 2, "label": "table", "alt_labels": [], "confidence": 0.8}]
    assert lookup("chairs", objects) == [1]


def test_lookup_stream_logs_query_and_resolves_pronoun(monkeypatch, tmp_path):
    monkeypatch.setenv("S3D_DATA_DIR", str(tmp_path))
    item = {"id": 7, "label": "chair", "alt_labels": [], "confidence": 0.9,
            "center": [0, 0, 0], "size": [1, 1, 1], "color": "red", "keyframes": [10]}
    with database() as connection:
        connection.execute("INSERT INTO objects(scene_id,id,data) VALUES (?,?,?)",
                           ("scene", 7, json.dumps(item)))
    events = list(answer_events("scene", {"text": "chairs"}))
    final = events[-1][1]
    assert final["target_ids"] == [7]
    assert final["evidence"]["frames"] == [{"object_id": 7, "frame_id": 10}]
    followup = list(answer_events("scene", {"text": "it", "session_id": final["session_id"]}))
    assert followup[-1][1]["target_ids"] == [7]
    with database() as connection:
        assert connection.execute("SELECT COUNT(*) FROM queries").fetchone()[0] == 2


def test_debug_program_clarifies_ambiguity(monkeypatch, tmp_path):
    monkeypatch.setenv("S3D_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("S3D_DEBUG_PROGRAM", "1")
    with database() as connection:
        for identifier in (1, 2):
            item = {"id": identifier, "label": "chair", "alt_labels": [],
                    "confidence": 0.8, "center": [identifier, 0, 0], "size": [1, 1, 1],
                    "color": "gray", "keyframes": []}
            connection.execute("INSERT INTO objects(scene_id,id,data) VALUES (?,?,?)",
                               ("scene", identifier, json.dumps(item)))
    program = {"intent": "ground", "vars": {"t": "chair"}, "target": "t"}
    events = list(answer_events("scene", {"text": "chairs", "program": program}))
    clarify = events[-1][1]
    assert events[-1][0] == "clarify"
    assert {item["id"] for item in clarify["candidates"]} == {1, 2}
    choice = list(answer_events("scene", {"selected_object_id": 2,
                                          "session_id": clarify["session_id"]}))
    assert choice[-1][1]["target_ids"] == [2]


def test_clarify_choice_preserves_attribute_question(monkeypatch, tmp_path):
    monkeypatch.setenv("S3D_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("S3D_DEBUG_PROGRAM", "1")
    with database() as connection:
        for identifier, color in ((1, "red"), (2, "blue")):
            item = {"id": identifier, "label": "chair", "alt_labels": [],
                    "confidence": 0.8, "center": [identifier, 0, 0], "size": [1, 1, 1],
                    "color": color, "keyframes": []}
            connection.execute("INSERT INTO objects(scene_id,id,data) VALUES (?,?,?)",
                               ("scene", identifier, json.dumps(item)))
    program = {"intent": "attribute", "vars": {"t": "chair"}, "target": "t"}
    clarify = list(answer_events("scene", {"text": "What color is the chair?", "program": program}))[-1][1]
    chosen = list(answer_events("scene", {"choice_id": 2, "session_id": clarify["session_id"]}))[-1][1]
    assert chosen["target_ids"] == [2]
    assert chosen["answer"] == "The chair is blue."
