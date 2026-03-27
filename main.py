"""Point d'entree du monitor Chromecast Android TV."""

import argparse
import logging
import signal
import sys
import time
from typing import Optional

from monitor_loop import MonitoringLoop
from display import TerminalDisplay
import config


def setup_logging(verbose: bool = False, log_file: Optional[str] = None):
    """Configure le logging."""
    level = logging.DEBUG if verbose else logging.INFO
    
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    handler = logging.StreamHandler()
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(log_format))
    
    handlers = [handler]
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_handler.setFormatter(logging.Formatter(log_format))
        handlers.append(file_handler)
    
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(level)
    for h in handlers:
        root_logger.addHandler(h)

    # Evite que les logs debug verbeux de pychromecast masquent l'affichage.
    if verbose:
        logging.getLogger("pychromecast").setLevel(logging.INFO)
        logging.getLogger("pychromecast.discovery").setLevel(logging.INFO)


class MonitoringApp:
    """Application principale."""
    
    def __init__(self, verbose: bool = False, no_color: bool = False):
        self.verbose = verbose
        self.no_color = no_color
        self.monitor_loop: Optional[MonitoringLoop] = None
        self.display: Optional[TerminalDisplay] = None
        self.running = False
    
    def initialize(self):
        """Initialise l'application."""
        setup_logging(
            verbose=self.verbose,
            log_file=config.LOG_FILE if self.verbose else None
        )
        
        logger = logging.getLogger(__name__)
        logger.info("=== Android TV Chromecast Monitor ===")
        logger.info(f"Verbose: {self.verbose}, Display: {'Colors' if not self.no_color else 'No Color'}")
        
        self.display = TerminalDisplay(use_colors=not self.no_color)
        self.monitor_loop = MonitoringLoop(on_update_callback=self._on_states_update)
    
    def _on_states_update(self, states):
        """Callback appele quand les etats changent."""
        if self.display:
            self.display.display_states(states)
    
    def run(self):
        """Lance l'application."""
        if not self.monitor_loop or not self.display:
            raise RuntimeError("Application not initialized")
        
        logger = logging.getLogger(__name__)
        self.running = True
        
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        try:
            logger.info("Démarrage du monitoring...")
            self.monitor_loop.start()
            
            logger.info("Appuyez sur Ctrl+C pour arrêter")
            
            while self.running:
                time.sleep(1)
        
        except KeyboardInterrupt:
            logger.info("Arrêt demandé par l'utilisateur")
        
        except Exception as e:
            logger.error(f"Erreur fatale: {e}", exc_info=self.verbose)
        
        finally:
            self.shutdown()
    
    def _signal_handler(self, signum, frame):
        """Handler pour les signaux (SIGINT, SIGTERM)."""
        logger = logging.getLogger(__name__)
        logger.info(f"Signal {signum} reçu, arrêt...")
        self.running = False
    
    def shutdown(self):
        """Arrete l'application proprement."""
        logger = logging.getLogger(__name__)
        
        if self.monitor_loop:
            self.monitor_loop.stop()
        
        logger.info("Fermeture complète")
        sys.exit(0)


def main():
    """Point d'entrée principal"""
    parser = argparse.ArgumentParser(
        description="Monitore l'etat de lecture des applications Chromecast sur Android TV",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  python main.py
  python main.py --verbose
  python main.py --no-color
        """
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Mode verbose (debug logs)'
    )
    
    parser.add_argument(
        '--no-color',
        action='store_true',
        help='Désactiver les couleurs de terminal'
    )
    
    args = parser.parse_args()
    
    app = MonitoringApp(verbose=args.verbose, no_color=args.no_color)
    app.initialize()
    app.run()


if __name__ == '__main__':
    main()
