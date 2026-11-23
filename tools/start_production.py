"""Inisialisasi database demo pada disk persisten lalu jalankan Waitress."""
import os
import shutil
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main():
    db = Path(os.environ.get("TBCMS_DB", ROOT / "data" / "tb_cms.sqlite"))
    masuk = Path(os.environ.get("TBCMS_MASUK", ROOT / "masuk"))
    db.parent.mkdir(parents=True, exist_ok=True)
    masuk.mkdir(parents=True, exist_ok=True)

    if not db.exists():
        from tools import siapkan_demo
        siapkan_demo.siapkan(db)

    if not any(masuk.iterdir()):
        repository_masuk = ROOT / "masuk"
        if repository_masuk.exists():
            for batch in repository_masuk.iterdir():
                destination = masuk / batch.name
                if batch.is_dir():
                    shutil.copytree(batch, destination)
                else:
                    shutil.copy2(batch, destination)

    os.environ["TBCMS_DB"] = str(db)
    os.environ["TBCMS_MASUK"] = str(masuk)

    port = os.environ.get("PORT", "10000")
    command = [
        sys.executable,
        "-m",
        "waitress",
        "--host",
        "0.0.0.0",
        "--port",
        port,
        "--threads",
        "4",
        "app_flask:app",
    ]
    raise SystemExit(subprocess.call(command, cwd=str(ROOT)))


if __name__ == "__main__":
    main()
