"""Local two-organization worker/isolation smoke and a declared API load envelope."""

import concurrent.futures
import json
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path


def main():
    registry = json.loads(Path("artifacts/staging-v2/organizations.json").read_text())
    tokens = {
        c["organization"]: c["token"] for c in registry["credentials"] if c["subject"] == "alice"
    }

    def request(organization, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            "http://127.0.0.1:18004" + path,
            data=data,
            headers={
                "Authorization": "Bearer " + tokens[organization],
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.load(response)

    manifest = json.loads(Path("artifacts/staging-model-v2/manifest.json").read_text())
    event_id = "STAGING-SMOKE-" + uuid.uuid4().hex[:12]
    body = {
        "events": [
            {
                "id": event_id,
                "time": manifest["history_cutoff"] + 60,
                "amount": 125,
                "account": "staging-smoke",
            }
        ]
    }
    jobs, latency = {}, {}
    for organization in ["north", "south"]:
        job = request(organization, "/v1/jobs", body)["id"]
        jobs[organization] = job
        if organization == "north":
            try:
                request("south", "/v1/jobs/" + job)
                raise AssertionError("Cross-organization job visible")
            except urllib.error.HTTPError as exc:
                assert exc.code == 404
        for attempt in range(120):
            result = request(organization, "/v1/jobs/" + job)
            if result["status"] != "queued":
                assert result["status"] == "completed", result["status"]
                latency[organization] = result["result"]["latency_ms"]
                break
            if attempt % 20 == 0:
                print(f"Waiting for {organization} full-history worker job", flush=True)
            time.sleep(1)
        else:
            raise AssertionError("Worker exceeded 120-second smoke budget")
        alert = request(organization, "/v1/alerts/" + event_id)
        assert alert["model_version"] == manifest["version"]
        assert (
            request(organization, "/v1/alerts/" + event_id + "/graph")["cutoff"]
            == body["events"][0]["time"]
        )

    # 200 requests, 20 clients, equal traffic per organization; no production extrapolation.
    def measured(index):
        start = time.perf_counter()
        request("north" if index % 2 == 0 else "south", "/v1/alerts?limit=30")
        return (time.perf_counter() - start) * 1000

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
        times = sorted(pool.map(measured, range(200)))
    p95 = times[int(0.95 * (len(times) - 1))]
    assert p95 < 2000, f"Local p95 budget exceeded: {p95:.1f}ms"
    result = {
        "organizations": 2,
        "worker_jobs_completed": 2,
        "worker_scoring_ms": latency,
        "cross_organization_job_probe": "404",
        "load": {"requests": 200, "concurrency": 20, "errors": 0, "p95_ms": p95, "budget_ms": 2000},
        "scope": "Local staging observation; not an internet-facing production SLA",
    }
    Path("docs/results/staging-v2.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    Path("artifacts/staging-v2/verified-jobs.json").write_text(json.dumps(jobs), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
