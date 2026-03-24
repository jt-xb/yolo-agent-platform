"""
pytest fixtures for backend tests
"""
import os
import sys
import pytest
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Set test environment before imports
os.environ["LLM_API_KEY"] = "test-key"
os.environ["LLM_MODEL"] = "deepseek-chat"
os.environ["LLM_API_BASE"] = "https://api.deepseek.com/v1"
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["LOG_DIR"] = "/tmp/test_logs"
os.environ["MODELS_DIR"] = "/tmp/test_models"
os.environ["DATASETS_DIR"] = "/tmp/test_datasets"


@pytest.fixture(scope="session")
def test_dirs():
    """Create test directories"""
    dirs = [Path("/tmp/test_logs"), Path("/tmp/test_models"), Path("/tmp/test_datasets")]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
    yield
    # Cleanup is optional - leave for debugging


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test"""
    from backend.core.database import SessionLocal, init_db

    init_db()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        # Clean up tables after each test
        from backend.core.database import Base
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()
