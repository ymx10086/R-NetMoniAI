import os
import asyncio
import logging
from pathlib import Path
import netifaces
import psutil
from common_classes import MyDeps

# Environment configuration
os.environ["TOKENIZERS_PARALLELISM"] = "false"
logger = logging.getLogger(__name__)

# Global variables
connected_clients = set()
metrics_queue = asyncio.Queue()
attack_queue = asyncio.Queue()
reports_queue = asyncio.Queue()  # New queue for reports

# Network monitoring configuration
BACKEND_DIR = Path(__file__).resolve().parent
LAST_CAPTURE_DIR = BACKEND_DIR / "lastCapture"
DEFAULT_CAPTURE_PATH = LAST_CAPTURE_DIR / "capture.pcap"

# Ensure capture directory exists regardless of launch cwd.
LAST_CAPTURE_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_DEPS = MyDeps(
    pathToFile=str(DEFAULT_CAPTURE_PATH),
    duration=18,
    cycle_interval=1
)

SLIDING_WINDOW_MAXLEN = 15

def _interface_is_up(interface_name: str) -> bool:
    stats = psutil.net_if_stats().get(interface_name)
    return bool(stats and stats.isup)


def _detect_default_interface() -> str | None:
    try:
        gateways = netifaces.gateways()
        default = gateways.get("default", {}).get(netifaces.AF_INET)
        if default and len(default) > 1:
            return default[1]
    except Exception as exc:
        logger.warning("[CONFIG] Failed to detect default gateway interface: %s", exc)
    return None


def _resolve_capture_interface() -> str:
    env_interface = os.getenv("NETMON_INTERFACE", "").strip()
    if env_interface:
        if _interface_is_up(env_interface):
            logger.info("[CONFIG] Using NETMON_INTERFACE=%s", env_interface)
            return env_interface
        logger.warning(
            "[CONFIG] NETMON_INTERFACE=%s is not up, falling back to auto detection",
            env_interface,
        )

    default_iface = _detect_default_interface()
    if default_iface and _interface_is_up(default_iface):
        logger.info("[CONFIG] Auto-detected capture interface from default route: %s", default_iface)
        return default_iface

    for iface, stat in psutil.net_if_stats().items():
        if stat.isup and iface != "lo":
            logger.info("[CONFIG] Auto-detected fallback capture interface: %s", iface)
            return iface

    logger.warning("[CONFIG] No active non-loopback interface found, using loopback interface 'lo'")
    return "lo"


INTERFACE = _resolve_capture_interface()