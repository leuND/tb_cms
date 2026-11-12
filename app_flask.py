import sys
import time
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify

# Setup path biar bisa import folder core
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from core import pemantauan, queries as q

app = Flask(__name__)
app.secret_key = 'rahasia_tb_cms' # Dibutuhkan untuk session dan flash message

@app.before_request
def set_default_tanggal():
    # Set default tanggal pantau kalau user belum pilih
    tgl_list = q.daftar_tgl_pantau()
    if tgl_list:
        awal = "2026-10-31" if "2026-10-31" in tgl_list else tgl_list[-1]
        if 'tgl' not in session or session['tgl'] not in tgl_list:
            session['tgl'] = awal

@app.context_processor
def inject_global_data():
    # Bawa data ini ke semua file HTML tanpa harus di-pass satu-satu
    return {
        'daftar_tgl': q.daftar_tgl_pantau(),
        'tgl_aktif': session.get('tgl')
    }

@app.route('/set_tanggal', methods=['POST'])
def set_tanggal():
    # Logic dropdown ganti tanggal di sidebar
    tgl = request.form.get('tgl')
    if tgl in q.daftar_tgl_pantau():
        session['tgl'] = tgl
    return redirect(request.referrer or url_for('ringkasan'))

@app.route('/jalankan', methods=['POST'])
def jalankan():
    # Logic tombol "Jalankan pemantauan"
    tgl_baru = request.form.get('tgl_baru')
    if tgl_baru:
        hasil = pemantauan.jalankan_pemantauan(tgl_baru)
        session['tgl'] = tgl_baru
        flash(f"Pemantauan untuk {tgl_baru} berhasil dijalankan!", "success")
    return redirect(request.referrer or url_for('ringkasan'))

@app.route('/')
@app.route('/godmode')
def godmode():
    session['role'] = 'admin'
    # Hapus filter faskes agar admin bisa lihat se-kota
    session.pop('faskes_akses', None) 
    flash("Mode Admin aktif. Menu teknis & Sinkronisasi terbuka.", "success")
    return redirect(url_for('ringkasan'))

@app.route('/nakesmode')
def nakesmode():
    session['role'] = 'nakes'
    # Simulasi Nakes dari PKM Keputih (Nanti bisa diganti dinamis)
    session['faskes_akses'] = 'PKM Keputih' 
    flash("Mode Nakes aktif. Data difilter berdasarkan pasien PKM Keputih.", "info")
    return redirect(url_for('ringkasan'))


@app.route('/simulasi_etl', methods=['POST'])
def simulasi_etl():
    if session.get('role') != 'admin':
        return jsonify({"status": "error", "pesan": "Akses ditolak"}), 403
    
    # 1. Delay buatan seakan-akan sedang sedot API SIMRS
    time.sleep(2.5) 
    
    # 2. Panggil fungsi impor aslimu di sini (opsional untuk sekarang)
    # import_dari_csv_ke_sqlite()
    
    return jsonify({
        "status": "sukses", 
        "pesan": "Sinkronisasi ETL dari SIMRS berhasil dijalankan."
    })

@app.route('/ganti_faskes', methods=['POST'])
def ganti_faskes():
    # Menangkap pilihan dari dropdown Nakes
    faskes_baru = request.form.get('faskes')
    if faskes_baru:
        session['faskes_akses'] = faskes_baru
        flash(f"Faskes aktif diubah menjadi: {faskes_baru}", "info")
    return redirect(request.referrer or url_for('ringkasan'))

@app.route('/login_admin', methods=['POST'])
def login_admin():
    # Menangkap PIN dari pop-up rahasia di layar Nakes
    pin = request.form.get('pin')
    if pin == "admin123":  # Hardcode sederhana untuk prototipe
        session['role'] = 'admin'
        session.pop('faskes_akses', None) 
        flash("Akses Admin diberikan. Menu teknis terbuka.", "success")
    else:
        flash("PIN salah. Akses ditolak.", "danger")
    return redirect(url_for('ringkasan'))

@app.route('/ringkasan')
def ringkasan():
    tgl = session.get('tgl')
    if not tgl:
        return render_template('kosong.html') # Kalau DB benar-benar kosong
    
    r = q.ringkasan(tgl)
    kesimpulan = q.kesimpulan_tahap(tgl)
    return render_template('ringkasan.html', 
                           tgl=tgl, 
                           r=r, 
                           kesimpulan=kesimpulan, 
                           status_list=q.STATUS, 
                           ind_list=q.INDIKATOR)



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

    # Cek apakah ada episode yang dipilih lewat parameter URL ?id=EXX
    selected_id = request.args.get('id')
    detail_data = None
    timeline_data = None

    if selected_id:
        detail_data = q.detail_episode(selected_id, tgl)
        if detail_data:
            timeline_data = q.timeline_episode(selected_id, tgl)

    return render_template(
        'episode.html',
        tgl=tgl,
        daftar=daftar,
        selected_id=selected_id,
        detail=detail_data,
        timeline=timeline_data,
        f_status=f_status,
        f_indikator=f_indikator,
        f_tahap=f_tahap,
        status_list=q.STATUS,
        ind_list=q.INDIKATOR,
        tahap_list=q.TAHAP,
        warna_status=q.WARNA_STATUS
    )

@app.route('/aturan')
def aturan():
    if session.get('role') != 'admin':
        flash("Akses terbatas. Halaman ini khusus untuk Admin / Data Steward.", "warning")
        return redirect(url_for('ringkasan'))
        
    df_aturan = q.katalog_aturan()
    kolom = ["kode", "indikator", "kondisi", "tahap", "keparahan", "steward", "aspek", "dasar"]
    data_aturan = df_aturan[kolom].to_dict(orient='records')
    return render_template('aturan.html', aturan_list=data_aturan)

@app.route('/pengujian')
def pengujian():
    if session.get('role') != 'admin':
        flash("Akses terbatas. Halaman ini khusus untuk Admin / Data Steward.", "warning")
        return redirect(url_for('ringkasan'))
        
    return render_template('pengujian.html')

@app.route('/data_skema')
def data_skema():
    if session.get('role') != 'admin':
        flash("Akses terbatas. Halaman ini khusus untuk Admin / Data Steward.", "warning")
        return redirect(url_for('ringkasan'))
        
    df_tabel = q.daftar_tabel()
    data_tabel = df_tabel.to_dict(orient='records')
    return render_template('data_skema.html', tabel_list=data_tabel)

if __name__ == '__main__':
    app.run(debug=True)