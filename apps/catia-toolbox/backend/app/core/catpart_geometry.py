"""Partial, name-independent geometry signatures from CADMPEG STEP exports."""

from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from app.config import settings

_MAX_STEP_BYTES = 25 * 1024 * 1024
_MAX_SIGNATURE_POINTS = 128
_DISTANCE_BINS = 12
_CADMPEG_TIMEOUT_SECONDS = 30
_NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][+-]?\d+)?"
_ENTITY_RE = re.compile(r"(?m)^\s*#\d+\s*=\s*([A-Z][A-Z0-9_]*)\b", re.IGNORECASE)
_POINT_RE = re.compile(
    rf"CARTESIAN_POINT\s*\(\s*'(?:[^']|'')*'\s*,\s*"
    rf"\(\s*({_NUMBER})\s*,\s*({_NUMBER})\s*,\s*({_NUMBER})\s*\)\s*\)",
    re.IGNORECASE | re.DOTALL,
)
_GEOMETRY_TYPES = frozenset(
    {
        "ADVANCED_FACE",
        "CARTESIAN_POINT",
        "CIRCLE",
        "CLOSED_SHELL",
        "CONICAL_SURFACE",
        "CYLINDRICAL_SURFACE",
        "DIRECTION",
        "EDGE_CURVE",
        "ELLIPSE",
        "LINE",
        "MANIFOLD_SOLID_BREP",
        "PLANE",
        "SPHERICAL_SURFACE",
        "TOROIDAL_SURFACE",
        "VECTOR",
        "VERTEX_POINT",
        "B_SPLINE_CURVE_WITH_KNOTS",
        "B_SPLINE_SURFACE_WITH_KNOTS",
    }
)
_TOPOLOGY_TYPES = ("MANIFOLD_SOLID_BREP", "CLOSED_SHELL", "ADVANCED_FACE", "EDGE_CURVE", "VERTEX_POINT")


@dataclass(frozen=True)
class GeometrySignature:
    primitive_counts: dict[str, int]
    distance_histogram: tuple[int, ...]
    topology_complete: bool

    @property
    def quality(self) -> str:
        return "complete" if self.topology_complete else "partial"


@dataclass(frozen=True)
class GeometryIssue:
    code: str
    message: str


def resolve_cadmpeg() -> tuple[str | None, GeometryIssue | None]:
    configured = settings.cadmpeg_path.strip()
    if configured:
        candidate = Path(configured).expanduser()
        if candidate.is_file():
            return str(candidate.resolve()), None
        located = shutil.which(configured)
        if located:
            return located, None
        return None, GeometryIssue("CADMPEG_PATH_INVALID", "Le chemin CADMPEG configure est introuvable.")

    executable = shutil.which("cadmpeg") or shutil.which("cadmpeg.exe")
    if executable:
        return executable, None
    return None, GeometryIssue(
        "CADMPEG_NOT_FOUND",
        "CADMPEG est absent. Definissez CADMPEG_PATH ou ajoutez cadmpeg a PATH pour proposer des candidats.",
    )


def extract_geometry_signature(
    source: Path,
    executable: str,
    output_dir: Path,
    stem: str,
) -> tuple[GeometrySignature | None, GeometryIssue | None]:
    step_path = output_dir / f"{stem}.step"
    report_path = output_dir / f"{stem}.json"
    command = [
        executable,
        "convert",
        "--input-format",
        "catpart",
        "--limits",
        "desktop",
        str(source),
        "-o",
        str(step_path),
        "--report",
        str(report_path),
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_CADMPEG_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return None, GeometryIssue("CADMPEG_TIMEOUT", "Le decodage CADMPEG a depasse le delai autorise.")
    except OSError:
        return None, GeometryIssue(
            "CADMPEG_EXEC_FAILED",
            "Impossible de lancer l'executable CADMPEG configure.",
        )

    if result.returncode != 0:
        return None, GeometryIssue(
            "CADMPEG_CONVERSION_FAILED",
            "CADMPEG n'a pas pu decoder ce fichier CATPart.",
        )
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None, GeometryIssue(
            "CADMPEG_REPORT_INVALID",
            "Le rapport JSON CADMPEG est absent ou invalide.",
        )

    decode_report = report.get("decode_report")
    transfer = decode_report.get("transfer") if isinstance(decode_report, dict) else None
    if (
        report.get("status") != "ok"
        or not isinstance(transfer, dict)
        or transfer.get("geometry_transferred") is not True
    ):
        return None, GeometryIssue(
            "CATPART_GEOMETRY_UNAVAILABLE",
            "Aucune geometrie exploitable n'a ete extraite.",
        )

    try:
        if step_path.stat().st_size > _MAX_STEP_BYTES:
            return None, GeometryIssue(
                "CATPART_GEOMETRY_TOO_LARGE",
                "La signature geometrique depasse la limite autorisee.",
            )
        step_text = step_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None, GeometryIssue(
            "CATPART_STEP_MISSING",
            "Le fichier STEP temporaire CADMPEG est absent ou illisible.",
        )

    signature = parse_step_signature(step_text)
    if signature is None:
        return None, GeometryIssue(
            "CATPART_GEOMETRY_EMPTY",
            "Aucune primitive geometrique exploitable n'a ete extraite.",
        )
    return signature, None


def parse_step_signature(step_text: str) -> GeometrySignature | None:
    entity_counts = Counter(match.group(1).upper() for match in _ENTITY_RE.finditer(step_text))
    primitive_counts = {name: entity_counts[name] for name in _GEOMETRY_TYPES if entity_counts[name]}
    if not primitive_counts:
        return None

    points: list[tuple[float, float, float]] = []
    for match in _POINT_RE.finditer(step_text):
        points.append(tuple(float(value.replace("D", "E").replace("d", "e")) for value in match.groups()))
    histogram = _distance_histogram(points)
    topology_complete = all(entity_counts[name] > 0 for name in _TOPOLOGY_TYPES)
    return GeometrySignature(primitive_counts, histogram, topology_complete)


def geometry_similarity(left: GeometrySignature, right: GeometrySignature) -> float:
    primitive_score = _weighted_jaccard(left.primitive_counts, right.primitive_counts)
    left_distances = {str(index): value for index, value in enumerate(left.distance_histogram)}
    right_distances = {str(index): value for index, value in enumerate(right.distance_histogram)}
    distance_score = _weighted_jaccard(left_distances, right_distances)
    if sum(left.distance_histogram) and sum(right.distance_histogram):
        return round((0.4 * primitive_score + 0.6 * distance_score) * 100, 1)
    return round(primitive_score * 100, 1)


def _distance_histogram(points: list[tuple[float, float, float]]) -> tuple[int, ...]:
    histogram = [0] * _DISTANCE_BINS
    normalized_points = sorted(set(points))
    if len(normalized_points) > _MAX_SIGNATURE_POINTS:
        stride = math.ceil(len(normalized_points) / _MAX_SIGNATURE_POINTS)
        normalized_points = normalized_points[::stride][:_MAX_SIGNATURE_POINTS]
    if len(normalized_points) < 2:
        return tuple(histogram)

    distances = [
        math.dist(left, right)
        for index, left in enumerate(normalized_points)
        for right in normalized_points[index + 1 :]
    ]
    scale = max(distances, default=0.0)
    if scale <= 0:
        return tuple(histogram)
    for distance in distances:
        bucket = min(int((distance / scale) * _DISTANCE_BINS), _DISTANCE_BINS - 1)
        histogram[bucket] += 1
    return tuple(histogram)


def _weighted_jaccard(left: Mapping[str, int], right: Mapping[str, int]) -> float:
    keys = left.keys() | right.keys()
    denominator = sum(max(left.get(key, 0), right.get(key, 0)) for key in keys)
    if denominator == 0:
        return 0.0
    numerator = sum(min(left.get(key, 0), right.get(key, 0)) for key in keys)
    return numerator / denominator
