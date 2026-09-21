"""Config licence Composer (etape 2 conversion).

La conversion CATIA 3D -> Composer exige une licence Composer active. Ce module
stocke, en config runtime (`app_config`, cle `composer_license_server`), le
serveur de licence flottante (FlexNet/DSLS, format `port@hote`) que la
conversion positionne dans l'environnement avant de lancer Composer Converter.

Best-effort : la variable d'environnement exacte lue par Composer depend de
l'edition (`LM_LICENSE_FILE` pour FlexNet, souvent `DSLICSRV` pour DSLS). Sans
serveur configure, Composer utilise la configuration locale de l'utilisateur.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import AppConfig

_KEY = "composer_license_server"


def get_license_server(db: Session) -> str:
    """Serveur de licence Composer (`port@hote`), vide si non configure."""
    row = db.get(AppConfig, _KEY)
    return row.value if row and row.value else ""


def set_license_server(db: Session, value: str) -> str:
    """Enregistre le serveur de licence Composer (chaine libre, ex. `4085@srv`)."""
    val = (value or "").strip()[:200]
    row = db.get(AppConfig, _KEY)
    if row is None:
        db.add(AppConfig(key=_KEY, value=val))
    else:
        row.value = val
    db.commit()
    return val
