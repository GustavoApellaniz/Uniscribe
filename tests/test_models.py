from uniscribe.domain.models import Course


def test_course_name() -> None:
    course = Course(id="1", name="Cálculo", code="MAT101", professor="Ana")
    assert course.code == "MAT101"
