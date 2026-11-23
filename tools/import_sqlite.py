"""import_sqlite.py: salin semua CSV di data/ dan katalog aturan ke data/tb_cms.sqlite.

Nama tabel = nama file CSV, nama kolom = header CSV, supaya rules.py tidak berubah.
Semua kolom disimpan sebagai TEXT: NIK tetap 16 digit, tanggal tetap YYYY-MM-DD.
Sel kosong menjadi NULL. Menjalankan ulang menimpa tabel sumber (if_exists="replace").

Selain tabel sumber, dibuat juga:
- tabel hasil engine (run_pemantauan, temuan, episode_status + view), kosong kalau baru;
- tabel staging_* dan log_sinkronisasi untuk sinkronisasi folder masuk/ (selalu dikosongkan).

Pakai:  python tools/import_sqlite.py [--db path/ke/file.sqlite]
"""
import argparse
import sqlite3
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DB = DATA / "tb_cms.sqlite"
KATALOG = ROOT / "config" / "rules_catalog.csv"
TABEL = ["pasien", "episodes", "followups", "outcomes", "salinan_sitb", "audit_logs"]
# Tabel yang bisa diisi lewat sinkronisasi (audit_logs ditulis oleh proses sinkron sendiri)
TABEL_STAGING = ["pasien", "episodes", "followups", "outcomes", "salinan_sitb"]
# status_staging (pending | loaded); bukan status_sinkron karena nama itu sudah dipakai salinan_sitb
KOLOM_STAGING = ["batch_id", "diterima_pada", "status_staging"]

sys.path.insert(0, str(ROOT / "engine"))
from runner import SKEMA_HASIL  # noqa: E402  skema tabel hasil, satu sumber dengan runner


def baca_csv(path):
    # utf-8-sig membuang BOM kalau ada; dtype=str supaya tidak ada yang diubah jadi angka
    return pd.read_csv(path, dtype=str, encoding="utf-8-sig")


def _tulis(con, nama, df):
    df.to_sql(nama, con, if_exists="replace", index=False, dtype={k: "TEXT" for k in df.columns})


def main(db=DB):
    with sqlite3.connect(db) as con:
        kolom_sumber = {}
        for nama in TABEL:
            df = baca_csv(DATA / f"{nama}.csv")
            _tulis(con, nama, df)
            kolom_sumber[nama] = list(df.columns)
            print(f"{nama:13s} {len(df):3d} baris")
        aturan = baca_csv(KATALOG)
        _tulis(con, "aturan", aturan)
        print(f"{'aturan':13s} {len(aturan):3d} baris")

        # Tabel hasil engine (CREATE IF NOT EXISTS: run lama tetap ada kecuali file dihapus)
        con.executescript(SKEMA_HASIL)

        # Staging: kolom sumber + kolom kendali batch, selalu kosong setelah impor
        for nama in TABEL_STAGING:
            _tulis(con, f"staging_{nama}", pd.DataFrame(columns=kolom_sumber[nama] + KOLOM_STAGING))
        con.executescript("""
            DROP TABLE IF EXISTS log_sinkronisasi;
            CREATE TABLE log_sinkronisasi (
                batch_id     TEXT NOT NULL,
                hash_berkas  TEXT NOT NULL,
                waktu        TEXT NOT NULL,
                jumlah_baris INTEGER NOT NULL,
                status       TEXT NOT NULL,   -- loaded | gagal
                pesan        TEXT
            );
        """)
        print("staging_* dan log_sinkronisasi dikosongkan")
    print(f"Ditulis ke {db}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="CSV sumber -> SQLite")
    ap.add_argument("--db", default=str(DB), help="File SQLite tujuan")
    main(ap.parse_args().db)
