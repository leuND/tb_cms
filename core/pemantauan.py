"""pemantauan.py: jalankan engine untuk satu tanggal pantau dan simpan hasilnya ke SQLite.

Dipakai tombol "Jalankan pemantauan" di tampilan. Status dan aturan tetap dihitung
oleh engine (runner.jalankan); fungsi ini hanya memanggilnya lewat import.
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "tb_cms.sqlite"
sys.path.insert(0, str(ROOT / "engine"))  # runner.py memakai "from loader import ..."

import runner  # noqa: E402


def jalankan_pemantauan(tgl, db=DB):
    """Jalankan 15 aturan pada data di SQLite untuk tanggal tgl ('YYYY-MM-DD').
    Run lama dengan tanggal yang sama ditimpa. Mengembalikan ringkasan jumlah per status."""
    hasil = runner.jalankan(pd.Timestamp(tgl), str(ROOT / "data"), str(db))
    runner.simpan_db(hasil, str(db))
    return hasil["ringkasan"]
