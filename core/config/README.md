# Yuna Configuration System

An enterprise-grade configuration system built on Pydantic v2 and YAML, ensuring strong type-safety and seamless environment overrides across the entire Yuna architecture.

## 🏗️ Architecture

Configuration values are resolved in the following hierarchical priority (ADR-001):
1. **Default Configuration** (`default.yaml`)
2. **Environment Configuration** (e.g., `development.yaml` based on `YUNA_ENV`)
3. **Environment Variables** (`.env` file or exported runtime variables)

## 🚀 Usage

The entire configuration tree is strictly typed. Any missing critical variables (e.g., `DISCORD_TOKEN`) will intentionally crash the application at boot (Fail-fast).

```python
from core.config.manager import ConfigManager

# Load the singleton config
config = ConfigManager.get_config()

# Strictly typed access
prefix = config.bot.prefix
mongo_uri = config.database.mongodb_uri.unicode_string()
token = config.bot.token.get_secret_value()
```

## 🛠️ Modifying Configuration
To add a new configuration setting:
1. Define the Pydantic schema in `models.py`.
2. Update the default value in `default.yaml`.
3. Override if necessary in `.env`.
