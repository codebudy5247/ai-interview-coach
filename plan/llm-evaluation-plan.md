# LLM Evaluation Implementation Plan

This plan outlines a strategy for evaluating the quality, accuracy, and helpfulness of the AI-generated interview feedback in the app. We will focus entirely on **Offline Automated Evaluation** (LLM-as-a-Judge) to catch regressions or hallucinations before deploying prompt or model changes.

## 1. Golden Dataset Creation

Since we don't have an existing dataset, the first step is to generate a diverse set of test cases that cover typical user inputs.

### [NEW] `backend/evals/dataset.json`
Create a static JSON dataset containing roughly 5-10 "golden" test pairs. Each test case will have:
- `question`: The mock interview question.
- `transcript`: A simulated answer.
- `expected_behavior`: Human-readable notes on what the feedback should ideally catch (e.g., "The user completely misunderstood the question. The feedback should give a low relevance score and point out the misunderstanding.").

**Test Case Categories to Include:**
1. **The Perfect Answer:** Accurate, clear, structured. (Expected high score).
2. **The Rambler:** Technically okay, but very poorly structured and overly long. (Expected low structure/clarity score).
3. **The Blank Mind:** "Uh... I don't know." (Expected lowest possible score).
4. **The Confident Wrong Answer:** Sounds great but is technically incorrect. (Expected low correctness score).
5. **The Off-Topic Pivot:** Answers a completely different question. (Expected low relevance score).

## 2. Automated Evaluation Script (LLM-as-a-Judge)

This phase introduces the automated testing suite to measure the performance of `feedback_service.py` against our golden dataset. We will use a strong LLM (like Gemini) to act as a "Judge".

### [NEW] `backend/evals/run_eval.py`
Create a standalone CLI script that orchestrates the evaluation:
1. **Load Data:** Reads `dataset.json`.
2. **Generate Feedback:** Passes each `(question, transcript)` pair through the existing `get_feedback()` function in our app.
3. **Judge the Output:** Passes the *app's generated feedback* along with the original question and transcript to an **Eval LLM** (acting as a judge).
4. **Scoring Criteria:** The Eval LLM will score the generated feedback (1-5 scale) on:
   - **Accuracy**: Did the feedback correctly identify flaws in the transcript?
   - **Actionability**: Are the `improvements` concrete and useful?
   - **Hallucination**: Did the feedback invent details not present in the transcript?
5. **Report Generation:** Output a clear summary report to the console (and optionally a `.md` file in `evals/reports/`) detailing average scores and any flagged regressions.

## Implementation Phases

### Phase 1: Dataset Generation
- Draft the `dataset.json` with 10-15 varied test cases representing different types of interview answers.

### Phase 2: Evaluation Script
- Create `run_eval.py`.
- Implement the "Judge" prompt (using the `google-genai` SDK directly inside the script).
- Tie it together so it loops through the dataset and outputs the final scores.

## Verification Plan
1. Run `python -m evals.run_eval` from the backend directory.
2. Verify that the script successfully evaluates all test cases and generates a final report.
3. Temporarily break the prompt in `feedback_service.py` (e.g., tell it to always give a score of 10) and verify that the Eval script catches the regression and gives it a poor "Accuracy" score.
