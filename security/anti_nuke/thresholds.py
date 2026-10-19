from typing import Dict, Tuple
from .models import NukeType

# Maps NukeType to (max_allowed, time_window_seconds)
NUKE_THRESHOLDS: Dict[NukeType, Tuple[int, int]] = {
    NukeType.MASS_BAN: (3, 10),  # 3 bans per 10s
    NukeType.CHANNEL_DELETE: (2, 10),  # 2 channels deleted per 10s
    NukeType.ROLE_DELETE: (2, 10),  # 2 roles deleted per 10s
    NukeType.WEBHOOK_SPAM: (5, 10),  # 5 webhooks created per 10s
}
