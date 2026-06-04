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
    """Wipes and recreates the database before every single test."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def auth_headers():
    """Helper fixture to automatically register and log in a user for protected routes."""
    client.post("/auth/register", json={"email": "auth@test.com", "password": "pass", "full_name": "Auth User"})
    res = client.post("/auth/token", data={"username": "auth@test.com", "password": "pass"})
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def test_project(auth_headers):
    """Helper fixture to automatically create a project and return its ID."""
    res = client.post("/projects", json={"name": "Test Project", "description": "Desc"}, headers=auth_headers)
    return res.json()["id"]


def test_register_user():
    res = client.post("/auth/register", json={"email": "register@test.com", "password": "pass", "full_name": "Reg User"})
    assert res.status_code == 200
    assert res.json()["email"] == "register@test.com"

def test_login_user():
    client.post("/auth/register", json={"email": "login@test.com", "password": "pass", "full_name": "Login User"})
    login_res = client.post("/auth/token", data={"username": "login@test.com", "password": "pass"})
    assert login_res.status_code == 200
    assert "access_token" in login_res.json()

def test_create_project(auth_headers):
    proj_res = client.post("/projects", json={"name": "Alpha", "description": "Desc"}, headers=auth_headers)
    assert proj_res.status_code == 200
    assert proj_res.json()["name"] == "Alpha"

def test_create_task(auth_headers, test_project):
    task_res = client.post(f"/projects/{test_project}/tasks", json={"title": "Setup CI"}, headers=auth_headers)
    assert task_res.status_code == 200
    assert task_res.json()["status"] == "todo"

def test_filter_tasks_by_status(auth_headers, test_project):
    client.post(f"/projects/{test_project}/tasks", json={"title": "Task 1", "status": "todo"}, headers=auth_headers)
    client.post(f"/projects/{test_project}/tasks", json={"title": "Task 2", "status": "in_progress"}, headers=auth_headers)
    
    filter_res = client.get(f"/projects/{test_project}/tasks?status=todo", headers=auth_headers)
    assert filter_res.status_code == 200
    
    tasks = filter_res.json()
    assert len(tasks) == 1
    assert tasks[0]["title"] == "Task 1"

def test_patch_task_status(auth_headers, test_project):
    task_res = client.post(f"/projects/{test_project}/tasks", json={"title": "Patch Me"}, headers=auth_headers)
    task_id = task_res.json()["id"]
    
    patch_res = client.patch(f"/tasks/{task_id}/status", json={"status": "done"}, headers=auth_headers)
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == "done"