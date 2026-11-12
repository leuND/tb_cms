"""loader.py: baca katalog aturan dan data, dari CSV (bawaan) atau SQLite. Read-only.

Kalau db diberikan (path ke tb_cms.sqlite), tabel dibaca dari SQLite.
Kalau tidak, dibaca dari CSV seperti dulu. Pembersihan setelahnya sama persis.
"""
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
KATALOG = ROOT / "config" / "rules_catalog.csv"
DATA_DIR = ROOT / "data"

# Kolom tanggal per tabel, supaya langsung jadi tipe datetime
KOLOM_TANGGAL = {
    "pasien": ["tgl_lahir"],
    "episodes": ["tgl_diagnosis", "tgl_mulai", "created_at", "updated_at"],
    "followups": ["tgl_jadwal", "tgl_periksa", "tgl_input"],
    "outcomes": ["tgl_outcome", "tgl_input"],
    "salinan_sitb": ["tgl_diagnosis", "waktu_tarik"],
    "audit_logs": ["waktu"],
}


def _baca_sqlite(db, tabel):
    """Satu tabel SQLite sebagai DataFrame. Semua kolom TEXT, NULL jadi kosong."""
    # mode=ro: buka read-only, engine tidak boleh mengubah data sumber
    with sqlite3.connect(f"file:{Path(db).as_posix()}?mode=ro", uri=True) as con:
        return pd.read_sql_query(f'SELECT * FROM "{tabel}"', con, dtype=str)


def load_katalog(db=None):
    """Katalog aturan sebagai DataFrame (index = kode)."""
    if db is None:
        return pd.read_csv(KATALOG, encoding="utf-8-sig").set_index("kode")
    katalog = _baca_sqlite(db, "aturan").set_index("kode")
    # Di SQLite ambang tersimpan sebagai teks; samakan dengan versi CSV (angka)
    katalog["ambang"] = pd.to_numeric(katalog["ambang"])
    return katalog


def load_cfg(katalog):
    """Dict kode -> ambang (angka). Aturan tanpa ambang tidak masuk."""
    ambang = katalog["ambang"].dropna()
    return {kode: int(nilai) for kode, nilai in ambang.items()}


def load_data(data_dir=DATA_DIR, db=None):
    """Dict nama_tabel -> DataFrame. id/NIK dibaca sebagai teks."""
    data = {}
    for nama, kol_tgl in KOLOM_TANGGAL.items():
        if db is None:
            df = pd.read_csv(Path(data_dir) / f"{nama}.csv", dtype=str)
        else:
            df = _baca_sqlite(db, nama)
        # Sel yang hanya berisi spasi dianggap kosong (NaN), sama seperti sel kosong
        df = df.replace(r"^\s*$", None, regex=True)
        # Ubah kolom tanggal SETELAH spasi dibersihkan, supaya " " tidak bikin error
        for kol in kol_tgl:
            df[kol] = pd.to_datetime(df[kol])
        data[nama] = df
    return data
