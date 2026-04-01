"""Dify-specific prompt templates for golden dataset generation.

Data loaded from backend/data/detection_prompts_dify.json.
"""

from app.detection_enterprise.type_prompts_loader import load_type_prompts

DIFY_TYPE_PROMPTS = load_type_prompts("dify")
