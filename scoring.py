LIKELY_HUMAN_MAX = 0.40
LIKELY_AI_MIN = 0.65


def combine_scores(llm_score, heuristic_score):
    """Combine the two signal scores into one confidence score."""
    return 0.7 * llm_score + 0.3 * heuristic_score


def attribution_from_score(confidence_score):
    """Map a combined confidence score to likely_human / uncertain / likely_ai."""
    if confidence_score <= LIKELY_HUMAN_MAX:
        return "likely_human"
    if confidence_score >= LIKELY_AI_MIN:
        return "likely_ai"
    return "uncertain"
