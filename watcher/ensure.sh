#!/bin/bash
# Idempotent: start cron (keepalive) and the watcher supervisor if they aren't running. Called from cron every minute,
# cron @reboot, and ~/.profile / ~/.bashrc (so the first shell after a box restart brings it back even without an init system).
export PATH="/usr/local/bin:/usr/bin:/bin:/usr/sbin:$PATH"
mkdir -p "$HOME/.wcn"
pgrep -x cron >/dev/null || sudo -n /usr/sbin/cron 2>/dev/null
if ! flock -n "$HOME/.wcn/supervise.lock" true 2>/dev/null; then exit 0; fi   # supervisor holds the lock -> running
setsid nohup bash "$HOME/.wcn/repo/watcher/supervise.sh" >/dev/null 2>&1 < /dev/null &
echo "$(date -u +%FT%TZ) ensure: started supervisor" >>"$HOME/.wcn/watcher.log"
