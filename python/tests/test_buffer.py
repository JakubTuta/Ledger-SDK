import pytest

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

    @pytest.mark.asyncio
    async def test_get_batch(self):
        buffer = LogBuffer(max_size=100)

        for i in range(10):
            buffer.add({"id": i})

        batch = await buffer.get_batch(5)

        assert len(batch) == 5
        assert buffer.size() == 5

    @pytest.mark.asyncio
    async def test_get_batch_empty_buffer(self):
        buffer = LogBuffer(max_size=100)

        batch = await buffer.get_batch(5)

        assert len(batch) == 0

    def test_clear_buffer(self):
        buffer = LogBuffer(max_size=100)

        buffer.add({"id": 1})
        buffer.add({"id": 2})
        assert buffer.size() == 2

        buffer.clear()

        assert buffer.size() == 0
        assert buffer.is_empty() is True
