#!/usr/bin/env python3
"""
Script para debuggear la configuración del gateway.
Ejecuta esto desde el directorio gateway para ver qué configuración se está cargando.
"""

import os
import sys
from pathlib import Path
import yaml
sys.path.insert(0, '.')

from app.config import settings


def check_executable(name: str, path: str) -> bool:
    """Verificar si un ejecutable existe."""
    if not path:
        print(f"  ✗ {name}: Ruta no configurada")
        return False
    
    exe_path = Path(path)
    if exe_path.exists():
        print(f"  ✓ {name}: {path}")
        return True
    else:
        print(f"  ✗ {name}: No encontrado en {path}")
        return False

def find_unity_installations():
    """Buscar instalaciones comunes de Unity."""
    common_paths = [
        "C:\\Program Files\\Unity\\Hub\\Editor",
        "C:\\Program Files\\Unity\\Editor",
        "C:\\Program Files (x86)\\Unity\\Editor",
    ]
    
    unity_versions = []
    for base_path in common_paths:
        if Path(base_path).exists():
            for item in Path(base_path).iterdir():
                if item.is_dir():
                    unity_exe = item / "Editor" / "Unity.exe"
                    if unity_exe.exists():
                        unity_versions.append(str(unity_exe))
    
    return unity_versions

def find_blender_installations():
    """Buscar instalaciones comunes de Blender."""
    common_paths = [
        "C:\\Program Files\\Blender Foundation",
        "C:\\Program Files (x86)\\Blender Foundation",
        "D:\\blender",
        "C:\\blender",
    ]
    
    blender_versions = []
    for base_path in common_paths:
        if Path(base_path).exists():
            # Buscar en subdirectorios
            for item in Path(base_path).rglob("blender.exe"):
                blender_versions.append(str(item))
    
    return blender_versions

def check_bridge_scripts():
    """Verificar que los scripts de los bridges existan."""
    scripts = {
        "Unity Bridge": "bridges/mcp_adapter.py",
        "Blender Bridge": "mcp_blender_addon/server_bootstrap.py"
    }
    
    all_exist = True
    for name, script_path in scripts.items():
        if Path(script_path).exists():
            print(f"  ✓ {name}: {script_path}")
        else:
            print(f"  ✗ {name}: No encontrado en {script_path}")
            all_exist = False
    
    return all_exist

def main():
    print("=== CONFIGURACIÓN DEL GATEWAY ===")
    print(f"AUTH.REQUIRE_API_KEY: {settings.auth.require_api_key}")
    print(f"AUTH.API_KEY: {settings.auth.api_key}")
    print(f"SERVER.HOST: {settings.server.host}")
    print(f"SERVER.PORT: {settings.server.port}")

    print("\n=== VARIABLES DE ENTORNO ===")
    env_vars = [
        'AUTH__API_KEY',
        'AUTH__REQUIRE_API_KEY', 
        'VITE_API_KEY'
    ]

    for var in env_vars:
        value = os.getenv(var)
        print(f"{var}: {value}")

    print("\n=== ARCHIVOS DE CONFIGURACIÓN ===")
    from pathlib import Path

    # Verificar .env
    env_file = Path('.env')
    print(f".env existe: {env_file.exists()}")
    if env_file.exists():
        print("Contenido de .env:")
        print(env_file.read_text())

    # Verificar config/settings.yaml
    yaml_file = Path('config/settings.yaml')
    print(f"\nconfig/settings.yaml existe: {yaml_file.exists()}")
    if yaml_file.exists():
        print("Contenido de config/settings.yaml:")
        print(yaml_file.read_text())



    print("=== VERIFICACIÓN DE UNITY Y BLENDER ===")
    
    # Cargar configuración actual
    config_path = Path("config/settings.yaml")
    if not config_path.exists():
        print("✗ No se encontró config/settings.yaml")
        return
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # Verificar rutas configuradas
    print("\n1. Ejecutables configurados:")
    processes = config.get("gateway", {}).get("processes", {})
    unity_exe = processes.get("unity", {}).get("exe", "")
    blender_exe = processes.get("blender", {}).get("exe", "")
    
    unity_ok = check_executable("Unity", unity_exe)
    blender_ok = check_executable("Blender", blender_exe)
    
    # Buscar instalaciones alternativas si no están configuradas
    if not unity_ok:
        print("\n2. Buscando instalaciones de Unity disponibles:")
        unity_versions = find_unity_installations()
        if unity_versions:
            for version in unity_versions:
                print(f"  • {version}")
            print(f"\n  Sugerencia: Actualizar config con:")
            print(f"    exe: \"{unity_versions[0]}\"")
        else:
            print("  No se encontraron instalaciones de Unity")
    
    if not blender_ok:
        print("\n3. Buscando instalaciones de Blender disponibles:")
        blender_versions = find_blender_installations()
        if blender_versions:
            for version in blender_versions:
                print(f"  • {version}")
            print(f"\n  Sugerencia: Actualizar config con:")
            print(f"    exe: \"{blender_versions[0]}\"")
        else:
            print("  No se encontraron instalaciones de Blender")
    
    # Verificar scripts de bridges
    print("\n4. Scripts de bridges:")
    scripts_ok = check_bridge_scripts()
    
    # Resumen
    print("\n=== RESUMEN ===")
    if unity_ok and blender_ok and scripts_ok:
        print("✓ Todo configurado correctamente")
    else:
        print("✗ Faltan componentes:")
        if not unity_ok:
            print("  - Unity no encontrado o mal configurado")
        if not blender_ok:
            print("  - Blender no encontrado o mal configurado")
        if not scripts_ok:
            print("  - Scripts de bridges faltantes")

if __name__ == "__main__":
    main()



