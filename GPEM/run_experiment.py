#!/usr/bin/env python3
"""Headless parameterized Grover-circuit evolution driver.

Single-file refactor of the per-state notebooks
(ibm_lexicase_transpiled_XXX.ipynb / ibm_tournament_transpiled_XXX.ipynb).
All experiment logic (fitness, grammar, epsilon-lexicase/tournament selection,
in-loop transpilation, early stopping, checkpoints, diagnostics, metadata) is
extracted byte-for-byte from the canonical notebook cell sources; only the
following structural adaptations were made:

  1. Configuration, backend connection, and outputs are driven by CLI args
     (--state/--seed/--selection/--population/--generations/--outdir) instead
     of notebook cells.
  2. Per-run output root is --outdir (default "experiments", preserving the
     notebook layout experiments/{selection}/pop{N}/noise/state_{S}/run_*).
  3. IBM credentials come from the saved account or the QISKIT_IBM_TOKEN /
     QISKIT_IBM_INSTANCE environment variables -- never embedded in code.
  4. Deployment pick uses the agreed lambda-free lexicographic rule
     (max fidelity, then min transpiled 2Q gates, then min transpiled depth).
  5. IPython ``display`` calls are no-ops in headless mode; circuit PNGs are
     still saved exactly as before.
  6. lexi2 selection arm (8-case epsilon-lexicase over output-state
     probabilities + size tiebreak) is implemented; per_prob remains a stub
     that raises a clear NotImplementedError.

This script NEVER submits IBM Quantum hardware jobs. Noisy-simulation runs
only; hardware deployment remains a separate manual step (redeploy_hardware.py).

Usage:
  python run_experiment.py run \
      --state 000 --seed 21315 --selection epsilon_lexicase \
      --population 300 --generations 100 --outdir experiments
  python run_experiment.py aggregate \
      --state 000 --selection epsilon_lexicase --population 300 --outdir experiments
"""

# Standard Library Imports
import os
os.environ.setdefault('PYTHONHASHSEED', '0')  # Must also be set before launch to fully take effect
import re
import json
import random
import multiprocessing
from typing import Any, Tuple, Optional, List, Dict
from functools import partial
import glob
import shutil
import pickle
from datetime import datetime
import time
from collections import deque
import logging
import hashlib
import sys
import statistics

# Third-party Imports
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # headless: never open GUI windows; PNGs are still saved
import matplotlib.pyplot as plt
from qiskit import QuantumCircuit, transpile, ClassicalRegister, QuantumRegister
from qiskit import qasm2
from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2 as Sampler
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
from qiskit_aer import QasmSimulator, AerSimulator
from qiskit_aer.noise import NoiseModel
from qiskit.visualization import plot_distribution
from deap import creator, base, tools

import grape  # Grammatical evolution library
from grape import algorithms  # Evolutionary algorithms
from copy import deepcopy
import platform
from importlib.metadata import version as pkg_version


def display(*args, **kwargs):
    """Headless no-op stand-in for IPython.display.display (notebook only)."""
    return None


logger = logging.getLogger(__name__)

def stable_genome_hash(genome):
    import hashlib
    return int(hashlib.sha256(str(list(genome)).encode()).hexdigest()[:8], 16)

# === MULTI-RUN CONFIGURATION ===
# RUN_SEEDS holds 20 fixed seeds for future extension: the original five,
# then 15 new fixed seeds (drawn deterministically from
# random.Random(20260819); distinct from the original five). The frozen
# 3-arm paper batch (240 runs = 3 arms x 8 states x 10 seeds) used ONLY
# RUN_SEEDS[:10] below; the last 10 seeds have not been run. To run only
# the 15 new seeds, slice RUN_SEEDS[5:] and set NUMBER_OF_RUNS = 15.
RUN_SEEDS = [
    21315, 47182, 12147, 33537, 70300,          # original 5 (earlier GECCO paper)
    74135, 67154, 80248, 91197, 29440,          # next 5: frozen paper batch (RUN_SEEDS[:10])
    51418, 98274, 63664, 32849, 59179,          # not run (future extension)
    20168, 13982, 25033, 31330, 81964,          # not run (future extension)
]
NUMBER_OF_RUNS = len(RUN_SEEDS)

# === CORE CONFIGURATION ===
# Target state for Grover's algorithm (overridden by --state)
TARGET_STATE = "000"

# Simulation Configuration
USE_NOISE_MODEL = True  # Set to True for hardware-aware simulation (--ideal disables)
USE_FIXED_SEED = True    # Set to False for random initialization

# Set random seed (overridden by --seed)
RANDOM_SEED = 21315

# === CHECKPOINT & TRANSFER LEARNING CONFIGURATION ===
RESUME_FROM_CHECKPOINT = True
USE_TRANSFER_LEARNING = False
TRANSFER_SOURCE_PATH = "./checkpoints_ibm_ideal_001/checkpoint_latest.pkl"
TRANSFER_RATIO = 0.3
MUTATION_BOOST = 0.3
CHECKPOINT_FREQUENCY = 10

# Placeholder directories -- overridden per-run in run_evolution_experiment.
LOG_DIR = None
CHECKPOINT_DIR = None
CHECKPOINT_PATH = None

# === EARLY STOPPING CONFIGURATION ===
USE_EARLY_STOPPING = True
EARLY_STOPPING_MODE = "nisq_focused"
MIN_GENERATIONS_BEFORE_STOPPING = 15
FIDELITY_SUCCESS_THRESHOLD = 0.95
GATE_COUNT_TARGET = 20
DEPTH_TARGET = 15

if EARLY_STOPPING_MODE == "nisq_focused":
    EARLY_STOPPING_PATIENCE = {
        'fitness': 25,
        'fidelity': 8,
        'gate_count': 10,
        'depth': 10,
        'composite': 15
    }
    MIN_IMPROVEMENT_DELTA = {
        'fitness': 0.01,
        'fidelity': 0.005,
        'gate_count': 1,
        'depth': 1
    }
    METRIC_WEIGHTS = {
        'fitness': 0.15,
        'fidelity': 0.35,
        'gate_count': 0.30,
        'depth': 0.20
    }
    EARLY_STOPPING_STRATEGY = "nisq_hierarchical"

MOVING_AVERAGE_WINDOW = 3
USE_RELATIVE_IMPROVEMENT = True
EARLY_STOPPING_VERBOSE = True

# === EVOLUTION PARAMETERS ===
POPULATION_SIZE    = 300
MAX_GENERATIONS    = 100
N_GEN = 1
P_CROSSOVER        = 0.8
P_MUTATION         = 0.01
ELITE_SIZE         = 1
HALLOFFAME_SIZE    = 1
CODON_SIZE         = 400
MAX_TREE_DEPTH     = 50
TOURNAMENT_SIZE    = 5
MIN_INIT_DEPTH     = 20
MAX_INIT_DEPTH     = 40
CODON_CONSUMPTION  = "lazy"
GENOME_REPRESENTATION = 'list'

# Evaluation Constants
NUM_SHOTS = 10000
SUCCESS_THRESHOLD = 0.48
GATE_PENALTY_WEIGHT = 0.02  # Used only in tournament mode

# Lexicase normalization bounds (used to scale test cases to [0, 1])
MAX_EXPECTED_GATES = 200
MAX_EXPECTED_DEPTH = 150

# Selection / output roots (overridden by CLI)
SELECTION_METHOD = "epsilon_lexicase"
EXPERIMENTS_ROOT = "experiments"

# Lexi2 per-generation log: {generation: {eps, tiebreak_fires, selections,
# post_case_pool_sizes}}. Reset per run; written to LOG_DIR at run end.
lexi2_log = {}
ALL_STATES = [f"{i:03b}" for i in range(8)]

# Runtime globals populated by setup functions (kept as module globals because
# the extracted notebook code reads them directly).
service = None
backend = None
backend_name = None
noise_model_sim = None
ideal_sim = None
NOISE_MODEL_PATH = None
FROZEN_TARGET = None
transpile_cache = None
diagnostics = None
toolbox = None
pool = None
stats = None
evaluator = None
eval_counter = 0

# Load BNF Grammar (path resolved relative to this file, so the driver works
# from any working directory).
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BNF_GRAMMAR = grape.Grammar(os.path.join(_SCRIPT_DIR, "grammars", "grover.bnf"))

def connect_to_backend():
    """Connect to ibm_fez using the saved account or env credentials.

    Replaces the notebook's embedded save_account()/token: credentials are read
    from QISKIT_IBM_TOKEN / QISKIT_IBM_INSTANCE if set, otherwise the saved
    account on disk is used. No hardware jobs are ever submitted here; the
    backend is used for the in-loop transpilation target and to build the
    noise model (AerSimulator.from_backend) from the live calibration.
    """
    global service, backend, backend_name, noise_model_sim, ideal_sim
    global NOISE_MODEL_PATH, FROZEN_TARGET

    token = os.environ.get("QISKIT_IBM_TOKEN")
    instance = os.environ.get("QISKIT_IBM_INSTANCE")
    if token:
        service = QiskitRuntimeService(channel="ibm_cloud", token=token,
                                       instance=instance or None)
    else:
        service = QiskitRuntimeService(channel="ibm_cloud")

    backend = service.backend("ibm_fez")
    backend_name = backend.name
    print(f"✓ Connected to backend: {backend_name}")

    # === HARDWARE SETUP (notebook cell 17) ===
    num_cores = os.cpu_count()
    print(f"CPU cores available: {num_cores}")

    if USE_NOISE_MODEL:
        noise_model_path = (NOISE_MODEL_PATH
                            or os.environ.get("QISKIT_NOISE_MODEL_JSON"))
        if noise_model_path and os.path.exists(noise_model_path):
            _nm, _target = load_frozen_env(noise_model_path)
            noise_model_sim = AerSimulator(noise_model=_nm)
            ideal_sim = QasmSimulator()
            FROZEN_TARGET = _target
            print(f"✓ AerSimulator with FROZEN noise model: {noise_model_path}")
            if FROZEN_TARGET is not None:
                print(f"✓ FROZEN transpile target loaded from the same bundle "
                      f"({FROZEN_TARGET.num_qubits} qubits)")
            else:
                print("  ⚠ bundle has no frozen target; using live backend "
                      "for transpilation")
        else:
            noise_model_sim = AerSimulator.from_backend(backend)
            ideal_sim = QasmSimulator()
            print("✓ AerSimulator with noise model created")
    else:
        ideal_sim = QasmSimulator()
        noise_model_sim = ideal_sim
        print("✓ Using QasmSimulator (no noise)")

    return backend


def load_frozen_env(path: str):
    """Load a frozen environment bundle -> (NoiseModel, Target or None).

    The capture script (infra/capture_noise.py) writes a pickle bundle
    {"noise_model": NoiseModel, "target": Target} so both the simulation noise
    and the in-loop transpilation target are frozen (no live ibm_fez
    dependency for layout decisions). A bare NoiseModel pickle or a .json
    NoiseModel.to_dict() dump is also accepted (target stays None -> live
    backend is used for transpilation).
    """
    with open(path, "rb") as f:
        obj = pickle.load(f)
    if isinstance(obj, dict) and "noise_model" in obj:
        return obj["noise_model"], obj.get("target")
    if isinstance(obj, NoiseModel):
        return obj, None
    if path.endswith(".json"):
        with open(path) as f:
            return NoiseModel.from_dict(json.load(f)), None
    raise ValueError(f"unrecognized frozen-env format: {path}")


def transpile_target():
    """Target used for in-loop transpilation: frozen bundle target if present,
    otherwise the live backend (unchanged legacy behavior)."""
    return FROZEN_TARGET if FROZEN_TARGET is not None else backend

def selLexicaseQuantum(individuals, k):
    """
    Lexicase selection adapted for quantum circuit optimization.
    
    Each individual must have `fitness_each_sample` — a list of per-objective
    scores where HIGHER IS BETTER:
        [0] fidelity      (p_marked, range [0, 1])
        [1] gate_efficiency (1 - gate_count/MAX, range [0, 1])
        [2] depth_efficiency (1 - depth/MAX, range [0, 1])
    
    Algorithm:
        For each of k selections:
        1. Start with all candidates
        2. Shuffle the test cases (objectives)
        3. Filter to individuals that are best on the first objective
        4. Among survivors, filter to best on the second objective
        5. Continue until one remains or cases exhausted
        6. Pick randomly among survivors
    
    This preserves specialists: a high-fidelity but deep circuit can survive
    alongside a shallow but lower-fidelity one.
    
    Based on selLexicaseFilter from GRAPE (de Lima et al., 2022).
    """
    selected_individuals = []
    
    # Filter to valid individuals with fitness_each_sample
    valid = [ind for ind in individuals 
             if hasattr(ind, 'fitness_each_sample') and ind.fitness_each_sample is not None]
    
    if len(valid) == 0:
        # Fallback: random selection if no valid individuals
        for _ in range(k):
            selected_individuals.append(random.choice(individuals))
        return selected_individuals
    
    n_cases = len(valid[0].fitness_each_sample)
    
    # Prefilter: group by unique behavior vectors to speed up selection
    # This avoids redundant comparisons among identical individuals
    error_vectors = [tuple(ind.fitness_each_sample) for ind in valid]
    unique_vectors = list(set(error_vectors))
    
    # Build groups: each unique vector maps to a list of individuals
    vector_to_inds = {}
    for vec in unique_vectors:
        vector_to_inds[vec] = [ind for ind, ev in zip(valid, error_vectors) if ev == vec]
    
    for _ in range(k):
        # Build pool: one random representative per unique behavior vector
        pool = [random.choice(vector_to_inds[vec]) for vec in unique_vectors]
        
        # Shuffle objective order
        cases = list(range(n_cases))
        random.shuffle(cases)
        
        while len(cases) > 0 and len(pool) > 1:
            case_idx = cases[0]
            # Find best value for this objective (higher is better)
            best_val = max(ind.fitness_each_sample[case_idx] for ind in pool)
            # Keep only individuals matching the best value
            pool = [ind for ind in pool if ind.fitness_each_sample[case_idx] == best_val]
            del cases[0]
        
        selected_individuals.append(random.choice(pool))
    
    return selected_individuals


def selEpsilonLexicaseQuantum(individuals, k, epsilon_method="mad"):
    """
    Epsilon-lexicase selection for quantum circuits.
    
    Instead of requiring exact equality with the best, individuals within
    epsilon of the best are kept. Epsilon is computed per-objective using
    Median Absolute Deviation (MAD).
    
    This is more forgiving than strict lexicase when fitness values are
    continuous (as they are for fidelity from shot-based simulation).
    """
    selected_individuals = []
    
    valid = [ind for ind in individuals 
             if hasattr(ind, 'fitness_each_sample') and ind.fitness_each_sample is not None]
    
    if len(valid) == 0:
        for _ in range(k):
            selected_individuals.append(random.choice(individuals))
        return selected_individuals
    
    n_cases = len(valid[0].fitness_each_sample)
    
    # Build fitness matrix: individuals x objectives
    fitness_matrix = np.array([ind.fitness_each_sample for ind in valid])
    
    # Compute epsilon per objective using MAD
    if epsilon_method == "mad":
        medians = np.median(fitness_matrix, axis=0)
        mad = np.median(np.abs(fitness_matrix - medians), axis=0)
        epsilons = mad
    else:
        epsilons = np.zeros(n_cases)
    
    for _ in range(k):
        candidates = list(range(len(valid)))
        cases = list(range(n_cases))
        random.shuffle(cases)
        
        while len(cases) > 0 and len(candidates) > 1:
            case_idx = cases[0]
            vals = [fitness_matrix[c, case_idx] for c in candidates]
            best_val = max(vals)
            # Keep individuals within epsilon of best (higher is better)
            candidates = [c for c, v in zip(candidates, vals) 
                         if v >= best_val - epsilons[case_idx]]
            del cases[0]
        
        selected_individuals.append(valid[random.choice(candidates)])
    
    return selected_individuals


def selLexi2Quantum(individuals, k, gen=None):
    """Lexi2 selection: epsilon-lexicase over the 8 output-state probabilities,
    with a circuit-size lexicographic tiebreak after the cases are exhausted.

    Cases: one per computational basis state (p(|000>), ..., p(|111>)) measured
    on the transpiled circuit, higher-is-better. Epsilon is computed per case
    per call (per generation) using the same MAD machinery as
    selEpsilonLexicaseQuantum (epsilon = MAD of the case values in the pool).

    Tiebreak (only when >1 survivor after all 8 cases): smallest transpiled
    2-qubit gate count, then total transpiled gate count, then transpiled
    depth (individual.lexi2_size, set by the evaluator). If still tied, pick
    randomly. No scalar coefficient / lambda anywhere.

    When `gen` is not None and the active selection method is 'lexi2', per-call
    statistics (epsilon vector, tiebreak-fire count, selections, post-case pool
    sizes) are accumulated in the module-level `lexi2_log[gen]` for Douglas's
    requested logging.
    """
    global lexi2_log
    valid = [ind for ind in individuals
             if hasattr(ind, 'fitness_each_sample')
             and ind.fitness_each_sample is not None
             and len(ind.fitness_each_sample) == 8]
    if not valid:
        return [random.choice(individuals) for _ in range(k)]

    fitness_matrix = np.array([ind.fitness_each_sample for ind in valid], dtype=float)

    # MAD-based epsilon per case (all 8), computed from the current pool.
    medians = np.median(fitness_matrix, axis=0)
    mad = np.median(np.abs(fitness_matrix - medians), axis=0)
    epsilons = mad

    sizes = np.array([getattr(ind, "lexi2_size", (999, 999, 999)) for ind in valid],
                     dtype=float)

    selected = []
    fires = 0
    post_case_pool_sizes = []
    for _ in range(k):
        candidates = list(range(len(valid)))
        cases = list(range(8))
        random.shuffle(cases)

        while len(cases) > 0 and len(candidates) > 1:
            case_idx = cases[0]
            vals = fitness_matrix[candidates, case_idx]
            best_val = float(vals.max())
            candidates = [c for c, v in zip(candidates, vals)
                          if v >= best_val - epsilons[case_idx]]
            del cases[0]

        if len(candidates) > 1:
            fires += 1
            post_case_pool_sizes.append(len(candidates))
            best_size = min(tuple(sizes[c]) for c in candidates)
            tied = [c for c in candidates if tuple(sizes[c]) == best_size]
            selected.append(valid[random.choice(tied)])
        else:
            selected.append(valid[candidates[0]])

    if gen is not None and SELECTION_METHOD == "lexi2":
        entry = lexi2_log.setdefault(int(gen), {
            "eps": [round(float(e), 6) for e in epsilons],
            "tiebreak_fires": 0,
            "selections": 0,
            "post_case_pool_sizes": [],
        })
        entry["tiebreak_fires"] += fires
        entry["selections"] += k
        entry["post_case_pool_sizes"].extend(post_case_pool_sizes)

    return selected

class TranspilationCache:
    """
    Caches transpiled circuits keyed by a hash of the QASM representation.
    
    Avoids re-transpiling identical circuits across generations (elites,
    clones, unchanged individuals). The cache is generation-aware and can
    be pruned to avoid unbounded memory growth.
    """
    def __init__(self, target, optimization_level=3, seed=None):
        self.target = target
        self.optimization_level = optimization_level
        self.seed = seed
        self._cache = {}  # hash -> (transpiled_circuit, gate_count, depth)
        self.hits = 0
        self.misses = 0
    
    def _hash_circuit(self, circuit):
        """Generate a deterministic hash for a quantum circuit."""
        try:
            qasm_str = qasm2.dumps(circuit)
        except Exception:
            # Fallback: use string representation
            qasm_str = str(circuit.data)
        return hashlib.sha256(qasm_str.encode()).hexdigest()
    
    def get_or_transpile(self, circuit):
        """
        Return cached transpiled circuit if available, otherwise transpile and cache.
        Returns: (transpiled_circuit, gate_count, depth)
        """
        h = self._hash_circuit(circuit)
        if h in self._cache:
            self.hits += 1
            return self._cache[h]
        
        self.misses += 1
        transpiled = transpile(
            circuit, 
            target=self.target,
            optimization_level=self.optimization_level,
            seed_transpiler=self.seed
        )
        result = (transpiled, transpiled.size(), transpiled.depth())
        self._cache[h] = result
        return result

    def prune(self, max_size=500):
        """Keep cache from growing unbounded."""
        if len(self._cache) > max_size:
            # Remove oldest entries (FIFO via dict ordering in Python 3.7+)
            excess = len(self._cache) - max_size
            keys_to_remove = list(self._cache.keys())[:excess]
            for k in keys_to_remove:
                del self._cache[k]
    
    def stats(self):
        total = self.hits + self.misses
        hit_rate = self.hits / total if total > 0 else 0
        return f"Cache: {len(self._cache)} entries, {self.hits} hits, {self.misses} misses ({hit_rate:.1%} hit rate)"

class EvolutionDiagnostics:
    """
    Tracks per-generation statistics for epsilon-lexicase analysis.
    
    Records:
    - Population fitness distribution per objective
    - MAD (epsilon) per objective
    - Number of unique behavior vectors
    - Timing per generation
    - Best/worst/mean per objective
    """
    def __init__(self, objective_names=None):
        self.objective_names = objective_names or ["fidelity", "gate_eff", "depth_eff"]
        self.records = []  # list of dicts, one per generation
        self.gen_start_time = None
        self.evolution_start_time = None
        self.evolution_end_time = None
    
    def start_evolution(self):
        self.evolution_start_time = time.time()
    
    def end_evolution(self):
        self.evolution_end_time = time.time()
    
    def start_generation(self):
        self.gen_start_time = time.time()
    
    def record_generation(self, generation, population):
        """Compute and store diagnostics for this generation."""
        gen_time = time.time() - self.gen_start_time if self.gen_start_time else 0
        
        # Collect fitness_each_sample from valid individuals
        valid = [ind for ind in population 
                 if hasattr(ind, 'fitness_each_sample') 
                 and ind.fitness_each_sample is not None
                 and not ind.invalid]
        
        n_valid = len(valid)
        n_invalid = len(population) - n_valid
        
        if n_valid == 0:
            self.records.append({
                "generation": generation,
                "n_valid": 0,
                "n_invalid": n_invalid,
                "gen_time_sec": round(gen_time, 2),
            })
            return
        
        # Build fitness matrix
        fitness_matrix = np.array([ind.fitness_each_sample for ind in valid])
        
        # Per-objective statistics
        record = {
            "generation": generation,
            "n_valid": n_valid,
            "n_invalid": n_invalid,
            "gen_time_sec": round(gen_time, 2),
        }
        
        for i, name in enumerate(self.objective_names):
            vals = fitness_matrix[:, i]
            median = np.median(vals)
            mad = np.median(np.abs(vals - median))
            
            record[f"{name}_min"] = round(float(np.min(vals)), 6)
            record[f"{name}_max"] = round(float(np.max(vals)), 6)
            record[f"{name}_mean"] = round(float(np.mean(vals)), 6)
            record[f"{name}_std"] = round(float(np.std(vals)), 6)
            record[f"{name}_median"] = round(float(median), 6)
            record[f"{name}_mad"] = round(float(mad), 6)  # This IS the epsilon
        
        # Unique behavior vectors (how diverse is the population?)
        unique_vectors = len(set(tuple(ind.fitness_each_sample) for ind in valid))
        record["unique_behaviors"] = unique_vectors
        record["behavior_diversity"] = round(unique_vectors / n_valid, 4)
        
        # Scalar fitness stats
        scalar_fits = [ind.fitness.values[0] for ind in valid if ind.fitness.valid]
        if scalar_fits:
            record["scalar_fitness_min"] = round(min(scalar_fits), 6)
            record["scalar_fitness_mean"] = round(np.mean(scalar_fits), 6)
        
        self.records.append(record)
    
    def print_generation_summary(self, generation):
        """Print a compact table for the current generation."""
        if not self.records or self.records[-1]["generation"] != generation:
            return
        r = self.records[-1]
        
        if r["n_valid"] == 0:
            print(f"  [Diagnostics] Gen {generation}: No valid individuals")
            return
        
        print(f"  [Diagnostics] Gen {generation} ({r['gen_time_sec']:.1f}s) | "
              f"Valid: {r['n_valid']} | Unique behaviors: {r['unique_behaviors']} "
              f"({r['behavior_diversity']:.1%})")
        
        for name in self.objective_names:
            print(f"    {name:>12s}: "
                  f"min={r[f'{name}_min']:.4f} "
                  f"mean={r[f'{name}_mean']:.4f} "
                  f"max={r[f'{name}_max']:.4f} "
                  f"MAD(epsilon)={r[f'{name}_mad']:.4f}")
    
    def to_dataframe(self):
        """Convert records to a pandas DataFrame."""
        return pd.DataFrame(self.records)
    
    def save_csv(self, path):
        """Save diagnostics to CSV."""
        df = self.to_dataframe()
        df.to_csv(path, index=False)
        print(f"\u2713 Diagnostics saved to: {path}")
        return df
    
    def get_system_info(self):
        """Capture system and package information."""
        info = {
            "machine": platform.machine(),
            "processor": platform.processor(),
            "system": platform.system(),
            "system_version": platform.version(),
            "python_version": platform.python_version(),
            "cpu_count": os.cpu_count(),
        }
        
        # Try to get macOS-specific info
        if platform.system() == "Darwin":
            try:
                import subprocess
                chip = subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"], 
                                               text=True).strip()
                info["chip"] = chip
            except Exception:
                info["chip"] = platform.processor()
            try:
                import subprocess
                mem = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True).strip()
                info["ram_gb"] = round(int(mem) / (1024**3), 1)
            except Exception:
                pass
        
        # Package versions
        for pkg in ["qiskit", "qiskit-aer", "qiskit-ibm-runtime", "deap", "numpy"]:
            try:
                info[f"pkg_{pkg}"] = pkg_version(pkg)
            except Exception:
                info[f"pkg_{pkg}"] = "unknown"
        
        # GRAPE version
        try:
            import grape
            info["pkg_grape"] = getattr(grape, "__version__", "dev")
        except Exception:
            info["pkg_grape"] = "unknown"
        
        return info
    
    def save_run_metadata(self, path, config=None):
        """Save complete run metadata: system info, config, timing."""
        metadata = {
            "system": self.get_system_info(),
            "timing": {
                "evolution_start": self.evolution_start_time,
                "evolution_end": self.evolution_end_time,
                "total_seconds": round(self.evolution_end_time - self.evolution_start_time, 2) if self.evolution_end_time else None,
                "total_minutes": round((self.evolution_end_time - self.evolution_start_time) / 60, 2) if self.evolution_end_time else None,
                "avg_gen_seconds": round(np.mean([r["gen_time_sec"] for r in self.records if "gen_time_sec" in r]), 2) if self.records else None,
            },
            "config": config or {},
            "timestamp": datetime.now().isoformat(),
        }
        
        with open(path, "w") as f:
            json.dump(metadata, f, indent=2)
        print(f"\u2713 Run metadata saved to: {path}")
        return metadata

def generate_oracle_for_state(marked_state: str) -> str:
    """Generate Grover oracle code for a given marked state."""
    n = len(marked_state)
    code_lines = []
    for i, bit in enumerate(marked_state):
        if bit == '0':
            code_lines.append(f"qc.x({i})")
    code_lines.append(f"qc.h({n-1})")
    code_lines.append(f"qc.mcx(list(range({n-1})), {n-1})")
    code_lines.append(f"qc.h({n-1})")
    for i, bit in enumerate(marked_state):
        if bit == '0':
            code_lines.append(f"qc.x({i})")
    return "\n".join(code_lines) + "\n"

class CircuitEvaluator:
    def __init__(self, shots: int = NUM_SHOTS, log_dir: str = None, seed: int = None, use_noise: bool = USE_NOISE_MODEL):
        self.shots = shots
        self.seed = seed if seed is not None else RANDOM_SEED
        self.use_noise = use_noise
        self.log_dir = log_dir
        if self.log_dir:
            os.makedirs(self.log_dir, exist_ok=True)
    
    def decode_individual(self, ind) -> str:
        if ind.invalid or not hasattr(ind, 'phenotype'):
            return None
        try:
            if isinstance(ind.phenotype, list):
                code = ''.join(ind.phenotype)
            else:
                code = ind.phenotype
            code = code.replace('"', '')
            code = code.replace('\\n', '\n')
            match = re.search(r'qc\s*=\s*QuantumCircuit\((\d+),\s*(\d+)\)', code)
            if match:
                n_qubits = match.group(1)
                n_clbits = match.group(2)
                old_init = match.group(0)
                new_init = f"qr = QuantumRegister({n_qubits}, name='q')\ncr = ClassicalRegister({n_clbits}, name='cr')\nqc = QuantumCircuit(qr, cr)"
                code = code.replace(old_init, new_init, 1)
            code = '\n'.join(line.lstrip() for line in code.split('\n'))
            return code
        except Exception as ex:
            print(f"[Decode Error] {ex}")
            return None
    
    def execute_circuit(self, phenotype_code: str) -> QuantumCircuit:
        local_vars = {}
        try:
            exec(phenotype_code, globals(), local_vars)
            if "qc" in local_vars:
                return local_vars["qc"]
            else:
                return None
        except Exception as e:
            return None
    
    def simulate_circuit(self, circuit: QuantumCircuit, marked_state: str, individual_seed: int = None) -> dict:
        """Simulate a circuit with optional noise model and transpilation cache."""
        sim_seed = individual_seed if individual_seed is not None else self.seed
        try:
            if self.use_noise:
                # Use transpilation cache for noise-aware path
                if transpile_cache is not None:
                    transpiled, gate_count, depth = transpile_cache.get_or_transpile(circuit)
                else:
                    transpiled = transpile(circuit, target=transpile_target(),
                                           optimization_level=3,
                                           seed_transpiler=sim_seed)
                    gate_count = transpiled.size()
                    depth = transpiled.depth()
                
                simulator = noise_model_sim
                circuit_to_run = transpiled
                sim_type = "noise"
            else:
                simulator = ideal_sim
                circuit_to_run = circuit
                gate_count = circuit.size()
                depth = circuit.depth()
                sim_type = "ideal"

            # Transpiled 2Q count on the SAME circuit the fitness loop scores
            # (used by Lexi2's size tiebreak and the deployment rule).
            two_qubit_gates = sum(
                1 for inst in circuit_to_run.data if inst.operation.num_qubits >= 2)
            
            # Simulate with per-individual seed (preserves reproducibility)
            result = simulator.run(circuit_to_run, shots=self.shots, seed_simulator=sim_seed).result()
            
            counts = result.get_counts()
            corrected = {k[::-1]: v for k, v in counts.items()}
            total = sum(corrected.values())
            p_marked = corrected.get(marked_state, 0) / total if total > 0 else 0.0
            error = 1 - p_marked
            
            return {
                "counts": corrected,
                "p_marked": p_marked,
                "error": error,
                "gate_count": gate_count,
                "depth": depth,
                "two_qubit_gates": two_qubit_gates,
                "sim_type": sim_type
            }
        except Exception as e:
            print(f"[Simulation Error] {e}")
            return {
                "counts": {},
                "p_marked": 0.0,
                "error": 1.0,
                "gate_count": 999,
                "depth": 999,
                "two_qubit_gates": 999,
                "sim_type": "error"
            }
    
    def log_evaluation(self, logs: list, generation: int, individual) -> None:
        id_hash = stable_genome_hash(individual.genome) % 10**8
        log_file_json = os.path.join(self.log_dir, f"eval_gen{generation}_id{id_hash}.json")
        log_file_csv = os.path.join(self.log_dir, f"eval_gen{generation}_id{id_hash}.csv")
        for log_entry in logs:
            log_entry['noise_model_used'] = self.use_noise
            log_entry['selection_method'] = SELECTION_METHOD
        with open(log_file_json, "w") as f:
            json.dump(logs, f, indent=2)
        df = pd.DataFrame(logs)
        df[["state", "p_marked", "error", "gate_count", "depth", "noise_model_used", "selection_method"]].to_csv(log_file_csv, index=False)

def inject_oracle(phenotype_str: str, oracle_code: str) -> str:
    pattern = r"(## Begin Oracle\n)(.*?)(## End Oracle\n)"
    new_block = r"\1" + oracle_code + r"\3"
    return re.sub(pattern, new_block, phenotype_str, flags=re.DOTALL)

def fitness_function_qiskit(
    phenotype_str,
    shots=NUM_SHOTS,
    threshold=SUCCESS_THRESHOLD,
    gate_penalty_weight=GATE_PENALTY_WEIGHT,
    target_state=TARGET_STATE,
    log_states=True,
    individual_seed=None,
    use_noise=USE_NOISE_MODEL,
):
    """
    Evaluate a quantum circuit phenotype.
    
    Returns:
        If log_states=True:  (scalar_fitness, logs, per_case_scores)
        If log_states=False: scalar_fitness
        
    per_case_scores is a dict with raw values for lexicase:
        {"p_marked": float, "gate_count": int, "depth": int}
    """
    if not isinstance(phenotype_str, str):
        if log_states:
            return (float('inf'), [], {"p_marked": 0.0, "gate_count": 999, "depth": 999})
        return float('inf')
    
    evaluator = CircuitEvaluator(shots=shots, seed=individual_seed, use_noise=use_noise)
    logs = []
    
    oracle_code = generate_oracle_for_state(target_state)
    modified_code = inject_oracle(phenotype_str, oracle_code)
    qc = evaluator.execute_circuit(modified_code)
    if qc is None:
        if log_states:
            return (float('inf'), [], {"p_marked": 0.0, "gate_count": 999, "depth": 999})
        return float('inf')
    
    result = evaluator.simulate_circuit(qc, target_state, individual_seed=individual_seed)
    
    p_marked = result["p_marked"]
    error = 1 - p_marked
    miss = 1 if p_marked < threshold else 0
    gate_count = result.get("gate_count", 0)
    depth = result.get("depth", 0)
    
    # Scalar fitness (used for HOF ranking and tournament mode)
    fitness_score = 10 * miss + error + gate_penalty_weight * gate_count
    
    # Per-case raw scores (used by lexicase to build fitness_each_sample)
    per_case_scores = {
        "p_marked": p_marked,
        "gate_count": gate_count,
        "depth": depth,
        "two_qubit_gates": result.get("two_qubit_gates", 0),
        # Lexi2 cases: measured probability of every 3-bit computational
        # basis state on the transpiled circuit (higher = better).
        "probabilities": [
            round(counts.get(s, 0) / total, 6) for s in ALL_STATES
        ] if (counts := result.get("counts")) and (total := sum(counts.values())) > 0
        else [0.0] * 8,
    }
    
    if log_states:
        logs.append({
            "state": target_state,
            "p_marked": p_marked,
            "error": error,
            "gate_count": gate_count,
            "depth": depth,
            "oracle": oracle_code,
            "code": modified_code,
            "counts": result["counts"],
            "sim_type": result.get("sim_type", "unknown"),
        })
        return (fitness_score, logs, per_case_scores)
    else:
        return fitness_score

class EarlyStoppingMonitor:
    def __init__(self, 
                 patience_dict: Dict[str, int],
                 min_delta_dict: Dict[str, float],
                 weights_dict: Dict[str, float],
                 strategy: str = "any",
                 window_size: int = 3,
                 use_relative: bool = True,
                 min_generations: int = 10,
                 verbose: bool = True):
        
        self.patience = patience_dict
        self.min_delta = min_delta_dict
        self.weights = weights_dict
        self.strategy = strategy
        self.window_size = window_size
        self.use_relative = use_relative
        self.min_generations = min_generations
        self.verbose = verbose
        
        self.history = {
            'fitness': deque(maxlen=100),
            'fidelity': deque(maxlen=100),
            'gate_count': deque(maxlen=100),
            'depth': deque(maxlen=100),
            'composite': deque(maxlen=100)
        }
        
        self.best_values = {
            'fitness': float('inf'),
            'fidelity': 0.0,
            'gate_count': float('inf'),
            'depth': float('inf'),
            'composite': float('inf')
        }
        
        self.patience_counters = {
            'fitness': 0,
            'fidelity': 0,
            'gate_count': 0,
            'depth': 0,
            'composite': 0
        }
        
        self.generations_since_improvement = {
            'fitness': 0,
            'fidelity': 0,
            'gate_count': 0,
            'depth': 0,
            'composite': 0
        }
        
        self.fidelity_achieved_generation = None
        self.phase = "fidelity_search"
        self.current_generation = 0
        self.stop_triggered = False
        self.stop_reason = None
        self.metrics_at_stop = None
    
    def calculate_composite_score(self, metrics: Dict[str, float]) -> float:
        normalized = {}
        normalized['fitness'] = max(0, metrics.get('fitness', float('inf')))
        normalized['fidelity'] = 1.0 - metrics.get('fidelity', 0.0)
        normalized['gate_count'] = metrics.get('gate_count', 100) / 100.0
        normalized['depth'] = metrics.get('depth', 50) / 50.0
        
        composite = (
            self.weights['fitness'] * normalized['fitness'] +
            self.weights['fidelity'] * normalized['fidelity'] +
            self.weights['gate_count'] * normalized['gate_count'] +
            self.weights['depth'] * normalized['depth']
        )
        return composite
    
    def get_moving_average(self, metric_name: str) -> Optional[float]:
        if len(self.history[metric_name]) < self.window_size:
            return None
        recent_values = list(self.history[metric_name])[-self.window_size:]
        return np.mean(recent_values)
    
    def check_improvement(self, current_value: float, best_value: float, 
                         metric_name: str) -> bool:
        minimize_metrics = ['fitness', 'gate_count', 'depth', 'composite']
        maximize_metrics = ['fidelity']
        
        if self.use_relative and metric_name in ['fitness', 'fidelity']:
            if metric_name in minimize_metrics:
                if best_value == 0:
                    improvement = current_value < best_value
                else:
                    relative_change = (best_value - current_value) / abs(best_value)
                    improvement = relative_change > self.min_delta[metric_name]
            else:
                if best_value == 0:
                    improvement = current_value > best_value
                else:
                    relative_change = (current_value - best_value) / abs(best_value)
                    improvement = relative_change > self.min_delta[metric_name]
        else:
            if metric_name in minimize_metrics:
                improvement = current_value < (best_value - self.min_delta.get(metric_name, 0))
            else:
                improvement = current_value > (best_value + self.min_delta.get(metric_name, 0))
        
        return improvement
    
    def update(self, generation: int, metrics: Dict[str, float]) -> None:
        self.current_generation = generation
        composite_score = self.calculate_composite_score(metrics)
        metrics['composite'] = composite_score
        
        for metric_name in ['fitness', 'fidelity', 'gate_count', 'depth', 'composite']:
            if metric_name in metrics:
                self.history[metric_name].append(metrics[metric_name])
        
        if (self.fidelity_achieved_generation is None and 
            'fidelity' in metrics and 
            metrics['fidelity'] >= FIDELITY_SUCCESS_THRESHOLD):
            self.fidelity_achieved_generation = generation
            self.phase = "hardware_optimization"
            if self.verbose:
                print(f"   FIDELITY TARGET ACHIEVED at generation {generation}!")
        
        improvements = {}
        for metric_name in ['fitness', 'fidelity', 'gate_count', 'depth', 'composite']:
            if metric_name not in metrics:
                continue
                
            current_value = metrics[metric_name]
            avg_value = self.get_moving_average(metric_name)
            if avg_value is not None:
                current_value = avg_value
            
            improved = self.check_improvement(
                current_value, 
                self.best_values[metric_name], 
                metric_name
            )
            
            improvements[metric_name] = improved
            
            if improved:
                self.best_values[metric_name] = current_value
                self.patience_counters[metric_name] = 0
                self.generations_since_improvement[metric_name] = 0
                
                if self.verbose:
                    if metric_name == 'fidelity':
                        print(f"  ✓ {metric_name} improved to {current_value:.4f}")
                    elif metric_name in ['gate_count', 'depth']:
                        print(f"  ✓ {metric_name} improved to {int(current_value)}")
            else:
                self.patience_counters[metric_name] += 1
                self.generations_since_improvement[metric_name] += 1
        
        if self.verbose and generation % 5 == 0:
            self.print_nisq_status()
    
    def should_stop(self) -> Tuple[bool, Optional[str]]:
        if self.current_generation < self.min_generations:
            return False, None
        
        if self.strategy == "nisq_hierarchical":
            current_fidelity = self.history['fidelity'][-1] if self.history['fidelity'] else 0
            current_gates = self.history['gate_count'][-1] if self.history['gate_count'] else float('inf')
            current_depth = self.history['depth'][-1] if self.history['depth'] else float('inf')

            # Option (a): never stop non-converged runs on patience/stagnation.
            # Only runs that reach ALL hardware targets (fidelity >= 0.95,
            # gates <= 20, depth <= 15) may stop early, once the
            # hardware-optimization patience has elapsed. Non-converged runs
            # run the full generation budget and end 'completed_all_generations'.
            if current_fidelity < FIDELITY_SUCCESS_THRESHOLD:
                return False, None

            gates_at_target = current_gates <= GATE_COUNT_TARGET
            depth_at_target = current_depth <= DEPTH_TARGET
            gates_stagnant = self.patience_counters['gate_count'] >= self.patience.get('gate_count', float('inf'))
            depth_stagnant = self.patience_counters['depth'] >= self.patience.get('depth', float('inf'))

            if gates_at_target and depth_at_target:
                if gates_stagnant or depth_stagnant:
                    return True, f"Hardware targets achieved: fidelity={current_fidelity:.3f}, gates={int(current_gates)}, depth={int(current_depth)}"

            return False, None
        
        elif self.strategy == "any":
            for metric_name in ['fitness', 'fidelity', 'gate_count', 'composite']:
                if metric_name in self.patience_counters:
                    if self.patience_counters[metric_name] >= self.patience.get(metric_name, float('inf')):
                        current_value = self.history[metric_name][-1] if self.history[metric_name] else 'N/A'
                        reason = f"{metric_name} hasn't improved for {self.patience_counters[metric_name]} generations"
                        return True, reason
        
        return False, None
    
    def print_nisq_status(self) -> None:
        print(f"\n  Early Stopping Status (Gen {self.current_generation}) - Phase: {self.phase.upper()}")
        current_fidelity = self.history['fidelity'][-1] if self.history['fidelity'] else 0
        current_gates = self.history['gate_count'][-1] if self.history['gate_count'] else float('inf')
        current_depth = self.history['depth'][-1] if self.history['depth'] else float('inf')
        
        fidelity_status = "✓" if current_fidelity >= FIDELITY_SUCCESS_THRESHOLD else "✗"
        gates_status = "✓" if current_gates <= GATE_COUNT_TARGET else "✗"
        depth_status = "✓" if current_depth <= DEPTH_TARGET else "✗"
        
        print(f"  {'Metric':<12} {'Current':<10} {'Best':<10} {'Target':<10} {'Status':<6} {'Patience':<10}")
        print(f"  {'-'*68}")
        
        patience_str = f"{self.patience_counters['fidelity']}/{self.patience.get('fidelity', '∞')}"
        print(f"  {'Fidelity':<12} {current_fidelity:<10.4f} {self.best_values['fidelity']:<10.4f} "
              f"{FIDELITY_SUCCESS_THRESHOLD:<10.2f} {fidelity_status:<6} {patience_str:<10}")
        
        patience_str = f"{self.patience_counters['gate_count']}/{self.patience.get('gate_count', '∞')}"
        print(f"  {'Gates':<12} {int(current_gates):<10} {int(self.best_values['gate_count']):<10} "
              f"≤{GATE_COUNT_TARGET:<9} {gates_status:<6} {patience_str:<10}")
        
        patience_str = f"{self.patience_counters.get('depth', 0)}/{self.patience.get('depth', '∞')}"
        print(f"  {'Depth':<12} {int(current_depth):<10} {int(self.best_values['depth']):<10} "
              f"≤{DEPTH_TARGET:<9} {depth_status:<6} {patience_str:<10}")
    
    def get_state(self) -> Dict:
        return {
            'history': {k: list(v) for k, v in self.history.items()},
            'best_values': self.best_values.copy(),
            'patience_counters': self.patience_counters.copy(),
            'generations_since_improvement': self.generations_since_improvement.copy(),
            'current_generation': self.current_generation,
            'stop_triggered': self.stop_triggered,
            'stop_reason': self.stop_reason,
            'metrics_at_stop': self.metrics_at_stop,
            'fidelity_achieved_generation': self.fidelity_achieved_generation,
            'phase': self.phase
        }
    
    def load_state(self, state: Dict) -> None:
        self.history = {k: deque(v, maxlen=100) for k, v in state['history'].items()}
        self.best_values = state['best_values']
        self.patience_counters = state['patience_counters']
        self.generations_since_improvement = state['generations_since_improvement']
        self.current_generation = state['current_generation']
        self.stop_triggered = state.get('stop_triggered', False)
        self.stop_reason = state.get('stop_reason', None)
        self.metrics_at_stop = state.get('metrics_at_stop', None)
        self.fidelity_achieved_generation = state.get('fidelity_achieved_generation', None)
        self.phase = state.get('phase', 'fidelity_search')

def create_early_stopping_monitor():
    if not USE_EARLY_STOPPING:
        return None
    
    return EarlyStoppingMonitor(
        patience_dict=EARLY_STOPPING_PATIENCE,
        min_delta_dict=MIN_IMPROVEMENT_DELTA,
        weights_dict=METRIC_WEIGHTS,
        strategy=EARLY_STOPPING_STRATEGY,
        window_size=MOVING_AVERAGE_WINDOW,
        use_relative=USE_RELATIVE_IMPROVEMENT,
        min_generations=MIN_GENERATIONS_BEFORE_STOPPING,
        verbose=EARLY_STOPPING_VERBOSE
    )

def save_checkpoint(population, generation, hof, best_fitness_list, avg_gate_count_list, 
                    generations_list, early_stopping_monitor=None, checkpoint_path=CHECKPOINT_PATH,
                    fidelity_history=None, depth_history=None, diagnostics=None):
    """Save checkpoint with early stopping monitor state."""
    checkpoint_data = {
        'population': population,
        'generation': generation,
        'hof': hof,
        'best_fitness_list': best_fitness_list,
        'avg_gate_count_list': avg_gate_count_list,
        'generations_list': generations_list,
        'fidelity_history': list(fidelity_history) if fidelity_history is not None else None,
        'depth_history': list(depth_history) if depth_history is not None else None,
        'diagnostics_records': list(diagnostics.records) if diagnostics is not None else None,
        'random_state': random.getstate(),
        'numpy_state': np.random.get_state(),
        'timestamp': datetime.now().isoformat(),
        'noise_model_used': USE_NOISE_MODEL,
        'random_seed': RANDOM_SEED,
        'early_stopping_state': early_stopping_monitor.get_state() if early_stopping_monitor else None
    }
    
    # Save generation-stamped snapshot
    gen_path = os.path.join(CHECKPOINT_DIR, f"checkpoint_gen_{generation}.pkl")
    try:
        with open(gen_path, 'wb') as f:
            pickle.dump(checkpoint_data, f)
        with open(checkpoint_path, 'wb') as f:
            pickle.dump(checkpoint_data, f)
        print(f"✓ Checkpoint saved: {gen_path}")
        print(f"✓ Latest updated:   {checkpoint_path}")
    except Exception as e:
        print(f"Warning: Could not save checkpoint: {e}")

def load_checkpoint(checkpoint_path=CHECKPOINT_PATH):
    """Load checkpoint and restore RNG states if resuming."""
    try:
        with open(checkpoint_path, 'rb') as f:
            checkpoint_data = pickle.load(f)
        
        # Only restore RNG states if resuming (not transferring)
        if RESUME_FROM_CHECKPOINT:
            random.setstate(checkpoint_data['random_state'])
            np.random.set_state(checkpoint_data['numpy_state'])
            
        print(f"✓ Checkpoint loaded (gen {checkpoint_data['generation']}) from {checkpoint_path}")
        
        if 'noise_model_used' in checkpoint_data and checkpoint_data['noise_model_used'] != USE_NOISE_MODEL:
            print(f"  ⚠ Warning: Checkpoint noise_model={checkpoint_data['noise_model_used']} vs current={USE_NOISE_MODEL}")
        
        return checkpoint_data
    except Exception as e:
        print(f"Could not load checkpoint from {checkpoint_path}: {e}")
        return None

def load_transfer_population(source_checkpoint_path, transfer_ratio=0.3, mutation_boost=0.3):
    """Load and adapt population from source checkpoint for transfer learning."""
    try:
        print(f"\n{'='*60}")
        print(f"TRANSFER LEARNING")
        print(f"{'='*60}")
        print(f"Source checkpoint: {source_checkpoint_path}")
        print(f"Transfer ratio: {transfer_ratio*100:.1f}%")
        print(f"Mutation boost: {mutation_boost*100:.1f}%")
        
        with open(source_checkpoint_path, 'rb') as f:
            source_data = pickle.load(f)
        
        source_population = source_data['population']
        source_generation = source_data['generation']
        source_fitness = [ind.fitness.values[0] if ind.fitness.valid else float('inf') 
                         for ind in source_population]
        
        print(f"Source population: {len(source_population)} individuals from generation {source_generation}")
        print(f"Source best fitness: {min(source_fitness):.4f}")
        
        n_transfer = max(1, int(POPULATION_SIZE * transfer_ratio))
        n_mutated = max(1, int(POPULATION_SIZE * mutation_boost))
        n_random = max(1, POPULATION_SIZE - n_transfer - n_mutated)
        
        print(f"Transfer plan: {n_transfer} direct + {n_mutated} mutated + {n_random} random = {POPULATION_SIZE} total")
        
        valid_individuals = [(fit, ind) for fit, ind in zip(source_fitness, source_population) 
                           if fit != float('inf')]
        
        if not valid_individuals:
            print("No valid individuals in source population - using random initialization")
            return None
            
        valid_individuals.sort(key=lambda x: x[0])
        best_source = [ind for _, ind in valid_individuals[:n_transfer]]
        
        print(f"Selected {len(best_source)} best individuals from source")
        
        new_population = []
        
        # Transfer best individuals directly
        for source_ind in best_source:
            try:
                new_ind = creator.Individual(
                    genome=source_ind.genome.copy(),
                    grammar=BNF_GRAMMAR,
                    max_depth=MAX_TREE_DEPTH,
                    codon_consumption=CODON_CONSUMPTION
                )
                
                if hasattr(source_ind, 'phenotype'):
                    new_ind.phenotype = source_ind.phenotype
                new_ind.invalid = False
                new_ind.fitness = creator.FitnessMin()
                new_population.append(new_ind)
                
            except Exception as e:
                print(f"Warning: Could not transfer individual: {e}")
        
        print(f"✓ Transferred {len(new_population)} individuals directly")
        
        # Create mutated versions
        mutation_pool = best_source[:min(len(best_source), n_mutated)]
        for i in range(n_mutated):
            source_ind = mutation_pool[i % len(mutation_pool)]
            
            try:
                new_ind = creator.Individual(
                    genome=source_ind.genome.copy(),
                    grammar=BNF_GRAMMAR,
                    max_depth=MAX_TREE_DEPTH,
                    codon_consumption=CODON_CONSUMPTION
                )
                
                if hasattr(source_ind, 'phenotype'):
                    new_ind.phenotype = source_ind.phenotype
                new_ind.invalid = False
                new_ind.fitness = creator.FitnessMin()
                
                grape.mutation_int_flip_per_codon(
                    new_ind,
                    mut_probability=P_MUTATION,
                    codon_size=CODON_SIZE,
                    bnf_grammar=BNF_GRAMMAR,
                    max_depth=MAX_TREE_DEPTH,
                    codon_consumption=CODON_CONSUMPTION
                )
                new_ind.fitness = creator.FitnessMin()
                new_population.append(new_ind)
                
            except Exception as e:
                print(f"Warning: Could not create mutated individual: {e}")
        
        print(f"✓ Created {n_mutated} mutated variants")
        
        # Fill remainder with random individuals
        if n_random > 0:
            random_pop = toolbox.populationCreator(
                pop_size=n_random,
                bnf_grammar=BNF_GRAMMAR,
                min_init_depth=MIN_INIT_DEPTH,
                max_init_depth=MAX_INIT_DEPTH,
                codon_size=CODON_SIZE,
                codon_consumption=CODON_CONSUMPTION,
                genome_representation=GENOME_REPRESENTATION
            )
            new_population.extend(random_pop)
            
            print(f"✓ Added {len(random_pop)} random individuals")
        
        print(f"✓ Transfer learning complete: {len(new_population)} individuals ready")
        print(f"{'='*60}")
        
        return new_population
        
    except Exception as e:
        print(f"✗ Transfer learning failed: {e}")
        print(f"{'='*60}")
        return None

def evaluate_with_logging(individual, pts_train=None):
    """
    Evaluation function with deterministic seeding.
    
    Sets `individual.fitness_each_sample` for lexicase selection:
        [0] fidelity       — p_marked (higher = better)
        [1] gate_efficiency — 1 - gate_count/MAX (higher = better)
        [2] depth_efficiency — 1 - depth/MAX (higher = better)
    
    Returns scalar fitness tuple for DEAP compatibility (HOF, elitism).
    """
    global eval_counter
    
    genome_hash = stable_genome_hash(individual.genome) if hasattr(individual, 'genome') else stable_genome_hash(str(individual))
    individual_seed = (RANDOM_SEED + genome_hash) % (2**32)
    
    evaluator = CircuitEvaluator(shots=NUM_SHOTS, log_dir=LOG_DIR, seed=individual_seed, use_noise=USE_NOISE_MODEL)
    phenotype_str = evaluator.decode_individual(individual)
    if not phenotype_str:
        # Invalid individual — worst possible scores
        if SELECTION_METHOD == "lexi2":
            individual.fitness_each_sample = [0.0] * 8
            individual.lexi2_size = (999, 999, 999)
        else:
            individual.fitness_each_sample = [0.0, 0.0, 0.0]
        return (float('inf'),)
    
    fitness_val, logs, per_case = fitness_function_qiskit(
        phenotype_str, 
        shots=NUM_SHOTS, 
        threshold=SUCCESS_THRESHOLD, 
        gate_penalty_weight=GATE_PENALTY_WEIGHT,
        target_state=TARGET_STATE, 
        log_states=True,
        individual_seed=individual_seed,
        use_noise=USE_NOISE_MODEL,
    )
    
    if SELECTION_METHOD == "lexi2":
        # Lexi2: 8 cases = measured probabilities of the 8 output states.
        individual.fitness_each_sample = list(per_case["probabilities"])
        # Size tiebreak metrics on the scored (transpiled) circuit:
        # (2Q count, total gates, depth) — smaller is better.
        individual.lexi2_size = (
            per_case["two_qubit_gates"],
            per_case["gate_count"],
            per_case["depth"],
        )
    else:
        # Build per-case fitness vector for (epsilon-)lexicase (all higher-is-better)
        fidelity = per_case["p_marked"]  # [0, 1], higher = better
        gate_eff = max(0.0, 1.0 - per_case["gate_count"] / MAX_EXPECTED_GATES)  # [0, 1]
        depth_eff = max(0.0, 1.0 - per_case["depth"] / MAX_EXPECTED_DEPTH)      # [0, 1]
        individual.fitness_each_sample = [
            round(fidelity, 6),
            round(gate_eff, 6),
            round(depth_eff, 6),
        ]
    
    gen = getattr(individual, "generation", "unknown")
    evaluator.log_evaluation(logs, gen, individual)
    eval_counter += 1
    return (fitness_val,)

def setup_toolbox(num_workers: int, selection_method: str):
    """Create DEAP types + toolbox (notebook cell 35 logic) with a worker pool.

    Fork-based multiprocessing on POSIX so workers inherit the module globals
    (RANDOM_SEED, LOG_DIR, TARGET_STATE, transpile_cache, simulators) set in the
    parent before the pool is created -- identical semantics to the notebook.
    """
    global toolbox, pool, evaluator, eval_counter, SELECTION_METHOD

    SELECTION_METHOD = selection_method
    if selection_method == "per_prob":
        raise NotImplementedError(
            f"selection arm {selection_method!r} is not implemented yet; "
            f"use 'epsilon_lexicase', 'tournament', or 'lexi2'."
        )

    # Create DEAP types
    creator.create("FitnessMin", base.Fitness, weights=(-1.0,))
    creator.create("Individual", grape.Individual, fitness=creator.FitnessMin)

    # Setup toolbox
    toolbox = base.Toolbox()
    toolbox.register(
        "populationCreator",
        grape.sensible_initialisation,
        creator.Individual,
        bnf_grammar=BNF_GRAMMAR,
        min_init_depth=MIN_INIT_DEPTH,
        max_init_depth=MAX_INIT_DEPTH,
        codon_size=CODON_SIZE,
        codon_consumption=CODON_CONSUMPTION,
        genome_representation=GENOME_REPRESENTATION,
    )
    toolbox.register("mate", grape.crossover_onepoint)
    toolbox.register("mutate", grape.mutation_int_flip_per_codon)

    # === SELECTION METHOD ===
    if SELECTION_METHOD == "lexicase":
        toolbox.register("select", selLexicaseQuantum)
        print(f"✓ Selection: Lexicase (3 test cases: fidelity, gate_eff, depth_eff)")
    elif SELECTION_METHOD == "epsilon_lexicase":
        toolbox.register("select", selEpsilonLexicaseQuantum)
        print(f"✓ Selection: Epsilon-Lexicase (MAD-based thresholds)")
    elif SELECTION_METHOD == "lexi2":
        toolbox.register("select", selLexi2Quantum)
        print(f"✓ Selection: Lexi2 (8-case epsilon-lexicase on output-state "
              f"probabilities + 2Q/gates/depth tiebreak)")
    else:
        toolbox.register("select", tools.selTournament, tournsize=TOURNAMENT_SIZE)
        print(f"✓ Selection: Tournament (size {TOURNAMENT_SIZE})")

    # Setup multiprocessing
    if "fork" in multiprocessing.get_all_start_methods():
        try:
            multiprocessing.set_start_method("fork", force=True)
        except RuntimeError:
            pass
    pool = multiprocessing.Pool(num_workers)
    toolbox.register("map", pool.map)

    # Setup evaluation
    evaluator = CircuitEvaluator(shots=NUM_SHOTS, log_dir=None)
    eval_counter = 0
    toolbox.register("evaluate", evaluate_with_logging)

    setup_stats()


def setup_stats():
    """Setup statistics (notebook cell 37)."""
    global stats
    stats = tools.Statistics(lambda ind: ind.fitness.values)
    stats.register("avg", np.mean)
    stats.register("std", np.std)
    stats.register("min", np.min)
    stats.register("max", np.max)

# === MULTI-RUN EXPERIMENT WRAPPER ===
# Runs one complete GE evolution for a given (seed, target_state) and returns
# a result dict. Re-creates DEAP state, diagnostics, cache, and early-stopping
# monitor per run so the runs are truly independent and reproducible.

import copy as _copy
import matplotlib.pyplot as _plt

def run_evolution_experiment(run_id, seed, target_state, selection_method=None):
    """One full evolution. Returns a result dict with best circuit + histories."""
    global RANDOM_SEED, LOG_DIR, CHECKPOINT_DIR, CHECKPOINT_PATH, TARGET_STATE
    global SELECTION_METHOD, transpile_cache, diagnostics, toolbox, evaluator, pool

    # ---- Override module-level state that existing functions read ----
    RANDOM_SEED = seed
    TARGET_STATE = target_state
    if selection_method is not None:
        SELECTION_METHOD = selection_method

    lexi2_log.clear()
    random.seed(seed)
    np.random.seed(seed)

    # ---- Per-run directories (state/selection/run/seed separated) ----
    exp_base = os.path.join(EXPERIMENTS_ROOT, SELECTION_METHOD, f"pop{POPULATION_SIZE}",
                            "noise" if USE_NOISE_MODEL else "ideal")
    state_dir = os.path.join(exp_base, f"state_{target_state}")
    run_log_dir = os.path.join(state_dir, f"run_{run_id}_seed_{seed}")
    run_ckpt_dir = os.path.join(run_log_dir, "checkpoints")
    os.makedirs(run_log_dir, exist_ok=True)
    os.makedirs(run_ckpt_dir, exist_ok=True)
    LOG_DIR = run_log_dir
    CHECKPOINT_DIR = run_ckpt_dir
    CHECKPOINT_PATH = os.path.join(run_ckpt_dir, "checkpoint_latest.pkl")

    print(f"\n{'='*60}")
    print(f"RUN {run_id}/{NUMBER_OF_RUNS} | State |{target_state}> | Seed {seed} | {SELECTION_METHOD}")
    print(f"Logging to: {run_log_dir}")
    print(f"{'='*60}")

    # ---- Fresh DEAP creator + toolbox (critical for independence) ----
    for attr in ["FitnessMin", "Individual"]:
        if hasattr(creator, attr):
            delattr(creator, attr)
    creator.create("FitnessMin", base.Fitness, weights=(-1.0,))
    creator.create("Individual", grape.Individual, fitness=creator.FitnessMin)

    toolbox = base.Toolbox()
    toolbox.register("populationCreator", grape.sensible_initialisation,
                     creator.Individual, bnf_grammar=BNF_GRAMMAR,
                     min_init_depth=MIN_INIT_DEPTH, max_init_depth=MAX_INIT_DEPTH,
                     codon_size=CODON_SIZE, codon_consumption=CODON_CONSUMPTION,
                     genome_representation=GENOME_REPRESENTATION)
    toolbox.register("mate", grape.crossover_onepoint)
    toolbox.register("mutate", grape.mutation_int_flip_per_codon)
    _current_gen = [0]
    if SELECTION_METHOD == "lexicase":
        toolbox.register("select", selLexicaseQuantum)
    elif SELECTION_METHOD == "epsilon_lexicase":
        toolbox.register("select", selEpsilonLexicaseQuantum)
    elif SELECTION_METHOD == "lexi2":
        toolbox.register("select", lambda inds, k, _g=_current_gen:
                         selLexi2Quantum(inds, k, gen=_g[0]))
    else:
        toolbox.register("select", tools.selTournament, tournsize=TOURNAMENT_SIZE)
    toolbox.register("map", pool.map)
    toolbox.register("evaluate", evaluate_with_logging)

    # ---- Fresh per-run diagnostics + cache + early stopping ----
    if SELECTION_METHOD == "lexi2":
        diag_names = ["p000", "p001", "p010", "p011",
                      "p100", "p101", "p110", "p111"]
    else:
        diag_names = ["fidelity", "gate_eff", "depth_eff"]
    diagnostics = EvolutionDiagnostics(objective_names=diag_names)
    if USE_NOISE_MODEL:
        transpile_cache = TranspilationCache(target=transpile_target(),
                                             optimization_level=3, seed=seed)
    else:
        transpile_cache = None
    early_stopping_monitor = create_early_stopping_monitor()

    evaluator = CircuitEvaluator(shots=NUM_SHOTS, log_dir=LOG_DIR, use_noise=USE_NOISE_MODEL)

    # ---- Fresh population + trackers ----
    population = toolbox.populationCreator(
        pop_size=POPULATION_SIZE, bnf_grammar=BNF_GRAMMAR,
        min_init_depth=MIN_INIT_DEPTH, max_init_depth=MAX_INIT_DEPTH,
        codon_size=CODON_SIZE, codon_consumption=CODON_CONSUMPTION,
        genome_representation=GENOME_REPRESENTATION)
    hof = tools.HallOfFame(HALLOFFAME_SIZE)

    # Initial-population genome hashes: paired-design evidence that all arms
    # share a byte-identical gen-0 population for the same (state, seed).
    with open(os.path.join(run_log_dir, "gen0_genome_hashes.json"), "w") as _f:
        json.dump({
            "target_state": target_state,
            "seed": seed,
            "selection_method": SELECTION_METHOD,
            "hashes": [stable_genome_hash(ind.genome) for ind in population],
        }, _f)

    generations_list, best_fitness_list, avg_gate_count_list = [], [], []
    fidelity_history, depth_history = [], []
    stopped_gen = MAX_GENERATIONS - 1
    stop_reason = 'completed_all_generations'

    # ---- Resume from checkpoint if one exists and this run is not complete ----
    start_gen = 0
    resume_marker = os.path.join(run_log_dir,
                                 f"run_result_{target_state}_run{run_id}.json")
    if (os.path.exists(CHECKPOINT_PATH)
            and not os.path.exists(resume_marker)):
        try:
            resume = load_checkpoint(CHECKPOINT_PATH)
            if resume is not None:
                population = resume['population']
                hof = resume['hof']
                best_fitness_list = list(resume.get('best_fitness_list', []))
                avg_gate_count_list = list(resume.get('avg_gate_count_list', []))
                generations_list = list(resume.get('generations_list', []))
                fidelity_history = list(resume.get('fidelity_history', []))
                depth_history = list(resume.get('depth_history', []))
                if resume.get('early_stopping_state') is not None:
                    early_stopping_monitor.load_state(resume['early_stopping_state'])
                if resume.get('diagnostics_records') is not None:
                    diagnostics.records = list(resume['diagnostics_records'])
                start_gen = int(resume['generation']) + 1
                print(f"  ▶ Resuming evolution from gen {start_gen} "
                      f"(checkpoint gen {resume['generation']}, "
                      f"{len(diagnostics.records)} recorded generations)")
        except Exception as resume_error:
            print(f"  ⚠ Checkpoint present but could not resume "
                  f"({resume_error}); starting fresh.")
            start_gen = 0

    diagnostics.start_evolution()
    for gen in range(start_gen, MAX_GENERATIONS):
        diagnostics.start_generation()
        random.seed(seed + gen)
        _current_gen[0] = gen

        population, logbook = algorithms.ge_eaSimpleWithElitism(
            population, toolbox, cxpb=P_CROSSOVER, mutpb=P_MUTATION, ngen=N_GEN,
            elite_size=ELITE_SIZE, bnf_grammar=BNF_GRAMMAR, codon_size=CODON_SIZE,
            max_tree_depth=MAX_TREE_DEPTH, codon_consumption=CODON_CONSUMPTION,
            report_items=['gen', 'invalid', 'avg', 'std', 'min', 'max'],
            genome_representation=GENOME_REPRESENTATION,
            stats=stats, halloffame=hof, verbose=False)

        best_ind = tools.selBest(population, 1)[0]
        best_ind.generation = gen
        best_phenotype = evaluator.decode_individual(best_ind)

        p_marked = avg_gate = avg_depth = 0.0
        fitness_val = float('inf')
        if best_phenotype is not None:
            gh = stable_genome_hash(best_ind.genome)
            iseed = (seed + gh) % (2**32)
            fitness_val, logs, per_case = fitness_function_qiskit(
                best_phenotype, shots=NUM_SHOTS, threshold=SUCCESS_THRESHOLD,
                gate_penalty_weight=GATE_PENALTY_WEIGHT, target_state=target_state,
                log_states=True, individual_seed=iseed, use_noise=USE_NOISE_MODEL)
            if logs:
                avg_gate = float(np.mean([l["gate_count"] for l in logs]))
                avg_depth = float(np.mean([l["depth"] for l in logs]))
                p_marked = logs[0]["p_marked"]

        best_fitness_list.append(fitness_val)
        avg_gate_count_list.append(avg_gate)
        fidelity_history.append(p_marked)
        depth_history.append(avg_depth)
        generations_list.append(gen)

        diagnostics.record_generation(gen, population)
        if gen % 10 == 0:
            print(f"  gen {gen:3d} | fit={fitness_val:.4f} | fid={p_marked:.4f} "
                  f"| gates={avg_gate:.0f} | depth={avg_depth:.0f}")

        # Draw best circuit at gen 0 and every 10 generations
        if best_phenotype is not None and (gen == 0 or (gen + 1) % 10 == 0):
            _qc = evaluator.execute_circuit(best_phenotype)
            if _qc is not None:
                print(f"\n[Gen {gen}] Best circuit (raw) | fid={p_marked:.4f} "
                      f"| gates={avg_gate:.0f} depth={avg_depth:.0f}")
                display(_qc.draw("mpl"))
                if USE_NOISE_MODEL:
                    try:
                        _t = transpile(_qc, target=transpile_target(), optimization_level=3,
                                       seed_transpiler=seed)
                        print(f"[Gen {gen}] Transpiled | gates={_t.size()} depth={_t.depth()}")
                        display(_t.draw("mpl", idle_wires=False))
                    except Exception as _e:
                        print(f"  [transpile draw skipped: {_e}]")

        # Early stopping check
        if USE_EARLY_STOPPING and early_stopping_monitor:
            early_stopping_monitor.update(gen, {'fitness': fitness_val, 'fidelity': p_marked,
                                                'gate_count': avg_gate, 'depth': avg_depth})
            should_stop, reason = early_stopping_monitor.should_stop()
            if should_stop:
                print(f"  Early stop at gen {gen}: {reason}")
                early_stopping_monitor.stop_triggered = True
                early_stopping_monitor.stop_reason = reason
                stopped_gen = gen
                stop_reason = reason
                break

        # Prune transpile cache periodically
        if USE_NOISE_MODEL and transpile_cache is not None and (gen + 1) % 10 == 0:
            transpile_cache.prune(max_size=500)

        # Periodic checkpoint (explicit path per run; enables crash recovery)
        if (gen + 1) % CHECKPOINT_FREQUENCY == 0:
            save_checkpoint(population, gen, hof, best_fitness_list,
                            avg_gate_count_list, generations_list,
                            early_stopping_monitor, checkpoint_path=CHECKPOINT_PATH,
                            fidelity_history=fidelity_history, depth_history=depth_history,
                            diagnostics=diagnostics)

    diagnostics.end_evolution()

    # Persist full early-stopping state + reason (why the run ended)
    if USE_EARLY_STOPPING and early_stopping_monitor is not None:
        es_state = early_stopping_monitor.get_state()
        es_state['final_stop_reason'] = stop_reason
        es_state['stopped_gen'] = stopped_gen
        with open(os.path.join(LOG_DIR, f'early_stopping_{target_state}_run{run_id}.json'), 'w') as _f:
            json.dump(es_state, _f, indent=2, default=str)

    # Persist Lexi2 per-generation epsilon + tiebreak logging (Douglas).
    if SELECTION_METHOD == "lexi2" and lexi2_log:
        total_fires = sum(v["tiebreak_fires"] for v in lexi2_log.values())
        total_sel = sum(v["selections"] for v in lexi2_log.values())
        with open(os.path.join(LOG_DIR, f"lexi2_log_{target_state}_run{run_id}.json"), "w") as _f:
            json.dump({
                "target_state": target_state,
                "seed": seed,
                "selection_method": "lexi2",
                "per_generation": {str(g): v for g, v in sorted(lexi2_log.items())},
                "totals": {
                    "selections": total_sel,
                    "tiebreak_fires": total_fires,
                    "tiebreak_rate": (total_fires / total_sel if total_sel else 0.0),
                },
            }, _f, indent=2)

    # Final checkpoint for this run
    save_checkpoint(population, stopped_gen, hof, best_fitness_list,
                    avg_gate_count_list, generations_list,
                    early_stopping_monitor, checkpoint_path=CHECKPOINT_PATH,
                    fidelity_history=fidelity_history, depth_history=depth_history,
                    diagnostics=diagnostics)

    # ---- Final best individual analysis ----
    best_ind = hof.items[0]
    best_phenotype = evaluator.decode_individual(best_ind)
    gh = stable_genome_hash(best_ind.genome)
    iseed = (seed + gh) % (2**32)
    fv, logs, pc = fitness_function_qiskit(best_phenotype, target_state=target_state, log_states=True,
                                           individual_seed=iseed, use_noise=USE_NOISE_MODEL)
    best_qc = evaluator.execute_circuit(best_phenotype)

    # RAW (pre-transpile) metrics — the opt-0 column
    raw_gates = best_qc.size() if best_qc else None
    raw_depth = best_qc.depth() if best_qc else None
    gate_ops = dict(best_qc.count_ops()) if best_qc else {}
    raw_two_q = gate_ops.get("cz", 0) + gate_ops.get("cx", 0) + gate_ops.get("ecr", 0)
    # two_qubit_gates is now the TRANSPILED 2Q count (the metric the deployment
    # rule and Lexi2 tiebreak use); raw 2Q is preserved separately.
    two_q = int(pc.get("two_qubit_gates", raw_two_q))

    # ---- Always draw + save the FINAL best circuit (raw + transpiled) ----
    # Runs unconditionally after the loop, so an early-stopped run still shows
    # and saves its final circuit. PNGs land in this run's log folder.
    if best_qc is not None:
        print(f"\n[FINAL | run {run_id} | stopped gen {stopped_gen}] Best circuit (raw) "
              f"| fid={pc['p_marked']:.4f} | raw={raw_gates}g/{raw_depth}d")
        _fig_raw = best_qc.draw("mpl")
        display(_fig_raw)
        _fig_raw.savefig(os.path.join(LOG_DIR, f"circuit_raw_{target_state}_run{run_id}.png"),
                         dpi=150, bbox_inches="tight")
        _plt.close(_fig_raw)
        if USE_NOISE_MODEL:
            try:
                _tf = transpile(best_qc, target=transpile_target(), optimization_level=3,
                                seed_transpiler=seed)
                print(f"[FINAL | run {run_id}] Transpiled | {_tf.size()}g/{_tf.depth()}d")
                _fig_t = _tf.draw("mpl", idle_wires=False)
                display(_fig_t)
                _fig_t.savefig(os.path.join(LOG_DIR, f"circuit_transpiled_{target_state}_run{run_id}.png"),
                               dpi=150, bbox_inches="tight")
                _plt.close(_fig_t)
            except Exception as _e:
                print(f"  [final transpile draw skipped: {_e}]")

    # Persist per-run diagnostics + metadata
    diagnostics.save_csv(os.path.join(LOG_DIR, f"diagnostics_{target_state}_run{run_id}.csv"))
    run_cfg = {"target_state": target_state, "seed": seed, "run_id": run_id,
               "selection_method": SELECTION_METHOD, "population_size": POPULATION_SIZE,
               "max_generations": MAX_GENERATIONS, "backend": backend_name,
               "early_stopped_gen": stopped_gen,
               "stop_reason": stop_reason, "use_noise": USE_NOISE_MODEL}
    diagnostics.save_run_metadata(os.path.join(LOG_DIR, f"run_metadata_{target_state}_run{run_id}.json"),
                                  config=run_cfg)

    result = {
        "run_id": run_id, "seed": seed, "target_state": target_state,
        "selection_method": SELECTION_METHOD,
        "raw_fitness": float(best_ind.fitness.values[0]),
        "fitness": float(fv),
        "fidelity": pc["p_marked"],
        "gate_count": pc["gate_count"],          # transpiled (opt-3)
        "depth": pc["depth"],                    # transpiled (opt-3)
        "raw_gate_count": raw_gates,             # opt-0
        "raw_depth": raw_depth,                  # opt-0
        "gate_ops": gate_ops, "two_qubit_gates": two_q,
        "raw_two_qubit_gates": raw_two_q,
        "phenotype": best_phenotype,
        "genome_hash": str(gh),
        "individual": _copy.deepcopy(best_ind),  # for hardware run later
        "generations": generations_list,
        "fitness_history": best_fitness_list,
        "fidelity_history": fidelity_history,
        "gate_count_history": avg_gate_count_list,
        "depth_history": depth_history,
        "early_stopped_gen": stopped_gen,
        "stop_reason": stop_reason,
        "diagnostics_records": diagnostics.records,
        "log_dir": LOG_DIR,
    }
    print(f"  DONE: fid={pc['p_marked']:.4f}, transpiled={pc['gate_count']}g/{pc['depth']}d, "
          f"raw={raw_gates}g/{raw_depth}d, 2Q={two_q}")
    return result

def run_hof_on_ibm(evaluator, hof, target_state=TARGET_STATE, log_dir=None, seed_transpiler=None):
    """
    Run Hall of Fame individuals on IBM quantum hardware (robust).
    - Disables streaming callbacks to avoid notebook stalls.
    - Submits once and awaits the same job.
    - Handles counts consistently.
    """
    print(f"\n{'='*60}")
    print("IBM QUANTUM HARDWARE EXECUTION")
    print(f"{'='*60}")
    print(f"Evolution used noise model: {'YES' if USE_NOISE_MODEL else 'NO'}")
    print(f"Target state: {target_state}")
    print(f"Shots per circuit: {evaluator.shots}")

    # Init IBM Runtime
    try:
        # Use one channel consistently; add name if you use a saved profile
        service = QiskitRuntimeService(channel="ibm_cloud")  # , name="qgss-2025"
        backend = service.backend("ibm_fez")
        status = backend.status()
        print(f"✓ Connected to backend: {backend.name}")
        print(f"  Status: {status}")
        try:
            print(f"  Queue: {status.pending_jobs} jobs")
        except Exception:
            pass
    except Exception as e:
        print(f"✗ Could not connect to IBM backend: {e}")
        print("  Please check your IBM account/token/instance.")
        return

    sampler = Sampler(mode=backend)
    sampler.options.default_shots = evaluator.shots

    for i, ind in enumerate(hof.items):
        print(f"\n[HOF Individual {i+1}] Fitness: {ind.fitness.values[0]:.4f}")

        pheno_code = evaluator.decode_individual(ind)
        if pheno_code is None:
            print("  ✗ Could not decode individual - skipping")
            continue

        # Ensure explicit registers if your decoder emits qc = QuantumCircuit(3,3)
        pheno_code = re.sub(
            r"qc\s*=\s*QuantumCircuit\(\s*3\s*,\s*3\s*\)",
            "qr = QuantumRegister(3, name='q')\n"
            "cr = ClassicalRegister(3, name='cr')\n"
            "qc = QuantumCircuit(qr, cr)",
            pheno_code
        )

        circuit = evaluator.execute_circuit(pheno_code)
        if circuit is None:
            print("  ✗ Invalid circuit - skipping")
            continue

        print("\nEvolved circuit statistics:")
        print(f"  Original gates: {circuit.size()}")
        print(f"  Original depth: {circuit.depth()}")
        print(f"  Gate counts: {circuit.count_ops()}")

        print("\nOriginal evolved circuit:")
        display(circuit.draw("mpl"))
        plt.close()  # prevent figure buildup

        # Transpile
        print(f"\nTranspiling circuit for {backend.name}...")
        try:
            transpile_seed = seed_transpiler if seed_transpiler is not None else RANDOM_SEED
            pm = generate_preset_pass_manager(
                target=backend.target,
                optimization_level=3,
                seed_transpiler=transpile_seed  # matches fitness-time transpile seed
            )
            circuit_isa = pm.run(circuit)
            print("✓ Circuit transpiled successfully!")

            print("\nTranspiled circuit statistics:")
            print(f"  Transpiled gates: {circuit_isa.size()}")
            print(f"  Transpiled depth: {circuit_isa.depth()}")
            print(f"  Gate counts: {circuit_isa.count_ops()}")
            try:
                print(f"  Gate reduction: {((circuit.size() - circuit_isa.size()) / circuit.size() * 100):.1f}%")
                print(f"  Depth reduction: {((circuit.depth() - circuit_isa.depth()) / circuit.depth() * 100):.1f}%")
            except ZeroDivisionError:
                pass

            print("\nTranspiled circuit for hardware:")
            display(circuit_isa.draw(output="mpl", idle_wires=False))
            plt.close()
        except Exception as transpile_error:
            print(f"✗ Circuit transpilation failed: {transpile_error}")
            continue

        # Submit once, await that job
        print(f"\nSubmitting job to {backend.name}...")
        print(f"  Requested shots: {evaluator.shots}")

        try:
            job = sampler.run([circuit_isa])
            print("✓ Job submitted.")
            print(f"  Job ID: {job.job_id()}")
            print("  Waiting for results...")

            # Add a timeout to avoid indefinite waits (adjust as needed)
            result = job.result(timeout=1800)  # seconds

            # Extract counts (new qiskit-ibm-runtime API)
            pub_result = result[0]
            # Try different access patterns for compatibility
            try:
                # New API: pub_result.data.cr.get_counts()
                counts = pub_result.data.cr.get_counts()
            except AttributeError:
                try:
                    # Alternative: pub_result.data.c.get_counts()
                    counts = pub_result.data.c.get_counts()
                except AttributeError:
                    # Fallback: iterate data fields
                    data = pub_result.data
                    field_name = [f for f in dir(data) if not f.startswith('_') and hasattr(getattr(data, f), 'get_counts')][0]
                    counts = getattr(data, field_name).get_counts()
            # Reverse bitstrings to match target convention
            counts = {k[::-1]: v for k, v in counts.items()}

            # Compute metrics
            total = sum(counts.values())
            p_marked = counts.get(target_state, 0) / total if total > 0 else 0.0

            print(f"\n✓ Hardware execution completed!")
            print(f"  Total shots processed: {total}")
            print(f"  Hardware p(marked) for {target_state}: {p_marked:.4f}")
            print(f"  Measurement distribution: {counts}")

            # Plot + display
            fig = plot_distribution(counts, title=f"HOF #{i+1} on {backend.name} - {total} shots")
            display(fig)
            plt.close(fig)

            # Compare to evolution fitness (ensure these names are in scope)
            evolution_fitness = ind.fitness.values[0]
            error_hw = 1 - p_marked
            miss_hw = 1 if p_marked < SUCCESS_THRESHOLD else 0
            gate_penalty_hw = GATE_PENALTY_WEIGHT * circuit_isa.size()
            fitness_hw = 10 * miss_hw + error_hw + gate_penalty_hw

            print("\n  Performance comparison:")
            print(f"    Evolution fitness: {evolution_fitness:.4f}")
            print(f"    Hardware  fitness: {fitness_hw:.4f}")
            if fitness_hw < evolution_fitness:
                print(f"    Hardware shows better performance: {(evolution_fitness - fitness_hw):.4f}")
            elif fitness_hw > evolution_fitness:
                print(f"    ⚠ Hardware shows degradation: {(fitness_hw - evolution_fitness):.4f}")
            else:
                print("    ≡ Equivalent performance")

            # Persist results
            hw_data = {
                "individual_id": i + 1,
                "fitness_evolution": float(evolution_fitness),
                "fitness_hardware": float(fitness_hw),
                "backend": backend.name,
                "target_state": target_state,
                "counts": counts,
                "p_marked_hw": p_marked,
                "total_shots": total,
                "original_gates": circuit.size(),
                "original_depth": circuit.depth(),
                "transpiled_gates": circuit_isa.size(),
                "transpiled_depth": circuit_isa.depth(),
                "job_id": job.job_id(),
                "timestamp": datetime.now().isoformat(),
            }

            out_dir = log_dir or evaluator.log_dir or LOG_DIR
            os.makedirs(out_dir, exist_ok=True)
            json_path = os.path.join(out_dir, f"hof_{i+1}_ibm_hardware_data.json")
            with open(json_path, "w") as f:
                json.dump(hw_data, f, indent=2)
            print(f"  Results saved to: {json_path}")

        except Exception as execution_error:
            print(f"✗ Hardware execution failed: {execution_error}")
            print("  This could be due to:")
            print("    - Backend queue / transient network issues")
            print("    - Streaming callbacks (already disabled here)")
            print("    - Session/runtime mismatches")
            continue

    print(f"\n{'='*60}")
    print("IBM Quantum hardware execution completed!")
    print(f"Note: Results from real quantum hardware at {backend.name}")
    print(f"{'='*60}")

def select_deployed_run(per_run):
    """Lambda-free deployment rule (agreed change, applied everywhere a best
    circuit is selected for deployment):
      1. highest sim fidelity
      2. fewest transpiled two-qubit gates
      3. fewest total transpiled gates
      4. lowest transpiled depth
    Replaces the old min(raw_fitness) / max(fidelity) picks.
    """
    return max(per_run, key=lambda r: (
        r["fidelity"], -r["two_qubit_gates"], -r["gate_count"], -r["depth"]))


def write_run_result(result: dict) -> str:
    """Persist the serializable per-run result record (headless aggregation).

    New output file (not produced by the notebooks): run_result_<state>_run<i>.json
    in the run's log dir. Its fields are exactly the per_run subset the notebook
    writes into AGGREGATE_<state>.json (cell 40), so AGGREGATE can be rebuilt
    after the fact from independent headless runs.
    """
    subset = {k: result[k] for k in (
        "run_id", "seed", "target_state", "selection_method", "raw_fitness",
        "fitness", "fidelity", "gate_count", "depth", "raw_gate_count",
        "raw_depth", "gate_ops", "two_qubit_gates", "raw_two_qubit_gates",
        "phenotype", "genome_hash", "early_stopped_gen", "stop_reason",
    )}
    path = os.path.join(result["log_dir"],
                        f"run_result_{result['target_state']}_run{result['run_id']}.json")
    with open(path, "w") as f:
        json.dump(subset, f, indent=2)
    return path


def state_out_dir(outdir: str, selection: str, population: int,
                  use_noise: bool, state: str) -> str:
    return os.path.join(outdir, selection, f"pop{population}",
                        "noise" if use_noise else "ideal", f"state_{state}")


def aggregate_state(outdir: str, state: str, selection: str, population: int,
                    use_noise: bool) -> dict:
    """Rebuild AGGREGATE_<state>.json + experiment_seeds.json from per-run
    run_result files (mirrors notebook cell 40 schema), and write
    deployed_best.json using the lambda-free deployment rule.
    """
    state_dir = state_out_dir(outdir, selection, population, use_noise, state)
    os.makedirs(state_dir, exist_ok=True)

    # run_result files are written inside each run_*/ subdirectory.
    result_files = sorted(glob.glob(
        os.path.join(state_dir, "run_*", "run_result_*.json")))
    if not result_files:
        raise FileNotFoundError(
            f"no run_result_*.json files found in {state_dir} -- run the "
            f"'run' command for the seeds of this state first."
        )

    per_run = []
    for f in result_files:
        with open(f) as fh:
            per_run.append(json.load(fh))
    per_run.sort(key=lambda r: r["run_id"])

    # Save the seed list used (reproducibility) -- same shape as notebook cell 40.
    with open(os.path.join(state_dir, "experiment_seeds.json"), "w") as f:
        json.dump({"target_state": state,
                   "selection_method": selection,
                   "seeds": [r["seed"] for r in per_run],
                   "timestamp": datetime.now().isoformat()}, f, indent=2)

    fids  = [r["fidelity"] for r in per_run]
    deps  = [r["depth"] for r in per_run]
    gates = [r["gate_count"] for r in per_run]
    raw_d = [r["raw_depth"] for r in per_run]
    raw_g = [r["raw_gate_count"] for r in per_run]
    twoq  = [r["two_qubit_gates"] for r in per_run]
    stops = [r["early_stopped_gen"] for r in per_run]

    def ms(x): return (statistics.mean(x), statistics.stdev(x) if len(x) > 1 else 0.0)
    agg = {
        "target_state": state,
        "selection_method": selection,
        "n_runs": len(per_run), "seeds": [r["seed"] for r in per_run],
        "fidelity_mean": ms(fids)[0], "fidelity_std": ms(fids)[1],
        "depth_mean": ms(deps)[0], "depth_std": ms(deps)[1],
        "gate_count_mean": ms(gates)[0], "gate_count_std": ms(gates)[1],
        "raw_depth_mean": ms(raw_d)[0], "raw_depth_std": ms(raw_d)[1],
        "raw_gate_mean": ms(raw_g)[0], "raw_gate_std": ms(raw_g)[1],
        "two_qubit_mean": ms(twoq)[0], "two_qubit_std": ms(twoq)[1],
        "mean_early_stop_gen": ms(stops)[0],
        "per_run": [{k: r[k] for k in ("run_id", "seed", "fidelity", "depth",
                                       "gate_count", "raw_depth", "raw_gate_count",
                                       "two_qubit_gates", "raw_fitness",
                                       "early_stopped_gen", "stop_reason",
                                       "phenotype", "gate_ops")}
                    for r in per_run],
    }
    with open(os.path.join(state_dir, f"AGGREGATE_{state}.json"), "w") as f:
        json.dump(agg, f, indent=2)

    # Lambda-free deployment pick (no hardware submission).
    best = select_deployed_run(per_run)
    deployed = {k: best[k] for k in ("run_id", "seed", "fidelity", "depth",
                                     "gate_count", "two_qubit_gates",
                                     "raw_depth", "raw_gate_count", "phenotype")}
    deployed["selection_method"] = selection
    deployed["population_size"] = population
    deployed["rule"] = ("max fidelity -> min transpiled 2Q gates -> "
                        "min total transpiled gates -> min transpiled depth")
    with open(os.path.join(state_dir, "deployed_best.json"), "w") as f:
        json.dump(deployed, f, indent=2)

    print(f"AGGREGATE | State |{state}> | {selection} | {len(per_run)} runs")
    print(f"Fidelity:        {ms(fids)[0]*100:.2f}% +/- {ms(fids)[1]*100:.2f}%")
    print(f"Transpiled depth:{ms(deps)[0]:.2f} +/- {ms(deps)[1]:.2f}")
    print(f"Transpiled gates:{ms(gates)[0]:.2f} +/- {ms(gates)[1]:.2f}")
    print(f"2Q gates:        {ms(twoq)[0]:.2f} +/- {ms(twoq)[1]:.2f}")
    print(f"Mean early-stop: gen {ms(stops)[0]:.1f}")
    print(f"Deployed (lambda-free rule): run {best['run_id']} seed {best['seed']} "
          f"fid={best['fidelity']:.4f} 2Q={best['two_qubit_gates']} depth={best['depth']}")
    return agg

def run_cli(argv) -> int:
    import argparse
    ap = argparse.ArgumentParser(
        prog="run_experiment.py run",
        description="Run one complete Grover-circuit evolution (headless).")
    ap.add_argument("--state", required=True, help="target state, e.g. 000..111")
    ap.add_argument("--seed", type=int, required=True, help="RNG seed")
    ap.add_argument("--selection", required=True,
                    choices=["epsilon_lexicase", "tournament", "lexi2", "per_prob"],
                    help="selection arm (per_prob is a stub and errors)")
    ap.add_argument("--population", type=int, default=None)
    ap.add_argument("--generations", type=int, default=None)
    ap.add_argument("--outdir", default=None,
                    help="output root (default: experiments)")
    ap.add_argument("--run-id", type=int, default=None,
                    help="run id for output naming; default: seed's index in RUN_SEEDS")
    ap.add_argument("--workers", type=int, default=os.cpu_count(),
                    help="multiprocessing pool size for evaluation (default: cpu count)")
    ap.add_argument("--ideal", action="store_true",
                    help="use ideal simulation instead of the noise model")
    ap.add_argument("--noise-file", default=None,
                    help="path to a frozen-env bundle pickle "
                         "({noise_model, target}), a NoiseModel pickle, or a "
                         "NoiseModel.to_dict() JSON; defaults to "
                         "$QISKIT_NOISE_MODEL_JSON")
    args = ap.parse_args(argv)

    if not re.fullmatch(r"[01]{3}", args.state):
        raise ValueError(f"--state must be a 3-bit binary string, got {args.state!r}")
    if args.selection == "per_prob":
        raise NotImplementedError(
            f"selection arm {args.selection!r} is not implemented yet; "
            f"use 'epsilon_lexicase', 'tournament', or 'lexi2'. Refusing to run."
        )
    run_id = args.run_id or (RUN_SEEDS.index(args.seed) + 1 if args.seed in RUN_SEEDS else 1)

    # Apply CLI config to module globals (the extracted code reads these).
    global TARGET_STATE, RANDOM_SEED, SELECTION_METHOD, POPULATION_SIZE
    global MAX_GENERATIONS, USE_NOISE_MODEL, EXPERIMENTS_ROOT
    global NOISE_MODEL_PATH
    TARGET_STATE = args.state
    RANDOM_SEED = args.seed
    SELECTION_METHOD = args.selection
    POPULATION_SIZE = args.population if args.population is not None else POPULATION_SIZE
    MAX_GENERATIONS = args.generations if args.generations is not None else MAX_GENERATIONS
    USE_NOISE_MODEL = not args.ideal
    EXPERIMENTS_ROOT = args.outdir if args.outdir is not None else EXPERIMENTS_ROOT
    NOISE_MODEL_PATH = args.noise_file or os.environ.get("QISKIT_NOISE_MODEL_JSON")

    random.seed(RANDOM_SEED)
    np.random.seed(RANDOM_SEED)

    print(f"=== run_experiment.py | state {TARGET_STATE} | seed {RANDOM_SEED} "
          f"| {SELECTION_METHOD} | pop{POPULATION_SIZE} | "
          f"max_gen {MAX_GENERATIONS} | noise={USE_NOISE_MODEL} ===")

    connect_to_backend()
    setup_toolbox(args.workers, SELECTION_METHOD)

    try:
        result = run_evolution_experiment(run_id, RANDOM_SEED, TARGET_STATE,
                                          selection_method=SELECTION_METHOD)
    finally:
        if pool is not None:
            pool.close()
            pool.join()

    result_path = write_run_result(result)
    print(f"✓ Per-run result record: {result_path}")
    print("NOTE: simulation only -- no IBM Quantum hardware job was submitted.")
    return 0


def aggregate_cli(argv) -> int:
    import argparse
    ap = argparse.ArgumentParser(
        prog="run_experiment.py aggregate",
        description="Rebuild AGGREGATE_<state>.json from per-run results and "
                    "write the lambda-free deployed_best.json (no hardware).")
    ap.add_argument("--state", required=True, help="target state, e.g. 000..111")
    ap.add_argument("--selection", required=True,
                    choices=["epsilon_lexicase", "tournament", "lexi2", "per_prob"])
    ap.add_argument("--population", type=int, default=POPULATION_SIZE)
    ap.add_argument("--outdir", default=EXPERIMENTS_ROOT)
    ap.add_argument("--ideal", action="store_true")
    args = ap.parse_args(argv)

    if not re.fullmatch(r"[01]{3}", args.state):
        raise ValueError(f"--state must be a 3-bit binary string, got {args.state!r}")
    aggregate_state(args.outdir, args.state, args.selection,
                    args.population, not args.ideal)
    return 0


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in ("run", "aggregate"):
        sub = argv.pop(0)
        if sub == "aggregate":
            return aggregate_cli(argv)
        # "run" falls through to run_cli
    return run_cli(argv)


if __name__ == "__main__":
    sys.exit(main())
