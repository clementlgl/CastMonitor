"""Decouverte et monitoring Chromecast via pychromecast."""

import logging
import time
from typing import Optional, Dict, List
from dataclasses import dataclass

try:
    import pychromecast
    from pychromecast import Chromecast
    PYCHROMECAST_AVAILABLE = True
except ImportError:
    PYCHROMECAST_AVAILABLE = False

import config

logger = logging.getLogger(__name__)


@dataclass
class ChromecastDevice:
    """Represente un appareil Chromecast decouvert."""
    name: str
    ip: str
    port: int = 8009
    model: str = "Chromecast"


class ChromecastPlaybackState:
    """Etat de lecture Chromecast."""
    
    STATE_PLAYING = "playing"
    STATE_PAUSED = "paused"
    STATE_STOPPED = "stopped"
    STATE_IDLE = "idle"
    STATE_ERROR = "error"
    STATE_UNREACHABLE = "unreachable"
    
    def __init__(self, device_ip: str, device_name: str = ""):
        self.device_ip = device_ip
        self.device_name = device_name
        self.state = self.STATE_UNREACHABLE
        self.app_name = "Unknown"
        self.title = ""
        self.current_time = 0
        self.duration = 0
        self.volume = 0
        self.last_update = time.time()
        self.error_count = 0
    
    def __repr__(self):
        return f"ChromecastPlaybackState(state={self.state}, app={self.app_name}, device={self.device_ip})"
    
    @property
    def is_playing(self) -> bool:
        return self.state == self.STATE_PLAYING
    
    @property
    def is_paused(self) -> bool:
        return self.state == self.STATE_PAUSED
    
    @property
    def is_reachable(self) -> bool:
        return self.state not in [self.STATE_UNREACHABLE, self.STATE_ERROR]
    
    @property
    def display_title(self) -> str:
        if not self.title:
            if self.state in [self.STATE_STOPPED, self.STATE_IDLE]:
                return "---"
            return f"<{self.app_name}>"
        return self.title[:config.DISPLAY_WIDTH_TITLE]


class ChromecastDiscovery:
    """Decouverte des appareils Chromecast."""
    
    def __init__(self):
        if not PYCHROMECAST_AVAILABLE:
            logger.warning("pychromecast non installé")
        
        self.devices: Dict[str, ChromecastDevice] = {}
        self.scan_timeout = config.DISCOVERY_TIMEOUT
    
    def discover(self, timeout: int = None) -> List[ChromecastDevice]:
        """Decouvre les appareils Chromecast."""
        if not PYCHROMECAST_AVAILABLE:
            logger.error("pychromecast non disponible")
            return []
        
        if timeout is None:
            timeout = self.scan_timeout
        
        try:
            logger.info("Lancement discovery Chromecast...")
            self.devices.clear()
            
            chromecasts, _browser = pychromecast.discovery.discover_chromecasts(
                timeout=timeout
            )
            
            for cast_info in chromecasts:
                device = ChromecastDevice(
                    name=cast_info.friendly_name,
                    ip=cast_info.host,
                    port=cast_info.port,
                    model=cast_info.model_name or "Chromecast"
                )
                self.devices[device.ip] = device
                logger.info(f"✓ Découvert: {device.name} ({device.ip})")

            logger.info(f"Discovery terminé: {len(self.devices)} appareils")
            
        except Exception as e:
            logger.error(f"Erreur discovery Chromecast: {e}")
        
        return list(self.devices.values())
    
class ChromecastMonitor:
    """Monitore l'etat de lecture Chromecast."""
    
    def __init__(self, device_ip: str, port: int = 8009, device_name: str = ""):
        if not PYCHROMECAST_AVAILABLE:
            raise RuntimeError("pychromecast non disponible")
        
        self.device_ip = device_ip
        self.port = port
        self.device_name = device_name
        self.playback_state = ChromecastPlaybackState(device_ip, device_name=device_name)
        self.cast: Optional[Chromecast] = None
    
    def get_playback_state(self) -> ChromecastPlaybackState:
        """Récupère l'état de lecture actuel"""
        try:
            if not self.cast:
                host_tuple = (self.device_ip, self.port, None, "Unknown", self.device_ip)
                self.cast = pychromecast.get_chromecast_from_host(host_tuple)
                self.cast.wait()

            cast_status = getattr(self.cast, "status", None)
            app_id = getattr(self.cast, "app_id", None)
            app_display_name = getattr(self.cast, "app_display_name", None)

            # Nom d'app plus fiable selon version pychromecast
            if app_display_name:
                self.playback_state.app_name = app_display_name
            elif app_id:
                self.playback_state.app_name = self._get_app_name(app_id)

            if self.cast.is_idle:
                self.playback_state.state = ChromecastPlaybackState.STATE_IDLE
                self.playback_state.title = ""

            if self.cast.media_controller and self.cast.media_controller.is_active:
                media = self.cast.media_controller

                # Compat versions: parfois les bool is_playing/is_paused ne sont
                # pas renseignés alors que player_state est disponible.
                player_state = ""
                if getattr(media, "status", None):
                    player_state = (getattr(media.status, "player_state", "") or "").upper()

                if getattr(media, "is_playing", False) or player_state == "PLAYING":
                    self.playback_state.state = ChromecastPlaybackState.STATE_PLAYING
                elif getattr(media, "is_paused", False) or player_state == "PAUSED":
                    self.playback_state.state = ChromecastPlaybackState.STATE_PAUSED
                else:
                    # Cas fréquent Android TV + VLC: player_state == UNKNOWN mais app active.
                    if player_state == "UNKNOWN" and self.playback_state.app_name.lower().startswith("vlc"):
                        self.playback_state.state = ChromecastPlaybackState.STATE_PLAYING
                    else:
                        self.playback_state.state = ChromecastPlaybackState.STATE_STOPPED

                self.playback_state.current_time = (
                    getattr(media, "current_time", None)
                    or getattr(getattr(media, "status", None), "current_time", None)
                    or 0
                )
                self.playback_state.duration = (
                    getattr(media, "duration", None)
                    or getattr(getattr(media, "status", None), "duration", None)
                    or 0
                )

                media_title = (
                    getattr(media, "title", None)
                    or getattr(getattr(media, "status", None), "title", None)
                )
                content_id = (
                    getattr(media, "content_id", None)
                    or getattr(getattr(media, "status", None), "content_id", None)
                )

                if media_title:
                    self.playback_state.title = media_title
                elif content_id:
                    self.playback_state.title = str(content_id).split('/')[-1]

            if cast_status and getattr(cast_status, "volume_level", None) is not None:
                self.playback_state.volume = cast_status.volume_level * 100

            self.playback_state.error_count = 0
            
        except Exception as e:
            self.playback_state.state = ChromecastPlaybackState.STATE_UNREACHABLE
            self.playback_state.error_count += 1
            logger.debug(f"Chromecast {self.device_ip}: {type(e).__name__}: {e}")
            self.cast = None
        
        self.playback_state.last_update = time.time()
        return self.playback_state
    
    def _get_app_name(self, app_id: str) -> str:
        """Traduit app_id en nom lisible"""
        app_names = {
            "CC1AD845": "Chromecast",
            "E8C28D3C": "YouTube",
            "233637DE": "Hangouts",
            "0F5096E8": "Spotify",
            "03DD221C": "Netflix",
            "AndroidNativeApp": "VLC",
            "org.videolan.vlc": "VLC",
        }
        return app_names.get(app_id, app_id[:20])
