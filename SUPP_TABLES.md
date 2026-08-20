# SUPP_TABLES — LaTeX-ready supplementary tables

Assembled 2026-08-11 from existing aggregates, diagnostics, hardware JSONs and the calibration CSV. No experiments were re-run. Seed column order: 21315, 47182, 12147, 33537, 70300.

## Table 1 — Epsilon-lexicase pop300 per-seed final fidelity

\begin{tabular}{lccccc}
\hline
State & 21315 & 47182 & 12147 & 33537 & 70300 \\
\hline
$\ket{000}$ & \textbf{0.982} & 0.947 & \textbf{0.985} & \textbf{0.987} & \textbf{0.986} \\
$\ket{001}$ & \textbf{0.988} & \textbf{0.986} & 0.502 & \textbf{0.986} & 0.509 \\
$\ket{010}$ & \textbf{0.982} & \textbf{0.986} & \textbf{0.986} & \textbf{0.991} & \textbf{0.985} \\
$\ket{011}$ & 0.495 & \textbf{0.985} & \textbf{0.989} & \textbf{0.980} & 0.493 \\
$\ket{100}$ & \textbf{0.986} & \textbf{0.987} & 0.485 & \textbf{0.990} & \textbf{0.983} \\
$\ket{101}$ & \textbf{0.987} & 0.495 & 0.491 & \textbf{0.986} & \textbf{0.989} \\
$\ket{110}$ & \textbf{0.969} & \textbf{0.962} & 0.505 & 0.510 & \textbf{0.986} \\
$\ket{111}$ & \textbf{0.951} & \textbf{0.961} & \textbf{0.982} & \textbf{0.985} & \textbf{0.990} \\
\hline
\end{tabular}

*Values \geq 0.95 in bold.*

## Table 2 — Tournament pop300 per-seed final fidelity (verified)

\begin{tabular}{lccccc}
\hline
State & 21315 & 47182 & 12147 & 33537 & 70300 \\
\hline
$\ket{000}$ & \textbf{0.977} & \textbf{0.978} & \textbf{0.980} & \textbf{0.981} & 0.578 \\
$\ket{001}$ & \textbf{0.987} & \textbf{0.977} & \textbf{0.969} & \textbf{0.986} & 0.507 \\
$\ket{010}$ & \textbf{0.978} & \textbf{0.980} & 0.501 & 0.509 & 0.497 \\
$\ket{011}$ & \textbf{0.978} & \textbf{0.975} & 0.550 & 0.490 & \textbf{0.958} \\
$\ket{100}$ & 0.506 & \textbf{0.979} & \textbf{0.962} & \textbf{0.978} & 0.487 \\
$\ket{101}$ & 0.489 & 0.492 & \textbf{0.967} & 0.482 & 0.547 \\
$\ket{110}$ & 0.481 & \textbf{0.980} & \textbf{0.977} & 0.511 & 0.483 \\
$\ket{111}$ & \textbf{0.961} & \textbf{0.987} & 0.485 & \textbf{0.977} & 0.500 \\
\hline
\end{tabular}

**Verification: no substantive mismatches.** state 011/seed 33537: claimed 0.490, exact 0.4905; state 101/seed 21315: claimed 0.489, exact 0.4895; state 110/seed 33537: claimed 0.511, exact 0.5115; state 111/seed 21315: claimed 0.961, exact 0.9605 — these sit exactly on the 3rd-decimal rounding boundary (half-way cases).

## Table 3 — Stop-reason counts (per state, 5 runs; reasons normalized)

### epsilon-lexicase pop300

\begin{tabular}{lccccc}
\hline
State & Hardware targets achieved & Fidelity stagnant & Hardware metrics stagnant & completed_all_generations & Unknown \\
\hline
$\ket{000}$ & 4 & 1 & 0 & 0 & 0 \\
$\ket{001}$ & 3 & 2 & 0 & 0 & 0 \\
$\ket{010}$ & 5 & 0 & 0 & 0 & 0 \\
$\ket{011}$ & 2 & 2 & 1 & 0 & 0 \\
$\ket{100}$ & 4 & 1 & 0 & 0 & 0 \\
$\ket{101}$ & 3 & 2 & 0 & 0 & 0 \\
$\ket{110}$ & 3 & 2 & 0 & 0 & 0 \\
$\ket{111}$ & 4 & 0 & 1 & 0 & 0 \\
\hline
\end{tabular}

### tournament pop300

\begin{tabular}{lccccc}
\hline
State & Hardware targets achieved & Fidelity stagnant & Hardware metrics stagnant & completed_all_generations & Unknown \\
\hline
$\ket{000}$ & 4 & 1 & 0 & 0 & 0 \\
$\ket{001}$ & 4 & 1 & 0 & 0 & 0 \\
$\ket{010}$ & 2 & 3 & 0 & 0 & 0 \\
$\ket{011}$ & 3 & 2 & 0 & 0 & 0 \\
$\ket{100}$ & 3 & 2 & 0 & 0 & 0 \\
$\ket{101}$ & 1 & 4 & 0 & 0 & 0 \\
$\ket{110}$ & 2 & 3 & 0 & 0 & 0 \\
$\ket{111}$ & 3 & 2 & 0 & 0 & 0 \\
\hline
\end{tabular}

## Table 4 — Hardware job metadata (deployed best-fidelity circuit per state)

\begin{tabular}{lcccccl}
\hline
Method & State & Seed & Job ID & Timestamp & Transpiled D/G & p\_marked \\
\hline
epsilon-lexicase & $\ket{000}$ & 33537 & \texttt{d9h3du8gk0ls73f2eig0} & 2026-07-23T16:45:09 & 5/11 & 0.9766 \\
epsilon-lexicase & $\ket{001}$ & 21315 & \texttt{d9is2tjhdfks73chf9jg} & 2026-07-26T09:26:01 & 4/9 & 0.9837 \\
epsilon-lexicase & $\ket{010}$ & 33537 & \texttt{d9h3a0bsbqfc73epgjh0} & 2026-07-23T16:36:44 & 5/8 & 0.9803 \\
epsilon-lexicase & $\ket{011}$ & 12147 & \texttt{d9j4f4rjf64c739g9us0} & 2026-07-26T18:58:56 & 2/5 & 0.9771 \\
epsilon-lexicase & $\ket{100}$ & 33537 & \texttt{d9j4f80ii2cc73eeacag} & 2026-07-26T18:59:14 & 3/5 & 0.9902 \\
epsilon-lexicase & $\ket{101}$ & 70300 & \texttt{d9q6oc17s9kc73ausk70} & 2026-08-07T09:15:33 & 5/9 & 0.9827 \\
epsilon-lexicase & $\ket{110}$ & 70300 & \texttt{d9j4ifibr2fc73e5er6g} & 2026-08-11T08:34:21 & 5/9 & 0.9767 \\
epsilon-lexicase & $\ket{111}$ & 70300 & \texttt{d9q6oc17s9kc73ausk7g} & 2026-08-07T09:15:33 & 5/9 & 0.9742 \\
tournament & $\ket{000}$ & 33537 & \texttt{d9r3i6fpemts73cs37jg} & 2026-08-07T21:53:59 & 5/11 & 0.9773 \\
tournament & $\ket{001}$ & 21315 & \texttt{d9r84lvpemts73cs99n0} & 2026-08-08T02:12:05 & 4/9 & 0.9765 \\
tournament & $\ket{010}$ & 47182 & \texttt{d9r82i9dsedc73agaglg} & 2026-08-08T02:07:35 & 7/13 & 0.9712 \\
tournament & $\ket{011}$ & 21315 & \texttt{d9r6cvpdsedc73ag8hdg} & 2026-08-08T00:13:14 & 5/10 & 0.9661 \\
tournament & $\ket{100}$ & 47182 & \texttt{d9r56tftfhrs73dr76ig} & 2026-08-11T08:34:20 & 5/10 & 0.9720 \\
tournament & $\ket{101}$ & 12147 & \texttt{d9r6fqgpdb6s73e4gu70} & 2026-08-08T00:19:15 & 8/12 & 0.9595 \\
tournament & $\ket{110}$ & 47182 & \texttt{d9r1tthdsedc73ag263g} & 2026-08-11T08:34:20 & 6/10 & 0.9750 \\
tournament & $\ket{111}$ & 47182 & \texttt{d9r676vtfhrs73dr8g5g} & 2026-08-08T00:06:42 & 4/8 & 0.9719 \\
\hline
\end{tabular}


Provenance: lexicase |101> and |111> are August re-deployments with the deployed run's own seed; lexicase |110> was restored from its July job (d9j4ifibr2fc73e5er6g); tournament |100>/|110> were recovered from jobs d9r56tftfhrs73dr76ig / d9r1tthdsedc73ag263g. Remaining rows are the original July (lexicase) / August (tournament) runs.

## Table 5 — ibm_fez calibration, July vs August sweep windows

\begin{tabular}{lccc}
\hline
Metric & July & August & Delta \\
\hline
T1 median (us) & 119.27624 & 133.43488 & +14.158637 \\
T2 median (us) & 91.903511 & 97.585813 & +5.6823022 \\
readout error median & 0.009185791 & 0.0083618164 & -0.00082397461 \\
1Q gate error median (sx/x) & 0.00030028571 & 0.00030871505 & +8.4293442e-06 \\
2Q gate error median (ECR) & 0.0028126803 & 0.0030202916 & +0.00020761129 \\
2Q gate error mean & 0.033121766 & 0.033172488 & +5.0721981e-05 \\
\hline
\end{tabular}

## Table 6 — Mechanism numbers: verification against source diagnostics

\begin{tabular}{llll}
\hline
Metric & Claimed & Recomputed & Match \\
\hline
Diversity converged (\% of pop) & lex 70.3\% / tour 79.2\% & lex 70.3\% (mean 211.0/300) / tour 79.2\% (mean 237.6/300) & OK \\
Diversity failed (\% of pop) & lex 66.9\% / tour 76.4\% & lex 66.9\% (mean 200.7/300) / tour 76.4\% (mean 229.2/300) & OK \\
Failed crossing $\geq$ 0.6 & lex 0\% / tour 24\% & lex 0\% (n=8) / tour 24\% (n=17) & OK \\
Failed mean peak fid & lex 0.549 / tour 0.614 & lex 0.5485 / tour 0.6141 & OK \\
Failed median peak fid & lex 0.563 / tour 0.583 & lex 0.5625 / tour 0.5828 & OK \\
Mann-Whitney p & 0.17 & 0.1747 (n=8 vs 17) & OK \\
\hline
\end{tabular}

Recomputation detail:
- converged n: lex 32 / tour 23; failed n: lex 8 / tour 17
- failed peak max (lex): 0.5928; failed peak max (tour): 0.8713
