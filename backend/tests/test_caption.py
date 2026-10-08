import json

from PIL import Image

from s3d_app.pipeline import artifact_dir
from s3d_app.storage import database
from s3d_app.vision import caption


def test_caption_is_cached_in_sqlite_across_queries(monkeypatch, tmp_path):
    monkeypatch.setenv("S3D_DATA_DIR", str(tmp_path))
    directory = artifact_dir("scene", "S4") / "crops/1"
    directory.mkdir(parents=True)
    Image.new("RGB", (20, 20), "brown").save(directory / "000010.jpg")
    item = {"id": 1, "keyframes": [10]}
    with database() as connection:
        connection.execute("INSERT INTO objects(scene_id,id,data) VALUES ('scene',1,?)", (json.dumps(item),))
    calls = []
    monkeypatch.setattr("s3d_app.vision.chat_with_images", lambda *_: calls.append(1) or "A wooden chair.")
    assert caption("scene", item, None) == "A wooden chair."
    with database() as connection:
        saved = json.loads(connection.execute("SELECT data FROM objects WHERE id=1").fetchone()[0])
    assert caption("scene", saved, None) == "A wooden chair."
    assert len(calls) == 1
