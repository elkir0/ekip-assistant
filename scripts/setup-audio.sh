#!/bin/bash
# Wait for Devialet RAOP sink to appear, prefer auto-discovered IPv4
for i in $(seq 1 30); do
    # Prefer auto-discovered IPv4 Phantom sink (most reliable)
    SINK=$(pactl list sinks short 2>/dev/null | grep -i phantom | grep -v "fe80" | grep -v "devialet_ipv4" | head -1 | awk '{print $2}')
    # Fallback to manual IPv4
    if [ -z "$SINK" ]; then
        SINK=$(pactl list sinks short 2>/dev/null | grep "devialet_ipv4" | awk '{print $2}')
    fi
    # Fallback to any Phantom
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
