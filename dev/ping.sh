#!/usr/bin/env bash
# ping.sh — is the model answering, or still rate-limited?
#
# A throttled call to mimo-v2.5-free *hangs* rather than erroring (hence the
# orchestrator's long turn_timeout), so we wrap a one-shot `opencode run` in a hard
# timeout. No TUI, no project boot: --pure skips plugins and we run from a neutral
# dir, so this probes only the model/account quota (which is per-account, not
# per-project).
#
#   .opencode/dev/ping.sh              # one probe
#   .opencode/dev/ping.sh 4            # 4 back-to-back probes (truer signal than one)
#   MODEL=opencode/other ping.sh       # probe a different model
#
# A single ping clearing doesn't prove sustained throughput — a full autoplay/
# benchmark burst can re-trip a rolling-window limit even when one shot succeeds.

set -u

MODEL="${MODEL:-opencode/mimo-v2.5-free}"
TIMEOUT="${TIMEOUT:-45}"
COUNT="${1:-1}"

probe() {
    local out code
    out=$(cd /tmp && timeout "$TIMEOUT" opencode run --pure -m "$MODEL" "Reply with exactly: OK" 2>&1)
    code=$?
    case $code in
        0)   echo "  cleared — model replied (${MODEL})" ;;
        124) echo "  STILL THROTTLED — call hung past ${TIMEOUT}s" ;;
        *)   echo "  errored (exit $code): $(echo "$out" | tail -1)" ;;
    esac
    return $code
}

rc=0
for i in $(seq 1 "$COUNT"); do
    [ "$COUNT" -gt 1 ] && printf 'probe %d/%d:' "$i" "$COUNT"
    probe || rc=$?
done
exit $rc
