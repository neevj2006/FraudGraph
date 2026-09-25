"""Causal transaction projection plus typed evidence graph.

Message-passing edges go from earlier transactions to later transactions. This
prevents shared entity embeddings from carrying future information backwards.
"""

import hashlib
from collections import defaultdict

import numpy as np
import pandas as pd

from ml.data.dataset import ENTITIES


def node_id(kind, value):
    return f"{kind}:" + hashlib.sha256(str(value).encode()).hexdigest()[:20]


def causal_edges(df, neighbors=8, omit=None):
    history = defaultdict(list)
    edges, relations = [], []
    for _, group in df.groupby("time", sort=True):
        for idx, row in group.iterrows():
            for rel, kind in enumerate(ENTITIES):
                if row[kind] is None or kind == omit:
                    continue
                for old in history[(kind, row[kind])][-neighbors:]:
                    edges.append((old, idx))
                    relations.append(rel)
        for idx, row in group.iterrows():
            for kind in ENTITIES:
                if row[kind] is not None:
                    history[(kind, row[kind])].append(idx)
    return (np.array(edges, dtype=np.int64).reshape(-1, 2).T, np.array(relations, dtype=np.int64))


def evidence(df, transaction_id, limit=60):
    selected = df[df.id == transaction_id]
    if selected.empty:
        raise KeyError(transaction_id)
    row = selected.iloc[0]
    past = df[df.time < row.time]
    matched = set()
    patterns = []
    for kind in ENTITIES:
        if row[kind] is None:
            continue
        neighbors = past[past[kind] == row[kind]]
        matched.update(neighbors.index)
        if len(neighbors):
            patterns.append(
                f"{kind.title()} signature appears in {len(neighbors)} earlier transactions "
                f"across {neighbors.account.nunique()} account signatures."
            )
    ordered = sorted(matched, key=lambda i: (df.loc[i, "time"], df.loc[i, "id"]), reverse=True)
    subset = df.loc[ordered[:limit]]
    nodes, edges = {}, []
    for _, tx in pd.concat([selected, subset]).iterrows():
        tid = node_id("transaction", tx.id)
        nodes[tid] = {
            "id": tid,
            "type": "transaction",
            "label": tx.id,
            "focal": tx.id == transaction_id,
            "time": float(tx.time),
        }
        for kind in ENTITIES:
            if tx[kind] is None:
                continue
            eid = node_id(kind, tx[kind])
            nodes.setdefault(
                eid, {"id": eid, "type": kind, "label": f"{kind} · {eid[-6:]}", "focal": False}
            )
            edges.append(
                {
                    "id": f"{tid}-{eid}",
                    "source": tid,
                    "target": eid,
                    "type": kind,
                    "time": float(tx.time),
                    "provenance": "canonical-event-v1",
                    "rule": "observed-signature-association",
                }
            )
    return {
        "schema_version": "1",
        "cutoff": float(row.time),
        "nodes": list(nodes.values()),
        "edges": edges,
        "patterns": patterns or ["No earlier shared identifiers were observed."],
        "truncated": len(ordered) > limit,
        "historical_transactions": len(ordered),
        "attribution": "Observed relational evidence; not model attribution or causal proof.",
    }
