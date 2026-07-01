# Provenance Guard

An API that classifies submitted text as likely AI-generated, likely human-written, or uncertain, using two independent detection signals, and lets creators appeal a decision. See [planning.md](planning.md) for the original design narrative and architecture diagram.

## Running the app

```
pip install -r requirements.txt
python app.py
```

The server runs on `http://localhost:5001`.

## Architecture

```
POST /submit (text, creator_id)
      |
      v
  LLM Signal ------------\
  Stylometric Heuristics -+--> Confidence Scoring --> Attribution --> Transparency Label
      |                                                                     |
      v                                                                     v
  content_id assigned                                              Audit Log entry written
                                                                             |
                                                                             v
                                                                  JSON response returned

POST /appeal (content_id, creator_reasoning)
      |
      v
  Look up original decision --> append new Audit Log entry (status: under_review)
      |
      v
  Confirmation response
```

## Detection signals

**1. LLM signal** ([main.py](main.py), `get_llm_signal`) — sends the text to Groq's LLM with a prompt asking it to judge naturalness, generic/hedging phrasing, common AI stock phrases, and overall tone, and to return a structured `llm_score` in [0, 1].

**2. Stylometric heuristics signal** ([main.py](main.py), `get_heuristic_signal`) — pure computation over the text's structure: sentence-length variation (coefficient of variation), vocabulary diversity (type-token ratio), punctuation-type variety, and repeated 3-word phrases. No API call, no keyword lists — just counting.

**Why these two, and why in this combination:** they fail in different, mostly non-overlapping ways, which is the point of having two signals instead of one.

- The LLM signal reads meaning and register. It catches AI text that *reads* generic — hedging, stock transitions, a certain smoothed-over "essay" voice — even when there's nothing numerically unusual about the sentences. Its weakness is that it's itself a model being asked to judge another model's output, so it can be fooled by paraphrasing or "sound more human" prompting, and it's the most expensive/slowest part of the pipeline.
- The heuristic signal can't be talked around the same way — exact repeated phrasing or robotically uniform sentence lengths show up in the math no matter how the text is otherwise dressed up. But because it never reads content, it's blind to anything that only shows up in wording. We deliberately kept it free of keyword/phrase matching (an earlier version detected AI clichés directly, which really is just a second, weaker LLM-style signal in disguise, not a heuristic).

In testing, this split held up: short, well-formed AI text with varied vocabulary and no repeated phrases scored *low* on the heuristic signal but was still caught by the LLM signal; a long passage with an exact phrase repeated four times scored high on the heuristic signal even before the LLM signal weighed in.

**If deploying for real**, I would not stop at two signals. I'd add a perplexity/burstiness-style statistical signal (comparing the text against a language model's token probabilities, which is what tools like GPTZero use) as a third, model-free-of-prompting check, and I'd want ground-truth labeled data to actually calibrate the weights below instead of setting them by hand.

## Confidence scoring

The two signal scores are combined with a weighted average, in [scoring.py](scoring.py):

```python
def combine_scores(llm_score, heuristic_score):
    return 0.7 * llm_score + 0.3 * heuristic_score
```

**Why 0.7/0.3 and not an even split:** early testing (with an equal-weight average) showed the heuristic signal is the noisier of the two, short passages and well-formed formal writing (AI or human) produce similar structural stats, so the heuristic signal alone doesn't separate them well. The LLM signal, which is actually reading the text, was the more reliable discriminator in every case we tried. Weighting it higher reflects that difference in reliability rather than treating the two signals as equally trustworthy votes. This is a hand-tuned choice, not one derived from labeled data. See Known Limitations.

The combined score is then mapped to an attribution label:

```
0.00 – 0.40  =  likely_human
0.41 – 0.64  =  uncertain
0.65 – 1.00  =  likely_ai
```

The uncertain band is intentionally wide (24 points) rather than a thin midpoint, because a false "likely_ai" label is more damaging to a creator than an honest "uncertain" — better to admit the system doesn't know than to confidently guess wrong.

**Example submissions showing meaningful variation** (both are real runs against the live LLM signal, not fabricated):

| Case | Text (truncated) | `llm_score` | `heuristic_score` | `confidence_score` | Attribution |
|---|---|---|---|---|---|
| High-confidence | "It is increasingly important to leverage cutting-edge solutions in order to remain competitive. It is increasingly important to leverage cutting-edge solutions..." (exact sentence repeated 3x) | 0.99 | 0.59 | **0.871** | `likely_ai` |
| Lower-confidence | "Remote work offers flexibility, but it also comes with challenges. Some people thrive without a commute, while others struggle with isolation. It really depends on the person and the type of job." | 0.40 | 0.50 | **0.429** | `uncertain` |

The first case combines an LLM signal that's almost certain (0.99) with a heuristic signal picking up the literal repeated sentence — both signals agree, so the combined score sits well above the `likely_ai` threshold. The second is genuinely ambiguous prose with no repetition and no strong AI-style tell either way — both signals land near the middle, and the combined score falls squarely in the `uncertain` band rather than being forced toward a confident-sounding but unjustified label.

## Transparency labels

Exactly one of three fixed strings is returned in the `label` field, chosen by the attribution result ([scoring.py](scoring.py), `LABELS`):

- **High-confidence AI** (`likely_ai`): `"Our automated system found strong signs that this content may have been AI-generated."`
- **High-confidence human** (`likely_human`): `"Our automated system found strong signs that this content was likely written by a person."`
- **Uncertain**: `"Our system could not confidently determine whether this content was written by a person or generated by AI."`

## Appeals workflow
Any creator can appeal a decision they disagree with via `POST /appeal` with `content_id` and `creator_reasoning`. The endpoint looks up the original classification, and appends a **new** audit log entry (rather than mutating the original) carrying over the original signal scores/attribution/label but with `status: "under_review"` and the appeal reasoning attached. No automatic re-classification happens — a human is expected to review the flagged content_id. The response confirms receipt: `{"content_id": ..., "status": "under_review", "message": "Your appeal has been received and marked for review."}`. An unknown `content_id` returns 404; a missing field returns 400.

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

- **10 per minute** — a real person submitting their own writing does so in bursts: draft, read the classification, tweak a paragraph, resubmit. Even fast iterative revising rarely produces more than one submission every few seconds, so 10/minute leaves generous headroom for that workflow while still capping a tight request loop — a script hammering the endpoint to scrape scores or run up LLM API costs hits the wall almost immediately.
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

## Known limitations
**Formal/ESL writing gets pulled toward "AI-like" by the heuristic signal, specifically because of the `sentence_variation` and `punctuation_uniformity` components.** These two components treat *uniformity* itself as an AI tell: consistent sentence lengths and a narrow range of punctuation (periods and commas, no dashes/exclamations/question marks) push the score up, regardless of why the text is uniform. But a non-native English speaker, or anyone writing in a formal/academic register, tends to produce exactly that kind of measured, evenly-paced, punctuation-restrained prose as a *feature of their writing style*, not because it's AI-generated. We hit this directly during appeals testing — a submission whose appeal reasoning was literally "I am a non-native English speaker and my writing style may appear more formal than typical" is exactly the profile these two components would score higher, since they can't distinguish "uniform because formulaic" from "uniform because careful and non-native." This is a structural property of the signal, not a data-volume problem: no amount of additional heuristic tuning fixes it without either adding content-aware context (which the LLM signal already partially provides, at 0.7 weight) or accepting that formal/ESL writers are more likely to receive an `uncertain` or occasionally an incorrect `likely_ai` label than casual native-English writers are.

A second, related gap: the heuristic signal's `vocabulary_diversity` and `repetition` components are only meaningful past a certain length (see `MIN_RELIABLE_WORD_COUNT` in [main.py](main.py)) — on short submissions, almost any text has high lexical diversity and zero repeated phrases, AI-written or not, so those two components contribute close to nothing at that length. We damp the heuristic score toward neutral for short text for this reason, but that doesn't fix the underlying issue: sophisticated short-form AI text (a paragraph, not an essay) is caught almost entirely by the LLM signal, and if that call is ever wrong, the heuristic signal has little ability to catch or override it.

## Spec Reflection
The spec helped guide my implementation because it had detailed instructions/detailed guide I could use throughout the project, allowing me to focus on the details of implementation rather than figuring out what I needed to do next. This was especially useful in building out each signal because I already knew the purpose of each one. One way I diverged from the initial spec was with the confidence score identifications. Originally, I had scores of 0.75 and higher be classified as AI-generated but later I changed it to 0.6 due to the fact that my model tended to lean towards human-written/unknown more often than leaning towards AI-generated. This is because I designed my program in such a way that it would be very cautious before labelling something as AI-generated (because humans would not like it if their writing got classified as AI-generated).

## AI Usage
1. I directed the AI to implement the get_heuristic_signal function of my program, which returns the heuristic score for a piece of text. However, within this function, claude added a list of common AI-generated words and included AI-generated common words being in the text as the highest weight for the heuristic score. I realized that the heuristic score should not consider common AI-generated words as part of the scoring and should just consider sentence structure and other computational aspects of the text, since the LLM is taking care of word matching. I changed the get_heuristic_signal to only care about computation, not about words.
2. When writing planning.md, I told the AI to give me feedback on my initial confidence scoring mechanism, and claude told me to take the average of llm_score and heuristic_score to calculate the confidence_score. However, as I worked through the project, I realized that the llm_score is usually more accurate than the hueristic_score because computation alone does not say too much about the text, so I tweaked the confidence_score calculation to be 0.7 * llm_score + 0.3 * heuristic_score. This ended up producing more accurate results.
