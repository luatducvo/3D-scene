"""Cross-platform project commands (stdlib only), not an app entrypoint. Run `uv run main.py --help` from the repository root."""

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
# Profiles of compose.yaml; `up` starts PARTS unless told which.
PARTS = ("backend", "frontend")
PROFILES = (*PARTS, "local-gpu")

COMMANDS = {}


def command(help_text, *arguments, name=None, passthrough=False):
    """Registers a command under its function's name; `arguments` are (flags, options) for argparse."""

    def register(handler):
        COMMANDS[name or handler.__name__.replace("_", "-")] = (
            handler,
            help_text + ("; extra arguments go to the tool" if passthrough else ""),
            arguments,
            passthrough,
        )
        return handler

    return register


IMAGE_ARGUMENTS = ((["--image"], {}), (["--extras"], {"default": "", "choices": ["", "gpu"]}))


# Processes


def run(*argv, env=None, check=True):
    print("+", " ".join(argv), flush=True)
    return subprocess.run(argv, cwd=ROOT, env={**os.environ, **(env or {})}, check=check)


def output(*argv):
    return subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, check=True).stdout


def python(*arguments, env=None, check=True):
    return run(sys.executable, "-m", *arguments, env=env, check=check)


def env_values():
    """backend/.env as a dict, created from .env.example on first use."""
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


def compose(*arguments, profiles=PROFILES):
    env_values()
    flags = [flag for profile in profiles for flag in ("--profile", profile)]
    files = ["-f", str(ROOT / "compose.yaml"), "--env-file", str(ENV_FILE)]
    return run("docker", "compose", *files, *flags, *arguments)


def require_docker():
    try:
        running = subprocess.run(["docker", "info"], capture_output=True).returncode == 0
    except FileNotFoundError:
        running = False
    if not running:
        sys.exit(
            "Docker is not running. Start Docker Desktop (or the Docker daemon) and try again; "
            "`uv run main.py test-unit` runs the tests that need no database."
        )


def models_dir():
    return (BACKEND / env_values().get("HOST_MODELS_DIR", "./models")).resolve()


# Stack


@command("create the host model cache folder")
def init_storage(_=None):
    folder = models_dir()
    folder.mkdir(parents=True, exist_ok=True)
    print(f"Model cache: {folder}")


@command(
    "start the backend (Postgres, scene-api, scene-worker) and the frontend",
    (["parts"], {"nargs": "*", "choices": PARTS, "help": "start only these profiles"}),
)
def up(args):
    init_storage()
    compose("up", "-d", "--build", profiles=args.parts or PARTS)


@command("also start scene-compute on the local GPU")
def up_local_gpu(_):
    init_storage()
    compose("up", "-d", "--build")


@command("stop every service, keeping all data")
def down(_):
    compose("down")


@command("delete all Scenes and the database, keep model weights")
def reset(_):
    compose("down", "-v")


@command("fetch model weights into the host cache")
def download_models(_):
    init_storage()
    module = ["python", "-m", "scene_compute.download_models"]
    compose("run", "--rm", "scene-compute", *module, profiles=["local-gpu"])


@command("show Docker volume and model cache sizes")
def disk_usage(_):
    run("docker", "system", "df", "-v", check=False)
    folder = models_dir()
    size = sum(p.stat().st_size for p in folder.rglob("*") if p.is_file()) if folder.exists() else 0
    print(f"Model cache {folder}: {size / 2**30:.2f} GiB")


# Checks


def ensure_test_database():
    """A fresh test database each run, so it always has the current backend/migrations/001_init.sql."""
    require_docker()
    subprocess.run(["docker", "rm", "-f", TEST_DB], capture_output=True)
    keys = ("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB")
    credentials = [flag for key in keys for flag in ("-e", f"{key}=scene")]
    schema = f"{BACKEND / 'migrations'}:/docker-entrypoint-initdb.d:ro"
    container = ["--name", TEST_DB, "-p", f"127.0.0.1:{TEST_DB_PORT}:5432", "-v", schema]
    run("docker", "run", "-d", *container, *credentials, "pgvector/pgvector:pg16")
    # Over TCP: the server that runs initdb.d listens only on its socket, so this waits for the schema.
    ready = ["docker", "exec", TEST_DB, "pg_isready", "-U", "scene", "-h", "127.0.0.1"]
    for _ in range(60):
        if subprocess.run(ready, capture_output=True).returncode == 0:
            return
        time.sleep(1)
    sys.exit("Test database did not become ready")


def pytest(*arguments, env=None):
    # Pytest's temporary Workspaces live outside the repository.
    basetemp = Path(tempfile.gettempdir()) / "scene-pytest"
    python("pytest", "-p", "no:cacheprovider", f"--basetemp={basetemp}", *arguments, env=env)


def ruff(subcommand, arguments):
    # Findings are the output, not a crash: exit with Ruff's status and no traceback.
    sys.exit(python("ruff", subcommand, "backend", "main.py", *arguments, check=False).returncode)


@command("run every test against a disposable test database (needs Docker)", passthrough=True)
def test(args):
    ensure_test_database()
    pytest(*args.extra_args, env={"TEST_DATABASE_URL": TEST_DATABASE_URL})


@command("run the tests that need no database or Docker", passthrough=True)
def test_unit(args):
    pytest("-m", "not db", *args.extra_args)


@command("check the Python code with Ruff", passthrough=True)
def lint(args):
    ruff("check", args.extra_args)


@command("format the Python code with Ruff", name="format", passthrough=True)
def format_code(args):
    ruff("format", args.extra_args)


@command("export the API contract to backend/openapi/openapi.json")
def openapi(_):
    python("scene_api.export_openapi", env={"DATABASE_URL": "postgresql://unused@localhost/unused"})


@command("remove all caches (Python, uv, frontend .next)")
def clean(_):
    skip = {".venv", "venv", "node_modules", ".git"}
    caches = {"__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache", ".cache"}
    removed = 0
    for folder, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in skip]
        for d in [d for d in dirs if d in caches]:
            shutil.rmtree(Path(folder) / d, ignore_errors=True)
            dirs.remove(d)
            removed += 1
        for f in files:
            if f.endswith((".pyc", ".pyo")):
                (Path(folder) / f).unlink(missing_ok=True)
                removed += 1
    for cache in (ROOT / "frontend/.next", ROOT / "frontend/node_modules/.cache"):
        if cache.exists():
            shutil.rmtree(cache, ignore_errors=True)
            removed += 1
    if shutil.which("uv"):
        run("uv", "cache", "clean", "--force", check=False)
    print(f"Cleaned {removed} cache locations and cleared uv cache.")


# GPU image


def image_name(args):
    """`--image` wins; otherwise COMPUTE_IMAGE_REPO:<variant>-<git short sha>, so live checks name an exact build."""
    if args.image:
        return args.image
    repository = env_values().get("COMPUTE_IMAGE_REPO")
    if not repository or "<" in repository:
        sys.exit("Pass --image or set COMPUTE_IMAGE_REPO in backend/.env")
    revision = output("git", "rev-parse", "--short", "HEAD").strip()
    return f"{repository}:{args.extras or 'fake'}-{revision}"


@command("build the GPU image", *IMAGE_ARGUMENTS)
def compute_image(args):
    dockerfile = str(ROOT / "Dockerfile.compute")
    platform = ["--platform", "linux/amd64", "--build-arg", f"EXTRAS={args.extras}"]
    run("docker", "build", *platform, "-f", dockerfile, "-t", image_name(args), str(ROOT))


@command("build and push the GPU image", *IMAGE_ARGUMENTS)
def push_compute_image(args):
    compute_image(args)
    image = image_name(args)
    run("docker", "push", image)
    template = "{{range .RepoDigests}}{{println .}}{{end}}"
    digests = output("docker", "image", "inspect", "--format", template, image).split()
    digest = next((d for d in digests if d.startswith(image.rsplit(":", 1)[0] + "@")), "unknown")
    print(f"Pushed {image}\nDigest {digest}")


@command(
    "deploy scene-compute to Modal (built remotely)",
    (["--variant"], {"default": "fake", "choices": ["fake", "gpu"]}),
)
def deploy_modal(args):
    fake = args.variant == "fake"
    env = {
        "COMPUTE_EXTRAS": "" if fake else args.variant,
        "MODAL_APP_NAME": "scene-compute" if fake else f"scene-compute-{args.variant}",
    }
    run("uvx", "modal", "deploy", str(BACKEND / "deploy/modal/app.py"), env=env)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name, (handler, help_text, arguments, _) in COMMANDS.items():
        subparser = subparsers.add_parser(name, help=help_text)
        for flags, options in arguments:
            subparser.add_argument(*flags, **options)
        subparser.set_defaults(handler=handler)
    args, extra = parser.parse_known_args()
    if extra and not COMMANDS[args.command][3]:
        parser.error(f"unrecognized arguments: {' '.join(extra)}")
    args.extra_args = extra
    args.handler(args)


if __name__ == "__main__":
    main()
