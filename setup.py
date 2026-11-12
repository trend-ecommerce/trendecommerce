from setuptools import setup, find_packages

setup(
    name='trendecommerce-ai',
    version='1.0.0',
    author='TrendEcommerce AI Team',
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    python_requires='>=3.10',
    install_requires=[
        'fastapi>=0.110.0',
        'uvicorn[standard]>=0.29.0',
        'xgboost>=2.0.0',
        'scikit-learn>=1.4.0',
        'pandas>=2.1.0',
        'numpy>=1.26.0',
        'psycopg2-binary>=2.9.0',
        'sqlalchemy>=2.0.0',
        'bcrypt>=4.0.0',
        'python-jose[cryptography]>=3.3.0',
        'email-validator>=2.0.0',
        'requests>=2.31.0',
        'httpx>=0.27.0',
        'python-dotenv>=1.0.0',
        'pydantic>=2.7.0',
    ],
)
