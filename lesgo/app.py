from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
from gtts import gTTS
import threading, time, pygame, os
from io import BytesIO

app = Flask(__name__)
CORS(app)

data_antrean = []
data_selesai = []
nomor_urut_global = 1
suara_sedang_jalan = False
last_notify_time = 0

# Penyimpanan status panggilan terakhir
data_panggilan = {"panggil_id": None, "panggil_item": "", "updated_at": 0} 
last_call = {"id": None, "item": "", "time": 0}

pygame.mixer.pre_init(44100, -16, 2, 512)
pygame.mixer.init()

def notify(text):
    global suara_sedang_jalan, last_notify_time
    current_time = time.time()
    if suara_sedang_jalan or (current_time - last_notify_time < 2): 
        return False
    
    def speak():
        global suara_sedang_jalan, last_notify_time
        try:
            suara_sedang_jalan = True
            last_notify_time = time.time()
            tts = gTTS(text=text, lang='id')
            fname = f"v_{int(time.time())}.mp3"
            tts.save(fname)
            pygame.mixer.music.load(fname)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy(): 
                time.sleep(0.1)
            pygame.mixer.music.unload()
            if os.path.exists(fname): 
                os.remove(fname)
        except Exception as e:
            print(f"Error Audio: {e}")
        finally:
            suara_sedang_jalan = False
            
    threading.Thread(target=speak, daemon=True).start()
    return True

@app.route('/')
def index(): 
    return render_template('index.html')

@app.route('/admin')
def admin_page():
    return render_template('admin.html')

@app.route('/monitor')
def monitor(): 
    return jsonify({
        "antrean": data_antrean,
        "selesai": data_selesai
    })

@app.route('/checkout', methods=['POST'])
def checkout():
    global data_antrean, nomor_urut_global
    d = request.json
    new_id = int(time.time() * 1000) 
    
    # Ambil asal pesanan (Ojek Online, Walk In, dll)
    asal_pesanan = d.get('asal', 'Pelanggan') 
    
    p = {
        "id": new_id, 
        "no_urut": nomor_urut_global,
        "item": d['item'], 
        "asal": asal_pesanan, 
        "waktu": d.get('waktu', '-')
    }
    data_antrean.append(p)
    nomor_urut_global += 1
    
    teks_notif = f"Pesanan baru masuk dari {asal_pesanan}"
    notify(teks_notif)
    
    return jsonify({"status": "success", "id": new_id})

@app.route('/cek_panggilan')
def cek_panggilan():
    global data_panggilan
    return jsonify({
        "panggil_id": data_panggilan["panggil_id"],
        "panggil_item": data_panggilan["panggil_item"],
        "updated_at": data_panggilan["updated_at"]
    })

@app.route('/get_audio/<text>')
def get_audio(text):
    tts = gTTS(text=text, lang='id')
    fp = BytesIO()
    tts.write_to_fp(fp)
    fp.seek(0)
    return send_file(fp, mimetype='audio/mpeg')

@app.route('/panggil', methods=['POST'])
def panggil():
    global data_panggilan
    d = request.json
    id_panggil = str(d.get('id', ''))
    
    # Ambil detail menu dari data_antrean
    pesanan = next((p for p in data_antrean if str(p['id']) == id_panggil), None)
    item_nama = pesanan['item'] if pesanan else "pesanan Anda"

    data_panggilan = {
        "panggil_id": id_panggil,
        "panggil_item": item_nama,
        "updated_at": time.time() * 1000
    }
    
    return jsonify({"status": "calling"})

@app.route('/selesai', methods=['POST'])
def selesai():
    global data_antrean, data_selesai
    tid = int(request.json['id'])
    pesanan = next((p for p in data_antrean if int(p['id']) == tid), None)
    if pesanan:
        data_selesai.append(pesanan)
        data_antrean = [p for p in data_antrean if int(p['id']) != tid]
    return jsonify({"status": "done"})

@app.route('/delete_permanent', methods=['POST'])
def delete_permanent():
    global data_selesai
    tid = int(request.json['id'])
    data_selesai = [p for p in data_selesai if int(p['id']) != tid]
    return jsonify({"status": "deleted"})

if __name__ == "__main__":

    # masukin ip dari cmd "ipconfig" di bagian IPv4 Address
    #contoh host='1xx.xxx.xxx.xxx'

    app.run(debug=True, host='1xx.xxx.xxx.xxx', port=5000)