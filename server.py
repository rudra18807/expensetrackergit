import os
import random
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory

load_dotenv()

AIRTABLE_PAT = os.environ.get("AIRTABLE_PAT", "").strip()
AIRTABLE_BASE_ID = os.environ.get("AIRTABLE_BASE_ID", "").strip()
AIRTABLE_TABLE_NAME = os.environ.get("AIRTABLE_TABLE_NAME", "").strip()

app = Flask(__name__, static_folder=".", static_url_path="")


def _require_env() -> Optional[Tuple[Dict[str, str], Any]]:
    missing = []
    if not AIRTABLE_PAT:
        missing.append("AIRTABLE_PAT")
    if not AIRTABLE_BASE_ID:
        missing.append("AIRTABLE_BASE_ID")
    if not AIRTABLE_TABLE_NAME:
        missing.append("AIRTABLE_TABLE_NAME")

    if missing:
        return (
            {"error": "server_not_configured", "missing": missing},
            500,
        )
    return None


def _airtable_table_url(table_name: str) -> str:
    # Table name needs URL encoding; requests will handle it for params but not path.
    from urllib.parse import quote

    return f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{quote(table_name, safe='')}"


def _airtable_headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {AIRTABLE_PAT}",
        "Content-Type": "application/json",
    }


def _airtable_request(method: str, url: str, *, params=None, json_body=None) -> Any:
    resp = requests.request(
        method,
        url,
        headers=_airtable_headers(),
        params=params,
        json=json_body,
        timeout=20,
    )
    if not resp.ok:
        raise RuntimeError(f"Airtable error: {resp.status_code} {resp.text}")
    return resp.json()


def _generate_ten_digit_id() -> str:
    first = random.randint(1, 9)
    rest = str(random.randint(0, 999_999_999)).zfill(9)
    return f"{first}{rest}"


def _get_record_by_client_id(client_id: str) -> Optional[Dict[str, Any]]:
    formula = f"ClientID='{client_id}'"
    data = _airtable_request(
        "GET",
        _airtable_table_url(AIRTABLE_TABLE_NAME),
        params={"filterByFormula": formula, "maxRecords": 1},
    )
    records = data.get("records", [])
    return records[0] if records else None


def _normalize_tx(record: Dict[str, Any]) -> Dict[str, Any]:
    fields = record.get("fields", {})
    return {
        "description": str(fields.get("Description", "")).strip(),
        "amount": float(fields.get("Amount", 0) or 0),
        "type": fields.get("Type", ""),
        "createdAt": fields.get("CreatedAt", ""),
    }


def _to_airtable_date(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return datetime.now(timezone.utc).date().isoformat()
    # Accept ISO datetime from frontend and keep only date part for Airtable Date fields.
    return text[:10]


def _get_transactions_by_client_id(client_id: str) -> List[Dict[str, Any]]:
    formula = f"ClientID='{client_id}'"
    all_records: List[Dict[str, Any]] = []
    offset = None
    while True:
        params = {"filterByFormula": formula, "pageSize": 100}
        if offset:
            params["offset"] = offset
        data = _airtable_request("GET", _airtable_table_url(AIRTABLE_TABLE_NAME), params=params)
        records = data.get("records", [])
        all_records.extend(records)
        offset = data.get("offset")
        if not offset:
            break

    txs = [_normalize_tx(record) for record in all_records]
    txs = [tx for tx in txs if tx["type"] in ("income", "expense")]
    txs.sort(key=lambda x: x.get("createdAt", ""))
    return txs


@app.get("/")
def root():
    return send_from_directory(".", "index.html")


@app.get("/health")
def health():
    return jsonify({"ok": True})


@app.post("/api/tracker")
def api_create_tracker():
    env_error = _require_env()
    if env_error:
        return env_error

    # Generate a unique 10-digit ID (check collisions just in case).
    for _ in range(10):
        client_id = _generate_ten_digit_id()
        existing_transactions = _get_transactions_by_client_id(client_id)
        if not existing_transactions:
            return jsonify({"clientId": client_id})

    return (
        jsonify({"error": "id_generation_failed"}),
        500,
    )


@app.get("/api/tracker/<client_id>")
def api_get_tracker(client_id: str):
    env_error = _require_env()
    if env_error:
        return env_error

    if not client_id.isdigit() or len(client_id) != 10:
        return jsonify({"error": "invalid_client_id"}), 400

    txs = _get_transactions_by_client_id(client_id)
    if not txs:
        return jsonify({"error": "not_found"}), 404

    return jsonify({"clientId": client_id, "transactions": txs})


@app.post("/api/tracker/<client_id>/transactions")
def api_add_transaction(client_id: str):
    env_error = _require_env()
    if env_error:
        return env_error

    if not client_id.isdigit() or len(client_id) != 10:
        return jsonify({"error": "invalid_client_id"}), 400

    body = request.get_json(silent=True) or {}
    description = str(body.get("description", "")).strip()
    amount = body.get("amount", None)
    tx_type = body.get("type", "")

    if not description:
        return jsonify({"error": "description_required"}), 400
    try:
        amount_num = float(amount)
    except Exception:
        return jsonify({"error": "amount_invalid"}), 400
    if amount_num <= 0:
        return jsonify({"error": "amount_must_be_positive"}), 400
    if tx_type not in ("income", "expense"):
        return jsonify({"error": "type_invalid"}), 400

    tx = {
        "description": description,
        "amount": amount_num,
        "type": tx_type,
        "createdAt": _to_airtable_date(body.get("createdAt")),
    }

    payload = {
        "records": [
            {
                "fields": {
                    "ClientID": client_id,
                    "Description": tx["description"],
                    "Amount": tx["amount"],
                    "Type": tx["type"],
                    "CreatedAt": tx["createdAt"],
                },
            }
        ]
    }
    _airtable_request("POST", _airtable_table_url(AIRTABLE_TABLE_NAME), json_body=payload)
    txs = _get_transactions_by_client_id(client_id)
    return jsonify({"clientId": client_id, "transactions": txs})


@app.get("/<path:path>")
def static_proxy(path: str):
    # Serve frontend assets (styles.css, app.js, etc.)
    return send_from_directory(".", path)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5173"))
    app.run(host="0.0.0.0", port=port, debug=True)
