"""
Server-Konfigurations-Verwaltung
Speichert und verwaltet ESXi Server-Verbindungsdaten
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Optional
from cryptography.fernet import Fernet
import base64


class ServerConfigManager:
    """Verwaltet gespeicherte ESXi Server-Konfigurationen"""
    
    def __init__(self, config_file: str = None):
        """
        Initialisiert den Server-Konfigurations-Manager
        
        Args:
            config_file: Pfad zur Konfigurationsdatei (optional)
        """
        if config_file is None:
            # Standard-Pfad: ~/.vmware_backup/servers.json
            config_dir = Path.home() / '.vmware_backup'
            config_dir.mkdir(exist_ok=True)
            config_file = str(config_dir / 'servers.json')
        
        self.config_file = config_file
        self.key_file = config_file.replace('.json', '.key')
        self._ensure_key()
    
    def _ensure_key(self):
        """Stellt sicher, dass ein Verschlüsselungsschlüssel existiert"""
        if not os.path.exists(self.key_file):
            # Erstelle neuen Schlüssel
            key = Fernet.generate_key()
            with open(self.key_file, 'wb') as f:
                f.write(key)
    
    def _get_cipher(self) -> Fernet:
        """Gibt den Verschlüsselungscipher zurück"""
        with open(self.key_file, 'rb') as f:
            key = f.read()
        return Fernet(key)
    
    def _encrypt_password(self, password: str) -> str:
        """Verschlüsselt ein Passwort"""
        cipher = self._get_cipher()
        return cipher.encrypt(password.encode()).decode()
    
    def _decrypt_password(self, encrypted_password: str) -> str:
        """Entschlüsselt ein Passwort"""
        try:
            cipher = self._get_cipher()
            return cipher.decrypt(encrypted_password.encode()).decode()
        except Exception:
            # Falls Entschlüsselung fehlschlägt, könnte es ein unverschlüsseltes Passwort sein
            return encrypted_password
    
    def save_server(self, name: str, host: str, port: int, user: str, 
                   password: str, description: str = "") -> bool:
        """
        Speichert einen Server
        
        Args:
            name: Name des Servers (eindeutig)
            host: Hostname oder IP-Adresse
            port: Port (Standard: 443)
            user: Benutzername
            password: Passwort
            description: Beschreibung (optional)
            
        Returns:
            True bei Erfolg, False sonst
        """
        try:
            servers = self.load_servers()
            
            # Prüfe, ob Server bereits existiert
            server_exists = any(s['name'] == name for s in servers)
            
            server_data = {
                'name': name,
                'host': host,
                'port': port,
                'user': user,
                'password': self._encrypt_password(password),
                'description': description
            }
            
            if server_exists:
                # Aktualisiere existierenden Server
                servers = [s if s['name'] != name else server_data for s in servers]
            else:
                # Füge neuen Server hinzu
                servers.append(server_data)
            
            # Speichere zurück
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(servers, f, indent=2, ensure_ascii=False)
            
            return True
            
        except Exception as e:
            print(f"Fehler beim Speichern des Servers: {str(e)}")
            return False
    
    def load_servers(self) -> List[Dict]:
        """
        Lädt alle gespeicherten Server
        
        Returns:
            Liste von Server-Dictionaries
        """
        if not os.path.exists(self.config_file):
            return []
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                servers = json.load(f)
            
            # Entschlüssele Passwörter beim Laden
            for server in servers:
                if 'password' in server:
                    server['password'] = self._decrypt_password(server['password'])
            
            return servers
            
        except Exception as e:
            print(f"Fehler beim Laden der Server: {str(e)}")
            return []
    
    def get_server(self, name: str) -> Optional[Dict]:
        """
        Lädt einen spezifischen Server
        
        Args:
            name: Name des Servers
            
        Returns:
            Server-Dictionary oder None
        """
        servers = self.load_servers()
        return next((s for s in servers if s['name'] == name), None)
    
    def delete_server(self, name: str) -> bool:
        """
        Löscht einen Server
        
        Args:
            name: Name des Servers
            
        Returns:
            True bei Erfolg, False sonst
        """
        try:
            servers = self.load_servers()
            servers = [s for s in servers if s['name'] != name]
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(servers, f, indent=2, ensure_ascii=False)
            
            return True
            
        except Exception as e:
            print(f"Fehler beim Löschen des Servers: {str(e)}")
            return False
    
    def get_server_names(self) -> List[str]:
        """
        Gibt eine Liste aller Server-Namen zurück
        
        Returns:
            Liste von Server-Namen
        """
        servers = self.load_servers()
        return [s['name'] for s in servers]
