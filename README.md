# **TB-CMS Web Interface**

# **Deskripsi Sistem**

**TB-CMS (Tuberculosis Case Management System)** adalah platform manajemen kasus Tuberkulosis berbasis web yang dirancang untuk mendukung pemantauan, pencatatan, dan analisis rekam medis pasien TB secara longitudinal. Sistem ini membantu tenaga kesehatan (Nakes) dan administrator dalam mengelola rantai perawatan pasien mulai dari skrining awal, diagnosis, rekam pengobatan, hingga integrasi pemrosesan data medis berstandar klinis.

# **🌟 Fitur Utama**

* **Role-Based Access Control (RBAC):** Otentikasi dan otorisasi bertingkat yang membedakan hak akses operasional harian untuk Tenaga Kesehatan (*Nakesmode*) dan kendali penuh konfigurasi sistem untuk Administrator (*Godmode*).  
* **Filter Longitudinal Berbasis Pasien:** Penelusuran riwayat medis pasien secara riil berbasis timeline longitudinal, memudahkan evaluasi kepatuhan minum obat, perubahan status dahak/bakteriologis, dan penyesuaian regimen medis dari waktu ke waktu.  
* **Simulated ETL (Extract, Transform, Load):** Fitur pemrosesan data otomatis untuk mengonversi data mentah rekam medis menjadi agregat analitik dan format terstruktur yang siap dianalisis tanpa mengganggu kinerja basis data utama.  
* **Responsive UI dengan Offcanvas Sidebar:** Antarmuka modern berstandar aksesibilitas tinggi menggunakan bilah navigasi *offcanvas* yang responsif di berbagai ukuran layar (desktop, tablet, maupun *smartphone*).

# **🛠️ Tech Stack**

| Komponen | Teknologi | Keterangan |
| :---- | :---- | :---- |
| **Backend Language** | Python 3.10+ | Bahasa pemrograman utama logika bisnis |
| **Web Framework** | Flask | Micro-framework untuk pengolahan *routing* dan sesi |
| **Database Engine** | SQLite3 | Penyimpanan relasional lokal yang ringan dan cepat |
| **Data Processing** | Pandas | Modul analisis dan transformasi data kuantitatif / ETL |
| **Frontend Framework** | Bootstrap 5 | Kerangka kerja UI responsif dan pemodelan komponen |

# **📂 Struktur Direktori Utama**

```
tb-cms/
├── app_flask.py          # Entry point utama aplikasi Flask & konfigurasi route
├── core/
│   └── queries.py        # Abstraksi query SQL dan fungsi manipulasi data
├── templates/
│   ├── base.html         # Skeleton Layout utama (termasuk Offcanvas Sidebar)
│   ├── dashboard.html    # Tampilan visualisasi data & matriks pasien
│   └── longitudinal.html # Antarmuka pemantauan rekam medis pasien
└── static/
    ├── css/              # Kustomisasi gaya visual
    └── js/               # Skrip interaktivitas antarmuka
```

# **🚀 Cara Menjalankan**

## **1\. Persiapan Lingkungan (Prerequisites)**

Pastikan Python versi 3.10 atau yang lebih baru telah terpasang di sistem Anda.

## **2\. Kloning Repositori & Navigasi**

```
git clone https://github.com/example/tb-cms.git
cd tb-cms
```

## **3\. Buat dan Aktifkan Virtual Environment**

* **Linux/macOS:**

```
python3 -m venv venv
source venv/bin/activate
```

* **Windows:**

```
python -m venv venv
venv\Scripts\activate
```

## **4\. Install Dependensi**

```
pip install flask pandas
```

## **5\. Jalankan Aplikasi**

```
python app_flask.py
```

Buka peramban (browser) dan akses alamat `http://127.0.0.1:5000/`.

# **🔒 Panduan Akses Role**

Sistem menyediakan dua tingkatan hak akses untuk pengujian dan operasional:

## **1\. Nakesmode (Tenaga Kesehatan)**

* **Akses:** Dipilih langsung melalui menu *dropdown* peran pada halaman otentikasi/header utama.  
* **Wewenang:** Menginput data rekam medis harian, melihat daftar pasien, memantau grafik longitudinal, dan memperbarui status pengobatan pasien.

## **2\. Godmode (Administrator Utama)**

* **Akses:** Diaktifkan melalui tautan tersembunyi (*secret link*) di bagian paling bawah (*footer*) halaman web.  
* **Otentikasi PIN:** Masukkan PIN saat jendela verifikasi muncul.  
* **Wewenang:** Akses penuh ke seluruh direktori data, eksekusi pembersihan/reset database, simulasi ETL manual, serta manajemen peran pengguna.

