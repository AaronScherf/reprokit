from reprokit.problems import Problem


def test_problem_str_names_file_field_and_message():
    assert str(Problem("a.yaml", "deliverables[0].audience", "required")) == "a.yaml: deliverables[0].audience: required"