import json

AUDIT_LOG_PATH = "audit_log.jsonl"
MAX_LOG_ENTRIES = 50


def log_submission(entry):
    """Append a structured audit log entry as one JSON line."""
    with open(AUDIT_LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")


def get_log():
    """Return the most recent audit log entries, newest first."""
    try:
        with open(AUDIT_LOG_PATH, "r") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return []

    entries = [json.loads(line) for line in lines if line.strip()]
    return list(reversed(entries))[:MAX_LOG_ENTRIES]


def get_latest_entry_by_content_id(content_id):
    """Return the most recent audit log entry for a given content_id, or None."""
    try:
        with open(AUDIT_LOG_PATH, "r") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return None

    for line in reversed(lines):
        if not line.strip():
            continue
        entry = json.loads(line)
        if entry.get("content_id") == content_id:
            return entry

    return None
