import threading

from ledger.core.buffer import LogBuffer


class TestLogBuffer:
    def test_buffer_initialization(self):
        buffer = LogBuffer(max_size=100)
        assert buffer.max_size == 100
        assert buffer.size() == 0
        assert buffer.is_empty() is True

    def test_add_log(self):
        buffer = LogBuffer(max_size=100)
        log_entry = {"message": "test", "level": "info"}

        buffer.add(log_entry)

        assert buffer.size() == 1
        assert buffer.is_empty() is False

    def test_buffer_overflow(self):
        buffer = LogBuffer(max_size=3)

        buffer.add({"id": 1})
        buffer.add({"id": 2})
        buffer.add({"id": 3})
        assert buffer.size() == 3
        assert buffer.get_dropped_count() == 0

        buffer.add({"id": 4})

        assert buffer.size() == 3
        assert buffer.get_dropped_count() == 1

    def test_get_batch(self):
        buffer = LogBuffer(max_size=100)

        for i in range(10):
            buffer.add({"id": i})

        batch = buffer.get_batch(5)

        assert len(batch) == 5
        assert buffer.size() == 5

    def test_get_batch_empty_buffer(self):
        buffer = LogBuffer(max_size=100)

        batch = buffer.get_batch(5)

        assert len(batch) == 0

    def test_clear_buffer(self):
        buffer = LogBuffer(max_size=100)

        buffer.add({"id": 1})
        buffer.add({"id": 2})
        assert buffer.size() == 2

        buffer.clear()

        assert buffer.size() == 0
        assert buffer.is_empty() is True

    def test_requeue_preserves_order(self):
        buffer = LogBuffer(max_size=100)
        for i in range(3):
            buffer.add({"id": i})

        batch = buffer.get_batch(3)
        assert [e["id"] for e in batch] == [0, 1, 2]

        buffer.requeue(batch)
        batch2 = buffer.get_batch(3)
        assert [e["id"] for e in batch2] == [0, 1, 2]

    def test_requeue_drops_overflow(self):
        buffer = LogBuffer(max_size=3)
        buffer.add({"id": 10})
        buffer.add({"id": 11})
        buffer.add({"id": 12})

        big_batch = [{"id": i} for i in range(5)]
        requeued = buffer.requeue(big_batch)

        assert requeued == 0
        assert buffer.get_dropped_count() == 5

    def test_threaded_add_and_batch(self):
        buffer = LogBuffer(max_size=100000)
        total_adds = 8 * 1000
        results: list[list[dict]] = []
        lock = threading.Lock()

        def worker() -> None:
            for i in range(1000):
                buffer.add({"x": i})
            batch = buffer.get_batch(500)
            with lock:
                results.append(batch)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        remaining = buffer.get_batch(total_adds)
        total_got = sum(len(r) for r in results) + len(remaining)
        assert total_got + buffer.get_dropped_count() == total_adds
