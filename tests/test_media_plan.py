from jafar.media_plan import MediaType, plan_media


def test_image_media_plan():
    plan = plan_media(topic="судебная реформа", format="разбор", needs_visual=True)
    assert plan.media_type == MediaType.IMAGE
    assert plan.prompt


def test_video_media_plan():
    plan = plan_media(topic="права при задержании", format="короткий разбор", needs_video=True)
    assert plan.media_type == MediaType.VIDEO
    assert plan.prompt


def test_no_media_when_not_needed():
    plan = plan_media(topic="новость", format="новость")
    assert plan.media_type == MediaType.NONE
