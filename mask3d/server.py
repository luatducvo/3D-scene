"""Small volume-path HTTP bridge that runs each Mask3D request in a child process."""

import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DATA = Path("/data").resolve()
RUN_LOCK = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/health":
            self.send_error(404)
            return
        self._json(200, {"status": "ok"})

    def do_POST(self):
        if self.path != "/run":
            self.send_error(404)
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size < 1 or size > 4096:
                raise ValueError("Invalid request length")
            body = json.loads(self.rfile.read(size))
            mesh = Path(body["mesh"]).resolve()
            output = Path(body["output"]).resolve()
            if not mesh.is_relative_to(DATA) or not output.is_relative_to(DATA):
                raise ValueError("Paths must be inside /data")
            if not mesh.is_file():
                raise ValueError("Mesh does not exist")
            with RUN_LOCK:
                requested = float(body.get("voxel_m", os.getenv("S3D_MASK3D_VOXEL", "0.03")))
                if requested not in {0.02, 0.03, 0.04}:
                    raise ValueError("Supported voxels: 0.02, 0.03, 0.04 m")
                for voxel in (str(requested), "0.04"):
                    result = subprocess.run([sys.executable, "/app/infer.py", str(mesh), str(output),
                                             "--voxel", voxel], capture_output=True, text=True,
                                            timeout=1200, check=False)
                    if not result.returncode or "out of memory" not in result.stderr.lower():
                        break
            if result.returncode:
                raise RuntimeError(result.stderr[-2000:] or f"Mask3D exited {result.returncode}")
            self._json(200, json.loads(result.stdout.splitlines()[-1]))
        except (KeyError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
            self._json(400, {"error": str(exc)})

    def _json(self, status: int, body: dict):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 9000), Handler).serve_forever()
