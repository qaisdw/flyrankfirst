import json
import requests

API_URL = "[http://127.0.0.1:8000/triage](http://127.0.0.1:8000/triage)"

def run_evals():
    with open("evals/cases.json", "r") as f:
        cases = json.load(f)
    
    correct = 0
    failed_cases = []

    for idx, case in enumerate(cases):
        print(f"Testing case {idx+1}/{len(cases)}...")
        try:
            res = requests.post(API_URL, json={"text": case["input"]})
            if res.status_code == 200:
                data = res.json()
                if data["category"] == case["expected_category"]:
                    correct += 1
                else:
                    failed_cases.append({"input": case["input"], "expected": case["expected_category"], "got": data["category"]})
            else:
                failed_cases.append({"input": case["input"], "error": res.status_code})
        except Exception as e:
            failed_cases.append({"input": case["input"], "error": str(e)})

    print("\n=== EVALUATION RESULTS ===")
    print(f"Score: {correct} out of {len(cases)}")
    
    if failed_cases:
        print("\nFailed Cases:")
        for fc in failed_cases:
            print(fc)

if __name__ == "__main__":
    run_evals()