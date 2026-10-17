import logging
import time

from scene_core.contracts import STAGES
from scene_core.results import SceneResults
from scene_store import SceneStore
from scene_target import open_target_workspace


class Worker:
    def __init__(self, database_url, data_dir, pipeline=None, compute=None, target=None):
        """target replaces the TargetWorkspace built from pipeline and compute, for tests."""
        self.store = SceneStore(database_url)
        self.data_dir = data_dir
        self.target = target or open_target_workspace(data_dir, pipeline, compute)

    def recover_interrupted(self):
        for failure in self.store.recover_interrupted():
            logging.warning(
                "Job %s was interrupted at %s; marked failed", failure["job_id"], failure["stage"]
            )

    def run_once(self):
        job = self.store.claim()
        if not job:
            return False
        stage = None
        try:
            scene_id = str(job["scene_id"])
            # Every Job runs all Stages from the uploaded inputs, which stay on the Target (ADR-0005).
            self.target.clear_outputs(scene_id)
            for stage in STAGES:
                self.store.stage_started(job, stage, self.target.pipeline.stages[stage].algorithm)
                self.store.stage_done(
                    job,
                    stage,
                    self.target.run_stage(scene_id, stage, on_progress=self._reporter(job, stage)),
                )
            stage = None
            # This Job's results become the Scene's publication only once they are complete, valid and committed.
            self.target.replace_results(
                scene_id,
                str(job["id"]),
                lambda results: self.store.publish(job, SceneResults(results).load()),
            )
        except Exception as exc:
            logging.exception("Job %s failed at %s", job["id"], stage)
            self.store.fail(
                job,
                stage,
                getattr(exc, "code", "STAGE_FAILED"),
                str(exc),
                getattr(exc, "details", {}),
            )
        return True

    def _reporter(self, job, stage, interval=2.0):
        """Store and announce Stage progress at most every interval seconds, always including the last report."""
        last = [float("-inf")]

        def report(progress):
            now = time.monotonic()
            if progress["done"] < progress["total"] and now - last[0] < interval:
                return
            last[0] = now
            self.store.stage_progress(job, stage, progress)

        return report
