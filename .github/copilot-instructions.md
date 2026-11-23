# Petunjuk untuk Copilot: TB-CMS

Monitoring layer READ-ONLY untuk kesinambungan data episode pengobatan TB (Manajemen Data, Teknologi Kedokteran ITS). Bukan sistem klinis. Semua data sintetis. Tanpa AI/ML.

## Arsitektur (jangan dicampur)
- `engine/`: 15 aturan (`rules.py`), `loader.py`, `runner.py`. Satu-satunya tempat status dan aturan dihitung.
- `core/`: lapisan layanan. `queries.py` (semua query ke SQLite), `pemantauan.py` (jalankan engine), `sinkron.py` (satu-satunya penulis tabel sumber selain `tools/import_sqlite.py`). Tidak boleh mengimpor Flask.
- `app_flask.py` dan `templates/`: tampilan. Route hanya memanggil fungsi di `core/`. Tanpa SQL dan tanpa logika aturan di route atau template.
- `config/rules_catalog.csv`: sumber kebenaran aturan dan ambang. Ambang tidak ditulis di kode.
- `data/*.csv`: data sumber sintetis. `masuk/`: batch simulasi sinkronisasi.

## Keputusan yang tidak boleh diubah tanpa izin
- Status = jumlah KODE ATURAN BERBEDA yang kena pada satu episode: 0 Sinambung, 1 Perlu Cek, 2 atau lebih Terputus. Dua temuan C3 pada satu episode tetap 1 aturan.
- Tanggal pantau selalu parameter. Jangan pakai `today()` di engine.
- Tampilan read-only terhadap tabel sumber. Tidak ada akun; mode nakes default, admin lewat satu password dari `.env` (`ADMIN_PASSWORD`, `SECRET_KEY`). Jangan menulis password di kode atau repo.
- NIK disimpan apa adanya sebagai TEXT. Jangan di-hash.
- Jumlah aturan tetap 15.

## Pola aturan baru
Satu fungsi per aturan: `fungsi(data, cfg, tgl_pantau)` mengembalikan DataFrame kolom `id_episode, kode, detail` (helper `_temuan`). Daftarkan di dict `ATURAN`. Data uji: tambah episode BARU (kena, kontrol, batas), jangan ubah episode lama.

## Jebakan yang pernah terjadi
- Merge tabel anak (followups, audit_logs) ke episodes menggandakan baris. Pakai `isin` atau `groupby`.
- Rantai `a > b > c` tidak jalan pada Series pandas.
- NIK dibaca sebagai angka menjadi notasi ilmiah: selalu `dtype=str`.
- CSV: edit di VS Code, tanggal `YYYY-MM-DD`, baca dengan `encoding="utf-8-sig"`. Jangan Excel.
- Nama kolom `status_sinkron` sudah dipakai `salinan_sitb`; kolom staging memakai `status_staging`.

## Cara menjalankan dan memeriksa
```
pip install -r requirements.txt
python tools/siapkan_demo.py          # bangun ulang data/tb_cms.sqlite, nol run
python app_flask.py                   # http://127.0.0.1:5000
python tests/cek_core.py              # harus: "Semua cek lolos."
```
Angka demo (Sinambung/Perlu Cek/Terputus), sebelum batch_001: 30 Okt 13/15/2, 31 Okt 12/16/2, 4 Nov 10/17/3, 10 Nov 9/18/3. Setelah batch_001 dimuat: 14/15/2, 13/16/2, 11/17/3, 10/18/3. Perubahan yang menggeser angka ini harus disebut dan dijelaskan.

## Gaya
Bahasa Indonesia, kalimat pendek. Komentar kode hanya untuk alasan, bukan apa yang sudah jelas. Jangan menambah fitur atau refactor di luar yang diminta.
