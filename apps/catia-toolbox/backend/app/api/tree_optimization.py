"""Optimize Composer part XML files in a selected input folder."""

from __future__ import annotations

import ipaddress
import os
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.core import onedrive
from app.core.errors import AppError
from app.core.security import safe_under_root
from app.core.tree_optimization import count_smgxml_files, optimize_folder
from app.db.session import get_db
from app.schemas import (
    TreeOptimizationCountIn,
    TreeOptimizationCountOut,
    TreeOptimizationFolderPickerIn,
    TreeOptimizationFolderPickerOut,
    TreeOptimizationIn,
    TreeOptimizationOut,
)

router = APIRouter(prefix="/tree-optimization", tags=["tree-optimization"])

_QT_APPLICATION = None


def _is_local_request(request: Request) -> bool:
    local_bind = settings.bind_host.strip().lower() in {"127.0.0.1", "localhost", "::1"}
    if not local_bind or request.client is None:
        return False
    host = request.client.host.lower()
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _open_folder_dialog(initial_path: str | None, title: str) -> str | None:
    if os.name == "nt":
        return open_qt_folder_dialog(initial_path, title)

    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError as exc:
        raise AppError(
            "FOLDER_DIALOG_UNAVAILABLE",
            "Le selecteur natif de dossier n'est pas disponible dans cet environnement.",
            status_code=503,
        ) from exc

    root = None
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        options = {"parent": root, "title": title, "mustexist": True}
        if initial_path and Path(initial_path).is_dir():
            options["initialdir"] = initial_path
        selected = filedialog.askdirectory(**options)
        return str(Path(selected).resolve()) if selected else None
    except tk.TclError as exc:
        raise AppError(
            "FOLDER_DIALOG_UNAVAILABLE",
            "Le selecteur de dossier local n'est pas disponible.",
            status_code=503,
        ) from exc
    finally:
        if root is not None:
            try:
                root.destroy()
            except tk.TclError:
                pass


def open_qt_folder_dialog(initial_path: str | None, title: str) -> str | None:
    global _QT_APPLICATION

    try:
        from PySide6.QtWidgets import QApplication, QFileDialog
    except ImportError as exc:
        raise AppError(
            "FOLDER_DIALOG_UNAVAILABLE",
            "Le selecteur Qt de dossier n'est pas disponible dans cet environnement.",
            status_code=503,
        ) from exc

    application = QApplication.instance()
    if application is None:
        application = QApplication([])
        application.setQuitOnLastWindowClosed(False)
    _QT_APPLICATION = application

    initial_directory = initial_path if initial_path and Path(initial_path).is_dir() else ""
    selected_path = QFileDialog.getExistingDirectory(
        None,
        title,
        initial_directory,
        QFileDialog.Option.ShowDirsOnly,
    )
    return str(Path(selected_path).resolve()) if selected_path else None


@router.post("/pick-folder", response_model=TreeOptimizationFolderPickerOut)
async def pick_local_folder(
    payload: TreeOptimizationFolderPickerIn,
    request: Request,
    db: Session = Depends(get_db),
) -> TreeOptimizationFolderPickerOut:
    if not _is_local_request(request):
        raise AppError(
            "LOCAL_FOLDER_PICKER_ONLY",
            "Le selecteur natif est disponible uniquement depuis l'application locale.",
            status_code=403,
        )
    if onedrive.get_onedrive_roots(db)["input"]:
        raise AppError(
            "INPUT_ROOT_CONFIGURED",
            "Parcourez les dossiers depuis la racine Input configurée.",
            status_code=400,
        )
    return TreeOptimizationFolderPickerOut(
        path=_open_folder_dialog(payload.initial_path, payload.title),
    )


def _resolve_input_folder(db: Session, path: str) -> Path:
    input_root = onedrive.get_onedrive_roots(db)["input"]
    if input_root:
        folder = safe_under_root(input_root, path)
    else:
        if settings.bind_host.strip().lower() not in {"127.0.0.1", "localhost", "::1"}:
            raise AppError(
                "ROOT_NOT_CONFIGURED",
                "Configurez une racine Input avant d'utiliser ce traitement sur un serveur distant.",
                status_code=400,
            )
        candidate = Path(path).expanduser()
        if not candidate.is_absolute():
            raise AppError(
                "TREE_OPTIMIZATION_PATH_INVALID",
                "Sans racine Input, fournissez un chemin absolu.",
                status_code=400,
            )
        folder = candidate.resolve()

    if not folder.is_dir():
        raise AppError(
            "TREE_OPTIMIZATION_PATH_INVALID",
            "Le chemin doit désigner un dossier existant sous la racine Input.",
            status_code=400,
            detail={"path": str(folder)},
        )
    return folder


@router.post("/count", response_model=TreeOptimizationCountOut)
def count_tree_optimization_files(
    payload: TreeOptimizationCountIn,
    db: Session = Depends(get_db),
) -> TreeOptimizationCountOut:
    folder = _resolve_input_folder(db, payload.path)
    try:
        files_count = count_smgxml_files(folder)
    except OSError as exc:
        raise AppError(
            "TREE_OPTIMIZATION_READ_FAILED",
            "Lecture du dossier impossible.",
            status_code=400,
            detail={"path": str(folder)},
        ) from exc
    return TreeOptimizationCountOut(path=str(folder), files_count=files_count)


@router.post("/run", response_model=TreeOptimizationOut)
def run_tree_optimization(
    payload: TreeOptimizationIn,
    db: Session = Depends(get_db),
) -> TreeOptimizationOut:
    folder = _resolve_input_folder(db, payload.path)
    try:
        result = optimize_folder(folder, apply=payload.apply)
    except OSError as exc:
        raise AppError(
            "TREE_OPTIMIZATION_READ_FAILED",
            "Lecture du dossier impossible.",
            status_code=400,
            detail={"path": str(folder)},
        ) from exc
    return TreeOptimizationOut(
        path=result["path"],
        applied=result["applied"],
        files_scanned=result["files_scanned"],
        files_with_changes=result["files_with_changes"],
        files_modified=result["files_modified"],
        removed_elements=result["removed_elements"],
    )
