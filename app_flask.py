import hmac
import os
import secrets
import sys
from datetime import date
from functools import wraps
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session, flash

# Setup path biar bisa import folder core
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from core import pemantauan, queries as q, sinkron

# Rahasia dibaca dari .env (lihat .env.example), tidak pernah ditulis di kode
load_dotenv(ROOT / ".env")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")  # kosong = login admin dinonaktifkan

app = Flask(__name__)
# Tanpa SECRET_KEY: kunci acak sementara, sesi hilang setiap server restart
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

def admin_required(fungsi):
    """Route khusus admin. Dicek di server, bukan hanya disembunyikan di menu:
    nakes yang membuka URL-nya langsung dialihkan ke Ringkasan dengan banner peringatan."""
    @wraps(fungsi)
    def terbungkus(*args, **kwargs):
        if session.get('role') != 'admin':
            flash("Akses terbatas. Halaman ini khusus untuk Admin / Data Steward.", "warning")
            return redirect(url_for('ringkasan'))
        return fungsi(*args, **kwargs)
    return terbungkus

@app.before_request
def set_default_tanggal():
    if request.endpoint == 'static':   # berkas CSS/gambar tidak perlu menyentuh database
        return
    # Tanggal aktif harus punya run. Kalau belum (mis. database baru di-reset),
    # pakai 2026-10-31 atau run terakhir; kalau belum ada run sama sekali, kosongkan.
    tgl_list = q.daftar_tgl_pantau()
    if session.get('tgl') not in tgl_list:
        if tgl_list:
            session['tgl'] = "2026-10-31" if "2026-10-31" in tgl_list else tgl_list[-1]
        else:
            session.pop('tgl', None)
    # Pengunjung baru = nakes dari faskes pertama. Admin hanya lewat password.
    if 'role' not in session:
        session['role'] = 'nakes'
    if session['role'] == 'nakes' and session.get('faskes_akses') not in q.daftar_faskes():
        session['faskes_akses'] = q.daftar_faskes()[0]

@app.context_processor
def inject_global_data():
    # Bawa data ini ke semua file HTML tanpa harus di-pass satu-satu
    tgl = session.get('tgl')
    return {
        'is_admin': session.get('role') == 'admin',
        'daftar_faskes': q.daftar_faskes(),
        'tgl_aktif': tgl,
        'hari_ini': date.today().isoformat(),     # batas atas kalender
        'run_aktif': q.info_run(tgl) if tgl else None,
        # Batch di masuk/ yang menunggu diproses (hanya dihitung untuk admin)
        'batch_menunggu': (sum(b['status'] == 'menunggu' for b in sinkron.daftar_batch())
                           if session.get('role') == 'admin' else 0),
    }

@app.route('/set_tanggal', methods=['POST'])
def set_tanggal():
    # Kalender di sidebar. Tanggal yang sudah punya run: tampilkan hasil tersimpan.
    # Tanggal baru: engine dijalankan sekali, hasilnya disimpan sebagai run baru.
    try:
        tgl = date.fromisoformat(request.form.get('tgl', ''))
    except ValueError:
        flash("Format tanggal tidak valid.", "danger")
        return redirect(request.referrer or url_for('ringkasan'))
    if tgl > date.today():
        flash(f"Tanggal pantau {tgl.isoformat()} ditolak: tidak boleh setelah hari ini.", "danger")
        return redirect(request.referrer or url_for('ringkasan'))
    tgl = tgl.isoformat()
    if tgl not in q.daftar_tgl_pantau():
        r = pemantauan.jalankan_pemantauan(tgl)
        flash(f"Run baru untuk {tgl}: {r['Sinambung']} Sinambung, {r['Perlu Cek']} Perlu Cek, "
              f"{r['Terputus']} Terputus.", "info")
    session['tgl'] = tgl
    return redirect(request.referrer or url_for('ringkasan'))

@app.route('/')
def index():
    # Halaman utama selalu ke Ringkasan. Admin hanya lewat password (/login_admin).
    return redirect(url_for('ringkasan'))

@app.route('/nakesmode')
def nakesmode():
    session['role'] = 'nakes'
    session['faskes_akses'] = q.daftar_faskes()[0]
    flash(f"Mode Nakes aktif. Data difilter: pasien yang pernah singgah di {session['faskes_akses']}.", "info")
    return redirect(url_for('ringkasan'))


@app.route('/proses_masuk', methods=['POST'])
@admin_required
def proses_masuk():
    # Simulasi sinkronisasi (data uji): proses batch siap di folder masuk/ lewat core/sinkron.py
    hasil = sinkron.proses_folder_masuk(tgl_aktif=session.get('tgl'))
    if not hasil['batch']:
        flash("Tidak ada batch baru di folder masuk/.", "info")
    for b in hasil['batch']:
        if b['status'] == 'loaded':
            flash(f"{b['batch_id']}: {b['jumlah_baris']} baris dimuat, episode baru/berubah: "
                  f"{', '.join(b['episode']) or '-'}.", "success")
        else:
            flash(f"{b['batch_id']} {b['status']}: {b['pesan']}", "danger")
    seb, ses = hasil['ringkasan_sebelum'], hasil['ringkasan_sesudah']
    if seb and ses and seb != ses:
        ubah = ", ".join(f"{s} {seb[s]} → {ses[s]}" for s in q.STATUS)
        flash(f"Ringkasan {session.get('tgl')}: {ubah}.", "info")
    return redirect(request.referrer or url_for('ringkasan'))

@app.route('/ganti_faskes', methods=['POST'])
def ganti_faskes():
    # Menangkap pilihan dari dropdown Nakes
    faskes_baru = request.form.get('faskes')
    if session.get('role') == 'nakes' and faskes_baru in q.daftar_faskes():
        session['faskes_akses'] = faskes_baru
        flash(f"Faskes aktif diubah menjadi: {faskes_baru}", "info")
    return redirect(request.referrer or url_for('ringkasan'))

@app.route('/login_admin', methods=['POST'])
def login_admin():
    # Satu password bersama untuk tampilan teknis (tanpa akun)
    if not ADMIN_PASSWORD:
        flash("Login admin dinonaktifkan: ADMIN_PASSWORD belum diisi di .env.", "danger")
        return redirect(url_for('ringkasan'))
    password = request.form.get('password', '')
    # compare_digest: waktu perbandingan konstan, tidak membocorkan berapa karakter yang cocok
    if hmac.compare_digest(password.encode(), ADMIN_PASSWORD.encode()):
        session['role'] = 'admin'
        session.pop('faskes_akses', None) 
        flash("Akses Admin diberikan. Menu teknis terbuka.", "success")
    else:
        flash("Password salah. Akses ditolak.", "danger")
    return redirect(url_for('ringkasan'))

@app.route('/ringkasan')
def ringkasan():
    tgl = session.get('tgl')
    if not tgl:
        return render_template('kosong.html') # Kalau DB benar-benar kosong
    
    faskes_akses = session.get('faskes_akses')  # None untuk admin
    r = q.ringkasan(tgl, faskes_akses=faskes_akses)
    kesimpulan = q.kesimpulan_tahap(tgl, faskes_akses=faskes_akses)
    # Pasangan (label, angka) untuk dua baris statistik
    stat_status = [("Total Episode", r['total'])] + [(s, r['status'][s]) for s in q.STATUS]
    stat_indikator = [(i, r['indikator'][i]) for i in q.INDIKATOR]
    return render_template('ringkasan.html',
                           tgl=tgl,
                           kesimpulan=kesimpulan,
                           stat_status=stat_status,
                           stat_indikator=stat_indikator)



@app.route('/episode')
def episode():
    tgl = session.get('tgl')
    if not tgl:
        return redirect(url_for('ringkasan'))

    f_status = request.args.get('status', 'Semua')
    f_indikator = request.args.get('indikator', 'Semua')
    f_tahap = request.args.get('tahap', 'Semua')
    
    # Ambil faskes dari session (Jika admin, nilainya None)
    faskes_akses = session.get('faskes_akses')

    # Oper parameter faskes_akses ke fungsi driver kita
    daftar_df = q.daftar_episode(
        tgl,
        status=None if f_status == 'Semua' else f_status,
        indikator=None if f_indikator == 'Semua' else f_indikator,
        tahap=None if f_tahap == 'Semua' else f_tahap,
        faskes_akses=faskes_akses
    )
    
    # Konversi DataFrame ke list of dict agar mudah di-loop di HTML (mirip struct array)
    daftar = daftar_df.to_dict(orient='records')
    # Jumlah seluruh episode yang boleh dilihat (tanpa filter), untuk "Menampilkan X dari Y"
    total_semua = len(q.daftar_episode(tgl, faskes_akses=faskes_akses))

    # Cek apakah ada episode yang dipilih lewat parameter URL ?id=EXX
    selected_id = request.args.get('id')
    detail_data = None
    timeline_data = None

    if selected_id and not q.boleh_akses(selected_id, faskes_akses):
        flash(f"Episode {selected_id} bukan milik pasien yang pernah singgah di {faskes_akses}.", "warning")
        selected_id = None
    if selected_id:
        detail_data = q.detail_episode(selected_id, tgl)
        if detail_data:
            timeline_data = q.timeline_episode(selected_id, tgl)

    # Pilihan untuk tiga filter ("Semua ..." = tanpa filter)
    def opsi(semua, daftar_nilai):
        return [{'nilai': 'Semua', 'teks': semua}] + [{'nilai': n, 'teks': n} for n in daftar_nilai]

    konteks = dict(
        tgl=tgl,
        f_status=f_status, f_indikator=f_indikator, f_tahap=f_tahap,
        opsi_status=opsi('Semua status', q.STATUS),
        opsi_indikator=opsi('Semua indikator', q.INDIKATOR),
        opsi_tahap=opsi('Semua tahap', q.TAHAP),
    )
    if detail_data:
        a = detail_data['angka']
        hari = a['hari_pengobatan']
        stat_episode = [("Hari Pengobatan", '—' if hari is None else hari), ("Follow-up", a['followup']),
                        ("Temuan", a['temuan']), ("Rujukan", a['rujukan'])]
        return render_template(
            'episode_detail.html', detail=detail_data, timeline=timeline_data, stat_episode=stat_episode,
            temuan=detail_data['temuan'].to_dict(orient='records'),
            audit=detail_data['audit'].to_dict(orient='records'), **konteks)
    return render_template('episode_daftar.html', daftar=daftar, total_semua=total_semua, **konteks)

@app.route('/aturan')
@admin_required
def aturan():
    df_aturan = q.katalog_aturan()
    kolom = ["kode", "indikator", "kondisi", "tahap", "keparahan", "steward", "aspek", "dasar"]
    data_aturan = df_aturan[kolom].to_dict(orient='records')
    return render_template('aturan.html', aturan_list=data_aturan)

@app.route('/data_skema')
@admin_required
def data_skema():
    df_tabel = q.daftar_tabel()
    data_tabel = df_tabel.to_dict(orient='records')
    return render_template('data_skema.html', tabel_list=data_tabel)

if __name__ == '__main__':
    app.run(debug=True)