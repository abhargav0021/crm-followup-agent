import time
from agent import main

SECONDS_PER_DAY = 86400


def run_scheduler(interval_seconds=SECONDS_PER_DAY):
    while True:
        print("Running automation pipeline...")
        main()
        time.sleep(interval_seconds)


if __name__ == "__main__":
    run_scheduler()
