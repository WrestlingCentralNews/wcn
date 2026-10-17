#!/bin/bash
cd "$(dirname "$0")"
# updater now runs on GitHub Actions; uncomment for local refresh
# nohup python3 aggregator.py --loop > aggregator.log 2>&1 &
nohup python3 -m http.server 8080 --directory public > server.log 2>&1 &
