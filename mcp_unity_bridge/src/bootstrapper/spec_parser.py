from __future__ import annotations

import re
from typing import List

from .models import GameSpecification, GameMechanic


class SpecificationParser:
    """
    Heuristic parser for natural language game prompts.
    Designed to be LLM-pluggable, but works offline with rules.
    """

    GENRES = [
        "platformer",
        "shooter",
        "rpg",
        "strategy",
        "puzzle",
        "adventure",
        "simulation",
        "survival",
        "racing",
        "metroidvania",
        "roguelike",
        "sports",
    ]

    DEFAULT_PACKAGES = [
        "com.unity.test-framework",
        "com.unity.cinemachine",
        "com.unity.inputsystem",
    ]

    def parse(self, prompt: str) -> GameSpecification:
        text = prompt.lower()

        game_type = self._extract_type(text)
        name = self._extract_name(prompt)
        genre = self._extract_genre(text)
        platforms = self._extract_platforms(text)
        unity_version = self._extract_version(text)
        art_style = self._extract_art_style(text)
        scope = self._extract_scope(text)
        mechanics = self._extract_mechanics(text)
        packages = self._infer_packages(text, mechanics)
        template = self._extract_template(text)

        return GameSpecification(
            name=name,
            type=game_type,
            genre=genre,
            platform=platforms,
            unity_version=unity_version,
            packages=packages,
            mechanics=mechanics,
            art_style=art_style,
            target_audience=self._extract_audience(text),
            estimated_scope=scope,
            template=template,
        )

    def _extract_type(self, text: str):
        if re.search(r"\bvr\b", text):
            return "VR"
        if re.search(r"\bar\b", text):
            return "AR"
        if re.search(r"\b3d\b|\bthree[- ]?d\b", text):
            return "3D"
        return "2D"

    def _extract_name(self, prompt: str) -> str:
        # Use first title-cased phrase in quotes or fallback
        m = re.search(r'"([^"]{3,60})"', prompt)
        if m:
            return m.group(1).strip()
        # Fallback to first 5 words titlecased
        words = re.findall(r"[A-Za-z0-9']+", prompt)
        return " ".join(words[:5]).title() or "New Unity Game"

    def _extract_genre(self, text: str) -> str:
        for g in self.GENRES:
            if g in text:
                return g
        return "adventure"

    def _extract_platforms(self, text: str) -> List[str]:
        plats = []
        if "pc" in text or "windows" in text:
            plats.append("PC")
        if "mac" in text or "osx" in text or "macos" in text:
            plats.append("Mac")
        if "linux" in text:
            plats.append("Linux")
        if "android" in text:
            plats.append("Android")
        if "ios" in text or "iphone" in text or "ipad" in text:
            plats.append("iOS")
        if not plats:
            plats = ["PC"]
        return plats

    def _extract_version(self, text: str) -> str:
        m = re.search(r"unity\s*(hub\s*)?(version|v)?\s*([0-9]{4}\.[0-9]+\.[0-9]+[a-z]\d+)", text)
        if m:
            return m.group(3)
        return ""

    def _extract_art_style(self, text: str) -> str:
        for key in ["pixel art", "low poly", "realistic", "toon", "voxel", "hand drawn"]:
            if key in text:
                return key
        return "generic"

    def _extract_scope(self, text: str):
        if "prototype" in text:
            return "prototype"
        if "mvp" in text:
            return "mvp"
        if "full" in text or "complete" in text:
            return "full"
        return "prototype"

    def _extract_mechanics(self, text: str) -> List[GameMechanic]:
        mechanics = []
        mapping = {
            "jump": "Player can jump",
            "shoot": "Player can shoot",
            "collect": "Collectibles present",
            "inventory": "Inventory system",
            "craft": "Crafting system",
            "procedural": "Procedural generation",
            "dialog": "Dialogue system",
        }
        for key, desc in mapping.items():
            if key in text:
                mechanics.append(GameMechanic(name=key, description=desc))
        if not mechanics:
            mechanics.append(GameMechanic(name="core-loop", description="Basic movement and interaction"))
        return mechanics

    def _infer_packages(self, text: str, mechanics: List[GameMechanic]) -> List[str]:
        packages = list(self.DEFAULT_PACKAGES)
        if "vr" in text:
            packages.append("com.unity.xr.management")
        if any(m.name == "dialog" for m in mechanics):
            packages.append("com.unity.visualscripting")
        return sorted(set(packages))

    def _extract_template(self, text: str):
        m = re.search(r"template\s*:\s*([a-z0-9_-]+)", text)
        return m.group(1) if m else None

    def _extract_audience(self, text: str):
        if "kids" in text or "niños" in text:
            return "kids"
        if "hardcore" in text:
            return "hardcore"
        if "casual" in text:
            return "casual"
        return "general"

