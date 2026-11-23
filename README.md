# TB-CMS Web Interface

All data in this project is synthetic. No real patient data is used.

Seluruh data dalam proyek ini adalah data sintetis. Tidak ada data pasien asli yang digunakan.

**Live demo:** https://leund.pythonanywhere.com/

## English

### Overview

TB-CMS is a Flask web application for longitudinal monitoring and management of synthetic tuberculosis case data. It supports health-worker and administrator access, batch processing, and storage of monitoring results.

### Features

- Longitudinal patient monitoring and status summaries.
- Separate health-worker and administrator views.
- Batch processing from the `masuk/` folder.
- SQLite storage for run results and audit records.
- Responsive interface built with Bootstrap.

### Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.10+ |
| Web framework | Flask |
| Database | SQLite |
| Data processing | Pandas |
| Environment | python-dotenv |
| Frontend | Bootstrap 5 |

### Directory Structure

```text
tb_cms/
├── app_flask.py
├── core/
│   ├── pemantauan.py
│   ├── queries.py
│   └── sinkron.py
├── engine/
│   ├── loader.py
│   ├── rules.py
│   └── runner.py
├── templates/
├── static/
├── data/
├── masuk/
├── tools/
│   └── siapkan_demo.py
└── pythonanywhere_wsgi.py.example
```

`engine/` loads data and configuration, executes the rule engine, and stores monitoring findings. It implements 15 data-governance rules from the `ATURAN` registry in `engine/rules.py`.

### Local Setup

Requirements: Python 3.10 or newer.

```bash
git clone https://github.com/leuND/tb_cms.git
cd tb_cms

python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
python tools/siapkan_demo.py
python app_flask.py
```

Open `http://127.0.0.1:5000/`. The development server is for local use only; production deployment must use the platform's WSGI configuration with debug disabled.

### Environment and Security

Copy `.env.example` to `.env` and set the variables locally. `.env` must not be committed.

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | Required Flask session key. |
| `ADMIN_PASSWORD` | Optional shared administrator password; leaving it empty disables admin login. |
| `TBCMS_DB` | Optional SQLite path. Default: `data/tb_cms.sqlite`. |
| `TBCMS_MASUK` | Optional incoming-batch folder. Default: `masuk/`. |

The application loads `.env` with `load_dotenv()` and reads `ADMIN_PASSWORD` and `SECRET_KEY` from process environment variables. It does not use a hardcoded PIN or "Godmode" value. `app_flask.py` raises an error when `SECRET_KEY` is missing.

Generate a session key locally:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

PythonAnywhere deployment is described in the Indonesian setup section below.

### Role Access

- **Health worker:** Views summaries and episode lists available to their facility scope.
- **Administrator:** Uses `ADMIN_PASSWORD` to access administrative functions. If the variable is empty, administrator login is disabled.

### Project Info

- Course project for Data Management, Medical Technology, ITS, completed by a team of four.
- My contribution: the rule engine and the Flask web application.
- This is a prototype, not a production system.

## Bahasa Indonesia

### Ringkasan

TB-CMS adalah aplikasi web berbasis Flask untuk pemantauan longitudinal dan pengelolaan data kasus Tuberkulosis sintetis. Sistem mendukung akses Tenaga Kesehatan dan Administrator, pemrosesan batch, serta penyimpanan hasil pemantauan.

### Fitur

- Pemantauan status dan indikator longitudinal pasien sintetis.
- Pemisahan tampilan Tenaga Kesehatan dan Administrator.
- Pemrosesan batch dari folder `masuk/`.
- Penyimpanan hasil run dan audit di SQLite.
- Antarmuka responsif menggunakan Bootstrap.

### Teknologi

| Komponen | Teknologi |
|---|---|
| Bahasa | Python 3.10+ |
| Framework web | Flask |
| Basis data | SQLite |
| Pemrosesan data | Pandas |
| Environment | python-dotenv |
| Frontend | Bootstrap 5 |

### Struktur Direktori

```text
tb_cms/
├── app_flask.py
├── core/
│   ├── pemantauan.py
│   ├── queries.py
│   └── sinkron.py
├── engine/
│   ├── loader.py
│   ├── rules.py
│   └── runner.py
├── templates/
├── static/
├── data/
├── masuk/
├── tools/
│   └── siapkan_demo.py
└── pythonanywhere_wsgi.py.example
```

`engine/` memuat data dan konfigurasi, menjalankan engine aturan, serta menyimpan temuan pemantauan. Folder ini mengimplementasikan 15 aturan tata kelola data dari kamus `ATURAN` di `engine/rules.py`.

### Menjalankan Secara Lokal

Persyaratan: Python 3.10 atau lebih baru.

```bash
git clone https://github.com/leuND/tb_cms.git
cd tb_cms

python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
python tools/siapkan_demo.py
python app_flask.py
```

Buka `http://127.0.0.1:5000/`. Server development hanya untuk penggunaan lokal; deployment produksi harus memakai konfigurasi WSGI platform dengan debug dimatikan.

### Environment dan Keamanan

Salin `.env.example` menjadi `.env`, lalu isi variabel secara lokal. `.env` tidak boleh di-commit.

| Variabel | Keterangan |
|---|---|
| `SECRET_KEY` | Wajib; kunci sesi Flask. |
| `ADMIN_PASSWORD` | Opsional; password bersama Administrator. Kosongkan untuk menonaktifkan login Administrator. |
| `TBCMS_DB` | Opsional; path SQLite. Default: `data/tb_cms.sqlite`. |
| `TBCMS_MASUK` | Opsional; folder batch masuk. Default: `masuk/`. |

Aplikasi memuat `.env` melalui `load_dotenv()` dan membaca `ADMIN_PASSWORD` serta `SECRET_KEY` dari environment process. Tidak ada PIN atau nilai "Godmode" yang ditulis langsung di kode. `app_flask.py` menolak startup apabila `SECRET_KEY` tidak tersedia.

Hasilkan kunci sesi secara lokal:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### Deploy PythonAnywhere

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

4. Buat `.env` dari `.env.example`, lalu isi `SECRET_KEY` dan variabel yang diperlukan. Untuk PythonAnywhere, path SQLite dan folder masuk dapat diarahkan ke direktori akun:

```text
TBCMS_DB=/home/USERNAME/tb_cms/data/tb_cms.sqlite
TBCMS_MASUK=/home/USERNAME/tb_cms/masuk
```

5. Di konfigurasi web app PythonAnywhere:
   - Pilih versi Python yang sesuai dengan virtualenv.
   - Isi virtualenv: `/home/USERNAME/tb_cms/venv`.
   - Edit WSGI configuration file menggunakan `pythonanywhere_wsgi.py.example`.
   - Ganti `USERNAME` dengan username PythonAnywhere.
   - Klik **Reload**.

Disk akun PythonAnywhere persisten, tetapi kuota disk dan lokasi SQLite tetap perlu diperhatikan. Jalankan `python tools/siapkan_demo.py` hanya untuk reset database demo karena proses ini membangun ulang database.

### Akses Peran

- **Tenaga Kesehatan:** Membuka ringkasan dan daftar episode sesuai cakupan faskes.
- **Administrator:** Menggunakan `ADMIN_PASSWORD` untuk membuka fungsi administratif. Jika variabel kosong, login Administrator dinonaktifkan.

### Informasi Proyek

- Proyek mata kuliah Manajemen Data, Teknologi Kedokteran ITS, dikerjakan oleh tim beranggotakan 4 orang.
- Kontribusi saya: engine aturan dan aplikasi web Flask.
- Ini adalah prototipe, bukan sistem produksi.
