from app.repository import CourseRepository, MemoryCourseRepository, SupabaseCourseRepository


def test_both_repositories_implement_every_protocol_method() -> None:
    protocol_methods = [name for name in dir(CourseRepository) if not name.startswith("_")]

    for method_name in protocol_methods:
        assert callable(getattr(MemoryCourseRepository, method_name, None)), (
            f"MemoryCourseRepository is missing '{method_name}' from the CourseRepository protocol."
        )
        assert callable(getattr(SupabaseCourseRepository, method_name, None)), (
            f"SupabaseCourseRepository is missing '{method_name}' from the CourseRepository protocol."
        )
