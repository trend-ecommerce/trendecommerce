import os


def load_dotenv_if_exists():
    """Simple parser for .env file if present in workspace."""
    env_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    if os.path.exists(env_file):
        try:
            with open(env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    stripped = line.strip()
                    if stripped and not stripped.startswith('#') and '=' in stripped:
                        key, value = stripped.split('=', 1)
                        key, value = key.strip(), value.strip()
                        if key not in os.environ:
                            os.environ[key] = value
        except Exception:
            pass


load_dotenv_if_exists()


class DatabaseConfig:
    @staticmethod
    def get_host() -> str:
        return os.getenv("POSTGRES_HOST", "127.0.0.1")

    @staticmethod
    def get_port() -> int:
        return int(os.getenv("POSTGRES_PORT", "5432"))

    @staticmethod
    def get_dbname() -> str:
        return os.getenv("POSTGRES_DB", "trendcommerce")

    @staticmethod
    def get_user() -> str:
        return os.getenv("POSTGRES_USER", "postgres")

    @staticmethod
    def get_password() -> str:
        return os.getenv("POSTGRES_PASSWORD", "postgres")

    @classmethod
    def get_connection_dict(cls) -> dict:
        return {
            "host": cls.get_host(),
            "port": cls.get_port(),
            "dbname": cls.get_dbname(),
            "user": cls.get_user(),
            "password": cls.get_password(),
            "connect_timeout": 5
        }
