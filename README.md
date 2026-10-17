# Wrestling Central News (WCN)
Static wrestling news site (`public/`) + Python pipeline (`aggregator.py`, `enrich.py`, `editorial.py`, `aliases.py`).
GitHub Actions runs the pipeline every 15 minutes, stores state (`data/`, `public/news.json`) as a single force-pushed commit on the `data` branch (keeps repo size flat), keeps 60 days of stories, and deploys `public/` to GitHub Pages.
Ads/analytics IDs: `public/ads-config.js`. Local: `./start.sh` → http://localhost:8080
