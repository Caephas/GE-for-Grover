#!/usr/bin/env python3
"""Headless sweep dispatcher with per-job retry (Spot-safe).

Runs the full (state x seed x arm) matrix as one `run_experiment.py run`
subprocess per job at a fixed concurrency. A job counts as done only when its
run_result_<state>_run<id>.json marker exists. If a process dies (Spot
preemption, crash, OOM) without the marker, the job is requeued up to
--max-retries times with a delay, so preemptions just extend the sweep
instead of losing runs.

Credentials are never printed or written by this script: QISKIT_IBM_TOKEN /
QISKIT_IBM_INSTANCE are read from the process environment only, and the
launcher sources them from a chmod-600 file outside the experiments tree.

Usage:
  python3 run_sweep.py --concurrency 15
  python3 run_sweep.py --concurrency 2 --arms epsilon_lexicase \
      --states 000 --seeds 21315          # tiny smoke / kill-test matrix
"""
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DRIVER = os.path.join(REPO, "run_experiment.py")
VENV_PY = os.path.join(REPO, ".venv", "bin", "python")

RUN_SEEDS = [
    21315, 47182, 12147, 33537, 70300,   # original 5 (kept first)
    74135, 67154, 80248, 91197, 29440,   # new fixed seeds 6-10
    51418, 98274, 63664, 32849, 59179,   # new fixed seeds 11-15
    20168, 13982, 25033, 31330, 81964,   # new fixed seeds 16-20
]
STATES = [f"{i:03b}" for i in range(8)]
ARMS = ["epsilon_lexicase", "tournament"]


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--concurrency", type=int, default=15)
    ap.add_argument("--arms", default=",".join(ARMS))
    ap.add_argument("--states", default=",".join(STATES))
    ap.add_argument("--seeds", default=",".join(map(str, RUN_SEEDS)))
    ap.add_argument("--population", type=int, default=300)
    ap.add_argument("--generations", type=int, default=100)
    ap.add_argument("--outdir", default=os.path.join(REPO, "experiments"))
    ap.add_argument("--logdir", default=os.path.join(REPO, "logs"))
    ap.add_argument("--max-retries", type=int, default=5)
    ap.add_argument("--retry-delay", type=int, default=120)
    ap.add_argument("--poll-interval", type=int, default=30)
    ap.add_argument("--sync-every", type=int, default=0,
                    help="seconds between GCS syncs (0 = off)")
    ap.add_argument("--sync-script",
                    default=os.path.join(HERE, "sync_gcs.sh"))
    ap.add_argument("--noise-file", default=None,
                    help="frozen noise-model snapshot (pickle or JSON); exported as "
                         "QISKIT_NOISE_MODEL_JSON to every child run")
    ap.add_argument("--python",
                    default=VENV_PY if os.path.exists(VENV_PY) else sys.executable)
    args = ap.parse_args()

    arms = [a for a in args.arms.split(",") if a]
    states = [s for s in args.states.split(",") if s]
    seeds = [int(s) for s in args.seeds.split(",") if s]
    os.makedirs(args.logdir, exist_ok=True)
    os.makedirs(args.outdir, exist_ok=True)
    sweep_log = os.path.join(args.logdir, "sweep.log")
    progress_path = os.path.join(args.logdir, "sweep_progress.json")

    jobs = []
    for arm in arms:
        for state in states:
            for run_id, seed in enumerate(seeds, start=1):
                run_dir = os.path.join(args.outdir, arm, f"pop{args.population}",
                                       "noise", f"state_{state}",
                                       f"run_{run_id}_seed_{seed}")
                marker = os.path.join(run_dir,
                                      f"run_result_{state}_run{run_id}.json")
                job_log = os.path.join(
                    args.logdir,
                    f"job_{arm}_{state}_seed{seed}_run{run_id}.log")
                jobs.append({
                    "arm": arm, "state": state, "seed": seed,
                    "run_id": run_id, "run_dir": run_dir, "marker": marker,
                    "log": job_log,
                })

    pending = [j for j in jobs if not os.path.exists(j["marker"])]
    done_initial = len(jobs) - len(pending)
    active = {}          # id(job) -> (job, Popen)
    completed = 0
    failed = 0
    last_sync = time.time()
    started_at = time.time()

    def append(msg: str) -> None:
        with open(sweep_log, "a") as f:
            f.write(f"[{utcnow()}] {msg}\n")

    def write_progress() -> None:
        info = {
            "started_utc": utcnow(),
            "total_jobs": len(jobs),
            "completed_on_entry": done_initial,
            "completed": completed,
            "failed": failed,
            "pending": len(pending),
            "active": len(active),
            "elapsed_sec": round(time.time() - started_at, 1),
        }
        with open(progress_path, "w") as f:
            json.dump(info, f, indent=2)

    append(f"Dispatcher start: {len(jobs)} jobs total, {done_initial} already "
           f"complete, {len(pending)} to run, concurrency={args.concurrency}")
    write_progress()

    def spawn(job: dict) -> subprocess.Popen:
        cmd = [
            args.python, "-u", DRIVER, "run",
            "--state", job["state"],
            "--seed", str(job["seed"]),
            "--selection", job["arm"],
            "--population", str(args.population),
            "--generations", str(args.generations),
            "--outdir", args.outdir,
            "--run-id", str(job["run_id"]),
            "--workers", "1",
        ]
        os.makedirs(job["run_dir"], exist_ok=True)
        fh = open(job["log"], "a")
        job["attempts"] = job.get("attempts", 0) + 1
        env = dict(os.environ)
        if args.noise_file:
            env["QISKIT_NOISE_MODEL_JSON"] = args.noise_file
        proc = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT,
                                env=env)
        append(f"start state={job['state']} seed={job['seed']} "
               f"arm={job['arm']} run_id={job['run_id']} pid={proc.pid} "
               f"attempt={job['attempts']}")
        return proc

    while pending or active:
        while len(active) < args.concurrency and pending:
            job = pending.pop(0)
            active[id(job)] = (job, spawn(job))

        if (args.sync_every and args.sync_script
                and time.time() - last_sync >= args.sync_every):
            append("periodic GCS sync")
            try:
                subprocess.run([args.sync_script], check=False)
            except Exception as exc:  # noqa: BLE001
                append(f"GCS sync error: {exc}")
            last_sync = time.time()

        time.sleep(args.poll_interval)

        for jid, (job, proc) in list(active.items()):
            ret = proc.poll()
            if ret is None:
                continue
            ok = (ret == 0) and os.path.exists(job["marker"])
            if ok:
                completed += 1
                append(f"done state={job['state']} seed={job['seed']} "
                       f"arm={job['arm']} run_id={job['run_id']} rc={ret}")
            else:
                attempts = job.get("attempts", 0)
                if attempts < args.max_retries:
                    append(f"retry state={job['state']} seed={job['seed']} "
                           f"arm={job['arm']} run_id={job['run_id']} rc={ret} "
                           f"attempt={attempts}")
                    time.sleep(min(args.retry_delay, 60))
                    pending.append(job)
                else:
                    failed += 1
                    append(f"FAILED state={job['state']} seed={job['seed']} "
                           f"arm={job['arm']} run_id={job['run_id']} rc={ret} "
                           f"(exhausted retries)")
            del active[jid]
        write_progress()

    write_progress()
    elapsed_h = round((time.time() - started_at) / 3600, 2)
    append(f"Dispatcher finished: {completed} completed, {failed} failed, "
           f"{done_initial} already complete (elapsed {elapsed_h} h)")
    print(f"[{utcnow()}] sweep finished: {completed} completed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
