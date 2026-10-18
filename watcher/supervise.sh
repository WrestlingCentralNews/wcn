#!/bin/bash
# Supervisor loop for the WCN watcher: restarts it if it ever exits; only one supervisor runs (flock).
exec 9>"$HOME/.wcn/supervise.lock"
flock -n 9 || exit 0
cd "$HOME/.wcn/repo" || exit 1
while true; do
  python3 -u watcher/wcn_watch.py >>"$HOME/.wcn/watcher.out" 2>&1
  echo "$(date -u +%FT%TZ) watcher exited ($?), restarting in 10s" >>"$HOME/.wcn/watcher.log"
  sleep 10
done
