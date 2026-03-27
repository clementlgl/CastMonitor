# CastMonitor (Home Assistant Integration)

Integration Home Assistant compatible HACS pour detecter les lectures actives sur Chromecast / Android TV.

## Structure du depot

- `hacs.json`
- `custom_components/castmonitor/__init__.py`
- `custom_components/castmonitor/manifest.json`
- `custom_components/castmonitor/sensor.py`
- `custom_components/castmonitor/strings.json`

## Installation via HACS

1. Pousser ce depot sur GitHub.
2. Dans Home Assistant, ouvrir HACS.
3. Aller dans `Integrations` puis `Custom repositories`.
4. Ajouter l'URL de ce depot avec le type `Integration`.
5. Installer `CastMonitor`.
6. Redemarrer Home Assistant.

## Configuration

Ajouter dans `configuration.yaml`:

```yaml
sensor:
	- platform: castmonitor
		scan_interval: 30
```

## Entite exposee

- Capteur: `sensor.castmonitor_active_streams`
- Valeur: nombre de lectures actives
- Attributs:
	- `playing_count`
	- `device_count`
	- `devices` (liste detaillee avec `device_name`, `ip`, `app_name`, `state`, `title`)

## Notes

- L'integration utilise `pychromecast` via le champ `requirements` du `manifest.json`.
- Les informations remontent ce que Chromecast expose; certaines applications peuvent fournir peu de metadonnees.
