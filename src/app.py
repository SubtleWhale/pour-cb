from pathlib import Path
from flask import Flask, render_template, request, jsonify, make_response
import json, os, uuid
from datetime import datetime

app = Flask(__name__)

SAVE_FOLDER = os.getenv("PARIS_FOLDER", "paris")

def data_file(id):
    return str(Path(SAVE_FOLDER) / f"{id}.json")

def get_ip():
    if request.headers.get("X-Forwarded-For"):
        return request.headers["X-Forwarded-For"].split(",")[0].strip()
    return request.remote_addr

def get_or_set_uid():
    uid = request.cookies.get("uid")
    if not uid:
        uid = str(uuid.uuid4())
    return uid

def load_pari(id):
    file = data_file(id)
    if not os.path.exists(file):
        return None
    with open(file, "r") as f:
        return json.load(f)

def save_pari(id, data):
    file = data_file(id)
    Path(file).parent.mkdir(parents=True, exist_ok=True)
    with open(file, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

@app.route("/")
def index():
    resp = make_response(render_template("index.html"))
    uid = get_or_set_uid()
    if "uid" not in request.cookies:
        resp.set_cookie("uid", uid, max_age=60*60*24*365)  # 1 year
    return resp

@app.route("/api/create", methods=["POST"])
def create_pari():
    data = request.json
    pari_id = str(uuid.uuid4())[:8]
    ip_a = get_ip()
    uid_a = get_or_set_uid()

    pari = {
        "id": pari_id,
        "pari": data["pari"],
        "max": None,
        "personne_a": data["personne_a"],
        "personne_b": data["personne_b"],
        "ip_a": ip_a,
        "uid_a": uid_a,
        "ip_b": None,
        "uid_b": None,
        "choix_a": None,
        "choix_b": None,
        "created_at": datetime.now().isoformat()
    }
    save_pari(pari_id, pari)

    resp = make_response(jsonify({"id": pari_id}))
    resp.set_cookie("uid", uid_a, max_age=60*60*24*365)
    return resp

@app.route("/pari/<pari_id>")
def pari(pari_id):
    pari = load_pari(pari_id)
    if pari is None:
        return render_template("404.html"), 404

    ip = get_ip()
    uid = get_or_set_uid()

    # Register person B if not yet registered
    if pari["uid_b"] is None and uid != pari["uid_a"]:
        pari["ip_b"] = ip
        pari["uid_b"] = uid
        save_pari(pari_id, pari)

    # Determine role based on UID
    if uid == pari["uid_a"]:
        role = "a"
    elif uid == pari["uid_b"]:
        role = "b"
    else:
        role = "spectator"

    resp = make_response(render_template("pari.html", pari=pari, role=role))
    if "uid" not in request.cookies:
        resp.set_cookie("uid", uid, max_age=60*60*24*365)
    return resp

@app.route("/api/pari/<pari_id>")
def get_pari(pari_id):
    pari = load_pari(pari_id)
    if pari is None:
        return jsonify({"error": "not found"}), 404

    uid = get_or_set_uid()
    if uid == pari["uid_a"]:
        role = "a"
    elif uid == pari["uid_b"]:
        role = "b"
    else:
        role = "spectator"

    return jsonify({**pari, "role": role})

@app.route("/api/pari/<pari_id>/setmax", methods=["POST"])
def set_max(pari_id):
    pari = load_pari(pari_id)
    if pari is None:
        return jsonify({"error": "not found"}), 404

    uid = get_or_set_uid()

    if uid != pari["uid_b"]:
        return jsonify({"error": "Seule la personne B peut définir le pour combien."}), 403
    if pari["max"] is not None:
        return jsonify({"error": "Le pour combien a déjà été défini."}), 400

    try:
        max_val = int(request.json["max"])
    except (ValueError, KeyError):
        return jsonify({"error": "Valeur invalide."}), 400

    if max_val < 2:
        return jsonify({"error": "Le pour combien doit être au moins 2."}), 400

    pari["max"] = max_val
    save_pari(pari_id, pari)
    return jsonify({**pari, "role": "b"})

@app.route("/api/pari/<pari_id>/choix", methods=["POST"])
def faire_choix(pari_id):
    pari = load_pari(pari_id)
    if pari is None:
        return jsonify({"error": "not found"}), 404

    uid = get_or_set_uid()

    if pari["max"] is None:
        return jsonify({"error": "Le pour combien n'a pas encore été défini."}), 400

    if uid == pari["uid_a"]:
        personne = "a"
    elif uid == pari["uid_b"]:
        personne = "b"
    else:
        return jsonify({"error": "Tu n'es pas autorisé à participer à ce pari."}), 403

    try:
        choix = int(request.json["choix"])
    except (ValueError, KeyError):
        return jsonify({"error": "Nombre invalide."}), 400

    if choix < 1 or choix > pari["max"]:
        return jsonify({"error": f"Le nombre doit être entre 1 et {pari['max']}."}), 400

    if personne == "a":
        if pari["choix_a"] is not None:
            return jsonify({"error": "Tu as déjà choisi !"}), 400
        pari["choix_a"] = choix
    else:
        if pari["choix_b"] is not None:
            return jsonify({"error": "Tu as déjà choisi !"}), 400
        pari["choix_b"] = choix

    save_pari(pari_id, pari)
    return jsonify({**pari, "role": personne})

if __name__ == "__main__":
    app.run(debug=True, port=5000)