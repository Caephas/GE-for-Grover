# PAPER_FILL_IN v2 — complete calibrated prose for every \TODO in main.tex

**Agent instructions.** Insert each block below into the matching `\TODO{}` in
`gpem_paper/main.tex`, VERBATIM. Fix ONLY: Unicode→LaTeX artefacts
(ε→`$\varepsilon$`, ×→`$\times$`, `|…⟩`→`$\ket{…}$`, — em-dash, ≥→`$\geq$`,
δ→`$\delta$`, ε→`$\epsilon$` in "epsilon" contexts) and cross-reference label
names to match the actual labels in the file. Do NOT alter wording, numbers, or
claims. After each section, compile; report any compile error.

**Verification gate.** Every number here is listed in the "NUMBERS TO VERIFY"
section at the end. Before finalising, check each against the corrected data files
(`PAPER_DATA_FROZEN_3ARM.md`, `STATS_3ARM_frozen.md`, the `2026-09-02` session
logs, `LEXI2_MECHANISM.md`, `DEPLOYMENT_RESELECTION.md`). If any number here does
NOT match those files, FLAG it and stop — do not change the prose yourself.

**Calibration rules (do not violate).**
- "Significant" appears only for the paired fidelity advantage, always paired with
  "small". Never unqualified, never for hardware-across-arms or the counterfactual.
- Hardware-across-arms and the counterfactual are DESCRIPTIVE / CASE STUDY (n=8).
- The Lexi2 mechanism is: size pressure is pervasive and early, but is NOT elevated
  in failed runs. Do NOT write or imply that failed runs fire the tiebreak more.
- Lexi2 claims are about "this Lexi2 configuration"; decomposition and tiebreak are
  confounded; the control arm is future work.

**Author-supplied / pending.** The Declarations block needs the author (funding,
Zenodo DOI, CRediT). Everything else is final.

**Figures to ensure placed/referenced.** fig16 = Lexi2 tiebreak fire rate by
generation (overall / converged / non-converged), source
`lexi2_tiebreak_firerate_bygen.csv` — place it near the Lexi2 mechanism paragraph
and reference as `\ref{fig:firerate}`.

**New supplementary table to build.** `tab:reselection` from the 24-row table in
`DEPLOYMENT_RESELECTION.md` (columns: Arm, State, Deployed seed/sim/D-G-2Q, Alt
seed/sim/D-G-2Q, Changed, Cost). Place in the appendix; reference from the
generalized-counterfactual paragraph.

===================================================================
## ABSTRACT
===================================================================

We study grammatical evolution for synthesising hardware-efficient circuits that
reproduce the output of Grover's algorithm on all eight three-qubit computational
basis states, comparing three coefficient-free selection ingredients under a single
frozen noise model and validating on the 156-qubit IBM Heron~r2 processor
\texttt{ibm\_fez}. Replacing the scalar parsimony fitness of prior work with
$\varepsilon$-lexicase selection over three objectives, we find that
$\varepsilon$-lexicase and tournament selection converge comparably, but that
$\varepsilon$-lexicase holds a small, consistent paired advantage in final fidelity
(wins 52 of 78 decided state--seed pairs; Wilcoxon $p=0.018$; Cliff's
$\delta=+0.23$). A size-aware deployment rule, selecting among near-top-fidelity
candidates by circuit size, improved measured hardware fidelity on the hardest
target by 2.2 percentage points under matched calibration, and would reduce circuit
size on nine of twenty-four deployed circuits at negligible simulated-fidelity cost,
showing that where in the pipeline circuit-size pressure is applied matters. A
lexicographic-parsimony variant (Lexi2) that applies that pressure inside selection
instead reduced circuit size most aggressively but converged least reliably and
measured worst on hardware, marking an applicability boundary for lexicographic
parsimony on continuous-valued cases. We also show that hardware validation
performed across separate calibration sessions is not comparable: the same circuits
reversed rank between sessions, requiring matched-window measurement. All methods
operate without a parsimony coefficient.

===================================================================
## INTRODUCTION — contributions list (replace existing list)
===================================================================

\noindent Our contributions are:
\begin{itemize}
  \item A controlled comparison, under a single frozen noise model, showing that
  $\varepsilon$-lexicase and tournament selection converge comparably while
  $\varepsilon$-lexicase holds a small but statistically significant paired
  advantage in final fidelity.
  \item Evidence, as a matched-calibration case study, that a size-aware deployment
  rule applied among near-top-fidelity candidates measurably improves hardware
  fidelity, and reduces circuit size on a substantial minority of deployed circuits
  at negligible cost---where circuit-size pressure is applied in the pipeline
  matters.
  \item A mechanistic applicability boundary for lexicographic parsimony (Lexi2):
  applied inside $\varepsilon$-lexicase selection on continuous-valued cases it
  over-applies size pressure, reducing circuit size most but harming convergence
  and hardware fidelity.
  \item A demonstration that all three selection ingredients operate without a
  hand-tuned parsimony coefficient, and that hardware validation across separate
  calibration sessions is not comparable and must be matched-window.
\end{itemize}

===================================================================
## RESULTS — primary paired comparison  (ALREADY INSERTED — verify only)
===================================================================

Already present (Results, "Final-fidelity comparison and effect sizes"). No action
unless the compile shows it missing. For reference the four paragraphs are the
primary paired ε-lexicase-vs-tournament analysis: comparable convergence (Fisher
p=0.21), paired win 52/26/2 Wilcoxon p=0.018 (0.027 w/o extreme pair), sign test
0.004, Cliff's δ +0.23 CI [+0.05,+0.40], MWU 0.012; clustering caveat (per-state
n=10 none significant, state-block permutation 0.0625); variance descriptive
(Brown-Forsythe 0.46, SD-ratio CI spans 1), concentrated on |111>.

===================================================================
## RESULTS — session reversal (methodological finding)
===================================================================

Insert as a Results subsection "Cross-session hardware validation is not comparable",
after Hardware validation:

Our deployed circuits were initially measured on \texttt{ibm\_fez} at their
respective deployment times, weeks apart. Re-measuring the same 24 circuits in a
single back-to-back window (2~September 2026, all within approximately fifteen
minutes) changed the cross-arm ranking. In the original, unmatched measurements the
Lexi2 circuits showed the smallest simulation-to-hardware gap; under matched
calibration this reversed, and Lexi2 showed the largest gap and the lowest mean
hardware fidelity of the three arms. Because the circuits are identical between the
two measurements, the difference is attributable entirely to device calibration
drift between sessions. We therefore report the matched-window session as the valid
cross-arm comparison, retain the original measurements labelled by session for
continuity, and note the methodological implication: hardware validation of
competing methods must be performed within a single calibration window, as
cross-session comparison can reverse the ordering.

===================================================================
## RESULTS — matched-session hardware validation (descriptive)
===================================================================

Insert where the three-arm hardware table is discussed:

Under matched calibration (Table~\ref{tab:hardware}), mean measured hardware
fidelity across the eight deployed circuits was 0.979 for $\varepsilon$-lexicase,
0.975 for tournament, and 0.965 for Lexi2, with mean simulation-to-hardware gaps of
0.008, 0.009, and 0.019 respectively. With one deployed circuit per state and arm
($n=8$), we report these descriptively: $\varepsilon$-lexicase leads on both mean
hardware fidelity and gap, but we make no significance claim across arms. The wider
Lexi2 gap is consistent with, and largely explained by, its circuits being the
smallest and most aggressively size-reduced---leanness reduces exposure to
noise-model mismatch---rather than being an independent property of the selection
method; the matched-session result shows that this leanness did not translate into
better hardware fidelity on this problem.

===================================================================
## RESULTS — |111> deployment counterfactual (REPLACE existing prose)
===================================================================

REPLACE the existing counterfactual subsection prose (the "simulated properties only
/ device recalibrated" version) with:

The deployment rule selects, from each arm's ten runs, the circuit with the highest
simulated fidelity, breaking ties by transpiled two-qubit-gate count, then total
gates, then depth. For $\ket{111}$, the hardest target, this rule selected an
$\varepsilon$-lexicase circuit of transpiled depth~10 and 19~gates, which measured
0.948 in the matched session---the lowest hardware fidelity among the
$\varepsilon$-lexicase deployments. Because fidelity is the primary selection key, a
smaller candidate of near-equal simulated fidelity can be passed over.

To test whether the deployed circuit was avoidably large, we re-ran the deployment
selection offline over the same ten $\ket{111}$ candidates, restricting to those
within 0.01 of the best simulated fidelity and choosing among them by the size
ordering. This size-aware rule selects a different circuit---transpiled depth~4,
8~gates, one two-qubit gate---at a simulated-fidelity cost of 0.002. Measured in the
same calibration window, this smaller circuit reached 0.970 on hardware, 2.2
percentage points above the deployed depth-10 circuit. For this state, therefore,
selecting among near-top-fidelity candidates by circuit size returned a
substantially smaller circuit that also measured higher on hardware. We report this
as a single-state case study; its value is in demonstrating that fidelity-only
deployment can be improved upon by size-aware selection, and in pairing with the
opposite result for size pressure applied inside selection (Section~\ref{sec:lexi2}).

===================================================================
## RESULTS — generalized reselection across 24 slots (NEW paragraph)
===================================================================

Insert immediately after the |111> counterfactual subsection:

The $\ket{111}$ counterfactual is not an isolated case. Applying the same size-aware
reselection offline to all 24 deployed circuits---restricting to candidates within
0.01 simulated fidelity of each slot's best and choosing by transpiled two-qubit
count, then gates, then depth---a strictly smaller circuit exists, and differs from
the deployed choice, in 9 of the 24 slots (Table~\ref{tab:reselection}). The
simulated-fidelity cost of switching is small throughout: median 0.0019, maximum
0.0042. The size reductions are often substantial: for tournament $\ket{011}$, from
transpiled depth~15 (22 gates, 5 two-qubit) to depth~5 (9 gates, 1 two-qubit) at a
cost of 0.004; for $\varepsilon$-lexicase $\ket{111}$, from depth~10 to depth~4 at a
cost of 0.002. Fidelity-only deployment therefore leaves avoidable circuit bloat on
a substantial minority of targets, across all three arms, which a size-aware rule
removes at negligible simulated-fidelity cost. Whether the smaller circuits also
measure higher on hardware was confirmed for $\ket{111}$; for the remaining slots we
report the simulated properties only.

===================================================================
## RESULTS — Lexi2 subsection (applicability boundary)
===================================================================

Insert as the Lexi2 Results subsection (label sec:lexi2):

The Lexi2 arm applies lexicographic parsimony: it runs $\varepsilon$-lexicase over
the eight measured output-state probabilities as cases, then, among the survivors,
breaks ties by circuit size (two-qubit-gate count, then total gates, then depth).
Unlike the scalar formulation it uses no parsimony coefficient; unlike the 3-case
$\varepsilon$-lexicase arm it decides size explicitly rather than through a
size-efficiency objective.

Per-run, Lexi2 converged least reliably of the three arms: 55 of 80 runs reached the
success threshold (68.8\%), against 98.8\% for $\varepsilon$-lexicase and 93.8\% for
tournament (Fisher's exact test, $\varepsilon$-lexicase vs Lexi2 $p<0.0001$;
tournament vs Lexi2 $p=0.0001$; both significant under Holm correction). Its failures
concentrate on the hard, entangled states $\ket{101}$, $\ket{110}$, and $\ket{111}$,
and are predominantly fidelity failures rather than size misses---a different failure
mode from the other arms, whose few non-convergences were size misses. Convergence
was also slower (mean stop generation 58 vs 28 and 34).

At deployment, however, Lexi2 produced the smallest circuits of the three arms: its
best-of-ten deployed circuits averaged 0.4 two-qubit gates, with most states
deploying a zero-two-qubit-gate circuit, against roughly one to one-and-a-half
two-qubit gates for the other arms. This is by construction: the size tiebreak
selects the leanest circuit among fidelity-equivalent candidates. As reported above,
this leanness did not yield better hardware fidelity under matched calibration; Lexi2
measured worst on hardware despite deploying the smallest circuits.

The size tiebreak engages almost immediately: its firing rate rises from roughly
1\% at generation~0 to 43\% at generation~1, exceeds 50\% by generation~2, and
plateaus near 0.85--0.93 through the remainder of evolution (pooled over the first
ten generations, 61\%; Figure~\ref{fig:firerate}). Size therefore decides a majority
of selections from very early, before high fidelity has been secured in most runs.
We note, however, that the firing rate is \emph{not} elevated in the runs that failed
to converge; through every generation in which both groups are active, non-converged
runs show a lower firing rate than converged runs. The mechanism is thus better
described as pervasive early size pressure than as excess size pressure specific to
the failing runs: with continuous-valued cases under MAD-based $\epsilon$, many
individuals clear each case, the post-case survivor pool stays large, and the size
tiebreak---rather than the cases---drives most of selection throughout. This is the
regime in which lexicographic parsimony behaves differently from its intended setting
of small, near-singleton survivor pools, and it locates the applicability boundary:
on continuous-valued cases the tiebreak assumes a role the method was not designed to
give it.

We emphasise that this is a result about \emph{this Lexi2 configuration}. Because the
arm changes two things at once relative to 3-case $\varepsilon$-lexicase---the case
decomposition (eight probability cases vs three objectives) and the size mechanism
(lexicographic tiebreak vs size-efficiency case)---we cannot cleanly attribute the
convergence collapse to the tiebreak alone. A control arm ($\varepsilon$-lexicase on
the same eight cases with the tiebreak disabled) would resolve this and is identified
as future work. The finding we draw is a boundary: lexicographic parsimony applied
inside $\varepsilon$-lexicase selection on continuous-valued cases over-applies size
pressure on this problem.

===================================================================
## DISCUSSION — central paragraph (pipeline placement) — the key idea
===================================================================

Insert as the opening substantive paragraph of the Discussion:

The three arms and the deployment counterfactual are best read together, and they
converge on a single point about \emph{where} circuit-size pressure is applied.
Applied inside selection, as Lexi2's lexicographic tiebreak, size pressure reduced
circuit size most aggressively but harmed both convergence and measured hardware
fidelity. Applied at deployment, among already-evolved near-top-fidelity candidates,
size pressure improved hardware fidelity---on the hardest state by 2.2 percentage
points under matched calibration---and would reduce circuit size on nine of
twenty-four deployed circuits at negligible fidelity cost. The same preference for
smaller circuits is therefore beneficial or harmful depending on the stage of the
pipeline at which it acts: as a selection pressure during evolution it can dominate
before high fidelity is secured, whereas as a post-hoc selection among viable
candidates it removes avoidable circuit bloat at negligible fidelity cost. This
distinction, rather than any single arm's win or loss, is the most useful thing the
comparison yields.

===================================================================
## DISCUSSION — concentration-on-hard-states thread
===================================================================

Insert after the central paragraph:

Several observations concentrate on the hardest, most entangled targets rather than
being distributed across states. Tournament's elevated final-fidelity variance, which
is not significant across the full set of states, is driven almost entirely by
$\ket{111}$ (per-state standard-deviation ratio 5.8$\times$), including a single run
that reached only 0.749. The two largest simulation-to-hardware gaps also occur on
hard targets: the bloated $\varepsilon$-lexicase $\ket{111}$ deployment discussed
above, and the tournament $\ket{011}$ deployment, whose matched-session hardware
fidelity of 0.956 came from a circuit transpiled to depth~15, far larger than the
depth-4 $\varepsilon$-lexicase circuit for the same state. In each case the
underperformance is associated with an unusually large deployed circuit. This is
consistent with the residual non-convergences, which were predominantly size-target
misses rather than fidelity failures on the easier states, and it reinforces the
value of controlling circuit size at deployment.

===================================================================
## DISCUSSION — honest scoping (state-preparation / zero-2Q)
===================================================================

Insert as a scoping paragraph in the Discussion:

A note on interpretation is required. Because each target basis state is specified in
advance, the task is equivalent to preparing a known state, and the evolutionary
search frequently discovers that the full oracle--diffuser structure is unnecessary,
collapsing the circuit toward a shallow state preparation. This is most visible in
the zero-two-qubit-gate circuits deployed by Lexi2 and, for several separable
targets, by the other arms: a marked basis state realised without entangling gates
is single-qubit state preparation. All three arms faced the same task, so the
comparison between them is unaffected; but the results should be read as
hardware-efficient synthesis for known target states, not as unstructured quantum
search or a claim of quantum speedup. The grammar seeds Grover structure as a prior,
and evolution shapes efficient circuits within and around it.

===================================================================
## DISCUSSION — Threats to validity
===================================================================

Insert under a Threats to Validity subsection:

\textbf{Frozen noise model.} All evolutionary runs use a single noise model and
transpilation target captured from \texttt{ibm\_fez}; this removes between-run
calibration drift and makes the arms comparable, but the evolved circuits are tuned
to one device snapshot. \textbf{Cross-session hardware.} As shown above, hardware
comparison across calibration sessions is invalid; our cross-arm hardware claims rest
on the single matched-window session ($n=8$ circuits per arm, reported descriptively).
\textbf{Scale.} All experiments are three-qubit; behaviour at larger sizes, where the
search space and fitness cost grow rapidly, is untested. \textbf{Statistical power.}
The paired fidelity advantage is small and, while significant by rank- and sign-based
tests, is borderline under the most conservative state-clustered permutation
($p=0.055$) and not significant per individual state at ten seeds; we report the full
battery rather than a selected subset. \textbf{Lexi2 attribution.} The Lexi2
configuration changes both case decomposition and size mechanism relative to 3-case
$\varepsilon$-lexicase, so its convergence deficit cannot be attributed to the
tiebreak alone; the control arm is future work. \textbf{Transpile-seed sensitivity.}
A minority of circuits transpile to different sizes under different seeds; we pin the
deployment transpile seed to the fitness-time seed, and report transpiled metrics at
the calibration used.

===================================================================
## CONCLUSION
===================================================================

Insert:

We compared three coefficient-free selection ingredients for evolving
hardware-efficient Grover-target circuits, under a single frozen noise model and with
matched-window hardware validation on \texttt{ibm\_fez}. $\varepsilon$-lexicase and
tournament selection converged comparably, with $\varepsilon$-lexicase holding a
small but significant paired advantage in final fidelity and leading on matched
hardware fidelity. A size-aware deployment rule improved hardware fidelity on the
hardest target as a case study and reduced circuit size on nine of twenty-four
deployed circuits at negligible cost, while a lexicographic-parsimony variant that
applied size pressure inside selection reduced circuit size most but converged and
measured worst---an applicability boundary for lexicographic parsimony on
continuous-valued cases. Taken together, the results indicate that circuit-size
pressure is valuable at deployment but can be counterproductive when it dominates
selection, and that competing methods must be hardware-validated within a single
calibration window. Future work includes an eight-case control arm to separate case
decomposition from the size tiebreak, gated or delayed tiebreak schedules motivated
by the pervasive early size pressure we observe, output-probability and
size-as-case variants, static-$\varepsilon$ comparisons, and scaling beyond three
qubits, where exact noise simulation becomes intractable and classical surrogates may
be required.

===================================================================
## DECLARATIONS  (AUTHOR SUPPLIES — leave as \TODO with these placeholders)
===================================================================

\textbf{Competing interests.} The authors declare no competing interests.
% CONFIRM.

\textbf{Funding.} The authors received no specific funding for this work.
% CONFIRM exact wording with Douglas.

\textbf{Data and code availability.} The grammar, evolved circuits, per-run
diagnostics, hardware results, and analysis code are available at
\TODO{GitHub URL} and archived at \TODO{Zenodo DOI for tag v0.1-frozen-sweep}.
% ACTION BEFORE PUBLIC: rotate/scrub the IBM token from all history; confirm the
% GECCO repository's public status; deposit the tagged release to Zenodo for the DOI.

\textbf{Author contributions.} \TODO{CRediT roles for A. Obidiegwu, D. Mota Dias,
E. Obidiegwu, C. Ryan — confirm with Douglas.}

===================================================================
## NUMBERS TO VERIFY  (agent: flag any mismatch, do not edit prose)
===================================================================

Primary paired (Table 11 / STATS): 52/26/2; Wilcoxon 0.018 (0.027 w/o extreme);
sign 0.004; Cliff δ +0.23 CI [+0.05,+0.40]; MWU 0.012; state-block perm 0.0625;
Brown–Forsythe 0.46; SD 0.0096 / 0.0264; Fisher eps-vs-tour 0.21.

Convergence: eps-lex 79/80 (98.8%), tour 75/80 (93.8%), Lexi2 55/80 (68.8%).
Fisher eps-vs-Lexi2 p<0.0001; tour-vs-Lexi2 p=0.0001 (Holm-significant).
Mean stop gen: eps-lex 28, tour 34, Lexi2 58.

Matched session (2026-09-02) per-arm mean HW fidelity: eps-lex 0.979, tour 0.975,
Lexi2 0.965. Mean gaps: 0.008 / 0.009 / 0.019.
|111> eps-lex deployed matched HW = 0.948 (0.9478); counterfactual seed 29440
matched HW = 0.970 (0.9703); gain 2.2 pp; counterfactual size 4/8/1, sim cost 0.002.
|011> tournament matched HW = 0.956 (0.9559), transpiled depth 15; eps-lex |011>
depth 4.
Lexi2 deployed mean 2Q ~0.4; other arms ~1 to ~1.5.

Reselection (DEPLOYMENT_RESELECTION.md): 9/24 slots change; cost median 0.0019,
max 0.0042; tournament |011> 15/22/5 -> 5/9/1 (+0.0041); eps-lex |111> 10/19/3 ->
4/8/1 (+0.0016).

Lexi2 fire rate (LEXI2_MECHANISM.md): gen0 ~1%, gen1 43%, gen2 >50% (0.545),
gens0–10 pooled 0.614 (conv 0.631 / non-conv 0.576); plateau ~0.85–0.93;
non-converged NOT higher than converged at any active generation.
