# WCN Cloudflare Worker watcher

Always-on 2-minute source poller. Same job as `watcher/wcn_watch.py` on the box: conditional-GET the site's feeds and listing pages, and when a new **trusted** (editorial tier 1–2) item appears, `workflow_dispatch` `update.yml` on `WrestlingCentralNews/wcn`.

Exists so builds still fire while the box VM is paused (nothing on the box runs then).

## How it coordinates with the box watcher

Both sides, before dispatching:

1. List active `update.yml` runs. If one is queued / in progress and was created after the item was seen, treat the items as **covered** (no extra dispatch). If anything is already queued, wait.
2. Count `workflow_dispatch` runs of `update.yml` in the last hour via the GitHub API. Shared cap: **20/hour**, **60s** minimum gap.

So a race at most queues a second run behind the concurrency group `wcn-update` (1 running + 1 waiting). They do **not** share seen-item state; duplicate detection is fine because a covered/queued run absorbs the second trigger.

## Free-plan budget

| Resource | Free limit | This worker |
| --- | --- | --- |
| Cron `*/2 * * * *` | 100k req/day | ~720/day |
| KV writes | 1,000/day | 1 key (`watcher`), written **only on change** (+ a 30‑min heartbeat) |
| Subrequests / invocation | 50 | ~15–30 (source GETs + ≤2 GitHub + ≤2 KV) |
| CPU / invocation | 10 ms | Parse at most 4 changed bodies per tick; Google News feeds rotate every other cycle; 304s skip parse |

If cron starts hitting Error 1102 (CPU), either trim sources further or move the account to Workers Paid ($5/mo → 30s cron CPU).

## Files

```
cfworker/
  wrangler.toml          # name, cron, KV binding (id filled at deploy)
  package.json
  src/index.js           # scheduled + /health + /run
  src/sources.js         # FEEDS + LISTINGS snapshot
  src/editorial.js       # tier + verdict (title DROP rules)
  src/rss.js             # RSS/Atom + fnv1a
  src/pages.js           # listing-page link extractor
  src/github.js          # active runs, recent dispatches, dispatch
  test/*.test.js
  README.md
```

## One-time setup (do not deploy until the Cloudflare account exists)

### 1. Cloudflare API token (minimal)

Create at https://dash.cloudflare.com/profile/api-tokens → **Create Token** → custom:

| Scope | Permission |
| --- | --- |
| Account · Workers Scripts | **Edit** |
| Account · Workers KV Storage | **Edit** |
| Account · Account Settings | **Read** |

(That set is what `wrangler deploy` + `wrangler kv namespace create` need. Do **not** grant Users/Billing/Zone DNS unless you need them elsewhere.)

```bash
export CLOUDFLARE_API_TOKEN=...      # the token above
export CLOUDFLARE_ACCOUNT_ID=...     # Overview → Account ID
```

### 2. KV namespace

```bash
cd cfworker
npm install
npx wrangler kv namespace create WCN_WATCHER
```

Copy the printed `id` into `wrangler.toml`:

```toml
[[kv_namespaces]]
binding = "STATE"
id = "PASTE_ID_HERE"
```

### 3. GitHub fine-grained PAT (Worker secret)

Create at https://github.com/settings/personal-access-tokens/new:

- Resource owner: **WrestlingCentralNews**
- Only repository: **wcn**
- Permissions: **Actions: Read and write** (contents not required)
- Expiration: your choice (90 days is fine; rotate before it lapses)

Do **not** reuse the box `gh` OAuth token. Do **not** commit the PAT.

```bash
npx wrangler secret put GITHUB_TOKEN
# paste the fine-grained PAT when prompted
```

### 4. Deploy

```bash
cd cfworker
npm install
npx wrangler deploy
```

Cron `*/2 * * * *` is in `wrangler.toml` and activates with the deploy. Confirm:

```bash
npx wrangler tail
curl -s https://wcn-watcher.<your-subdomain>.workers.dev/health
```

`/health` returns `last_run`, `last_trigger`, `cycle`, `pending`, `last_poll_stats` — **no secrets**.

### 5. Optional: keep sources in sync

`src/sources.js` is a snapshot of `aggregator.FEEDS` + `pagesrc.LISTINGS`. When those change on `main`, update the snapshot and redeploy.

## Local tests

```bash
cd cfworker && npm test
```

## Manual kick

`POST /run` on the workers.dev URL runs one poll+dispatch cycle (same as cron). Handy after deploy.

## What this does not do

- Does not post to X, push, or IndexNow (the GitHub workflow still does that).
- Does not replace the box watcher while the box is awake; both may detect the same item, and GitHub coordination prevents double-deploy storms.
- Does not create the Cloudflare account or the GitHub PAT — those are manual / parent-agent steps.
