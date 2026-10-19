from core.logging.logger import get_logger

class DatabaseLogger:
    """Provides structured logging for database events."""
    
    _logger = get_logger("DATABASE", "DatabaseSystem")
    
    @classmethod
    def info(cls, message: str, event: str = "Log", guild_id: str = "-", user_id: str = "-", correlation_id: str = "-"):
        cls._logger.info(message, event=event, guild_id=guild_id, user_id=user_id, correlation_id=correlation_id)
        
    @classmethod
    def warning(cls, message: str, event: str = "Warning", guild_id: str = "-", user_id: str = "-", correlation_id: str = "-"):
        cls._logger.warning(message, event=event, guild_id=guild_id, user_id=user_id, correlation_id=correlation_id)
        
    @classmethod
    def error(cls, message: str, event: str = "Error", guild_id: str = "-", user_id: str = "-", correlation_id: str = "-"):
        cls._logger.error(message, event=event, guild_id=guild_id, user_id=user_id, correlation_id=correlation_id)
        
    @classmethod
    def critical(cls, message: str, event: str = "Critical", guild_id: str = "-", user_id: str = "-", correlation_id: str = "-"):
        cls._logger.critical(message, event=event, guild_id=guild_id, user_id=user_id, correlation_id=correlation_id)
