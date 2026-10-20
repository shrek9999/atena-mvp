import unittest

from workout_quality import WorkoutBlock, duration_matches, total_duration_seconds


class WorkoutQualityTests(unittest.TestCase):
    def test_exact_twenty_minute_session(self):
        blocks = [
            WorkoutBlock("Ogrevanje", 180),
            WorkoutBlock("Glavni del", 840),
            WorkoutBlock("Umiritev", 180),
        ]
        self.assertEqual(total_duration_seconds(blocks), 1200)
        self.assertTrue(duration_matches(blocks, 20))

    def test_mismatched_duration_is_rejected(self):
        blocks = [WorkoutBlock("Ogrevanje", 180), WorkoutBlock("Glavni del", 780), WorkoutBlock("Umiritev", 180)]
        self.assertFalse(duration_matches(blocks, 20))

    def test_empty_workout_is_rejected(self):
        with self.assertRaises(ValueError):
            total_duration_seconds([])

    def test_zero_duration_is_rejected(self):
        with self.assertRaises(ValueError):
            total_duration_seconds([WorkoutBlock("Ogrevanje", 0)])

    def test_non_integer_duration_is_rejected(self):
        with self.assertRaises(ValueError):
            total_duration_seconds([WorkoutBlock("Ogrevanje", 30.5)])


if __name__ == "__main__":
    unittest.main()
