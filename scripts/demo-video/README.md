# PISAMA Demo Video Recording

Automated demo video recording system using CLI tools and MCP servers.

## Quick Start

```bash
# 1. Install dependencies
cd scripts/demo-video
npm install

# 2. Start frontend (in another terminal)
cd frontend && npm run dev

# 3. Generate voiceover audio
./generate-voiceover.sh

# 4. Record full demo
./record-demo.sh
```

## Components

| File | Purpose |
|------|---------|
| `record-demo.sh` | Master orchestration script |
| `generate-voiceover.sh` | Generate TTS audio from script |
| `demo-automation.ts` | Playwright browser automation |
| `voiceover-segments.json` | Script text with timing |

## Prerequisites

- **ffmpeg** - Screen recording and audio processing
- **Node.js 18+** - Playwright automation
- **macOS** - Uses AVFoundation for capture, `say` for TTS

### Install ffmpeg

```bash
brew install ffmpeg
```

### Screen Recording Permission

Grant Terminal screen recording permission:
1. System Preferences > Privacy & Security > Screen Recording
2. Enable Terminal (or your terminal app)
3. Restart Terminal

## Usage Options

```bash
# Full recording with voiceover
./record-demo.sh

# Skip voiceover generation (use existing)
./record-demo.sh --skip-voiceover

# Record without audio
./record-demo.sh --no-audio

# Dry run (show what would happen)
./record-demo.sh --dry-run
```

## Output

Files are saved to `output/`:
- `pisama_demo_YYYYMMDD_HHMMSS.mp4` - Final video

Audio files in `audio/`:
- `01_hook.m4a` through `14_cta.m4a` - Individual segments
- `full_voiceover.m4a` - Complete voiceover track

## Customization

### Change Voice

Edit `generate-voiceover.sh`:
```bash
VOICE="Samantha"  # or "Daniel", "Alex", etc.
RATE=180  # Words per minute
```

List available voices:
```bash
say -v '?'
```

### Change Recording Resolution

Edit `demo-automation.ts`:
```typescript
viewport: { width: 1920, height: 1080 }
```

### Modify Demo Flow

Edit `demo-automation.ts` to change the sequence of actions:
```typescript
const steps: DemoStep[] = [
  {
    name: 'Step Name',
    action: async () => { /* Playwright actions */ },
    duration: 3000  // Wait time in ms
  }
]
```

## Troubleshooting

### "Permission denied" for screen recording

Grant Terminal screen recording permission in System Preferences.

### ffmpeg shows "Input/output error"

Check device indices:
```bash
ffmpeg -f avfoundation -list_devices true -i ""
```

### Playwright can't find elements

The demo page selectors may have changed. Update `demo-automation.ts` with correct selectors.

### Audio out of sync

Adjust the `duration` values in `demo-automation.ts` to match voiceover timing.
