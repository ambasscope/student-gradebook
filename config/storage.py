"""All mutable application data stays in a movable folder."""
import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
configured = Path(os.environ.get("GRADEBOOK_DATA_DIR", "app-data")).expanduser()
DATA_DIR = (configured if configured.is_absolute() else BASE_DIR / configured).resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)
for name in ("reports", "backups", "config"):
    (DATA_DIR / name).mkdir(exist_ok=True)

def load_secret_key():
    path = DATA_DIR / "config" / "secret-key.txt"
    if not path.exists():
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(secrets.token_urlsafe(48))
    return path.read_text(encoding="utf-8").strip()
