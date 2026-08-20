"""Create tournament-selection baseline notebooks from the lexicase originals.

For each target state XXX in (000, 001, 010, 011, 100, 101, 110, 111):
  - copy ibm_lexicase_transpiled_XXX.ipynb -> ibm_tournament_transpiled_XXX.ipynb
  - change exactly two assignment lines:
      SELECTION_METHOD          = "epsilon_lexicase" -> "tournament"   (config cell)
      SELECTION_FOR_EXPERIMENT  = "epsilon_lexicase" -> "tournament"   (driver cell)
  - leave everything else byte-identical.
"""

import copy
import glob
import json
import re
import sys

STATES = ["000", "001", "010", "011", "100", "101", "110", "111"]

CFG_RE = re.compile(r'^(SELECTION_METHOD\s*=\s*)"epsilon_lexicase"(\s*)$')
DRIVER_RE = re.compile(r'^(SELECTION_FOR_EXPERIMENT\s*=\s*)"epsilon_lexicase"')


def edit_source(source) -> list[str] | str:
    """Return a new source list with the two selection-method assignments changed."""
    as_string = isinstance(source, str)
    out = source.splitlines(keepends=True) if as_string else list(source)
    wants_cfg = any(CFG_RE.match(line) for line in out)
    wants_driver = any(DRIVER_RE.match(line) for line in out)
    cfg_hits = 0
    driver_hits = 0
    for i, line in enumerate(out):
        m = CFG_RE.match(line)
        if m:
            out[i] = f'{m.group(1)}"tournament"{m.group(2)}'
            cfg_hits += 1
            continue
        m = DRIVER_RE.match(line)
        if m:
            out[i] = DRIVER_RE.sub(r'\1"tournament"', line)
            driver_hits += 1
    if cfg_hits != (1 if wants_cfg else 0):
        raise RuntimeError(f"expected exactly 1 SELECTION_METHOD assignment, found {cfg_hits}")
    if driver_hits != (1 if wants_driver else 0):
        raise RuntimeError(f"expected exactly 1 SELECTION_FOR_EXPERIMENT assignment, found {driver_hits}")
    return "".join(out) if as_string else out


def main() -> None:
    for state in STATES:
        src = f"ibm_lexicase_transpiled_{state}.ipynb"
        dst = f"ibm_tournament_transpiled_{state}.ipynb"
        if not glob.glob(src):
            print(f"!! missing original {src}")
            sys.exit(1)
        if glob.glob(dst):
            print(f"!! refusing to overwrite existing {dst}")
            sys.exit(1)

        nb = json.load(open(src))
        nb_new = copy.deepcopy(nb)
        for cell in nb_new["cells"]:
            if cell.get("cell_type") != "code":
                continue
            src = cell["source"]
            lines = src if isinstance(src, list) else src.splitlines(keepends=True)
            if not any(CFG_RE.match(line) or DRIVER_RE.match(line) for line in lines):
                continue
            cell["source"] = edit_source(cell["source"])

        with open(dst, "w") as f:
            json.dump(nb_new, f, indent=1, ensure_ascii=False)
            f.write("\n")
        print(f"✓ wrote {dst}")


if __name__ == "__main__":
    main()
