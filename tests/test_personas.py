from personas import PERSONA_HIERARCHY, get_persona_data


def test_every_persona_has_required_fields():
    for role, subs in PERSONA_HIERARCHY.items():
        assert subs, role
        for name, data in subs.items():
            for key in ("intent", "keywords", "prompt_style"):
                assert data.get(key), f"{role}/{name} missing {key}"


def test_known_persona_lookup():
    data = get_persona_data("Teacher", "Quiz Generation")
    assert "quiz" in data["keywords"]


def test_unknown_persona_falls_back_to_default():
    # Current behaviour (audit finding M2); Milestone 2 changes this to a validation error.
    assert get_persona_data("Nope", "Nope") is PERSONA_HIERARCHY["Student"]["First Year (Basics)"]
