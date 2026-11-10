"""Run the PostgreSQL simulation queue in a dedicated pool of processes."""

import argparse
import logging
import multiprocessing
from multiprocessing.connection import wait
import signal


def worker_main(shutdown):
    # The parent handles Ctrl+C and lets workers finish their current step.
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    logging.basicConfig(level=logging.INFO)

    from backend.app.db.session import SessionLocal
    from backend.app.services.simulation_execution import run_worker

    run_worker(SessionLocal, shutdown)


def stop_pool(signum, frame):
    raise KeyboardInterrupt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    if args.workers < 1:
        parser.error("--workers must be at least 1")

    context = multiprocessing.get_context("spawn")
    shutdown = context.Event()
    processes = []
    signal.signal(signal.SIGTERM, stop_pool)
    try:
        for number in range(1, args.workers + 1):
            process = context.Process(
                name=f"simulation-worker-{number}", target=worker_main, args=(shutdown,),
            )
            process.start()
            processes.append(process)
        print(f"Simulation workers started: {len(processes)}", flush=True)
        wait([process.sentinel for process in processes])
        raise SystemExit("A simulation worker exited unexpectedly")
    except KeyboardInterrupt:
        print("Stopping simulation workers after their current step", flush=True)
    finally:
        shutdown.set()
        for process in processes:
            process.join()


if __name__ == "__main__":
    main()
