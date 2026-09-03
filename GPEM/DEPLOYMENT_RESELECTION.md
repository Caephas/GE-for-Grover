# DEPLOYMENT_RESELECTION — size-aware reselection across all 24 slots

Rule applied offline to each slot's 10 saved candidates: restrict to candidates within 0.01 of the slot's best simulated fidelity, then pick by fewest transpiled 2Q gates -> total transpiled gates -> depth; size ties are broken toward higher simulated fidelity (equivalently: a swap counts only when it strictly reduces the transpiled 2Q/gates/depth tuple). Deployed = current lambda-free rule (max fidelity -> min 2Q -> min gates -> min depth); computed deployed seeds were verified to match `deployed_best.json` for all 24 slots. Simulated properties only; no hardware.

## Per-slot comparison

| Arm | State | Deployed seed | Deployed sim | Deployed D/G/2Q | Alt seed | Alt sim | Alt D/G/2Q | Changed | Cost (sim) |
|---|---|---|---|---|---|---|---|---|---|
| epsilon_lexicase | 000 | 47182 | 0.9898 | 1/3/0 | 47182 | 0.9898 | 1/3/0 | no | 0.0000 |
| epsilon_lexicase | 001 | 12147 | 0.9901 | 2/4/0 | 12147 | 0.9901 | 2/4/0 | no | 0.0000 |
| epsilon_lexicase | 010 | 33537 | 0.9818 | 5/8/1 | 33537 | 0.9818 | 5/8/1 | no | 0.0000 |
| epsilon_lexicase | 011 | 47182 | 0.9801 | 4/8/1 | 47182 | 0.9801 | 4/8/1 | no | 0.0000 |
| epsilon_lexicase | 100 | 29440 | 0.9881 | 5/8/0 | 12147 | 0.9845 | 2/4/0 | yes | 0.0036 |
| epsilon_lexicase | 101 | 80248 | 0.9895 | 3/6/0 | 74135 | 0.9887 | 2/5/0 | yes | 0.0008 |
| epsilon_lexicase | 110 | 33537 | 0.9859 | 2/6/0 | 33537 | 0.9859 | 2/6/0 | no | 0.0000 |
| epsilon_lexicase | 111 | 12147 | 0.9814 | 10/19/3 | 29440 | 0.9798 | 4/8/1 | yes | 0.0016 |
| tournament | 000 | 80248 | 0.9895 | 1/3/0 | 80248 | 0.9895 | 1/3/0 | no | 0.0000 |
| tournament | 001 | 80248 | 0.9881 | 2/5/0 | 80248 | 0.9881 | 2/5/0 | no | 0.0000 |
| tournament | 010 | 80248 | 0.9846 | 3/5/0 | 80248 | 0.9846 | 3/5/0 | no | 0.0000 |
| tournament | 011 | 70300 | 0.9797 | 15/22/5 | 80248 | 0.9756 | 5/9/1 | yes | 0.0041 |
| tournament | 100 | 80248 | 0.9883 | 2/4/0 | 80248 | 0.9883 | 2/4/0 | no | 0.0000 |
| tournament | 101 | 47182 | 0.9819 | 5/8/2 | 29440 | 0.9800 | 5/10/1 | yes | 0.0019 |
| tournament | 110 | 12147 | 0.9793 | 6/10/2 | 74135 | 0.9752 | 3/6/1 | yes | 0.0041 |
| tournament | 111 | 67154 | 0.9794 | 5/8/2 | 33537 | 0.9752 | 5/10/1 | yes | 0.0042 |
| lexi2 | 000 | 47182 | 0.9834 | 2/5/0 | 47182 | 0.9834 | 2/5/0 | no | 0.0000 |
| lexi2 | 001 | 33537 | 0.9819 | 7/12/2 | 74135 | 0.9801 | 3/6/1 | yes | 0.0018 |
| lexi2 | 010 | 80248 | 0.9851 | 3/5/0 | 80248 | 0.9851 | 3/5/0 | no | 0.0000 |
| lexi2 | 011 | 91197 | 0.9887 | 2/5/0 | 91197 | 0.9887 | 2/5/0 | no | 0.0000 |
| lexi2 | 100 | 29440 | 0.9869 | 3/6/0 | 29440 | 0.9869 | 3/6/0 | no | 0.0000 |
| lexi2 | 101 | 21315 | 0.9820 | 3/7/0 | 21315 | 0.9820 | 3/7/0 | no | 0.0000 |
| lexi2 | 110 | 21315 | 0.9805 | 6/11/1 | 33537 | 0.9803 | 4/9/1 | yes | 0.0002 |
| lexi2 | 111 | 21315 | 0.9876 | 3/7/0 | 21315 | 0.9876 | 3/7/0 | no | 0.0000 |

## Summary

- Slots where a strictly size-smaller pick exists within 0.01 fidelity and differs from the deployed pick: **9 / 24**.
- Simulated-fidelity cost when changed: min 0.0002, median 0.0019, mean 0.0025, max 0.0042.
- Changed slots: epsilon_lexicase 100 (+0.0036), epsilon_lexicase 101 (+0.0008), epsilon_lexicase 111 (+0.0016), tournament 011 (+0.0041), tournament 101 (+0.0019), tournament 110 (+0.0041), tournament 111 (+0.0042), lexi2 001 (+0.0018), lexi2 110 (+0.0002).

