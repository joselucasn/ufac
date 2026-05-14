"""
run.sh — Inicializa o Sistema de Gestão Contratual UFAC
"""
import subprocess
import sys
import os

if __name__ == "__main__":
    port = sys.argv[1] if len(sys.argv) > 1 else "8501"
    os.chdir(os.path.dirname(__file__))
    
    cmd = [
        "streamlit", "run", "dashboard.py",
        "--server.port", port,
        "--server.address", "0.0.0.0",
        "--server.headless", "true",
        "--browser.gatherUsageStats", "false",
    ]
    
    subprocess.run(cmd)
