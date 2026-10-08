"""Export or check the committed OpenAPI contract."""

import argparse
import json
from pathlib import Path

from s3d_app.api import app


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    destination = Path(__file__).resolve().parents[2] / "openapi.json"
    content = json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"
    if args.check:
        if not destination.exists() or destination.read_text() != content:
            parser.exit(1, "OpenAPI contract is stale; regenerate backend/openapi.json\n")
    else:
        destination.write_text(content)


if __name__ == "__main__":
    main()
