import numpy as np
from scene_stages.gpu import select_masks


def box(top, left, bottom, right, size=32):
    mask = np.zeros((size, size), bool)
    mask[top:bottom, left:right] = True
    return mask


def test_a_mask_mostly_inside_a_higher_scoring_mask_with_its_label_is_dropped():
    chair, seat = box(4, 4, 28, 20), box(16, 4, 22, 20)
    kept = select_masks([(0.7, "office chair", seat), (0.9, "office chair", chair)], 0.8)
    assert [(score, label) for score, label, _ in kept] == [(0.9, "office chair")]


def test_a_contained_mask_with_another_label_is_kept():
    wardrobe, handle = box(2, 2, 30, 30), box(14, 24, 18, 26)
    kept = select_masks([(0.9, "wardrobe", wardrobe), (0.6, "door handle", handle)], 0.8)
    assert [label for _, label, _ in kept] == ["wardrobe", "door handle"]


def test_containment_counts_against_higher_scoring_masks_only():
    chair, seat = box(4, 4, 28, 20), box(16, 4, 22, 20)
    # The seat scores higher, so it is kept first; the chair is not mostly inside the seat.
    kept = select_masks([(0.95, "office chair", seat), (0.9, "office chair", chair)], 0.8)
    assert [score for score, _, _ in kept] == [0.95, 0.9]


def test_a_partly_overlapping_mask_with_the_same_label_is_kept():
    left, right = box(4, 2, 28, 18), box(4, 12, 28, 30)  # 6 of the left's 16 columns shared
    kept = select_masks([(0.9, "chair", left), (0.8, "chair", right)], 0.8)
    assert len(kept) == 2


def test_near_identical_masks_are_dropped_whatever_their_labels():
    first, second = box(4, 4, 28, 28), box(4, 4, 28, 27)
    kept = select_masks([(0.9, "cabinet", first), (0.8, "wardrobe", second)], 0.8)
    assert [label for _, label, _ in kept] == ["cabinet"]
