#!/bin/bash
# PISAMA Demo Video Recording - Fully Automated Version
# No user prompts - runs everything automatically

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="$SCRIPT_DIR/output"
AUDIO_DIR="$SCRIPT_DIR/audio"
RECORDINGS_DIR="$SCRIPT_DIR/recordings"

SCREEN_DEVICE="4"
FRAMERATE="30"
OUTPUT_FILE="$OUTPUT_DIR/pisama_demo_$(date +%Y%m%d_%H%M%S).mp4"
TEMP_VIDEO="$OUTPUT_DIR/temp_screen.mp4"

mkdir -p "$OUTPUT_DIR" "$RECORDINGS_DIR"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║     PISAMA Demo Video - Fully Automated Recording           ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Step 1: Start screen recording in background
echo "[1/4] Starting screen recording..."
ffmpeg -y \
    -f avfoundation \
    -framerate $FRAMERATE \
    -i "$SCREEN_DEVICE:none" \
    -c:v h264_videotoolbox \
    -pix_fmt yuv420p \
    -t 180 \
    "$TEMP_VIDEO" &
FFMPEG_PID=$!
echo "  Recording started (PID: $FFMPEG_PID)"

# Give ffmpeg a moment to initialize
sleep 3

# Step 2: Play voiceover in background
echo "[2/4] Playing voiceover..."
if [ -f "$AUDIO_DIR/full_voiceover.m4a" ]; then
    afplay "$AUDIO_DIR/full_voiceover.m4a" &
    AUDIO_PID=$!
fi

# Step 3: Run browser automation
echo "[3/4] Running browser automation..."
cd "$SCRIPT_DIR"
npx ts-node demo-automation.ts 2>&1 || echo "  Automation completed with warnings"

# Step 4: Stop recording
echo "[4/4] Stopping recording..."
sleep 2
kill -INT $FFMPEG_PID 2>/dev/null || true
wait $FFMPEG_PID 2>/dev/null || true

# Stop audio if still playing
if [ -n "$AUDIO_PID" ]; then
    kill $AUDIO_PID 2>/dev/null || true
fi

# Merge audio and video
echo ""
echo "Merging audio and video..."
if [ -f "$AUDIO_DIR/full_voiceover.m4a" ] && [ -f "$TEMP_VIDEO" ]; then
    ffmpeg -y \
        -i "$TEMP_VIDEO" \
        -i "$AUDIO_DIR/full_voiceover.m4a" \
        -c:v copy \
        -c:a aac \
        -map 0:v:0 \
        -map 1:a:0 \
        -shortest \
        "$OUTPUT_FILE" 2>/dev/null
    rm -f "$TEMP_VIDEO"
else
    mv "$TEMP_VIDEO" "$OUTPUT_FILE"
fi

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                    Recording Complete!                       ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "Output: $OUTPUT_FILE"
if [ -f "$OUTPUT_FILE" ]; then
    DURATION=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$OUTPUT_FILE" 2>/dev/null || echo "unknown")
    SIZE=$(ls -lh "$OUTPUT_FILE" | awk '{print $5}')
    echo "Duration: ${DURATION}s"
    echo "Size: $SIZE"
fi
