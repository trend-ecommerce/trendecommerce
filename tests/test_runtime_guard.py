import unittest
from api_guardian.runtime_guard import guarded_request, set_network_executor, APIGuardianBlockedError


class TestRuntimeGuard(unittest.TestCase):
    def setUp(self):
        self.executed_calls = []

        def mock_executor(method, url, headers=None, **kwargs):
            self.executed_calls.append({
                'method': method,
                'url': url,
                'headers': headers
            })
            return {"status": 200, "data": "success"}

        set_network_executor(mock_executor)

    def tearDown(self):
        set_network_executor(None)

    def test_guarded_request_allow_executes_network(self):
        resp = guarded_request(
            method="GET",
            url="https://api.mercadolibre.com/sites/MLB/search",
            params={"q": "notebook"}
        )
        self.assertEqual(resp["status"], 200)
        self.assertEqual(len(self.executed_calls), 1)
        self.assertIn("q=notebook", self.executed_calls[0]['url'])

    def test_guarded_request_block_prevents_network(self):
        with self.assertRaises(APIGuardianBlockedError):
            guarded_request(
                method="GET",
                url="https://unauthorized-domain.com/data"
            )

        # Crucial check: Network executor MUST NOT be called!
        self.assertEqual(len(self.executed_calls), 0)


if __name__ == '__main__':
    unittest.main()
