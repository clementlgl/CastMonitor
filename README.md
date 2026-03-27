# Android TV Chromecast Monitor

Script Python minimal pour detecter les appareils Android TV exposes via Chromecast sur le reseau local et afficher leur etat de lecture en terminal.

## Fonctionnement

- decouverte automatique via `pychromecast`
- affichage temps reel de l'application active
- detection validee pour VLC sur Android TV

## Installation

```bash
cd /home/claigle/Dev/perso/player_on_network
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Utilisation

```bash
python main.py
python main.py --verbose
python main.py --no-color
```

## Sortie attendue

```text
Appareil             IP              État         En lecture
────────────────────────────────────────────────────────────────────────
▶ VLC                192.168.1.33    Playing      <VLC>
⏹ Unknown            192.168.1.30    Stopped      ---
```

## Fichiers utiles

- `main.py` : point d'entree
- `monitor_loop.py` : decouverte et polling
- `vlc_chromecast.py` : integration pychromecast
- `display.py` : affichage terminal
- `config.py` : timeouts et largeurs d'affichage

## Limitations

- le script depend uniquement des informations exposees par Chromecast
- certaines apps remontent peu de metadonnees
- VLC Android peut apparaitre en `Playing` sans titre detaille
