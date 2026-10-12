from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Event:
    name: str
    created: datetime = field(default_factory=datetime.utcnow)
