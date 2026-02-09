"""
Mac GUI für VMware ESXi Backup Tool
Verwendet PyQt6 für native Mac-Oberfläche
"""

import sys
import os
from pathlib import Path
from typing import Optional, Callable
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QFileDialog, QProgressBar,
    QGroupBox, QCheckBox, QListWidget, QListWidgetItem, QMessageBox,
    QTabWidget, QFormLayout, QSpinBox, QComboBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QIcon
from vmware_backup import VMwareBackup
from vmware_restore import VMwareRestore
from server_config import ServerConfigManager
from pyVmomi import vim


class BackupThread(QThread):
    """Thread für Backup-Operationen"""
    
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str)
    
    def __init__(self, backup_manager: VMwareBackup, backup_dir: str,
                 backup_host: bool, backup_vms: bool, vm_list: list):
        super().__init__()
        self.backup_manager = backup_manager
        self.backup_dir = backup_dir
        self.backup_host = backup_host
        self.backup_vms = backup_vms
        self.vm_list = vm_list
        self._cancel = False
        # Setze Cancel-Flag im Backup-Manager
        if self.backup_manager:
            self.backup_manager.set_cancel_flag(self)
    
    def cancel(self):
        """Bricht den Backup-Vorgang ab"""
        self._cancel = True
        if self.backup_manager:
            self.backup_manager.cancel_backup()
    
    def run(self):
        """Führt den Backup-Vorgang aus"""
        try:
            # Verbindung herstellen
            self.progress.emit("Verbinde mit ESXi Server...")
            if not self.backup_manager.connect():
                self.finished.emit(False, "Verbindung zum ESXi Server fehlgeschlagen")
                return
            
            success_count = 0
            error_messages = []
            
            # Host sichern
            if self.backup_host and not self._cancel:
                self.progress.emit("Sichere Host-Konfiguration...")
                hosts = self.backup_manager.get_hosts()
                for host in hosts:
                    if self._cancel:
                        break
                    if self.backup_manager.backup_host_config(host, self.backup_dir):
                        success_count += 1
                        self.progress.emit(f"Host {host.name} gesichert")
                    else:
                        error_messages.append(f"Fehler beim Sichern von Host {host.name}")
            
            # VMs sichern
            if self.backup_vms and not self._cancel:
                vms = self.backup_manager.get_vms()
                if self.vm_list:
                    # Nur ausgewählte VMs sichern
                    vms = [vm for vm in vms if vm.name in self.vm_list]
                
                total_vms = len(vms)
                for idx, vm in enumerate(vms):
                    if self._cancel:
                        break
                    
                    self.progress.emit(f"Sichere VM {vm.name} ({idx+1}/{total_vms})...")
                    if self.backup_manager.backup_vmdk(vm, self.backup_dir, 
                                                      lambda msg: self.progress.emit(msg)):
                        success_count += 1
                        self.progress.emit(f"VM {vm.name} gesichert")
                    else:
                        error_messages.append(f"Fehler beim Sichern von VM {vm.name}")
            
            self.backup_manager.disconnect()
            
            if self._cancel:
                self.finished.emit(False, "Backup abgebrochen")
            else:
                message = f"Backup abgeschlossen. {success_count} Objekte gesichert."
                if error_messages:
                    message += f"\nFehler: {len(error_messages)}"
                self.finished.emit(True, message)
                
        except Exception as e:
            self.finished.emit(False, f"Fehler: {str(e)}")


class RestoreThread(QThread):
    """Thread für Wiederherstellungs-Operationen"""
    
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str)
    
    def __init__(self, restore_manager: VMwareRestore, backup_path: str,
                 restore_type: str, new_name: str = None, datastore: str = None):
        super().__init__()
        self.restore_manager = restore_manager
        self.backup_path = backup_path
        self.restore_type = restore_type
        self.new_name = new_name
        self.datastore = datastore
    
    def run(self):
        """Führt die Wiederherstellung aus"""
        try:
            if self.restore_type == 'host':
                success = self.restore_manager.restore_host_config(
                    self.backup_path,
                    lambda msg: self.progress.emit(msg)
                )
                if success:
                    self.finished.emit(True, "Host-Konfiguration wiederhergestellt")
                else:
                    self.finished.emit(False, "Host-Wiederherstellung fehlgeschlagen")
                    
            elif self.restore_type == 'vm':
                success = self.restore_manager.restore_vm(
                    self.backup_path,
                    self.new_name,
                    self.datastore,
                    lambda msg: self.progress.emit(msg)
                )
                if success:
                    self.finished.emit(True, f"VM wiederhergestellt: {self.new_name or 'Originalname'}")
                else:
                    self.finished.emit(False, "VM-Wiederherstellung fehlgeschlagen")
                    
        except Exception as e:
            self.finished.emit(False, f"Fehler: {str(e)}")


class VMwareBackupGUI(QMainWindow):
    """Hauptfenster der Anwendung"""
    
    def __init__(self):
        super().__init__()
        self.backup_manager: Optional[VMwareBackup] = None
        self.restore_manager: Optional[VMwareRestore] = None
        self.backup_thread: Optional[BackupThread] = None
        self.restore_thread: Optional[RestoreThread] = None
        self.backup_data = {}  # Speichert Backup-Informationen
        self.server_config = ServerConfigManager()  # Server-Konfigurations-Manager
        self.init_ui()
    
    def init_ui(self):
        """Initialisiert die Benutzeroberfläche"""
        self.setWindowTitle("VMware ESXi Backup Tool")
        self.setMinimumSize(800, 600)
        
        # Zentrales Widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Hauptlayout
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        # Tabs
        tabs = QTabWidget()
        main_layout.addWidget(tabs)
        
        # Tab 1: Verbindung
        connection_tab = self.create_connection_tab()
        tabs.addTab(connection_tab, "Verbindung")
        
        # Tab 2: Backup
        backup_tab = self.create_backup_tab()
        tabs.addTab(backup_tab, "Backup")
        
        # Tab 3: Wiederherstellung
        restore_tab = self.create_restore_tab()
        tabs.addTab(restore_tab, "Wiederherstellung")
        
        # Status-Bereich
        status_group = QGroupBox("Status")
        status_layout = QVBoxLayout()
        
        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setMaximumHeight(150)
        status_layout.addWidget(self.status_text)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        status_layout.addWidget(self.progress_bar)
        
        status_group.setLayout(status_layout)
        main_layout.addWidget(status_group)
        
        # Log-Nachricht hinzufügen
        self.log("Anwendung gestartet")
    
    def refresh_servers(self):
        """Aktualisiert die Server-Liste"""
        self.server_combo.clear()
        self.server_combo.addItem("-- Neuer Server --", None)
        
        servers = self.server_config.load_servers()
        for server in servers:
            display_name = f"{server['name']} ({server['host']})"
            self.server_combo.addItem(display_name, server)
    
    def on_server_selected(self, index: int):
        """Wird aufgerufen, wenn ein Server ausgewählt wird"""
        server_data = self.server_combo.itemData(index)
        if server_data:
            self.host_input.setText(server_data['host'])
            self.port_input.setValue(server_data.get('port', 443))
            self.user_input.setText(server_data['user'])
            self.password_input.setText(server_data['password'])
        else:
            # "Neuer Server" ausgewählt - Felder leeren
            self.host_input.clear()
            self.port_input.setValue(443)
            self.user_input.clear()
            self.password_input.clear()
    
    def save_current_server(self):
        """Speichert die aktuellen Verbindungsdaten als Server"""
        host = self.host_input.text().strip()
        port = self.port_input.value()
        user = self.user_input.text().strip()
        password = self.password_input.text()
        
        if not host or not user or not password:
            QMessageBox.warning(self, "Fehler", 
                              "Bitte füllen Sie Host, Benutzername und Passwort aus.")
            return
        
        # Dialog für Server-Namen
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(
            self,
            "Server speichern",
            "Geben Sie einen Namen für diesen Server ein:",
            text=host
        )
        
        if not ok or not name.strip():
            return
        
        name = name.strip()
        
        # Prüfe, ob Server bereits existiert
        existing_server = self.server_config.get_server(name)
        if existing_server:
            reply = QMessageBox.question(
                self,
                "Server existiert bereits",
                f"Ein Server mit dem Namen '{name}' existiert bereits.\n"
                f"Möchten Sie ihn überschreiben?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        # Speichere Server
        if self.server_config.save_server(name, host, port, user, password):
            self.log(f"Server '{name}' gespeichert")
            QMessageBox.information(self, "Erfolg", f"Server '{name}' wurde gespeichert.")
            self.refresh_servers()
            # Wähle den gespeicherten Server aus
            index = self.server_combo.findData(None)
            for i in range(self.server_combo.count()):
                item_data = self.server_combo.itemData(i)
                if item_data and item_data['name'] == name:
                    self.server_combo.setCurrentIndex(i)
                    break
        else:
            QMessageBox.critical(self, "Fehler", "Fehler beim Speichern des Servers.")
    
    def delete_selected_server(self):
        """Löscht den ausgewählten Server"""
        index = self.server_combo.currentIndex()
        server_data = self.server_combo.itemData(index)
        
        if not server_data:
            QMessageBox.warning(self, "Fehler", "Bitte wählen Sie einen Server aus.")
            return
        
        name = server_data['name']
        
        reply = QMessageBox.question(
            self,
            "Server löschen",
            f"Möchten Sie den Server '{name}' wirklich löschen?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if self.server_config.delete_server(name):
                self.log(f"Server '{name}' gelöscht")
                QMessageBox.information(self, "Erfolg", f"Server '{name}' wurde gelöscht.")
                self.refresh_servers()
                self.server_combo.setCurrentIndex(0)  # Wähle "Neuer Server"
            else:
                QMessageBox.critical(self, "Fehler", "Fehler beim Löschen des Servers.")
    
    def create_connection_tab(self) -> QWidget:
        """Erstellt den Verbindungs-Tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        
        # Gespeicherte Server
        server_group = QGroupBox("Gespeicherte Server")
        server_layout = QVBoxLayout()
        
        server_select_layout = QHBoxLayout()
        server_select_layout.addWidget(QLabel("Server:"))
        self.server_combo = QComboBox()
        self.server_combo.currentIndexChanged.connect(self.on_server_selected)
        server_select_layout.addWidget(self.server_combo)
        
        refresh_servers_button = QPushButton("Aktualisieren")
        refresh_servers_button.clicked.connect(self.refresh_servers)
        server_select_layout.addWidget(refresh_servers_button)
        
        server_layout.addLayout(server_select_layout)
        
        # Server-Verwaltungs-Buttons
        server_buttons_layout = QHBoxLayout()
        save_server_button = QPushButton("Server speichern")
        save_server_button.clicked.connect(self.save_current_server)
        server_buttons_layout.addWidget(save_server_button)
        
        delete_server_button = QPushButton("Server löschen")
        delete_server_button.clicked.connect(self.delete_selected_server)
        server_buttons_layout.addWidget(delete_server_button)
        
        server_layout.addLayout(server_buttons_layout)
        server_group.setLayout(server_layout)
        layout.addWidget(server_group)
        
        # Verbindungsformular
        form_group = QGroupBox("ESXi Server Verbindung")
        form_layout = QFormLayout()
        
        self.host_input = QLineEdit()
        self.host_input.setPlaceholderText("z.B. 192.168.1.100 oder esxi.example.com")
        form_layout.addRow("Host:", self.host_input)
        
        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(443)
        form_layout.addRow("Port:", self.port_input)
        
        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("z.B. root")
        form_layout.addRow("Benutzername:", self.user_input)
        
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("Passwort")
        form_layout.addRow("Passwort:", self.password_input)
        
        form_group.setLayout(form_layout)
        layout.addWidget(form_group)
        
        # Verbindungs-Button
        button_layout = QHBoxLayout()
        self.connect_button = QPushButton("Verbinden")
        self.connect_button.clicked.connect(self.connect_to_server)
        button_layout.addWidget(self.connect_button)
        
        self.disconnect_button = QPushButton("Trennen")
        self.disconnect_button.clicked.connect(self.disconnect_from_server)
        self.disconnect_button.setEnabled(False)
        button_layout.addWidget(self.disconnect_button)
        
        layout.addLayout(button_layout)
        layout.addStretch()
        
        # Lade gespeicherte Server beim Start
        self.refresh_servers()
        
        return widget
    
    def create_backup_tab(self) -> QWidget:
        """Erstellt den Backup-Tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        
        # Backup-Optionen
        options_group = QGroupBox("Backup-Optionen")
        options_layout = QVBoxLayout()
        
        self.backup_host_checkbox = QCheckBox("Host-Konfiguration sichern")
        self.backup_host_checkbox.setChecked(True)
        options_layout.addWidget(self.backup_host_checkbox)
        
        self.backup_vms_checkbox = QCheckBox("VMs (VMDK) sichern")
        self.backup_vms_checkbox.setChecked(True)
        options_layout.addWidget(self.backup_vms_checkbox)
        
        options_group.setLayout(options_layout)
        layout.addWidget(options_group)
        
        # VM-Auswahl
        vm_group = QGroupBox("VM-Auswahl (leer = alle VMs)")
        vm_layout = QVBoxLayout()
        
        self.vm_list = QListWidget()
        self.vm_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        vm_layout.addWidget(self.vm_list)
        
        refresh_vms_button = QPushButton("VMs aktualisieren")
        refresh_vms_button.clicked.connect(self.refresh_vms)
        vm_layout.addWidget(refresh_vms_button)
        
        vm_group.setLayout(vm_layout)
        layout.addWidget(vm_group)
        
        # Backup-Ziel
        target_group = QGroupBox("Backup-Ziel")
        target_layout = QHBoxLayout()
        
        self.backup_dir_input = QLineEdit()
        self.backup_dir_input.setPlaceholderText("Wähle Backup-Verzeichnis...")
        target_layout.addWidget(self.backup_dir_input)
        
        browse_button = QPushButton("Durchsuchen...")
        browse_button.clicked.connect(self.browse_backup_dir)
        target_layout.addWidget(browse_button)
        
        target_group.setLayout(target_layout)
        layout.addWidget(target_group)
        
        # Backup-Button
        button_layout = QHBoxLayout()
        self.start_backup_button = QPushButton("Backup starten")
        self.start_backup_button.clicked.connect(self.start_backup)
        self.start_backup_button.setEnabled(False)
        button_layout.addWidget(self.start_backup_button)
        
        self.cancel_backup_button = QPushButton("Abbrechen")
        self.cancel_backup_button.clicked.connect(self.cancel_backup)
        self.cancel_backup_button.setEnabled(False)
        button_layout.addWidget(self.cancel_backup_button)
        
        layout.addLayout(button_layout)
        layout.addStretch()
        
        return widget
    
    def log(self, message: str):
        """Fügt eine Nachricht zum Log hinzu"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.status_text.append(f"[{timestamp}] {message}")
        # Auto-Scroll zum Ende
        self.status_text.verticalScrollBar().setValue(
            self.status_text.verticalScrollBar().maximum()
        )
    
    def connect_to_server(self):
        """Stellt Verbindung zum ESXi Server her"""
        host = self.host_input.text().strip()
        port = self.port_input.value()
        user = self.user_input.text().strip()
        password = self.password_input.text()
        
        if not host or not user or not password:
            QMessageBox.warning(self, "Fehler", 
                              "Bitte füllen Sie alle Felder aus.")
            return
        
        self.log(f"Verbinde mit {host}:{port}...")
        self.connect_button.setEnabled(False)
        
        # Verbindung im Hintergrund testen
        self.backup_manager = VMwareBackup(host, user, password, port)
        if self.backup_manager.connect():
            self.log("Verbindung erfolgreich!")
            self.connect_button.setEnabled(False)
            self.disconnect_button.setEnabled(True)
            self.start_backup_button.setEnabled(True)
            
            # Erstelle auch Restore-Manager mit gleichen Credentials
            self.restore_manager = VMwareRestore(host, user, password, port)
            self.restore_manager.connect()
            
            self.refresh_vms()
            self.refresh_datastores()
        else:
            self.log("Verbindung fehlgeschlagen!")
            QMessageBox.critical(self, "Fehler", 
                                "Verbindung zum ESXi Server fehlgeschlagen.\n"
                                "Bitte überprüfen Sie die Zugangsdaten.")
            self.connect_button.setEnabled(True)
            self.backup_manager = None
            self.restore_manager = None
    
    def cancel_backup(self):
        """Bricht den Backup-Vorgang ab"""
        if self.backup_thread and self.backup_thread.isRunning():
            self.log("Backup wird abgebrochen...")
            self.backup_thread.cancel()
            
            # Informiere Backup-Manager über Cancel
            if self.backup_manager:
                self.backup_manager.cancel_backup()
            
            # Warte kurz, damit der Thread reagieren kann
            if not self.backup_thread.wait(3000):  # Warte max. 3 Sekunden
                # Falls Thread nicht reagiert, erzwinge Beendigung
                self.log("Thread reagiert nicht, erzwinge Beendigung...")
                self.backup_thread.terminate()
                self.backup_thread.wait(1000)  # Warte auf Beendigung
                self.log("Backup-Thread wurde beendet")
    
    def disconnect_from_server(self):
        """Trennt die Verbindung zum ESXi Server"""
        if self.backup_manager:
            self.backup_manager.disconnect()
            self.backup_manager = None
        if self.restore_manager:
            self.restore_manager.disconnect()
            self.restore_manager = None
        self.log("Verbindung getrennt")
        self.connect_button.setEnabled(True)
        self.disconnect_button.setEnabled(False)
        self.start_backup_button.setEnabled(False)
        self.vm_list.clear()
        self.restore_datastore_combo.clear()
    
    def refresh_vms(self):
        """Aktualisiert die VM-Liste"""
        if not self.backup_manager:
            return
        
        self.vm_list.clear()
        try:
            vms = self.backup_manager.get_vms()
            for vm in vms:
                item = QListWidgetItem(vm.name)
                item.setCheckState(Qt.CheckState.Unchecked)
                self.vm_list.addItem(item)
            self.log(f"{len(vms)} VMs gefunden")
        except Exception as e:
            self.log(f"Fehler beim Abrufen der VMs: {str(e)}")
    
    def browse_backup_dir(self):
        """Öffnet Dialog zur Auswahl des Backup-Verzeichnisses"""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Backup-Verzeichnis wählen",
            str(Path.home())
        )
        if directory:
            self.backup_dir_input.setText(directory)
    
    def start_backup(self):
        """Startet den Backup-Vorgang"""
        if not self.backup_manager:
            QMessageBox.warning(self, "Fehler", 
                              "Bitte verbinden Sie sich zuerst mit dem Server.")
            return
        
        backup_dir = self.backup_dir_input.text().strip()
        if not backup_dir:
            QMessageBox.warning(self, "Fehler", 
                              "Bitte wählen Sie ein Backup-Verzeichnis.")
            return
        
        if not os.path.exists(backup_dir):
            try:
                os.makedirs(backup_dir, exist_ok=True)
            except Exception as e:
                QMessageBox.critical(self, "Fehler", 
                                   f"Konnte Backup-Verzeichnis nicht erstellen: {str(e)}")
                return
        
        backup_host = self.backup_host_checkbox.isChecked()
        backup_vms = self.backup_vms_checkbox.isChecked()
        
        if not backup_host and not backup_vms:
            QMessageBox.warning(self, "Fehler", 
                              "Bitte wählen Sie mindestens eine Backup-Option.")
            return
        
        # Ausgewählte VMs ermitteln
        selected_vms = []
        for i in range(self.vm_list.count()):
            item = self.vm_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                selected_vms.append(item.text())
        
        # Backup-Thread starten
        self.backup_thread = BackupThread(
            self.backup_manager,
            backup_dir,
            backup_host,
            backup_vms,
            selected_vms if selected_vms else None
        )
        self.backup_thread.progress.connect(self.log)
        self.backup_thread.finished.connect(self.backup_finished)
        self.backup_thread.start()
        
        # UI aktualisieren
        self.start_backup_button.setEnabled(False)
        self.cancel_backup_button.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Unbestimmter Fortschritt
        self.log("Backup gestartet...")
    
    def backup_finished(self, success: bool, message: str):
        """Wird aufgerufen, wenn der Backup-Vorgang abgeschlossen ist"""
        self.progress_bar.setVisible(False)
        self.start_backup_button.setEnabled(True)
        self.cancel_backup_button.setEnabled(False)
        
        self.log(message)
        
        if success:
            QMessageBox.information(self, "Erfolg", message)
        else:
            QMessageBox.warning(self, "Fehler", message)
    
    def create_restore_tab(self) -> QWidget:
        """Erstellt den Wiederherstellungs-Tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        
        # Backup-Verzeichnis
        backup_dir_group = QGroupBox("Backup-Verzeichnis")
        backup_dir_layout = QHBoxLayout()
        
        self.restore_backup_dir_input = QLineEdit()
        self.restore_backup_dir_input.setPlaceholderText("Wähle Backup-Verzeichnis...")
        backup_dir_layout.addWidget(self.restore_backup_dir_input)
        
        browse_backup_button = QPushButton("Durchsuchen...")
        browse_backup_button.clicked.connect(self.browse_restore_backup_dir)
        backup_dir_layout.addWidget(browse_backup_button)
        
        scan_button = QPushButton("Backups scannen")
        scan_button.clicked.connect(self.scan_backups)
        backup_dir_layout.addWidget(scan_button)
        
        backup_dir_group.setLayout(backup_dir_layout)
        layout.addWidget(backup_dir_group)
        
        # Verfügbare Backups
        backups_group = QGroupBox("Verfügbare Backups")
        backups_layout = QVBoxLayout()
        
        self.backups_list = QListWidget()
        self.backups_list.itemDoubleClicked.connect(self.on_backup_selected)
        backups_layout.addWidget(self.backups_list)
        
        backups_group.setLayout(backups_layout)
        layout.addWidget(backups_group)
        
        # Wiederherstellungs-Optionen
        restore_options_group = QGroupBox("Wiederherstellungs-Optionen")
        restore_options_layout = QVBoxLayout()
        
        # VM-Name (für VM-Wiederherstellung)
        vm_name_layout = QHBoxLayout()
        vm_name_layout.addWidget(QLabel("Neuer VM-Name (optional):"))
        self.restore_vm_name_input = QLineEdit()
        self.restore_vm_name_input.setPlaceholderText("Leer lassen für Originalnamen")
        vm_name_layout.addWidget(self.restore_vm_name_input)
        restore_options_layout.addLayout(vm_name_layout)
        
        # Datastore-Auswahl
        from PyQt6.QtWidgets import QComboBox
        datastore_layout = QHBoxLayout()
        datastore_layout.addWidget(QLabel("Datastore:"))
        self.restore_datastore_combo = QComboBox()
        datastore_layout.addWidget(self.restore_datastore_combo)
        restore_options_layout.addLayout(datastore_layout)
        
        refresh_datastores_button = QPushButton("Datastores aktualisieren")
        refresh_datastores_button.clicked.connect(self.refresh_datastores)
        restore_options_layout.addWidget(refresh_datastores_button)
        
        restore_options_group.setLayout(restore_options_layout)
        layout.addWidget(restore_options_group)
        
        # Wiederherstellungs-Buttons
        button_layout = QHBoxLayout()
        
        self.restore_host_button = QPushButton("Host wiederherstellen")
        self.restore_host_button.clicked.connect(self.start_host_restore)
        self.restore_host_button.setEnabled(False)
        button_layout.addWidget(self.restore_host_button)
        
        self.restore_vm_button = QPushButton("VM wiederherstellen")
        self.restore_vm_button.clicked.connect(self.start_vm_restore)
        self.restore_vm_button.setEnabled(False)
        button_layout.addWidget(self.restore_vm_button)
        
        self.cancel_restore_button = QPushButton("Abbrechen")
        self.cancel_restore_button.clicked.connect(self.cancel_restore)
        self.cancel_restore_button.setEnabled(False)
        button_layout.addWidget(self.cancel_restore_button)
        
        layout.addLayout(button_layout)
        layout.addStretch()
        
        return widget
    
    def browse_restore_backup_dir(self):
        """Öffnet Dialog zur Auswahl des Backup-Verzeichnisses"""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Backup-Verzeichnis wählen",
            str(Path.home())
        )
        if directory:
            self.restore_backup_dir_input.setText(directory)
            self.scan_backups()
    
    def scan_backups(self):
        """Scannt das Backup-Verzeichnis nach verfügbaren Backups"""
        backup_dir = self.restore_backup_dir_input.text().strip()
        if not backup_dir:
            QMessageBox.warning(self, "Fehler", "Bitte wählen Sie ein Backup-Verzeichnis.")
            return
        
        if not os.path.exists(backup_dir):
            QMessageBox.warning(self, "Fehler", "Backup-Verzeichnis existiert nicht.")
            return
        
        self.log(f"Scanne Backup-Verzeichnis: {backup_dir}...")
        
        # Verwende Restore-Manager zum Scannen (auch ohne Verbindung möglich)
        if not self.restore_manager:
            self.restore_manager = VMwareRestore("", "", "")
        
        backups = self.restore_manager.scan_backup_directory(backup_dir)
        
        self.backups_list.clear()
        self.backup_data = {}
        
        for backup in backups:
            backup_type = backup['type']
            backup_name = backup['name']
            backup_info = backup['info']
            
            if backup_type == 'vm':
                display_name = f"VM: {backup_info.get('name', backup_name)}"
                details = f"OS: {backup_info.get('guest_os', 'Unknown')}, "
                details += f"RAM: {backup_info.get('memory_mb', 0)}MB, "
                details += f"CPU: {backup_info.get('num_cpu', 0)}"
            else:
                display_name = f"Host: {backup_info.get('name', backup_name)}"
                details = f"Version: {backup_info.get('version', 'Unknown')}"
            
            item_text = f"{display_name} ({backup['timestamp'] or 'Unbekannt'})"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, backup['path'])
            self.backups_list.addItem(item)
            self.backup_data[backup['path']] = backup
        
        self.log(f"{len(backups)} Backups gefunden")
        
        # Aktiviere Buttons wenn Backups gefunden
        has_backups = len(backups) > 0
        self.restore_host_button.setEnabled(has_backups)
        self.restore_vm_button.setEnabled(has_backups)
    
    def on_backup_selected(self, item):
        """Wird aufgerufen, wenn ein Backup ausgewählt wird"""
        backup_path = item.data(Qt.ItemDataRole.UserRole)
        if backup_path in self.backup_data:
            backup = self.backup_data[backup_path]
            if backup['type'] == 'vm':
                self.restore_vm_name_input.setText(backup['info'].get('name', ''))
    
    def refresh_datastores(self):
        """Aktualisiert die Datastore-Liste"""
        if not self.restore_manager or not self.restore_manager.content:
            QMessageBox.warning(self, "Fehler", "Bitte verbinden Sie sich zuerst mit dem Server.")
            return
        
        self.restore_datastore_combo.clear()
        try:
            datastores = self.restore_manager._get_datastores()
            for ds in datastores:
                self.restore_datastore_combo.addItem(ds.name)
            self.log(f"{len(datastores)} Datastores gefunden")
        except Exception as e:
            self.log(f"Fehler beim Abrufen der Datastores: {str(e)}")
    
    def start_host_restore(self):
        """Startet die Host-Wiederherstellung"""
        selected_items = self.backups_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Fehler", "Bitte wählen Sie ein Backup aus.")
            return
        
        backup_path = selected_items[0].data(Qt.ItemDataRole.UserRole)
        backup = self.backup_data.get(backup_path)
        
        if not backup or backup['type'] != 'host':
            QMessageBox.warning(self, "Fehler", "Bitte wählen Sie ein Host-Backup aus.")
            return
        
        if not self.restore_manager:
            QMessageBox.warning(self, "Fehler", "Bitte verbinden Sie sich zuerst mit dem Server.")
            return
        
        reply = QMessageBox.question(
            self,
            "Bestätigung",
            f"Möchten Sie die Host-Konfiguration wirklich wiederherstellen?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.restore_thread = RestoreThread(
                self.restore_manager,
                backup_path,
                'host'
            )
            self.restore_thread.progress.connect(self.log)
            self.restore_thread.finished.connect(self.restore_finished)
            self.restore_thread.start()
            
            self.restore_host_button.setEnabled(False)
            self.restore_vm_button.setEnabled(False)
            self.cancel_restore_button.setEnabled(True)
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)
            self.log("Host-Wiederherstellung gestartet...")
    
    def start_vm_restore(self):
        """Startet die VM-Wiederherstellung"""
        selected_items = self.backups_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Fehler", "Bitte wählen Sie ein Backup aus.")
            return
        
        backup_path = selected_items[0].data(Qt.ItemDataRole.UserRole)
        backup = self.backup_data.get(backup_path)
        
        if not backup or backup['type'] != 'vm':
            QMessageBox.warning(self, "Fehler", "Bitte wählen Sie ein VM-Backup aus.")
            return
        
        if not self.restore_manager:
            QMessageBox.warning(self, "Fehler", "Bitte verbinden Sie sich zuerst mit dem Server.")
            return
        
        # Datastore auswählen
        if self.restore_datastore_combo.currentIndex() < 0:
            QMessageBox.warning(self, "Fehler", "Bitte wählen Sie einen Datastore aus.")
            return
        
        datastore_name = self.restore_datastore_combo.currentText()
        new_vm_name = self.restore_vm_name_input.text().strip() or None
        
        reply = QMessageBox.question(
            self,
            "Bestätigung",
            f"Möchten Sie die VM wirklich wiederherstellen?\n"
            f"Name: {new_vm_name or backup['info'].get('name', 'Original')}\n"
            f"Datastore: {datastore_name}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.restore_thread = RestoreThread(
                self.restore_manager,
                backup_path,
                'vm',
                new_vm_name,
                datastore_name
            )
            self.restore_thread.progress.connect(self.log)
            self.restore_thread.finished.connect(self.restore_finished)
            self.restore_thread.start()
            
            self.restore_host_button.setEnabled(False)
            self.restore_vm_button.setEnabled(False)
            self.cancel_restore_button.setEnabled(True)
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)
            self.log("VM-Wiederherstellung gestartet...")
    
    def cancel_restore(self):
        """Bricht die Wiederherstellung ab"""
        if self.restore_thread and self.restore_thread.isRunning():
            self.restore_thread.terminate()
            self.log("Wiederherstellung wird abgebrochen...")
    
    def restore_finished(self, success: bool, message: str):
        """Wird aufgerufen, wenn die Wiederherstellung abgeschlossen ist"""
        self.progress_bar.setVisible(False)
        self.restore_host_button.setEnabled(True)
        self.restore_vm_button.setEnabled(True)
        self.cancel_restore_button.setEnabled(False)
        
        self.log(message)
        
        if success:
            QMessageBox.information(self, "Erfolg", message)
        else:
            QMessageBox.warning(self, "Fehler", message)


def main():
    """Hauptfunktion"""
    app = QApplication(sys.argv)
    app.setApplicationName("VMware ESXi Backup Tool")
    
    # Mac-spezifische Einstellungen
    if sys.platform == 'darwin':
        app.setStyle('macos')
    
    window = VMwareBackupGUI()
    window.show()
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
