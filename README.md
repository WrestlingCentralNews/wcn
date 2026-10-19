# Wrestling Central News (WCN)
Static wrestling news site (`public/`) + Python pipeline (`aggregator.py`, `enrich.py`, `editorial.py`, `aliases.py`).
GitHub Actions runs the pipeline every 15 minutes, stores state (`data/`, `public/news.json`) as a single force-pushed commit on the `data` branch (keeps repo size flat), keeps 60 days of stories, and deploys `public/` to GitHub Pages.
Ads/analytics IDs: `public/ads-config.js`. Local: `./start.sh` → http://localhost:8080

## Fast pickup (2-minute source checks)
- **Box watcher** (`watcher/wcn_watch.py`): runs on the admin box; stops while the box VM is paused.
- **GitHub Actions poller** (`.github/workflows/poller.yml` → `watcher/gha_poller.py`): always-on. Same detection/dispatch code as the box watcher, one ~5h30m job polling every 2 min, which then hands off to the next run (concurrency group `wcn-poller`, so only one runs). A `:07/:37` cron "gate" restarts the chain if it ever breaks. Last-seen state lives in the Actions cache (`wcn-poller-*`); live status on branch `poller-status` (`status.json`, force-pushed every 10 min) and in each run's summary. Kill switch: repo variable `POLLER_ENABLED=false`.
- Both dispatch `update.yml` only when no update run is queued, treat items as covered by a run created after they were seen, and share the cap of 20 `workflow_dispatch` runs/hour with a 60 s gap (counted via the GitHub API).
- **Cloudflare Worker** (`cfworker/`): **on hold** until the WCN Cloudflare account's email is verified (Workers deploy fails with error 10034). Not deployed; kept for later.
