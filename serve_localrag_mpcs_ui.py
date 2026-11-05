#!/usr/bin/env python3
"""
MPCS-LocalRAG Unified Cognitive Studio Launcher
================================================
Launches the integrated Neuro-Symbolic Cognitive UI connecting:
  - LocalRAG / LocalKG (Dual-Persona Spreading Activation & Provenance Engine)
  - MPCS Generation 9 Core (dlCBF Bloom Gates, HyST Slots, VAD Somatic Markers, TIDE Anytime Sufficiency Routing)

Usage:
  python serve_localrag_mpcs_ui.py [--port 8090] [--no-browser]
"""

from __future__ import annotations

import argparse
import os
import sys
import webbrowser
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
BRIDGE_DIR = REPO_ROOT / "Model" / "experimental" / "09_localrag_bridge"

if str(BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_DIR))

try:
    from server import start_server
except ImportError as e:
    print(f"[ERROR] Failed to import bridge server: {e}")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="MPCS-LocalRAG Cognitive Studio Launcher")
    parser.add_argument("--port", type=int, default=8090, help="Port to bind server (default: 8090)")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically launch browser")
    args = parser.parse_args()

    print("\n" + "=" * 65)
    print("   MPCS-LocalRAG Neuro-Symbolic Cognitive Studio")
    print("   Architecture: MPCS Gen 9 (TIDE) + LocalKG Dual-Persona RAG")
    print(f"   Server URL:   http://localhost:{args.port}")
    print("=" * 65 + "\n")

    start_server(port=args.port, open_browser=not args.no_browser)


if __name__ == "__main__":
    main()

