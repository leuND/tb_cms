"""siapkan_demo.py: kembalikan data/tb_cms.sqlite ke keadaan awal demo.

Langkah:
1. Hapus file database lama (semua run, staging, dan log sinkronisasi ikut hilang).
2. Bangun ulang dari CSV sumber lewat import_sqlite (NOL run).
3. Opsional: --prarun TGL1 TGL2 ... menjalankan engine untuk tanggal itu.

Pakai (dari folder tb_cms, matikan server Flask dulu):
    python tools/siapkan_demo.py
    python tools/siapkan_demo.py --prarun 2026-10-31 2026-11-04
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import import_sqlite  # noqa: E402


def siapkan(db=import_sqlite.DB, prarun=()):
    db = Path(db)
    for f in [db, db.with_name(db.name + "-journal")]:
        try:
            f.unlink(missing_ok=True)
        except PermissionError:
            sys.exit(f"Tidak bisa menghapus {f}: file sedang dipakai. Matikan server Flask dulu.")
    import_sqlite.main(db)

    if prarun:
        from core import pemantauan
        for tgl in prarun:
            print(f"prarun {tgl}: {pemantauan.jalankan_pemantauan(tgl, db)}")
    print(f"Siap demo: {len(prarun)} run.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Reset database demo TB-CMS")
    ap.add_argument("--db", default=str(import_sqlite.DB))
    ap.add_argument("--prarun", nargs="*", default=[], metavar="TGL",
                    help="Tanggal pantau yang langsung dijalankan (YYYY-MM-DD)")
    a = ap.parse_args()
    siapkan(a.db, a.prarun)
