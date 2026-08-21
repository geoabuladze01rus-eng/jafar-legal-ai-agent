from jafar.analytics import PostMetrics, rank_posts
from jafar.content_feedback import recommend_formats


def test_posts_are_ranked_by_engagement():
    low = PostMetrics("low", views=1000, reactions=10)
    high = PostMetrics("high", views=1000, reactions=100)
    assert [x.post_id for x in rank_posts([low, high])] == ["high", "low"]


def test_recommend_formats_prefers_better_average_performance():
    result = recommend_formats([
        ("case", PostMetrics("1", 1000, reactions=100)),
        ("news", PostMetrics("2", 1000, reactions=10)),
    ])
    assert result[0] == "case"
