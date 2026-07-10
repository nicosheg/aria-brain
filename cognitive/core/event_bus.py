# cognitive/core/event_bus.py

from typing import Dict, List, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid


@dataclass
class Event:
    """An event for the event bus."""
    id: str
    type: str
    payload: Dict
    timestamp: str


class EventBus:
    """
    Simple event bus for decoupled communication between cognitive modules.
    """
    
    def __init__(self):
        self.subscribers: Dict[str, List[Callable]] = {}
        self.events: List[Event] = []
        self.max_events: int = 1000
    
    def subscribe(self, event_type: str, callback: Callable):
        """Subscribe to an event type."""
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        if callback not in self.subscribers[event_type]:
            self.subscribers[event_type].append(callback)
    
    def unsubscribe(self, event_type: str, callback: Callable):
        """Unsubscribe from an event type."""
        if event_type in self.subscribers:
            if callback in self.subscribers[event_type]:
                self.subscribers[event_type].remove(callback)
    
    def publish(self, event_type: str, payload: Dict):
        """Publish an event."""
        event = Event(
            id=str(uuid.uuid4()),
            type=event_type,
            payload=payload,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        self.events.append(event)
        
        # Limit event history
        if len(self.events) > self.max_events:
            self.events = self.events[-self.max_events:]
        
        # Notify subscribers
        for callback in self.subscribers.get(event_type, []):
            try:
                callback(event)
            except Exception as e:
                print(f"[EventBus] Error in subscriber for {event_type}: {e}")
    
    def get_events(self, event_type: str = None, limit: int = 100) -> List[Event]:
        """Get recent events."""
        if event_type:
            return [e for e in self.events[-limit:] if e.type == event_type]
        return self.events[-limit:]
    
    def clear(self):
        """Clear all events."""
        self.events = []
