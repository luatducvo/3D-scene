import os,time,logging
from pathlib import Path
from .runner import Worker

def main():
    logging.basicConfig(level=logging.INFO)
    worker=Worker(os.environ["DATABASE_URL"],Path(os.getenv("DATA_DIR","data")))
    worker.repo.migrate()
    while True:
        if not worker.run_once():time.sleep(0.5)
if __name__=="__main__":main()
