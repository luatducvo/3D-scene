"""Grounded question answering: the LLM plans and phrases, every number comes from a tool."""

import json
import math
import os
import re

import httpx
from scene_core.domain import OrientedBox
from scene_core.errors import SceneError
from scene_core.geometry import box_surface_distance, center_distance, relative_direction

MAX_STEPS = 6
SYSTEM_PROMPT = (
    "You answer questions about one scanned room. Always answer in English. Each question is independent. "
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
            "properties": {
                "answer": {"type": "string"},
                "object_ids": {"type": "array", "items": {"type": "string"}},
            },
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
        self.client = httpx.Client(
            base_url=base_url.rstrip("/") + "/",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=120,
        )

    @classmethod
    def from_env(cls):
        if not os.getenv("LLM_BASE_URL") or not os.getenv("LLM_MODEL"):
            return None
        return cls(
            os.environ["LLM_BASE_URL"], os.getenv("LLM_API_KEY", ""), os.environ["LLM_MODEL"]
        )

    def complete(self, messages, tools):
        """One reply in the agent's protocol: tool calls (final_answer among them), or plain content."""
        response = self.client.post(
            "chat/completions",
            json={"model": self.model, "messages": messages, "tools": tools, "temperature": 0},
        )
        response.raise_for_status()
        message = response.json()["choices"][0]["message"]
        calls = message.get("tool_calls") or []
        return {"tool_calls": calls} if calls else {"content": message.get("content") or ""}


def _tool(name, description, properties, required=()):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties, "required": list(required)},
        },
    }


class SceneTools:
    """The agent's tools for one Scene. Objects come from the published Scene Graph."""

    definitions = [
        _tool(
            "find_objects",
            "Find objects matching a free-text description in any language.",
            {"query": {"type": "string"}, "top_k": {"type": "integer"}},
            ["query"],
        ),
        _tool(
            "count_objects",
            "Count objects matching a name or description in any language.",
            {"label": {"type": "string"}},
            ["label"],
        ),
        _tool(
            "get_object",
            "Label, size in meters and attributes of one object.",
            {"object_id": {"type": "string"}},
            ["object_id"],
        ),
        _tool("get_room_info", "Floor area, ceiling height and object counts per label.", {}),
        _tool(
            "measure_distance",
            "Distance in meters between two objects.",
            {
                "a_id": {"type": "string"},
                "b_id": {"type": "string"},
                "mode": {"type": "string", "enum": ["surface", "center"]},
            },
            ["a_id", "b_id"],
        ),
        _tool(
            "get_relations",
            "Stored spatial relations of an object (on, under, above, inside, next_to, near, against_wall).",
            {"object_id": {"type": "string"}, "predicate": {"type": "string"}},
            ["object_id"],
        ),
        _tool(
            "relative_direction",
            "Whether object a is left, right, in front of or behind object b, "
            "seen from the user's camera or from the front of object b.",
            {
                "a_id": {"type": "string"},
                "b_id": {"type": "string"},
                "viewpoint": {"type": "string", "enum": ["camera", "object"]},
            },
            ["a_id", "b_id"],
        ),
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
        return {
            "id": obj["id"],
            "label": obj["label"],
            "label_vi": obj.get("label_vi"),
            "size_m": [round(v, 3) for v in obj["box"]["size"]],
            "center_m": [round(v, 3) for v in obj["box"]["center"]],
        }

    def _find_objects(self, query, top_k=5):
        hits = self.search(query)[: int(top_k)]
        self.mentioned.extend(hit["object"]["id"] for hit in hits)
        return {
            "objects": [
                {**self._summary(hit["object"]), "score": round(hit["score"], 3)} for hit in hits
            ]
        }

    def _count_objects(self, label):
        hits = self.search(label)
        self.mentioned.extend(hit["object"]["id"] for hit in hits)
        return {"count": len(hits), "object_ids": [hit["object"]["id"] for hit in hits]}

    def _get_object(self, object_id):
        obj = self._object(object_id)
        return {
            **self._summary(obj),
            "attributes": obj.get("attributes", {}),
        }

    def _get_room_info(self):
        counts = {}
        for obj in self.objects.values():
            counts[obj["label"]] = counts.get(obj["label"], 0) + 1
        return {
            "floor_area_m2": self.room.get("floor_area"),
            "ceiling_height_m": self.room.get("ceiling_height"),
            "object_counts": counts,
        }

    def _measure_distance(self, a_id, b_id, mode="surface"):
        a, b = (OrientedBox.model_validate(self._object(i)["box"]) for i in (a_id, b_id))
        distance = center_distance(a, b) if mode == "center" else box_surface_distance(a, b)
        return {"distance_m": round(distance, 3), "mode": mode}

    def _get_relations(self, object_id, predicate=None):
        self._object(object_id)
        found = [
            r
            for r in self.relations
            if object_id in (r["subject_id"], r["object_id"])
            and (predicate is None or r["predicate"] == predicate)
        ]
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


NUMBER = re.compile(r"(?<![\w.,-])-?\d+(?:[.,]\d+)?")
# An answer may give meters in centimeters or millimeters.
UNIT_FACTORS = (1, 100, 1000)
UNGROUNDED_FEEDBACK = (
    "Your answer states numbers no tool returned: {numbers}. Use only numbers from tool "
    "results, calling a tool to measure if needed, then call final_answer again."
)


def numbers_in(value):
    """Every number in a tool result, however deeply nested; ids such as chair-1 are not numbers."""
    if isinstance(value, bool):
        return []
    if isinstance(value, (int, float)):
        return [float(value)]
    if isinstance(value, dict):
        return [n for v in value.values() for n in numbers_in(v)]
    if isinstance(value, (list, tuple)):
        return [n for v in value for n in numbers_in(v)]
    if isinstance(value, str):
        return [float(m.replace(",", ".")) for m in NUMBER.findall(value)]
    return []


def ungrounded(answer, facts):
    """The numbers in answer that match no fact at the precision the answer states them."""
    unsupported = []
    for text in NUMBER.findall(answer):
        value = float(text.replace(",", "."))
        decimals = len(text.replace(",", ".").partition(".")[2])
        # A fact rounded to the answer's precision, half up: 0.25 may be said as 0.3 but not as 0.4.
        tolerance = 0.5 * 10**-decimals + 1e-9
        if not any(
            abs(fact * factor - value) <= tolerance for fact in facts for factor in UNIT_FACTORS
        ):
            unsupported.append(text)
    return unsupported


class QAAgent:
    """Runs the tools the LLM asks for and accepts only answers whose numbers those tools returned."""

    def __init__(self, llm, max_steps=MAX_STEPS):
        # SOLID (DIP): real and scripted LLMs share complete(); the agent owns no HTTP transport.
        self.llm, self.max_steps = llm, max_steps

    def answer(self, question, tools):
        """Yield QueryEvent dicts: tool events, one delta, then the final answer."""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ]
        # Numbers the user wrote may be repeated; every other number must come from a tool result.
        facts = numbers_in(question)
        rejected = False
        for _ in range(self.max_steps):
            reply = self.llm.complete(messages, [*tools.definitions, FINAL_ANSWER])
            calls = reply.get("tool_calls") or []
            final = None
            if not calls:
                final = {
                    "answer": reply.get("content") or "",
                    "object_ids": reply.get("object_ids") or [],
                }
                messages.append({"role": "assistant", "content": final["answer"]})
            else:
                messages.append({"role": "assistant", "content": None, "tool_calls": calls})
            # Other tools in the same reply run first, so a final answer can use what they return.
            for call in sorted(calls, key=lambda c: c["function"]["name"] == "final_answer"):
                name = call["function"]["name"]
                try:
                    arguments = json.loads(call["function"].get("arguments") or "{}")
                except json.JSONDecodeError as exc:
                    arguments, result = None, {"error": f"Invalid tool arguments: {exc}"}
                if name == "final_answer" and arguments is not None:
                    final = {
                        "answer": arguments.get("answer", ""),
                        "object_ids": arguments.get("object_ids", []),
                        "call": call,
                    }
                    continue
                yield {"type": "tool", "tool": name}
                if arguments is not None:
                    result = tools.execute(name, arguments)
                    facts.extend(numbers_in(result))
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.get("id", name),
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                )
            if final is None:
                continue
            unsupported = ungrounded(final["answer"], facts)
            if unsupported:
                if rejected:
                    raise SceneError(
                        "QA_UNGROUNDED",
                        f"The answer states numbers no tool measured: {', '.join(unsupported)}",
                        502,
                    )
                rejected = True
                feedback = UNGROUNDED_FEEDBACK.format(numbers=", ".join(unsupported))
                if "call" in final:
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": final["call"].get("id", "final_answer"),
                            "content": feedback,
                        }
                    )
                else:
                    messages.append({"role": "user", "content": feedback})
                continue
            if "call" in final:
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": final["call"].get("id", "final_answer"),
                        "content": "accepted",
                    }
                )
            object_ids = [i for i in final["object_ids"] if i in tools.objects] or list(
                dict.fromkeys(tools.mentioned)
            )
            yield {"type": "delta", "delta": final["answer"]}
            yield {"type": "final", "answer": final["answer"], "object_ids": object_ids}
            return
        raise SceneError("QA_STEP_LIMIT", f"No answer within {self.max_steps} steps", 502)
