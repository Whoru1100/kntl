from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
from gtts import gTTS
import threading, time, pygame, os, datetime
from io import BytesIO

app = Flask(__name__)
CORS(app)

# --- State Management ---
# Bagian ini menyimpan data antrian, selesai, nomor urut global, status suara, dan data panggilan terakhir.
state = {
    "antrian": [],
    "selesai": [],
    "nomor_urut_global": 1,
    "suara_sedang_jalan": False,
    "last_notify_time": 0,
    "data_panggilan": {"panggil_id": None, "panggil_item": "", "updated_at": 0}
}

# --- Audio Initialization ---
try:
    pygame.mixer.pre_init(44100, -16, 2, 512)
    pygame.mixer.init()
except Exception as e:
    print(f"Peringatan Audio: Mixer tidak bisa inisialisasi ({e})")

def notify(text):
    """Mengaktifkan notifikasi suara via gTTS tanpa memblokir thread utama."""
    current_time = time.time()
    
    # Pencegahan spam suara dalam rentang 2 detik
    if state["suara_sedang_jalan"] or (current_time - state["last_notify_time"] < 2): 
        return False
    
    def speak():
        state["suara_sedang_jalan"] = True
        state["last_notify_time"] = time.time()
        # Gunakan ID unik untuk nama file agar tidak bentrok (race condition)
        fname = f"notif_{int(time.time() * 1000)}.mp3"
        try:
            tts = gTTS(text=text, lang='id')
            tts.save(fname)
            pygame.mixer.music.load(fname)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy(): 
                time.sleep(0.1)
            pygame.mixer.music.unload()
        except Exception as e:
            print(f"Error Audio: {e}")
        finally:
            if os.path.exists(fname):
                try: os.remove(fname)
                except: pass
            state["suara_sedang_jalan"] = False
            
    threading.Thread(target=speak, daemon=True).start()
    return True

# --- Routes ---

@app.route('/')
def index(): 
    return render_template('index.html')

@app.route('/admin')
def admin_page():
    return render_template('admin.html')

@app.route('/monitor')
def monitor():
    return jsonify({
        "antrian": state["antrian"], 
        "selesai": state["selesai"]
    })

@app.route('/checkout', methods=['POST'])
def checkout():
    data = request.json
    if not data or 'item' not in data:
        return jsonify({"status": "error", "message": "Item wajib diisi"}), 400

    new_id = int(time.time() * 1000) 
    asal_pesanan = data.get('asal', 'Pelanggan') 
    
    pesanan = {
        "id": new_id, 
        "no_urut": state["nomor_urut_global"],
        "item": data['item'], 
        "asal": asal_pesanan, 
        "waktu": data.get('waktu', datetime.datetime.now().strftime("%H:%M")),
        "estimasi_kustom": None,
        "created_at": datetime.datetime.now().isoformat() 
    }
    
    state["antrian"].append(pesanan)
    state["nomor_urut_global"] += 1
    
    notify(f"Pesanan baru: {pesanan['item']} dari {asal_pesanan}")
    return jsonify({"status": "success", "id": new_id})

@app.route('/selesai', methods=['POST'])
def selesai():
    """Memproses pesanan (Input Estimasi atau Tandai Selesai)"""
    data = request.json
    tid = int(data.get('id'))
    
    # Kasus 1: Update Estimasi (Status tetap di Antrian)
    if 'estimasi_kustom' in data:
        for p in state["antrian"]:
            if p['id'] == tid:
                p['estimasi_kustom'] = data['estimasi_kustom']
                return jsonify({"status": "updated"})
                
    # Kasus 2: Final Selesai (Pindah dari Antrian ke Selesai)
    pesanan = next((p for p in state["antrian"] if p['id'] == tid), None)
    if pesanan:
        state["selesai"].append(pesanan)
        state["antrian"] = [p for p in state["antrian"] if p['id'] != tid]
        return jsonify({"status": "done"})
    
    return jsonify({"status": "error", "message": "ID tidak ditemukan"}), 404

@app.route('/panggil', methods=['POST'])
def panggil():
    data = request.json
    id_panggil = str(data.get('id', ''))
    
    # Cari di kedua list (antrian & selesai)
    semua_data = state["antrian"] + state["selesai"]
    pesanan = next((p for p in semua_data if str(p['id']) == id_panggil), None)
    item_nama = pesanan['item'] if pesanan else "pesanan Anda"

    state["data_panggilan"] = {
        "panggil_id": id_panggil,
        "panggil_item": item_nama,
        "updated_at": time.time() * 1000
    }
    return jsonify({"status": "calling"})

@app.route('/cek_panggilan')
def cek_panggilan():
    return jsonify(state["data_panggilan"])

@app.route('/delete_permanent', methods=['POST'])
def delete_permanent():
    tid = int(request.json.get('id'))
    state["selesai"] = [p for p in state["selesai"] if p['id'] != tid]
    return jsonify({"status": "deleted"})

@app.route('/clear_all_done', methods=['POST'])
def clear_all_done():
    state["selesai"].clear()
    return jsonify({"status": "success"})

# --- Helper Audio Route ---
@app.route('/get_audio/<text>')
def get_audio(text):
    try:
        tts = gTTS(text=text, lang='id')
        fp = BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        return send_file(fp, mimetype='audio/mpeg')
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    # Penting: host 0.0.0.0 agar bisa diakses dari perangkat lain dalam satu WiFi
    app.run(debug=True, host='0.0.0.0', port=5000)
