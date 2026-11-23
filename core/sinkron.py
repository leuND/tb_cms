"""sinkron.py: komponen ETL simulasi. Satu-satunya penulis tabel sumber selain import_sqlite.

Folder masuk/ berisi batch siap pakai (masuk/batch_001/, ...). Tiap batch berisi CSV
dengan format sama seperti CSV sumber, ditambah berkas .done sebagai tanda siap.
Ini SIMULASI: tidak terhubung ke SIMRS atau SITB asli.

Alur proses_folder_masuk():
1. Pindai masuk/, ambil batch ber-.done yang belum tercatat di log_sinkronisasi.
2. Validasi kolom. Tidak cocok: batch ditolak, log status "gagal", data tidak berubah.
3. Isi staging_* dengan status_staging "pending".
4. Upsert ke tabel sumber dalam SATU transaksi, lalu tandai staging "loaded".
5. Catat di log_sinkronisasi.
6. Tambah baris audit_logs "Sinkronisasi dari SIMRS" untuk tiap episode yang baru atau berubah
   (supaya R2 tidak salah menandai record yang diubah oleh sinkronisasi).
7. Jalankan ulang engine untuk tanggal pantau aktif.

Idempotent: batch_id + hash isi yang sama diproses dua kali tidak menggandakan data.
Tidak mengimpor flask.
"""
import hashlib
import os
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

from core import pemantauan, queries as q

ROOT = Path(__file__).resolve().parent.parent
MASUK = Path(os.environ.get("TBCMS_MASUK", ROOT / "masuk"))

# Tabel yang boleh diisi lewat batch dan kolom kuncinya (satu baris per kunci)
KUNCI = {
    "pasien": "id_pasien",
    "episodes": "id_episode",
    "followups": "id_followup",
    "outcomes": "id_episode",
    "salinan_sitb": "id_episode",
}
OLEH = "sinkron_simrs"


def _hash_batch(folder):
    """SHA-256 atas nama dan isi semua CSV di batch (urut nama). Isi berubah = hash berubah."""
    h = hashlib.sha256()
    for f in sorted(folder.glob("*.csv")):
        h.update(f.name.encode())
        h.update(f.read_bytes())
    return h.hexdigest()


def _kolom_tabel(con, tabel):
    return [r[1] for r in con.execute(f'PRAGMA table_info("{tabel}")')]


def _isi(nilai):
    """NaN/spasi -> None, selain itu teks. Sama dengan cara import_sqlite menyimpan."""
    if nilai is None or (not isinstance(nilai, str) and pd.isna(nilai)) or str(nilai).strip() == "":
        return None
    return str(nilai)


def _baca_dan_validasi(con, folder):
    """Dict tabel -> DataFrame. ValueError kalau berkas atau kolom tidak cocok dengan tabel sumber."""
    berkas = sorted(folder.glob("*.csv"))
    if not berkas:
        raise ValueError("batch tidak berisi CSV")
    hasil = {}
    for f in berkas:
        tabel = f.stem
        if tabel not in KUNCI:
            raise ValueError(f"{f.name}: tabel tidak dikenal (boleh: {', '.join(KUNCI)})")
        df = pd.read_csv(f, dtype=str, encoding="utf-8-sig")
        harus = _kolom_tabel(con, tabel)
        if list(df.columns) != harus:
            kurang = [k for k in harus if k not in df.columns]
            lebih = [k for k in df.columns if k not in harus]
            raise ValueError(f"{f.name}: kolom tidak cocok (kurang {kurang}, lebih {lebih}, atau urutan beda)")
        kunci = KUNCI[tabel]
        if df[kunci].map(_isi).isna().any():
            raise ValueError(f"{f.name}: ada baris tanpa {kunci}")
        if df[kunci].duplicated().any():
            raise ValueError(f"{f.name}: {kunci} ganda di dalam batch")
        hasil[tabel] = df
    return hasil


def daftar_batch(masuk=MASUK, db=q.DB):
    """Status tiap folder batch: 'belum siap' (tanpa .done), 'menunggu', 'loaded', atau 'gagal'."""
    if not Path(masuk).exists():
        return []
    with sqlite3.connect(db) as con:
        log = {(b, h): s for b, h, s in con.execute("SELECT batch_id, hash_berkas, status FROM log_sinkronisasi")}
    hasil = []
    for folder in sorted(p for p in Path(masuk).iterdir() if p.is_dir()):
        if not (folder / ".done").exists():
            status = "belum siap"
        else:
            status = log.get((folder.name, _hash_batch(folder)), "menunggu")
        hasil.append({"batch_id": folder.name, "status": status})
    return hasil


def _catat_log(con, batch_id, h, waktu, jumlah, status, pesan):
    con.execute("INSERT INTO log_sinkronisasi VALUES (?, ?, ?, ?, ?, ?)",
                (batch_id, h, waktu, jumlah, status, pesan))


def proses_batch(folder, db=q.DB):
    """Proses satu folder batch. Hasil dict: batch_id, status, jumlah_baris, episode, pesan."""
    folder = Path(folder)
    batch_id, h = folder.name, _hash_batch(folder)
    waktu = datetime.now().isoformat(timespec="seconds")
    con = sqlite3.connect(db)
    try:
        # 1. Sudah pernah diproses dengan isi sama? Lewati (idempotent)
        lama = con.execute("SELECT hash_berkas, status FROM log_sinkronisasi WHERE batch_id = ?",
                           (batch_id,)).fetchall()
        if (h, "loaded") in lama or (h, "gagal") in lama:
            return {"batch_id": batch_id, "status": "dilewati", "jumlah_baris": 0, "episode": [],
                    "pesan": "sudah tercatat di log dengan isi yang sama"}
        if any(s == "loaded" for _, s in lama):
            with con:
                _catat_log(con, batch_id, h, waktu, 0, "gagal", "batch_id sudah dimuat dengan isi berbeda")
            return {"batch_id": batch_id, "status": "gagal", "jumlah_baris": 0, "episode": [],
                    "pesan": "batch_id sudah dimuat dengan isi berbeda"}

        # 2. Validasi; gagal = catat log, data tidak berubah
        try:
            data = _baca_dan_validasi(con, folder)
        except ValueError as e:
            with con:
                _catat_log(con, batch_id, h, waktu, 0, "gagal", str(e))
            return {"batch_id": batch_id, "status": "gagal", "jumlah_baris": 0, "episode": [], "pesan": str(e)}
        jumlah = sum(len(df) for df in data.values())

        # 3. Staging pending (transaksi sendiri: jejak batch tetap ada walau langkah 4 gagal)
        with con:
            for tabel, df in data.items():
                kolom = list(df.columns) + ["batch_id", "diterima_pada", "status_staging"]
                tanda = ", ".join("?" * len(kolom))
                con.executemany(f'INSERT INTO "staging_{tabel}" VALUES ({tanda})',
                                [[_isi(v) for v in baris] + [batch_id, waktu, "pending"]
                                 for baris in df.itertuples(index=False)])

        # 4-6. Upsert + tandai loaded + log + audit, semuanya satu transaksi
        episode = set()
        try:
            with con:
                for tabel, df in data.items():
                    kunci, kolom = KUNCI[tabel], list(df.columns)
                    daftar = ", ".join(f'"{k}"' for k in kolom)
                    for baris in df.itertuples(index=False):
                        baru = tuple(_isi(v) for v in baris)
                        nilai_kunci = baru[kolom.index(kunci)]
                        lama_row = con.execute(f'SELECT {daftar} FROM "{tabel}" WHERE "{kunci}" = ?',
                                               (nilai_kunci,)).fetchone()
                        if lama_row == baru:
                            continue  # sama persis: tidak dihitung berubah
                        con.execute(f'DELETE FROM "{tabel}" WHERE "{kunci}" = ?', (nilai_kunci,))
                        con.execute(f'INSERT INTO "{tabel}" ({daftar}) VALUES ({", ".join("?" * len(kolom))})', baru)
                        if tabel == "pasien":
                            episode |= {r[0] for r in con.execute(
                                "SELECT id_episode FROM episodes WHERE id_pasien = ?", (nilai_kunci,))}
                        else:
                            episode.add(baru[kolom.index("id_episode")])
                    con.execute(f'UPDATE "staging_{tabel}" SET status_staging = ? WHERE batch_id = ?',
                                ("loaded", batch_id))
                # Episode dari baris pasien yang baru dimuat di batch yang sama
                if "pasien" in data and "episodes" in data:
                    ids = set(data["pasien"]["id_pasien"])
                    episode |= set(data["episodes"].loc[data["episodes"]["id_pasien"].isin(ids), "id_episode"])
                waktu_audit = waktu.replace("T", " ")[:16]
                con.executemany("INSERT INTO audit_logs (id_episode, waktu, oleh, aksi) VALUES (?, ?, ?, ?)",
                                [(e, waktu_audit, OLEH, f"Sinkronisasi dari SIMRS ({batch_id})")
                                 for e in sorted(episode)])
                _catat_log(con, batch_id, h, waktu, jumlah, "loaded", f"{len(episode)} episode baru/berubah")
        except sqlite3.Error as e:
            with con:
                _catat_log(con, batch_id, h, waktu, 0, "gagal", f"upsert dibatalkan: {e}")
            return {"batch_id": batch_id, "status": "gagal", "jumlah_baris": 0, "episode": [], "pesan": str(e)}
        return {"batch_id": batch_id, "status": "loaded", "jumlah_baris": jumlah,
                "episode": sorted(episode), "pesan": f"{len(episode)} episode baru/berubah"}
    finally:
        con.close()


def proses_folder_masuk(tgl_aktif=None, db=q.DB, masuk=MASUK):
    """Proses semua batch siap di masuk/, lalu jalankan ulang engine untuk tgl_aktif.

    Hasil dict: batch (list hasil proses_batch), ringkasan_sebelum, ringkasan_sesudah
    (jumlah per status pada tgl_aktif; None kalau tgl_aktif kosong atau belum ada run).
    """
    sebelum = q.ringkasan(tgl_aktif, db=db)["status"] if tgl_aktif and q.info_run(tgl_aktif, db) else None
    hasil = []
    for b in daftar_batch(masuk, db):
        if b["status"] == "menunggu":
            hasil.append(proses_batch(Path(masuk) / b["batch_id"], db))
    sesudah = sebelum
    if tgl_aktif and any(h["status"] == "loaded" for h in hasil):
        pemantauan.jalankan_pemantauan(tgl_aktif, db)
        sesudah = q.ringkasan(tgl_aktif, db=db)["status"]
    return {"batch": hasil, "ringkasan_sebelum": sebelum, "ringkasan_sesudah": sesudah}
