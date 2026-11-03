"""SQLAlchemy 2.0 models pour Catia Toolbox.

Domaine : optimisation d'arborescence CATIA a partir de donnees exportees
(scan de dossier en metadonnees seules, ou import d'un listing CSV/JSON).

- `AppConfig` (key/value) : chemins locaux et configuration Composer, preserves au reset.
- `StructureImport` : une arborescence importee + ses metriques cachees.
- `TreeNode` : un noeud (fichier ou dossier) de l'arborescence importee.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid4() -> uuid.UUID:
    return uuid.uuid4()


# =============================================================================
# Imports & noeuds d'arborescence
# =============================================================================


class StructureImport(Base):
    __tablename__ = "structure_imports"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid4)
    # "folder" (scan local) | "csv" | "json" (listing importe).
    source_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    root_label: Mapped[str] = mapped_column(String(500), default="", server_default="")
    # Chemin scanne (folder) ou nom du fichier de listing importe. Audit only.
    source_ref: Mapped[str] = mapped_column(Text, default="", server_default="")
    node_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # Metriques calculees (TreeMetrics) serialisees en JSON. Jamais le type JSON
    # SQLite (incompat. cross-dialecte) -> Text.
    metrics_json: Mapped[str] = mapped_column(Text, default="{}", server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    nodes: Mapped[list["TreeNode"]] = relationship(
        back_populates="import_", cascade="all, delete-orphan", passive_deletes=True
    )


class TreeNode(Base):
    __tablename__ = "tree_nodes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid4)
    import_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("structure_imports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("tree_nodes.id", ondelete="CASCADE"), nullable=True, index=True
    )
    rel_path: Mapped[str] = mapped_column(String(1000), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    ext: Mapped[str] = mapped_column(String(40), default="", server_default="")
    kind: Mapped[str] = mapped_column(String(8), nullable=False)  # "file" | "folder"
    depth: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    size: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    mtime: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    import_: Mapped["StructureImport"] = relationship(back_populates="nodes")


# =============================================================================
# Module Comparaison (detection de pieces modifiees)
# =============================================================================


class DiffRun(Base):
    __tablename__ = "diff_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid4)
    base_import_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("structure_imports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    other_import_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("structure_imports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(30), default="completed", server_default="completed")
    summary: Mapped[str] = mapped_column(Text, default="{}", server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    entries: Mapped[list["DiffEntry"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", passive_deletes=True
    )


class DiffEntry(Base):
    __tablename__ = "diff_entries"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("diff_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rel_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    # added | removed | modified
    change_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    detail: Mapped[str] = mapped_column(Text, default="", server_default="")

    run: Mapped["DiffRun"] = relationship(back_populates="entries")


# =============================================================================
# Module Conversion (CATIA 3D -> Composer)
# =============================================================================


class ConversionRun(Base):
    __tablename__ = "conversion_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid4)
    import_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("structure_imports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(30), default="completed", server_default="completed")
    config_json: Mapped[str] = mapped_column(Text, default="{}", server_default="{}")
    summary: Mapped[str] = mapped_column(Text, default="{}", server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    items: Mapped[list["ConversionItem"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", passive_deletes=True
    )


class ConversionItem(Base):
    __tablename__ = "conversion_items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("conversion_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    target_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    source_ext: Mapped[str] = mapped_column(String(40), default="", server_default="")
    status: Mapped[str] = mapped_column(
        String(16), default="pending", server_default="pending", index=True
    )  # pending | accepted | rejected

    run: Mapped["ConversionRun"] = relationship(back_populates="items")


# =============================================================================
# Module Colorisation (couleur des pieces : par etat / type / profondeur)
# =============================================================================


class ColorizationRun(Base):
    __tablename__ = "colorization_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid4)
    import_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("structure_imports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Renseigne quand strategy == "by_change" (colorisation depuis une comparaison).
    diff_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("diff_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    strategy: Mapped[str] = mapped_column(String(20), default="by_type", server_default="by_type")
    status: Mapped[str] = mapped_column(String(30), default="completed", server_default="completed")
    config_json: Mapped[str] = mapped_column(Text, default="{}", server_default="{}")
    summary: Mapped[str] = mapped_column(Text, default="{}", server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    items: Mapped[list["ColorizationItem"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", passive_deletes=True
    )


class ColorizationItem(Base):
    __tablename__ = "colorization_items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("colorization_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rel_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    # Couleur RGB 0-255 (format natif CATIA / Composer ; pas de hex en dur).
    color_r: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    color_g: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    color_b: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    reason: Mapped[str] = mapped_column(Text, default="", server_default="")

    run: Mapped["ColorizationRun"] = relationship(back_populates="items")


# =============================================================================
# App-level config (key/value)
# =============================================================================


class AppConfig(Base):
    __tablename__ = "app_config"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="", server_default="")


# =============================================================================
# Etape 1 - Identification CATPart a traiter (nomenclature .xlsm + DE .zip)
# =============================================================================


class NomenclatureRun(Base):
    __tablename__ = "nomenclature_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid4)
    # Nom du fichier nomenclature (.xlsm) importe. Audit only.
    source_ref: Mapped[str] = mapped_column(Text, default="", server_default="")
    sheet: Mapped[str] = mapped_column(String(200), default="", server_default="")
    status: Mapped[str] = mapped_column(String(30), default="completed", server_default="completed")
    summary: Mapped[str] = mapped_column(Text, default="{}", server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    items: Mapped[list["NomenclatureItem"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", passive_deletes=True
    )


class NomenclatureItem(Base):
    __tablename__ = "nomenclature_items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("nomenclature_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    catpart: Mapped[str] = mapped_column(String(500), default="", server_default="", index=True)
    designation: Mapped[str] = mapped_column(Text, default="", server_default="")
    sin: Mapped[str] = mapped_column(String(200), default="", server_default="", index=True)
    version: Mapped[str] = mapped_column(String(60), default="", server_default="")  # Uxxx n
    # Identifie comme "a traiter" (colonne A TRAITER non vide).
    to_treat: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", index=True)
    # Contenu brut de la cellule "A TRAITER" (pour affichage / controle du filtre).
    to_treat_value: Mapped[str] = mapped_column(String(200), default="", server_default="")
    optimized: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", index=True)
    # Piece remplacee : ancien / nouveau PN et indice sur la meme ligne.
    replaced: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", index=True)
    old_pn: Mapped[str] = mapped_column(String(500), default="", server_default="")
    new_pn: Mapped[str] = mapped_column(String(500), default="", server_default="")
    old_rev: Mapped[str] = mapped_column(String(60), default="", server_default="")
    new_rev: Mapped[str] = mapped_column(String(60), default="", server_default="")
    # Reference couleur (nom de style / couleur) portee par la nomenclature (etape 3).
    color_ref: Mapped[str] = mapped_column(String(200), default="", server_default="")
    # Matiere / materiaux : vide => piece simple (mono-corps) ciblee par la colorisation.
    materials: Mapped[str] = mapped_column(String(200), default="", server_default="")
    # Slots (onglet Materiaux) : contenu brut des colonnes Slot 1 / 2 / 3.
    slot_1: Mapped[str] = mapped_column(String(200), default="", server_default="")
    slot_2: Mapped[str] = mapped_column(String(200), default="", server_default="")
    slot_3: Mapped[str] = mapped_column(String(200), default="", server_default="")
    # Reference de profil unique issue des slots pour les pieces mono-corps.
    mono_texture: Mapped[str] = mapped_column(String(200), default="", server_default="")
    # Piece mono-corps : un seul slot renseigne OU tous les slots identiques
    # (cible des modifications XML specifiques). Calcule depuis slot_1/2/3.
    mono_body: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", index=True)
    # Pieces portant une seule couleur (etape 3).
    mono_color: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    color_r: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    color_g: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    color_b: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    source_row: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    run: Mapped["NomenclatureRun"] = relationship(back_populates="items")


# =============================================================================
# Etapes 3 & 4 - Traitement / Integration via le SMGXML (CATComposer)
# =============================================================================


class SmgxmlRun(Base):
    __tablename__ = "smgxml_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid4)
    # Nom/chemin du SMGXML traite. Audit only.
    source_ref: Mapped[str] = mapped_column(Text, default="", server_default="")
    # "recolor" (etape 3) | "rename" (etape 4).
    operation: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="planned", server_default="planned")
    # "planned" (dry-run, rien ecrit) | "applied" (SMGXML modifie, .bak conserve).
    applied: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    backup_path: Mapped[str] = mapped_column(Text, default="", server_default="")
    output_path: Mapped[str] = mapped_column(Text, default="", server_default="")
    config_json: Mapped[str] = mapped_column(Text, default="{}", server_default="{}")
    summary: Mapped[str] = mapped_column(Text, default="{}", server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    changes: Mapped[list["SmgxmlChange"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", passive_deletes=True
    )


class SmgxmlChange(Base):
    __tablename__ = "smgxml_changes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("smgxml_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Acteur / piece visee dans le SMGXML.
    target: Mapped[str] = mapped_column(String(500), default="", server_default="")
    # "color" | "rename".
    change_type: Mapped[str] = mapped_column(String(16), nullable=False)
    old_value: Mapped[str] = mapped_column(Text, default="", server_default="")
    new_value: Mapped[str] = mapped_column(Text, default="", server_default="")

    run: Mapped["SmgxmlRun"] = relationship(back_populates="changes")
