"""LangGraph-specific prompt templates for golden dataset generation.

Data loaded from backend/data/detection_prompts_langgraph.json.
"""

from app.detection_enterprise.type_prompts_loader import load_type_prompts

LANGGRAPH_TYPE_PROMPTS = load_type_prompts("langgraph")
