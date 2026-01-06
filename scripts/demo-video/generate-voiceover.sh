#!/bin/bash
# Generate voiceover audio files from script segments
# Uses macOS 'say' command with Daniel voice

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="$SCRIPT_DIR/audio"
VOICE="Daniel"
RATE=175

mkdir -p "$OUTPUT_DIR"

echo "Generating voiceover audio files..."

# Section 1: Hook (0:00-0:30)
echo "  [1/14] Generating hook.aiff..."
say -v "$VOICE" -r $RATE -o "$OUTPUT_DIR/01_hook.aiff" \
"If you're building AI agents, you've probably experienced this: you come back from a break to find your agent has burned through fifty dollars in API tokens doing absolutely nothing. It got stuck in a loop, and you had no idea. PISAMA detects these failures in under ten seconds and can automatically fix them. Let me show you how."

# Section 2: Demo intro
echo "  [2/14] Generating demo_intro.aiff..."
say -v "$VOICE" -r $RATE -o "$OUTPUT_DIR/02_demo_intro.aiff" \
"Let's start with an interactive demo. PISAMA detects sixteen types of agent failures, but let's focus on the most common one: infinite loops."

# Select scenario
echo "  [3/14] Generating select_scenario.aiff..."
say -v "$VOICE" -r $RATE -o "$OUTPUT_DIR/03_select_scenario.aiff" \
"I'll select the infinite loop scenario and start the simulation."

# Watch agents
echo "  [4/14] Generating watch_agents.aiff..."
say -v "$VOICE" -r $RATE -o "$OUTPUT_DIR/04_watch_agents.aiff" \
"Watch as the agents execute. You can see real-time metrics: active agents, messages, token usage, and costs."

# Detection
echo "  [5/14] Generating detection.aiff..."
say -v "$VOICE" -r $RATE -o "$OUTPUT_DIR/05_detection.aiff" \
"And there it is. PISAMA detected a loop in under eight seconds. It identified the exact pattern: the agent repeated the same action multiple times without making progress."

# Explanation
echo "  [6/14] Generating explanation.aiff..."
say -v "$VOICE" -r $RATE -o "$OUTPUT_DIR/06_explanation.aiff" \
"Notice the plain English explanation. No need to dig through logs to understand what happened. And here's the suggested fix. One click to apply it."

# Try your own intro
echo "  [7/14] Generating try_own_intro.aiff..."
say -v "$VOICE" -r $RATE -o "$OUTPUT_DIR/07_try_own_intro.aiff" \
"But you don't have to take my word for it. You can upload your own traces and see PISAMA analyze them right now."

# Upload trace
echo "  [8/14] Generating upload_trace.aiff..."
say -v "$VOICE" -r $RATE -o "$OUTPUT_DIR/08_upload_trace.aiff" \
"I'll drop in a trace from one of our test sessions."

# Analysis result
echo "  [9/14] Generating analysis_result.aiff..."
say -v "$VOICE" -r $RATE -o "$OUTPUT_DIR/09_analysis_result.aiff" \
"And there we go. It found a semantic loop: the agent kept asking the same question in different words. This is something that's really hard to catch manually, but PISAMA's embedding-based detection caught it instantly."

# CLI intro
echo "  [10/14] Generating cli_intro.aiff..."
say -v "$VOICE" -r $RATE -o "$OUTPUT_DIR/10_cli_intro.aiff" \
"Getting this for your own agents takes about thirty seconds."

# CLI commands
echo "  [11/14] Generating cli_commands.aiff..."
say -v "$VOICE" -r $RATE -o "$OUTPUT_DIR/11_cli_commands.aiff" \
"Install the package, run the install command to set up the hooks, and run the demo to see it in action with your first trace."

# CLI done
echo "  [12/14] Generating cli_done.aiff..."
say -v "$VOICE" -r $RATE -o "$OUTPUT_DIR/12_cli_done.aiff" \
"That's it. From now on, every agent session is monitored. Loops are caught before they waste your budget."

# Features
echo "  [13/14] Generating features.aiff..."
say -v "$VOICE" -r $RATE -o "$OUTPUT_DIR/13_features.aiff" \
"Quick recap of what PISAMA gives you: Real-time detection for sixteen failure modes, including loops, state corruption, coordination failures, and more. Plain English explanations so you understand what went wrong. One-click fixes to resolve issues immediately. Framework support for LangGraph, AutoGen, CrewAI, Claude Code, and n8n. All running locally. Your traces never leave your machine."

# CTA
echo "  [14/14] Generating cta.aiff..."
say -v "$VOICE" -r $RATE -o "$OUTPUT_DIR/14_cta.aiff" \
"Our detection accuracy is publicly benchmarked. Check out our benchmarks page to see how we perform on over twenty thousand real-world traces. Ready to try it? Check out our getting started guide at pisama.dev/docs. The free tier includes unlimited local analysis. Stop debugging agent failures manually. Let PISAMA catch them for you."

echo ""
echo "Converting AIFF to M4A for better compatibility..."

# Convert all AIFF to M4A using ffmpeg
for f in "$OUTPUT_DIR"/*.aiff; do
    basename="${f%.aiff}"
    echo "  Converting $(basename "$f")..."
    ffmpeg -y -i "$f" -c:a aac -b:a 192k "${basename}.m4a" 2>/dev/null
done

echo ""
echo "Concatenating all segments into full voiceover..."

# Create concat file
cat > "$OUTPUT_DIR/concat.txt" << EOF
file '01_hook.m4a'
file '02_demo_intro.m4a'
file '03_select_scenario.m4a'
file '04_watch_agents.m4a'
file '05_detection.m4a'
file '06_explanation.m4a'
file '07_try_own_intro.m4a'
file '08_upload_trace.m4a'
file '09_analysis_result.m4a'
file '10_cli_intro.m4a'
file '11_cli_commands.m4a'
file '12_cli_done.m4a'
file '13_features.m4a'
file '14_cta.m4a'
EOF

ffmpeg -y -f concat -safe 0 -i "$OUTPUT_DIR/concat.txt" -c copy "$OUTPUT_DIR/full_voiceover.m4a" 2>/dev/null

echo ""
echo "Done! Generated files in $OUTPUT_DIR:"
ls -la "$OUTPUT_DIR"/*.m4a | awk '{print "  " $NF " (" $5 " bytes)"}'

# Get duration
DURATION=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$OUTPUT_DIR/full_voiceover.m4a" 2>/dev/null)
echo ""
echo "Total voiceover duration: ${DURATION}s"
