"""Affichage terminal pour le monitoring Chromecast."""

import os
import sys
import time
from typing import Dict

from vlc_chromecast import ChromecastPlaybackState
import config


class TerminalDisplay:
    """Affiche les etats de lecture Chromecast en temps reel."""
    
    # Couleurs ANSI
    RESET = "\033[0m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    GREY = "\033[90m"
    
    # Symboles
    PLAY_SYMBOL = "▶"
    PAUSE_SYMBOL = "⏸"
    STOP_SYMBOL = "⏹"
    ERROR_SYMBOL = "✕"
    
    def __init__(self, use_colors: bool = True):
        self.use_colors = use_colors
    
    def clear_screen(self):
        """Efface l'écran (fonctionne sur Linux/Mac/Windows)"""
        if sys.stdout.isatty():
            os.system('clear' if os.name == 'posix' else 'cls')
    
    def display_states(self, states: Dict[str, ChromecastPlaybackState]):
        """Affiche tous les etats de lecture dans le terminal."""
        self.clear_screen()
        
        # En-tête
        header = self._build_header()
        print(header, flush=True)
        
        separator = "─" * (len(header) - 10)  # -10 pour codes ANSI
        print(separator, flush=True)
        
        # Lignes pour chaque appareil
        if not states:
            print(f"{self.GREY}Aucun appareil découvert...{self.RESET}", flush=True)
        else:
            for ip, state in sorted(states.items()):
                line = self._build_device_line(ip, state)
                print(line, flush=True)
        
        # Footer
        print("-" * 120, flush=True)
        print(f"{self.GREY}Dernière mise à jour: {time.strftime('%H:%M:%S')}{self.RESET}", flush=True)
    
    def _build_header(self) -> str:
        """Construit la ligne d'en-tête"""
        header = (
            f"{'Peripherique':<{config.DISPLAY_WIDTH_DEVICE}} "
            f"{'App':<{config.DISPLAY_WIDTH_APP}} "
            f"{'IP':<{config.DISPLAY_WIDTH_IP}} "
            f"{'État':<{config.DISPLAY_WIDTH_STATE}} "
            f"{'En lecture':<{config.DISPLAY_WIDTH_TITLE}}"
        )
        
        if self.use_colors:
            return f"{self.BLUE}{header}{self.RESET}"
        return header
    
    def _build_device_line(self, ip: str, state: ChromecastPlaybackState) -> str:
        """Construit une ligne d'affichage pour un appareil."""
        app_name = state.app_name if state.app_name else "Chromecast"
        device_name = state.device_name if getattr(state, "device_name", "") else ip
        
        # Déterminer le symbole et couleur selon l'état
        if not state.is_reachable:
            symbol = self.ERROR_SYMBOL
            color = self.RED
            state_text = "Offline"
        elif state.is_playing:
            symbol = self.PLAY_SYMBOL
            color = self.GREEN
            state_text = "Playing"
        elif state.is_paused:
            symbol = self.PAUSE_SYMBOL
            color = self.YELLOW
            state_text = "Paused"
        else:
            symbol = self.STOP_SYMBOL
            color = self.GREY
            state_text = "Stopped"
        
        # Construire la ligne
        line = (
            f"{symbol} {device_name:<{config.DISPLAY_WIDTH_DEVICE - 2}} "
            f"{app_name:<{config.DISPLAY_WIDTH_APP}} "
            f"{ip:<{config.DISPLAY_WIDTH_IP}} "
            f"{state_text:<{config.DISPLAY_WIDTH_STATE}} "
            f"{state.display_title}"
        )
        
        # Ajouter progressbar si en lecture
        if state.is_playing and state.duration > 0:
            progress = int((state.current_time / state.duration) * 10)
            progress_bar = "█" * progress + "░" * (10 - progress)
            line += f" [{progress_bar}]"
        
        if self.use_colors:
            return f"{color}{line}{self.RESET}"
        return line
    
