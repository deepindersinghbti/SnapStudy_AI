import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import Quiz, QuizResult, User
from app.schemas import QuizScoreRequest, QuizScoreResponse

router = APIRouter(prefix="/quizzes", tags=["quizzes"])


@router.post("/score", response_model=QuizScoreResponse)
def score_quiz(
    payload: QuizScoreRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> QuizScoreResponse:
    quiz = db.query(Quiz).filter(Quiz.id == payload.quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    answer_key = json.loads(quiz.answer_key_json)
    user_answers = payload.answers

    total = len(answer_key)
    correct = sum(
        1 for i, answer in enumerate(user_answers[:total]) if answer == answer_key[i]
    )
    score = round((correct / total) * 100, 2) if total > 0 else 0.0

    result = QuizResult(
        quiz_id=quiz.id,
        user_id=current_user.id,
        submitted_answers_json=json.dumps(user_answers),
        score=score,
    )
    db.add(result)
    db.commit()

    return QuizScoreResponse(
        quiz_id=quiz.id,
        score=score,
        total_questions=total,
        correct_answers=correct,
    )
