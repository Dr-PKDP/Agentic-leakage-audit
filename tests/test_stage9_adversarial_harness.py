def test_adversarial_fixture_expectations_are_met():
    from src.stage9_adversarial_harness import evaluate_fixtures

    report = evaluate_fixtures()

    assert report["overall_status"] == "pass"
    assert report["fixture_count"] == 8
    assert report["matched_expectations"] == 8


def test_each_failing_fixture_is_blocked():
    from src.stage9_adversarial_harness import evaluate_fixtures

    report = evaluate_fixtures()

    failures = [
        item
        for item in report["results"]
        if item["expected_status"] == "fail"
    ]

    assert len(failures) == 7
    assert all(item["observed_status"] == "fail" for item in failures)


def test_valid_fixture_remains_approved():
    from src.stage9_adversarial_harness import evaluate_fixtures

    report = evaluate_fixtures()

    valid = next(
        item
        for item in report["results"]
        if item["id"] == "valid_screening_model"
    )

    assert valid["observed_status"] == "pass"