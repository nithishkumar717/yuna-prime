import sys
import os
from loguru import logger
from core.config.manager import ConfigManager

# Log Directories strictly adhering to ADR-002
LOG_DIRS = [
    "application", "security", "audit", "performance", 
    "errors", "database", "dashboard", "ai", "commands"
]
for d in LOG_DIRS:
    os.makedirs(f"logs/{d}", exist_ok=True)

def _formatter(record):
    """
    ADR-002 Format:
    Timestamp | Level | Module | Component | Event | Message | Guild ID | User ID | Correlation ID
    """
    extra = record["extra"]
    module = extra.get("module", "CORE")
    component = extra.get("component", record["name"])
    event = extra.get("event", "Log")
    guild_id = extra.get("guild_id", "-")
    user_id = extra.get("user_id", "-")
    correlation_id = extra.get("correlation_id", "-")
    
    fmt = (
        "<green>{time:YYYY-MM-DD hh:mm:ss A} IST</green> | "
        "<level>{level: <8}</level> | "
        f"<cyan>{module: <11}</cyan> | "
        f"<blue>{component: <15}</blue> | "
        f"<magenta>{event: <12}</magenta> | "
        "<level>{message}</level> | "
        f"Guild: {guild_id} | "
        f"User: {user_id} | "
        f"CorrID: {correlation_id}\n{'{exception}'}"
    )
    return fmt

def setup_loguru():
    """Initializes Loguru based on Pydantic configuration and ADR-002 formatting in IST."""
    try:
        config = ConfigManager.get_config()
        level = config.logging.level
        rotation = config.logging.rotation
        retention = config.logging.retention
    except Exception:
        level = "INFO"
        rotation = "5 MB"
        retention = "10 days"

    from utils.time_utils import IST
    logger.remove()
    logger.configure(patcher=lambda r: r.update(time=r["time"].astimezone(IST)))
    
    # Console handler
    logger.add(sys.stdout, level=level, format=_formatter)
    
    # File handlers mapped to ADR-002 directories
    logger.add("logs/application/app.log", level=level, rotation=rotation, retention=retention, format=_formatter, filter=lambda r: r["extra"].get("module") == "APPLICATION")
    logger.add("logs/security/security.log", level=level, rotation=rotation, retention=retention, format=_formatter, filter=lambda r: r["extra"].get("module") == "SECURITY")
    logger.add("logs/audit/audit.log", level=level, rotation=rotation, retention=retention, format=_formatter, filter=lambda r: r["extra"].get("module") == "AUDIT")
    logger.add("logs/performance/performance.log", level=level, rotation=rotation, retention=retention, format=_formatter, filter=lambda r: r["extra"].get("module") == "PERFORMANCE")
    logger.add("logs/errors/error.log", level="ERROR", rotation=rotation, retention=retention, format=_formatter) # Catch all errors globally
    logger.add("logs/database/db.log", level=level, rotation=rotation, retention=retention, format=_formatter, filter=lambda r: r["extra"].get("module") == "DATABASE")
    logger.add("logs/dashboard/dashboard.log", level=level, rotation=rotation, retention=retention, format=_formatter, filter=lambda r: r["extra"].get("module") == "DASHBOARD")
    logger.add("logs/ai/ai.log", level=level, rotation=rotation, retention=retention, format=_formatter, filter=lambda r: r["extra"].get("module") == "AI")
    logger.add("logs/commands/commands.log", level=level, rotation=rotation, retention=retention, format=_formatter, filter=lambda r: r["extra"].get("module") == "COMMANDS")

def get_logger(module: str, component: str = "General"):
    """
    Returns a logger explicitly bound to a specific Module and Component as per ADR-002.
    """
    return logger.bind(module=module.upper(), component=component)
