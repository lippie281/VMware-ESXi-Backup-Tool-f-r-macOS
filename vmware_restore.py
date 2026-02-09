"""
VMware ESXi Restore Modul
Handhabt die Wiederherstellung von Backups auf ESXi Servern
"""

import ssl
import os
import json
import re
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path
from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim, vmodl


class VMwareRestore:
    """Klasse zur Verwaltung von VMware ESXi Restores"""
    
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
        
    def connect(self) -> bool:
        """
        Stellt Verbindung zum ESXi Server her
        
        Returns:
            True bei erfolgreicher Verbindung, False sonst
        """
        try:
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
    
    def scan_backup_directory(self, backup_dir: str) -> List[Dict]:
        """
        Durchsucht ein Backup-Verzeichnis nach verfügbaren Backups
        
        Args:
            backup_dir: Pfad zum Backup-Verzeichnis
            
        Returns:
            Liste von Backup-Informationen
        """
        backups = []
        
        if not os.path.exists(backup_dir):
            return backups
        
        for item in os.listdir(backup_dir):
            item_path = os.path.join(backup_dir, item)
            if not os.path.isdir(item_path):
                continue
            
            # Prüfe, ob es ein Backup-Verzeichnis ist (enthält vm_info.json oder host_config.json)
            backup_info = {
                'name': item,
                'path': item_path,
                'type': None,
                'timestamp': None,
                'info': {}
            }
            
            # Prüfe auf VM-Backup
            vm_info_file = os.path.join(item_path, 'vm_info.json')
            if os.path.exists(vm_info_file):
                try:
                    with open(vm_info_file, 'r', encoding='utf-8') as f:
                        vm_info = json.load(f)
                    backup_info['type'] = 'vm'
                    backup_info['info'] = vm_info
                    backup_info['timestamp'] = self._extract_timestamp(item)
                except Exception as e:
                    print(f"Fehler beim Lesen von {vm_info_file}: {str(e)}")
                    continue
            
            # Prüfe auf Host-Backup
            host_config_file = os.path.join(item_path, 'host_config.json')
            if os.path.exists(host_config_file):
                try:
                    with open(host_config_file, 'r', encoding='utf-8') as f:
                        host_info = json.load(f)
                    backup_info['type'] = 'host'
                    backup_info['info'] = host_info
                    backup_info['timestamp'] = self._extract_timestamp(item)
                except Exception as e:
                    print(f"Fehler beim Lesen von {host_config_file}: {str(e)}")
                    continue
            
            if backup_info['type']:
                backups.append(backup_info)
        
        return sorted(backups, key=lambda x: x['timestamp'] if x['timestamp'] else '', reverse=True)
    
    def _extract_timestamp(self, name: str) -> Optional[str]:
        """Extrahiert Timestamp aus Backup-Verzeichnisnamen"""
        # Format: Name_YYYYMMDD_HHMMSS
        match = re.search(r'_(\d{8}_\d{6})$', name)
        if match:
            return match.group(1)
        return None
    
    def restore_host_config(self, backup_path: str, progress_callback=None) -> bool:
        """
        Stellt Host-Konfiguration aus Backup wieder her
        
        Args:
            backup_path: Pfad zum Host-Backup-Verzeichnis
            progress_callback: Optional Callback für Fortschritt
            
        Returns:
            True bei Erfolg, False sonst
        """
        try:
            if progress_callback:
                progress_callback("Starte Host-Konfigurations-Wiederherstellung...")
            
            host_config_file = os.path.join(backup_path, 'host_config.json')
            if not os.path.exists(host_config_file):
                if progress_callback:
                    progress_callback(f"Fehler: host_config.json nicht gefunden in {backup_path}")
                return False
            
            with open(host_config_file, 'r', encoding='utf-8') as f:
                host_config = json.load(f)
            
            if progress_callback:
                progress_callback(f"Host-Konfiguration geladen: {host_config.get('name', 'Unknown')}")
                progress_callback("Hinweis: Host-Konfiguration kann nicht automatisch wiederhergestellt werden.")
                progress_callback("Bitte verwenden Sie die ESXi-Weboberfläche oder CLI-Tools.")
                progress_callback("Gesicherte Informationen:")
                progress_callback(f"  - Hostname: {host_config.get('name', 'N/A')}")
                progress_callback(f"  - Version: {host_config.get('version', 'N/A')}")
                progress_callback(f"  - Build: {host_config.get('build', 'N/A')}")
            
            return True
            
        except Exception as e:
            if progress_callback:
                progress_callback(f"Fehler bei Host-Wiederherstellung: {str(e)}")
            return False
    
    def restore_vm(self, backup_path: str, new_vm_name: str = None, 
                   datastore_name: str = None, progress_callback=None) -> bool:
        """
        Stellt eine VM aus Backup wieder her
        
        Args:
            backup_path: Pfad zum VM-Backup-Verzeichnis
            new_vm_name: Neuer Name für die VM (optional)
            datastore_name: Name des Datastores für die VM (optional)
            progress_callback: Optional Callback für Fortschritt
            
        Returns:
            True bei Erfolg, False sonst
        """
        try:
            if progress_callback:
                progress_callback("Starte VM-Wiederherstellung...")
            
            # Lade VM-Informationen
            vm_info_file = os.path.join(backup_path, 'vm_info.json')
            if not os.path.exists(vm_info_file):
                if progress_callback:
                    progress_callback(f"Fehler: vm_info.json nicht gefunden in {backup_path}")
                return False
            
            with open(vm_info_file, 'r', encoding='utf-8') as f:
                vm_info = json.load(f)
            
            original_vm_name = vm_info.get('name', 'Unknown')
            vm_name = new_vm_name if new_vm_name else original_vm_name
            
            if progress_callback:
                progress_callback(f"Wiederherstelle VM: {vm_name} (Original: {original_vm_name})")
            
            # Finde Datastore
            datastores = self._get_datastores()
            if not datastores:
                if progress_callback:
                    progress_callback("Fehler: Keine Datastores gefunden")
                return False
            
            # Wähle Datastore
            if datastore_name:
                datastore = next((ds for ds in datastores if ds.name == datastore_name), None)
            else:
                # Verwende ersten verfügbaren Datastore
                datastore = datastores[0]
            
            if not datastore:
                if progress_callback:
                    progress_callback(f"Fehler: Datastore '{datastore_name}' nicht gefunden")
                return False
            
            if progress_callback:
                progress_callback(f"Verwende Datastore: {datastore.name}")
            
            # Lade VMDK-Dateien hoch
            vmdk_files = self._find_vmdk_files(backup_path)
            
            if not vmdk_files:
                if progress_callback:
                    progress_callback("Fehler: Keine VMDK-Dateien im Backup gefunden")
                return False
            
            if progress_callback:
                progress_callback(f"Gefundene VMDK-Dateien: {len(vmdk_files)}")
            
            # Erstelle VM-Verzeichnis auf Datastore
            vm_folder = vm_name.replace(' ', '_')
            
            # Lade VMDK-Dateien hoch
            uploaded_files = []
            for vmdk_file in vmdk_files:
                if progress_callback:
                    progress_callback(f"Lade hoch: {os.path.basename(vmdk_file)}...")
                
                uploaded_path = self._upload_vmdk(
                    vmdk_file, 
                    datastore, 
                    vm_folder, 
                    progress_callback
                )
                
                if uploaded_path:
                    uploaded_files.append(uploaded_path)
                else:
                    if progress_callback:
                        progress_callback(f"Fehler beim Hochladen von {os.path.basename(vmdk_file)}")
                    return False
            
            # Erstelle VM-Konfiguration
            if progress_callback:
                progress_callback("Erstelle VM-Konfiguration...")
            
            vm_config = self._create_vm_config(vm_info, uploaded_files, datastore)
            
            # Registriere VM
            if progress_callback:
                progress_callback("Registriere VM auf ESXi Server...")
            
            vm = self._register_vm(vm_config, vm_name, datastore, progress_callback)
            
            if vm:
                if progress_callback:
                    progress_callback(f"VM erfolgreich wiederhergestellt: {vm_name}")
                return True
            else:
                if progress_callback:
                    progress_callback("Fehler beim Registrieren der VM")
                return False
            
        except Exception as e:
            if progress_callback:
                progress_callback(f"Fehler bei VM-Wiederherstellung: {str(e)}")
            import traceback
            if progress_callback:
                progress_callback(f"Details: {traceback.format_exc()[:500]}")
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
    
    def _find_vmdk_files(self, backup_path: str) -> List[str]:
        """Findet alle VMDK-Dateien im Backup-Verzeichnis"""
        vmdk_files = []
        
        for file in os.listdir(backup_path):
            if file.endswith('.vmdk') and not file.endswith('.metadata.json'):
                file_path = os.path.join(backup_path, file)
                if os.path.isfile(file_path):
                    vmdk_files.append(file_path)
        
        # Sortiere: Descriptor-Datei zuerst, dann -flat.vmdk
        vmdk_files.sort(key=lambda x: (not x.endswith('-flat.vmdk'), x))
        
        return vmdk_files
    
    def _upload_vmdk(self, local_file: str, datastore: vim.Datastore, 
                     vm_folder: str, progress_callback=None) -> Optional[str]:
        """
        Lädt eine VMDK-Datei auf den Datastore hoch
        
        Args:
            local_file: Pfad zur lokalen VMDK-Datei
            datastore: Datastore-Objekt
            vm_folder: VM-Verzeichnisname auf dem Datastore
            progress_callback: Optional Callback
            
        Returns:
            Pfad zur hochgeladenen Datei oder None
        """
        try:
            import paramiko
            import re
            
            file_name = os.path.basename(local_file)
            file_size = os.path.getsize(local_file)
            
            # SSH-Verbindung herstellen
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            ssh.connect(
                self.host,
                username=self.user,
                password=self.password,
                port=22,
                timeout=30,
                allow_agent=False,
                look_for_keys=False
            )
            
            # Erstelle VM-Verzeichnis auf Datastore
            remote_dir = f"/vmfs/volumes/{datastore.name}/{vm_folder}"
            ssh.exec_command(f"mkdir -p '{remote_dir}'")
            
            # Remote-Pfad
            remote_path = f"{remote_dir}/{file_name}"
            
            if progress_callback:
                progress_callback(f"Lade hoch: {file_name} ({file_size // (1024*1024)}MB)...")
            
            # Upload mit SCP
            scp = ssh.open_sftp()
            
            try:
                scp.put(local_file, remote_path, callback=lambda x, y: self._upload_progress_callback(
                    x, y, file_size, file_name, progress_callback
                ) if file_size > 1024 else None)
                
                scp.close()
                ssh.close()
                
                if progress_callback:
                    progress_callback(f"Hochladen abgeschlossen: {file_name}")
                
                return f"[{datastore.name}] {vm_folder}/{file_name}"
                
            except Exception as e:
                scp.close()
                ssh.close()
                if progress_callback:
                    progress_callback(f"Upload-Fehler: {str(e)}")
                return None
                
        except Exception as e:
            if progress_callback:
                progress_callback(f"Upload-Fehler: {str(e)}")
            return None
    
    def _upload_progress_callback(self, transferred, total, file_size, file_name, progress_callback):
        """Callback für Upload-Fortschrittsanzeige"""
        if progress_callback and file_size > 1024:
            progress = (transferred / file_size) * 100
            progress_callback(f"Upload {file_name}: {progress:.1f}% ({transferred // (1024*1024)}MB / {file_size // (1024*1024)}MB)")
    
    def _create_vm_config(self, vm_info: Dict, vmdk_files: List[str], 
                         datastore: vim.Datastore) -> vim.vm.ConfigSpec:
        """Erstellt VM-Konfiguration aus Backup-Informationen"""
        
        # Finde Descriptor-Datei (auf dem Datastore, nicht lokal)
        descriptor_file = None
        for f in vmdk_files:
            if not f.endswith('-flat.vmdk'):
                # f ist bereits der Datastore-Pfad
                descriptor_file = f
                break
        
        if not descriptor_file:
            raise Exception("Keine VMDK-Descriptor-Datei gefunden")
        
        # Erstelle ConfigSpec
        config_spec = vim.vm.ConfigSpec()
        config_spec.name = vm_info.get('name', 'Restored_VM')
        config_spec.memoryMB = vm_info.get('memory_mb', 1024)
        config_spec.numCPUs = vm_info.get('num_cpu', 1)
        
        # Konvertiere guest_os zu guestId
        guest_os = vm_info.get('guest_os', 'otherGuest')
        config_spec.guestId = self._convert_guest_os_to_id(guest_os)
        
        # Erstelle SCSI-Controller
        scsi_ctrl_spec = vim.vm.device.VirtualDeviceSpec()
        scsi_ctrl_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
        scsi_ctrl_spec.device = vim.vm.device.VirtualLsiLogicController()
        scsi_ctrl_spec.device.key = 1000
        scsi_ctrl_spec.device.busNumber = 0
        scsi_ctrl_spec.device.sharedBus = vim.vm.device.VirtualSCSIController.Sharing.noSharing
        
        # Erstelle Disk-Device
        disk_spec = vim.vm.device.VirtualDeviceSpec()
        disk_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
        disk_spec.fileOperation = vim.vm.device.VirtualDeviceSpec.FileOperation.create
        
        disk_backing = vim.vm.device.VirtualDisk.FlatVer2BackingInfo()
        disk_backing.fileName = descriptor_file
        disk_backing.diskMode = vim.vm.device.VirtualDiskOption.DiskMode.persistent
        
        disk_spec.device = vim.vm.device.VirtualDisk()
        disk_spec.device.backing = disk_backing
        disk_spec.device.controllerKey = 1000
        disk_spec.device.unitNumber = 0
        disk_spec.device.key = 2000
        
        # Lese Kapazität aus VMDK-Descriptor (lokal)
        try:
            # Finde lokale Descriptor-Datei
            local_descriptor = None
            for f in vmdk_files:
                if not f.endswith('-flat.vmdk') and os.path.exists(f):
                    local_descriptor = f
                    break
            
            if local_descriptor:
                with open(local_descriptor, 'r') as f:
                    descriptor_content = f.read()
                    match = re.search(r'RW\s+(\d+)', descriptor_content)
                    if match:
                        sectors = int(match.group(1))
                        disk_spec.device.capacityInKB = sectors * 512 // 1024
        except:
            disk_spec.device.capacityInKB = 10240  # Default: 10GB
        
        config_spec.deviceChange = [scsi_ctrl_spec, disk_spec]
        
        return config_spec
    
    def _convert_guest_os_to_id(self, guest_os: str) -> str:
        """Konvertiert Guest-OS-Beschreibung zu VMware guestId"""
        guest_os_lower = guest_os.lower()
        
        if 'windows' in guest_os_lower:
            if '10' in guest_os_lower or '11' in guest_os_lower:
                return 'windows9_64Guest'
            elif '8' in guest_os_lower:
                return 'windows8_64Guest'
            elif '7' in guest_os_lower:
                return 'windows7_64Guest'
            else:
                return 'windows8_64Guest'
        elif 'ubuntu' in guest_os_lower:
            if '22' in guest_os_lower:
                return 'ubuntu64Guest'
            elif '20' in guest_os_lower:
                return 'ubuntu64Guest'
            else:
                return 'ubuntu64Guest'
        elif 'linux' in guest_os_lower:
            return 'other3xLinux64Guest'
        else:
            return 'otherGuest'
    
    def _register_vm(self, config_spec: vim.vm.ConfigSpec, vm_name: str,
                    datastore: vim.Datastore, progress_callback=None) -> Optional[vim.VirtualMachine]:
        """Registriert VM auf ESXi Server"""
        try:
            # Finde Datacenter oder Host
            datacenter = self._get_datacenter()
            if not datacenter:
                if progress_callback:
                    progress_callback("Fehler: Kein Datacenter gefunden")
                return None
            
            # Finde VM-Folder
            vm_folder = datacenter.vmFolder
            
            # Erstelle VM
            if progress_callback:
                progress_callback(f"Erstelle VM '{vm_name}'...")
            
            task = vm_folder.CreateVM_Task(config=config_spec, pool=None)
            
            # Warte auf Task-Abschluss
            while task.info.state == 'running':
                import time
                time.sleep(1)
            
            if task.info.state == 'success':
                vm = task.info.result
                if progress_callback:
                    progress_callback(f"VM erfolgreich erstellt: {vm.name}")
                return vm
            else:
                if progress_callback:
                    progress_callback(f"VM-Erstellung fehlgeschlagen: {task.info.error}")
                return None
                
        except Exception as e:
            if progress_callback:
                progress_callback(f"Fehler beim Registrieren der VM: {str(e)}")
            return None
    
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
