"""Enterprise detection modules.

These modules require enterprise feature flags to be enabled.
They include ML-based detection, quality gates, and advanced evaluators.

Feature flags required:
- ml_detection: ML detector, tiered detection, orchestrator
- advanced_evals: Quality gate, retrieval quality, grounding

To enable, set in environment:
    FEATURE_ENTERPRISE_ENABLED=true
    FEATURE_ML_DETECTION=true
"""

from app.core.feature_gate import is_feature_enabled

# Conditionally export based on feature flags
__all__ = []

if is_feature_enabled("ml_detection"):
    from .ml_detector import MLFailureDetector
    from .ml_detector_v2 import AdvancedMLDetector
    from .ml_detector_v3 import MultiTaskDetector
    from .ml_detector_v4 import MultiTaskDetectorV4, load_pretrained as load_pretrained_v4
    from .tiered import TieredDetector, create_all_tiered_detectors
    from .orchestrator import DetectionOrchestrator
    from .golden_dataset import GoldenDataset, create_default_golden_dataset
    __all__.extend([
        "MLFailureDetector",
        "AdvancedMLDetector",
        "MultiTaskDetector",
        "MultiTaskDetectorV4",
        "load_pretrained_v4",
        "TieredDetector",
        "create_all_tiered_detectors",
        "DetectionOrchestrator",
        "GoldenDataset",
        "create_default_golden_dataset",
    ])

if is_feature_enabled("advanced_evals"):
    from .quality_gate import QualityGateDetector
    from .retrieval_quality import RetrievalQualityDetector
    from .grounding import GroundingDetector
    from .output_validation import OutputValidationDetector
    from .resource_misallocation import ResourceMisallocationDetector
    from .role_usurpation import RoleUsurpationDetector
    from .tool_provision import ToolProvisionDetector
    __all__.extend([
        "QualityGateDetector",
        "RetrievalQualityDetector",
        "GroundingDetector",
        "OutputValidationDetector",
        "ResourceMisallocationDetector",
        "RoleUsurpationDetector",
        "ToolProvisionDetector",
    ])
