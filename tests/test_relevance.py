import pytest

from relevance import calculate_hybrid_score


def test_results_sorted_by_final_score():
    items = [{"chunk": "unrelated text", "score": 2.0}, {"chunk": "close match", "score": 0.1}]
    ranked = calculate_hybrid_score(items, "Student", "Exam Preparation", "")
    scores = [r["final_score"] for r in ranked]
    assert scores == sorted(scores, reverse=True)
    assert ranked[0]["chunk"] == "close match"


def test_persona_keywords_raise_score():
    plain = calculate_hybrid_score([{"chunk": "x y z", "score": 1.0}], "Student", "Exam Preparation", "")
    boosted = calculate_hybrid_score([{"chunk": "define the important difference", "score": 1.0}],
                                     "Student", "Exam Preparation", "")
    assert boosted[0]["final_score"] > plain[0]["final_score"]


@pytest.mark.xfail(strict=True, reason="Audit M1: query overlap uses substring matching; fixed in Milestone 2")
def test_query_overlap_matches_whole_words_only():
    # "is" should not match inside "this"
    with_q = calculate_hybrid_score([{"chunk": "this", "score": 1.0}], "Student", "Exam Preparation", "is")
    without_q = calculate_hybrid_score([{"chunk": "this", "score": 1.0}], "Student", "Exam Preparation", "")
    assert with_q[0]["final_score"] == without_q[0]["final_score"]
