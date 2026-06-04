import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import get_db, Base

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

def test_register_and_login():
    res = client.post("/auth/register", json={"email": "test@test.com", "password": "pass", "full_name": "Test User"})
    assert res.status_code == 200
    assert res.json()["email"] == "test@test.com"

    login_res = client.post("/auth/token", data={"username": "test@test.com", "password": "pass"})
    assert login_res.status_code == 200
    assert "access_token" in login_res.json()
    return login_res.json()["access_token"]

def test_create_project_and_task():
    token = test_register_and_login()
    headers = {"Authorization": f"Bearer {token}"}

    proj_res = client.post("/projects", json={"name": "Alpha", "description": "Desc"}, headers=headers)
    assert proj_res.status_code == 200
    project_id = proj_res.json()["id"]

    task_res = client.post(f"/projects/{project_id}/tasks", json={"title": "Setup CI"}, headers=headers)
    assert task_res.status_code == 200
    assert task_res.json()["status"] == "todo"

    client.post(f"/projects/{project_id}/tasks", json={"title": "In Progress Task", "status": "in_progress"}, headers=headers)
    
    filter_res = client.get(f"/projects/{project_id}/tasks?status=todo", headers=headers)
    assert filter_res.status_code == 200
    tasks = filter_res.json()
    assert len(tasks) == 1
    assert tasks[0]["title"] == "Setup CI"