"""Grounded question answering: the LLM plans and phrases, every number comes from a tool."""
import json
import math
import os

import httpx

from scene_core.domain import OrientedBox
from scene_core.errors import SceneError
from scene_core.geometry import box_surface_distance, center_distance, relative_direction

MAX_STEPS = 6
SYSTEM_PROMPT = (
    "You answer questions about one scanned room. Answer in the language of the question. "
    "Use only facts returned by tools; never estimate a number yourself. Distances are meters. "
    "When done, call final_answer with the answer text and the ids of the objects it refers to."
)
FINAL_ANSWER = {
    "type": "function",
    "function": {
        "name": "final_answer",
        "description": "Return the final answer and the ids of the objects it refers to.",
        "parameters": {
            "type": "object",
            "properties": {"answer": {"type": "string"}, "object_ids": {"type": "array", "items": {"type": "string"}}},
            "required": ["answer", "object_ids"],
        },
    },
}


class ScriptedLLM:
    """Replays prepared responses; selected by configuration in tests."""

    def __init__(self, responses):
        self.responses = list(responses)

    def complete(self, messages, tools):
        if not self.responses:
            raise RuntimeError("ScriptedLLM has no responses left")
        return self.responses.pop(0)


class OpenAICompatibleLLM:
    """Any OpenAI-compatible chat completions endpoint, cloud or local."""

    def __init__(self, base_url, api_key, model):
        self.model = model
        self.client = httpx.Client(base_url=base_url.rstrip("/") + "/", headers={"Authorization": f"Bearer {api_key}"}, timeout=120)

    @classmethod
    def from_env(cls):
        if not os.getenv("LLM_BASE_URL") or not os.getenv("LLM_MODEL"):
            return None
        return cls(os.environ["LLM_BASE_URL"], os.getenv("LLM_API_KEY", ""), os.environ["LLM_MODEL"])

    def complete(self, messages, tools):
        response = self.client.post("chat/completions", json={"model": self.model, "messages": messages, "tools": [*tools, FINAL_ANSWER], "temperature": 0})
        response.raise_for_status()
        message = response.json()["choices"][0]["message"]
        calls = message.get("tool_calls") or []
        for call in calls:
            if call["function"]["name"] == "final_answer":
                arguments = json.loads(call["function"]["arguments"] or "{}")
                return {"content": arguments.get("answer", ""), "object_ids": arguments.get("object_ids", [])}
        if calls:
            return {"tool_calls": calls}
        return {"content": message.get("content") or "", "object_ids": []}


def _tool(name, description, properties, required=()):
    return {"type": "function", "function": {"name": name, "description": description,
            "parameters": {"type": "object", "properties": properties, "required": list(required)}}}


class SceneTools:
    """The agent's tools for one Scene. Objects come from the published Scene Graph."""

    definitions = [
        _tool("find_objects", "Find objects matching a free-text description in any language.",
              {"query": {"type": "string"}, "top_k": {"type": "integer"}}, ["query"]),
        _tool("count_objects", "Count objects matching a name or description in any language.",
              {"label": {"type": "string"}}, ["label"]),
        _tool("get_object", "Label, size in meters, attributes and evidence images of one object.",
              {"object_id": {"type": "string"}}, ["object_id"]),
        _tool("get_room_info", "Floor area, ceiling height and object counts per label.", {}),
        _tool("measure_distance", "Distance in meters between two objects.",
              {"a_id": {"type": "string"}, "b_id": {"type": "string"},
               "mode": {"type": "string", "enum": ["surface", "center"]}}, ["a_id", "b_id"]),
        _tool("get_relations", "Stored spatial relations of an object (on, under, above, inside, next_to, near, against_wall).",
              {"object_id": {"type": "string"}, "predicate": {"type": "string"}}, ["object_id"]),
        _tool("relative_direction", "Whether object a is left, right, in front of or behind object b, "
              "seen from the user's camera or from the front of object b.",
              {"a_id": {"type": "string"}, "b_id": {"type": "string"},
               "viewpoint": {"type": "string", "enum": ["camera", "object"]}}, ["a_id", "b_id"]),
    ]

    def __init__(self, objects, relations, room, search, camera=None):
        self.objects = {obj["id"]: obj for obj in objects}
        self.relations, self.room, self.search, self.camera = relations, room or {}, search, camera
        self.mentioned = []

    def execute(self, name, arguments):
        handler = getattr(self, "_" + name, None)
        if handler is None or name not in {d["function"]["name"] for d in self.definitions}:
            return {"error": f"Unknown tool {name}"}
        try:
            return handler(**arguments)
        except (KeyError, TypeError, ValueError) as exc:
            return {"error": str(exc)}

    def _object(self, object_id):
        if object_id not in self.objects:
            raise KeyError(f"Unknown object id {object_id}")
        self.mentioned.append(object_id)
        return self.objects[object_id]

    def _summary(self, obj):
        return {"id": obj["id"], "label": obj["label"], "label_vi": obj.get("label_vi"),
                "size_m": [round(v, 3) for v in obj["box"]["size"]], "center_m": [round(v, 3) for v in obj["box"]["center"]]}

    def _find_objects(self, query, top_k=5):
        hits = self.search(query)[:int(top_k)]
        self.mentioned.extend(hit["object"]["id"] for hit in hits)
        return {"objects": [{**self._summary(hit["object"]), "score": round(hit["score"], 3)} for hit in hits]}

    def _count_objects(self, label):
        hits = self.search(label)
        self.mentioned.extend(hit["object"]["id"] for hit in hits)
        return {"count": len(hits), "object_ids": [hit["object"]["id"] for hit in hits]}

    def _get_object(self, object_id):
        obj = self._object(object_id)
        return {**self._summary(obj), "attributes": obj.get("attributes", {}),
                "evidence": [view.get("image_url") for view in obj.get("best_views", [])]}

    def _get_room_info(self):
        counts = {}
        for obj in self.objects.values():
            counts[obj["label"]] = counts.get(obj["label"], 0) + 1
        return {"floor_area_m2": self.room.get("floor_area"), "ceiling_height_m": self.room.get("ceiling_height"),
                "object_counts": counts}

    def _measure_distance(self, a_id, b_id, mode="surface"):
        a, b = (OrientedBox.model_validate(self._object(i)["box"]) for i in (a_id, b_id))
        distance = center_distance(a, b) if mode == "center" else box_surface_distance(a, b)
        return {"distance_m": round(distance, 3), "mode": mode}

    def _get_relations(self, object_id, predicate=None):
        self._object(object_id)
        found = [r for r in self.relations if object_id in (r["subject_id"], r["object_id"])
                 and (predicate is None or r["predicate"] == predicate)]
        self.mentioned.extend(i for r in found for i in (r["subject_id"], r["object_id"]) if i)
        return {"relations": found}

    def _relative_direction(self, a_id, b_id, viewpoint="camera"):
        a, b = (OrientedBox.model_validate(self._object(i)["box"]) for i in (a_id, b_id))
        if viewpoint == "object":
            # An Object's front is its local +x axis after gravity alignment.
            front = (b.center[0] + math.cos(b.yaw), b.center[1] + math.sin(b.yaw), b.center[2])
            position, target = b.center, front
        else:
            if not self.camera:
                raise ValueError("No camera was sent with the question; use viewpoint 'object'")
            position, target = self.camera["position"], self.camera["target"]
        direction = relative_direction(a, b, position, target)
        if viewpoint == "object":
            # The camera convention calls "farther along the view" behind; from b's own front it is in front.
            direction = {"behind": "in_front", "in_front": "behind"}.get(direction, direction)
        return {"direction": direction, "viewpoint": viewpoint}


class QAAgent:
    def __init__(self, llm, max_steps=MAX_STEPS):
        self.llm, self.max_steps = llm, max_steps

    def answer(self, question, tools, history=()):
        """Yield QueryEvent dicts: tool events, one delta, then the final answer."""
        messages = [{"role": "system", "content": SYSTEM_PROMPT}, *history, {"role": "user", "content": question}]
        for _ in range(self.max_steps):
            reply = self.llm.complete(messages, tools.definitions)
            calls = reply.get("tool_calls") or []
            if not calls:
                answer = reply.get("content") or ""
                object_ids = [i for i in reply.get("object_ids") or [] if i in tools.objects]
                if not object_ids:
                    object_ids = list(dict.fromkeys(tools.mentioned))
                yield {"type": "delta", "delta": answer}
                yield {"type": "final", "answer": answer, "object_ids": object_ids}
                return
            messages.append({"role": "assistant", "content": None, "tool_calls": calls})
            for call in calls:
                name = call["function"]["name"]
                yield {"type": "tool", "tool": name}
                try:
                    arguments = json.loads(call["function"].get("arguments") or "{}")
                except json.JSONDecodeError as exc:
                    result = {"error": f"Invalid tool arguments: {exc}"}
                else:
                    result = tools.execute(name, arguments)
                messages.append({"role": "tool", "tool_call_id": call.get("id", name), "content": json.dumps(result, ensure_ascii=False)})
        raise SceneError("QA_STEP_LIMIT", f"No answer within {self.max_steps} steps", 502)
