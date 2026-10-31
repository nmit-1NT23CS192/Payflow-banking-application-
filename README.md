# PayFlow — Python Flask Backend

This project keeps the original HTML/CSS/JavaScript frontend and replaces the Node.js backend with Python Flask.

## Requirements
- Python 3.10+

## Run on Windows
Open this folder in VS Code Terminal:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
$env:JWT_SECRET="replace-this-with-a-long-random-secret"
python app.py
```

Then open http://127.0.0.1:5000

## Run on macOS/Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export JWT_SECRET="replace-this-with-a-long-random-secret"
python app.py
```

## API routes
- `POST /api/register` — name, email, password
- `POST /api/login` — email, password
- `GET /api/me` — authenticated user summary
- `GET /api/transactions` — authenticated user's transactions
- `GET /api/beneficiaries` — authenticated user's beneficiaries
- `POST /api/beneficiaries` — name, acc
- `DELETE /api/beneficiaries/<id>` — delete beneficiary
- `POST /api/deposit` — amount
- `POST /api/transfer` — beneficiaryId, amount, optional note

Protected APIs accept `Authorization: Bearer <JWT>`.

## Demo limitations
- `db.json` is a learning/demo database. For a production system, use SQLite/MySQL/PostgreSQL and database transactions.
- Transfers are simulated (90% success). They do not move real bank/UPI money.
- The default JWT secret is for local development only. Set `JWT_SECRET` before deployment.
- Flask debug mode is enabled for local development; disable it in production.
