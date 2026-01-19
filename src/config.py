import json
from pathlib import Path

CONFIG_FILE = Path("config/config.json")

def carregar_config():
    print(">>> carregar_config() chamada <<<")
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def salvar_config(dados: dict):
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=4, ensure_ascii=False)
