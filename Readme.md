# Evolving Hardware-Efficient Grover Circuits with Grammatical Evolution

> **GECCO '26 Submission** — *Arinze Obidiegwu, Douglas Mota Dias, Emmanuel Obidiegwu*
>
> Automatic synthesis of state-specific, NISQ-optimised, 3-qubit Grover's search circuits via Grammatical Evolution, validated on the 133-qubit IBM Heron processor (`ibm_torino`).

---

## Overview

Classical implementations of Grover's algorithm use a *fixed* oracle + diffuser decomposition that is mathematically optimal on ideal hardware but performs poorly on real Noisy Intermediate-Scale Quantum (NISQ) processors due to decoherence. A canonical Grover circuit for 3 qubits transpiles to a depth of ~140 gates — with an execution time (~80 μs) that approaches the T₂ dephasing limit (~98 μs) of current IBM Heron hardware, leading to inevitable phase randomisation.

This project uses **Grammatical Evolution (GE)** to automatically discover alternative circuit topologies that achieve significantly higher fidelity on actual hardware. The approach follows a **"one-circuit-per-state"** design philosophy: rather than evolving a general oracle, we evolve a *distinct, specialised* circuit for each of the 8 three-qubit target states. This allows the evolutionary process to exploit state-specific mathematical shortcuts (e.g., cancelling adjacent gates, finding non-standard entangling sequences) that are only valid for a particular instance but yield dramatically shallower circuits.

### Key Results

| Target | Canonical Fidelity | Evolved Fidelity | Canonical Depth | Evolved Depth | Depth Reduction |
|:--|:--|:--|:--|:--|:--|
| \|000⟩ | 74.5% | **96.8%** | 145 | 5 | 96.6% |
| \|110⟩ | 66.3% | **96.9%** | 139 | 6 | 95.7% |
| \|111⟩ | 75.3% | **88.4%** | 137 | 24 | 82.5% |

> [!IMPORTANT]
> Evolved circuits achieved fidelities between **88.4% – 96.9%** vs **66.3% – 79.5%** for canonical baselines — an average **93% depth reduction** — all validated on IBM Heron (`ibm_torino`) with 10,000 shots. Results are statistically significant (Mann-Whitney U, p < 0.01).

---

## Architecture

### High-Level System Architecture

```mermaid
---
config:
  theme: base
  themeVariables:
    primaryColor: "#e8eaf6"
    primaryBorderColor: "#3949ab"
    primaryTextColor: "#1a237e"
    lineColor: "#5c6bc0"
    secondaryColor: "#fce4ec"
    tertiaryColor: "#e8f5e9"
---
flowchart TB
    subgraph Grammar["📖 Context-Free Grammar"]
        G1(["grover.bnf"])
    end

    E1(["🎲 Population Init<br/>N = 1000"])

    subgraph Evolution["⚙️ Evolutionary Loop — GRAPE + DEAP"]
        E2["🧬 Genome → Phenotype<br/>Modulo Mapping"]
        E3[\"🔬 Oracle Injection<br/>state-specific"/]
        E4{{"🎯 Fitness Evaluation<br/>Qiskit Aer, opt_level=0"}}
        E5[/"⚖️ Tournament Selection<br/>k = 5"\]
        E6["🧪 Crossover & Mutation<br/>p_cx=0.8 • p_mut=0.01"]
        E7[("🏆 Hall of Fame<br/>Elite")]
    end

    subgraph Validation["📡 Hardware Validation"]
        V1["Best Circuit<br/>Selection"]
        V2["Transpile for<br/>IBM Heron<br/>opt_level=3"]
        V3["Execute on<br/>ibm_torino<br/>10k shots"]
        V4(["✅ Fidelity Report"])
    end

    G1 ==> E1
    E1 ==> E2
    E2 --> E3 --> E4 --> E5 --> E6 -.->|"next gen"| E2
    E4 ==> E7
    E7 ==>|"after all gens"| V1 --> V2 --> V3 --> V4

    classDef grammar fill:#ede7f6,stroke:#7e57c2,stroke-width:2px,color:#4a148c
    classDef decode fill:#e3f2fd,stroke:#1e88e5,stroke-width:2px,color:#0d47a1
    classDef inject fill:#e0f2f1,stroke:#00897b,stroke-width:2px,color:#004d40
    classDef eval fill:#fff8e1,stroke:#f9a825,stroke-width:2px,color:#e65100
    classDef sel fill:#e8f5e9,stroke:#43a047,stroke-width:2px,color:#1b5e20
    classDef breed fill:#e8eaf6,stroke:#5c6bc0,stroke-width:2px,color:#1a237e
    classDef elite fill:#fce4ec,stroke:#e91e63,stroke-width:2px,color:#880e4f
    classDef hw fill:#fbe9e7,stroke:#e64a19,stroke-width:2px,color:#bf360c
    classDef result fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px,color:#1b5e20

    class G1 grammar
    class E1 grammar
    class E2 decode
    class E3 inject
    class E4 eval
    class E5 sel
    class E6 breed
    class E7 elite
    class V1,V2,V3 hw
    class V4 result
```

### Evolutionary Loop (per Target State)

Each target state runs **5 independent evolutionary experiments**, each with a distinct random seed, to enable statistical analysis. In successful runs, the algorithm maximises fidelity (p_marked ≈ 1.0) within ~20 generations, after which fitness pressure shifts to minimising gate count and depth.

```mermaid
---
config:
  theme: base
  themeVariables:
    primaryColor: "#e8eaf6"
    primaryBorderColor: "#3949ab"
    primaryTextColor: "#1a237e"
    lineColor: "#5c6bc0"
---
flowchart LR
    subgraph Run["🔄 Single Evolutionary Run"]
        direction TB
        A(["🎲 Init Population<br/>N = 1000"]) --> B["🧬 Decode Genome<br/>via BNF Grammar"]
        B --> C[\"🔬 Inject Oracle<br/>state-specific"/]
        C --> D["⚙️ Transpile<br/>opt_level = 0"]
        D --> E["💻 Simulate<br/>Qiskit Aer • 10k shots"]
        E --> F{{"🎯 Compute Fitness<br/>10×miss + 1−p + λ·gates"}}
        F --> G{"Gen < 100?"}
        G -- "✅ Yes" --> H["⚖️ Select → 🧪 Cross → 🧬 Mutate<br/>Elitism: best survives"]
        H -.->|"next gen"| B
        G -- "🏁 No" --> I(["🏆 Return Best<br/>Hall of Fame"])
    end

    classDef initNode fill:#ede7f6,stroke:#7e57c2,stroke-width:2px,color:#4a148c
    classDef decodeNode fill:#e3f2fd,stroke:#1e88e5,stroke-width:2px,color:#0d47a1
    classDef injectNode fill:#e0f2f1,stroke:#00897b,stroke-width:2px,color:#004d40
    classDef simNode fill:#f3e5f5,stroke:#8e24aa,stroke-width:2px,color:#4a148c
    classDef fitNode fill:#fff8e1,stroke:#f9a825,stroke-width:2px,color:#e65100
    classDef selectNode fill:#e8f5e9,stroke:#43a047,stroke-width:2px,color:#1b5e20
    classDef resultNode fill:#fce4ec,stroke:#e91e63,stroke-width:2px,color:#880e4f
    classDef decisionNode fill:#fff3e0,stroke:#ef6c00,stroke-width:2px,color:#e65100
    classDef transpileNode fill:#e8eaf6,stroke:#5c6bc0,stroke-width:2px,color:#1a237e

    class A initNode
    class B decodeNode
    class C injectNode
    class D transpileNode
    class E simNode
    class F fitNode
    class G decisionNode
    class H selectNode
    class I resultNode
```

### BNF Grammar Structure

The grammar (`grammars/grover.bnf`) balances the **expressivity-tractability trade-off**: it enforces a *macroscopic bias* (the Grover skeleton) while permitting *microscopic variance* (evolvable internal blocks). This prunes the search space of topologically invalid circuits while allowing GE to discover hardware-efficient decompositions that standard compilers miss.

```mermaid
---
config:
  theme: base
  themeVariables:
    primaryColor: "#f3e5f5"
    primaryBorderColor: "#8e24aa"
    primaryTextColor: "#4a148c"
    lineColor: "#7e57c2"
---
flowchart TB
    P(["📄 Program"]) ==> Init["Initialize<br/>QuantumCircuit 3,3"]
    P ==> Had["HadamardAll<br/>H 0 H 1 H 2"]
    P ==> Iter["GroverIterations<br/>1 or more"]
    P ==> Meas["Measure<br/>measure 0-2"]

    Iter --> GI{{"GroverIteration"}}
    GI -->|"OR"| Ora["🧬 OracleBlock<br/>Fully Evolvable"]
    GI -->|"OR"| Diff["🧬 DiffuserBlock<br/>Fixed + Evolvable tail"]

    Ora --> GL1["SmallGateList<br/>1+ gates, recursive"]
    Diff --> SD["StandardDiffuser<br/>H-X-CX-X-H, fixed"]
    Diff --> OG["OptionalGates<br/>1+ gates, recursive"]

    GL1 --- Gates{{"🎨 Gate Palette"}}
    OG --- Gates

    Gates --> SQ["Single-Qubit<br/>X Y Z H S T I"]
    Gates --> TQ["Two-Qubit<br/>CX CY CZ SWAP"]
    Gates --> ThQ["Three-Qubit<br/>CCX CSWAP"]
    Gates --> PG["Parameterised<br/>RX RY RZ U<br/>RXX RYY RZZ RZX"]

    classDef root fill:#ede7f6,stroke:#7e57c2,stroke-width:3px,color:#4a148c
    classDef fixed fill:#e3f2fd,stroke:#1565c0,stroke-width:2px,color:#0d47a1
    classDef evolvable fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px,color:#1b5e20
    classDef choice fill:#fff8e1,stroke:#f9a825,stroke-width:2px,color:#e65100
    classDef palette fill:#fce4ec,stroke:#c62828,stroke-width:2px,color:#880e4f
    classDef gate fill:#f3e5f5,stroke:#8e24aa,stroke-width:1px,color:#4a148c

    class P root
    class Init,Had,Meas fixed
    class Iter fixed
    class GI choice
    class Ora,Diff evolvable
    class GL1,OG evolvable
    class SD fixed
    class Gates palette
    class SQ,TQ,ThQ,PG gate
```

> [!NOTE]
> The grammar is **more permissive** than the paper's idealised formula `U_total = U_init · (U_diff · U_oracle)^k`. Each `⟨GroverIteration⟩` produces *either* an Oracle *or* a Diffuser block (not both), and `⟨GroverIterations⟩` is a recursive list of one or more such iterations. This means evolution can produce any mixed sequence (e.g., Oracle → Oracle → Diffuser → Oracle), giving it freedom to discover non-standard block orderings.

### Dual-Stage Transpilation Strategy

A critical design decision ensures the evolutionary process learns efficient structures *natively* rather than relying on the compiler:

| Stage | Optimisation Level | Purpose |
|:--|:--|:--|
| **During Evolution** (simulation) | `optimization_level=0` | Disables gate cancellation/commutation — forces GE to discover efficient topologies itself |
| **During Validation** (hardware) | `optimization_level=3` | Full Qiskit optimisation — ensures fair comparison against canonical baselines |

### Fitness Function

Adapted from Spector et al.'s hit-criterion formulation, extended for the NISQ era with a gate-count parsimony term:

```
Fitness(C) = 10 × miss + (1 − p_marked) + λ × gate_count
```

| Term | Definition | Purpose |
|:--|:--|:--|
| `p_marked` | Probability of measuring target state \|w⟩ in noiseless sim | Core correctness metric |
| `miss` | 1 if p_marked < 0.48, else 0 | **Viability gate** — ensures correctness *before* size optimisation |
| `10` | Heavy penalty coefficient on `miss` | Any non-viable circuit always ranks worse than a viable one |
| `λ` | 0.02 (parsimony coefficient) | Penalises gate count to drive depth reduction |

> [!NOTE]
> Fitness is **minimised** (f(C) = 0 is perfect). The `miss` term acts as a phase transition: evolution first achieves viability (p > 0.48), then shifts to structural optimisation. Sensitivity analysis showed λ ≤ 0.01 causes bloat (depth > 50); λ ≥ 0.05 drives populations to trivial empty circuits.

### Experiment Pipeline

```mermaid
---
config:
  theme: base
  themeVariables:
    actorBkg: "#ede7f6"
    actorBorder: "#7e57c2"
    actorTextColor: "#4a148c"
    activationBorderColor: "#5c6bc0"
    activationBkgColor: "#e8eaf6"
    signalColor: "#3949ab"
    signalTextColor: "#1a237e"
    loopTextColor: "#e65100"
    labelBoxBkgColor: "#fff8e1"
    labelBoxBorderColor: "#f9a825"
    labelTextColor: "#e65100"
    noteBkgColor: "#e8f5e9"
    noteBorderColor: "#43a047"
    noteTextColor: "#1b5e20"
---
sequenceDiagram
    participant E as 🧪 Experiment Runner
    participant GE as ⚙️ GRAPE/DEAP Engine
    participant SIM as 💻 Qiskit Aer<br/>opt_level=0
    participant HW as 📡 IBM Heron<br/>ibm_torino

    E->>E: 🎲 Generate 5 random seeds
    E->>E: 💾 Save seeds to experiment_seeds.json

    loop 🔄 Run 1 … 5
        E->>+GE: Init population, seed_i, N=1000
        loop 🧬 Generation 1 … 100
            GE->>GE: Decode genomes via BNF
            GE->>GE: Inject state-specific oracle
            GE->>+SIM: Simulate circuits, 10k shots
            SIM-->>-GE: Measurement distributions
            GE->>GE: Fitness = 10 x miss + 1-p + lambda x gates
            GE->>GE: Select, Cross, Mutate, Elitism
        end
        GE-->>-E: 🏆 Best individual, Hall of Fame
    end

    Note over E: 📊 Statistical Analysis
    E->>E: Mean and SD of fidelity, depth, gates
    E->>E: Mann-Whitney U test
    E->>E: Select overall best circuit

    E->>+HW: Transpile opt_level=3 and execute
    HW-->>-E: ✅ Hardware measurement results

    E->>E: 📈 Generate convergence plots
```

---

## Repository Structure

```text
├── grammars/
│   └── grover.bnf                  # BNF grammar for GRAPE
├── Grover_000_STD.ipynb            # GE pipeline for |000⟩
├── Grover_001_STD.ipynb            # GE pipeline for |001⟩
├── Grover_010_STD.ipynb            # GE pipeline for |010⟩
├── Grover_011_STD.ipynb            # GE pipeline for |011⟩
├── Grover_100_STD.ipynb            # GE pipeline for |100⟩
├── Grover_101_STD.ipynb            # GE pipeline for |101⟩
├── Grover_110_STD.ipynb            # GE pipeline for |110⟩
├── Grover_111_STD.ipynb            # GE pipeline for |111⟩
├── grovers-algorithm.ipynb         # Canonical Grover baseline
├── GECCO_2026_QCE_Camera_Ready.pdf # Accompanying paper
└── Readme.md
```

Each `Grover_XXX_STD.ipynb` contains the **complete pipeline** for one target state:

1. **Imports & IBM Backend Config** — Qiskit, GRAPE, DEAP, IBM Runtime
2. **Grammar Loading** — Loads `grammars/grover.bnf` via GRAPE
3. **Oracle Generation** — Creates state-specific oracle code
4. **Circuit Evaluator** — Decodes genomes, injects oracle, builds `QuantumCircuit`, simulates with `optimization_level=0`
5. **Fitness Function** — Three-term fitness with viability gate
6. **GE Hyperparameters** — Population, generations, crossover/mutation, etc.
7. **5 Independent Runs** — Each with a unique random seed
8. **Statistical Analysis** — Mean ± SD of fidelity, depth, gate count
9. **Best Circuit → IBM Hardware** — Transpiled with `optimization_level=3`, executed on `ibm_torino`
10. **Aggregate Visualisation** — Convergence curves across all runs

---

## GE Hyperparameters

| Parameter | Value | Note |
|:--|:--|:--|
| Population Size | 1 000 | |
| Generations | 100 | Fidelity converges ~gen 20; depth reduces thereafter |
| Selection | Tournament (k = 5) | |
| Crossover Rate | 0.80 | |
| Mutation Rate | 0.01 | Integer mutation |
| Elitism | 1 | Best individual survives each generation |
| Codon Size | 400 | |
| Max Tree Depth | 50 | |
| Init Depth Range | 20 – 40 | |
| Codon Consumption | Lazy | |
| Independent Runs | 5 | Per target state |
| Shots | 10 000 | Per simulation / hardware execution |

---

## Prerequisites

**Python 3.8+** with Jupyter.

```bash
pip install qiskit qiskit-aer qiskit-ibm-runtime deap grape-bds numpy pandas matplotlib jupyterlab
```

> [!IMPORTANT]
> Ensure the `grape-bds` library (GRAPE: Grammatical Algorithms in Python for Evolution) is installed and on your Python path.

---

## How to Run

1. **Clone** the repository.
2. **Launch Jupyter:**
   ```bash
   jupyter lab
   ```
3. **Open** the notebook for the desired target state (e.g., `Grover_000_STD.ipynb`).
4. **Run all cells.** The notebook will:
   - Load the BNF grammar
   - Initialise a GRAPE/DEAP population
   - Execute 5 independent evolutionary runs (100 generations each)
   - Output statistical results and convergence plots
   - *(Optionally)* Submit the best circuit to IBM quantum hardware

---

## Hardware Execution

Results reported in the paper were obtained on the **IBM Heron (`ibm_torino`)** 133-qubit processor during a specific calibration window (T₁ ≈ 146 μs, T₂ ≈ 98 μs).

To reproduce hardware validation:

1. Obtain a valid [IBM Quantum](https://quantum.ibm.com/) account.
2. Set your API token securely — do **not** commit tokens to version control.
3. Update the backend configuration in the notebook.

> [!WARNING]
> The notebooks contain placeholder tokens (`IBM_QUANTUM_TOKEN_HERE`). You must replace these with your own credentials before hardware execution.

---

## Grammar Details

The BNF grammar enforces a rigid **macro-structure** while leaving **micro-structure** fully evolvable:

```
U_total = U_init · (U_diff · U_oracle)^k
```

- **Fixed skeleton:** `⟨Program⟩ ::= ⟨Initialize⟩ ⟨HadamardAll⟩ ⟨GroverIterations⟩ ⟨Measure⟩`
- **Evolvable Oracle:** Can contain any sequence from the gate palette `{X, Y, Z, H, S, S†, T, T†, I, CX, CY, CZ, SWAP, CCX, CSWAP, RX, RY, RZ, U, RXX, RYY, RZZ, RZX}` with discrete angles `{0, π/4, π/2, π, 3π/2, 2π, 0.5, 1.3, 2.7, 0.314, 1.5708, 3.1415}`.
- **Evolvable Diffuser tail:** The diffuser starts with a fixed H-X-CX-X-H scaffold, followed by an evolvable gate sequence.

GE's **modulo-based mapping** (`r = c_i mod R`) decouples search-space dimensionality from solution complexity. The **wrapping operator** introduces non-locality: a mutation at codon c_k alters the modulus context for all subsequent codons, enabling large topological jumps (exploration) rather than mere parameter tuning (exploitation).

---

## Reproducibility Notes

- **Stochastic Process:** GE is inherently stochastic. Each run produces different circuits. The 5-run experimental design with seed logging enables statistical analysis.
- **Seed Logging:** Seeds are saved to `experiment_seeds.json` for exact reproducibility.
- **Hardware Noise:** Real quantum hardware calibration (T₁, T₂, readout error) fluctuates daily, so hardware fidelity may vary.
- **Statistical Validation:** Results validated via Mann-Whitney U test (p < 0.01 for all states with Hamming weight ≤ 2). Cohen's d > 2.0 indicates extremely large effect sizes.

---

## Future Directions

- **Lexicase / Lexi2 Selection** — Eliminate manual λ tuning via multi-objective selection
- **Noise-Aware Simulation** — Incorporate device-specific noise models into fitness evaluation
- **Hybrid Optimisation** — Combine GE structural search with gradient-based parameter fine-tuning
- **Intrinsic Evolution** — Evaluate fitness directly on the QPU, allowing evolution to exploit device-specific physics