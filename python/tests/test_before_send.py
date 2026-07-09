import ledger.core.scrubbers as scrubbers_module
from tests.conftest import flush_client


class TestBeforeSendHook:
    def test_before_send_can_mutate_body(self, make_client, log_exporter):
        def _hook(record):
            record["body"] = record["body"].upper()
            return record

        client = make_client(before_send=_hook)
        client.log_info("hello world")
        flush_client(client)

        record = log_exporter.get_finished_logs()[0].log_record
        assert record.body == "HELLO WORLD"

    def test_before_send_can_mutate_attributes(self, make_client, log_exporter):
        def _hook(record):
            record["attributes"]["custom"] = "added"
            return record

        client = make_client(before_send=_hook)
        client.log_info("hi", {"user_id": "1"})
        flush_client(client)

        record = log_exporter.get_finished_logs()[0].log_record
        assert record.attributes["custom"] == "added"
        assert record.attributes["user_id"] == "1"

    def test_before_send_returning_none_drops_record(self, make_client, log_exporter):
        client = make_client(before_send=lambda _record: None)
        client.log_info("dropped")
        client.log_error("also dropped")
        flush_client(client)

        assert len(log_exporter.get_finished_logs()) == 0

    def test_before_send_can_selectively_drop(self, make_client, log_exporter):
        def _hook(record):
            if record["attributes"].get("skip"):
                return None
            return record

        client = make_client(before_send=_hook)
        client.log_info("keep me")
        client.log_info("skip me", {"skip": True})
        flush_client(client)

        records = log_exporter.get_finished_logs()
        assert len(records) == 1
        assert records[0].log_record.body == "keep me"

    def test_before_send_receives_severity_fields(self, make_client, log_exporter):  # noqa: ARG002
        seen = []

        def _hook(record):
            seen.append((record["severity_text"], record["severity_number"]))
            return record

        client = make_client(before_send=_hook)
        client.log_error("boom")
        flush_client(client)

        assert seen[0][0] == "ERROR"


class TestScrubPii:
    def test_scrub_pii_redacts_sensitive_header_attribute(self, make_client, log_exporter):
        client = make_client(scrub_pii=True)
        client.log_info("request", {"Authorization": "Bearer secret-token-value"})
        flush_client(client)

        record = log_exporter.get_finished_logs()[0].log_record
        assert record.attributes["Authorization"] == "[REDACTED]"

    def test_scrub_pii_redacts_secret_shaped_key(self, make_client, log_exporter):
        client = make_client(scrub_pii=True)
        client.log_info("login", {"password": "hunter2", "user_id": "123"})
        flush_client(client)

        record = log_exporter.get_finished_logs()[0].log_record
        assert record.attributes["password"] == "[REDACTED]"  # noqa: S105
        assert record.attributes["user_id"] == "123"

    def test_scrub_pii_redacts_email_in_body(self, make_client, log_exporter):
        client = make_client(scrub_pii=True)
        client.log_info("Contact us at support@example.com for help")
        flush_client(client)

        record = log_exporter.get_finished_logs()[0].log_record
        assert "support@example.com" not in record.body
        assert "[REDACTED]" in record.body

    def test_scrub_pii_redacts_credit_card_like_sequence_in_body(self, make_client, log_exporter):
        client = make_client(scrub_pii=True)
        client.log_info("card 4111 1111 1111 1111 was charged")
        flush_client(client)

        record = log_exporter.get_finished_logs()[0].log_record
        assert "4111 1111 1111 1111" not in record.body
        assert "[REDACTED]" in record.body

    def test_scrub_pii_leaves_non_sensitive_data_alone(self, make_client, log_exporter):
        client = make_client(scrub_pii=True)
        client.log_info("order placed", {"order_id": "abc-123"})
        flush_client(client)

        record = log_exporter.get_finished_logs()[0].log_record
        assert record.attributes["order_id"] == "abc-123"

    def test_scrub_pii_composes_with_explicit_before_send_scrub_first(
        self,
        make_client,
        log_exporter,  # noqa: ARG002
    ):
        seen = []

        def _hook(record):
            seen.append(dict(record["attributes"]))
            return record

        client = make_client(scrub_pii=True, before_send=_hook)
        client.log_info("login", {"password": "hunter2"})
        flush_client(client)

        # Built-in scrubbers run first, so the user's hook only ever sees the
        # already-redacted value.
        assert seen[0]["password"] == "[REDACTED]"  # noqa: S105

    def test_scrub_pii_explicit_before_send_can_still_drop(self, make_client, log_exporter):
        client = make_client(scrub_pii=True, before_send=lambda _record: None)
        client.log_info("login", {"password": "hunter2"})
        flush_client(client)

        assert len(log_exporter.get_finished_logs()) == 0


class TestScrubbersModule:
    def test_build_pii_scrubber_composes_all_default_scrubbers(self):
        scrub = scrubbers_module.build_pii_scrubber()
        record = {
            "body": "email me at person@example.com",
            "attributes": {"api_key": "sk-live-abc123", "region": "eu"},
            "severity_number": None,
            "severity_text": "INFO",
        }

        result = scrub(record)

        assert result is not None
        assert "person@example.com" not in result["body"]
        assert result["attributes"]["api_key"] == "[REDACTED]"
        assert result["attributes"]["region"] == "eu"

    def test_scrub_secret_keys_matches_common_substrings(self):
        record = {
            "body": None,
            "attributes": {
                "password": "x",
                "user_secret": "y",
                "session_token": "z",
                "safe_field": "ok",
            },
        }

        result = scrubbers_module.scrub_secret_keys(record)

        assert result["attributes"]["password"] == "[REDACTED]"  # noqa: S105
        assert result["attributes"]["user_secret"] == "[REDACTED]"  # noqa: S105
        assert result["attributes"]["session_token"] == "[REDACTED]"  # noqa: S105
        assert result["attributes"]["safe_field"] == "ok"
