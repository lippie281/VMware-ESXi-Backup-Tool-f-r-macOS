# Kurzanleitung - VMware ESXi Backup Tool

## Schnellstart

1. **Installation**:
   ```bash
   ./setup.sh
   ```

2. **Anwendung starten**:
   ```bash
   python3 main.py
   ```

## Schritt-für-Schritt Anleitung

### 1. Verbindung zum ESXi Server

- Öffnen Sie den Tab "Verbindung"
- Geben Sie ein:
  - **Host**: IP-Adresse oder Hostname Ihres ESXi Servers (z.B. `192.168.1.100`)
  - **Port**: Standard ist `443` (HTTPS)
  - **Benutzername**: Meist `root` oder ein anderer Administrator-Benutzer
  - **Passwort**: Ihr ESXi Passwort
- Klicken Sie auf "Verbinden"
- Bei erfolgreicher Verbindung sehen Sie eine Bestätigung im Status-Bereich

### 2. Backup konfigurieren

- Wechseln Sie zum Tab "Backup"
- **Backup-Optionen**:
  - ✅ Host-Konfiguration sichern: Sichert Systeminformationen, Netzwerk- und Zeitkonfiguration
  - ✅ VMs (VMDK) sichern: Sichert virtuelle Festplatten der VMs
  
- **VM-Auswahl**:
  - Klicken Sie auf "VMs aktualisieren" um die Liste zu laden
  - Wählen Sie einzelne VMs aus (optional) - wenn keine ausgewählt, werden alle gesichert
  
- **Backup-Ziel**:
  - Klicken Sie auf "Durchsuchen..." und wählen Sie ein Verzeichnis
  - Stellen Sie sicher, dass genug Speicherplatz vorhanden ist

### 3. Backup starten

- Klicken Sie auf "Backup starten"
- Der Fortschritt wird im Status-Bereich angezeigt
- Sie können den Vorgang jederzeit mit "Abbrechen" stoppen

## Was wird gesichert?

### Host-Konfiguration
- Systeminformationen (Name, Version, Build, Vendor, Model)
- Hardware-Spezifikationen (CPU-Kerne, RAM)
- Netzwerk-Konfiguration (DNS, IP-Routen)
- Zeitkonfiguration (Zeitzone)
- UUID und Verbindungsstatus

### VMs (VMDK)
- VM-Metadaten (Name, UUID, Gast-OS, Hardware-Konfiguration)
- Alle VMDK-Dateien (virtuelle Festplatten)
- VM-Konfigurationsdateien

## Backup-Verzeichnisstruktur

```
Ihr_Backup_Verzeichnis/
├── esxi-host_20250209_143022/
│   ├── host_config.json          # Host-Informationen
│   └── host_config_details.json  # Detaillierte Konfiguration
│
├── Windows-VM_20250209_143045/
│   ├── vm_info.json              # VM-Metadaten
│   ├── Windows-VM.vmdk           # Hauptfestplatte
│   └── Windows-VM_1.vmdk         # Weitere Festplatten
│
└── Linux-VM_20250209_143050/
    ├── vm_info.json
    └── Linux-VM.vmdk
```

## Wichtige Hinweise

⚠️ **Speicherplatz**: VMDK-Dateien können sehr groß sein. Stellen Sie sicher, dass genug Speicherplatz vorhanden ist.

⚠️ **Netzwerk**: Große Backups können lange dauern. Eine stabile Netzwerkverbindung ist wichtig.

⚠️ **Berechtigungen**: Der verwendete Benutzer benötigt Leseberechtigungen für Hosts und VMs.

⚠️ **VM-Status**: VMs können während des Backups laufen. Für konsistente Backups sollten VMs jedoch ausgeschaltet oder Snapshots erstellt werden.

## Fehlerbehebung

**"Verbindung fehlgeschlagen"**
- Überprüfen Sie die Netzwerkverbindung
- Überprüfen Sie Host, Port, Benutzername und Passwort
- Stellen Sie sicher, dass der ESXi Server erreichbar ist

**"VMDK-Download fehlgeschlagen"**
- Überprüfen Sie die Benutzerberechtigungen
- Stellen Sie sicher, dass HTTP-Datastore-Zugriff aktiviert ist
- Große Dateien benötigen Zeit - haben Sie Geduld

**"Keine VMs gefunden"**
- Überprüfen Sie die Verbindung
- Stellen Sie sicher, dass VMs auf dem Server vorhanden sind
- Klicken Sie auf "VMs aktualisieren"

## Tipps

💡 **Regelmäßige Backups**: Erstellen Sie regelmäßige Backups, besonders vor wichtigen Änderungen.

💡 **Inkrementelle Backups**: Die Anwendung erstellt vollständige Backups. Für inkrementelle Backups müssten Sie externe Tools verwenden.

💡 **Komprimierung**: VMDK-Dateien können nach dem Backup komprimiert werden, um Speicherplatz zu sparen.

💡 **Verschlüsselung**: Für sensible Daten sollten Sie Backups verschlüsseln.
