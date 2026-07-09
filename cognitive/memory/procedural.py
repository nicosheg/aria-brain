# cognitive/memory/procedural.py

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid


@dataclass
class Procedure:
    """
    A procedure or skill.
    Stores steps, when to use, and success metrics.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    steps: List[str] = field(default_factory=list)
    when_to_use: str = ""
    success_rate: float = 0.5  # 0.0 to 1.0
    times_used: int = 0
    times_succeeded: int = 0
    created: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_updated: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    version: int = 1

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "steps": self.steps,
            "when_to_use": self.when_to_use,
            "success_rate": self.success_rate,
            "times_used": self.times_used,
            "times_succeeded": self.times_succeeded,
            "created": self.created,
            "last_updated": self.last_updated,
            "version": self.version
        }


class ProceduralMemory:
    """
    Stores procedures and skills.
    Allows retrieval by name, description, or use case.
    """
    
    def __init__(self):
        self.procedures: List[Procedure] = []
    
    def add(self, name: str, description: str, steps: List[str],
            when_to_use: str = "", success_rate: float = 0.5) -> Procedure:
        """Add a new procedure."""
        proc = Procedure(
            name=name,
            description=description,
            steps=steps,
            when_to_use=when_to_use,
            success_rate=success_rate
        )
        self.procedures.append(proc)
        return proc
    
    def get_by_name(self, name: str) -> Optional[Procedure]:
        """Get procedure by exact name."""
        for proc in self.procedures:
            if proc.name.lower() == name.lower():
                return proc
        return None
    
    def search(self, query: str) -> List[Procedure]:
        """Search procedures by name, description, or when_to_use."""
        query_lower = query.lower()
        results = []
        for proc in self.procedures:
            if (query_lower in proc.name.lower() or
                query_lower in proc.description.lower() or
                query_lower in proc.when_to_use.lower()):
                results.append(proc)
        return results
    
    def get_by_use_case(self, scenario: str) -> List[Procedure]:
        """Get procedures that match a scenario."""
        scenario_lower = scenario.lower()
        results = []
        for proc in self.procedures:
            if scenario_lower in proc.when_to_use.lower():
                results.append(proc)
        return results
    
    def get_all(self) -> List[Procedure]:
        return self.procedures
    
    def count(self) -> int:
        return len(self.procedures)
    
    def clear(self):
        self.procedures = []
    
    def record_use(self, procedure_id: str, success: bool):
        """Record a usage and update success rate."""
        for proc in self.procedures:
            if proc.id == procedure_id:
                proc.times_used += 1
                if success:
                    proc.times_succeeded += 1
                proc.success_rate = proc.times_succeeded / proc.times_used if proc.times_used > 0 else 0.5
                proc.last_updated = datetime.now(timezone.utc).isoformat()
                return True
        return False
    
    def to_dict(self) -> Dict:
        return {
            "procedures": [p.to_dict() for p in self.procedures],
            "count": len(self.procedures)
        }
