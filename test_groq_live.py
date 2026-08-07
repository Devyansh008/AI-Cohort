import json
import os
import sys

# Ensure the .env variables are loaded (or already present in the environment)
from dotenv import load_dotenv
load_dotenv()

from fastapi.testclient import TestClient
from app.main import app

def main():
    client = TestClient(app)
    
    # 1. Load candidate data
    with open("data/candidate.json", "r") as f:
        data = json.load(f)
        
    # Find Sarah Johnson (CAND-001)
    sarah = None
    for cand in data.get("candidates", []):
        if cand["member"]["id"] == "CAND-001":
            sarah = cand
            break
            
    if not sarah:
        print("Error: Could not find CAND-001 in candidate.json")
        sys.exit(1)
        
    print("--- 🚀 RUNNING LIVE INTEGRATION TEST WITH GROQ ---")
    print(f"Model: {os.environ.get('GROQ_MODEL')}")
    print(f"Candidate: {sarah['member']['name']} ({sarah['member']['jobRole']})")
    print("--------------------------------------------------\n")
    
    # 2. Make the live API call (this will hit Groq via the LLMService)
    payload = {
        "sessionId": "live-test-groq-001",
        "candidate": sarah
    }
    
    print("Sending POST /api/interview ...")
    response = client.post("/api/interview", json=payload)
    
    # 3. Print the results
    if response.status_code == 200:
        print("\n✅ SUCCESS! (200 OK)")
        print("\n--- 🤖 AGENT RESPONSE ---\n")
        print(response.json()["message"])
        print("\n-------------------------\n")
    else:
        print(f"\n❌ FAILED! ({response.status_code})")
        print(response.text)

if __name__ == "__main__":
    main()
