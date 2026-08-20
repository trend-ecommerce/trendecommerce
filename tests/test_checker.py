import unittest
import os
import tempfile
from api_guardian.checker import GuardianChecker


class TestChecker(unittest.TestCase):
    def setUp(self):
        self.checker = GuardianChecker()

    def test_direct_http_call_detection(self):
        code = """
import requests

def fetch_data():
    # Direct HTTP call bypassing Guardian
    resp = requests.get("https://api.mercadolibre.com/sites/MLB/search?q=phone")
    return resp
"""
        with tempfile.NamedTemporaryFile('w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            res = self.checker.check_file(temp_path)
            self.assertGreater(res['blocked_count'], 0)
            reasons = [v['reason'] for v in res['violations']]
            self.assertTrue(any("Import direto" in r or "direta" in r for r in reasons))
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_guarded_call_detection(self):
        code = """
from api_guardian.runtime_guard import guarded_request

def fetch_data():
    return guarded_request("GET", "https://api.mercadolibre.com/sites/MLB/search?q=phone")
"""
        with tempfile.NamedTemporaryFile('w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            res = self.checker.check_file(temp_path)
            self.assertEqual(res['blocked_count'], 0)
            self.assertEqual(res['approved_count'], 1)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


if __name__ == '__main__':
    unittest.main()
