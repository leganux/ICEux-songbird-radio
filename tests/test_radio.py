from app.services.radio import RadioState


def test_queue_exposes_first_item_as_next_track():
    radio = RadioState()
    radio.enqueue("Northern Lights", "Songbird")
    assert radio.snapshot()["next_track"]["title"] == "Northern Lights"
