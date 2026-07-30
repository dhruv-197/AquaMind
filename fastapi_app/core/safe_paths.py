"""Path-containment helpers for user-supplied dataset paths.

Training endpoints used to accept a free-text `dataset_path` and hand it
straight to `pandas.read_csv`/`read_parquet` with no containment check —
an authenticated (now admin-only) caller could still point it at an
arbitrary server-readable file (e.g. `.env.local`). These helpers restrict
any user-supplied path to a fixed uploads directory.
"""
from __future__ import annotations

from pathlib import Path

# Only files under this directory may be referenced by a `dataset_path`
# request field. Uploads (e.g. /imports/reservoir) also land here.
UPLOADS_DIR = Path(__file__).resolve().parents[2] / "data" / "imports"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_SUFFIXES = {".csv", ".parquet", ".pq"}


class UnsafeDatasetPathError(ValueError):
    """Raised when a dataset_path escapes the sandboxed uploads directory."""


def resolve_dataset_path(user_path: str) -> Path:
    """Resolve a user-supplied dataset path, confined to UPLOADS_DIR.

    Accepts either a bare filename ("reservoir_latest.csv") or a path
    already inside UPLOADS_DIR. Anything else — absolute paths, `..`
    traversal, or paths resolving outside UPLOADS_DIR — is rejected.
    """
    raw = (user_path or "").strip()
    if not raw:
        raise UnsafeDatasetPathError("dataset_path must not be empty.")

    candidate = Path(raw)
    resolved = (candidate if candidate.is_absolute() else UPLOADS_DIR / candidate).resolve()

    try:
        resolved.relative_to(UPLOADS_DIR.resolve())
    except ValueError:
        raise UnsafeDatasetPathError(
            f"dataset_path must reference a file inside {UPLOADS_DIR} "
            "(upload it via the import endpoint first, then pass its filename)."
        )

    if resolved.suffix.lower() not in ALLOWED_SUFFIXES:
        raise UnsafeDatasetPathError(
            f"Unsupported dataset file type {resolved.suffix!r}; expected one of {sorted(ALLOWED_SUFFIXES)}."
        )
    if not resolved.exists():
        raise UnsafeDatasetPathError(f"No such uploaded dataset: {resolved.name}")

    return resolved
