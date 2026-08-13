import unittest
from db.config import DatabaseConfig
from db.connection import get_db_connection, set_mock_mode, is_mock_mode
from db.migrator import DatabaseMigrator


class TestDatabase(unittest.TestCase):
    def setUp(self):
        set_mock_mode(True)

    def test_database_config_defaults(self):
        self.assertEqual(DatabaseConfig.get_host(), "127.0.0.1")
        self.assertEqual(DatabaseConfig.get_port(), 5432)
        self.assertEqual(DatabaseConfig.get_dbname(), "trendcommerce")

    def test_connection_mock_fallback(self):
        conn = get_db_connection()
        self.assertIsNotNone(conn)
        self.assertTrue(is_mock_mode())

    def test_run_migrations(self):
        migrator = DatabaseMigrator()
        applied = migrator.run_migrations()
        self.assertIn("001", applied)


if __name__ == "__main__":
    unittest.main()
