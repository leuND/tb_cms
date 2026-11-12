"""runner.py: jalankan semua aturan dan tulis findings.json.

Contoh (dari folder tb_cms):
    python engine/runner.py --tgl-pantau 2026-10-31
"""
import argparse
import json
import sqlite3
from datetime import datetime

import pandas as pd

from loader import ROOT, load_cfg, load_data, load_katalog

DB_DEFAULT = ROOT / "data" / "tb_cms.sqlite"
from rules import ATURAN, KOLOM_TEMUAN


def status_data(jumlah_aturan):
    """Dari jumlah ATURAN unik yang kena (bukan jumlah baris temuan).
    0 = Sinambung, 1 = Perlu Cek, >=2 = Terputus (status DATA, bukan pasien)."""
    if jumlah_aturan == 0:
        return "Sinambung"
    if jumlah_aturan == 1:
        return "Perlu Cek"
    return "Terputus"


def jalankan(tgl_pantau, data_dir, db=None):
    katalog = load_katalog(db)
    cfg = load_cfg(katalog)
    data = load_data(data_dir, db)

    # 1. Jalankan tiap aturan, kumpulkan semua temuan
    hasil = [fungsi(data, cfg, tgl_pantau) for fungsi in ATURAN.values()]
    temuan = pd.concat(hasil, ignore_index=True) if hasil else pd.DataFrame(columns=KOLOM_TEMUAN)

    # 2. Susun per episode, tambahkan info aturan dari katalog
    episode_list = []
    for _, ep in data["episodes"].iterrows():
        milik = temuan[temuan["id_episode"] == ep["id_episode"]]
        daftar = []
        for _, t in milik.iterrows():
            aturan = katalog.loc[t["kode"]]
            ambang = cfg.get(t["kode"], "")  # pakai versi int, supaya tidak tampil "240.0"
            daftar.append({
                "kode": t["kode"],
                "indikator": aturan["indikator"],
                "tahap": aturan["tahap"],
                "keparahan": aturan["keparahan"],
                "kondisi": aturan["kondisi"].format(ambang=ambang, satuan=aturan["satuan"]),
                "detail": t["detail"],
            })
        jumlah_aturan = milik["kode"].nunique()  # 2 temuan C3 tetap dihitung 1 aturan
        episode_list.append({
            "id_episode": ep["id_episode"],
            "faskes": ep["faskes"],
            "status": status_data(jumlah_aturan),
            "jumlah_aturan": int(jumlah_aturan),
            "jumlah_temuan": len(daftar),
            "temuan": daftar,
        })

    # 3. Ringkasan jumlah episode per status
    ringkasan = {s: 0 for s in ["Sinambung", "Perlu Cek", "Terputus"]}
    for e in episode_list:
        ringkasan[e["status"]] += 1

    return {
        "tgl_pantau": tgl_pantau.strftime("%Y-%m-%d"),
        "aturan_dijalankan": list(ATURAN.keys()),
        "ringkasan": ringkasan,
        "episode": episode_list,
    }


SKEMA_HASIL = """
CREATE TABLE IF NOT EXISTS run_pemantauan (
    id_run          INTEGER PRIMARY KEY AUTOINCREMENT,
    tgl_pantau      TEXT NOT NULL UNIQUE,
    dijalankan_pada TEXT NOT NULL,
    jumlah_aturan   INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS temuan (
    id_run     INTEGER NOT NULL REFERENCES run_pemantauan(id_run),
    id_episode TEXT NOT NULL,
    kode       TEXT NOT NULL,
    detail     TEXT
);
CREATE TABLE IF NOT EXISTS episode_status (
    id_run        INTEGER NOT NULL REFERENCES run_pemantauan(id_run),
    id_episode    TEXT NOT NULL,
    status        TEXT NOT NULL,
    jumlah_aturan INTEGER NOT NULL,
    jumlah_temuan INTEGER NOT NULL
);
CREATE VIEW IF NOT EXISTS v_episode_status AS
    SELECT r.tgl_pantau, s.id_episode, e.faskes, e.lifecycle_status,
           s.status, s.jumlah_aturan, s.jumlah_temuan
    FROM episode_status s
    JOIN run_pemantauan r ON r.id_run = s.id_run
    LEFT JOIN episodes e ON e.id_episode = s.id_episode;
CREATE VIEW IF NOT EXISTS v_ringkasan AS
    SELECT r.tgl_pantau, s.status, COUNT(*) AS jumlah
    FROM episode_status s
    JOIN run_pemantauan r ON r.id_run = s.id_run
    GROUP BY r.tgl_pantau, s.status;
CREATE VIEW IF NOT EXISTS v_temuan AS
    SELECT r.tgl_pantau, t.id_episode, t.kode, t.detail,
           a.indikator, a.tahap, a.keparahan, a.steward, a.kondisi, a.ambang, a.satuan
    FROM temuan t
    JOIN run_pemantauan r ON r.id_run = t.id_run
    LEFT JOIN aturan a ON a.kode = t.kode;
"""


def simpan_db(hasil, db):
    """Tulis hasil satu tanggal pantau ke tabel hasil di SQLite.
    Tanggal yang sama dijalankan ulang: run lama dihapus dulu, jadi tidak dobel.
    Hanya tabel hasil yang ditulis; tabel sumber tidak disentuh."""
    tgl = hasil["tgl_pantau"]
    with sqlite3.connect(db) as con:  # with = satu transaksi: semua masuk atau tidak sama sekali
        con.executescript(SKEMA_HASIL)
        lama = con.execute("SELECT id_run FROM run_pemantauan WHERE tgl_pantau = ?", (tgl,)).fetchone()
        if lama:
            for tabel in ["temuan", "episode_status", "run_pemantauan"]:
                con.execute(f"DELETE FROM {tabel} WHERE id_run = ?", lama)
        cur = con.execute(
            "INSERT INTO run_pemantauan (tgl_pantau, dijalankan_pada, jumlah_aturan) VALUES (?, ?, ?)",
            (tgl, datetime.now().isoformat(timespec="seconds"), len(hasil["aturan_dijalankan"])))
        id_run = cur.lastrowid
        con.executemany(
            "INSERT INTO episode_status VALUES (?, ?, ?, ?, ?)",
            [(id_run, e["id_episode"], e["status"], e["jumlah_aturan"], e["jumlah_temuan"])
             for e in hasil["episode"]])
        con.executemany(
            "INSERT INTO temuan VALUES (?, ?, ?, ?)",
            [(id_run, e["id_episode"], t["kode"], t["detail"])
             for e in hasil["episode"] for t in e["temuan"]])
    return id_run


def main():
    parser = argparse.ArgumentParser(description="TB-CMS rule runner")
    parser.add_argument("--tgl-pantau", required=True, help="Tanggal pantau, format YYYY-MM-DD")
    parser.add_argument("--data", default=str(ROOT / "data"), help="Folder CSV data")
    parser.add_argument("--out", default=str(ROOT / "findings.json"), help="File output")
    parser.add_argument("--db", default=None,
                        help="Baca dari SQLite (mis. data/tb_cms.sqlite), bukan CSV")
    parser.add_argument("--simpan-db", action="store_true",
                        help="Tulis hasil ke tabel hasil di SQLite (--db, bawaan data/tb_cms.sqlite)")
    args = parser.parse_args()

    hasil = jalankan(pd.Timestamp(args.tgl_pantau), args.data, args.db)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(hasil, f, ensure_ascii=False, indent=2)
    if args.simpan_db:
        db = args.db or str(DB_DEFAULT)
        id_run = simpan_db(hasil, db)
        print(f"Disimpan ke {db} (id_run {id_run})")

    print(f"Tanggal pantau {hasil['tgl_pantau']}: {hasil['ringkasan']}")
    for e in hasil["episode"]:
        kode = ", ".join(t["kode"] for t in e["temuan"]) or "-"
        print(f"  {e['id_episode']}  {e['status']:<10} {kode}")
    print(f"Ditulis ke {args.out}")


if __name__ == "__main__":
    main()
