"""OpenClaw-specific prompt templates for golden dataset generation.

Data loaded from backend/data/detection_prompts_openclaw.json.
"""

from app.detection_enterprise.type_prompts_loader import load_type_prompts

OPENCLAW_TYPE_PROMPTS = load_type_prompts("openclaw")
