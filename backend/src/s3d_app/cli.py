"""Command line entry point."""

import argparse

import uvicorn

from s3d_app.models import pull_models


def main() -> None:
    parser = argparse.ArgumentParser(prog="s3d")
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve", help="Serve the local application")
    serve.add_argument("--port", type=int, default=8000)
    models = commands.add_parser("models", help="Manage pinned model files")
    models.add_argument("action", choices=["pull"])
    args = parser.parse_args()
    if args.command == "serve":
        uvicorn.run("s3d_app.api:app", host="127.0.0.1", port=args.port)
    elif args.command == "models" and args.action == "pull":
        try:
            downloaded = pull_models()
        except (OSError, ValueError) as exc:
            parser.exit(1, f"models pull: {exc}\n")
        print(f"Verified models; downloaded {len(downloaded)} file(s).")
