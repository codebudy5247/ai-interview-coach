import requests
import time
import json
import os

BASE_URL = "http://localhost:8000/api"
TEST_AUDIO = "temp/closure.mp3"

def run_test(name, payload, expected_code=True, expect_language=None):
    print(f"\n--- Running Test: {name} ---")
    
    # 1. Start analysis
    files = {"audio": ("closure.mp3", open(TEST_AUDIO, "rb"), "audio/mpeg")}
    data = {"question": payload["question"]}
    if "code_snippet" in payload:
        data["code_snippet"] = payload["code_snippet"]
    if "code_language" in payload:
        data["code_language"] = payload["code_language"]
        
    print("Submitting POST /api/analyze...")
    resp = requests.post(f"{BASE_URL}/analyze", data=data, files=files)
    if resp.status_code != 200:
        print(f"FAILED to start analysis: {resp.text}")
        return False
        
    session_id = resp.json()["session_id"]
    print(f"Session ID: {session_id}")
    
    # 2. Poll for feedback
    print("Polling for feedback...", end="", flush=True)
    feedback = None
    for _ in range(60): # up to 60 seconds
        time.sleep(2)
        print(".", end="", flush=True)
        r = requests.get(f"{BASE_URL}/feedback/{session_id}")
        if r.status_code == 200:
            feedback = r.json()
            break
        elif r.status_code == 500:
            print(f"\nPipeline failed: {r.text}")
            return False
    print()
    
    if not feedback:
        print("Timeout waiting for feedback.")
        return False
        
    print("Feedback received!")
    
    # 3. Verify
    success = True
    if expected_code:
        if "code_snippet" not in feedback or not feedback["code_snippet"]:
            print("ERROR: Expected code_snippet in feedback, but it was missing.")
            success = False
        if expect_language and feedback.get("code_language") != expect_language:
            print(f"ERROR: Expected language {expect_language}, got {feedback.get('code_language')}")
            success = False
    else:
        if feedback.get("code_snippet"):
            print("ERROR: Did not expect code_snippet, but one was returned.")
            success = False
            
    if success:
        print("✅ TEST PASSED")
    else:
        print("❌ TEST FAILED")
        
    return success

if __name__ == "__main__":
    if not os.path.exists(TEST_AUDIO):
        print(f"ERROR: Missing test audio file at {TEST_AUDIO}. Please provide one.")
        exit(1)
        
    # Test 1: With code
    run_test("With Code", {
        "question": "What does this code do?",
        "code_snippet": "def hello():\n    print('world')",
        "code_language": "python"
    }, expected_code=True, expect_language="python")
    
    # Test 2: Without code
    run_test("Without Code", {
        "question": "Explain closures."
    }, expected_code=False)
    
    # Test 3: Empty code
    run_test("Empty Code", {
        "question": "Explain closures.",
        "code_snippet": "   \n  "
    }, expected_code=False)
    
    # Test 4: Long code
    long_code = "print('hello')\n" * 200 # approx 3000 chars
    run_test("Long Code", {
        "question": "What is this?",
        "code_snippet": long_code,
        "code_language": "python"
    }, expected_code=True, expect_language="python")
    
    # Test 5: Language tag
    run_test("Language Tag Only", {
        "question": "Explain this.",
        "code_snippet": "console.log('test');",
        "code_language": "javascript"
    }, expected_code=True, expect_language="javascript")
