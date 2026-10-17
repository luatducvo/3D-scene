import json
from pathlib import Path

from .main import app
from .models import ProgressEvent, QueryEvent


def export(path=None):
    schema = app.openapi()
    for model in (ProgressEvent, QueryEvent):
        definition = model.model_json_schema(ref_template="#/components/schemas/{model}")
        definitions = definition.pop("$defs", {})
        schema["components"]["schemas"].update(definitions)
        schema["components"]["schemas"][model.__name__] = definition
    target = Path(path) if path else Path(__file__).resolve().parents[4] / "openapi/openapi.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
    return target


if __name__ == "__main__":
    print(export())
