from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from .models import GameTemplate, TemplateInfo
from .template_engine import TemplateEngine


class TemplateMarketplace:
    """File-based local marketplace stub. Stores metadata in .index.json.
    This avoids network dependencies and can be replaced later."""

    def __init__(self, storage_dir: Optional[str] = None):
        self.storage = Path(storage_dir or "templates_market").resolve()
        self.storage.mkdir(parents=True, exist_ok=True)
        self.index = self.storage / ".index.json"
        if not self.index.exists():
            self.index.write_text(json.dumps({"templates": []}, indent=2), encoding="utf-8")

    def upload_template(self, template: GameTemplate, author: str) -> str:
        meta = self._load_index()
        tid = f"{template.info.id}-{len(meta['templates'])+1}"
        entry = {
            "id": tid,
            "name": template.info.name,
            "version": template.info.version,
            "author": author,
            "description": template.info.description,
        }
        meta["templates"].append(entry)
        self._save_index(meta)
        return tid

    def download_template(self, template_id: str) -> Optional[TemplateInfo]:
        # In this stub, returns metadata if found; in real impl it would fetch files
        meta = self._load_index()
        for t in meta.get("templates", []):
            if t.get("id") == template_id:
                return TemplateInfo(id=t["id"], name=t["name"], version=t["version"], description=t.get("description", ""))
        return None

    def rate_template(self, template_id: str, rating: int) -> None:
        meta = self._load_index()
        for t in meta.get("templates", []):
            if t.get("id") == template_id:
                ratings = t.setdefault("ratings", [])
                ratings.append(max(1, min(5, int(rating))))
        self._save_index(meta)

    def search_templates(self, query: str, filters: Dict) -> List[TemplateInfo]:
        q = (query or "").lower()
        meta = self._load_index()
        results: List[TemplateInfo] = []
        for t in meta.get("templates", []):
            text = f"{t.get('name','')} {t.get('description','')}".lower()
            if q in text:
                results.append(TemplateInfo(id=t["id"], name=t["name"], version=t["version"], description=t.get("description", "")))
        return results

    def _load_index(self) -> dict:
        try:
            return json.loads(self.index.read_text(encoding="utf-8"))
        except Exception:
            return {"templates": []}

    def _save_index(self, data: dict) -> None:
        self.index.write_text(json.dumps(data, indent=2), encoding="utf-8")

