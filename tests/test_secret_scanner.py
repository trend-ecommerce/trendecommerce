import unittest
import os
import tempfile
from api_guardian.secret_scanner import SecretScanner, mask_secret


class TestSecretScanner(unittest.TestCase):
    def setUp(self):
        self.scanner = SecretScanner()

    def test_mask_secret(self):
        self.assertEqual(mask_secret("1234567890"), "12********90")
        self.assertEqual(mask_secret("short"), "********")

    def test_detect_hardcoded_credentials(self):
        # Construct test strings dynamically so CLI scanner does not flag test file itself
        var1 = "ACCESS_" + "TOKEN"
        var2 = "API_" + "KEY"
        var3 = "LWA_" + "TOKEN"

        content = f"""
# Safe usage
token = os.getenv("{var1}")

# Violations
{var1} = "secret_access_token_12345"
{var2} = "sk_live_998877665544332211"
{var3} = "lwa_token_super_secret_xyz"
"""
        with tempfile.NamedTemporaryFile('w', suffix='.py', delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            violations = self.scanner.scan_file(temp_path)
            self.assertGreaterEqual(len(violations), 3)
            reasons = [v['reason'] for v in violations]
            self.assertTrue(any("Hardcoded" in r for r in reasons))

            # Ensure secret values are masked in output
            for v in violations:
                self.assertNotIn("secret_access_token_12345", v['reason'])
                self.assertNotIn("sk_live_998877665544332211", v['reason'])
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


if __name__ == '__main__':
    unittest.main()
