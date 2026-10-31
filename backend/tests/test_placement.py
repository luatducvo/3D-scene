import numpy as np
import pytest
from scene_core.domain import SceneObject
from scene_core.errors import SceneError
from scene_stages.placement import placement_facts

# A 4 m x 3 m room: the mesh's vertices seen from above.
ROOM = np.array([[x, y, z] for x in (0, 2, 4) for y in (0, 1.5, 3) for z in (0, 2.5)])


def box(name, center, size, yaw=0.0, label=None):
    return SceneObject(
        id=name, label=label or name, box={"center": center, "size": size, "yaw": yaw}
    )


def test_an_object_rests_on_what_is_under_it_on_the_floor_or_on_nothing():
    facts = placement_facts(
        [
            box("desk", (2, 1.5, 0.4), (1.2, 0.6, 0.8)),
            box("mug", (2, 1.5, 0.85), (0.1, 0.1, 0.1)),
            box("chair", (1, 1.5, 0.5), (0.5, 0.5, 1)),
            box("picture", (2, 2.95, 1.5), (0.6, 0.05, 0.4)),
        ],
        ROOM,
    )
    assert (facts["mug"].support, facts["mug"].support_id) == ("object", "desk")
    assert (facts["desk"].support, facts["desk"].support_id) == ("floor", None)
    assert facts["chair"].support == "floor"
    assert (facts["picture"].support, facts["picture"].support_id) == ("mounted", None)
    assert facts["mug"].height_above_floor_m == pytest.approx(0.8)
    assert facts["mug"].size_m == pytest.approx((0.1, 0.1, 0.1))


def test_an_object_mostly_off_the_box_under_it_does_not_rest_on_it():
    # 49% of the book's footprint lies over the shelf.
    facts = placement_facts(
        [
            box("shelf", (2, 1.5, 0.5), (1, 1, 1)),
            box("book", (2.501, 1.5, 1.02), (0.1, 0.1, 0.04)),
        ],
        ROOM,
    )
    assert facts["book"].support == "mounted"


def test_an_object_over_several_boxes_rests_on_the_one_it_overlaps_most():
    facts = placement_facts(
        [
            box("big-table", (2, 1.5, 0.4), (2, 1, 0.8)),
            box("small-table", (2.4, 1.5, 0.4), (0.4, 0.4, 0.8)),
            box("lamp", (2.3, 1.5, 0.9), (0.4, 0.2, 0.2)),
        ],
        ROOM,
    )
    assert facts["lamp"].support_id == "big-table"


def test_neighbours_are_the_two_closest_objects():
    facts = placement_facts(
        [
            box("bed", (1, 1.5, 0.3), (1, 2, 0.6)),
            box("nightstand", (1.8, 1.5, 0.3), (0.4, 0.4, 0.6)),
            box("lamp", (2.6, 1.5, 0.3), (0.2, 0.2, 0.6)),
            box("wardrobe", (3.5, 2.5, 1), (0.6, 0.6, 2)),
        ],
        ROOM,
    )
    assert [n.id for n in facts["nightstand"].neighbours] == ["bed", "lamp"]
    assert facts["nightstand"].neighbours[0].distance_m == pytest.approx(0.1)
    assert [n.id for n in facts["wardrobe"].neighbours] == ["lamp", "nightstand"]


def test_room_position_is_corner_wall_or_open():
    facts = placement_facts(
        [
            box("plant", (0.2, 0.2, 0.5), (0.3, 0.3, 1)),
            box("sofa", (2, 2.6, 0.4), (2, 0.6, 0.8)),
            box("rug", (2, 1.5, 0.01), (1, 1, 0.02)),
        ],
        ROOM,
    )
    assert facts["plant"].room_position == "corner"
    assert facts["sofa"].room_position == "wall"
    assert facts["rug"].room_position == "open"


def test_a_rotated_box_near_a_wall_is_by_the_wall():
    facts = placement_facts([box("desk", (2, 2.4, 0.4), (1, 0.6, 0.8), yaw=np.pi / 2)], ROOM)
    # Turned a quarter, the desk reaches 0.5 m towards the far wall: 0.1 m from it.
    assert facts["desk"].room_position == "wall"


@pytest.mark.parametrize(
    "name", ["support_gap_m", "support_overlap", "wall_distance_m", "num_neighbours"]
)
def test_a_non_positive_threshold_is_invalid_parameters(name):
    with pytest.raises(SceneError) as error:
        placement_facts([box("chair", (1, 1, 0.5), (0.5, 0.5, 1))], ROOM, {name: 0})
    assert error.value.code == "INVALID_PARAMETERS"
