## Installation via HACS

1. Pousser ce dépôt sur GitHub.
2. Dans Home Assistant, ouvrir HACS.
3. Aller dans `Intégrations` puis `Dépôts personnalisés`.
4. Ajouter l'URL de ce dépôt avec le type `Intégration`.
5. Installer `CastMonitor`.
6. Redémarrer Home Assistant.

## Ajout d'un appareil

1. Aller dans **Paramètres → Appareils et services**.
2. Cliquer **+ Ajouter une intégration** et rechercher `CastMonitor`.
3. Renseigner :
   - **Nom** — nom affiché dans HA (ex: `Salon TV` )
   - **Adresse IP** — IP locale du Chromecast
   - **Port** — `8009` par défaut
4. HA tente une connexion pour valider. En cas d'échec, un message d'erreur s'affiche.
5. Répéter pour chaque appareil à surveiller.

## Entités exposées

Pour chaque appareil ajouté (ex: `Salon TV` ) :

| Entité | ID                       | Description             |
|--------|--------------------------|-------------------------|
| Player | `sensor.salon_tv_player` | État de lecture         |
| Title  | `sensor.salon_tv_title`  | Titre du média en cours |

### États possibles ( `sensor.<nom>_player` )

| Valeur        | Description                 |
|---------------|-----------------------------|
| `playing`     | Lecture en cours            |
| `paused`      | En pause                    |
| `idle`        | App active, rien en lecture |
| `stopped`     | Aucune app active           |
| `unreachable` | Appareil inaccessible       |

### Attributs du sensor Player

| Attribut   | Description                          |
|------------|--------------------------------------|
| `app_name` | Application en cours (YouTube, VLC…) |
| `title`    | Titre du média                       |
| `ip`       | Adresse IP de l'appareil             |
| `port`     | Port de connexion                    |

## Fonctionnement technique

- Connexion TCP persistante via `pychromecast` — pas de polling.
- Mise à jour instantanée à chaque changement d'état.
- Reconnexion automatique après 15 secondes en cas de déconnexion.
- Dépendance : `pychromecast==13.1.0` (installée automatiquement).

## Notes

- Les Chromecasts doivent être accessibles sur le réseau local de HA.
