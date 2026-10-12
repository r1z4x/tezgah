from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import partial


@dataclass
class Event:
    name: str
    created: datetime = field(default_factory=partial(datetime.now, timezone.utc))
