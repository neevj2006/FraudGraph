import type { components } from "./schema";
export type Score = components["schemas"]["AlertScore"];
export type Case = components["schemas"]["CaseRecord"];
export type Detail = components["schemas"]["AlertDetail"];
export type Graph = components["schemas"]["EvidenceGraph"];
export type Queue = components["schemas"]["AlertQueue"];
export type Manifest = {version: string; selected: string; dataset: string; dataset_sha256: string; code_sha256: string; seeds: number[]; graph_schema: string; calibration: string; features: string[]; policy: {top_k: number}};
export async function api<T>(path: string, token: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`/api/v1/${path}`, {headers: {Authorization: `Bearer ${token}`, "Content-Type": "application/json"}, method: body ? "POST" : "GET", body: body ? JSON.stringify(body) : undefined, signal});
  if (!response.ok) { const data = await response.json().catch(() => ({})); throw new Error(typeof data.detail === "string" ? data.detail : `Request failed (${response.status})`); }
  return response.json();
}
