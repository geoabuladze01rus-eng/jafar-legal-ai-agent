from jafar.search.models import SearchResult


def require_sources(results: list[SearchResult]) -> None:
    """Fail closed when a grounded legal answer has no evidence."""
    if not results:
        raise ValueError("No source evidence found for grounded legal analysis")
