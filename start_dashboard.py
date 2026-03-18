#!/usr/bin/env python3
"""
Launcher ufficiale per la Hypnonyx Dashboard
Gestisce l'avvio del backend e del frontend in un unico processo.
"""

import subprocess
import os
import sys
import time
from pathlib import Path


# ANSI colors for premium terminal output
class Colors:
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def print_banner():
    banner = f"""
{Colors.CYAN}{Colors.BOLD}
    ____             ___                      __      ____  __
   / __ \\___ _   __ /   | ____ ____  ____  __/ /_    / __ \\/ /
  / / / / _ \\ | / // /| |/ __ `/ _ \\/ __ \\/ _  __/   / / / / / 
 / /_/ /  __/ |/ // ___ / /_/ /  __/ / / / / / /_    / /_/ /_/  
/_____/\\___/|___//_/  |_\\__, /\\___/_/ /_/_/  \\__/   /_____/(_)  
                       /____/                                   
{Colors.RESET}
{Colors.BLUE}--- Kanban Dashboard Multi-Agent System ---{Colors.RESET}
"""
    print(banner)


def check_requirements():
    """Verifica che le dipendenze base siano installate"""
    try:
        import fastapi
        import uvicorn
        import websockets
    except ImportError:
        print(
            f"{Colors.YELLOW}Dipendenze mancanti. Installazione in corso...{Colors.RESET}"
        )
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "fastapi",
                "uvicorn",
                "aiosqlite",
                "websockets",
            ]
        )


def start_dashboard():
    print_banner()
    check_requirements()

    dashboard_api = Path(__file__).parent / "dashboard" / "api.py"

    if not dashboard_api.exists():
        print(
            f"{Colors.BOLD}Errore: Impossibile trovare dashboard/api.py{Colors.RESET}"
        )
        return

    print(f"{Colors.GREEN}🚀 Avvio Backend e Frontend...{Colors.RESET}")
    print(
        f"{Colors.CYAN}📍 Dashboard accessibile su: {Colors.BOLD}http://localhost:8000{Colors.RESET}"
    )
    print(f"{Colors.BLUE}ℹ️  Premi CTRL+C per fermare il sistema.{Colors.RESET}")
    print("-" * 60)

    try:
        # Avvia uvicorn tramite sys.executable
        # L'API (api.py) monta automaticamente i file statici (frontend)
        subprocess.run([sys.executable, str(dashboard_api)])
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}👋 Dashboard fermata correttamente.{Colors.RESET}")
    except Exception as e:
        print(f"\n{Colors.BOLD}Errore fatale: {e}{Colors.RESET}")
        import traceback

        print(traceback.format_exc())


if __name__ == "__main__":
    start_dashboard()
