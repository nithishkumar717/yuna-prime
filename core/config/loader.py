import os
import yaml
from pathlib import Path
from pydantic import ValidationError
from dotenv import load_dotenv
from .models import YunaConfiguration
from .exceptions import ConfigurationValidationError


class ConfigurationLoader:
    def __init__(self, config_dir: str = "core/config"):
        self.config_dir = Path(config_dir)
        load_dotenv()

    def load_yaml(self, filename: str) -> dict:
        file_path = self.config_dir / filename
        if not file_path.exists():
            return {}
        with open(file_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def deep_merge(self, dict1: dict, dict2: dict) -> dict:
        result = dict1.copy()
        for k, v in dict2.items():
            if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                result[k] = self.deep_merge(result[k], v)
            else:
                result[k] = v
        return result

    def build_config(self) -> YunaConfiguration:
        # Load Default
        base_config = self.load_yaml("default.yaml")

        # Load Feature Modules
        feature_configs = ["security.yaml", "dashboard.yaml", "premium.yaml", "ai.yaml"]
        for feat in feature_configs:
            feat_config = self.load_yaml(feat)
            base_config = self.deep_merge(base_config, feat_config)

        # Load Environment
        env = os.getenv("YUNA_ENV", "development")
        env_config = self.load_yaml(f"{env}.yaml")

        merged_config = self.deep_merge(base_config, env_config)

        # Merge direct .env overrides
        if "bot" not in merged_config:
            merged_config["bot"] = {}
        if "database" not in merged_config:
            merged_config["database"] = {}
        if "ai" not in merged_config:
            merged_config["ai"] = {}

        token = os.getenv("DISCORD_TOKEN") or os.getenv("TOKEN")
        if token:
            merged_config["bot"]["token"] = token
        if os.getenv("MONGODB_URI"):
            merged_config["database"]["mongodb_uri"] = os.getenv("MONGODB_URI")
        if os.getenv("GEMINI_API_KEY"):
            merged_config["ai"]["gemini_api_key"] = os.getenv("GEMINI_API_KEY")

        try:
            return YunaConfiguration(**merged_config)
        except ValidationError as e:
            raise ConfigurationValidationError(
                f"Configuration validation failed:\\n{e}"
            )
