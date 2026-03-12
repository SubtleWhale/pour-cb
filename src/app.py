from pathlib import Path
from flask import Flask, render_template, request, jsonify, make_response
import json, os, uuid
from datetime import datetime

app = Flask(__name__)

SAVE_FOLDER = os.getenv("PARIS_FOLDER", "paris")

# Set to False in local dev if not using HTTPS
SECURE_COOKIES = os.getenv("SECURE_COOKIES", "false").lower() != "false"

def data_file(id):
    return str(Path(SAVE_FOLDER) / f"{id}.json")

def get_or_create_uid():
    """Get existing UID from cookie, or generate a new one."""
    uid = request.cookies.get("uid")
    if not uid:
        uid = str(uuid.uuid4())
    return uid

def set_uid_cookie(resp, uid):
    """Attach a secure, long-lived UID cookie to a response."""
    resp.set_cookie(
        "uid",
        uid,
        max_age=60 * 60 * 24 * 365,  # 1 year
        httponly=True,                 # Not accessible via JS
        secure=SECURE_COOKIES,         # HTTPS only (required for SameSite=None)
        samesite="None" if SECURE_COOKIES else "Lax",  # Cross-site for mobile
    )
    return resp

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

def get_role(pari, uid):
    if uid == pari["uid_a"]:
        return "a"
    elif uid == pari["uid_b"]:
        return "b"
    return "spectator"

@app.route("/")
def index():
    uid = get_or_create_uid()
    resp = make_response(render_template("index.html"))
    set_uid_cookie(resp, uid)
    return resp

@app.route("/api/create", methods=["POST"])
def create_pari():
    data = request.json
    pari_id = str(uuid.uuid4())[:8]
    uid_a = get_or_create_uid()

    pari = {
        "id": pari_id,
        "pari": data["pari"],
        "max": None,
        "personne_a": data["personne_a"],
        "personne_b": data["personne_b"],
        "uid_a": uid_a,
        "uid_b": None,
        "choix_a": None,
        "choix_b": None,
        "created_at": datetime.now().isoformat()
    }
    save_pari(pari_id, pari)

    resp = make_response(jsonify({"id": pari_id}))
    set_uid_cookie(resp, uid_a)
    return resp

@app.route("/pari/<pari_id>")
def pari(pari_id):
    pari = load_pari(pari_id)
    if pari is None:
        return render_template("404.html"), 404

    uid = get_or_create_uid()

    # Register person B on first visit (anyone who isn't A)
    if pari["uid_b"] is None and uid != pari["uid_a"]:
        pari["uid_b"] = uid
        save_pari(pari_id, pari)

    role = get_role(pari, uid)
    resp = make_response(render_template("pari.html", pari=pari, role=role))
    set_uid_cookie(resp, uid)
    return resp

@app.route("/api/pari/<pari_id>")
def get_pari(pari_id):
    pari = load_pari(pari_id)
    if pari is None:
        return jsonify({"error": "not found"}), 404

    uid = get_or_create_uid()
    role = get_role(pari, uid)

    # Never expose UIDs to the client
    safe_pari = {k: v for k, v in pari.items() if not k.startswith("uid_")}
    resp = make_response(jsonify({**safe_pari, "role": role}))
    set_uid_cookie(resp, uid)
    return resp

@app.route("/api/pari/<pari_id>/setmax", methods=["POST"])
def set_max(pari_id):
    pari = load_pari(pari_id)
    if pari is None:
        return jsonify({"error": "not found"}), 404

    uid = get_or_create_uid()

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

    safe_pari = {k: v for k, v in pari.items() if not k.startswith("uid_")}
    resp = make_response(jsonify({**safe_pari, "role": "b"}))
    set_uid_cookie(resp, uid)
    return resp

@app.route("/api/pari/<pari_id>/choix", methods=["POST"])
def faire_choix(pari_id):
    pari = load_pari(pari_id)
    if pari is None:
        return jsonify({"error": "not found"}), 404

    uid = get_or_create_uid()

    if pari["max"] is None:
        return jsonify({"error": "Le pour combien n'a pas encore été défini."}), 400

    role = get_role(pari, uid)
    if role == "spectator":
        return jsonify({"error": "Tu n'es pas autorisé à participer à ce pari."}), 403

    try:
        choix = int(request.json["choix"])
    except (ValueError, KeyError):
        return jsonify({"error": "Nombre invalide."}), 400

    if choix < 1 or choix > pari["max"]:
        return jsonify({"error": f"Le nombre doit être entre 1 et {pari['max']}."}), 400

    if role == "a":
        if pari["choix_a"] is not None:
            return jsonify({"error": "Tu as déjà choisi !"}), 400
        pari["choix_a"] = choix
    else:
        if pari["choix_b"] is not None:
            return jsonify({"error": "Tu as déjà choisi !"}), 400
        pari["choix_b"] = choix

    save_pari(pari_id, pari)

    safe_pari = {k: v for k, v in pari.items() if not k.startswith("uid_")}
    resp = make_response(jsonify({**safe_pari, "role": role}))
    set_uid_cookie(resp, uid)
    return resp

if __name__ == "__main__":
    app.run(debug=True, port=5000)