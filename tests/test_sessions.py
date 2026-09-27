import unittest
from datetime import datetime, timezone

from tdv_metals.sessions import CalendarConfig, session_status


def _utc(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def _calendar() -> dict:
    # A research fixture, not a claim about any current exchange schedule.
    return {
        "name": "Test future",
        "timezone": "America/New_York",
        "windows": [
            {"weekday": weekday, "start": "18:00", "end": "17:00", "label": "test hours"}
            for weekday in (6, 0, 1, 2, 3)
        ],
        "source": "test fixture",
    }


class SessionTests(unittest.TestCase):
    def test_open_maintenance_and_weekend_next_transition(self) -> None:
        cal = _calendar()
        open_status = session_status(_utc("2026-01-12T16:00:00"), cal)
        self.assertEqual(open_status["status"], "OPEN")
        self.assertEqual(open_status["next_transition_utc"], "2026-01-12T22:00:00+00:00")
        self.assertEqual(open_status["seconds_to_transition"], 6 * 3600)
        self.assertEqual(open_status["next_transition_kind"], "CLOSE")

        maintenance = session_status(_utc("2026-01-12T22:30:00"), cal)
        self.assertEqual(maintenance["status"], "CLOSED")
        self.assertEqual(maintenance["next_transition_utc"], "2026-01-12T23:00:00+00:00")
        self.assertEqual(maintenance["next_transition_kind"], "OPEN")

        weekend = session_status(_utc("2026-01-17T16:00:00"), cal)
        self.assertEqual(weekend["status"], "CLOSED")
        self.assertEqual(weekend["next_transition_utc"], "2026-01-18T23:00:00+00:00")

    def test_dst_changes_utc_open_and_close_without_rewriting_local_hours(self) -> None:
        cal = _calendar()
        winter = session_status(_utc("2026-01-18T22:00:00"), cal)
        summer = session_status(_utc("2026-07-19T21:00:00"), cal)
        self.assertEqual(winter["next_transition_utc"], "2026-01-18T23:00:00+00:00")
        self.assertEqual(summer["next_transition_utc"], "2026-07-19T22:00:00+00:00")

    def test_dated_closure_and_early_close_split_overnight_window(self) -> None:
        cal = _calendar()
        cal["closed_dates"] = ["2026-01-12"]
        cal["early_closes"] = [{"date": "2026-01-13", "time": "13:00"}]

        sunday = session_status(_utc("2026-01-12T03:00:00"), cal)
        self.assertEqual(sunday["status"], "OPEN")
        self.assertEqual(sunday["next_transition_utc"], "2026-01-12T05:00:00+00:00")

        holiday = session_status(_utc("2026-01-12T16:00:00"), cal)
        self.assertEqual(holiday["status"], "CLOSED")
        self.assertEqual(holiday["next_transition_utc"], "2026-01-13T05:00:00+00:00")

        shortened = session_status(_utc("2026-01-13T16:00:00"), cal)
        self.assertEqual(shortened["status"], "OPEN")
        self.assertEqual(shortened["next_transition_utc"], "2026-01-13T18:00:00+00:00")

    def test_context_overlap_does_not_change_exchange_status(self) -> None:
        contexts = [
            {"name": "London", "timezone": "Europe/London", "windows": [{"weekday": 0, "start": "08:00", "end": "17:00"}]},
            {"name": "New York", "timezone": "America/New_York", "windows": [{"weekday": 0, "start": "09:00", "end": "17:00"}]},
        ]
        status = session_status(_utc("2026-01-12T15:00:00"), _calendar(), contexts)
        self.assertEqual(status["context"]["active"], ["London", "New York"])
        self.assertTrue(status["context"]["overlap"])
        self.assertTrue(status["is_open"])

    def test_rejects_naive_datetime_and_invalid_config(self) -> None:
        with self.assertRaisesRegex(ValueError, "timezone aware"):
            session_status(datetime(2026, 1, 12), _calendar())  # noqa: DTZ001 - intentional naive input
        invalid = _calendar()
        invalid["timezone"] = "Not/AnIanaZone"
        with self.assertRaisesRegex(ValueError, "unknown IANA timezone"):
            CalendarConfig.from_dict(invalid)
        invalid = _calendar()
        invalid["windows"] = [{"weekday": 7, "start": "18:00", "end": "17:00"}]
        with self.assertRaisesRegex(ValueError, "weekday"):
            CalendarConfig.from_dict(invalid)


if __name__ == "__main__":
    unittest.main()
