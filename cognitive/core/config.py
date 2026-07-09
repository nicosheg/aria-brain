# cognitive/core/config.py
# Configuration for ARIA - all weights and thresholds are here

class ARIAConfig:
    """Central configuration - no hardcoded values in memory stores."""
    
    # ─── Episodic Memory ────────────────────────────────────────
    EPISODIC_MAX_SIZE = 1000
    EPISODIC_CONSOLIDATION_IMPORTANCE_WEIGHT = 0.6
    EPISODIC_CONSOLIDATION_RECENCY_WEIGHT = 0.4
    EPISODIC_IMPORTANCE_THRESHOLD = 0.7
    EPISODIC_RECENCY_DAYS = 30
    
    # ─── Semantic Memory ────────────────────────────────────────
    SEMANTIC_GET_RELEVANT_OVERLAP_WEIGHT = 1.0
    SEMANTIC_GET_RELEVANT_CONFIDENCE_WEIGHT = 0.5
    SEMANTIC_HIGH_CONFIDENCE_THRESHOLD = 0.7
    
    # ─── Procedural Memory ──────────────────────────────────────
    PROCEDURAL_SUCCESS_RATE_DEFAULT = 0.5
    
    # ─── General ────────────────────────────────────────────────
    DEFAULT_IMPORTANCE = 0.5
    DEFAULT_CONFIDENCE = 0.5
    
    # ─── Testing ────────────────────────────────────────────────
    TEST_VERBOSE = False
