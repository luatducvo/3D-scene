import numpy as np
import pytest

from s3d_app.instances import InstanceProposal, dominant_component, select_proposals


def test_select_proposals_with_fake_model():
    first = np.zeros(250, dtype=bool)
    first[:120] = True
    duplicate = first.copy()
    second = np.zeros(250, dtype=bool)
    second[110:230] = True
    tiny = np.zeros(250, dtype=bool)
    tiny[230:] = True
    ids, rows = select_proposals([
        InstanceProposal(duplicate, 9, 0.7, "fake"),
        InstanceProposal(second, 4, 0.8, "fake"),
        InstanceProposal(first, 9, 0.9, "fake"),
        InstanceProposal(tiny, 3, 1.0, "fake"),
    ], 250)
    assert [row["label_id"] for row in rows] == [9, 4]
    assert np.all(ids[:120] == 0)
    assert np.all(ids[120:230] == 1)
    assert np.all(ids[230:] == -1)


def test_bad_mask_rejected():
    with pytest.raises(ValueError):
        select_proposals([InstanceProposal(np.ones(3, dtype=np.int32), 1, 1.0, "fake")], 3)


def test_disconnected_noise_cannot_expand_object_bbox():
    points = np.asarray([[0, 0, 0], [0.05, 0, 0], [0.1, 0, 0], [10, 10, 10]], dtype=np.float32)
    clean = dominant_component(points, np.ones(4, dtype=bool))
    assert clean.tolist() == [True, True, True, False]
