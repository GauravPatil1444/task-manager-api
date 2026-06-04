from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models import User, Project, Task, TaskStatus
from app.schemas import UserCreate, UserResponse, ProjectCreate, ProjectResponse, TaskCreate, TaskUpdate, TaskResponse, TaskStatusUpdate
from app.auth import get_password_hash, verify_password, create_access_token, get_current_user

app = FastAPI(title="Task Manager API")

@app.post("/auth/register", response_model=UserResponse)
def register(user: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == user.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    new_user = User(
        email=user.email,
        hashed_password=get_password_hash(user.password),
        full_name=user.full_name
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.post("/auth/token")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user

@app.get("/projects", response_model=List[ProjectResponse])
def get_projects(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Project).filter(Project.owner_id == current_user.id).all()

@app.post("/projects", response_model=ProjectResponse)
def create_project(project: ProjectCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    new_project = Project(**project.model_dump(), owner_id=current_user.id)
    db.add(new_project)
    db.commit()
    db.refresh(new_project)
    return new_project

@app.post("/projects/{project_id}/tasks", response_model=TaskResponse)
def create_task(project_id: int, task: TaskCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to add tasks to this project")
    
    new_task = Task(**task.model_dump(), project_id=project_id)
    db.add(new_task)
    db.commit()
    db.refresh(new_task)
    return new_task

@app.get("/projects/{project_id}/tasks", response_model=List[TaskResponse])
def get_tasks(project_id: int, status: Optional[TaskStatus] = None, assignee_id: Optional[int] = None, page: int = Query(1, ge=1, description="Page number"), limit: int = Query(10, ge=1, le=100, description="Items per page"), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view these tasks")
    
    query = db.query(Task).filter(Task.project_id == project_id)
    
    if status:
        query = query.filter(Task.status == status)
    if assignee_id:
        query = query.filter(Task.assignee_id == assignee_id)

    offset = (page - 1) * limit
    
    return query.offset(offset).limit(limit).all()

@app.put("/tasks/{task_id}", response_model=TaskResponse)
def update_task(task_id: int, task_update: TaskUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    project = db.query(Project).filter(Project.id == task.project_id).first()
    
    if task.assignee_id != current_user.id and project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to edit this task")
    
    update_data = task_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(task, key, value)
        
    db.commit()
    db.refresh(task)
    return task

@app.delete("/tasks/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
        
    project = db.query(Project).filter(Project.id == task.project_id).first()
    if task.assignee_id != current_user.id and project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this task")
        
    db.delete(task)
    db.commit()
    return {"detail": "Task deleted"}

@app.patch("/tasks/{task_id}/status", response_model=TaskResponse)
def update_task_status(task_id: int, status_update: TaskStatusUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    project = db.query(Project).filter(Project.id == task.project_id).first()

    if task.assignee_id != current_user.id and project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to edit this task")

    task.status = status_update.status
    db.commit()
    db.refresh(task)
    return task