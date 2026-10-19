/** GitHub Actions helpers for WrestlingCentralNews/wcn update.yml.
 * Auth: env.GITHUB_TOKEN — fine-grained PAT, repo-only, Actions: Read and write.
 * Never log or return the token.
 */
const GH_REPO = "WrestlingCentralNews/wcn";
const WORKFLOW = "update.yml";
const API = `https://api.github.com/repos/${GH_REPO}`;

function headers(token) {
  return {
    Accept: "application/vnd.github+json",
    Authorization: `Bearer ${token}`,
    "User-Agent": "WCN-cfworker/1.0",
    "X-GitHub-Api-Version": "2022-11-05",
  };
}

/** Active (not completed) update.yml runs. */
export async function activeRuns(token) {
  const url = `${API}/actions/workflows/${WORKFLOW}/runs?per_page=15`;
  const r = await fetch(url, { headers: headers(token) });
  if (!r.ok) throw new Error(`gh runs list HTTP ${r.status}`);
  const j = await r.json();
  const active = new Set(["queued", "in_progress", "pending", "waiting", "requested"]);
  return (j.workflow_runs || [])
    .filter((x) => active.has(x.status))
    .map((x) => ({
      id: x.id,
      status: x.status,
      event: x.event,
      created: Date.parse(x.created_at) / 1000,
    }));
}

/**
 * workflow_dispatch runs of update.yml created in the last `windowS` seconds.
 * Shared hourly cap source of truth for both this Worker and the box watcher.
 */
export async function recentDispatches(token, windowS = 3600) {
  const url = `${API}/actions/workflows/${WORKFLOW}/runs?event=workflow_dispatch&per_page=40`;
  const r = await fetch(url, { headers: headers(token) });
  if (!r.ok) throw new Error(`gh dispatches list HTTP ${r.status}`);
  const j = await r.json();
  const since = Date.now() / 1000 - windowS;
  return (j.workflow_runs || [])
    .map((x) => ({ id: x.id, created: Date.parse(x.created_at) / 1000, status: x.status }))
    .filter((x) => x.created >= since);
}

/** Trigger update.yml via workflow_dispatch. */
export async function dispatchUpdate(token) {
  const url = `${API}/actions/workflows/${WORKFLOW}/dispatches`;
  const r = await fetch(url, {
    method: "POST",
    headers: { ...headers(token), "Content-Type": "application/json" },
    body: JSON.stringify({ ref: "main" }),
  });
  if (r.status !== 204 && r.status !== 200) {
    const t = await r.text().catch(() => "");
    throw new Error(`gh dispatch HTTP ${r.status}: ${t.slice(0, 200)}`);
  }
  return true;
}
