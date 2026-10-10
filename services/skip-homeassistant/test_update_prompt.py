import unittest
import update_prompt as u

BASE = "You are Skip, a wallaby.\n\n<!-- SKIP_REPORTING_RULES_START -->\nreporting\n<!-- SKIP_REPORTING_RULES_END -->"


class MergeTests(unittest.TestCase):
    def test_appends_once_and_preserves_existing_blocks(self):
        once = u.merge(BASE)
        self.assertTrue(once.startswith(BASE))
        self.assertEqual(once.count(u.START), 1)
        self.assertEqual(u.merge(once), once)

    def test_replaces_old_rules_in_place(self):
        old = u.merge(BASE, "old rules") + "\ntrailing"
        new = u.merge(old)
        self.assertNotIn("old rules", new)
        self.assertIn("reporting", new)
        self.assertTrue(new.endswith("\ntrailing"))

    def test_refuses_unexpected_or_broken_prompt(self):
        with self.assertRaises(ValueError):
            u.merge("You are a generic assistant.")
        with self.assertRaises(ValueError):
            u.merge("You are Skip.\n" + u.START + "\nno end")

    def test_rules_name_every_tool_and_plan(self):
        for name in ("home_status_now", "daily_totals_7d", "recent_changes_24h", "Immich photos to Wasabi", "restic appliance to Wasabi"):
            self.assertIn(name, u.RULES)


if __name__ == "__main__":
    unittest.main()
