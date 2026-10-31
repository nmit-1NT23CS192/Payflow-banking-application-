import os, json, time, random, secrets, threading
from pathlib import Path
from datetime import datetime, timezone
from functools import wraps

import bcrypt
import jwt
from flask import Flask, request, jsonify, send_from_directory

BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "db.json"
SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-me")

app = Flask(__name__, static_folder="public", static_url_path="")

# Small JSON-file database for learning/demo use. For production, use SQLite/MySQL.
def load_db():
    if DB_FILE.exists():
        try:
            data = json.loads(DB_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("users"), list):
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return {"users": []}

db = load_db()
db_lock = threading.RLock()
attempts = {}  # email -> {count, until}

def save_db():
    with db_lock:
        temp = DB_FILE.with_suffix(".tmp")
        temp.write_text(json.dumps(db, indent=2), encoding="utf-8")
        temp.replace(DB_FILE)

def uid():
    return secrets.token_hex(8)

def new_account_no():
    return str(random.randint(100000000000, 999999999999))

def public_user(user):
    return {"name": user["name"], "email": user["email"],
            "accountNo": user["accountNo"], "balance": user["balance"]}

def fail(code, message):
    return jsonify({"error": message}), code

def sign_token(user):
    token = jwt.encode({"id": user["id"], "exp": int(time.time()) + 7200}, SECRET, algorithm="HS256")
    return token.decode("utf-8") if isinstance(token, bytes) else token

def auth_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        token = header[7:] if header.startswith("Bearer ") else header
        try:
            payload = jwt.decode(token, SECRET, algorithms=["HS256"])
            user = next((u for u in db["users"] if u.get("id") == payload.get("id")), None)
            if user is None:
                raise jwt.InvalidTokenError("unknown user")
            request.user = user
        except jwt.PyJWTError:
            return fail(401, "Your session has expired. Please log in again.")
        return fn(*args, **kwargs)
    return wrapped

def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

@app.get("/")
def home():
    return send_from_directory(app.static_folder, "index.html")

@app.post("/api/register")
def register():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).lower().strip()
    password = str(data.get("password", ""))
    if not name or not __import__("re").match(r"^\S+@\S+\.\S+$", email):
        return fail(400, "Enter your name and a valid email.")
    if len(password) < 6:
        return fail(400, "Password must be at least 6 characters.")
    with db_lock:
        if any(u.get("email") == email for u in db["users"]):
            return fail(409, "This email is already registered.")
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=10)).decode()
        user = {"id": uid(), "name": name, "email": email, "hash": hashed,
                "accountNo": new_account_no(), "balance": 10000,
                "beneficiaries": [], "transactions": []}
        db["users"].append(user)
        save_db()
    return jsonify({"token": sign_token(user), "user": public_user(user)})

@app.post("/api/login")
def login():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).lower().strip()
    password = str(data.get("password", ""))
    user = next((u for u in db["users"] if u.get("email") == email), None)
    if user is None:
        return fail(401, "No account found for this email.")
    attempt = attempts.setdefault(email, {"count": 0, "until": 0})
    if time.time() < attempt["until"]:
        return fail(429, "Too many wrong attempts. Try again in a minute.")
    try:
        valid = bcrypt.checkpw(password.encode(), user["hash"].encode())
    except (ValueError, KeyError):
        valid = False
    if not valid:
        attempt["count"] += 1
        if attempt["count"] >= 5:
            attempt["until"] = time.time() + 60
            attempt["count"] = 0
        return fail(401, "Invalid password.")
    attempt["count"] = 0
    return jsonify({"token": sign_token(user), "user": public_user(user)})

@app.get("/api/me")
@auth_required
def me():
    return jsonify(public_user(request.user))

@app.get("/api/transactions")
@auth_required
def transactions():
    return jsonify(request.user.get("transactions", []))

@app.get("/api/beneficiaries")
@auth_required
def beneficiaries():
    return jsonify(request.user.get("beneficiaries", []))

@app.post("/api/beneficiaries")
@auth_required
def add_beneficiary():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    acc = str(data.get("acc", "")).strip()
    import re
    user = request.user
    if not name or not re.fullmatch(r"\d{9,12}", acc):
        return fail(400, "Enter a name and a 9–12 digit account number.")
    if acc == user["accountNo"]:
        return fail(400, "You can't add your own account.")
    if any(b.get("acc") == acc for b in user["beneficiaries"]):
        return fail(409, "That account is already saved.")
    beneficiary = {"id": uid(), "name": name, "acc": acc}
    user["beneficiaries"].append(beneficiary)
    save_db()
    return jsonify(beneficiary)

@app.delete("/api/beneficiaries/<beneficiary_id>")
@auth_required
def delete_beneficiary(beneficiary_id):
    user = request.user
    user["beneficiaries"] = [b for b in user["beneficiaries"] if b.get("id") != beneficiary_id]
    save_db()
    return jsonify({"ok": True})

@app.post("/api/deposit")
@auth_required
def deposit():
    data = request.get_json(silent=True) or {}
    try:
        amount = float(data.get("amount"))
    except (TypeError, ValueError):
        amount = float("nan")
    if not amount.is_integer() or amount < 1 or amount > 100000:
        return fail(400, "Enter a whole amount between ₹1 and ₹1,00,000.")
    amount = int(amount)
    user = request.user
    user["balance"] += amount
    user["transactions"].insert(0, {"id": uid(), "type": "credit", "name": "Added to wallet",
        "amount": amount, "note": "", "date": now_iso(), "status": "completed"})
    save_db()
    return jsonify(public_user(user))

@app.post("/api/transfer")
@auth_required
def transfer():
    data = request.get_json(silent=True) or {}
    user = request.user
    amount_raw = data.get("amount")
    try:
        amount = float(amount_raw)
    except (TypeError, ValueError):
        amount = float("nan")
    beneficiary = next((b for b in user["beneficiaries"] if b.get("id") == data.get("beneficiaryId")), None)
    if beneficiary is None:
        return fail(400, "Choose a beneficiary.")
    if not amount.is_integer() or amount < 1:
        return fail(400, "Enter a whole amount of ₹1 or more.")
    amount = int(amount)
    if amount > user["balance"]:
        return fail(400, f"Not enough balance. You have ₹{user['balance']}.")
    tx = {"id": uid(), "type": "debit", "name": beneficiary["name"], "acc": beneficiary["acc"],
          "amount": amount, "note": str(data.get("note", ""))[:40], "date": now_iso(), "status": "pending"}
    user["balance"] -= amount
    user["transactions"].insert(0, tx)
    save_db()
    track(user, tx)
    return jsonify(tx)

def track(user, tx):
    def set_status(status):
        with db_lock:
            tx["status"] = status
            if status == "failed":
                user["balance"] += tx["amount"]
            elif status == "completed":
                receiver = next((x for x in db["users"] if x.get("accountNo") == tx.get("acc")), None)
                if receiver:
                    receiver["balance"] += tx["amount"]
                    receiver.setdefault("transactions", []).insert(0, {"id": uid(), "type": "credit",
                        "name": user["name"], "amount": tx["amount"], "note": tx.get("note", ""),
                        "date": now_iso(), "status": "completed"})
            save_db()
    def finish():
        set_status("completed" if random.random() < 0.9 else "failed")
    if tx.get("status") == "pending":
        threading.Timer(1.5, lambda: (set_status("processing"), threading.Timer(2.0, finish).start())).start()
    else:
        threading.Timer(2.0, finish).start()

# Resume in-flight demo payments after restarting the server.
for existing_user in db["users"]:
    for existing_tx in existing_user.get("transactions", []):
        if existing_tx.get("status") in ("pending", "processing"):
            track(existing_user, existing_tx)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)
