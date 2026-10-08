import numpy as np

from s3d_app.semantics import project, rofa_average, vote_labels


def test_secondary_label_votes_have_less_weight():
    distribution = vote_labels([("chair", 0.8, 1.0, "text-prompt"),
                                 ("stool", 1.0, 1.0, "prompt-free")])
    assert next(iter(distribution)) == "chair"
    assert abs(sum(distribution.values()) - 1) < 1e-4


def test_rofa_removes_a_directional_outlier_and_normalizes():
    features = np.tile([1.0, 0.0], (20, 1))
    features[-1] = [-1.0, 0.0]
    vector = rofa_average(features)
    np.testing.assert_allclose(vector, [1, 0], atol=1e-5)
    assert np.linalg.norm(vector) == 1


def test_projection_rejects_points_behind_camera():
    points = np.asarray([[0, 0, 1], [0, 0, -1], [20, 0, 1]], dtype=np.float32)
    intrinsic = np.asarray([[100, 0, 50], [0, 100, 50], [0, 0, 1]])
    u, v, valid = project(points, np.eye(4), intrinsic, 100, 100)
    assert (u[0], v[0]) == (50, 50)
    assert valid.tolist() == [True, False, False]
