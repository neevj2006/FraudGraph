# Decision problem and leakage contract

One row is a transaction observed at event time `time`, with nonnegative amount and optional account/card/device/address/merchant signatures. The target is the dataset's offline binary fraud outcome. An analyst acts after scoring; no payment is blocked automatically.

```text
earlier events -------- event time = prediction time -------- outcome observed later
allowed histories      current transaction fields allowed   label is target only
timestamps < cutoff    current relationships may be shown   never a history feature
```

Real label-observation delays are not provided by the canonical schema. The demo's label is generated offline. Training assumes training labels are known at model-fit time; a real rollout must supply label-availability timestamps and embargo recently unsettled labels. No prior fraud rate or neighbor label enters the implemented features.

| Actual / decision | Investigate | Do not investigate |
|---|---|---|
| Fraud | True positive: potentially recover value | False negative: missed loss |
| Legitimate | False positive: analyst time and customer friction | True negative: no unnecessary work |

The product assumption is a queue of the top 100 transactions per evaluation window, not a validated staffing capacity. For the small demo selection window of 180 events, this is a generous budget. Report K and population size alongside precision@K. API score filters are exploratory and do not replace this experimental policy.

Average precision (reported as PR-AUC) summarizes ranking under class imbalance. Always-positive or always-negative accuracy can look impressive with rare positives. ROC-AUC weights the large true-negative population, whereas the queue's precision and amount captured expose actual investigative workload. The implementation reports sklearn's non-interpolated average precision, not trapezoidal integration of a precision-recall curve.

On labels `[1,0,1,0]` ranked in that order, precision@2 = 1/2, recall@2 = 1/2, and average precision = `(1 + 2/3)/2 = 5/6`. The unit test checks this calculation. For logistic weights `[0.5,-1]`, values `[2,1]` and intercept `-0.2`, the logit is `-0.2` and the probability is about `0.4502`.

Leakage checklist: group equal timestamps; fit scalers only on training; omit current/future events from histories; retain edge direction; never inject labels; keep model selection separate from calibration; derive unseen masks from training IDs only; evaluate test only through the sealed command. An account's five later transactions may contribute to none of its earlier prediction features.

Splits use unique timestamp boundaries at 60% and 80%. The earlier half of validation chooses checkpoints and model family. The later half fits Platt scaling. No test rows enter training tensors. Tests alter future amounts, invert labels and append future graph nodes, then assert unchanged earlier features/predictions.
