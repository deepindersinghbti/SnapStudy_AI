import json


def generate_quiz_from_text(extracted_text: str) -> tuple[str, str]:
    questions = [
        {
            "question": "What is the primary topic discussed in the uploaded page?",
            "options": [
                "A definition",
                "A process",
                "A historical event",
                "A mathematical proof",
            ],
        },
        {
            "question": "Which statement best matches the main idea?",
            "options": ["Option A", "Option B", "Option C", "Option D"],
        },
    ]
    answer_key = ["A definition", "Option A"]
    return json.dumps(questions), json.dumps(answer_key)
