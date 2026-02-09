#!/bin/bash
# Setup-Skript für VMware ESXi Backup Tool
# Dieses Skript erstellt ein virtuelles Environment und installiert alle Abhängigkeiten

set -e  # Beende bei Fehlern

echo "=========================================="
echo "VMware ESXi Backup Tool - Setup"
echo "=========================================="
echo ""

# Prüfe Python-Version
if ! command -v python3 &> /dev/null; then
    echo "❌ Fehler: Python 3 ist nicht installiert!"
    echo "Bitte installieren Sie Python 3.9 oder höher."
    exit 1
fi

python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Python-Version: $python_version"
echo ""

# Prüfe Python-Version (mindestens 3.9)
python3 -c "import sys; exit(0 if sys.version_info >= (3, 9) else 1)" 2>/dev/null || {
    echo "❌ Fehler: Python 3.9 oder höher ist erforderlich!"
    echo "Aktuelle Version: $python_version"
    exit 1
}

# Erstelle virtuelles Environment
if [ -d "venv" ]; then
    echo "⚠️  Virtuelles Environment existiert bereits."
    read -p "Möchten Sie es neu erstellen? (j/n): " recreate_venv
    if [ "$recreate_venv" = "j" ] || [ "$recreate_venv" = "J" ]; then
        echo "Entferne altes virtuelles Environment..."
        rm -rf venv
    else
        echo "Verwende vorhandenes virtuelles Environment."
    fi
fi

if [ ! -d "venv" ]; then
    echo "Erstelle virtuelles Environment..."
    python3 -m venv venv
    echo "✓ Virtuelles Environment erstellt"
fi

# Aktiviere virtuelles Environment
echo "Aktiviere virtuelles Environment..."
source venv/bin/activate

# Upgrade pip
echo ""
echo "Aktualisiere pip..."
pip install --upgrade pip --quiet

# Installiere Abhängigkeiten
echo ""
echo "Installiere Abhängigkeiten..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    echo "✓ Abhängigkeiten installiert"
else
    echo "❌ Fehler: requirements.txt nicht gefunden!"
    exit 1
fi

echo ""
echo "=========================================="
echo "✅ Setup erfolgreich abgeschlossen!"
echo "=========================================="
echo ""
echo "Um die Anwendung zu starten, führen Sie aus:"
echo ""
echo "  source venv/bin/activate"
echo "  python3 main.py"
echo ""
echo "Oder direkt:"
echo ""
echo "  ./venv/bin/python3 main.py"
echo ""
