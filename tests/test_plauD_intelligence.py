from jafar.plauD_intelligence import PlaudIntelligence


def test_plauD_recording_becomes_audio_evidence():
    evidence = PlaudIntelligence().ingest({
        "recording_id": "rec-1",
        "file_name": "meeting.mp3",
        "duration_seconds": 120,
        "transcript": "Обсудили договор.",
        "participants": ["Иван Иванов", "Петр Петров"],
        "facts": [{"title": "Договор", "description": "Согласованы условия"}],
        "confidence": 0.91,
    })
    assert evidence.source == "plaud"
    assert evidence.participants == ("Иван Иванов", "Петр Петров")
    assert PlaudIntelligence.timeline_candidates(evidence)[0]["confidence"] == 0.91
