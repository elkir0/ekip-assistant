#!/bin/bash
# Wait for Devialet RAOP sink to appear, prefer manual IPv4 config
for i in $(seq 1 30); do
    # Prefer manual IPv4 sink first
    SINK=$(pactl list sinks short 2>/dev/null | grep "devialet_ipv4" | awk '{print $2}')
    # Fallback to any Phantom sink
    if [ -z "$SINK" ]; then
        SINK=$(pactl list sinks short 2>/dev/null | grep -i phantom | head -1 | awk '{print $2}')
    fi
    if [ -n "$SINK" ]; then
        pactl set-default-sink "$SINK"
        pactl set-sink-volume "$SINK" 50%
        echo "[AUDIO] Devialet set as default at 50%: $SINK"
        exit 0
    fi
    sleep 2
done
echo "[AUDIO] Devialet not found after 60s"
