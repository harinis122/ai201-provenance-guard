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


## Architecture
## Submission Flow
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


## Appeal Flow
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


## Detection Signals
What are your 2+ signals? What does each one measure? What does each signal's output look like (a score between 0–1? a binary flag?), and how will you combine them into a single confidence score?
My two signals are the LLM signal and the Stylometric Heuristics Signal. The LLM signal uses an LLM to identify whether a piece of text is human written or AI generated, and identifies things like common AI-generated phrases and overall feel of the text and outputs a score between 0-1. The Stylometric Heuristics Signal uses computation to identfy whether a piece of text is human written or AI generated and looks at sentence structure, sentence structure variation, repeated phrases, and uniform punctuation, and also outputs a score between 0-1. I will combine the two scores into a single confidence score by taking the average of both scores as both signals are equally important in evaluating the text. For both signals, 0 means strongly human-like, 1 means strongly AI-like, and 0.5 means unclear.


## Uncertainty representation
What does a confidence score of 0.6 mean to your system? How will you map raw signal outputs to a calibrated score? What threshold separates "likely AI" from "uncertain" from "likely human"?
A confidence score of 0.6 means the system sees some AI-like patterns, but not enough to confidently say that the text is AI-generated. In my system, 0.6 is still treated as uncertain.
0.00 - 0.35 = likely human-written
0.36 - 0.74 = uncertain
0.75 - 1.00 = likely AI-generated
I chose a wider uncertain range because false positives are risky. If the system incorrectly labels a human writer’s work as AI-generated, that could be unfair to the creator. Because of that, the system should only show a high-confidence AI label when the score is very high.


## Transparency label design
For a high-confidence AI result, the label will show "Our automated system found strong signs that this content may have been AI-generated". For a high-confidence human result, the label will show "Our automated system found strong signs that this content was likely written by a person". For an uncertain result, the label will just be "Our system could not confidently determine whether this content was written by a person or generated by AI".


## Appeals workflow
Who can submit an appeal? What information do they provide? What does the system do when an appeal is received — what status changes, what gets logged? What would a human reviewer see when they open the appeal queue?
A creator can submit an appeal if they think their content was incorrectly classified. The appeal is mostly meant for instances where human-written content may have been labeled as AI-generated. The POST /appeal endpoint receives the text_id and the creator’s explanation. The system finds the original decision, updates the content status to under_review, and writes a new audit log entry showing that an appeal was submitted. The system does not automatically reclassify the text after the appeal, it just records the creator’s reasoning and marks the text for human review. A confirmation response is returned to the user ("Your appeal has been received and marked for review").

## Anticipated edge cases
1. LLM signal: will miss things like uniform sentence structure, repeated phrases, and vocabulary/word choice that give away AI-generated text
2. Stylometric Heuristics Signal: will miss common AI-generated phrases (for example "increasingly important part of")
Collectively, both signals will probably misclassify polished/formal human writing as AI-generated sometimes and might misclassify short sentences as AI-generated due to their tendancy to be straighforward, uniform length, and limited context.

## AI Tool Plan
Submission Endpoint & First Signal: I will provide the AI tool with my detection signals section & architecture diagram, and I'll ask it to generate the Flask app skeleton and the first signal function. I will verify the output by testing the generated code with some inputs before adding it to the endpoint.

Second Signal & Confidence Scoring: I will provide the AI tool with the detection signals and uncertainty representation and architecture diagram, and I will ask it to generate the second signal function and scoring logic. I will check if the scores vary meaningfully between clearly AI and clearly human text.

Production Layer: I will provide the AI tool with the label variants and appeals workflow and architecture diagram, and I'll ask for the label generation logic and the /appeal endpoint. I will verify this by testing if all three label variants are reachable and if an appeal updates status correctly.

