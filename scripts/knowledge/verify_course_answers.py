import json

import httpx


COURSE_QUESTIONS = {
    "CMA": "Explain contribution margin and calculate it when sales are 100000 and variable costs are 60000.",
    "CPA": "Explain sufficient appropriate audit evidence and why both quantity and quality matter.",
    "CFA": "Explain bond duration and what happens to bond price when market yield increases.",
    "ACCA": "Explain material price variance with its formula and a simple numerical example.",
    "CS": "Explain the purpose of board meeting minutes and the main compliance points they should record.",
    "EA": "Explain the difference between a tax deduction and a tax credit with a simple example.",
}


def main() -> None:
    results = []
    with httpx.Client(timeout=120.0) as client:
        for course, question in COURSE_QUESTIONS.items():
            response = client.post(
                "http://localhost:8000/v1/chat",
                json={
                    "student_id": "multi-course-live-check",
                    "course": course,
                    "message": question,
                    "level": "beginner",
                    "mode": "doubt_solving",
                    "use_cache": False,
                },
            )
            payload = response.json()
            answer = str(payload.get("answer") or "")
            results.append(
                {
                    "course": course,
                    "status": response.status_code,
                    "answer_chars": len(answer),
                    "refused": "not related to your enrolled" in answer.lower(),
                    "sources": len(payload.get("sources") or []),
                }
            )
    print(json.dumps(results))


if __name__ == "__main__":
    main()
