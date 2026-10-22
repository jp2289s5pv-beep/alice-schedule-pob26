import unittest
from datetime import date
import app

class ScheduleTests(unittest.TestCase):
    def test_october_22_upper_week(self):
        day = date(2026, 10, 22)
        self.assertEqual(app.week_type_for(day), "upper")
        lessons = app.lessons_for(day)
        subjects = [x["subject"] for x in lessons]
        self.assertIn("Введение в химию природной среды", subjects)
        self.assertIn("Геофизика", subjects)

    def test_subgroups(self):
        day = date(2026, 10, 22)
        first = app.lessons_for(day, "1")
        second = app.lessons_for(day, "2")
        self.assertTrue(any(x["subject"] == "Введение в химию природной среды" and x.get("subgroup") == "1" for x in first))
        self.assertTrue(any(x["subject"] == "Геофизика" and x.get("subgroup") == "2" for x in second))

    def test_alice_response_shape(self):
        result = app.handle_alice_event({"request": {"original_utterance": "Что у меня в четверг?"}})
        self.assertEqual(result["version"], "1.0")
        self.assertIn("response", result)
        self.assertIn("text", result["response"])

if __name__ == "__main__":
    unittest.main()
