"""
prompts.py
----------
Prompt engineering for interview feedback generation, kept separate from the
provider/transport logic in feedback_service.py so prompts can be tuned and
versioned independently.

Public surface:
  RUBRIC          — scoring dimensions + per-dimension guidance
  EXAMPLE_OUTPUT  — concrete JSON schema example shown to the model
  build_prompt()  — assembles the full evaluation prompt
"""

import json
from textwrap import dedent

# ---------------------------------------------------------------------------
# Scoring rubric — centralised so it's easy to tune weights / criteria
# ---------------------------------------------------------------------------
RUBRIC: dict[str, str] = {
    "correctness": "Technical accuracy and depth — are the claims true, precise, and complete?",
    "clarity": "How easy the answer is to follow for a competent listener; concise and unambiguous.",
    "structure": "Logical flow: clear opening, ordered body, and a conclusion (STAR/PREP preferred).",
    "relevance": "How directly and completely the answer addresses every part of what was asked.",
}

# Score calibration anchors — gives the model concrete reference points so
# scores stay consistent across runs and don't cluster around 7.
SCORE_ANCHORS = dedent(
    """
    - 9-10: Excellent. Accurate, complete, well-structured; a strong-hire answer.
    - 7-8:  Good. Mostly correct and clear, minor gaps or imprecision.
    - 5-6:  Borderline. Core idea present but notable gaps, vagueness, or missing parts.
    - 3-4:  Weak. Significant errors, omissions, or fails to address the question.
    - 1-2:  Poor. Largely incorrect, irrelevant, or essentially no substance.
    """
).strip()

# JSON schema shown to the model as a concrete example
EXAMPLE_OUTPUT = {
    "overall_score": 7,
    "scores": {dim: {"score": 7, "feedback": "..."} for dim in RUBRIC},
    "what_went_well": ["point 1", "point 2"],
    "what_was_missed": ["point 1", "point 2"],
    "improvements": ["actionable suggestion 1", "actionable suggestion 2"],
    "ideal_answer": "A complete model answer to this question.",
    "ideal_code": "// Code snippet accompanying the ideal answer, if applicable",
}


def build_prompt(
    question: str,
    transcript: str,
    code_snippet: str | None = None,
    code_language: str | None = None,
) -> str:
    """
    Build the evaluation prompt used by Azure OpenAI / Gemini.

    Design choices
    --------------
    * Role + hiring-bar framing up front — LLMs attend more strongly to early tokens.
    * Explicit rubric + numeric calibration anchors keep scores consistent and
      prevent clustering around 7.
    * Anti-hallucination guardrails: judge only what was actually said, and treat
      obvious speech-to-text artifacts charitably (the answer was spoken, not typed).
    * Optional code section so the model can critique code the candidate discussed.
    * JSON schema is generated programmatically so it stays in sync with RUBRIC.
    * Negative constraints ("JSON only") are placed right before the output
      request, where recency makes them most effective.
    """
    if not question.strip():
        raise ValueError("question must not be blank")
    if not transcript.strip():
        raise ValueError("transcript must not be blank")

    rubric_block = "\n".join(
        f"  - {dim} (1-10): {desc}" for dim, desc in RUBRIC.items()
    )
    schema = json.dumps(EXAMPLE_OUTPUT, indent=2)

    code_section = ""
    code_instruction = ""
    if code_snippet and code_snippet.strip():
        lang = code_language or ""
        code_section = dedent(f"""
            ## Code Snippet Under Discussion
            The candidate was given this code to read, explain, or improve:
            ```{lang}
            {code_snippet}
            ```
        """)
        code_instruction = (
            "- Factor the code into your scoring: did the candidate read it correctly, "
            "spot bugs/edge cases, and reason about complexity? Make `ideal_code` a "
            "corrected/improved version relevant to this snippet.\n        "
        )

    return dedent(f"""
        You are a senior software engineer and experienced interviewer evaluating a
        candidate's spoken answer in a mock technical interview. Hold the answer to a
        real hiring bar: be honest, specific, and constructive. Reward correct
        substance over confident-sounding filler.

        ## Interview Question
        {question.strip()}
{code_section}
        ## Candidate's Answer (auto-transcribed from audio)
        {transcript.strip()}

        ## Grounding rules (read carefully)
        - Evaluate ONLY what the candidate actually said. Do not invent strengths,
          claims, or mistakes that are not in the transcript.
        - The answer was SPOKEN and machine-transcribed. Do not penalize obvious
          transcription artifacts (e.g. "laxical" for "lexical", run-on punctuation);
          judge the intended meaning. Do flag genuine conceptual errors.
        - If the answer is empty, off-topic, or far too short to assess, score it low
          and say why — do not pad it with generic praise.

        ## Evaluation Rubric
        Score each dimension from 1 (poor) to 10 (excellent):
        {rubric_block}

        ## Score calibration
        {SCORE_ANCHORS}

        ## Instructions
        - Be strict but fair; a 9-10 requires a near-complete, precise answer.
        - Per-dimension `feedback` must be 1-2 concrete sentences that quote or
          reference what was said — no generic praise.
        - `what_went_well` and `what_was_missed` should each have 2-4 specific bullets.
        - `improvements` must be concrete and actionable (e.g. "State the Big-O and
          why", "Give one real-world use case"), not vague advice like "be clearer".
        - `ideal_answer` is a complete, concise model answer (3-5 sentences).
        - `ideal_code` is an accompanying snippet when the question is code-related,
          else an empty string.
        {code_instruction}- `overall_score` is your holistic judgment, NOT a simple average of dimensions.

        ## Output
        Return ONLY a valid JSON object matching this exact shape. No markdown
        fences, no commentary, no trailing text.

        {schema}
    """).strip()
