import json

import pytest
from scene_core.errors import SceneError
from scene_stages.mg3d_doc import DescriptionRequest, describe, placement_text
from scene_stages.placement import Neighbour, Placement

VALID = json.dumps(
    {
        "appearance": "A brown wooden chair.",
        "use": "It is used for sitting.",
        "placement": "It stands on the floor by the wall, about 1 m tall.",
    }
)


def requests(*ids):
    return [
        DescriptionRequest(id=i, label="chair", facts="Rests on: the floor.", images=[])
        for i in ids
    ]


class ScriptedVLM:
    """Answers each Object's prompts in turn from a script, and records every batch it was given."""

    def __init__(self, answers):
        self.answers = {key: list(value) for key, value in answers.items()}
        self.batches = []

    def __call__(self, batch):
        self.batches.append([request.id for request in batch])
        return [self.answers[request.id].pop(0) for request in batch]


def test_every_object_gets_its_three_sentences_from_one_batched_call():
    vlm = ScriptedVLM({"chair-1": [VALID], "chair-2": [VALID]})
    descriptions = describe(requests("chair-1", "chair-2"), vlm)
    assert vlm.batches == [["chair-1", "chair-2"]]
    assert descriptions["chair-1"].text() == (
        "A brown wooden chair. It is used for sitting."
        " It stands on the floor by the wall, about 1 m tall."
    )
    assert set(descriptions) == {"chair-1", "chair-2"}


def test_a_json_answer_inside_a_code_fence_is_read():
    vlm = ScriptedVLM({"chair-1": [f"```json\n{VALID}\n```"]})
    assert describe(requests("chair-1"), vlm)["chair-1"].use == "It is used for sitting."


@pytest.mark.parametrize(
    "malformed",
    [
        "A brown chair you sit on.",
        json.dumps({"appearance": "A chair.", "use": "Sitting."}),
        json.dumps({"appearance": "A chair.", "use": "", "placement": "On the floor."}),
        json.dumps(
            {"appearance": "A chair. It is brown.", "use": "Sitting.", "placement": "Floor."}
        ),
        json.dumps(["A chair.", "Sitting.", "Floor."]),
    ],
)
def test_a_malformed_answer_is_asked_again_for_that_object_only(malformed):
    vlm = ScriptedVLM({"chair-1": [malformed, VALID], "chair-2": [VALID]})
    descriptions = describe(requests("chair-1", "chair-2"), vlm)
    assert vlm.batches == [["chair-1", "chair-2"], ["chair-1"]]
    assert set(descriptions) == {"chair-1", "chair-2"}


def test_a_third_malformed_answer_is_invalid_model_output_naming_the_object():
    vlm = ScriptedVLM({"chair-1": ["no", "still no", "never"], "chair-2": [VALID]})
    with pytest.raises(SceneError, match="chair-1") as error:
        describe(requests("chair-1", "chair-2"), vlm)
    assert error.value.code == "INVALID_MODEL_OUTPUT"
    assert len(vlm.batches) == 3


def test_a_vlm_returning_the_wrong_number_of_answers_is_invalid_model_output():
    with pytest.raises(SceneError) as error:
        describe(requests("chair-1", "chair-2"), lambda batch: [VALID])
    assert error.value.code == "INVALID_MODEL_OUTPUT"


def test_placement_facts_are_told_with_the_labels_of_the_objects_they_name():
    labels = {"mug": "mug", "desk": "desk", "lamp": "lamp"}
    text = placement_text(
        Placement(
            size_m=(0.1, 0.1, 0.1),
            height_above_floor_m=0.8,
            support="object",
            support_id="desk",
            neighbours=[Neighbour(id="desk", distance_m=0), Neighbour(id="lamp", distance_m=0.3)],
            room_position="wall",
        ),
        labels,
    )
    assert "rests on the desk" in text
    assert "0.80 m above the floor" in text
    assert "the desk (0.00 m), the lamp (0.30 m)" in text
    assert "by a wall" in text
