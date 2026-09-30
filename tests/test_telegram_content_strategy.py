from jafar.telegram_content_strategy import (
    AggregatingSourceMonitor,
    ContentPillar,
    ImagePromptGenerator,
    SevenDayPlanner,
    SourceItem,
    TopicCandidate,
    TopicDimensions,
    TopicScorer,
)


class StaticMonitor:
    def __init__(self, items):
        self.items = items

    def collect(self):
        return self.items


def candidate(candidate_id: str, pillar: str, **overrides):
    dims = {
        "relevance": 90,
        "legal_value": 80,
        "practical_value": 90,
        "author_unique_angle": 90,
        "shareability": 80,
        "timeliness": 80,
        "risk": 5,
        "duplication": 5,
    }
    dims.update(overrides.pop("dimensions", {}))
    return TopicCandidate(
        candidate_id=candidate_id,
        title=overrides.pop("title", candidate_id),
        pillar=pillar,
        is_news=overrides.pop("is_news", False),
        dimensions=TopicDimensions(**dims),
        **overrides,
    )


def test_source_monitor_deduplicates_canonical_urls() -> None:
    first = SourceItem(title="Тема", url="https://example.com/item?utm_source=x")
    second = SourceItem(title="Тема", url="https://example.com/item")
    monitor = AggregatingSourceMonitor([StaticMonitor([first]), StaticMonitor([second])])
    assert len(monitor.collect()) == 1


def test_good_topic_is_eligible() -> None:
    score = TopicScorer().score(candidate("a", "what_to_do"))
    assert score.eligible is True
    assert score.score >= 65


def test_high_risk_topic_is_blocked_even_if_interesting() -> None:
    score = TopicScorer().score(
        candidate("a", "practice_case", dimensions={"risk": 90})
    )
    assert score.eligible is False
    assert "risk_too_high" in score.reasons


def test_news_without_unique_author_angle_is_blocked() -> None:
    score = TopicScorer().score(
        candidate(
            "news",
            "news_analysis",
            is_news=True,
            dimensions={"author_unique_angle": 20},
        )
    )
    assert score.eligible is False
    assert "news_lacks_author_unique_angle" in score.reasons


def test_planner_avoids_same_pillar_on_adjacent_days_when_possible() -> None:
    planner = SevenDayPlanner()
    plan = planner.plan(
        [
            candidate("a", "what_to_do"),
            candidate("b", "what_to_do"),
            candidate("c", "court_practice"),
            candidate("d", "investigator_logic"),
        ]
    )
    assert 1 <= len(plan) <= 7
    for previous, current in zip(plan, plan[1:]):
        assert previous.pillar != current.pillar


def test_planner_never_invents_slots_without_candidates() -> None:
    assert SevenDayPlanner().plan([]) == []


def test_image_prompt_forbids_identifiable_people_and_fake_evidence() -> None:
    prompt = ImagePromptGenerator().generate(
        topic="Иван Иванов на допросе",
        pillar=ContentPillar.CRIMINAL_PROCEDURE,
    )
    assert "no identifiable real people" in prompt
    assert "no readable fake evidence" in prompt
    assert "Иван Иванов" not in prompt
