# cognitive/observe/observation.py

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import uuid
from datetime import datetime, timezone

@dataclass
class Observation:
    """
    First-class observation – the starting point of all cognition.
    
    Everything that enters the cognitive system becomes an Observation.
    This is the single entry point for all inputs.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: str = "conversation"  # conversation, pdf, image, api, etc.
    raw: str = ""
    embeddings: Optional[List[float]] = None
    attachments: Optional[List[str]] = None
    entities: Optional[List[str]] = None  # Entity IDs identified
    metadata: Dict = field(default_factory=dict)
    importance: float = 0.5
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    processed: bool = False

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "source": self.source,
            "raw": self.raw,
            "embeddings": self.embeddings,
            "attachments": self.attachments,
            "entities": self.entities,
            "metadata": self.metadata,
            "importance": self.importance,
            "timestamp": self.timestamp,
            "processed": self.processed
  }
