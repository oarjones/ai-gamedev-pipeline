from __future__ import annotations

from pathlib import Path
from typing import Tuple


class CodeGenerator:
    def generate_player_controller(self, params: dict) -> str:
        speed = params.get("player_speed", 5.0)
        jump = params.get("jump_height", 2.0)
        return f"""
using UnityEngine;

public class PlayerController : MonoBehaviour {{
    public float moveSpeed = {float(speed):.2f}f;
    public float jumpHeight = {float(jump):.2f}f;
    private Rigidbody2D rb;

    void Awake() {{ rb = GetComponent<Rigidbody2D>(); }}
    void Update() {{
        float h = Input.GetAxis("Horizontal");
        rb.velocity = new Vector2(h * moveSpeed, rb.velocity.y);
        if (Input.GetButtonDown("Jump")) {{ rb.velocity = new Vector2(rb.velocity.x, jumpHeight); }}
    }}
}}
""".strip()

    def generate_enemy_ai(self, ai_type: str, difficulty: str) -> str:
        return f"""
using UnityEngine;

public class EnemyAI : MonoBehaviour {{
    public string aiType = "{ai_type}";
    public string difficulty = "{difficulty}";
    void Update() {{ /* TODO: implement {ai_type} behaviour */ }}
}}
""".strip()

    def generate_game_manager(self, game_mode: str) -> str:
        return f"""
using UnityEngine;

public class GameManager : MonoBehaviour {{
    public string gameMode = "{game_mode}";
    void Start() {{ DontDestroyOnLoad(this.gameObject); }}
}}
""".strip()

    def generate_save_system(self, storage_type: str) -> str:
        return f"""
using UnityEngine;
using System.IO;

public static class SaveSystem {{
    public static void Save(string key, string data) {{
        PlayerPrefs.SetString(key, data);
        PlayerPrefs.Save();
    }}
    public static string Load(string key) {{
        return PlayerPrefs.GetString(key, "");
    }}
}}
""".strip()

    def generate_inventory_system(self, slots: int, stackable: bool) -> str:
        return f"""
using System.Collections.Generic;

public class Inventory {{
    public int slots = {int(slots)};
    public bool stackable = {str(stackable).lower()};
    private List<string> items = new List<string>();
}}
""".strip()


class AssetGenerator:
    def create_placeholder_sprites(self, count: int, style: str, out_dir: Path) -> None:
        out_dir.mkdir(parents=True, exist_ok=True)
        for i in range(count):
            self._write_png_placeholder(out_dir / f"sprite_{i+1}.png")

    def generate_terrain(self, size: Tuple[int, int], type: str, out_dir: Path) -> None:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"terrain_{size[0]}x{size[1]}_{type}.txt").write_text("placeholder", encoding="utf-8")

    def create_ui_elements(self, theme: str, out_dir: Path) -> None:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"ui_{theme}.txt").write_text("placeholder", encoding="utf-8")

    def generate_sound_effects(self, type: str, out_dir: Path) -> None:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"sfx_{type}.txt").write_text("placeholder", encoding="utf-8")

    def _write_png_placeholder(self, path: Path) -> None:
        # Minimal 1x1 transparent PNG
        png_bytes = bytes.fromhex(
            "89504E470D0A1A0A0000000D49484452000000010000000108060000001F15C4890000000A49444154789C6360000002000154AFA6A90000000049454E44AE426082"
        )
        path.write_bytes(png_bytes)

