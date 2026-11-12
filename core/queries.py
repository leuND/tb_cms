"""queries.py: semua query ke data/tb_cms.sqlite untuk tampilan.

Aturan lapisan ini:
- Read-only. Koneksi dibuka dengan mode=ro, jadi tidak bisa menulis.
- Tidak menghitung status atau aturan. Status dan temuan dibaca dari tabel hasil
  yang ditulis engine (runner.py --simpan-db).
- Tidak mengimpor streamlit. Mengembalikan dict, list, atau DataFrame,
  supaya bisa dipakai ulang oleh UI lain (mis. FastAPI) nanti.
"""
import re
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "tb_cms.sqlite"

STATUS = ["Sinambung", "Perlu Cek", "Terputus"]
WARNA_STATUS = {"Sinambung": "green", "Perlu Cek": "orange", "Terputus": "red"}
INDIKATOR = ["Completeness", "Consistency", "Timeliness", "Traceability"]
TAHAP = ["Create", "Store", "Use", "Share", "Archive", "Destroy"]


def _sql(query, params=(), db=DB):
    """Jalankan SELECT, hasilnya DataFrame."""
    with sqlite3.connect(f"file:{Path(db).as_posix()}?mode=ro", uri=True) as con:
        return pd.read_sql_query(query, con, params=params)


def _isi_kondisi(df):
    """Ganti {ambang} dan {satuan} di teks kondisi dengan nilainya. Hanya teks tampilan."""
    def isi(baris):
        teks = baris["kondisi"] or ""
        ambang = baris["ambang"] if pd.notna(baris["ambang"]) else ""
        satuan = baris["satuan"] if pd.notna(baris["satuan"]) else ""
        return teks.replace("{ambang}", str(ambang)).replace("{satuan}", str(satuan))
    df = df.copy()
    if len(df):
        df["kondisi"] = df.apply(isi, axis=1)
    return df


def daftar_tgl_pantau(db=DB):
    """List tanggal pantau yang sudah dijalankan engine, urut naik ('YYYY-MM-DD')."""
    return _sql("SELECT tgl_pantau FROM run_pemantauan ORDER BY tgl_pantau", db=db)["tgl_pantau"].tolist()


def ringkasan(tgl, db=DB):
    """Ringkasan satu tanggal pantau.

    Hasil dict:
      status          {"Sinambung": n, "Perlu Cek": n, "Terputus": n}
      total           jumlah episode
      indikator       {indikator: jumlah episode yang kena >= 1 aturan indikator itu}
      tahap_indikator DataFrame (baris = tahap, kolom = indikator),
                      isi = jumlah episode yang kena aturan di sel itu
    """
    st = _sql("SELECT status, jumlah FROM v_ringkasan WHERE tgl_pantau = ?", (tgl,), db)
    status = {s: 0 for s in STATUS}
    status.update(dict(zip(st["status"], st["jumlah"].astype(int))))

    tm = _sql("SELECT DISTINCT id_episode, indikator, tahap FROM v_temuan WHERE tgl_pantau = ?", (tgl,), db)
    per_ind = tm.drop_duplicates(["id_episode", "indikator"])["indikator"].value_counts()
    indikator = {i: int(per_ind.get(i, 0)) for i in INDIKATOR}

    return {"status": status, "total": sum(status.values()),
            "indikator": indikator, "tahap_indikator": _matriks_tahap(tgl, db)}


def _matriks_tahap(tgl, db=DB):
    """DataFrame baris = tahap, kolom = indikator, isi = jumlah episode yang kena."""
    tm = _sql("SELECT DISTINCT id_episode, indikator, tahap FROM v_temuan WHERE tgl_pantau = ?", (tgl,), db)
    return (tm.groupby(["tahap", "indikator"])["id_episode"].nunique()
              .unstack(fill_value=0)
              .reindex(index=TAHAP, columns=INDIKATOR, fill_value=0))


def _gabung(kata):
    """['A'] -> 'A', ['A','B'] -> 'A dan B', ['A','B','C'] -> 'A, B, dan C'."""
    kata = list(kata)
    if len(kata) <= 2:
        return " dan ".join(kata)
    return ", ".join(kata[:-1]) + ", dan " + kata[-1]


def kesimpulan_tahap(tgl, db=DB):
    """Satu paragraf kesimpulan dari matriks tahap x indikator, dihitung dari data.

    Isi: sel (tahap, indikator) dengan episode terbanyak, tahap yang hanya terkena satu
    indikator, indikator yang hanya muncul di satu tahap, dan tahap yang bersih.
    """
    m = _matriks_tahap(tgl, db)
    if m.values.sum() == 0:
        return "Tidak ada episode bermasalah pada tanggal pantau ini."
    kalimat = []

    # 1. Sel terbanyak (bisa lebih dari satu kalau seri)
    maks = int(m.values.max())
    sel = [(t, i) for t in TAHAP for i in INDIKATOR if m.loc[t, i] == maks]
    if len(sel) == 1:
        t, i = sel[0]
        kalimat.append(f"Masalah terbanyak ada di tahap {t} ({i}, {maks} episode).")
    else:
        daftar = _gabung(f"tahap {t} ({i})" for t, i in sel)
        kalimat.append(f"Masalah terbanyak ada di {daftar}, masing-masing {maks} episode.")

    # 2. Tahap yang hanya terkena satu indikator, dikelompokkan per indikator
    satu = {}
    for t in TAHAP:
        ind = [i for i in INDIKATOR if m.loc[t, i] > 0]
        if len(ind) == 1:
            satu.setdefault(ind[0], []).append(t)
    for i, tahap_ in satu.items():
        kalimat.append(f"Tahap {_gabung(tahap_)} hanya terkena {i}.")

    # 3. Indikator yang hanya muncul di satu tahap (lewati kalau sudah tersirat di kalimat 2)
    for i in INDIKATOR:
        tahap_ = [t for t in TAHAP if m.loc[t, i] > 0]
        if not tahap_:
            kalimat.append(f"Tidak ada masalah {i} sama sekali.")
        elif len(tahap_) == 1 and tahap_[0] not in satu.get(i, []):
            kalimat.append(f"Tidak ada masalah {i} di luar tahap {tahap_[0]}.")

    # 4. Tahap bersih
    bersih = [t for t in TAHAP if m.loc[t].sum() == 0]
    if bersih:
        kalimat.append(f"Tahap {_gabung(bersih)} bersih.")
    else:
        kalimat.append("Tidak ada tahap yang bersih.")
    return " ".join(kalimat)


def daftar_episode(tgl, status=None, indikator=None, tahap=None, faskes_akses=None, db=DB):
    """Tabel episode pada satu tanggal pantau, dengan filter opsional.

    status/indikator/tahap: None = semua. Filter indikator dan tahap memilih episode
    yang punya minimal satu temuan dengan indikator/tahap tersebut.
    Kolom: id_episode, faskes, lifecycle_status, status, jumlah_aturan, jumlah_temuan, kode.
    """
    ep = _sql("SELECT * FROM v_episode_status WHERE tgl_pantau = ? ORDER BY id_episode", (tgl,), db)
    tm = _sql("SELECT id_episode, kode, indikator, tahap FROM v_temuan WHERE tgl_pantau = ?", (tgl,), db)

    # Daftar kode unik per episode, mis. "C1, C2"
    kode = tm.groupby("id_episode")["kode"].apply(lambda k: ", ".join(sorted(set(k))))
    ep["kode"] = ep["id_episode"].map(kode).fillna("-")

    # --- INI INTI LOGIKA FILTER PASIEN (Versi SQL Terisolasi) ---
    if faskes_akses and faskes_akses != 'Semua':
        # Query langsung ke tabel master 'episodes' untuk mencari id_episode yang berelasi
        q_filter = """
            SELECT id_episode FROM episodes 
            WHERE id_pasien IN (
                SELECT id_pasien FROM episodes WHERE faskes = ?
            )
        """
        valid_episodes = _sql(q_filter, (faskes_akses,), db)["id_episode"].tolist()
        ep = ep[ep["id_episode"].isin(valid_episodes)]
    # -----------------------------------------------------------

    # Lanjutkan filter bawaan
    if status and status != 'Semua':
        ep = ep[ep["status"] == status]
    if indikator and indikator != 'Semua':
        ep = ep[ep["id_episode"].isin(tm.loc[tm["indikator"] == indikator, "id_episode"])]
    if tahap and tahap != 'Semua':
        ep = ep[ep["id_episode"].isin(tm.loc[tm["tahap"] == tahap, "id_episode"])]
        
    kolom = ["id_episode", "faskes", "lifecycle_status", "status", "jumlah_aturan", "jumlah_temuan", "kode"]

    return ep[kolom].reset_index(drop=True)

def detail_episode(id_episode, tgl, db=DB):
    """Semua yang perlu ditampilkan untuk satu episode pada satu tanggal pantau.

    Hasil dict:
      episode    dict data episode + pasien (nik, tgl_lahir, jenis_kelamin)
      status     dict status, jumlah_aturan, jumlah_temuan (None kalau belum dijalankan)
      temuan     DataFrame kode, detail, indikator, tahap, keparahan, steward, kondisi
      lifecycle  list dict {tahap, kode: [..]} untuk 6 tahap, urut Create..Destroy
      audit     DataFrame waktu, oleh, aksi
      sitb       dict salinan SITB, atau None kalau tidak ada
    """
    p = (id_episode,)
    ep = _sql("""SELECT e.*, p.nik, p.tgl_lahir, p.jenis_kelamin
                 FROM episodes e LEFT JOIN pasien p ON p.id_pasien = e.id_pasien
                 WHERE e.id_episode = ?""", p, db)
    if ep.empty:
        return None
    st = _sql("""SELECT status, jumlah_aturan, jumlah_temuan FROM v_episode_status
                 WHERE id_episode = ? AND tgl_pantau = ?""", (id_episode, tgl), db)
    tm = _sql("""SELECT kode, detail, indikator, tahap, keparahan, steward, kondisi, ambang, satuan
                 FROM v_temuan WHERE id_episode = ? AND tgl_pantau = ? ORDER BY kode""",
              (id_episode, tgl), db)
    tm = _isi_kondisi(tm).drop(columns=["ambang", "satuan"])

    lifecycle = [{"tahap": t, "kode": sorted(set(tm.loc[tm["tahap"] == t, "kode"]))} for t in TAHAP]

    audit = _sql("SELECT waktu, oleh, aksi FROM audit_logs WHERE id_episode = ? ORDER BY waktu", p, db)
    sitb = _sql("SELECT * FROM salinan_sitb WHERE id_episode = ?", p, db)

    return {
        "episode": {k: _isi(v) for k, v in ep.iloc[0].items()},  # sel kosong jadi None, bukan NaN
        "status": st.iloc[0].to_dict() if len(st) else None,
        "temuan": tm,
        "lifecycle": lifecycle,
        "audit": audit,
        "sitb": {k: _isi(v) for k, v in sitb.iloc[0].items()} if len(sitb) else None,
    }


# Aturan -> titik timeline tempat temuannya ditempelkan.
# "periksa" dan "tempo" adalah titik per follow-up; follow-up mana dibaca dari teks detail.
PETA_ATURAN = {
    "C1": "diagnosis", "K4": "diagnosis", "K5": "diagnosis",
    "K1": "mulai",
    "C3": "tempo", "T1": "periksa", "T2": "periksa", "K2": "periksa",
    "C2": "batas_outcome", "K3": "outcome", "T3": "outcome",
    "R1": "dibuat", "R2": "diubah",
    "R3": "batas_arsip", "R4": "batas_retensi",
}

# Titik cadangan kalau titik tujuan tidak ada (mis. tanggalnya kosong): (peristiwa, tahap, jenis)
_TITIK_CADANGAN = {
    "diagnosis": ("Diagnosis", "Create", "peristiwa"),
    "mulai": ("Mulai obat", "Create", "peristiwa"),
    "periksa": ("Follow-up", "Use", "peristiwa"),
    "tempo": ("Jatuh tempo follow-up", "Use", "batas"),
    "outcome": ("Outcome", "Use", "peristiwa"),
    "batas_outcome": ("Batas outcome", "Use", "batas"),
    "dibuat": ("Record dibuat", "Store", "peristiwa"),
    "diubah": ("Record diubah", "Store", "peristiwa"),
    "batas_arsip": ("Batas arsip", "Archive", "batas"),
    "batas_retensi": ("Batas retensi", "Destroy", "batas"),
}


def _isi(nilai, kosong=None):
    """Teks sel, atau `kosong` kalau sel NULL/NaN/hanya spasi."""
    if nilai is None or (not isinstance(nilai, str) and pd.isna(nilai)) or str(nilai).strip() == "":
        return kosong
    return str(nilai)


def _tgl(nilai):
    """Teks tanggal/waktu -> 'YYYY-MM-DD', atau None kalau kosong."""
    if _isi(nilai) is None:
        return None
    return pd.Timestamp(nilai).strftime("%Y-%m-%d")


def _geser(tanggal, **offset):
    """Tanggal 'YYYY-MM-DD' + offset (days=.. atau years=..), hasil 'YYYY-MM-DD'."""
    if tanggal is None:
        return None
    return (pd.Timestamp(tanggal) + pd.DateOffset(**offset)).strftime("%Y-%m-%d")


def _kunci_followup(dasar, detail, fu):
    """Cari follow-up yang dimaksud teks detail: 'id F24' atau 'bulan 5'. None kalau tidak ketemu."""
    m = re.search(r"id (F\w+)", detail or "")
    if m and m.group(1) in set(fu["id_followup"]):
        return f"{dasar}:{m.group(1)}"
    m = re.search(r"bulan (\d+)", detail or "")
    if m:
        cocok = fu.loc[fu["bulan"].str.strip() == m.group(1), "id_followup"]
        if len(cocok):
            return f"{dasar}:{cocok.iloc[0]}"
    return None


def timeline_episode(id_episode, tgl, db=DB):
    """Timeline vertikal satu episode: peristiwa + titik batas, dengan temuan ditempelkan.

    Hasil: list dict urut tanggal (tanggal kosong di akhir), tiap dict berisi
      tanggal, peristiwa, keterangan, tahap, jenis ("peristiwa" | "batas"),
      temuan [{kode, detail, steward}], warna ("merah" | "hijau" | "abu"), kunci.
    Warna: merah = ada temuan; abu = titik batas yang belum terlewati pada tgl;
    hijau = sisanya. Temuan dibaca dari tabel hasil engine, tidak dihitung ulang di sini.
    Titik batas memakai ambang dari tabel aturan, hanya untuk tampilan.
    """
    p = (id_episode,)
    ep = _sql("SELECT * FROM episodes WHERE id_episode = ?", p, db)
    if ep.empty:
        return None
    e = ep.iloc[0]
    fu = _sql("SELECT * FROM followups WHERE id_episode = ? ORDER BY CAST(bulan AS INTEGER)", p, db)
    oc = _sql("SELECT * FROM outcomes WHERE id_episode = ?", p, db)
    tm = _sql("SELECT kode, detail, steward FROM v_temuan WHERE id_episode = ? AND tgl_pantau = ? ORDER BY kode",
              (id_episode, tgl), db)
    ambang = {r["kode"]: r["ambang"] for _, r in _sql("SELECT kode, ambang FROM aturan", db=db).iterrows()}

    titik = {}  # kunci -> dict, urutan sisip dipertahankan (dict Python urut)

    def tambah(kunci, tanggal, peristiwa, keterangan, tahap, jenis="peristiwa"):
        titik[kunci] = {"tanggal": tanggal, "peristiwa": peristiwa, "keterangan": keterangan,
                        "tahap": tahap, "jenis": jenis, "temuan": [], "kunci": kunci}

    kosong = "(kosong)"
    isi = lambda nilai: _isi(nilai, kosong)  # noqa: E731
    tambah("diagnosis", _tgl(e["tgl_diagnosis"]), "Diagnosis", f"metode {isi(e['metode_diagnosis'])}", "Create")
    tambah("mulai", _tgl(e["tgl_mulai"]), "Mulai obat", f"paduan {isi(e['paduan'])}", "Create")
    tambah("dibuat", _tgl(e["created_at"]), "Record dibuat",
           f"sumber {isi(e['sumber_sistem'])}, oleh {isi(e['dibuat_oleh'])}", "Store")
    if _tgl(e["updated_at"]) and _tgl(e["updated_at"]) != _tgl(e["created_at"]):
        tambah("diubah", _tgl(e["updated_at"]), "Record diubah", "updated_at", "Store")

    # Follow-up: jadwal, periksa, dan jatuh tempo (hanya kalau hasil belum ada)
    for _, f in fu.iterrows():
        b, fid = f["bulan"], f["id_followup"]
        tambah(f"jadwal:{fid}", _tgl(f["tgl_jadwal"]), f"Jadwal follow-up bulan {b}", fid, "Use")
        if _tgl(f["tgl_periksa"]):
            tambah(f"periksa:{fid}", _tgl(f["tgl_periksa"]), f"Periksa follow-up bulan {b}",
                   f"hasil {isi(f['hasil'])}, diinput {_tgl(f['tgl_input']) or kosong}", "Use")
        if _isi(f["hasil"]) is None:
            n = int(ambang["C3"])
            tambah(f"tempo:{fid}", _geser(_tgl(f["tgl_jadwal"]), days=n), f"Jatuh tempo follow-up bulan {b}",
                   f"jadwal + {n} hari, hasil belum ada", "Use", "batas")

    # Outcome, atau batas outcome kalau belum ada
    tgl_outcome = None
    if len(oc):
        o = oc.iloc[0]
        tgl_outcome = _tgl(o["tgl_outcome"])
        tambah("outcome", tgl_outcome, "Outcome", f"{isi(o['hasil'])}, diinput {_tgl(o['tgl_input']) or kosong}", "Use")
    elif _tgl(e["tgl_mulai"]):
        n = int(ambang["C2"])
        tambah("batas_outcome", _geser(_tgl(e["tgl_mulai"]), days=n), f"Batas outcome hari ke-{n}",
               "outcome belum dicatat", "Use", "batas")

    # Batas arsip: outcome ada dan lifecycle belum Arsip
    if tgl_outcome and e["lifecycle_status"] != "Arsip":
        n = int(ambang["R3"])
        tambah("batas_arsip", _geser(tgl_outcome, days=n), f"Batas arsip hari ke-{n} setelah outcome",
               f"lifecycle {e['lifecycle_status']}", "Archive", "batas")

    # Batas retensi: hanya untuk record yang sudah diarsipkan atau siap musnah
    if e["lifecycle_status"] in ("Arsip", "Siap Musnah"):
        kunjungan = max(t for t in [_tgl(e["tgl_diagnosis"]), _tgl(e["tgl_mulai"]), tgl_outcome]
                        + [_tgl(x) for x in fu["tgl_periksa"]] if t)
        n = int(ambang["R4"])
        tambah("batas_retensi", _geser(kunjungan, years=n), f"Batas retensi {n} tahun",
               f"kunjungan terakhir {kunjungan}, berita acara {isi(e['berita_acara'])}", "Destroy", "batas")

    # Tempelkan temuan ke titiknya
    for _, t in tm.iterrows():
        dasar = PETA_ATURAN.get(t["kode"], "diagnosis")
        kunci = dasar
        if dasar in ("periksa", "tempo"):
            kunci = _kunci_followup(dasar, t["detail"], fu)
            if kunci and kunci not in titik:  # mis. periksa belum ada tanggalnya -> pakai jadwalnya
                kunci = "jadwal:" + kunci.split(":", 1)[1]
            kunci = kunci or dasar
        if kunci not in titik:  # titik tujuan tidak ada: buat titik tanpa tanggal supaya temuan tetap tampil
            peristiwa, tahap, jenis = _TITIK_CADANGAN[dasar]
            tambah(kunci, None, peristiwa, "tanggal tidak tersedia", tahap, jenis)
        titik[kunci]["temuan"].append({"kode": t["kode"], "detail": t["detail"], "steward": t["steward"]})

    # Warna dan urutan
    hasil = list(titik.values())
    for x in hasil:
        if x["temuan"]:
            x["warna"] = "merah"
        elif x["jenis"] == "batas" and (x["tanggal"] is None or x["tanggal"] >= tgl):
            x["warna"] = "abu"
        else:
            x["warna"] = "hijau"
    return sorted(hasil, key=lambda x: (x["tanggal"] is None, x["tanggal"] or ""))


def katalog_aturan(db=DB):
    """Katalog 15 aturan, teks kondisi sudah diisi ambang dan satuannya."""
    df = _sql("SELECT * FROM aturan", db=db)
    return _isi_kondisi(df)


def daftar_tabel(db=DB):
    """Daftar tabel dan view di SQLite beserta jumlah baris dan kolomnya."""
    obj = _sql("""SELECT name AS nama, type AS jenis FROM sqlite_master
                  WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%'
                  ORDER BY type, name""", db=db)
    jumlah, kolom = [], []
    for nama in obj["nama"]:
        jumlah.append(int(_sql(f'SELECT COUNT(*) AS n FROM "{nama}"', db=db)["n"][0]))
        kolom.append(", ".join(_sql(f"SELECT name FROM pragma_table_info('{nama}')", db=db)["name"]))
    obj["jumlah_baris"] = jumlah
    obj["kolom"] = kolom
    return obj
