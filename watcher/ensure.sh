#!/bin/bash
# Idempotent keepalive: start cron and the watcher supervisor if they aren't running. Called from cron every minute,
# cron @reboot, and ~/.profile / ~/.bashrc (so the first shell after a box restart brings it back even without an init system).
# Second line of defence: if the supervisor is alive but the heartbeat is badly stale (supervisor wedged too), kill it and
# start a fresh one. Ages use CLOCK_BOOTTIME (/proc/uptime), which stops while the box VM is paused.
export PATH="/usr/local/bin:/usr/bin:/bin:/usr/sbin:$PATH"
W="$HOME/.wcn"; mkdir -p "$W"; LOG="$W/watcher.log"
HARD_STALE_S=${WCN_HARD_STALE_S:-300}
if ! pgrep -x cron >/dev/null; then
  if [ -x /usr/sbin/cron ]; then sudo -n /usr/sbin/cron 2>/dev/null
  else echo "$(date -u +%FT%TZ) ensure: cron is not installed - only the supervisor + shell hooks keep the watcher alive" >>"$LOG"; fi
fi
if ! flock -n "$W/supervise.lock" true 2>/dev/null; then       # supervisor holds the lock -> running; check it is not wedged
  read -r hb _ <"$W/watcher.heartbeat" 2>/dev/null || exit 0
  now=$(cut -d' ' -f1 /proc/uptime)
  awk -v a="$now" -v b="$hb" -v s="$HARD_STALE_S" 'BEGIN{exit !(a-b>s)}' || exit 0
  sp=$(cat "$W/supervise.pid" 2>/dev/null)
  echo "$(date -u +%FT%TZ) ensure: heartbeat stale >${HARD_STALE_S}s with supervisor ${sp:-?} alive - killing it and the watcher" >>"$LOG"
  pkill -f 'watcher/wcn_watch.py' ; [ -n "$sp" ] && kill "$sp" 2>/dev/null
  sleep 3; pkill -KILL -f 'watcher/wcn_watch.py'; [ -n "$sp" ] && kill -KILL "$sp" 2>/dev/null
  for _ in 1 2 3 4 5; do flock -n "$W/supervise.lock" true 2>/dev/null && break; sleep 1; done
fi
setsid nohup bash "$W/repo/watcher/supervise.sh" >/dev/null 2>&1 < /dev/null &
echo "$(date -u +%FT%TZ) ensure: started supervisor" >>"$LOG"
