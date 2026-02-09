# VMware ESXi Backup Tool für macOS

Eine eigenständige macOS-Anwendung zur Sicherung und Wiederherstellung von VMware ESXi Servern (Host-Konfigurationen und VMDK-Dateien).

![macOS](https://img.shields.io/badge/macOS-10.14+-blue.svg)
![Python](https://img.shields.io/badge/Python-3.9+-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## 📋 Inhaltsverzeichnis

- [Features](#-features)
- [Screenshots](#-screenshots)
- [Installation](#-installation)
- [Verwendung](#-verwendung)
- [Backup-Struktur](#-backup-struktur)
- [Anforderungen](#-anforderungen)
- [Technische Details](#-technische-details)
- [Fehlerbehebung](#-fehlerbehebung)
- [Lizenz](#-lizenz)

## ✨ Features

### Backup-Funktionen

- **Host-Sicherung**: Vollständige Sicherung von ESXi Host-Konfigurationen
  - Systeminformationen (CPU, RAM, Speicher)
  - Netzwerk-Konfiguration (VLANs, Portgruppen)
  - DNS- und Zeitkonfiguration
  - Datastore-Informationen
- **VMDK-Sicherung**: Sichern von virtuellen Festplatten (VMDK-Dateien)
  - Unterstützung für große Dateien (>100GB)
  - Automatische Erkennung von Descriptor- und Flat-Dateien
  - Mehrere Download-Methoden (HTTP, SSH/SCP, cat/dd)
  - Fortschrittsanzeige mit Cancel-Funktionalität
- **VM-Metadaten**: Vollständige VM-Konfigurationen werden gesichert
  - CPU, RAM, Netzwerk-Adapter
  - Festplatten-Konfiguration
  - Snapshot-Informationen

### Wiederherstellungs-Funktionen
- **VM-Wiederherstellung**: VMs aus Backups wiederherstellen
- **Host-Konfiguration**: Host-Einstellungen wiederherstellen
- **Datastore-Auswahl**: Flexible Auswahl des Ziel-Datastores

### Benutzerfreundlichkeit
- **Native macOS GUI**: Moderne grafische Oberfläche mit PyQt6
- **Server-Verwaltung**: Speichern und Verwalten mehrerer ESXi-Server
  - Verschlüsselte Passwort-Speicherung
  - Schnelle Server-Auswahl aus Liste
- **VM-Auswahl**: Möglichkeit, einzelne VMs auszuwählen oder alle zu sichern
- **Fortschrittsanzeige**: Echtzeit-Fortschrittsanzeige für alle Operationen
- **Cancel-Funktionalität**: Downloads können jederzeit abgebrochen werden

### Sicherheit
- **Verschlüsselte Credentials**: Passwörter werden mit Fernet-Verschlüsselung gespeichert
- **SSL/TLS-Unterstützung**: Unterstützt selbstsignierte Zertifikate
- **Eigenständig**: Keine zusätzliche Software erforderlich

## 📸 Screenshots

<img width="805" height="807" alt="Bildschirmfoto 2026-02-10 um 00 12 04" src="https://github.com/user-attachments/assets/8eb10949-eca9-4a66-968d-0134deca41d5" />

## 🚀 Installation

### Voraussetzungen

- **macOS**: 10.14 (Mojave) oder höher
- **Python**: 3.9 oder höher (meist bereits auf macOS installiert)
- **Internetverbindung**: Für den Download der Python-Pakete

### Schnellstart mit Setup-Skript

Das einfachste Installationsverfahren:

```bash
# Repository klonen
git clone https://github.com/lippie281/vmware-esxi-backup.git
cd vmware-esxi-backup

# Setup-Skript ausführen (erstellt venv und installiert Abhängigkeiten)
chmod +x setup.sh
./setup.sh

# Anwendung starten
source venv/bin/activate
python3 main.py
```

### Manuelle Installation

#### 1. Repository klonen

```bash
git clone https://github.com/IHR_USERNAME/vmware-esxi-backup.git
cd vmware-esxi-backup
```

#### 2. Virtuelles Environment erstellen (empfohlen)

```bash
python3 -m venv venv
source venv/bin/activate
```

#### 3. Abhängigkeiten installieren

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

#### 4. Anwendung starten

```bash
python3 main.py
```

### Installation ohne venv (nicht empfohlen)

```bash
pip3 install -r requirements.txt
python3 main.py
```

**Hinweis**: Die Verwendung eines virtuellen Environments wird dringend empfohlen, um Konflikte mit anderen Python-Projekten zu vermeiden.

## 📖 Verwendung

### GUI starten

```bash
# Mit aktiviertem venv
source venv/bin/activate
python3 main.py

# Oder direkt mit venv-Python
./venv/bin/python3 main.py
```

### Schritt-für-Schritt-Anleitung

#### 1. Verbindung herstellen

1. Öffnen Sie die Anwendung
2. Gehen Sie zum Tab **"Verbindung"**
3. Geben Sie die ESXi Server-Daten ein:
   - **IP-Adresse oder Hostname** (z.B. `192.168.1.100`)
   - **Port** (Standard: `443`)
   - **Benutzername** (z.B. `root`)
   - **Passwort**
4. Optional: Klicken Sie auf **"Speichern"**, um die Server-Daten zu speichern
5. Klicken Sie auf **"Verbinden"**

Nach erfolgreicher Verbindung werden alle VMs und Datastores angezeigt.

#### 2. Server-Konfiguration speichern

- Geben Sie einen **Namen** für die Server-Konfiguration ein
- Klicken Sie auf **"Speichern"**
- Die Konfiguration erscheint in der Dropdown-Liste
- Zum Laden: Wählen Sie die Konfiguration aus der Liste und klicken Sie auf **"Verbinden"**

#### 3. Backup erstellen

1. Gehen Sie zum Tab **"Backup"**
2. Wählen Sie die Backup-Optionen:
   - ☑ **Host-Konfiguration sichern**
   - ☑ **VMs sichern**
3. Optional: Wählen Sie spezifische VMs aus der Liste aus (Standard: Alle VMs)
4. Wählen Sie das **Backup-Zielverzeichnis** (klicken Sie auf "Durchsuchen...")
5. Klicken Sie auf **"Backup starten"**
6. Der Fortschritt wird im Status-Bereich angezeigt
7. Sie können den Download jederzeit mit **"Abbrechen"** stoppen

#### 4. Wiederherstellung

1. Gehen Sie zum Tab **"Wiederherstellung"**
2. Wählen Sie das **Backup-Verzeichnis** aus
3. Wählen Sie die **VM** oder **Host-Konfiguration** aus der Liste
4. Für VMs: Wählen Sie den **Ziel-Datastore**
5. Klicken Sie auf **"Wiederherstellen"**

### Tipps

- **Große VMDK-Dateien**: Downloads können bei großen Dateien (>50GB) mehrere Stunden dauern
- **Laufende VMs**: Für konsistente Backups sollten VMs ausgeschaltet werden oder ein Snapshot erstellt werden
- **Netzwerk**: Stellen Sie sicher, dass eine stabile Verbindung zum ESXi Server besteht
- **SSH**: Für optimale Download-Performance sollte SSH auf dem ESXi Server aktiviert sein

## 📁 Backup-Struktur

Backups werden im folgenden Format gespeichert:

```
backup_verzeichnis/
├── Hostname_20250209_143022/
│   ├── host_config.json          # Host-Konfiguration
│   └── host_config_details.json  # Detaillierte Host-Informationen
│
├── VM_Name_20250209_143045/
│   ├── vm_info.json             # VM-Konfiguration und Metadaten
│   ├── disk1.vmdk               # VMDK Descriptor-Datei
│   ├── disk1-flat.vmdk          # VMDK Daten-Datei
│   ├── disk2.vmdk
│   └── disk2-flat.vmdk
│
└── VM_Name2_20250209_143100/
    └── ...
```

### Dateiformate

- **host_config.json**: Host-Konfiguration im JSON-Format
- **vm_info.json**: VM-Konfiguration mit allen Details (CPU, RAM, Netzwerk, etc.)
- **\*.vmdk**: VMware Disk Descriptor-Dateien
- **\*-flat.vmdk**: VMware Disk Daten-Dateien

## 🔧 Anforderungen

### System-Anforderungen

- **Betriebssystem**: macOS 10.14 (Mojave) oder höher
- **Python**: 3.9 oder höher
- **RAM**: Mindestens 4GB (für große VMDK-Dateien empfohlen: 8GB+)
- **Festplattenspeicher**: Abhängig von der Größe der zu sichernden VMs

### ESXi Server-Anforderungen

- **VMware ESXi**: Version 6.0 oder höher
- **API-Zugriff**: Muss aktiviert sein (Standard)
- **HTTP-Datastore-Zugriff**: Für VMDK-Downloads empfohlen
- **SSH**: Optional, aber empfohlen für bessere Download-Performance
- **Benutzer-Berechtigungen**:
  - Host-Konfiguration lesen
  - VM-Konfiguration lesen
  - Datastore-Zugriff (für VMDK-Downloads)

### Netzwerk-Anforderungen

- **HTTPS**: Port 443 (Standard)
- **HTTP**: Port 80 (optional, für Datastore-Zugriff)
- **SSH**: Port 22 (optional, für optimale Performance)

## 🔬 Technische Details

### Verwendete Technologien

- **Python 3.9+**: Programmiersprache
- **PyQt6**: GUI-Framework für native macOS-Oberfläche
- **pyvmomi**: VMware vSphere API Python-Bibliothek
- **paramiko**: SSH/SCP für Datei-Downloads
- **requests**: HTTP/HTTPS für Datastore-Zugriff
- **cryptography**: Verschlüsselung für gespeicherte Passwörter

### Download-Methoden

Die Anwendung verwendet mehrere Methoden für VMDK-Downloads:

1. **SCP (Standard)**: Für Dateien < 10GB
2. **SSH cat**: Fallback-Methode mit Cancel-Unterstützung
3. **SSH dd**: Für gesperrte Dateien (laufende VMs)
4. **HTTP/HTTPS**: Alternative Methode über Datastore-URLs

### Sicherheit

- **Passwort-Verschlüsselung**: Fernet-Symmetric-Encryption (AES 128)
- **SSL/TLS**: Unterstützt selbstsignierte Zertifikate
- **Lokale Speicherung**: Credentials werden nur lokal gespeichert (`~/.vmware_backup/`)

## 🐛 Fehlerbehebung

### Verbindungsfehler

**Problem**: "Verbindung fehlgeschlagen"

**Lösungen**:
- Überprüfen Sie die Netzwerkverbindung zum ESXi Server
- Stellen Sie sicher, dass der API-Zugriff aktiviert ist
- Überprüfen Sie Benutzername und Passwort
- Prüfen Sie die Firewall-Einstellungen
- Bei selbstsignierten Zertifikaten wird die Validierung automatisch umgangen

### VMDK-Download-Probleme

**Problem**: "HTTP-Fehler 404" oder "Download fehlgeschlagen"

**Lösungen**:
- Stellen Sie sicher, dass HTTP-Datastore-Zugriff aktiviert ist:
  - Host → Manage → Services → Enable "HTTP Client"
- Überprüfen Sie die Berechtigungen des Benutzers
- Aktivieren Sie SSH für bessere Download-Performance:
  - Host → Manage → Services → Enable "SSH"
- Für laufende VMs: Erstellen Sie einen Snapshot oder schalten Sie die VM aus

**Problem**: "Device or resource busy"

**Lösungen**:
- Die VM läuft und die VMDK-Datei ist gesperrt
- Erstellen Sie einen Snapshot für konsistente Backups
- Oder schalten Sie die VM aus

### PyQt6-Fehler

**Problem**: "Symbol not found: __Z13lcPermissionsv"

**Lösung**:
- Stellen Sie sicher, dass das venv aktiviert ist: `source venv/bin/activate`
- Neuinstallation von PyQt6:
  ```bash
  pip uninstall PyQt6 PyQt6-Qt6 PyQt6_sip
  pip install PyQt6>=6.10.0
  ```

### Allgemeine Probleme

**Problem**: "ModuleNotFoundError"

**Lösung**:
- Stellen Sie sicher, dass alle Abhängigkeiten installiert sind:
  ```bash
  pip install -r requirements.txt
  ```
- Aktivieren Sie das venv: `source venv/bin/activate`

**Problem**: Downloads stoppen nicht bei "Abbrechen"

**Lösung**:
- Die Cancel-Funktionalität funktioniert nur bei der SSH cat/dd-Methode
- Bei SCP-Downloads kann es einige Sekunden dauern, bis der Download gestoppt wird
- Für große Dateien wird automatisch die cat-Methode verwendet, die besser unterbrechbar ist

## 📝 Bekannte Einschränkungen

- **Große Dateien**: Downloads von sehr großen VMDK-Dateien (>100GB) können mehrere Stunden dauern
- **Laufende VMs**: Backups von laufenden VMs können inkonsistent sein (Snapshot wird automatisch erstellt)
- **Netzwerk**: Benötigt stabile Netzwerkverbindung zum ESXi Server
- **macOS-only**: Aktuell nur für macOS verfügbar (kann aber auf Linux/Windows portiert werden)

## 🤝 Beitragen

Beiträge sind willkommen! Bitte:

1. Forken Sie das Repository
2. Erstellen Sie einen Feature-Branch (`git checkout -b feature/AmazingFeature`)
3. Committen Sie Ihre Änderungen (`git commit -m 'Add some AmazingFeature'`)
4. Pushen Sie zum Branch (`git push origin feature/AmazingFeature`)
5. Öffnen Sie einen Pull Request

## 📄 Lizenz

Dieses Projekt steht unter der MIT-Lizenz. Siehe `LICENSE` Datei für Details.

## 👤 Autor

**Philipp**

- GitHub: [@lippie281](https://github.com/lippie281
## 🙏 Danksagungen

- VMware für die vSphere API
- PyQt-Projekt für die hervorragende GUI-Bibliothek
- Allen Beitragenden der verwendeten Open-Source-Bibliotheken

## 📞 Unterstützung

Bei Problemen oder Fragen:

1. Überprüfen Sie die [Fehlerbehebung](#-fehlerbehebung)
2. Überprüfen Sie die Log-Ausgabe in der GUI
3. Stellen Sie sicher, dass alle [Anforderungen](#-anforderungen) erfüllt sind
4. Öffnen Sie ein [Issue](https://github.com/lippie281/vmware-esxi-backup/issues) auf GitHub

---

**Hinweis**: Dieses Tool ist nicht von VMware entwickelt oder unterstützt. Verwenden Sie es auf eigene Verantwortung.
