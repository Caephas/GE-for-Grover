# Evolving Hardware-Efficient Grover Circuits with Grammatical Evolution

This repository contains the source code, grammar definitions, and experimental notebooks accompanying the paper **"Evolving Hardware-Efficient Grover Circuits with Grammatical Evolution"** submitted to **GECCO '26**.

The project uses Grammatical Evolution (GE) to automatically synthesize state-specific quantum circuits for Grover's algorithm (3-qubit), optimized for execution on Noisy Intermediate-Scale Quantum (NISQ) devices.

## Repository Structure

The repository is organized by target state. Each Jupyter Notebook contains the full evolutionary pipeline (Evolution, Fitness Evaluation, and Circuit Construction) for a specific 3-qubit state.

```text
├── grammars/               # Contains the BNF grammar definition used by GRAPE
├── Grover_000_STD.ipynb    # Evolution pipeline for target state |000>
├── Grover_001_STD.ipynb    # Evolution pipeline for target state |001>
├── ...                     # (Notebooks for states |010> through |110>)
├── Grover_111_STD.ipynb    # Evolution pipeline for target state |111>
├── grovers-algorithm.ipynb # Baseline canonical implementation reference
└── README.md               # This file

```

## Prerequisites

To run these notebooks, you need a Python environment (3.8+) with Jupyter installed.

**Required Packages:**

* `jupyterlab` or `notebook`
* `qiskit` (Quantum SDK)
* `deap` (Evolutionary Computation framework)
* `grape` (Grammatical Algorithms in Python for Evolution)
* `numpy`
* `matplotlib`

To install the core dependencies:

```bash
pip install qiskit deap numpy grape-bds matplotlib jupyterlab

```

*(Note: Ensure the specific GRAPE library used in the notebooks is installed/accessible in your python path).*

## How to Run

1. **Clone the repository** (or download the files).
2. **Launch Jupyter:**
```bash
jupyter lab

```


3. **Open a Notebook:** Select the notebook corresponding to the target state you wish to investigate (e.g., `Grover_000_STD.ipynb`).
4. **Run All Cells:** Execute the cells in order. The notebook will:
* Load the grammar from the `grammars/` folder.
* Initialize the GRAPE/DEAP population.
* Run the evolutionary loop for the specified number of generations (default: 100).
* Output the best circuit found and its fitness statistics.



## Hardware Execution

The results reported in the paper regarding hardware fidelity were obtained using the **IBM Heron (`ibm_torino`)** processor.

To reproduce the hardware validation steps found inside the notebooks:

1. You must have a valid IBM Quantum account.
2. Set your API token in your environment or securely load it in the notebook (do not commit your token to version control).
3. Change the backend provider in the execution cells from the simulator to your available IBM backend.

## Grammar Details

The context-free grammar (BNF) enforces a high-level Grover structure:
`Init -> Hadamard -> Iteration -> Measure`
However, it allows the evolutionary process to inject arbitrary sequences of single and two-qubit gates within the Oracle and Diffuser blocks to discover hardware-efficient topologies.

## Notes on Reproducibility

* **Stochastic Nature:** Grammatical Evolution is stochastic. Running the notebooks again will generate new random seeds, potentially resulting in slightly different circuit topologies or convergence rates compared to the specific runs cited in the paper.
* **Hardware Noise:** Real quantum hardware calibration data (, , readout error) fluctuates daily.

## License

This code is provided for academic review purposes.
