"""One worker process cycles through isolated organization job stores."""

import argparse
import os
import time

from services.api.storage import database
from services.inference.worker import run_one
from services.organizations import load_registry


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    registry = load_registry(os.environ["FRAUDGRAPH_ORGANIZATIONS_FILE"])
    workers = []
    try:
        for organization in registry.organizations:
            settings = registry.settings_for(organization)
            engine, sessions = database(settings.database_url)
            workers.append((settings, engine, sessions))
        while True:
            worked = False
            for settings, _, sessions in workers:
                worked = run_one(settings, sessions) or worked
            if args.once:
                return
            if not worked:
                time.sleep(2)
    finally:
        for _, engine, _ in workers:
            engine.dispose()


if __name__ == "__main__":
    main()
