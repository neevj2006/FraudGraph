# Dataset decision and acquisition

**Chosen public benchmark: IEEE-CIS Fraud Detection.** A separate synthetic fixture supports deterministic tests and product demonstrations.

| Candidate | Useful properties | Limitations |
|---|---|---|
| IEEE-CIS | Labeled transactions; relative event times; card/address/device signatures; payment fraud task | Kaggle sign-in and accepted competition rules; ambiguous identities; labels delayed in practice; large CPU workload |
| AMLSim HI-Small | Publicly described simulated money transfers with temporal account relationships | AML simulation rather than card fraud; no actual device/card identifiers; third-party mirrors require provenance/license verification |

The [official IEEE-CIS data page](https://www.kaggle.com/c/ieee-fraud-detection/data) states that access requires accepting the competition rules. Download `train_transaction.csv` and `train_identity.csv` from your authorized account. Do not use the competition's unlabeled test file as this project's chronological labeled holdout. Do not redistribute source rows, model-derived raw identifiers, or restricted files through GitHub.

`import-ieee` records original filenames, byte sizes, SHA-256 checksums, source URL, license notes, and a canonical audit. Preserve the raw files unchanged. Record your retrieval date and accepted rule version alongside `source-manifest.json`; redistribution permission cannot be inferred from a public mirror.

Mapping:

- `TransactionID` â†’ stable transaction ID; `TransactionDT` â†’ relative seconds, not a fabricated calendar date.
- `TransactionAmt` â†’ amount; `isFraud` â†’ offline target.
- card fields â†’ card signature. `card1 + addr1 + P_emaildomain` â†’ account-like signature, explicitly not verified identity.
- `DeviceType + DeviceInfo` â†’ device signature. These may be very coarse and must not be described as hardware fingerprints.
- `addr1 + addr2` â†’ address signature. Merchant remains absent because there is no defensible merchant identity in the selected mapping.

Missing identifiers remain absent. No synthetic account/device relationships are invented for the public data. The canonical schema validates ID uniqueness, required fields, finite nonnegative times/amounts and binary labels. Audit outputs show missingness, signature cardinality, prevalence, time range and amount quantiles.

The synthetic generator has its own deterministic checksum and seed. It includes independent low-rate fraud, shared infrastructure with elevated fraud probability, missing device signatures, new accounts over time, and a legitimate public terminal. Its labels are probabilistic by design and are never used by graph construction.

Public-data acquisition and full canonical import completed on 2026-09-13: 590,540 rows, 3.499% fraud labels, 76.148% missing device signatures. The source audit is recorded in docs/results/ieee-source-audit.json. Three-seed training and once-only final evaluation are complete for the predeclared 10,000-row chronological cohort; see docs/ieee-results.md. Full-data tabular and graph training/evaluation are now recorded in [the combined graph comparison](scaled-gnn-results.md); the prior tabular inspection of the final window is disclosed.
