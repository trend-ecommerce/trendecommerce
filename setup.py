from setuptools import setup, find_packages

setup(
    name='trendcommerce-ai',
    version='0.1.0',
    author='TrendCommerce Team',
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    python_requires='>=3.10',
    install_requires=[
        'xgboost==2.1.0',
        'scikit-learn==1.5.1',
        'pandas==2.2.2',
        'numpy==1.26.4',
        'psycopg2-binary==2.9.9',
        'sqlalchemy==2.0.31',
        'alembic==1.13.2',
        'requests==2.32.3',
        'httpx==0.27.0',
        'aiohttp==3.9.5',
        'python-dotenv==1.0.1',
        'pydantic==2.8.2',
        'pydantic-settings==2.4.0',
    ],
)
