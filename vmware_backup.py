"""
VMware ESXi Backup Modul
Handhabt die Verbindung und Sicherung von ESXi Servern
"""

import ssl
import os
import shutil
from datetime import datetime
from typing import List, Dict, Optional
from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim, vmodl


class VMwareBackup:
    """Klasse zur Verwaltung von VMware ESXi Backups"""
    
    def __init__(self, host: str, user: str, password: str, port: int = 443):
        """
        Initialisiert die Verbindung zum ESXi Server
        
        Args:
            host: ESXi Server Hostname oder IP
            user: Benutzername
            password: Passwort
            port: Port (Standard: 443)
        """
        self.host = host
        self.user = user
        self.password = password
        self.port = port
        self.service_instance = None
        self.content = None
        self._cancel_flag = None  # Referenz zum Cancel-Flag vom Thread
        self._active_ssh_connection = None  # Aktive SSH-Verbindung für Cancel
        self._active_scp_session = None  # Aktive SCP-Session für Cancel
    
    def set_cancel_flag(self, thread):
        """Setzt das Cancel-Flag vom Thread"""
        self._cancel_flag = thread
    
    def cancel_backup(self):
        """Bricht den aktuellen Backup-Vorgang ab"""
        # Schließe aktive SSH-Verbindungen
        if self._active_ssh_connection:
            try:
                self._active_ssh_connection.close()
            except:
                pass
            self._active_ssh_connection = None
        
        if self._active_scp_session:
            try:
                self._active_scp_session.close()
            except:
                pass
            self._active_scp_session = None
    
    def _is_cancelled(self) -> bool:
        """Prüft, ob der Backup-Vorgang abgebrochen wurde"""
        if self._cancel_flag:
            return self._cancel_flag._cancel
        return False
        
    def connect(self) -> bool:
        """
        Stellt Verbindung zum ESXi Server her
        
        Returns:
            True bei erfolgreicher Verbindung, False sonst
        """
        try:
            # SSL-Zertifikat-Validierung umgehen (für selbstsignierte Zertifikate)
            context = ssl._create_unverified_context()
            
            self.service_instance = SmartConnect(
                host=self.host,
                user=self.user,
                pwd=self.password,
                port=self.port,
                sslContext=context
            )
            
            self.content = self.service_instance.RetrieveContent()
            return True
            
        except Exception as e:
            print(f"Verbindungsfehler: {str(e)}")
            return False
    
    def disconnect(self):
        """Trennt die Verbindung zum ESXi Server"""
        if self.service_instance:
            Disconnect(self.service_instance)
    
    def get_hosts(self) -> List[vim.HostSystem]:
        """
        Ruft alle Hosts vom ESXi Server ab
        
        Returns:
            Liste von HostSystem-Objekten
        """
        if not self.content:
            return []
        
        host_view = self.content.viewManager.CreateContainerView(
            self.content.rootFolder,
            [vim.HostSystem],
            True
        )
        hosts = host_view.view
        host_view.Destroy()
        return hosts
    
    def get_vms(self) -> List[vim.VirtualMachine]:
        """
        Ruft alle VMs vom ESXi Server ab
        
        Returns:
            Liste von VirtualMachine-Objekten
        """
        if not self.content:
            return []
        
        vm_view = self.content.viewManager.CreateContainerView(
            self.content.rootFolder,
            [vim.VirtualMachine],
            True
        )
        vms = vm_view.view
        vm_view.Destroy()
        return vms
    
    def get_host_info(self, host: vim.HostSystem) -> Dict:
        """
        Ruft Host-Informationen ab
        
        Args:
            host: HostSystem-Objekt
            
        Returns:
            Dictionary mit Host-Informationen
        """
        return {
            'name': host.name,
            'version': host.config.product.version,
            'build': host.config.product.build,
            'vendor': host.config.product.vendor,
            'model': host.hardware.systemInfo.model,
            'cpu_cores': host.hardware.cpuInfo.numCpuCores,
            'memory_mb': host.hardware.memorySize // (1024 * 1024),
            'uuid': host.hardware.systemInfo.uuid,
            'connection_state': str(host.runtime.connectionState),
            'power_state': str(host.runtime.powerState),
        }
    
    def backup_host_config(self, host: vim.HostSystem, backup_dir: str) -> bool:
        """
        Sichert die Host-Konfiguration
        
        Args:
            host: HostSystem-Objekt
            backup_dir: Zielverzeichnis für Backup
            
        Returns:
            True bei Erfolg, False sonst
        """
        try:
            host_info = self.get_host_info(host)
            host_name = host_info['name'].replace(' ', '_')
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            host_backup_dir = os.path.join(backup_dir, f"{host_name}_{timestamp}")
            os.makedirs(host_backup_dir, exist_ok=True)
            
            # Host-Informationen speichern
            import json
            config_file = os.path.join(host_backup_dir, 'host_config.json')
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(host_info, f, indent=2, ensure_ascii=False)
            
            # Host-Konfiguration exportieren (falls verfügbar)
            try:
                # Versuche Host-Profile zu exportieren
                host_config = {
                    'config': {
                        'network': {
                            'dns': list(host.config.network.dnsConfig.addressHostName) if hasattr(host.config.network.dnsConfig, 'addressHostName') else [],
                            'ip_routes': []
                        },
                        'datetime': {
                            'timezone': host.config.dateTimeInfo.timeZone.name if hasattr(host.config.dateTimeInfo, 'timeZone') else None
                        }
                    }
                }
                
                config_details_file = os.path.join(host_backup_dir, 'host_config_details.json')
                with open(config_details_file, 'w', encoding='utf-8') as f:
                    json.dump(host_config, f, indent=2, ensure_ascii=False)
            except Exception as e:
                print(f"Warnung: Konnte einige Host-Konfigurationsdetails nicht exportieren: {str(e)}")
            
            return True
            
        except Exception as e:
            print(f"Fehler beim Sichern der Host-Konfiguration: {str(e)}")
            return False
    
    def get_vm_disks(self, vm: vim.VirtualMachine) -> List[Dict]:
        """
        Ruft alle Festplatten einer VM ab
        
        Args:
            vm: VirtualMachine-Objekt
            
        Returns:
            Liste von Festplatten-Informationen
        """
        disks = []
        if vm.config and vm.config.hardware and vm.config.hardware.device:
            for device in vm.config.hardware.device:
                if isinstance(device, vim.vm.device.VirtualDisk):
                    disk_info = {
                        'label': device.deviceInfo.label if device.deviceInfo else 'Unknown',
                        'capacity': device.capacityInKB * 1024,  # In Bytes
                        'backing': {}
                    }
                    
                    if device.backing:
                        if hasattr(device.backing, 'fileName'):
                            disk_info['backing']['fileName'] = device.backing.fileName
                        if hasattr(device.backing, 'datastore'):
                            if device.backing.datastore:
                                disk_info['backing']['datastore'] = device.backing.datastore.name
                    
                    disks.append(disk_info)
        return disks
    
    def backup_vmdk(self, vm: vim.VirtualMachine, backup_dir: str, progress_callback=None) -> bool:
        """
        Sichert VMDK-Dateien einer VM
        
        Args:
            vm: VirtualMachine-Objekt
            backup_dir: Zielverzeichnis für Backup
            progress_callback: Optional Callback-Funktion für Fortschritt
            
        Returns:
            True bei Erfolg, False sonst
        """
        try:
            vm_name = vm.name.replace(' ', '_')
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            vm_backup_dir = os.path.join(backup_dir, f"{vm_name}_{timestamp}")
            os.makedirs(vm_backup_dir, exist_ok=True)
            
            # Prüfe VM-Status
            power_state = str(vm.runtime.powerState)
            is_running = power_state == "poweredOn"
            was_powered_on = is_running
            
            if is_running and progress_callback:
                progress_callback(f"Warnung: VM {vm.name} läuft.")
                progress_callback(f"Versuche Backup mit Snapshot-Methode...")
                progress_callback(f"Hinweis: Falls Backup fehlschlägt, VM manuell ausschalten und erneut versuchen.")
            
            # VM-Informationen speichern
            import json
            vm_info = {
                'name': vm.name,
                'uuid': vm.config.uuid if vm.config else None,
                'guest_os': vm.config.guestFullName if vm.config else None,
                'memory_mb': vm.config.hardware.memoryMB if vm.config else None,
                'num_cpu': vm.config.hardware.numCPU if vm.config else None,
                'power_state': power_state,
                'is_running': is_running,
                'disks': self.get_vm_disks(vm)
            }
            
            vm_info_file = os.path.join(vm_backup_dir, 'vm_info.json')
            with open(vm_info_file, 'w', encoding='utf-8') as f:
                json.dump(vm_info, f, indent=2, ensure_ascii=False)
            
            # VMDK-Dateien sichern über Datastore Browser
            if progress_callback:
                progress_callback(f"Starte VMDK-Sicherung für {vm.name}...")
            
            # Für VMDK-Sicherung benötigen wir Zugriff auf den Datastore
            # Dies erfolgt über den Datastore Browser API
            datastores = self._get_datastores()
            
            disks_backed_up = 0
            for disk_info in vm_info['disks']:
                # Prüfe auf Cancel vor jeder Disk
                if self._is_cancelled():
                    if progress_callback:
                        progress_callback("Backup wurde abgebrochen")
                    break
                
                if 'datastore' in disk_info.get('backing', {}):
                    datastore_name = disk_info['backing']['datastore']
                    file_name = disk_info['backing'].get('fileName', '')
                    
                    if file_name:
                        # Finde den Datastore
                        datastore = next((ds for ds in datastores if ds.name == datastore_name), None)
                        if datastore:
                            if progress_callback:
                                progress_callback(f"Sichere VMDK: {file_name}...")
                            
                            # Prüfe auf Cancel vor Download
                            if self._is_cancelled():
                                if progress_callback:
                                    progress_callback("Backup wurde abgebrochen")
                                break
                            
                            # Versuche Snapshot-basiertes Backup, wenn VM läuft
                            if is_running:
                                if progress_callback:
                                    progress_callback(f"VM läuft - verwende Snapshot-Methode...")
                                
                                # Versuche zuerst Snapshot-Methode
                                success = self._download_vmdk_with_snapshot(
                                    vm, datastore, file_name, vm_backup_dir, progress_callback
                                )
                                
                                # Prüfe auf Cancel nach Snapshot-Versuch
                                if self._is_cancelled():
                                    if progress_callback:
                                        progress_callback("Backup wurde abgebrochen")
                                    break
                                
                                # Falls Snapshot-Methode fehlschlägt, gebe klare Anweisungen
                                if not success:
                                    if progress_callback:
                                        progress_callback(f"⚠️ Backup fehlgeschlagen: Datei ist gesperrt (Device or resource busy)")
                                        progress_callback(f"")
                                        progress_callback(f"Lösungsoptionen:")
                                        progress_callback(f"1. VM manuell ausschalten und Backup erneut starten")
                                        progress_callback(f"2. VM über vSphere Client ausschalten")
                                        progress_callback(f"3. Backup während VM-Wartungsfenster durchführen")
                                        progress_callback(f"")
                                        progress_callback(f"Hinweis: Die VM läuft weiterhin normal.")
                            else:
                                # Normales Backup für ausgeschaltete VMs
                                success = self._download_vmdk(datastore, file_name, vm_backup_dir, progress_callback)
                            
                            # Prüfe auf Cancel nach Download
                            if self._is_cancelled():
                                if progress_callback:
                                    progress_callback("Backup wurde abgebrochen")
                                break
                            
                            if success:
                                disks_backed_up += 1
                            else:
                                if progress_callback:
                                    progress_callback(f"Warnung: Konnte VMDK {file_name} nicht vollständig sichern")
            
            if progress_callback:
                progress_callback(f"VMDK-Sicherung für {vm.name} abgeschlossen ({disks_backed_up}/{len(vm_info['disks'])} Festplatten)")
            
            return True
            
        except Exception as e:
            print(f"Fehler beim Sichern der VMDK: {str(e)}")
            return False
    
    def _get_datastores(self) -> List[vim.Datastore]:
        """Ruft alle Datastores ab"""
        if not self.content:
            return []
        
        datastore_view = self.content.viewManager.CreateContainerView(
            self.content.rootFolder,
            [vim.Datastore],
            True
        )
        datastores = datastore_view.view
        datastore_view.Destroy()
        return datastores
    
    def _download_vmdk(self, datastore: vim.Datastore, file_path: str, 
                      backup_dir: str, progress_callback=None) -> bool:
        """
        Lädt eine VMDK-Datei vom Datastore herunter
        VMDK-Dateien bestehen aus:
        1. Descriptor-Datei (.vmdk) - kleine Datei mit Metadaten
        2. Daten-Datei (-flat.vmdk) - große Datei mit den eigentlichen Daten
        
        Args:
            datastore: Datastore-Objekt
            file_path: Pfad zur VMDK-Datei auf dem Datastore
            backup_dir: Zielverzeichnis
            progress_callback: Optional Callback für Fortschritt
            
        Returns:
            True bei Erfolg, False sonst
        """
        try:
            import re
            
            # Entferne Datastore-Präfix
            clean_path = file_path
            if file_path.startswith('['):
                match = re.match(r'\[.*?\]\s*(.+)', file_path)
                if match:
                    clean_path = match.group(1).strip()
            
            # Prüfe auf Cancel vor Download
            if self._is_cancelled():
                if progress_callback:
                    progress_callback("Backup wurde abgebrochen")
                return False
            
            # Versuche zuerst SSH/SCP (zuverlässiger für große Dateien)
            if self._download_vmdk_scp(datastore, file_path, backup_dir, progress_callback):
                # Prüfe auf Cancel nach Descriptor-Download
                if self._is_cancelled():
                    if progress_callback:
                        progress_callback("Backup wurde abgebrochen")
                    return False
                
                # Prüfe, ob es eine Descriptor-Datei ist und lade die -flat.vmdk Datei
                descriptor_path = os.path.join(backup_dir, os.path.basename(clean_path))
                if os.path.exists(descriptor_path):
                    # Parse Descriptor, um die -flat.vmdk Datei zu finden
                    flat_file = self._parse_vmdk_descriptor(descriptor_path, clean_path)
                    if flat_file:
                        # Lade die -flat.vmdk Datei
                        dir_path = os.path.dirname(clean_path)
                        flat_path = f"{dir_path}/{flat_file}" if dir_path else flat_file
                        if progress_callback:
                            progress_callback(f"Lade Daten-Datei: {flat_path}...")
                        
                        # Prüfe auf Cancel vor Flat-Datei-Download
                        if self._is_cancelled():
                            if progress_callback:
                                progress_callback("Backup wurde abgebrochen")
                            return False
                        
                        if not self._download_vmdk_scp(datastore, f"[{datastore.name}] {flat_path}", backup_dir, progress_callback):
                            return False
                return True
            
            # Falls SSH/SCP fehlschlägt, versuche HTTP-Download
            if progress_callback:
                progress_callback(f"SSH/SCP nicht verfügbar, versuche HTTP-Download...")
            if self._download_vmdk_http(datastore, file_path, backup_dir, progress_callback):
                # Prüfe, ob es eine Descriptor-Datei ist und lade die -flat.vmdk Datei
                descriptor_path = os.path.join(backup_dir, os.path.basename(clean_path))
                if os.path.exists(descriptor_path):
                    # Parse Descriptor, um die -flat.vmdk Datei zu finden
                    flat_file = self._parse_vmdk_descriptor(descriptor_path, clean_path)
                    if flat_file:
                        # Lade die -flat.vmdk Datei
                        dir_path = os.path.dirname(clean_path)
                        flat_path = f"{dir_path}/{flat_file}" if dir_path else flat_file
                        if progress_callback:
                            progress_callback(f"Lade Daten-Datei: {flat_path}...")
                        self._download_vmdk_http(datastore, f"[{datastore.name}] {flat_path}", backup_dir, progress_callback)
                return True
            
            # Falls beide Methoden fehlschlagen, versuche alternative Methode über vSphere API
            if progress_callback:
                progress_callback(f"SSH/SCP fehlgeschlagen, versuche vSphere API...")
            if self._download_vmdk_vsphere_api(datastore, file_path, backup_dir, progress_callback):
                return True
            
            # Falls beide Methoden fehlschlagen, speichere Metadaten
            import json
            vmdk_metadata = {
                'datastore': datastore.name,
                'file_path': file_path,
                'backup_timestamp': datetime.now().isoformat(),
                'note': 'VMDK-Metadaten gesichert. Download nicht verfügbar - möglicherweise Berechtigungsproblem oder HTTP-Datastore-Zugriff nicht aktiviert.'
            }
            
            file_name = os.path.basename(file_path)
            if file_name.startswith('['):
                import re
                match = re.match(r'\[.*?\]\s*(.+)', file_path)
                if match:
                    file_name = os.path.basename(match.group(1).strip())
            
            metadata_file = os.path.join(backup_dir, f"{file_name}.metadata.json")
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(vmdk_metadata, f, indent=2, ensure_ascii=False)
            
            if progress_callback:
                progress_callback(f"Metadaten für {file_name} gesichert")
            
            return True
            
        except Exception as e:
            if progress_callback:
                progress_callback(f"Fehler beim Herunterladen der VMDK: {str(e)}")
            return False
    
    def _find_snapshot_files(self, vm: vim.VirtualMachine, datastore: vim.Datastore,
                            original_file: str, progress_callback=None) -> List[str]:
        """
        Findet Snapshot-Dateien nach Snapshot-Erstellung
        
        Args:
            vm: VirtualMachine-Objekt
            datastore: Datastore-Objekt
            original_file: Pfad zur ursprünglichen VMDK-Datei
            progress_callback: Optional Callback
            
        Returns:
            Liste von Snapshot-Dateipfaden
        """
        try:
            import re
            import paramiko
            
            # Entferne Datastore-Präfix
            clean_path = original_file
            if original_file.startswith('['):
                match = re.match(r'\[.*?\]\s*(.+)', original_file)
                if match:
                    clean_path = match.group(1).strip()
            
            vm_dir = os.path.dirname(clean_path)
            base_name = os.path.splitext(os.path.basename(clean_path))[0]
            
            # SSH-Verbindung
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            try:
                ssh.connect(
                    self.host,
                    username=self.user,
                    password=self.password,
                    port=22,
                    timeout=10,
                    allow_agent=False,
                    look_for_keys=False
                )
                
                # Suche nach Snapshot-Dateien im VM-Verzeichnis
                # Snapshot-Dateien haben normalerweise Namen wie: VM-000001.vmdk, VM-000001-delta.vmdk, etc.
                search_path = f"/vmfs/volumes/{datastore.name}/{vm_dir}"
                
                # Suche nach verschiedenen Snapshot-Datei-Mustern
                patterns = [
                    f"'{base_name}-[0-9]+.*\\.vmdk$'",  # Standard-Snapshot-Format
                    f"'{base_name}.*delta.*\\.vmdk$'",  # Delta-Dateien
                    f"'{base_name}.*-snapshot.*\\.vmdk$'",  # Snapshot-Dateien
                ]
                
                snapshot_files = []
                for pattern in patterns:
                    stdin, stdout, stderr = ssh.exec_command(f"ls -1 '{search_path}' 2>/dev/null | grep -E {pattern}")
                    for line in stdout:
                        file_name = line.strip()
                        if file_name and file_name not in [os.path.basename(clean_path)]:
                            snapshot_path = f"[{datastore.name}] {vm_dir}/{file_name}"
                            if snapshot_path not in snapshot_files:
                                snapshot_files.append(snapshot_path)
                
                ssh.close()
                
                return snapshot_files
                
            except Exception as e:
                try:
                    ssh.close()
                except:
                    pass
                if progress_callback:
                    progress_callback(f"Fehler beim Suchen nach Snapshot-Dateien: {str(e)}")
                return []
                
        except Exception as e:
            if progress_callback:
                progress_callback(f"Fehler: {str(e)}")
            return []
    
    def _download_vmdk_with_snapshot(self, vm: vim.VirtualMachine, datastore: vim.Datastore, 
                                    file_path: str, backup_dir: str, progress_callback=None) -> bool:
        """
        Erstellt einen Snapshot und sichert die VMDK-Datei über den Snapshot
        
        Args:
            vm: VirtualMachine-Objekt
            datastore: Datastore-Objekt
            file_path: Pfad zur VMDK-Datei
            backup_dir: Zielverzeichnis
            progress_callback: Optional Callback
            
        Returns:
            True bei Erfolg, False sonst
        """
        snapshot = None
        try:
            if progress_callback:
                progress_callback(f"Erstelle Snapshot für konsistentes Backup...")
            
            # Erstelle Snapshot
            snapshot_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            task = vm.CreateSnapshot(
                name=snapshot_name,
                description="Backup Snapshot",
                memory=False,  # Kein Memory-Snapshot (schneller)
                quiesce=False  # Kein Quiesce (schneller, aber weniger konsistent)
            )
            
            # Warte auf Snapshot-Erstellung
            while task.info.state == 'running':
                import time
                time.sleep(1)
            
            if task.info.state == 'success':
                snapshot = task.info.result
                if progress_callback:
                    progress_callback(f"Snapshot erstellt: {snapshot_name}")
                
                # Nach Snapshot-Erstellung: Die ursprüngliche Datei bleibt gesperrt
                # Wir müssen die ursprüngliche Datei sichern, aber sie ist gesperrt
                # Lösung: Warte etwas und versuche dann die Datei zu sichern
                # Oder: Sichere die Snapshot-Dateien (Delta-Dateien)
                
                if progress_callback:
                    progress_callback(f"Warte kurz, damit Snapshot vollständig erstellt wird...")
                import time
                time.sleep(2)
                
                # Versuche die ursprüngliche Datei zu sichern
                # Manchmal wird sie nach kurzer Zeit entsperrt
                success = self._download_vmdk(datastore, file_path, backup_dir, progress_callback)
                
                # Falls das nicht funktioniert, versuche Snapshot-Dateien zu finden
                if not success:
                    if progress_callback:
                        progress_callback(f"Ursprüngliche Datei gesperrt, suche nach Snapshot-Dateien...")
                    
                    snapshot_files = self._find_snapshot_files(vm, datastore, file_path, progress_callback)
                    
                    if snapshot_files:
                        if progress_callback:
                            progress_callback(f"Snapshot-Dateien gefunden: {len(snapshot_files)}")
                        
                        # Sichere die Snapshot-Dateien
                        success = True
                        for snapshot_file in snapshot_files:
                            if progress_callback:
                                progress_callback(f"Sichere Snapshot-Datei: {snapshot_file}...")
                            if not self._download_vmdk(datastore, snapshot_file, backup_dir, progress_callback):
                                success = False
                                break
                
                # Lösche Snapshot nach Backup
                if snapshot:
                    if progress_callback:
                        progress_callback(f"Lösche Snapshot...")
                    try:
                        remove_task = snapshot.RemoveSnapshot_Task(removeChildren=False)
                        # Warte kurz auf Snapshot-Löschung
                        while remove_task.info.state == 'running':
                            time.sleep(0.5)
                    except Exception as e:
                        if progress_callback:
                            progress_callback(f"Warnung: Snapshot konnte nicht gelöscht werden: {str(e)}")
                
                return success
            else:
                if progress_callback:
                    progress_callback(f"Snapshot-Erstellung fehlgeschlagen: {task.info.error}")
                return False
                
        except Exception as e:
            if progress_callback:
                progress_callback(f"Fehler bei Snapshot-Backup: {str(e)}")
                progress_callback(f"Versuche direktes Backup ohne Snapshot...")
            
            # Fallback: Versuche direktes Backup
            return self._download_vmdk(datastore, file_path, backup_dir, progress_callback)
    
    def _parse_vmdk_descriptor(self, descriptor_path: str, original_path: str) -> str:
        """
        Parst eine VMDK-Descriptor-Datei, um den Namen der -flat.vmdk Datei zu finden
        
        Args:
            descriptor_path: Pfad zur lokalen Descriptor-Datei
            original_path: Original-Pfad der VMDK-Datei
            
        Returns:
            Name der -flat.vmdk Datei oder None
        """
        try:
            with open(descriptor_path, 'r') as f:
                content = f.read()
                
            # Suche nach der -flat.vmdk Datei im Descriptor
            # Format: RW <sectors> VMFS "<filename>-flat.vmdk"
            import re
            match = re.search(r'RW\s+\d+\s+VMFS\s+"([^"]+)"', content)
            if match:
                return match.group(1)
            
            # Alternative: Suche nach "Extent description" und extrahiere Dateinamen
            match = re.search(r'RW\s+\d+\s+\w+\s+"([^"]+-flat\.vmdk)"', content)
            if match:
                return match.group(1)
            
            # Falls nicht gefunden, konstruiere den Namen basierend auf dem Original-Namen
            base_name = os.path.splitext(os.path.basename(original_path))[0]
            return f"{base_name}-flat.vmdk"
            
        except Exception as e:
            print(f"Fehler beim Parsen der VMDK-Descriptor: {str(e)}")
            return None
    
    def _download_vmdk_scp(self, datastore: vim.Datastore, file_path: str,
                          backup_dir: str, progress_callback=None) -> bool:
        """
        Lädt VMDK über SSH/SCP herunter (alternative Methode)
        Diese Methode funktioniert, wenn SSH auf dem ESXi Server aktiviert ist.
        
        Args:
            datastore: Datastore-Objekt
            file_path: Pfad zur VMDK-Datei
            backup_dir: Zielverzeichnis
            progress_callback: Optional Callback
            
        Returns:
            True bei Erfolg, False sonst
        """
        try:
            import paramiko
            import re
            
            if progress_callback:
                progress_callback(f"Versuche SSH/SCP-Download...")
            
            # Entferne Datastore-Präfix
            clean_path = file_path
            if file_path.startswith('['):
                match = re.match(r'\[.*?\]\s*(.+)', file_path)
                if match:
                    clean_path = match.group(1).strip()
            
            # Konstruiere den vollständigen Pfad auf dem ESXi Server
            # Format: /vmfs/volumes/datastore_name/path/to/file.vmdk
            esxi_path = f"/vmfs/volumes/{datastore.name}/{clean_path}"
            
            # Prüfe auf Cancel
            if self._is_cancelled():
                if progress_callback:
                    progress_callback("Backup wurde abgebrochen")
                return False
            
            # SSH-Verbindung herstellen
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Speichere SSH-Verbindung für Cancel
            self._active_ssh_connection = ssh
            
            # Versuche verschiedene SSH-Ports (22 ist Standard, manchmal wird ein anderer Port verwendet)
            ssh_ports = [22, 2222]
            ssh_connected = False
            
            for ssh_port in ssh_ports:
                # Prüfe auf Cancel
                if self._is_cancelled():
                    ssh.close()
                    self._active_ssh_connection = None
                    if progress_callback:
                        progress_callback("Backup wurde abgebrochen")
                    return False
                
                try:
                    if progress_callback:
                        progress_callback(f"Versuche SSH-Verbindung auf Port {ssh_port}...")
                    ssh.connect(
                        self.host,
                        username=self.user,
                        password=self.password,
                        port=ssh_port,
                        timeout=10,
                        allow_agent=False,
                        look_for_keys=False
                    )
                    ssh_connected = True
                    if progress_callback:
                        progress_callback(f"SSH-Verbindung erfolgreich auf Port {ssh_port}")
                    break
                except Exception as e:
                    if progress_callback and ssh_port == ssh_ports[-1]:  # Nur beim letzten Versuch Fehler zeigen
                        progress_callback(f"SSH-Verbindung auf Port {ssh_port} fehlgeschlagen: {str(e)}")
                    continue
            
            if not ssh_connected:
                self._active_ssh_connection = None
                if progress_callback:
                    progress_callback(f"SSH-Verbindung fehlgeschlagen auf allen Ports")
                    progress_callback(f"Hinweis: SSH muss auf dem ESXi Server aktiviert sein")
                    progress_callback(f"  - Gehen Sie zu: Host → Manage → Services")
                    progress_callback(f"  - Aktivieren Sie den 'SSH' Service")
                return False
            
            # Prüfe, ob die Datei existiert
            stdin, stdout, stderr = ssh.exec_command(f"ls -lh '{esxi_path}'")
            exit_status = stdout.channel.recv_exit_status()
            
            if exit_status != 0:
                if progress_callback:
                    progress_callback(f"Datei nicht gefunden auf ESXi: {esxi_path}")
                ssh.close()
                return False
            
            # Dateigröße ermitteln
            file_info = stdout.read().decode('utf-8')
            if progress_callback:
                progress_callback(f"Datei gefunden: {file_info.strip()}")
            
            # Prüfe auf Cancel
            if self._is_cancelled():
                ssh.close()
                self._active_ssh_connection = None
                if progress_callback:
                    progress_callback("Backup wurde abgebrochen")
                return False
            
            # SCP-Download
            file_name = os.path.basename(clean_path)
            local_path = os.path.join(backup_dir, file_name)
            
            scp = ssh.open_sftp()
            self._active_scp_session = scp
            
            try:
                # Dateigröße für Fortschrittsanzeige
                file_size = scp.stat(esxi_path).st_size
                
                if progress_callback:
                    if file_size < 1024:
                        progress_callback(f"Datei ist sehr klein ({file_size} Bytes) - wahrscheinlich Descriptor-Datei")
                    else:
                        progress_callback(f"Starte SCP-Download ({file_size // (1024*1024)}MB)...")
                
                # Prüfe auf Cancel vor Download-Start
                if self._is_cancelled():
                    scp.close()
                    ssh.close()
                    self._active_scp_session = None
                    self._active_ssh_connection = None
                    if progress_callback:
                        progress_callback("Backup wurde abgebrochen")
                    return False
                
                # Versuche SCP.get() für kleine Dateien
                # Für große Dateien (>10GB) verwenden wir cat/dd, da SCP.get() nicht gut unterbrechbar ist
                if file_size > 10 * 1024 * 1024 * 1024:  # Größer als 10GB
                    if progress_callback:
                        progress_callback(f"Große Datei erkannt, verwende cat-Methode für bessere Cancel-Unterstützung...")
                    scp.close()
                    raise Exception("Use cat method for large file")
                
                # Verwende SCP.get() für normale Dateien
                scp.get(esxi_path, local_path)
                
                # Prüfe auf Cancel nach Download
                if self._is_cancelled():
                    scp.close()
                    ssh.close()
                    self._active_scp_session = None
                    self._active_ssh_connection = None
                    if os.path.exists(local_path):
                        try:
                            os.remove(local_path)
                        except:
                            pass
                    if progress_callback:
                        progress_callback("Download wurde abgebrochen")
                    return False
                
                # Prüfe, ob die Datei erfolgreich heruntergeladen wurde
                if os.path.exists(local_path):
                    actual_size = os.path.getsize(local_path)
                    if actual_size > 0:
                        if progress_callback:
                            if file_size > 0 and actual_size == file_size:
                                if file_size < 1024:
                                    progress_callback(f"Descriptor-Datei gesichert: {file_name} ({actual_size} Bytes)")
                                else:
                                    progress_callback(f"SCP-Download abgeschlossen: {file_name} ({actual_size // (1024*1024)}MB)")
                            elif file_size > 0:
                                progress_callback(f"Warnung: Dateigröße stimmt nicht überein (erwartet: {file_size}, erhalten: {actual_size})")
                                # Für große Dateien kann es kleine Abweichungen geben
                                if abs(actual_size - file_size) < 1024:  # Weniger als 1KB Unterschied ist OK
                                    progress_callback(f"Kleine Abweichung toleriert")
                                else:
                                    return False
                            else:
                                # Dateigröße war unbekannt
                                progress_callback(f"SCP-Download abgeschlossen: {file_name} ({actual_size // (1024*1024)}MB)")
                        scp.close()
                        ssh.close()
                        self._active_scp_session = None
                        self._active_ssh_connection = None
                        return True
                    else:
                        if progress_callback:
                            progress_callback(f"SCP-Download fehlgeschlagen: Datei ist leer")
                        if os.path.exists(local_path):
                            os.remove(local_path)
                        scp.close()
                        ssh.close()
                        self._active_scp_session = None
                        self._active_ssh_connection = None
                        return False
                else:
                    if progress_callback:
                        progress_callback(f"SCP-Download fehlgeschlagen: Datei wurde nicht erstellt")
                    scp.close()
                    ssh.close()
                    self._active_scp_session = None
                    self._active_ssh_connection = None
                    return False
                
            except Exception as download_error:
                # Falls SCP.get fehlschlägt oder für große Dateien, verwende cat über SSH
                use_cat_method = "Use cat method" in str(download_error)
                
                if not use_cat_method:
                    if progress_callback:
                        progress_callback(f"SCP-Download fehlgeschlagen, versuche alternativen Ansatz...")
                        progress_callback(f"Fehlerdetails: {str(download_error)}")
                
                # Verwende SSH cat für bessere Cancel-Unterstützung
                try:
                    stdin, stdout, stderr = ssh.exec_command(f"cat '{esxi_path}'")
                    
                    with open(local_path, 'wb') as f:
                        downloaded = 0
                        chunk_size = 1024 * 1024  # 1MB chunks
                        import time
                        
                        while True:
                            # Prüfe auf Cancel während des Downloads (bei jedem Chunk)
                            if self._is_cancelled():
                                try:
                                    stdout.channel.close()
                                except:
                                    pass
                                f.close()
                                if os.path.exists(local_path):
                                    try:
                                        os.remove(local_path)
                                    except:
                                        pass
                                if progress_callback:
                                    progress_callback("Download wurde abgebrochen")
                                return False
                            
                            # Prüfe, ob Daten verfügbar sind
                            if stdout.channel.recv_ready():
                                chunk = stdout.read(chunk_size)
                                if not chunk:
                                    # Prüfe, ob Channel geschlossen wurde
                                    if stdout.channel.closed:
                                        break
                                    # Warte kurz und prüfe erneut
                                    time.sleep(0.1)
                                    continue
                                
                                f.write(chunk)
                                downloaded += len(chunk)
                                
                                if progress_callback and file_size > 1024:
                                    progress = (downloaded / file_size) * 100
                                    progress_callback(f"SSH cat Download {file_name}: {progress:.1f}% ({downloaded // (1024*1024)}MB / {file_size // (1024*1024)}MB)")
                            else:
                                # Warte kurz, wenn keine Daten verfügbar
                                time.sleep(0.1)
                                # Prüfe erneut auf Cancel
                                if self._is_cancelled():
                                    try:
                                        stdout.channel.close()
                                    except:
                                        pass
                                    f.close()
                                    if os.path.exists(local_path):
                                        try:
                                            os.remove(local_path)
                                        except:
                                            pass
                                    if progress_callback:
                                        progress_callback("Download wurde abgebrochen")
                                    return False
                                
                                # Prüfe, ob Channel geschlossen wurde
                                if stdout.channel.closed:
                                    break
                    
                    # Prüfe Exit-Status
                    exit_status = stdout.channel.recv_exit_status()
                    if exit_status != 0:
                        error_msg = stderr.read().decode('utf-8', errors='ignore')
                        if progress_callback:
                            progress_callback(f"SSH cat Fehler (Exit {exit_status}): {error_msg}")
                        
                        # Wenn "Device or resource busy", versuche dd
                        if "busy" in error_msg.lower() or "resource busy" in error_msg.lower():
                            if progress_callback:
                                progress_callback(f"Datei ist gesperrt, versuche dd-Methode...")
                            raise Exception("Device busy - try dd")
                        
                        os.remove(local_path)
                        return False
                except Exception as cat_error:
                    # Alternative 2: Verwende dd für gesperrte Dateien
                    if "Device busy" in str(cat_error) or "busy" in str(cat_error).lower():
                        try:
                            if progress_callback:
                                progress_callback(f"Verwende dd für gesperrte Datei...")
                            
                            # Verwende dd mit bs=1M für bessere Performance
                            dd_command = f"dd if='{esxi_path}' bs=1M 2>/dev/null"
                            stdin, stdout, stderr = ssh.exec_command(dd_command)
                            
                            with open(local_path, 'wb') as f:
                                downloaded = 0
                                chunk_size = 1024 * 1024  # 1MB chunks
                                import time
                                
                                while True:
                                    # Prüfe auf Cancel während des Downloads (bei jedem Chunk)
                                    if self._is_cancelled():
                                        try:
                                            stdout.channel.close()
                                        except:
                                            pass
                                        f.close()
                                        if os.path.exists(local_path):
                                            try:
                                                os.remove(local_path)
                                            except:
                                                pass
                                        if progress_callback:
                                            progress_callback("Download wurde abgebrochen")
                                        return False
                                    
                                    # Prüfe, ob Daten verfügbar sind
                                    if stdout.channel.recv_ready():
                                        chunk = stdout.read(chunk_size)
                                        if not chunk:
                                            # Prüfe, ob Channel geschlossen wurde
                                            if stdout.channel.closed:
                                                break
                                            # Warte kurz und prüfe erneut
                                            time.sleep(0.1)
                                            continue
                                        
                                        f.write(chunk)
                                        downloaded += len(chunk)
                                        
                                        if progress_callback and file_size > 1024:
                                            progress = (downloaded / file_size) * 100
                                            progress_callback(f"dd Download {file_name}: {progress:.1f}% ({downloaded // (1024*1024)}MB / {file_size // (1024*1024)}MB)")
                                    else:
                                        # Warte kurz, wenn keine Daten verfügbar
                                        time.sleep(0.1)
                                        # Prüfe erneut auf Cancel
                                        if self._is_cancelled():
                                            try:
                                                stdout.channel.close()
                                            except:
                                                pass
                                            f.close()
                                            if os.path.exists(local_path):
                                                try:
                                                    os.remove(local_path)
                                                except:
                                                    pass
                                            if progress_callback:
                                                progress_callback("Download wurde abgebrochen")
                                            return False
                                        
                                        # Prüfe, ob Channel geschlossen wurde
                                        if stdout.channel.closed:
                                            break
                            
                            # Prüfe Exit-Status
                            exit_status = stdout.channel.recv_exit_status()
                            if exit_status != 0:
                                error_msg = stderr.read().decode('utf-8', errors='ignore')
                                if progress_callback:
                                    progress_callback(f"dd Fehler (Exit {exit_status}): {error_msg}")
                                os.remove(local_path)
                                return False
                            
                            if progress_callback:
                                progress_callback(f"dd-Download erfolgreich!")
                                
                        except Exception as dd_error:
                            if progress_callback:
                                progress_callback(f"dd-Download fehlgeschlagen: {str(dd_error)}")
                                progress_callback(f"Die VM läuft und die Datei ist gesperrt.")
                                progress_callback(f"Lösung: VM ausschalten oder Snapshot erstellen")
                            return False
                    else:
                        if progress_callback:
                            progress_callback(f"Alternativer Download fehlgeschlagen: {str(cat_error)}")
                        return False
                
                # Schließe Verbindungen nach erfolgreichem Download
                try:
                    scp.close()
                except:
                    pass
                ssh.close()
                self._active_scp_session = None
                self._active_ssh_connection = None
                
                # Prüfe auf Cancel nach Download
                if self._is_cancelled():
                    if os.path.exists(local_path):
                        try:
                            os.remove(local_path)
                        except:
                            pass
                    if progress_callback:
                        progress_callback("Download wurde abgebrochen")
                    return False
                
                # Prüfe, ob die Datei erfolgreich heruntergeladen wurde
                if os.path.exists(local_path):
                    actual_size = os.path.getsize(local_path)
                    if actual_size > 0:
                        if progress_callback:
                            if file_size > 0 and actual_size == file_size:
                                if file_size < 1024:
                                    progress_callback(f"Descriptor-Datei gesichert: {file_name} ({actual_size} Bytes)")
                                else:
                                    progress_callback(f"Download abgeschlossen: {file_name} ({actual_size // (1024*1024)}MB)")
                            elif file_size > 0:
                                # Für kleine Dateien (< 1KB) toleriere kleine Abweichungen
                                if file_size < 1024:
                                    if actual_size > 0:
                                        progress_callback(f"Descriptor-Datei gesichert: {file_name} ({actual_size} Bytes)")
                                    else:
                                        if progress_callback:
                                            progress_callback(f"Download fehlgeschlagen: Datei ist leer")
                                        if os.path.exists(local_path):
                                            os.remove(local_path)
                                        return False
                                else:
                                    progress_callback(f"Warnung: Dateigröße stimmt nicht überein (erwartet: {file_size}, erhalten: {actual_size})")
                                    # Für große Dateien kann es kleine Abweichungen geben
                                    if abs(actual_size - file_size) < 1024:  # Weniger als 1KB Unterschied ist OK
                                        progress_callback(f"Kleine Abweichung toleriert")
                                    else:
                                        return False
                            else:
                                # Dateigröße war unbekannt
                                progress_callback(f"Download abgeschlossen: {file_name} ({actual_size // (1024*1024)}MB)")
                        return True
                    else:
                        if progress_callback:
                            progress_callback(f"Download fehlgeschlagen: Datei ist leer")
                        if os.path.exists(local_path):
                            os.remove(local_path)
                        return False
                else:
                    if progress_callback:
                        progress_callback(f"Download fehlgeschlagen: Datei wurde nicht erstellt")
                    return False
                    
            except Exception as e:
                try:
                    scp.close()
                except:
                    pass
                try:
                    ssh.close()
                except:
                    pass
                self._active_scp_session = None
                self._active_ssh_connection = None
                if progress_callback:
                    import traceback
                    error_details = traceback.format_exc()
                    progress_callback(f"Download-Fehler: {str(e)}")
                    progress_callback(f"Details: {error_details[:500]}")
                return False
                
        except ImportError:
            if progress_callback:
                progress_callback(f"SSH/SCP nicht verfügbar: paramiko-Bibliothek fehlt")
                progress_callback(f"Installieren Sie mit: pip install paramiko")
            return False
        except Exception as e:
            if progress_callback:
                progress_callback(f"SSH/SCP-Fehler: {str(e)}")
            return False
    
    def _scp_progress_callback(self, transferred, total, file_size, file_name, progress_callback):
        """Callback für SCP-Fortschrittsanzeige"""
        if progress_callback and total > 0:
            progress = (transferred / file_size) * 100
            progress_callback(f"SCP Download {file_name}: {progress:.1f}% ({transferred // (1024*1024)}MB / {file_size // (1024*1024)}MB)")
    
    def _download_vmdk_vsphere_api(self, datastore: vim.Datastore, file_path: str,
                                  backup_dir: str, progress_callback=None) -> bool:
        """
        Versucht VMDK über vSphere API direkt herunterzuladen (alternative Methode)
        Diese Methode verwendet die Datastore Browser API, um die Datei zu finden und dann
        über HTTP herunterzuladen.
        
        Args:
            datastore: Datastore-Objekt
            file_path: Pfad zur VMDK-Datei
            backup_dir: Zielverzeichnis
            progress_callback: Optional Callback
            
        Returns:
            True bei Erfolg, False sonst
        """
        # Diese Methode würde eine komplexere Implementierung erfordern
        # und ist möglicherweise nicht für alle ESXi-Versionen verfügbar
        # Daher verwenden wir weiterhin die HTTP-Methode mit verbesserter URL-Konstruktion
        return False
    
    def _download_vmdk_datastore_browser(self, datastore: vim.Datastore, file_path: str,
                                        backup_dir: str, progress_callback=None) -> bool:
        """
        Lädt VMDK über Datastore Browser API (alternative Methode)
        
        Args:
            datastore: Datastore-Objekt
            file_path: Pfad zur VMDK-Datei
            backup_dir: Zielverzeichnis
            progress_callback: Optional Callback
            
        Returns:
            True bei Erfolg, False sonst
        """
        # Diese Methode würde eine komplexere Implementierung erfordern
        # Die Datastore Browser API ist hauptsächlich für Suche, nicht für Download
        return False
    
    def _download_vmdk_http(self, datastore: vim.Datastore, file_path: str,
                            backup_dir: str, progress_callback=None) -> bool:
        """
        Lädt VMDK über HTTP/HTTPS herunter (vollständige Implementierung)
        
        Args:
            datastore: Datastore-Objekt
            file_path: Pfad zur VMDK-Datei
            backup_dir: Zielverzeichnis
            progress_callback: Optional Callback
            
        Returns:
            True bei Erfolg, False sonst
        """
        try:
            import requests
            from requests.auth import HTTPBasicAuth
            import urllib3
            import re
            
            # SSL-Warnungen unterdrücken
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            # Entferne Datastore-Präfix aus dem Pfad (Format: [datastore] path)
            # Beispiel: [datastore1] BAUERP_PRO/BAUERP_PRO.vmdk -> BAUERP_PRO/BAUERP_PRO.vmdk
            clean_path = file_path
            if file_path.startswith('['):
                # Entferne [datastore] Präfix
                match = re.match(r'\[.*?\]\s*(.+)', file_path)
                if match:
                    clean_path = match.group(1)
            
            # Erstelle Download-URL
            # Format: https://hostname/folder/path?dcPath=datacenter&dsName=datastore
            datacenter = self._get_datacenter()
            dc_path = datacenter.name if datacenter else ""
            
            # Dateipfad für URL anpassen (Leerzeichen und Sonderzeichen encoden)
            import urllib.parse
            # Pfad normalisieren (führende Leerzeichen entfernen)
            clean_path = clean_path.strip()
            encoded_path = urllib.parse.quote(clean_path, safe='/')
            
            # URL zusammenstellen
            url = f"https://{self.host}/folder/{encoded_path}"
            params = {
                'dcPath': dc_path,
                'dsName': datastore.name
            }
            
            # HTTP-Basic-Auth verwenden
            auth = HTTPBasicAuth(self.user, self.password)
            
            # SSL-Verifizierung deaktivieren (für selbstsignierte Zertifikate)
            session = requests.Session()
            session.auth = auth
            session.verify = False
            
            if progress_callback:
                progress_callback(f"Starte Download von {os.path.basename(clean_path)}...")
            
            # Versuche verschiedene URL-Formate
            # Format-Optionen für ESXi Datastore-Download:
            # Die korrekte URL-Struktur für ESXi Datastore-Download ist:
            # https://host/folder/path?dcPath=datacenter&dsName=datastore
            
            # Wichtig: Der Pfad muss relativ zum Datastore sein, nicht absolut
            # Beispiel: Wenn fileName = "[datastore1] VM/VM.vmdk", dann sollte der Pfad "VM/VM.vmdk" sein
            
            urls_to_try = []
            
            # Option 1: Standard mit Datacenter
            urls_to_try.append((url, params, "Standard mit Datacenter"))
            
            # Option 2: Ohne Datacenter
            urls_to_try.append((f"https://{self.host}/folder/{encoded_path}", {'dsName': datastore.name}, "Ohne Datacenter"))
            
            # Option 3: Mit Datastore im Pfad (manchmal benötigt)
            urls_to_try.append((f"https://{self.host}/folder/{datastore.name}/{encoded_path}", {}, "Mit Datastore im Pfad"))
            
            # Option 4: Versuche auch ohne URL-Encoding für den Pfad (manchmal funktioniert das besser)
            if clean_path != encoded_path:
                urls_to_try.append((f"https://{self.host}/folder/{clean_path}", {'dcPath': dc_path, 'dsName': datastore.name}, "Ohne URL-Encoding"))
                urls_to_try.append((f"https://{self.host}/folder/{clean_path}", {'dsName': datastore.name}, "Ohne Encoding und Datacenter"))
            
            response = None
            successful_url = None
            
            for test_url, test_params, description in urls_to_try:
                if progress_callback:
                    progress_callback(f"Versuche Download ({description})...")
                    progress_callback(f"URL: {test_url}")
                    progress_callback(f"Parameter: {test_params}")
                
                try:
                    # Erste Anfrage ohne Stream, um zu prüfen, ob die Datei existiert
                    test_response = session.get(test_url, params=test_params, stream=False, timeout=30)
                    
                    if test_response.status_code == 200:
                        # Prüfe Content-Type
                        content_type = test_response.headers.get('content-type', '').lower()
                        
                        # Prüfe auf HTML-Fehler
                        if 'text/html' in content_type or 'application/xhtml' in content_type:
                            if progress_callback:
                                error_text = test_response.text[:200]
                                progress_callback(f"URL {description} gibt HTML zurück: {error_text}...")
                            continue
                        
                        # Prüfe die ersten Bytes des Inhalts
                        content_preview = test_response.content[:512]
                        
                        # Prüfe auf HTML-Fehler im Content
                        if content_preview.startswith(b'<') or b'<html' in content_preview.lower() or b'<!doctype' in content_preview.lower():
                            if progress_callback:
                                error_text = content_preview.decode('utf-8', errors='ignore')[:200]
                                progress_callback(f"URL {description} gibt HTML zurück: {error_text}...")
                            continue
                        
                        # Prüfe auf Text-Fehlermeldungen
                        try:
                            text_content = content_preview.decode('utf-8', errors='ignore')
                            if any(keyword in text_content.lower() for keyword in ['not found', '404', 'forbidden', 'unauthorized', 'error']):
                                if progress_callback:
                                    progress_callback(f"URL {description} gibt Fehlermeldung zurück: {text_content[:200]}")
                                continue
                        except:
                            pass
                        
                        # Prüfe Dateigröße
                        content_length = len(test_response.content)
                        if content_length < 1024:  # Weniger als 1KB ist verdächtig
                            if progress_callback:
                                progress_callback(f"URL {description} gibt sehr kleine Datei zurück ({content_length} Bytes)")
                                # Zeige Inhalt zur Diagnose
                                preview = test_response.text[:200] if hasattr(test_response, 'text') else str(test_response.content[:200])
                                progress_callback(f"Inhalt: {preview}")
                            continue
                        
                        # Wenn wir hier sind, sieht es nach einer echten Datei aus
                        # Jetzt erstellen wir einen neuen Stream-Request für den Download
                        response = session.get(test_url, params=test_params, stream=True, timeout=30)
                        successful_url = description
                        if progress_callback:
                            progress_callback(f"Download-URL erfolgreich: {description}")
                        break
                    else:
                        if progress_callback:
                            progress_callback(f"URL {description} fehlgeschlagen: HTTP {test_response.status_code}")
                            try:
                                error_text = test_response.text[:200]
                                progress_callback(f"Fehlerdetails: {error_text}")
                            except:
                                pass
                except Exception as e:
                    if progress_callback:
                        progress_callback(f"Fehler bei URL {description}: {str(e)}")
                    continue
            
            if response and response.status_code == 200:
                file_name = os.path.basename(clean_path)
                local_path = os.path.join(backup_dir, file_name)
                
                # Prüfe Content-Type und Content-Length
                content_type = response.headers.get('content-type', '')
                total_size = int(response.headers.get('content-length', 0))
                
                # Prüfe, ob die Response eine HTML-Fehlerseite ist (statt VMDK)
                if 'text/html' in content_type.lower():
                    if progress_callback:
                        progress_callback(f"Fehler: Server hat HTML statt VMDK zurückgegeben")
                        progress_callback(f"Möglicherweise falsche URL oder Berechtigungsproblem")
                        # Zeige ersten Teil der Response
                        try:
                            preview = response.text[:500]
                            progress_callback(f"Response-Vorschau: {preview}")
                        except:
                            pass
                    return False
                
                if progress_callback:
                    progress_callback(f"Content-Type: {content_type}")
                    progress_callback(f"Erwartete Größe: {total_size // (1024*1024)}MB" if total_size > 0 else "Größe unbekannt")
                
                downloaded = 0
                chunk_size = 1024 * 1024  # 1MB chunks
                bytes_written = 0
                
                # Stream-Download - wichtig: Response nur einmal lesen!
                with open(local_path, 'wb') as f:
                    # Verwende iter_content für Streaming-Download
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        if chunk:  # chunk kann leer sein, prüfe das
                            f.write(chunk)
                            bytes_written += len(chunk)
                            downloaded += len(chunk)
                            
                            if progress_callback:
                                if total_size > 0:
                                    progress = (downloaded / total_size) * 100
                                    progress_callback(f"Download {file_name}: {progress:.1f}% ({downloaded // (1024*1024)}MB / {total_size // (1024*1024)}MB)")
                                else:
                                    # Wenn Größe unbekannt, zeige nur heruntergeladene Menge
                                    if downloaded % (10 * 1024 * 1024) < chunk_size:  # Alle 10MB
                                        progress_callback(f"Download {file_name}: {downloaded // (1024*1024)}MB...")
                    
                    # Stelle sicher, dass Daten geschrieben wurden
                    f.flush()
                    os.fsync(f.fileno())
                
                # Prüfe, ob die Datei tatsächlich geschrieben wurde
                if os.path.exists(local_path):
                    actual_size = os.path.getsize(local_path)
                    if actual_size == 0:
                        if progress_callback:
                            progress_callback(f"Fehler: Datei wurde erstellt, aber ist leer (0 Bytes)")
                        os.remove(local_path)  # Lösche leere Datei
                        return False
                    elif actual_size < 10240:  # Weniger als 10KB ist verdächtig für eine VMDK
                        # Prüfe, ob es eine HTML-Fehlerseite oder Text-Fehlermeldung ist
                        try:
                            with open(local_path, 'rb') as f:
                                first_bytes = f.read(512)
                                # Prüfe auf HTML
                                if b'<html' in first_bytes.lower() or b'<!doctype' in first_bytes.lower():
                                    if progress_callback:
                                        progress_callback(f"Fehler: Server hat HTML-Fehlerseite zurückgegeben statt VMDK")
                                        # Zeige ersten Teil der Fehlermeldung
                                        f.seek(0)
                                        error_text = f.read(1000).decode('utf-8', errors='ignore')
                                        progress_callback(f"Fehlerdetails: {error_text[:200]}...")
                                    os.remove(local_path)
                                    return False
                                # Prüfe auf Text-Fehlermeldungen
                                try:
                                    text_content = first_bytes.decode('utf-8', errors='ignore')
                                    if any(keyword in text_content.lower() for keyword in ['error', 'not found', '404', 'forbidden', 'unauthorized']):
                                        if progress_callback:
                                            progress_callback(f"Fehler: Server hat Fehlermeldung zurückgegeben: {text_content[:200]}")
                                        os.remove(local_path)
                                        return False
                                except:
                                    pass
                        except Exception as e:
                            if progress_callback:
                                progress_callback(f"Fehler beim Überprüfen der Datei: {str(e)}")
                        
                        if progress_callback:
                            progress_callback(f"Warnung: Datei ist sehr klein ({actual_size} Bytes). Möglicherweise Fehler.")
                        os.remove(local_path)
                        return False
                    
                    if progress_callback:
                        progress_callback(f"Download abgeschlossen: {file_name} ({actual_size // (1024*1024)}MB)")
                    
                    return True
                else:
                    if progress_callback:
                        progress_callback(f"Fehler: Datei wurde nicht erstellt")
                    return False
            else:
                if progress_callback:
                    progress_callback(f"Alle Download-Versuche fehlgeschlagen für {clean_path}")
                    progress_callback(f"Bitte überprüfen Sie:")
                    progress_callback(f"  - HTTP-Datastore-Zugriff ist aktiviert")
                    progress_callback(f"  - Benutzer hat Leseberechtigung für den Datastore")
                    progress_callback(f"  - Dateipfad ist korrekt: {clean_path}")
                return False
                
        except requests.exceptions.RequestException as e:
            if progress_callback:
                progress_callback(f"Netzwerkfehler beim Download: {str(e)}")
            return False
        except Exception as e:
            if progress_callback:
                progress_callback(f"Fehler beim HTTP-Download: {str(e)}")
            return False
    
    def _get_datacenter(self) -> Optional[vim.Datacenter]:
        """Ruft das Datacenter ab"""
        if not self.content:
            return None
        
        datacenter_view = self.content.viewManager.CreateContainerView(
            self.content.rootFolder,
            [vim.Datacenter],
            True
        )
        datacenters = datacenter_view.view
        datacenter_view.Destroy()
        return datacenters[0] if datacenters else None
