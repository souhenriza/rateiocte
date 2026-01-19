import json
import os
from pathlib import Path

CONFIG_FILE = Path("config/config.json")

def carregar_config(self):
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            cfg = json.load(f)
            self.v_planilha.set(cfg.get("planilha", ""))
            self.v_pdfs.set(cfg.get("pdfs", ""))
            self.v_xml.set(cfg.get("xml", ""))
            self.v_saida.set(cfg.get("saida", ""))

def salvar_config(self):
    with open(CONFIG_FILE, "w") as f:
        json.dump({
            "planilha": self.v_planilha.get(),
            "pdfs": self.v_pdfs.get(),
            "xml": self.v_xml.get(),
            "saida": self.v_saida.get()
            }, f, indent=4)