import json
import os
import re

def _safe_load_config_yaml(file_path: str = "config.yml") -> dict:
    """Loads config.yml safely with PyYAML if available, or using a built-in clean parser."""
    try:
        import yaml
        with open(file_path, "r", encoding="utf-8") as f:
            loaded = yaml.safe_load(f)
            if isinstance(loaded, dict):
                return loaded
    except ImportError:
        pass
    except Exception as e:
        print(f"[CONFIG LOADER] PyYAML error reading {file_path}: {e}")

    # Built-in resilient parser for config.yml
    data = {}
    if not os.path.isfile(file_path):
        return data

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        current_list_key = None
        for raw_line in lines:
            line = re.sub(r"#.*$", "", raw_line).rstrip()
            if not line.strip():
                continue

            # List item (e.g. "  - item")
            m_item = re.match(r"^\s*-\s*(.*)$", line)
            if m_item:
                if current_list_key and isinstance(data.get(current_list_key), list):
                    val = m_item.group(1).strip()
                    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                        val = val[1:-1]
                    data[current_list_key].append(val)
                continue

            # Key-value pair (e.g. "KEY: value" or "KEY:")
            m_kv = re.match(r"^([A-Za-z0-9_]+)\s*:\s*(.*)$", line)
            if m_kv:
                k = m_kv.group(1).strip()
                raw_v = m_kv.group(2).strip()
                if not raw_v:
                    data[k] = []
                    current_list_key = k
                else:
                    current_list_key = None
                    low = raw_v.lower()
                    if low == "true":
                        v = True
                    elif low == "false":
                        v = False
                    elif raw_v.isdigit():
                        v = int(raw_v)
                    else:
                        if (raw_v.startswith('"') and raw_v.endswith('"')) or (raw_v.startswith("'") and raw_v.endswith("'")):
                            raw_v = raw_v[1:-1]
                        v = raw_v
                    data[k] = v
    except Exception as e:
        print(f"[CONFIG LOADER] Fallback parser error: {e}")

    return data

config = _safe_load_config_yaml("config.yml")

## Language settings ##
valid_language_codes = []
lang_directory = "lang"

current_language_code = config['LANGUAGE']

for filename in os.listdir(lang_directory):
    if filename.startswith("lang.") and filename.endswith(".json") and os.path.isfile(
            os.path.join(lang_directory, filename)):
        language_code = filename.split(".")[1]
        valid_language_codes.append(language_code)

def load_current_language() -> dict:
    lang_file_path = os.path.join(
        lang_directory, f"lang.{current_language_code}.json")
    with open(lang_file_path, encoding="utf-8") as lang_file:
        current_language = json.load(lang_file)
    return current_language

# Instructions loader
def load_instructions() -> dict:
    instructions = {}
    for file_name in os.listdir("instructions"):
        if file_name.endswith('.txt'):
            file_path = os.path.join("instructions", file_name)
            with open(file_path, 'r', encoding='utf-8') as file:
                file_content = file.read()
            # Use the file name without extension as the variable name
                variable_name = file_name.split('.')[0]
                instructions[variable_name] = file_content
    return instructions

def load_active_channels() -> dict:
    if os.path.exists("channels.json"):
        with open("channels.json", "r", encoding='utf-8') as f:
            active_channels = json.load(f)
    return active_channels