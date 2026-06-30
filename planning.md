## Architechture Narrative
## Architecture Narrative

When a creator submits a piece of text, the text first enters the system through the POST/submit API endpoint. This endpoint receives the raw text and the user ID. Before the request is processed, the rate limiter checks whether the user has submitted too many requests recently. If the request exceeds the allowed limit, the system rejects it with a rate-limit error. If the request is allowed, the API creates a unique text_id for this submission.

The text then goes into the LLM signal. This signal sends the text to a language model and asks it to judge whether the writing appears to be AI-generated or written by a human. The LLM signal returns a score based on overall style, phrasing, and patterns that might look AI-like.

Next, the same text goes to the stylometric heuristics signal. This signal does not try to understand the meaning of the text, but rather measures structural properties such as sentence length variation, vocabulary, punctuation, and how repetitive the writing is. This signal returns a score based on writing patterns.

After both signals finish, their scores go to the confidence scoring component. This component combines both the LLM score and the stylometric score into one final score. The score represents how strongly the system believes the text is AI-generated or written by a human. A middle score means the system is unsure, while a score closer to either end means the system has stronger confidence.

The combined score then goes to the attribution decision component. This component maps the score into one of three results: likely AI-generated, likely human-written, or uncertain. The system does not force every text into a simple AI-or-human answer because some writing will be ambiguous.

The attribution result and confidence score then go to the transparency label component. This component outputs the exact label text that a reader would see on the platform. High-confidence AI text would receive a label explaining that the system believes the content is likely AI-generated. High-confidence human text would receive a label explaining that the system found the content likely human-written. Ambigious cases would receive a label saying that the system could not confidently figure out the source.

Before the response is returned to the user, the audit log component records the decision. The audit log records the timestamp, content ID, user ID, individual signal scores, combined confidence score, final attribution result, label text, and current status. The status is initially set to classified.

Finally, the API returns a structured JSON response to the platform. The response includes the text_id, attribution result, confidence score, individual signal scores, and the transparency label text that should be shown to the reader.

If the creator disagrees with the classification, they can submit an appeal through the POST/appeal endpoint. The appeal endpoint receives the text_id and the creator’s explanation. The system finds the original decision, updates the content status to under_review, and writes a new audit log entry showing that an appeal was submitted. The system does not automatically reclassify the text after the appeal, it just records the creator’s reasoning and marks the text for human review.

## Potential Blind Spots
1. LLM signal: This uses an LLM to identify whether a piece of text is human written or AI generated, and identifies things like common AI-generated phrases and overall feel of the text. It therefore will miss things like uniform sentence structure, repeated phrases, and vocabulary/word choice.
2. Stylometric Heuristics Signal: This uses computation to identfy whether a piece of text is human written or AI generated and looks at sentence structure, sentence structure variation, repeated phrases, and uniform punctuation. It will miss common AI-generated phrases.
* Collectively, both signals will probably misclassify polished/formal human writing as AI-generated sometimes and might misclassify short sentences due to limited context.

## Overall Architecture
User submits text
      |
      v
POST /submit endpoint
- accepts text and user_id
- creates text_id
      |
      v
Rate Limiter
- blocks excessive requests
- allows normal submissions
      |
      v
Detection Pipeline
      |
      +--> Signal 1: LLM Signal
      |    - judges overall AI-like or human-like writing
      |    - returns llm_score
      |
      +--> Signal 2: Stylometric Heuristics Signal
           - measures sentence variation, vocabulary diversity, punctuation, repetition
           - returns heuristic_score
      |
      v
Confidence Scoring
- combines both signal scores
- produces final combined confidence score
      |
      v
Attribution Decision
- likely_ai
- likely_human
- uncertain
      |
      v
Transparency Label Generator
- creates English label text for users to read
      |
      v
Audit Log
- records text_id, user_id, signal scores, confidence, label, status (classified or under_review)
      |
      v
JSON Response
- returns text_id, attribution, confidence, label text


## Appeal Architecture

Creator submits appeal
      |
      v
POST /appeal endpoint
- accepts text_id and user_reasoning
      |
      v
Status Update
- changes status from classified to under_review
      |
      v
Audit Log
- records appeal reasoning and updated status
      |
      v
JSON Response
- confirms appeal was received






