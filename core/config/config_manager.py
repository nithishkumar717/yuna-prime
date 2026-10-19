import os
import yaml
from pathlib import Path
from dotenv import load_dotenv
from typing import Any, Dict


class ConfigManager:
    """
    Configuration Manager for Yuna.
    Features:
    - .env loading
    - YAML configuration loading
    - Environment overrides
    - Singleton configuration service
    """

    def __init__(self, config_dir: str = "core/config"):
        self.config_dir = Path(config_dir)
        self._configs: Dict[str, dict] = {}

        # Load environment variables
        load_dotenv()

    def load(self, filename: str) -> dict:
        """Loads a YAML file, handling environment overrides."""
        if filename in self._configs:
            return self._configs[filename]

        file_path = self.config_dir / filename
        if not file_path.exists():
            return {}

        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

            # Simple environment variable override logic
            for key, value in data.items():
                env_val = os.getenv(f"YUNA_{key.upper()}")
                if env_val:
                    data[key] = env_val

            self._configs[filename] = data
            return data

    def get(self, filename: str, key: str, default: Any = None) -> Any:
        return self.load(filename).get(key, default)
