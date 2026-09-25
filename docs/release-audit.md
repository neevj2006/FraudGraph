ï»¿# Local release audit

This audit covers the local research release. GitHub publication, remote CI execution and production deployment are separate actions and have not occurred.

| Check | Evidence | Result |
|---|---|---|
| Backend correctness | 27 tests, including PostgreSQL, graph cutoff invariance, batched prediction/gradient parity and case authorization | Passed |
| Python source quality | Ruff lint and formatting | Passed |
| Python dependencies | Locked resolution and installed-package compatibility check | Passed; not a Python advisory scan |
| Browser dependencies | Production npm audit | Zero reported known vulnerabilities at audit time |
| Clean-source build | 130 eligible files staged without environments, data, weights or credentials; API and web images built from that folder | Passed |
| Source identity | 51 runtime/configuration files compared with the clean build | Identical |
| Clean training | Fresh 900-row, three-seed, eight-epoch synthetic smoke run in the clean API image | Passed |
| Public-data browser | Investigation, source units, provenance, filters, pagination, export and mobile layout | Passed against clean-built images |
| Synthetic browser | Five full investigator workflows against clean-built images | Passed; updated synthetic screenshots/video retained |
| Durable worker | Public-cohort job scored by clean worker image | Passed |
| Restart persistence | Saved case and completed job survived clean API restart | Passed |
| Data/artifact exclusions | Git-eligible inventory excludes source data, vectors, model artifacts, local environment and browser test media | Passed |
| Frozen bundles | Synthetic, public cohort, full tabular and full GNN bundle hashes | All four verified |
| GNN scale capacity | 10k, 50k, 100k and full-data stages under a 2 GiB container limit | Passed |
| Full GNN experiment | Three seeds per family, frozen validation choice, then full held-out comparison | Passed under 2 GiB; prior tabular test inspection disclosed |

The first public browser attempt began before the clean API finished initial evidence population and failed to load the queue. After readiness was confirmed, the same workflow passed. Fresh evidence population can take minutes under CPU contention; callers must wait for `/ready`. This is a research deployment, not an instant-start or production throughput claim.

Runtime images contain the scaling package. The serving application remains on its separate compatible cohort artifact; larger offline comparisons do not silently change investigator cases or model versions.

## Intentional exclusions

- CI results cover local runs; remote CI has not run.
- Independent analyst utility, production identity management, public hosting and automated adverse decisions are outside this local research release.
- The later full-data test window was previously inspected for tabular models. The GNN evaluation is a subsequent held-out comparison and must disclose that history.
- Source and artifact inventory checks are not a comprehensive security audit. Dependency findings are time-specific observations.

Machine-readable inventory is in `docs/results/release-inventory.json`; detailed numerical experiments are linked from the README and model card.

Experiment completion: the full-data graph experiment and source/artifact inventory completed on September 16, 2026. The offline research choice and aggregate evaluation are in [the GNN report](scaled-gnn-results.md). No data or model weights were added to the publication inventory.
