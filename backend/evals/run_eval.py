import json
import os
import sys
from pathlib import Path
from datetime import datetime
from pydantic import BaseModel

# Add backend directory to sys.path so we can import services
sys.path.append(str(Path(__file__).resolve().parent.parent))

from google import genai
from google.genai import types
from dotenv import load_dotenv

from services.feedback_service import get_feedback

# Load environment variables (GEMINI_API_KEY)
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = "gemini-3-flash-preview"

class EvalScore(BaseModel):
    accuracy: int
    actionability: int
    hallucination: int
    rationale: str

def run_evaluation():
    if not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY is not set in backend/.env")
        sys.exit(1)

    evals_dir = Path(__file__).parent
    dataset_path = evals_dir / "dataset.json"
    reports_dir = evals_dir / "reports"
    reports_dir.mkdir(exist_ok=True)

    if not dataset_path.exists():
        print(f"Error: Dataset not found at {dataset_path}")
        sys.exit(1)

    with open(dataset_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)[:5]  # Limit to 5 test cases to avoid rate limits

    client = genai.Client(api_key=GEMINI_API_KEY)
    results = []
    
    print(f"Starting evaluation of {len(dataset)} test cases using {GEMINI_MODEL}...")
    print("-" * 50)
    
    for i, tc in enumerate(dataset):
        tc_id = tc["id"]
        print(f"[{i+1}/{len(dataset)}] Evaluating {tc_id} ({tc['category']})...")
        
        # 1. Generate feedback using our app's pipeline
        try:
            # We don't pass on_status callback to keep the console clean
            feedback = get_feedback(tc["question"], tc["transcript"])
        except Exception as e:
            print(f"  ❌ Error generating feedback: {e}")
            continue
            
        # 2. Judge the feedback
        judge_prompt = f"""
You are an expert prompt engineer and quality assurance judge.
Your task is to evaluate the quality of an AI-generated interview feedback report.

# Original Interview Question
{tc["question"]}

# Candidate's Transcript
{tc["transcript"]}

# Expected Behavior for this test case
{tc["expected_behavior"]}

# Generated Feedback from Pipeline
{json.dumps(feedback, indent=2)}

# Evaluation Criteria
Score the Generated Feedback on a scale of 1 to 5 for each metric (5 is best):
- accuracy (1-5): Did the feedback correctly identify flaws and strengths? Did it align with the 'Expected Behavior'?
- actionability (1-5): Are the 'improvements' concrete and useful?
- hallucination (1-5): Did the feedback invent details not present in the transcript? (5 = no hallucination at all, 1 = severe hallucination/completely made up)

Return the result as a JSON object matching the requested schema.
"""
        
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=judge_prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=EvalScore,
                )
            )
            
            # The API returns the JSON string in response.text
            score_data = json.loads(response.text)
            
            results.append({
                "id": tc_id,
                "category": tc["category"],
                "expected_behavior": tc["expected_behavior"],
                "scores": score_data,
                "generated_feedback": feedback
            })
            print(f"  ✅ Scores - Accuracy: {score_data['accuracy']}/5, Actionability: {score_data['actionability']}/5, Hallucination: {score_data['hallucination']}/5")
            print(f"  📝 Rationale: {score_data['rationale']}\n")
            
        except Exception as e:
            print(f"  ❌ Error judging feedback: {e}")
            
    # Calculate averages and generate report
    if not results:
        print("No successful evaluations to report.")
        return
        
    avg_acc = sum(r["scores"]["accuracy"] for r in results) / len(results)
    avg_act = sum(r["scores"]["actionability"] for r in results) / len(results)
    avg_hall = sum(r["scores"]["hallucination"] for r in results) / len(results)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = reports_dir / f"eval_report_{timestamp}.md"
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# LLM Evaluation Report\n\n")
        f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Model:** {GEMINI_MODEL}\n")
        f.write(f"**Total Test Cases:** {len(results)} / {len(dataset)}\n\n")
        f.write("## Average Scores (out of 5)\n")
        f.write(f"- **Accuracy:** {avg_acc:.2f}\n")
        f.write(f"- **Actionability:** {avg_act:.2f}\n")
        f.write(f"- **Anti-Hallucination (5=None):** {avg_hall:.2f}\n\n")
        f.write("---\n\n")
        f.write("## Detailed Results\n\n")
        
        for r in results:
            f.write(f"### {r['id']} ({r['category']})\n")
            f.write(f"**Expected Behavior:** {r['expected_behavior']}\n\n")
            f.write(f"**Scores:**\n")
            f.write(f"- Accuracy: {r['scores']['accuracy']}/5\n")
            f.write(f"- Actionability: {r['scores']['actionability']}/5\n")
            f.write(f"- Hallucination: {r['scores']['hallucination']}/5\n\n")
            f.write(f"**Judge Rationale:**\n> {r['scores']['rationale']}\n\n")
            f.write("<details>\n<summary>View Generated Feedback</summary>\n\n```json\n")
            f.write(json.dumps(r['generated_feedback'], indent=2))
            f.write("\n```\n</details>\n\n---\n\n")
            
    print("-" * 50)
    print(f"Evaluation complete! Averages:")
    print(f"Accuracy: {avg_acc:.2f} | Actionability: {avg_act:.2f} | Hallucination: {avg_hall:.2f}")
    print(f"Report saved to: {report_path}")

if __name__ == "__main__":
    run_evaluation()
