"""Boucle principale de monitoring Chromecast."""

import threading
import time
import logging
from typing import Dict, Callable, Optional

import config

logger = logging.getLogger(__name__)

# Essayer d'importer Chromecast support
try:
    from vlc_chromecast import (
        ChromecastDiscovery, ChromecastMonitor, ChromecastPlaybackState,
        PYCHROMECAST_AVAILABLE
    )
except ImportError:
    PYCHROMECAST_AVAILABLE = False
    ChromecastDiscovery = None
    ChromecastMonitor = None
    ChromecastPlaybackState = object


class MonitoringLoop:
    """Boucle de monitoring pour découverte et polling Chromecast"""
    
    def __init__(self, on_update_callback: Optional[Callable] = None):
        """
        Initialise la boucle de monitoring.
        
        Args:
            on_update_callback: Fonction appelée à chaque mise à jour (args: devices_dict)
        """
        self.playback_states: Dict[str, ChromecastPlaybackState] = {}  # IP -> State
        
        self.chromecast_discovery = None
        self.chromecast_monitors: Dict[str, ChromecastMonitor] = {}
        if PYCHROMECAST_AVAILABLE:
            logger.info("pychromecast disponible - support Chromecast activé")
            self.chromecast_discovery = ChromecastDiscovery()
        else:
            logger.warning("pychromecast non disponible - installez via: pip install pychromecast")
        
        self.on_update_callback = on_update_callback
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()
    
    def start(self):
        """Lance la boucle de monitoring dans un thread"""
        if self.running:
            logger.warning("Monitoring déjà en cours")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        logger.info("Boucle de monitoring lancée")
    
    def stop(self):
        """Arrête la boucle de monitoring"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("Boucle de monitoring arrêtée")
    
    def _run_loop(self):
        """Boucle principale (exécutée dans un thread)"""
        last_discovery = 0
        first_render_done = False
        
        while self.running:
            try:
                current_time = time.time()

                if self.on_update_callback and not first_render_done:
                    self.on_update_callback(self.playback_states)
                    first_render_done = True
                
                if current_time - last_discovery > config.DISCOVERY_CACHE_TTL:
                    self._update_devices()
                    last_discovery = current_time
                    if self.on_update_callback:
                        self.on_update_callback(self.playback_states)
                
                self._poll_states()
                
                if self.on_update_callback:
                    self.on_update_callback(self.playback_states)
                
                time.sleep(config.POLL_INTERVAL)
            
            except Exception as e:
                logger.error(f"Erreur dans la boucle de monitoring: {e}")
                time.sleep(1)
    
    def _update_devices(self):
        """Découvre les appareils Chromecast et crée les monitors"""
        try:
            chromecast_devices = []
            if self.chromecast_discovery:
                try:
                    logger.info("Démarrage découverte Chromecast...")
                    chromecast_devices = self.chromecast_discovery.discover()
                except Exception as e:
                    logger.warning(f"Erreur discovery Chromecast: {e}")
            
            with self.lock:
                for device in chromecast_devices:
                    if device.ip not in self.chromecast_monitors:
                        logger.info(f"Nouvel appareil Chromecast: {device.name} ({device.ip})")
                        self.chromecast_monitors[device.ip] = ChromecastMonitor(
                            device.ip,
                            port=device.port,
                            device_name=device.name,
                        )
                        self.playback_states[device.ip] = ChromecastPlaybackState(
                            device.ip,
                            device_name=device.name,
                        )
                    elif device.ip in self.playback_states:
                        self.playback_states[device.ip].device_name = device.name

                ips_found = {d.ip for d in chromecast_devices}
                
                for ip in list(self.chromecast_monitors.keys()):
                    if ip not in ips_found:
                        logger.debug(f"Appareil Chromecast disparu: {ip}")
                        if ip in self.playback_states:
                            del self.playback_states[ip]
                        del self.chromecast_monitors[ip]
        
        except Exception as e:
            logger.error(f"Erreur découverte Chromecast: {e}")
    
    def _poll_states(self):
        """Poll l'état Chromecast de tous les appareils"""
        with self.lock:
            for ip, monitor in list(self.chromecast_monitors.items()):
                try:
                    state = monitor.get_playback_state()
                    self.playback_states[ip] = state
                except Exception as e:
                    logger.debug(f"Erreur polling Chromecast {ip}: {e}")

    def get_states(self) -> Dict[str, ChromecastPlaybackState]:
        """Retourne une copie des états de lecture actuels"""
        with self.lock:
            return dict(self.playback_states)
    
    def get_monitors(self) -> Dict[str, ChromecastMonitor]:
        """Retourne les monitors actuels"""
        with self.lock:
            return dict(self.chromecast_monitors)
