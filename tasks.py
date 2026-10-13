"""Cross-platform project tasks (stdlib only). Run `uv run tasks.py --help` from the repository root."""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
ENV_FILE = BACKEND / ".env"
TEST_DB = "scene-test-db"
TEST_DB_PORT = "15432"
TEST_DATABASE_URL = f"postgresql://scene:scene@127.0.0.1:{TEST_DB_PORT}/scene"


def run(*command, env=None, check=True):
    print("+", " ".join(command), flush=True)
    return subprocess.run(command, cwd=ROOT, env={**os.environ, **(env or {})}, check=check)


def env_values():
    if not ENV_FILE.exists():
        shutil.copyfile(BACKEND / ".env.example", ENV_FILE)
        print(f"Created {ENV_FILE.relative_to(ROOT)} from .env.example; fill in the keys you need.")
    values = {}
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.split(" #", 1)[0].strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def compose(*arguments):
    env_values()
    compose_file = ROOT / "compose.yaml" if (ROOT / "compose.yaml").exists() else BACKEND / "compose.yaml"
    return run("docker", "compose", "-f", str(compose_file), "--env-file", str(ENV_FILE), *arguments)


def models_dir():
    return (BACKEND / env_values().get("HOST_MODELS_DIR", "./models")).resolve()


def init_storage(_):
    models_dir().mkdir(parents=True, exist_ok=True)
    print(f"Model cache: {models_dir()}")


def up(args):
    init_storage(args)
    compose("up", "-d", "--build")


def up_local_gpu(args):
    init_storage(args)
    compose("--profile", "local-gpu", "up", "-d", "--build")


def down(_):
    compose("--profile", "local-gpu", "down")


def reset(_):
    """Delete every Scene and the database; keep the host model cache."""
    compose("--profile", "local-gpu", "down", "-v")


def ensure_test_database():
    state = subprocess.run(["docker", "inspect", "-f", "{{.State.Running}}", TEST_DB], capture_output=True, text=True)
    if state.returncode != 0:
        run("docker", "run", "-d", "--name", TEST_DB, "-p", f"127.0.0.1:{TEST_DB_PORT}:5432",
            "-e", "POSTGRES_USER=scene", "-e", "POSTGRES_PASSWORD=scene", "-e", "POSTGRES_DB=scene", "pgvector/pgvector:pg16")
    elif state.stdout.strip() != "true":
        run("docker", "start", TEST_DB)
    for _ in range(60):
        ready = subprocess.run(["docker", "exec", TEST_DB, "pg_isready", "-U", "scene", "-h", "127.0.0.1"], capture_output=True)
        if ready.returncode == 0:
            return
        time.sleep(1)
    sys.exit("Test database did not become ready")


def test(args):
    ensure_test_database()
    # Pytest's temporary Workspaces live outside the repository.
    basetemp = Path(tempfile.gettempdir()) / "scene-pytest"
    run(sys.executable, "-m", "pytest", "-p", "no:cacheprovider", f"--basetemp={basetemp}", *args.pytest_args,
        env={"TEST_DATABASE_URL": TEST_DATABASE_URL})


def openapi(_):
    run(sys.executable, "-m", "scene_api.export_openapi", env={"DATABASE_URL": "postgresql://unused@localhost/unused"})


def download_models(_):
    init_storage(_)
    compose("--profile", "local-gpu", "run", "--rm", "scene-compute", "python", "-m", "scene_compute.download_models")


def disk_usage(_):
    run("docker", "system", "df", "-v", check=False)
    folder = models_dir()
    size = sum(p.stat().st_size for p in folder.rglob("*") if p.is_file()) if folder.exists() else 0
    print(f"Model cache {folder}: {size / 2**30:.2f} GiB")


def image_name(args):
    """`--image` wins; otherwise COMPUTE_IMAGE_REPO:<variant>-<git short sha>, so live checks name an exact build."""
    if args.image:
        return args.image
    repository = env_values().get("COMPUTE_IMAGE_REPO")
    if not repository or "<" in repository:
        sys.exit("Pass --image or set COMPUTE_IMAGE_REPO in backend/.env")
    revision = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    return f"{repository}:{args.extras or 'fake'}-{revision}"


def compute_image(args):
    run("docker", "build", "--platform", "linux/amd64", "-f", str(BACKEND / "docker/compute.Dockerfile"),
        "--build-arg", f"EXTRAS={args.extras}", "-t", image_name(args), str(ROOT))


def push_compute_image(args):
    compute_image(args)
    image = image_name(args)
    run("docker", "push", image)
    digests = subprocess.run(["docker", "image", "inspect", "--format", "{{range .RepoDigests}}{{println .}}{{end}}", image],
                             capture_output=True, text=True, check=True).stdout.split()
    digest = next((d for d in digests if d.startswith(image.rsplit(":", 1)[0] + "@")), "unknown")
    print(f"Pushed {image}\nDigest {digest}")


def deploy_modal(args):
    extras = "" if args.variant == "fake" else args.variant
    name = "scene-compute" if args.variant == "fake" else f"scene-compute-{args.variant}"
    run("uvx", "modal", "deploy", str(BACKEND / "deploy/modal/app.py"),
        env={"COMPUTE_EXTRAS": extras, "MODAL_APP_NAME": name})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name, handler, help_text in [
        ("init-storage", init_storage, "create the host model cache folder"),
        ("up", up, "start Postgres, scene-api, scene-worker and frontend"),
        ("up-local-gpu", up_local_gpu, "also start scene-compute on the local GPU"),
        ("down", down, "stop the backend, keeping all data"),
        ("reset", reset, "delete all Scenes and the database, keep model weights"),
        ("openapi", openapi, "export the API contract to backend/openapi/openapi.json"),
        ("download-models", download_models, "fetch model weights into the host cache"),
        ("disk-usage", disk_usage, "show Docker volume and model cache sizes"),
    ]:
        commands.add_parser(name, help=help_text).set_defaults(handler=handler)
    tester = commands.add_parser("test", help="run pytest against a disposable test database; extra arguments go to pytest")
    tester.set_defaults(handler=test)
    for name, handler, help_text in [("compute-image", compute_image, "build the GPU image"),
                                     ("push-compute-image", push_compute_image, "build and push the GPU image")]:
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--image")
        command.add_argument("--extras", default="", choices=["", "recon", "perception"])
        command.set_defaults(handler=handler)
    modal = commands.add_parser("deploy-modal", help="deploy scene-compute to Modal (built remotely)")
    modal.add_argument("--variant", default="fake", choices=["fake", "recon", "perception"])
    modal.set_defaults(handler=deploy_modal)
    args, extra = parser.parse_known_args()
    if extra and args.command != "test":
        parser.error(f"unrecognized arguments: {' '.join(extra)}")
    args.pytest_args = extra
    args.handler(args)


if __name__ == "__main__":
    main()
