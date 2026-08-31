import asyncio

from app.question_history import QuestionAnswerStore, normalize_question_text, question_key


def test_question_normalization_keeps_calculations_distinct():
    assert normalize_question_text("  What is 2 + 2? ") == "what is 2 + 2"
    assert question_key("CPA", "What is 2 + 2?") != question_key("CPA", "What is 2 - 2?")


def test_txt_store_reuses_only_valid_stage_one_answer(tmp_path):
    store = QuestionAnswerStore(str(tmp_path / "question_answers.txt"))

    asyncio.run(
        store.append(
            course="CPA",
            question="Explain audit risk?",
            answer="First approved answer",
            stage=1,
            reusable=True,
        )
    )
    asyncio.run(
        store.append(
            course="CPA",
            question="Explain audit risk?",
            answer="Second deeper answer",
            stage=2,
            reusable=False,
        )
    )

    found = asyncio.run(store.find_first_answer(course="CPA", question="Explain audit risk."))

    assert found is not None
    assert found["answer"] == "First approved answer"


def test_history_write_failure_does_not_fail_a_valid_answer(tmp_path, monkeypatch):
    store = QuestionAnswerStore(str(tmp_path / "question_answers.txt"))

    def deny_write(record):
        raise PermissionError(13, "Permission denied", str(store.path))

    monkeypatch.setattr(store, "_append_sync", deny_write)

    asyncio.run(
        store.append(
            course="CMA",
            question="Explain contribution margin.",
            answer="Contribution margin is sales less variable costs.",
            stage=1,
            reusable=True,
        )
    )
