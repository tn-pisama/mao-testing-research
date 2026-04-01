"""N8N-specific prompt templates for golden dataset generation.

Data loaded from backend/data/detection_prompts_n8n.json.
"""

from app.detection_enterprise.type_prompts_loader import load_type_prompts

N8N_TYPE_PROMPTS = load_type_prompts("n8n")
