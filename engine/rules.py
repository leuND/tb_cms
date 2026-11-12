"""rules.py: satu fungsi per aturan.

Setiap fungsi menerima (data, cfg, tgl_pantau):
  data       = dict tabel dari loader.load_data()
  cfg        = dict ambang dari loader.load_cfg()
  tgl_pantau = pd.Timestamp, tanggal pemantauan
dan mengembalikan DataFrame temuan dengan kolom: id_episode, kode, detail.
"""
import pandas as pd

KOLOM_TEMUAN = ["id_episode", "kode", "detail"]


def _temuan(id_episode, kode, detail):
    """Bentuk DataFrame temuan standar."""
    return pd.DataFrame({"id_episode": list(id_episode), "kode": kode,
                         "detail": list(detail)}, columns=KOLOM_TEMUAN)


def C1_field_wajib_kosong(data, cfg, tgl_pantau):
    ep = data["episodes"].merge(data["pasien"], on="id_pasien", how="left")
    wajib = ["nik", "tgl_lahir", "jenis_kelamin", "tgl_diagnosis",
             "metode_diagnosis", "tgl_mulai", "paduan"]
    kosong = ep[wajib].isna()
    kena = ep[kosong.any(axis=1)]
    detail = [", ".join(k for k in wajib if kosong.loc[i, k]) + " kosong"
              for i in kena.index]
    return _temuan(kena["id_episode"], "C1", detail)


def C2_tanpa_outcome(data, cfg, tgl_pantau):
    ep = data["episodes"]
    sudah_outcome = ep["id_episode"].isin(data["outcomes"]["id_episode"])
    hari = (tgl_pantau - ep["tgl_mulai"]).dt.days
    kena = ep[~sudah_outcome & (hari > cfg["C2"])]
    detail = [f"hari ke-{int(hari[i])} tanpa outcome" for i in kena.index]
    return _temuan(kena["id_episode"], "C2", detail)


def C3_followup_tanpa_hasil(data, cfg, tgl_pantau):
    fu = data["followups"]
    jatuh_tempo = fu["tgl_jadwal"] + pd.Timedelta(days=cfg["C3"])
    kena = fu[fu["hasil"].isna() & (jatuh_tempo < tgl_pantau)]
    detail = [f"follow-up bulan {fu.loc[i, 'bulan']} (jadwal "
              f"{fu.loc[i, 'tgl_jadwal']:%Y-%m-%d}) belum ada hasil"
              for i in kena.index]
    return _temuan(kena["id_episode"], "C3", detail)


def K1_mulai_sebelum_diagnosis(data, cfg, tgl_pantau):
    ep = data["episodes"]
    selisih = (ep["tgl_mulai"] - ep["tgl_diagnosis"]).dt.days
    kena = ep[selisih < -cfg["K1"]]
    detail = [f"mulai {abs(int(selisih[i]))} hari sebelum diagnosis"
              for i in kena.index]
    return _temuan(kena["id_episode"], "K1", detail)


def K2_sembuh_tapi_positif(data, cfg, tgl_pantau):
    fu = data["followups"].dropna(subset=["hasil"]).copy()
    fu["bulan"] = fu["bulan"].astype(int)
    terakhir = fu.sort_values("bulan").groupby("id_episode").tail(1)
    gabung = data["outcomes"].merge(terakhir, on="id_episode",
                                    suffixes=("_outcome", "_fu"))
    outcome = gabung["hasil_outcome"].str.strip().str.lower()
    hasil_fu = gabung["hasil_fu"].str.strip().str.lower()
    kena = gabung[(outcome == "sembuh") & (hasil_fu == "positif")]
    detail = [f"outcome Sembuh, follow-up terakhir (bulan {b}) Positif"
              for b in kena["bulan"]]
    return _temuan(kena["id_episode"], "K2", detail)


def K3_outcome_terlalu_cepat(data, cfg, tgl_pantau):
    gabung = data["outcomes"].merge(data["episodes"], on="id_episode")
    hari = (gabung["tgl_outcome"] - gabung["tgl_mulai"]).dt.days
    hasil = gabung["hasil"].str.strip().str.lower()
    selesai = hasil.isin(["sembuh", "pengobatan lengkap"])
    kena = gabung[selesai & (hari < cfg["K3"])]
    detail = [f"{gabung.loc[i, 'hasil']} setelah {int(hari[i])} hari pengobatan"
              for i in kena.index]
    return _temuan(kena["id_episode"], "K3", detail)

def K4_kelamin_tgl_diagnosis_tidak_sesuai(data, cfg, tgl_pantau):
    ep = data["episodes"].merge(data["pasien"], on="id_pasien", how="left")
    sitb = data["salinan_sitb"]
    gabung = ep.merge(sitb, on="id_episode", how="inner", suffixes=("_rme", "_sitb"))
    beda_kelamin = gabung["jenis_kelamin_rme"].str.strip().str.upper() != gabung["jenis_kelamin_sitb"].str.strip().str.upper()
    beda_tgl = gabung["tgl_diagnosis_rme"] != gabung["tgl_diagnosis_sitb"]
    kena = gabung[beda_kelamin | beda_tgl]
    detail = []
    for i in kena.index:
        bagian = []
        if beda_kelamin[i]:
            bagian.append(f"jenis kelamin {gabung.loc[i, 'jenis_kelamin_rme']} (RME) vs {gabung.loc[i, 'jenis_kelamin_sitb']} (SITB)")
        if beda_tgl[i]:
            bagian.append(f"tgl diagnosis {gabung.loc[i, 'tgl_diagnosis_rme']:%Y-%m-%d} (RME) vs {gabung.loc[i, 'tgl_diagnosis_sitb']:%Y-%m-%d} (SITB)")
        detail.append("; ".join(bagian))
    return _temuan(kena["id_episode"], "K4", detail)


def K5_jarak_episode_sama_nik_kurang_dari_60_hari(data, cfg, tgl_pantau):
    ep = data["episodes"].merge(data["pasien"], on="id_pasien", how="left")
    ep = ep.sort_values(by=["nik", "tgl_diagnosis"])
    hari = (ep["tgl_diagnosis"] - ep.groupby("nik")["tgl_diagnosis"].shift(1)).dt.days
    kena = ep[(hari < cfg["K5"])]
    detail = [f"{ep.loc[i, 'id_episode']} berjarak {int(hari[i])} hari dengan episode sebelumnya" for i in kena.index]
    return _temuan(kena["id_episode"], "K5", detail)

def T1_input_followup_terlambat(data, cfg, tgl_pantau):
    fu = data["followups"]
    hari = (fu["tgl_input"] - fu["tgl_periksa"]).dt.days
    kena = fu[hari > cfg["T1"]]
    detail = [f"pengisian follow-up id {fu.loc[i, 'id_followup']} terlambat {int(hari[i])} hari" for i in kena.index]
    return _temuan(kena["id_episode"], "T1", detail)
    
def T2_periksa_followup_terlambat(data, cfg, tgl_pantau):
    fu = data["followups"]
    hari = (fu["tgl_periksa"] - fu["tgl_jadwal"]).dt.days
    kena = fu[hari > cfg["T2"]]
    detail = [f"follow-up id {fu.loc[i, 'id_followup']} terlambat diperiksa {int(hari[i])} hari" for i in kena.index]
    return _temuan(kena["id_episode"], "T2", detail)

def T3_input_outcome_terlambat(data, cfg, tgl_pantau):
    out = data["outcomes"]
    hari = (out["tgl_input"] - out["tgl_outcome"]).dt.days
    kena = out[hari > cfg["T3"]]
    detail = [f"pengisian outcome id {out.loc[i, 'id_episode']} terlambat {int(hari[i])} hari" for i in kena.index]
    return _temuan(kena["id_episode"], "T3", detail)

def R1_sumber_petugas_tidak_tercatat(data, cfg, tgl_pantau):
    ep = data["episodes"]
    wajib = ["sumber_sistem", "dibuat_oleh"]
    kosong = ep[wajib].isna()
    kena = ep[kosong.any(axis=1)]
    detail = [", ".join(k for k in wajib if kosong.loc[i, k]) + " kosong"
                  for i in kena.index]
    return _temuan(kena["id_episode"], "R1", detail)

def R2_record_berubah_tanpa_audit(data, cfg, tgl_pantau):
    ep = data["episodes"]
    audit = data["audit_logs"]
    punya_audit = ep["id_episode"].isin(audit["id_episode"])
    kena = ep[~punya_audit & (ep["updated_at"] > ep["created_at"])]
    detail = [f"updated_at {ep.loc[i, 'updated_at']:%Y-%m-%d} lebih besar dari created_at {ep.loc[i, 'created_at']:%Y-%m-%d} tanpa log audit"
              for i in kena.index]
    return _temuan(kena["id_episode"], "R2", detail)

def R3_outcome_lama_belum_arsip(data, cfg, tgl_pantau):
    gabung = data["outcomes"].merge(data["episodes"], on="id_episode")
    hari = (tgl_pantau - gabung["tgl_outcome"]).dt.days
    kena = gabung[(hari > cfg["R3"]) & (gabung["lifecycle_status"] != "Arsip")]
    detail = [f"outcome {int(hari[i])} hari lalu, status {gabung.loc[i, 'lifecycle_status']}" for i in kena.index]
    return _temuan(kena["id_episode"], "R3", detail)

def R4_belum_musnah_25_tahun(data, cfg, tgl_pantau):
    ep = data["episodes"].copy()  # copy: kolom bantu di bawah tidak boleh mengubah data asli
    # Langkah 1: satu tanggal per episode dari tiap tabel anak (Series berindeks id_episode)
    periksa = data["followups"].groupby("id_episode")["tgl_periksa"].max()
    outcome = data["outcomes"].set_index("id_episode")["tgl_outcome"]
    # Langkah 2: map = lookup per baris. Episode tanpa follow-up/outcome jadi NaT
    ep["periksa_terakhir"] = ep["id_episode"].map(periksa)
    ep["tgl_outcome"] = ep["id_episode"].map(outcome)
    # Langkah 3: tanggal paling akhir di antara empat kolom, per baris (NaT diabaikan)
    kolom = ["tgl_diagnosis", "tgl_mulai", "periksa_terakhir", "tgl_outcome"]
    kunjungan = ep[kolom].max(axis=1)
    # Langkah 4: kena kalau kunjungan + 25 tahun sudah lewat dan berita acara kosong
    batas = kunjungan + pd.DateOffset(years=cfg["R4"])
    kena = ep[(batas < tgl_pantau) & ep["berita_acara"].isna()]
    detail = [f"kunjungan terakhir {kunjungan[i]:%Y-%m-%d}, lebih dari {cfg['R4']} tahun, "
              f"berita acara pemusnahan kosong" for i in kena.index]
    return _temuan(kena["id_episode"], "R4", detail)


# Daftar aturan yang dijalankan runner. Tambah aturan baru di sini.
ATURAN = {
    "C1": C1_field_wajib_kosong,
    "C2": C2_tanpa_outcome,
    "C3": C3_followup_tanpa_hasil,
    "K1": K1_mulai_sebelum_diagnosis,
    "K2": K2_sembuh_tapi_positif,
    "K3": K3_outcome_terlalu_cepat,
    "K4": K4_kelamin_tgl_diagnosis_tidak_sesuai,
    "K5": K5_jarak_episode_sama_nik_kurang_dari_60_hari,
    "T1": T1_input_followup_terlambat,
    "T2": T2_periksa_followup_terlambat,
    "T3": T3_input_outcome_terlambat,
    "R1": R1_sumber_petugas_tidak_tercatat,
    "R2": R2_record_berubah_tanpa_audit,
    "R3": R3_outcome_lama_belum_arsip,
    "R4": R4_belum_musnah_25_tahun,
}