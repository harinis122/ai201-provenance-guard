# Provenance Guard

See [planning.md](planning.md) for the full architecture narrative, detection signals, and uncertainty representation.

## Running the app

```
pip install -r requirements.txt
python app.py
```

The server runs on `http://localhost:5001`.

## Rate limiting

`POST /submit` is rate-limited with [Flask-Limiter](https://flask-limiter.readthedocs.io/):

```python
@app.route("/submit", methods=["POST"])
@limiter.limit("10 per minute;100 per day")
def submit():
    ...
```

### Reasoning

The limits are chosen to comfortably cover a legitimate writer's usage pattern while capping the cost/abuse surface of an endpoint that calls a paid LLM API on every request.

- **10 per minute** — a real person submitting their own writing does so in bursts: draft, read the classification, tweak a paragraph, resubmit. Even fast iterative revising rarely produces more than one submission every few seconds, so 10/minute leaves generous headroom for that workflow (a submission roughly every 6 seconds, sustained for a full minute) while still capping a tight request loop — a script hammering the endpoint to scrape scores or run up LLM API costs hits the wall almost immediately.
- **100 per day** — accounts for a highly active user submitting many separate pieces or many revisions of the same piece across a full day (roughly one submission every ~15 minutes for 24 hours straight, well beyond what one writer would realistically do). It exists mainly to block sustained low-and-slow abuse that stays under the per-minute limit but still adds up to meaningful API cost over a day.

Both limits are enforced per-IP address (`get_remote_address`), using in-memory storage (`storage_uri="memory://"`), which is sufficient for local development/single-process deployment.

### Verifying it works

With the server running, send 12 rapid requests (more than the 10/minute limit):

```
for i in $(seq 1 12); do
  curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:5001/submit \
    -H "Content-Type: application/json" \
    -d '{"text": "This is a test submission for rate limit testing purposes only.", "creator_id": "ratelimit-test"}'
done
```

Observed output — first 10 requests succeed, the next 2 are rejected:

```
200
200
200
200
200
200
200
200
200
200
429
429
```
