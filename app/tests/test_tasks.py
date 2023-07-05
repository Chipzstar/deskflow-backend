from app.worker import create_task, adding_task


def test_task():
    assert adding_task.delay(3, 9)
    assert create_task.delay("B057MQM2RMZ:1688244790.268349", 10)
    assert create_task.delay("B057MQM2RMZ:1688244790.268349", 10)
