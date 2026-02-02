# PISAMA 360° Launch Tracker

## Overview
Google Sheets-based tracking system for the 8-week PISAMA launch plan.

## Access
**Sheet URL:** https://docs.google.com/spreadsheets/d/1L4XyGBMk50mz_D4fZJbb6_sMWikfWClEIEd9DFjrOto

**Sheet ID:** `1L4XyGBMk50mz_D4fZJbb6_sMWikfWClEIEd9DFjrOto`

**Service Account:** `ai-discovery-key@ai-discovery-469923.iam.gserviceaccount.com`

## Structure

### Sheet1: Tasks (73 total)
| Column | Description |
|--------|-------------|
| A | Task ID (PIS-W{week}-{category}-{number}) |
| B | Week (1-2, 3-4, 5-6, 7, 8+) |
| C | Category (BUILD, CONTENT, GTM, OUTREACH, CAREER, LAUNCH, POST-LAUNCH) |
| D | Task description |
| E | Priority (P0, P1, P2) |
| F | Status (Todo, In Progress, Done, Blocked) |
| G | Due Date |
| H | Notes |

### Dashboard: Metrics
- Overall progress tracking
- Tasks by week breakdown
- Tasks by priority breakdown
- Tasks by category breakdown
- Auto-updating formulas

## Task Breakdown by Week

| Week | Tasks | Focus |
|------|-------|-------|
| 1-2 (Foundation) | 12 | Product polish, design, billing, demo video |
| 3-4 (Traction) | 18 | SDK publish, landing page, design partners, content |
| 5-6 (Pre-Launch) | 19 | Assets ready, 10 partners, PH submission |
| 7 (Launch) | 8 | Product Hunt launch day execution |
| 8+ (Post-Launch) | 8 | Convert, iterate, scale |

## Features

### Conditional Formatting
- **Priority**: P0=Red, P1=Yellow, P2=Gray
- **Status**: Done=Green+strikethrough, InProgress=Blue+bold, Blocked=Red+bold+italic

### API Integration
- Full read/write access via Google Sheets API
- Authenticated with GCP service account
- Used by `/pisama-weekly-review` skill for progress tracking

## Category Codes

| Code | Category | Description |
|------|----------|-------------|
| B | BUILD | Product development tasks |
| C | CONTENT | Content creation (blogs, videos, docs) |
| G | GTM | Go-to-market (landing page, messaging) |
| O | OUTREACH | Design partners, community engagement |
| R | CAREER | Personal brand building |
| L | LAUNCH | Launch day execution |
| P | POST-LAUNCH | Post-launch conversion & iteration |

## Usage with Claude Skills

```bash
# Weekly accountability check-in
/pisama-weekly-review

# Project management / sprint planning
/pisama-launch-pm

# GTM and messaging help
/pisama-gtm

# Outreach templates
/pisama-outreach

# Personal brand building
/pisama-career

# Launch day execution
/pisama-launch-day
```

## Source
Generated from: `~/.claude/plans/delegated-plotting-hopper.md` (PISAMA 360° Launch Plan)

## Last Updated
2026-02-02 - Initial setup with 73 curated actionable tasks
