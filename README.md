# TB-CMS Web Interface

TB-CMS (Tuberculosis Case Management System) adalah aplikasi web berbasis Flask untuk pemantauan dan pengelolaan kasus Tuberkulosis secara longitudinal.

Sistem mendukung pembagian akses Tenaga Kesehatan (Nakes) dan Administrator, penyaringan pasien, pemrosesan batch sintetis, serta penyimpanan hasil pemantauan. Semua data dalam repositori merupakan data sintetis.

## Fitur

- Pemantauan status dan indikator longitudinal pasien.
- Pemisahan tampilan Nakes dan Administrator.
- Pemrosesan batch dari folder `masuk/`.
- Penyimpanan hasil run dan audit ke SQLite.
- Antarmuka responsif menggunakan Bootstrap.

## Teknologi

| Komponen | Teknologi |
|---|---|
| Bahasa | Python 3.10+ |
| Web framework | Flask |
| Basis data | SQLite |
| Pemrosesan data | Pandas |
| Environment | python-dotenv |
| Frontend | Bootstrap 5 |

## Struktur

```text
tb_cms/
├── app_flask.py
├── core/
│   ├── pemantauan.py
│   ├── queries.py
│   └── sinkron.py
├── engine/
├── templates/
├── static/
├── data/
├── masuk/
├── tools/
│   └── siapkan_demo.py
└── pythonanywhere_wsgi.py.example
```

## Menjalankan Secara Lokal

Persyaratan: Python 3.10 atau lebih baru.

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
python tools/siapkan_demo.py
python app_flask.py
```

Buka `http://127.0.0.1:5000/`.

Server development hanya boleh digunakan secara lokal. Jalankan Flask dengan `debug=False`; deployment produksi harus memakai WSGI server/platform.

## Konfigurasi Lingkungan

Rahasia dibaca dari environment atau file `.env`. Jangan menyimpan nilai rahasia di repository.

| Variabel | Keterangan |
|---|---|
| `SECRET_KEY` | Wajib; kunci sesi Flask. |
| `ADMIN_PASSWORD` | Opsional; kosongkan untuk menonaktifkan login Administrator. |
| `TBCMS_DB` | Opsional; path SQLite. Default: `data/tb_cms.sqlite`. |
| `TBCMS_MASUK` | Opsional; folder batch masuk. Default: `masuk/`. |

Hasilkan kunci sesi acak:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

## Deploy PythonAnywhere

1. Clone repository ke `/home/USERNAME/tb_cms`.
2. Buat virtualenv dan instal dependency:

```bash
cd ~/tb_cms
python3.13 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

3. Buat database demo sintetis:

```bash
python tools/siapkan_demo.py
```

4. Buat `.env` dari `.env.example`, lalu isi `SECRET_KEY` dan variabel yang diperlukan:

```bash
cp .env.example .env
nano .env
```

Contoh path:

```text
TBCMS_DB=/home/USERNAME/tb_cms/data/tb_cms.sqlite
TBCMS_MASUK=/home/USERNAME/tb_cms/masuk
```

5. Di konfigurasi web app PythonAnywhere:
   - Pilih Python versi yang sesuai dengan virtualenv.
   - Isi virtualenv: `/home/USERNAME/tb_cms/venv`.
   - Edit WSGI configuration file menggunakan `pythonanywhere_wsgi.py.example`.
   - Ganti `USERNAME` dengan username PythonAnywhere.
   - Klik **Reload**.

Disk akun PythonAnywhere bersifat persisten, tetapi tetap perlu mempertimbangkan kuota disk dan lokasi file SQLite. Menjalankan `python tools/siapkan_demo.py` akan menghapus dan membangun ulang database demo; jalankan hanya saat reset database memang diperlukan.

## Peran

### Nakes

Tenaga kesehatan dapat membuka ringkasan dan daftar episode sesuai cakupan faskesnya.

### Administrator

Login admin memerlukan `ADMIN_PASSWORD`. Jika variabel ini kosong, login Administrator dinonaktifkan.
