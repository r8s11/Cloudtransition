# Week 1: Complete Day-by-Day Guide

> Updated 2026-03-17: Rewritten for Python-first strategy. React deferred to Weeks 17-20.

## 🎯 Week 1 Overview

**Goal:** Build Python fundamentals, set up dev environment, and deploy your first FastAPI backend

**Time Commitment:** 2-3 hours/day + 8-10 hours weekend
**Total:** ~20 hours

**Deliverables:**

- ✅ Python fundamentals solid (variables, lists, functions, dictionaries)
- ✅ FastAPI Task Manager API deployed to Azure
- ✅ GitHub repo with 20+ commits
- ✅ SQL basics mastered (SQLBolt Lessons 1-12)
- ✅ 2 books started

---

## 📅 MONDAY - Day 1: Setup & Python Basics

### Morning (1 hour) - 6:00-7:00 AM

**Reading: 30 minutes**

- Start "The Phoenix Project" - Chapters 1-2
- This is a novel, so it's an easy, engaging read
- Take mental notes on IT challenges described

**Python Setup: 30 minutes**

- Verify Python: `python3 --version` (should be 3.11+)
- Install VS Code (if not installed)
- Install VS Code extensions:
  - Python (Microsoft)
  - Pylance
  - Python Debugger
  - Prettier - Code formatter

### Evening (1.5 hours) - 7:00-8:30 PM

**Python Quick Start: 90 minutes**

1. **Create your first Python project (10 minutes)**

```bash
# Open terminal
mkdir -p ~/projects/week1-python-practice
cd ~/projects/week1-python-practice
python3 -m venv venv
source venv/bin/activate  # Mac/Linux
# venv\Scripts\activate   # Windows
```

2. **Python Crash Course Ch 1-2 follow-along (60 minutes)**

Create `hello.py`:

```python
# Variables and data types
name = "Roosevelt"
age = 30
learning = True

print(f"Hello! My name is {name}.")
print(f"I'm learning Python: {learning}")

# Basic math
hours_per_day = 3
days_per_week = 7
total_hours = hours_per_day * days_per_week
print(f"Weekly study hours: {total_hours}")

# Strings
message = "  Hello, Python World!  "
print(message.strip())
print(message.upper())
print(message.lower())
print(message.title())
```

3. **Practice Exercise (20 minutes)**
   Create `skills_tracker.py`:

```python
skills = ["Python", "SQL", "FastAPI", "Azure", "DevOps"]

print("My Tech Stack Learning Journey")
print("=" * 40)
print(f"Week 1: Building foundations\n")
print("Skills I'm Learning:")
for i, skill in enumerate(skills, 1):
    print(f"  {i}. {skill}")
print(f"\nTotal skills to master: {len(skills)}")
```

Run it: `python3 skills_tracker.py`

### Day 1 Checklist

- [ ] Python 3.11+ verified
- [ ] VS Code extensions installed
- [ ] Virtual environment created
- [ ] First Python scripts running
- [ ] Understand variables, strings, f-strings
- [ ] Read Phoenix Project Ch 1-2

---

## 📅 TUESDAY - Day 2: Git & Python Fundamentals

### Morning (1 hour) - 6:00-7:00 AM

**Reading: 30 minutes**

- Continue "The Phoenix Project" - Chapter 3
- Start "Python Crash Course" - Chapter 3 (Lists)

**Git Setup: 30 minutes**

1. Install Git: git-scm.com/downloads
2. Configure Git:

```bash
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

3. Create GitHub account (if you don't have one)
   - Go to github.com
   - Sign up with personal email

4. Initialize your Python practice project:

```bash
cd ~/projects/week1-python-practice
git init
echo "venv/" >> .gitignore
echo "__pycache__/" >> .gitignore
git add .
git commit -m "Initial commit: Python practice project"
```

5. Create GitHub repo:
   - GitHub → New Repository → "week1-python-practice"
   - Follow instructions to push existing repo

```bash
git remote add origin https://github.com/YOUR_USERNAME/week1-python-practice.git
git branch -M main
git push -u origin main
```

### Evening (1.5 hours) - 7:00-8:30 PM

**Python Lists & Loops: 90 minutes**

1. **Lists Practice (45 minutes)**
   Create `lists_practice.py`:

```python
# Lists — Python Crash Course Ch 3
technologies = ["Python", "FastAPI", "SQL", "Docker", "Azure"]

# Access elements
print(f"First skill: {technologies[0]}")
print(f"Last skill: {technologies[-1]}")

# Modify lists
technologies.append("Kubernetes")
technologies.insert(2, "Git")
removed = technologies.pop()
print(f"Removed: {removed}")

# List operations
print(f"\nAll skills ({len(technologies)} total):")
for tech in technologies:
    print(f"  → {tech}")

# Sorting
technologies.sort()
print(f"\nSorted: {technologies}")

# List comprehensions
upper_skills = [t.upper() for t in technologies]
print(f"Uppercase: {upper_skills}")
```

2. **Loops & Ranges (30 minutes)**
   Create `loops_practice.py`:

```python
# For loops with range
days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
topics = ["Setup", "Git & Lists", "Functions & SQL", "Dictionaries", "FastAPI"]

print("Week 1 Study Plan:")
for day, topic in zip(days, topics):
    print(f"  {day}: {topic}")

# Number patterns
print("\nStudy hours this week:")
for day in range(1, 8):
    hours = 3 if day < 6 else 6
    bar = "█" * hours
    print(f"  Day {day}: {bar} ({hours}h)")
```

3. **Commit your work:**

```bash
git add .
git commit -m "Add lists and loops practice"
git push
```

### Day 2 Checklist

- [ ] Git installed and configured
- [ ] GitHub account created
- [ ] First repo pushed to GitHub
- [ ] Understand Python lists (append, insert, pop, sort)
- [ ] Comfortable with for loops and range
- [ ] List comprehensions practiced

---

## 📅 WEDNESDAY - Day 3: Python Functions & SQL Basics

### Morning (1 hour) - 6:00-7:00 AM
**Reading: 60 minutes**
- "Python Crash Course" Chapter 5 (If Statements)
- OR "The Phoenix Project" Chapter 4

### Evening (2 hours) - 7:00-9:00 PM
**Python Functions: 60 minutes**

Create `functions_practice.py`:
```python
# Functions — Python Crash Course Ch 8

def greet(name, role="learner"):
    """Generate a greeting message."""
    return f"Hello, {name}! You're a {role}."

print(greet("Roosevelt"))
print(greet("Roosevelt", "Python developer"))

# Functions with lists
def show_skills(skills):
    """Display skills with numbering."""
    print(f"\n{'=' * 30}")
    print(f"Skills Inventory ({len(skills)} total)")
    print(f"{'=' * 30}")
    for i, skill in enumerate(skills, 1):
        print(f"  {i}. {skill}")

my_skills = ["Python", "SQL", "Git", "FastAPI"]
show_skills(my_skills)

# Return values
def calculate_progress(completed, total):
    """Calculate and return progress percentage."""
    if total == 0:
        return 0
    percentage = (completed / total) * 100
    return round(percentage, 1)

progress = calculate_progress(3, 10)
print(f"\nProgress: {progress}%")

# *args for flexible functions
def log_activities(*activities):
    """Log multiple activities."""
    print(f"\nToday's activities ({len(activities)}):")
    for activity in activities:
        print(f"  ✓ {activity}")

log_activities("Read Python Crash Course", "Practice SQL", "Git commit")
```

Commit:
```bash
git add .
git commit -m "Add functions practice"
git push
```

**SQL Basics: 60 minutes**

1. **Setup (10 minutes)**
- Go to sqlbolt.com (no installation needed)

2. **SQLBolt Tutorial (40 minutes)**
- Complete Lessons 1-6:
  - Lesson 1: SELECT queries 101
  - Lesson 2: Queries with constraints
  - Lesson 3: Filtering and sorting
  - Lesson 4: Reviewing SELECT
  - Lesson 5: Multi-table queries with JOINs
  - Lesson 6: Outer JOINs

3. **Practice Exercise (10 minutes)**

```sql
-- Create tasks table
CREATE TABLE tasks (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    completed BOOLEAN DEFAULT FALSE,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO tasks (id, title, description) VALUES
    (1, 'Learn Python', 'Complete Python Crash Course Part I', FALSE),
    (2, 'Practice SQL', 'Finish SQLBolt lessons', FALSE),
    (3, 'Setup Git', 'Push code to GitHub', TRUE);

SELECT * FROM tasks;
SELECT * FROM tasks WHERE completed = FALSE;
SELECT COUNT(*) as total_tasks FROM tasks;
```

### Day 3 Checklist
- [ ] Python functions mastered (def, return, *args)
- [ ] SQLBolt Lessons 1-6 complete
- [ ] Created tasks table in SQL
- [ ] Git commit and push

---

## 📅 THURSDAY - Day 4: Dictionaries & More SQL

### Morning (1 hour) - 6:00-7:00 AM

**Reading: 60 minutes**

- "Python Crash Course" Chapter 6 (Dictionaries)
- OR continue "The Phoenix Project"

### Evening (2 hours) - 7:00-9:00 PM

**Python Dictionaries & File I/O: 60 minutes**

Create `dictionaries_practice.py`:

```python
# Dictionaries — Python Crash Course Ch 6

# Task as a dictionary
task = {
    "id": 1,
    "title": "Learn Python",
    "description": "Complete Python Crash Course Part I",
    "completed": False,
    "priority": "high"
}

print(f"Task: {task['title']}")
print(f"Status: {'Done' if task['completed'] else 'In Progress'}")
print(f"Priority: {task['priority']}")

# List of dictionaries (like a database!)
tasks = [
    {"id": 1, "title": "Learn Python", "completed": False},
    {"id": 2, "title": "Practice SQL", "completed": False},
    {"id": 3, "title": "Setup Git", "completed": True},
    {"id": 4, "title": "Build FastAPI app", "completed": False},
    {"id": 5, "title": "Deploy to Azure", "completed": False},
]

# Filter and display
print("\n📋 Task Manager")
print("=" * 40)
for t in tasks:
    status = "✅" if t["completed"] else "⬜"
    print(f"  {status} {t['title']}")

completed = [t for t in tasks if t["completed"]]
pending = [t for t in tasks if not t["completed"]]
print(f"\nCompleted: {len(completed)} / {len(tasks)}")
print(f"Remaining: {len(pending)}")
```

Create `file_io_practice.py`:

```python
import json

# Save tasks to JSON file
tasks = [
    {"id": 1, "title": "Learn Python", "completed": False},
    {"id": 2, "title": "Practice SQL", "completed": True},
    {"id": 3, "title": "Build FastAPI app", "completed": False},
]

# Write to file
with open("tasks.json", "w") as f:
    json.dump(tasks, f, indent=2)
print("Tasks saved to tasks.json")

# Read from file
with open("tasks.json", "r") as f:
    loaded_tasks = json.load(f)
print(f"Loaded {len(loaded_tasks)} tasks from file")

for task in loaded_tasks:
    print(f"  - {task['title']}: {'done' if task['completed'] else 'pending'}")
```

Commit:

```bash
git add .
git commit -m "Add dictionaries and file I/O practice"
git push
```

**SQL Practice: 60 minutes**

- Complete SQLBolt Lessons 7-12
- Practice JOINs, Aggregations, GROUP BY

```sql
-- Advanced queries
SELECT completed, COUNT(*) as count FROM tasks GROUP BY completed;

-- Create users table for JOIN practice
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE
);

INSERT INTO users (id, name, email) VALUES
    (1, 'Alice', 'alice@email.com'),
    (2, 'Bob', 'bob@email.com');

-- JOIN example
SELECT u.name, COUNT(t.id) as task_count
FROM users u
LEFT JOIN tasks t ON t.id <= 2
GROUP BY u.name;
```

### Day 4 Checklist

- [ ] Python dictionaries mastered
- [ ] JSON file I/O working
- [ ] SQLBolt Lessons 7-12 complete
- [ ] JOINs and GROUP BY practiced
- [ ] Git commit and push

---

## 📅 FRIDAY - Day 5: FastAPI Intro & Azure Setup

### Morning (1 hour) - 6:00-7:00 AM

**Reading: 60 minutes**

- "Python Crash Course" Chapter 7 (User Input and While Loops)
- Take notes on input handling patterns

### Evening (2 hours) - 7:00-9:00 PM

**Azure Setup: 30 minutes**

1. Go to portal.azure.com
2. Sign up for free account ($200 credit)
3. Complete verification
4. Explore Azure Portal
5. Create first resource group:
   - Name: "week1-practice-rg"
   - Region: East US

**FastAPI Introduction: 90 minutes**

1. Install FastAPI (15 minutes):

```bash
mkdir ~/projects/week1-task-api
cd ~/projects/week1-task-api
python3 -m venv venv
source venv/bin/activate
pip install fastapi uvicorn[standard]
```

2. Create your first API (30 minutes):

```python
# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Task Manager API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory tasks list
tasks = [
    {"id": 1, "title": "Learn Python", "completed": False},
    {"id": 2, "title": "Learn SQL", "completed": False},
    {"id": 3, "title": "Setup Azure", "completed": True},
]

@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Task Manager!"}

@app.get("/tasks")
def get_tasks():
    return tasks

@app.get("/tasks/{task_id}")
def get_task(task_id: int):
    for task in tasks:
        if task["id"] == task_id:
            return task
    return {"error": "Task not found"}
```

3. Run the API (5 minutes):

```bash
uvicorn main:app --reload
```

- Open browser to http://localhost:8000
- Go to http://localhost:8000/docs (Swagger UI)
- Test your endpoints!

4. Add POST and DELETE endpoints (30 minutes):

```python
from pydantic import BaseModel
from typing import Optional

class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = ""
    completed: bool = False

@app.post("/tasks")
def create_task(task: TaskCreate):
    new_id = max(t["id"] for t in tasks) + 1 if tasks else 1
    new_task = {"id": new_id, **task.model_dump()}
    tasks.append(new_task)
    return new_task

@app.delete("/tasks/{task_id}")
def delete_task(task_id: int):
    for i, task in enumerate(tasks):
        if task["id"] == task_id:
            tasks.pop(i)
            return {"message": "Task deleted"}
    return {"error": "Task not found"}
```

Test all endpoints in Swagger UI!

5. Git setup for backend:

```bash
git init
echo "venv/" >> .gitignore
echo "__pycache__/" >> .gitignore
git add .
git commit -m "feat: initial FastAPI task manager API"
```

### Day 5 Checklist

- [ ] Azure account created
- [ ] FastAPI installed
- [ ] First API created with GET, POST, DELETE
- [ ] Swagger docs working
- [ ] Pydantic models used
- [ ] Backend code in Git

---

## 📅 WEEKEND - Days 6-7: Build & Deploy Task Manager API

### Saturday (6 hours)

**Morning (3 hours) - 9:00 AM - 12:00 PM**

**1. Setup SQLite Database (30 minutes)**

```bash
cd ~/projects/week1-task-api
pip install databases[sqlite] aiosqlite
```

**2. Create Database Schema (15 minutes)**
Create `database.py`:

```python
import sqlite3

def get_db():
    conn = sqlite3.connect("tasks.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            completed BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
```

**3. Build Complete FastAPI Backend (2 hours)**
Update `main.py`:

```python
# main.py - Complete CRUD API with SQLite
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from database import get_db, init_db

app = FastAPI(title="Task Manager API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database on startup
@app.on_event("startup")
def startup():
    init_db()

class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = ""
    completed: bool = False

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None

@app.get("/")
def read_root():
    return {"message": "Task Manager API v1.0", "docs": "/docs"}

@app.get("/tasks")
def get_tasks():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tasks ORDER BY created_at DESC")
    tasks = [dict(row) for row in cur.fetchall()]
    conn.close()
    return tasks

@app.get("/tasks/{task_id}")
def get_task(task_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    task = cur.fetchone()
    conn.close()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return dict(task)

@app.post("/tasks", status_code=201)
def create_task(task: TaskCreate):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO tasks (title, description, completed) VALUES (?, ?, ?)",
        (task.title, task.description, task.completed)
    )
    task_id = cur.lastrowid
    conn.commit()
    conn.close()
    return {"id": task_id, **task.model_dump()}

@app.patch("/tasks/{task_id}")
def update_task(task_id: int, task: TaskUpdate):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    existing = cur.fetchone()
    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail="Task not found")

    updates = task.model_dump(exclude_unset=True)
    for key, value in updates.items():
        cur.execute(f"UPDATE tasks SET {key} = ? WHERE id = ?", (value, task_id))
    conn.commit()
    conn.close()
    return {"id": task_id, **updates}

@app.delete("/tasks/{task_id}")
def delete_task(task_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    if cur.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Task not found")
    conn.commit()
    conn.close()
    return {"message": "Task deleted"}

@app.get("/stats")
def get_stats():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as total FROM tasks")
    total = cur.fetchone()["total"]
    cur.execute("SELECT COUNT(*) as done FROM tasks WHERE completed = 1")
    done = cur.fetchone()["done"]
    conn.close()
    return {"total": total, "completed": done, "pending": total - done}
```

Test all endpoints in Swagger UI (http://localhost:8000/docs)!

**Afternoon (3 hours) - 1:00 PM - 4:00 PM**

**4. Build Python CLI Client (1 hour)**
Create `cli.py` — a command-line interface for your task manager:

```python
"""CLI client for Task Manager."""
import sys
import json

TASKS_FILE = "tasks_cli.json"

def load_tasks():
    try:
        with open(TASKS_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_tasks(tasks):
    with open(TASKS_FILE, "w") as f:
        json.dump(tasks, f, indent=2)

def list_tasks(tasks):
    if not tasks:
        print("  No tasks yet. Add one with: python cli.py add 'task name'")
        return
    print(f"\n📋 Tasks ({len(tasks)} total)")
    print("=" * 40)
    for t in tasks:
        status = "✅" if t["completed"] else "⬜"
        print(f"  {t['id']}. {status} {t['title']}")
    completed = sum(1 for t in tasks if t["completed"])
    print(f"\n  Progress: {completed}/{len(tasks)} completed")

def add_task(tasks, title):
    new_id = max(t["id"] for t in tasks) + 1 if tasks else 1
    tasks.append({"id": new_id, "title": title, "completed": False})
    save_tasks(tasks)
    print(f"  ✅ Added: {title}")

def complete_task(tasks, task_id):
    for t in tasks:
        if t["id"] == task_id:
            t["completed"] = True
            save_tasks(tasks)
            print(f"  ✅ Completed: {t['title']}")
            return
    print(f"  ❌ Task {task_id} not found")

def main():
    tasks = load_tasks()
    if len(sys.argv) < 2:
        list_tasks(tasks)
        return

    command = sys.argv[1]
    if command == "list":
        list_tasks(tasks)
    elif command == "add" and len(sys.argv) > 2:
        add_task(tasks, " ".join(sys.argv[2:]))
    elif command == "done" and len(sys.argv) > 2:
        complete_task(tasks, int(sys.argv[2]))
    else:
        print("Usage: python cli.py [list|add <title>|done <id>]")

if __name__ == "__main__":
    main()
```

Test it:

```bash
python cli.py add "Learn Python basics"
python cli.py add "Build FastAPI app"
python cli.py add "Deploy to Azure"
python cli.py list
python cli.py done 1
python cli.py list
```

**5. Add Tests (1 hour)**

```bash
pip install pytest httpx
```

Create `test_main.py`:

```python
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()

def test_create_task():
    response = client.post("/tasks", json={
        "title": "Test task",
        "description": "A test task"
    })
    assert response.status_code == 201
    assert response.json()["title"] == "Test task"

def test_get_tasks():
    response = client.get("/tasks")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_get_stats():
    response = client.get("/stats")
    assert response.status_code == 200
    assert "total" in response.json()
```

Run tests:

```bash
pytest test_main.py -v
```

**6. Polish & Document (1 hour)**

Create `requirements.txt`:

```
fastapi
uvicorn[standard]
pytest
httpx
```

Commit everything:

```bash
git add .
git commit -m "feat: complete Task Manager API with CRUD, CLI, and tests"
git push
```

### Sunday (4 hours)

**Morning (2 hours) - 9:00 AM - 11:00 AM**

**7. Deploy Backend to Azure (2 hours)**

1. Create Dockerfile:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

2. Deploy to Azure App Service:

```bash
# Login
az login

# Create resource group
az group create --name TaskManagerRG --location eastus

# Create App Service plan
az appservice plan create \
  --name TaskManagerPlan \
  --resource-group TaskManagerRG \
  --sku B1 \
  --is-linux

# Create web app
az webapp create \
  --resource-group TaskManagerRG \
  --plan TaskManagerPlan \
  --name task-manager-api-[yourname] \
  --runtime "PYTHON:3.11"

# Deploy code
zip -r app.zip . -x "venv/*" "__pycache__/*" "*.pyc" ".git/*"
az webapp deployment source config-zip \
  --resource-group TaskManagerRG \
  --name task-manager-api-[yourname] \
  --src app.zip
```

Your API is now live at: `https://task-manager-api-[yourname].azurewebsites.net/docs`

**Afternoon (2 hours) - 1:00 PM - 3:00 PM**

**8. Documentation & README (1 hour)**

Create a professional README.md for your repo documenting:

- Tech stack (Python, FastAPI, SQLite)
- Features (CRUD API, Swagger docs, CLI, tests)
- Live demo URL
- Local development instructions
- What you learned
- Next steps

**9. Weekly Review (1 hour)**

Write `week1-review.md` covering:

- Achievements (Python fundamentals, FastAPI, SQL, Git, Azure)
- Books progress (Phoenix Project + Python Crash Course)
- Challenges faced and how you solved them
- Week 2 goals

Commit and push final documentation:

```bash
git add .
git commit -m "docs: add README and week 1 review"
git push
```

---

## 📊 Week 1 Success Metrics

Check all that apply:

- [ ] FastAPI Task Manager API deployed to Azure
- [ ] GitHub repo with 20+ commits
- [ ] SQLBolt completed (Lessons 1-12)
- [ ] Python fundamentals solid (lists, dicts, functions, file I/O)
- [ ] CLI client working
- [ ] Tests passing
- [ ] Read ~100 pages (Phoenix Project + Python Crash Course)
- [ ] Can explain to someone how your API works

**If you checked 6+, you CRUSHED Week 1!** 💪

---

## 🎯 Key Takeaways from Week 1

### Python

- Lists and dictionaries are your bread and butter
- Functions keep code organized and reusable
- f-strings make formatting easy
- JSON for data persistence
- Virtual environments isolate dependencies

### FastAPI

- Automatic API documentation (Swagger UI)
- Type hints with Pydantic models
- CORS middleware for frontend access
- Simple and fast — Python at its best

### SQL

- SELECT retrieves data
- JOIN combines tables
- WHERE filters results
- GROUP BY aggregates data

### Git

- Commit frequently with meaningful messages
- Push to GitHub daily
- `.gitignore` keeps repos clean
- Branches for features (coming Week 2)

### Azure

- App Service for Python APIs
- Resource groups organize resources
- Free tier is generous for learning
- CLI deployment is straightforward

---

## 📚 Reading Summary

**Books Started:**

1. **"The Phoenix Project"** (~100 pages)
   - Key insight: IT challenges are universal
   - DevOps mindset: Continuous improvement
   - Next: Continue to Part 2

2. **"Python Crash Course"** (~200 pages)
   - Variables, lists, dictionaries, functions, file I/O
   - Python fundamentals solid
   - Next: Classes, exceptions, testing

**Total Reading:** ~300 pages
**Time Invested:** ~7 hours (30-60 min/day)

---

## 🚀 Prepare for Week 2

### Order/Download (if you haven't):

- [ ] "Clean Code" by Robert C. Martin
- [ ] Continue "Python Crash Course" (Part I remaining chapters)

### Technical Setup:

- [ ] SQLite working locally
- [ ] Azure CLI installed
- [ ] VS Code Python debugging configured

### Plan Week 2:

- [ ] Review Week 2 goals
- [ ] Schedule daily study time
- [ ] Block calendar for weekend project time

---

## 💡 Tips for Success Going Forward

### Daily Habits:

1. **Morning:** Read for 30-40 minutes
2. **Code:** At least 1 hour/day of Python
3. **Commit:** Push to GitHub daily
4. **Evening:** Light reading 20-30 minutes

### Weekend Projects:

- Saturday: Build features (6 hours)
- Sunday: Deploy & document (4 hours)

### Weekly Review:

- Sunday evening: 30 minutes
- What worked? What didn't?
- Adjust for next week

### Momentum:

- Don't break the chain
- Even 30 minutes counts
- Progress over perfection
- Ship, don't polish endlessly

---

## 🎓 What's Next: Week 2 Preview

**Learning:**

- Python classes and OOP
- Error handling and exceptions
- FastAPI with SQLAlchemy ORM
- Advanced SQL (subqueries, window functions)

**Building:**

- Enhance Task Manager API
- Add user model and relationships
- Structured error responses
- API versioning

**Reading:**

- Continue Phoenix Project
- Python Crash Course Ch 9-11 (Classes, Files, Testing)
- Start "Clean Code"

**Goals:**

- 15+ new commits
- SQLAlchemy models working
- Python OOP practiced
- Books: 150+ more pages

---

## ✅ Final Week 1 Checklist

Before starting Week 2:

- [ ] Task Manager API deployed and working
- [ ] GitHub repo public and documented
- [ ] Weekly review completed
- [ ] Week 2 prep done
- [ ] Rest day taken (Sunday evening - relax!)
- [ ] Celebrated your wins! 🎉

**Congratulations on completing Week 1!**

You went from zero to deployed Python API in 7 days. That's incredible progress!
