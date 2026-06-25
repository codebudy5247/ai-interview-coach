import requests, time

files = {"audio": ("closure.mp3", open("temp/closure.mp3", "rb"), "audio/mpeg")}
data = {
    "question": "How do closures work in Python?",
    "code_snippet": "def a(): pass",
    "code_language": "python",
}
resp = requests.post("http://localhost:8000/api/analyze", data=data, files=files).json()
session_id = resp["session_id"]
for _ in range(30):
    r = requests.get(f"http://localhost:8000/api/feedback/{session_id}")
    if r.status_code == 200:
        fb = r.json()
        print("Ideal code snippet:")
        print(fb.get("ideal_code"))
        break
    time.sleep(2)
