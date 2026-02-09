#!/usr/bin/env python3
"""
VMware ESXi Backup Tool - Hauptanwendung
Startet die GUI-Anwendung
"""

import sys
import os

# Füge das aktuelle Verzeichnis zum Python-Pfad hinzu
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gui import main

if __name__ == '__main__':
    main()
