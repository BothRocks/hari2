from app.services.quality.scorer import calculate_quality_score, QualityGrade, get_grade


class TestQualityGradeEnum:
    """Test QualityGrade enum values."""

    def test_quality_grade_a(self):
        assert QualityGrade.A.value == "A"

    def test_quality_grade_b(self):
        assert QualityGrade.B.value == "B"

    def test_quality_grade_c(self):
        assert QualityGrade.C.value == "C"

    def test_quality_grade_d(self):
        assert QualityGrade.D.value == "D"

    def test_quality_grade_all_values(self):
        """Verify all grade values exist."""
        grades = [grade.value for grade in QualityGrade]
        assert grades == ["A", "B", "C", "D"]


class TestCalculateQualityScore:
    """Test calculate_quality_score function."""

    def test_complete_document_optimal(self):
        """Test with all optimal values."""
        score = calculate_quality_score(
            summary="A good summary with enough content. " * 100,  # ~4000 chars
            quick_summary="Brief but sufficient summary that meets minimum requirements",
            keywords=["key1", "key2", "key3", "key4", "key5"],
            industries=["Tech"],
            has_embedding=True,
        )
        assert 90 <= score <= 100

    def test_empty_document(self):
        """Test with all empty/None values."""
        score = calculate_quality_score()
        assert score == 0.0

    def test_none_values(self):
        """Test with explicit None values."""
        score = calculate_quality_score(
            summary=None,
            quick_summary=None,
            keywords=None,
            industries=None,
            has_embedding=False,
        )
        assert score == 0.0

    # Summary quality tests (40% weight)
    def test_summary_optimal_length(self):
        """Test summary with optimal length (800-2500 chars) scores 40%."""
        summary = "x" * 1500  # Optimal length
        score = calculate_quality_score(summary=summary)
        assert score == 40.0

    def test_summary_good_length_short(self):
        """Test summary with good but suboptimal length (400-800 chars) scores 30%."""
        summary = "x" * 600  # Good but short
        score = calculate_quality_score(summary=summary)
        assert score == 30.0

    def test_summary_good_length_long(self):
        """Test summary with good but suboptimal length (2500-4000 chars) scores 30%."""
        summary = "x" * 3000  # Good but long
        score = calculate_quality_score(summary=summary)
        assert score == 30.0

    def test_summary_poor_length(self):
        """Test summary with poor length (<400 or >4000 chars) scores 15%."""
        summary = "x" * 100  # Too short
        score = calculate_quality_score(summary=summary)
        assert score == 15.0

    def test_summary_empty_string(self):
        """Test empty summary scores 0%."""
        score = calculate_quality_score(summary="")
        assert score == 0.0

    # Quick summary tests (10% weight)
    def test_quick_summary_sufficient(self):
        """Test quick summary with sufficient length (>=50 chars) scores 10%."""
        quick_summary = "x" * 60
        score = calculate_quality_score(quick_summary=quick_summary)
        assert score == 10.0

    def test_quick_summary_minimum_length(self):
        """Test quick summary with exactly 50 chars scores 10%."""
        quick_summary = "x" * 50
        score = calculate_quality_score(quick_summary=quick_summary)
        assert score == 10.0

    def test_quick_summary_too_short(self):
        """Test quick summary with insufficient length (<50 chars) scores 0%."""
        quick_summary = "x" * 49
        score = calculate_quality_score(quick_summary=quick_summary)
        assert score == 0.0

    def test_quick_summary_empty(self):
        """Test empty quick summary scores 0%."""
        score = calculate_quality_score(quick_summary="")
        assert score == 0.0

    # Keywords tests (15% weight)
    def test_keywords_optimal_count(self):
        """Test keywords with optimal count (5-10) scores 15%."""
        keywords = ["key1", "key2", "key3", "key4", "key5"]
        score = calculate_quality_score(keywords=keywords)
        assert score == 15.0

    def test_keywords_optimal_max(self):
        """Test keywords with 10 items scores 15%."""
        keywords = [f"key{i}" for i in range(10)]
        score = calculate_quality_score(keywords=keywords)
        assert score == 15.0

    def test_keywords_suboptimal(self):
        """Test keywords with suboptimal count scores 8%."""
        keywords = ["key1", "key2"]
        score = calculate_quality_score(keywords=keywords)
        assert score == 8.0

    def test_keywords_single(self):
        """Test single keyword scores 8%."""
        keywords = ["key1"]
        score = calculate_quality_score(keywords=keywords)
        assert score == 8.0

    def test_keywords_too_many(self):
        """Test keywords with >10 items scores 8%."""
        keywords = [f"key{i}" for i in range(15)]
        score = calculate_quality_score(keywords=keywords)
        assert score == 8.0

    def test_keywords_empty_list(self):
        """Test empty keywords list scores 0%."""
        score = calculate_quality_score(keywords=[])
        assert score == 0.0

    # Industries tests (15% weight)
    def test_industries_present(self):
        """Test industries present scores 15%."""
        industries = ["Tech"]
        score = calculate_quality_score(industries=industries)
        assert score == 15.0

    def test_industries_multiple(self):
        """Test multiple industries scores 15%."""
        industries = ["Tech", "Finance", "Healthcare"]
        score = calculate_quality_score(industries=industries)
        assert score == 15.0

    def test_industries_empty_list(self):
        """Test empty industries list scores 0%."""
        score = calculate_quality_score(industries=[])
        assert score == 0.0

    # Embedding tests (20% weight)
    def test_has_embedding_true(self):
        """Test has_embedding=True scores 20%."""
        score = calculate_quality_score(has_embedding=True)
        assert score == 20.0

    def test_has_embedding_false(self):
        """Test has_embedding=False scores 0%."""
        score = calculate_quality_score(has_embedding=False)
        assert score == 0.0

    # Combination tests
    def test_combined_partial_score(self):
        """Test combination of components."""
        score = calculate_quality_score(
            summary="x" * 1500,  # 40%
            keywords=["key1", "key2"],  # 8%
            has_embedding=True,  # 20%
        )
        assert score == 68.0

    def test_score_capped_at_100(self):
        """Test score is capped at 100."""
        # Even if somehow we exceed 100, it should be capped
        score = calculate_quality_score(
            summary="x" * 1500,  # 40%
            quick_summary="x" * 60,  # 10%
            keywords=["key1", "key2", "key3", "key4", "key5"],  # 15%
            industries=["Tech"],  # 15%
            has_embedding=True,  # 20%
        )
        # Total: 100%
        assert score == 100.0
        assert score <= 100.0

    def test_score_range_valid(self):
        """Test score is always between 0 and 100."""
        test_cases = [
            {},
            {"summary": "test"},
            {"summary": "x" * 1500, "has_embedding": True},
            {"summary": "x" * 1500, "quick_summary": "x" * 60, "keywords": ["k1", "k2", "k3", "k4", "k5"], "industries": ["Tech"], "has_embedding": True},
        ]
        for params in test_cases:
            score = calculate_quality_score(**params)
            assert 0 <= score <= 100


class TestGetGrade:
    """Test get_grade function."""

    def test_grade_a_minimum(self):
        """Test score 90 gets grade A."""
        grade = get_grade(90.0)
        assert grade == QualityGrade.A

    def test_grade_a_maximum(self):
        """Test score 100 gets grade A."""
        grade = get_grade(100.0)
        assert grade == QualityGrade.A

    def test_grade_a_mid(self):
        """Test score 95 gets grade A."""
        grade = get_grade(95.0)
        assert grade == QualityGrade.A

    def test_grade_b_minimum(self):
        """Test score 70 gets grade B."""
        grade = get_grade(70.0)
        assert grade == QualityGrade.B

    def test_grade_b_maximum(self):
        """Test score 89.9 gets grade B."""
        grade = get_grade(89.9)
        assert grade == QualityGrade.B

    def test_grade_b_mid(self):
        """Test score 80 gets grade B."""
        grade = get_grade(80.0)
        assert grade == QualityGrade.B

    def test_grade_c_minimum(self):
        """Test score 50 gets grade C."""
        grade = get_grade(50.0)
        assert grade == QualityGrade.C

    def test_grade_c_maximum(self):
        """Test score 69.9 gets grade C."""
        grade = get_grade(69.9)
        assert grade == QualityGrade.C

    def test_grade_c_mid(self):
        """Test score 60 gets grade C."""
        grade = get_grade(60.0)
        assert grade == QualityGrade.C

    def test_grade_d_maximum(self):
        """Test score 49.9 gets grade D."""
        grade = get_grade(49.9)
        assert grade == QualityGrade.D

    def test_grade_d_mid(self):
        """Test score 25 gets grade D."""
        grade = get_grade(25.0)
        assert grade == QualityGrade.D

    def test_grade_d_minimum(self):
        """Test score 0 gets grade D."""
        grade = get_grade(0.0)
        assert grade == QualityGrade.D

    def test_grade_thresholds(self):
        """Test all grade boundary thresholds."""
        assert get_grade(90.0) == QualityGrade.A
        assert get_grade(89.999) == QualityGrade.B
        assert get_grade(70.0) == QualityGrade.B
        assert get_grade(69.999) == QualityGrade.C
        assert get_grade(50.0) == QualityGrade.C
        assert get_grade(49.999) == QualityGrade.D
