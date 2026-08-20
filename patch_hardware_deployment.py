"""Fix hardware deployment/attribution in all lexicase + tournament notebooks.

Changes, applied identically to every ibm_lexicase_transpiled_*.ipynb and
ibm_tournament_transpiled_*.ipynb (state 000-111):

1. run_hof_on_ibm (cell 42): accept an explicit log_dir and save the hardware
   JSON there instead of the stale module-global LOG_DIR.
2. Hardware validation cell (43): deploy the run with the lambda-free
   lexicographic rule (max fidelity, then min transpiled 2Q gates, then min
   transpiled depth) instead of min raw_fitness, and pass that run's log_dir.
3. run_hof_on_ibm (cell 42): accept the deployed run's seed as seed_transpiler
   so the hardware transpilation matches the fitness-time transpilation seed.
"""

import glob
import json
import sys

SIGNATURE_OLD = "def run_hof_on_ibm(evaluator, hof, target_state=TARGET_STATE):"
SIGNATURE_NEW = "def run_hof_on_ibm(evaluator, hof, target_state=TARGET_STATE, log_dir=None):"

SAVE_OLD = (
    "            os.makedirs(LOG_DIR, exist_ok=True)\n"
    "            json_path = os.path.join(LOG_DIR, f\"hof_{i+1}_ibm_hardware_data.json\")"
)
SAVE_NEW = (
    "            out_dir = log_dir or evaluator.log_dir or LOG_DIR\n"
    "            os.makedirs(out_dir, exist_ok=True)\n"
    "            json_path = os.path.join(out_dir, f\"hof_{i+1}_ibm_hardware_data.json\")"
)

BEST_OLD = 'best_run = min(all_run_results, key=lambda r: r["raw_fitness"])'
BEST_NEW = ('best_run = max(all_run_results, '
            'key=lambda r: (r["fidelity"], -r["two_qubit_gates"], -r["depth"]))')

CALL_OLD = "run_hof_on_ibm(hw_evaluator, dummy_hof, target_state=TARGET_STATE_FOR_EXPERIMENT)"
CALL_NEW = (
    "run_hof_on_ibm(hw_evaluator, dummy_hof, "
    "target_state=TARGET_STATE_FOR_EXPERIMENT, log_dir=best_run[\"log_dir\"])"
)

SEED_SIG_OLD = "def run_hof_on_ibm(evaluator, hof, target_state=TARGET_STATE, log_dir=None):"
SEED_SIG_NEW = (
    "def run_hof_on_ibm(evaluator, hof, target_state=TARGET_STATE, "
    "log_dir=None, seed_transpiler=None):"
)

PM_OLD = (
    "            pm = generate_preset_pass_manager(\n"
    "                target=backend.target,\n"
    "                optimization_level=3,\n"
    "                seed_transpiler=RANDOM_SEED  # makes transpilation consistent\n"
    "            )"
)
PM_NEW = (
    "            transpile_seed = seed_transpiler if seed_transpiler is not None else RANDOM_SEED\n"
    "            pm = generate_preset_pass_manager(\n"
    "                target=backend.target,\n"
    "                optimization_level=3,\n"
    "                seed_transpiler=transpile_seed  # matches fitness-time transpile seed\n"
    "            )"
)

SEED_CALL_OLD = CALL_NEW
SEED_CALL_NEW = (
    "run_hof_on_ibm(hw_evaluator, dummy_hof, "
    "target_state=TARGET_STATE_FOR_EXPERIMENT, log_dir=best_run[\"log_dir\"], "
    "seed_transpiler=best_run[\"seed\"])"
)


CELL42_PAIRS = [
    (SIGNATURE_OLD, SIGNATURE_NEW, "cell42 signature"),
    (SAVE_OLD, SAVE_NEW, "cell42 save block"),
    (SEED_SIG_OLD, SEED_SIG_NEW, "cell42 seed-transpiler signature"),
    (PM_OLD, PM_NEW, "cell42 pass-manager seed"),
]
CELL43_PAIRS = [
    (BEST_OLD, BEST_NEW, "cell43 best_run"),
    (CALL_OLD, CALL_NEW, "cell43 call"),
    (SEED_CALL_OLD, SEED_CALL_NEW, "cell43 seed-transpiler call"),
]


def apply_replacements(source: str, pairs) -> str:
    for old, new, what in pairs:
        n = source.count(old)
        if n != 1:
            raise RuntimeError(f"expected exactly 1 occurrence of {what}, found {n}")
        source = source.replace(old, new)
    return source


CELL42_FINAL = [SEED_SIG_NEW, SAVE_NEW, PM_NEW]
CELL43_FINAL = [BEST_NEW, SEED_CALL_NEW]


def main() -> None:
    states = ["000", "001", "010", "011", "100", "101", "110", "111"]
    files = sorted(
        [f"ibm_lexicase_transpiled_{s}.ipynb" for s in states]
        + [f"ibm_tournament_transpiled_{s}.ipynb" for s in states]
    )
    if len(files) != 16:
        print(f"!! expected 16 notebooks, found {len(files)}: {files}")
        sys.exit(1)

    for f in files:
        nb = json.load(open(f))
        for ci in (42, 43):
            cell = nb["cells"][ci]
            if cell["cell_type"] != "code":
                raise RuntimeError(f"{f}: cell {ci} is not a code cell")
            src = "".join(cell["source"])
            final = CELL42_FINAL if ci == 42 else CELL43_FINAL
            if all(frag in src for frag in final):
                continue  # already fully patched (idempotent re-run)
            pairs = CELL42_PAIRS if ci == 42 else CELL43_PAIRS
            src_new = apply_replacements(src, pairs)
            cell["source"] = src_new.splitlines(keepends=True)
        with open(f, "w") as fh:
            json.dump(nb, fh, indent=1, ensure_ascii=False)
            fh.write("\n")
        print(f"✓ patched {f}")


if __name__ == "__main__":
    main()
