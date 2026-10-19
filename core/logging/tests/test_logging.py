from core.logging import setup_loguru, SecurityLogger, DatabaseLogger

def test_setup_loguru():
    """Ensure setup loguru does not throw exceptions."""
    setup_loguru()
    assert True

def test_security_logger():
    # Should run without raising
    SecurityLogger.info("Test security info log")
    SecurityLogger.warning("Test security warning log")

def test_database_logger():
    DatabaseLogger.error("Test database error log", event="ConnectionFailed")
