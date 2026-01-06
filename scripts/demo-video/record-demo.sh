#!/bin/bash
# PISAMA Demo Video Recording - Master Orchestration Script
#
# This script:
# 1. Generates voiceover audio (if not exists)
# 2. Starts screen recording with ffmpeg
# 3. Plays voiceover audio in sync
# 4. Runs browser automation
# 5. Stops recording and merges audio/video
#
# Prerequisites:
# - ffmpeg installed (brew install ffmpeg)
# - playwright installed (npm install -g playwright)
# - Frontend running at localhost:3000
#
# Usage: ./record-demo.sh [options]
#   --skip-voiceover   Skip voiceover generation (use existing)
#   --no-audio        Record without audio/voiceover
#   --dry-run         Show what would be done without executing

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
OUTPUT_DIR="$SCRIPT_DIR/output"
AUDIO_DIR="$SCRIPT_DIR/audio"
RECORDINGS_DIR="$SCRIPT_DIR/recordings"

# Screen recording settings
SCREEN_DEVICE="4"  # Capture screen 0
AUDIO_DEVICE="1"   # MacBook Pro Microphone
FRAMERATE="30"
OUTPUT_FILE="$OUTPUT_DIR/pisama_demo_$(date +%Y%m%d_%H%M%S).mp4"

# Parse arguments
SKIP_VOICEOVER=false
NO_AUDIO=false
DRY_RUN=false

for arg in "$@"; do
  case $arg in
    --skip-voiceover) SKIP_VOICEOVER=true ;;
    --no-audio) NO_AUDIO=true ;;
    --dry-run) DRY_RUN=true ;;
  esac
done

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Create directories
mkdir -p "$OUTPUT_DIR" "$RECORDINGS_DIR"

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║           PISAMA Demo Video Recording System                 ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Check prerequisites
log_info "Checking prerequisites..."

if ! command -v ffmpeg &> /dev/null; then
    log_error "ffmpeg not found. Install with: brew install ffmpeg"
    exit 1
fi

if ! command -v npx &> /dev/null; then
    log_error "npx not found. Install Node.js"
    exit 1
fi

# Check if frontend is running
if ! curl -s http://localhost:3000 > /dev/null 2>&1; then
    log_warn "Frontend not running at localhost:3000"
    log_info "Starting frontend in background..."
    if [ "$DRY_RUN" = false ]; then
        cd "$PROJECT_ROOT/frontend" && npm run dev &
        FRONTEND_PID=$!
        sleep 5
    fi
fi

log_info "Prerequisites OK"

# Step 1: Generate voiceover
echo ""
log_info "Step 1: Generate Voiceover Audio"
if [ "$SKIP_VOICEOVER" = true ]; then
    log_info "Skipping voiceover generation (--skip-voiceover)"
elif [ -f "$AUDIO_DIR/full_voiceover.m4a" ]; then
    log_info "Voiceover already exists at $AUDIO_DIR/full_voiceover.m4a"
else
    log_info "Generating voiceover audio files..."
    if [ "$DRY_RUN" = false ]; then
        chmod +x "$SCRIPT_DIR/generate-voiceover.sh"
        "$SCRIPT_DIR/generate-voiceover.sh"
    fi
fi

# Step 2: Prepare recording
echo ""
log_info "Step 2: Prepare Screen Recording"
log_info "Output file: $OUTPUT_FILE"
log_info "Screen device: $SCREEN_DEVICE (Capture screen 0)"
log_info "Framerate: $FRAMERATE fps"

# Grant screen recording permission reminder
echo ""
log_warn "IMPORTANT: Ensure Terminal has Screen Recording permission"
log_warn "System Preferences > Privacy & Security > Screen Recording > Terminal"
echo ""
read -p "Press ENTER when ready to start recording (Ctrl+C to cancel)..."

# Step 3: Start screen recording
echo ""
log_info "Step 3: Starting Screen Recording..."

if [ "$DRY_RUN" = true ]; then
    log_info "[DRY RUN] Would start ffmpeg recording"
else
    # Start screen recording in background
    TEMP_VIDEO="$OUTPUT_DIR/temp_screen.mp4"

    ffmpeg -y \
        -f avfoundation \
        -framerate $FRAMERATE \
        -i "$SCREEN_DEVICE:none" \
        -c:v h264_videotoolbox \
        -pix_fmt yuv420p \
        -preset ultrafast \
        "$TEMP_VIDEO" &
    FFMPEG_PID=$!

    log_info "Recording started (PID: $FFMPEG_PID)"
    log_info "Recording to: $TEMP_VIDEO"
fi

# Step 4: Play voiceover and run automation
echo ""
log_info "Step 4: Running Demo Automation..."

if [ "$DRY_RUN" = true ]; then
    log_info "[DRY RUN] Would run Playwright automation"
    log_info "[DRY RUN] Would play voiceover audio"
else
    # Play voiceover in background (if exists and not disabled)
    if [ "$NO_AUDIO" = false ] && [ -f "$AUDIO_DIR/full_voiceover.m4a" ]; then
        log_info "Playing voiceover audio..."
        afplay "$AUDIO_DIR/full_voiceover.m4a" &
        AUDIO_PID=$!
    fi

    # Give a moment before starting browser
    sleep 2

    # Run Playwright automation
    log_info "Running Playwright browser automation..."
    cd "$SCRIPT_DIR"

    # Install playwright if needed
    if ! npx playwright --version &> /dev/null 2>&1; then
        log_info "Installing Playwright..."
        npm install playwright typescript ts-node @types/node
        npx playwright install chromium
    fi

    # Run the automation
    npx ts-node demo-automation.ts 2>&1 || log_warn "Automation completed with warnings"
fi

# Step 5: Stop recording
echo ""
log_info "Step 5: Stopping Recording..."

if [ "$DRY_RUN" = false ] && [ -n "$FFMPEG_PID" ]; then
    # Wait a moment then stop
    sleep 2
    kill -INT $FFMPEG_PID 2>/dev/null || true
    wait $FFMPEG_PID 2>/dev/null || true
    log_info "Recording stopped"
fi

# Stop audio if still playing
if [ -n "$AUDIO_PID" ]; then
    kill $AUDIO_PID 2>/dev/null || true
fi

# Step 6: Merge audio and video
echo ""
log_info "Step 6: Merging Audio and Video..."

if [ "$DRY_RUN" = true ]; then
    log_info "[DRY RUN] Would merge audio and video"
elif [ "$NO_AUDIO" = true ]; then
    log_info "No audio mode - copying video as-is"
    mv "$TEMP_VIDEO" "$OUTPUT_FILE"
elif [ -f "$AUDIO_DIR/full_voiceover.m4a" ] && [ -f "$TEMP_VIDEO" ]; then
    log_info "Merging voiceover with screen recording..."
    ffmpeg -y \
        -i "$TEMP_VIDEO" \
        -i "$AUDIO_DIR/full_voiceover.m4a" \
        -c:v copy \
        -c:a aac \
        -map 0:v:0 \
        -map 1:a:0 \
        -shortest \
        "$OUTPUT_FILE"

    # Clean up temp file
    rm -f "$TEMP_VIDEO"
    log_info "Merged successfully!"
else
    if [ -f "$TEMP_VIDEO" ]; then
        mv "$TEMP_VIDEO" "$OUTPUT_FILE"
    fi
    log_warn "Could not merge audio - voiceover or video missing"
fi

# Stop frontend if we started it
if [ -n "$FRONTEND_PID" ]; then
    kill $FRONTEND_PID 2>/dev/null || true
fi

# Step 7: Summary
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                    Recording Complete!                       ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

if [ -f "$OUTPUT_FILE" ]; then
    DURATION=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$OUTPUT_FILE" 2>/dev/null || echo "unknown")
    SIZE=$(ls -lh "$OUTPUT_FILE" | awk '{print $5}')

    log_info "Output: $OUTPUT_FILE"
    log_info "Duration: ${DURATION}s"
    log_info "Size: $SIZE"
    echo ""
    log_info "Next steps:"
    echo "  1. Review the video: open \"$OUTPUT_FILE\""
    echo "  2. Upload to Loom or YouTube for sharing"
    echo "  3. Embed on landing page"
else
    log_warn "No output file generated"
fi

echo ""
