#!/bin/bash
# Supervisor + watchdog for the WCN watcher; only one supervisor runs (flock on ~/.wcn/supervise.lock).
#  - restarts the watcher whenever it exits (crash);
#  - STALL: the watcher rewrites ~/.wcn/watcher.heartbeat ("<CLOCK_BOOTTIME s> <pid> <phase> <wall s>") every <=2 s while
#    sleeping and at every step. If the heartbeat is older than STALE_S of box-running time, the watcher is hung while alive:
#    dump its thread stacks (SIGUSR1 -> ~/.wcn/watcher.stacks, copied into watcher.log), SIGTERM, then SIGKILL, restart.
#  - ages are measured on CLOCK_BOOTTIME (/proc/uptime), which stops while the box VM is paused, so a pause/resume is never
#    mistaken for a hang; if the watchdog's own sleep spans a pause, that round is skipped (grace) anyway.
export PATH="/usr/local/bin:/usr/bin:/bin:$PATH"   # cron starts us with PATH=/usr/bin:/bin; gh lives in /usr/local/bin
W="$HOME/.wcn"; LOG="$W/watcher.log"; HB="$W/watcher.heartbeat"
STALE_S=${WCN_STALE_S:-180}; CHECK_S=${WCN_CHECK_S:-15}; START_GRACE_S=${WCN_START_GRACE_S:-90}
exec 9>"$W/supervise.lock"
flock -n 9 || exit 0
echo $$ >"$W/supervise.pid"
cd "$W/repo" || exit 1
log() { echo "$(date -u +%FT%TZ) supervisor: $*" >>"$LOG"; }
up() { cut -d' ' -f1 /proc/uptime; }
older() { awk -v a="$1" -v b="$2" -v s="$3" 'BEGIN{exit !(a-b>s)}'; }   # older NOW THEN SECS -> true if NOW-THEN > SECS
log "start pid=$$ stale=${STALE_S}s check=${CHECK_S}s"
while true; do
  python3 -u watcher/wcn_watch.py >>"$W/watcher.out" 2>&1 9>&- &
  wp=$!; started=$(up)
  while kill -0 "$wp" 2>/dev/null; do
    t0=$(up); sleep "$CHECK_S" 9>&- & wait $!; now=$(up)
    kill -0 "$wp" 2>/dev/null || break
    older "$now" "$t0" $((CHECK_S * 4)) && { log "box pause noticed - skipping one stale check"; continue; }
    older "$now" "$started" "$START_GRACE_S" || continue
    read -r hb hpid phase _ <"$HB" 2>/dev/null || { hb=0; hpid=0; phase=none; }
    [ "$hpid" = "$wp" ] || { hb=$started; phase="no-heartbeat-yet"; }
    if older "$now" "$hb" "$STALE_S"; then
      age=$(awk -v a="$now" -v b="$hb" 'BEGIN{printf "%d", a-b}')
      log "STALL: watcher pid=$wp heartbeat ${age}s old (phase=$phase) - dumping stacks, killing, restarting"
      kill -USR1 "$wp" 2>/dev/null; sleep 2 9>&-
      [ -s "$W/watcher.stacks" ] && sed 's/^/    stack| /' "$W/watcher.stacks" | tail -n 60 >>"$LOG"
      kill -TERM "$wp" 2>/dev/null
      for _ in 1 2 3 4 5 6 7 8 9 10; do kill -0 "$wp" 2>/dev/null || break; sleep 1 9>&-; done
      kill -0 "$wp" 2>/dev/null && { kill -KILL "$wp" 2>/dev/null; log "watcher pid=$wp needed SIGKILL"; }
      break
    fi
  done
  wait "$wp"; rc=$?
  log "watcher pid=$wp exited (rc=$rc), restarting in 10s"
  sleep 10 9>&-
done
