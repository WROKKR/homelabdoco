import unittest
from pathlib import Path
import apply_base_prompt as a

LIVE = Path(__file__).resolve().parents[2] / "docs/skip-prompt-live.txt"


class MergeTests(unittest.TestCase):
    def test_keeps_all_rule_blocks_verbatim(self):
        live = "You are Skip, old.\n\n<!-- SKIP_REPORTING_RULES_START -->\nr\n<!-- SKIP_REPORTING_RULES_END -->\n\n<!-- SKIP_HOMEASSISTANT_RULES_START -->\nh\n<!-- SKIP_HOMEASSISTANT_RULES_END -->"
        out = a.merge(live, "You are Skip, new.\n")
        self.assertTrue(out.startswith("You are Skip, new.\n\n\n<!-- SKIP_REPORTING"))
        self.assertTrue(out.endswith(live[live.index("<!-- SKIP_"):]))
        self.assertNotIn("old", out)

    def test_idempotent_and_no_blocks(self):
        once = a.merge("You are Skip, old.\n<!-- SKIP_X_START -->\nx", "You are Skip, new.")
        self.assertEqual(a.merge(once, "You are Skip, new."), once)
        self.assertEqual(a.merge("You are Skip, old.", "You are Skip, new."), "You are Skip, new.")

    def test_refuses_bad_input(self):
        for live, base in (("Generic assistant", "You are Skip, x"), ("You are Skip, x", "Hello"), ("You are Skip, x", "You are Skip, x <!-- SKIP_Y -->")):
            with self.assertRaises(ValueError):
                a.merge(live, base)

    def test_real_capture_and_repo_base(self):
        base = (Path(__file__).with_name("base_prompt.txt")).read_text()
        live = LIVE.read_text().strip()
        out = a.merge(live, base)
        for marker in ("SKIP_REPORTING_RULES_END", "SKIP_HOMEASSISTANT_RULES_END", "Mimisbrunnr", "I'm a wallaby"):
            self.assertIn(marker, out)
        self.assertNotIn("Wasabi uploads remain unconfigured", out)


if __name__ == "__main__":
    unittest.main()
