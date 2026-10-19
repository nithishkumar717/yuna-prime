# Yuna Logging Framework

Provides structured logging across all Yuna modules using Loguru.
Ensures every log adheres to ADR-002:
`Timestamp | Level | Module | Component | Event | Message | Guild ID | User ID | Correlation ID`

## 🚀 Usage

Instead of using raw `print` statements or generic loggers, use the domain-specific logger:

```python
from core.logging import SecurityLogger

SecurityLogger.warning("Unauthorized access attempt", event="Ban", user_id="12345")
```
