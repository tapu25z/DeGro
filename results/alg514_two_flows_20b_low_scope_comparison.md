# ALG514 scope comparison

Snapshot: 2026-10-03T12:21:16.371519+07:00. Only cases completed by both flows are compared.

| Scope | Paired cases | Direct | ModelSpec -> Z3 |
|---|---:|---:|---:|
| all | 176 | 170/176 (96.59%) | 162/176 (92.05%) |
| exclude_minmax_threshold | 172 | 166/172 (96.51%) | 162/172 (94.19%) |
| exclude_minmax_threshold_and_resource_limits | 170 | 164/170 (96.47%) | 162/170 (95.29%) |

## Source-based exclusions

- alg514/657: Earliest radio-contact loss time at a distance threshold.
- alg514/1035: Minimum sales to meet an at-least earnings requirement.
- alg514/1119: Maximum mileage within a budget.
- alg514/2031: Maximum mileage within a budget.
- alg514/15: Page/word resource limits without explicit exact usage; gold assumes exact usage.
- alg514/2120: Production resource allocations without explicit exact usage or an optimization objective; gold assumes exact usage.

## Remaining ModelSpec-to-Z3 failures

| Case | Cause |
|---|---|
| alg514/155 | Invalid && / || syntax; longer/shorter roles are also unfixed. |
| alg514/580 | Minutes incorrectly declared Int; released answer is 28.08. |
| alg514/1089 | Cork/wine relation mistranslated; 0.10 instead of 0.05. |
| alg514/1532 | Subtraction reversed relative to gold; 3 instead of -4.5. |
| alg514/2074 | Both directions of an asymmetric relation asserted, causing inconsistency. |
| alg514/2075 | Added x<=y contradicts the roles used in 3*x=4*y+2. |
| alg514/2196 | Both flows convert to mph correctly; gold remains in km/h. |
| alg514/2247 | Thirty total coins mistranslated as thirty nickels. |

Metrics are ALG514-compatible answer matching, not ordered semantic correctness. These exclusions were reviewed after outcomes were seen; report as scope sensitivity and retain the unfiltered comparison. The model run continues, so later results may differ.
