# Week 1: Complete Day-by-Day Guide

## 🎯 Week 1 Overview

**Goal:** Build and deploy your first full-stack application (React + FastAPI + SQL + Azure)

**Time Commitment:** 2-3 hours/day + 8-10 hours weekend
**Total:** ~20 hours

**Deliverables:**
- ✅ Task Manager app deployed to Azure
- ✅ GitHub repo with 20+ commits
- ✅ React, SQL, and Git basics mastered
- ✅ 2 books started

---

## 📅 MONDAY - Day 1: Setup & React Basics

### Morning (1 hour) - 6:00-7:00 AM
**Reading: 30 minutes**
- Start "The Phoenix Project" - Chapters 1-2
- This is a novel, so it's an easy, engaging read
- Take mental notes on IT challenges described

**React Setup: 30 minutes**
- Install Node.js from nodejs.org (if not installed)
- Verify: `node --version` (should be v20.x or later)
- Install VS Code (if not installed)
- Install VS Code extensions:
  - ES7+ React/Redux snippets
  - Prettier - Code formatter
  - ESLint

### Evening (1.5 hours) - 7:00-8:30 PM
**React Quick Start: 90 minutes**

1. **Create your first React app (10 minutes)**
```bash
# Open terminal
cd ~/projects
npm create vite@latest week1-react-practice -- --template react
cd week1-react-practice
npm install
npm run dev
```
- Open browser to http://localhost:5173
- You should see the Vite + React page!

2. **Follow React.dev Quick Start (60 minutes)**
- Go to react.dev/learn
- Complete "Quick Start" section
- Focus on:
  - Creating components
  - Writing JSX
  - Adding styles
  - Displaying data
  - Conditional rendering
  - Rendering lists

3. **Practice Exercise (20 minutes)**
Replace App.jsx with this:
```jsx
function App() {
  const skills = ["Python", "React", "SQL", "Azure", "DevOps"];
  
  return (
    <div style={{ padding: '20px', fontFamily: 'Arial' }}>
      <h1>My Tech Stack Learning Journey</h1>
      <p>Week 1: Building foundations</p>
      <h2>Skills I'm Learning:</h2>
      <ul>
        {skills.map((skill, index) => (
          <li key={index} style={{ margin: '10px 0' }}>
            {skill}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default App;
```

Save and watch it update in browser!

### Day 1 Checklist
- [ ] Node.js installed
- [ ] First React app running
- [ ] Understand JSX basics
- [ ] Created first component
- [ ] Read Phoenix Project Ch 1-2

---

## 📅 TUESDAY - Day 2: Git & SQL Basics

### Morning (1 hour) - 6:00-7:00 AM
**Reading: 30 minutes**
- Continue "The Phoenix Project" - Chapter 3
- Start "Python Crash Course" - Chapter 1 (if book arrived)

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

4. Initialize your React practice project:
```bash
cd ~/projects/week1-react-practice
git init
git add .
git commit -m "Initial commit: First React app"
```

5. Create GitHub repo:
   - GitHub → New Repository → "week1-react-practice"
   - Follow instructions to push existing repo

```bash
git remote add origin https://github.com/YOUR_USERNAME/week1-react-practice.git
git branch -M main
git push -u origin main
```

### Evening (1.5 hours) - 7:00-8:30 PM
**SQL Basics: 90 minutes**

1. **Setup (15 minutes)**
- Go to sqliteonline.com (no installation needed)
- OR install PostgreSQL locally (postgresql.org)

2. **SQLBolt Tutorial (60 minutes)**
- Go to sqlbolt.com
- Complete Lessons 1-6:
  - Lesson 1: SELECT queries 101
  - Lesson 2: Queries with constraints
  - Lesson 3: Filtering and sorting
  - Lesson 4: Reviewing SELECT
  - Lesson 5: Multi-table queries with JOINs
  - Lesson 6: Outer JOINs

3. **Practice Exercise (15 minutes)**
Create your first database:

```sql
-- Create users table
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Insert data
INSERT INTO users (id, name, email) VALUES
    (1, 'Alice Johnson', 'alice@email.com'),
    (2, 'Bob Smith', 'bob@email.com'),
    (3, 'Carol White', 'carol@email.com');

-- Query data
SELECT * FROM users;
SELECT * FROM users WHERE name LIKE 'A%';
SELECT COUNT(*) FROM users;
```

### Day 2 Checklist
- [ ] Git installed and configured
- [ ] GitHub account created
- [ ] First repo pushed to GitHub
- [ ] SQLBolt Lessons 1-6 complete
- [ ] Created first database table
- [ ] Wrote 10+ SQL queries

---

## 📅 WEDNESDAY - Day 3: React State & More SQL

### Morning (1 hour) - 6:00-7:00 AM
**Reading: 60 minutes**
- "Python Crash Course" Chapter 2 (Variables and data types)
- OR "The Phoenix Project" Chapter 4

### Evening (2 hours) - 7:00-9:00 PM
**React State with useState: 60 minutes**

1. Create new component (src/Counter.jsx):
```jsx
import { useState } from 'react';

function Counter() {
  const [count, setCount] = useState(0);
  
  return (
    <div style={{ textAlign: 'center', padding: '20px' }}>
      <h2>Counter: {count}</h2>
      <button onClick={() => setCount(count + 1)}>
        Increment
      </button>
      <button onClick={() => setCount(count - 1)}>
        Decrement
      </button>
      <button onClick={() => setCount(0)}>
        Reset
      </button>
    </div>
  );
}

export default Counter;
```

2. Build a To-Do List (src/TodoList.jsx):
```jsx
import { useState } from 'react';

function TodoList() {
  const [todos, setTodos] = useState([]);
  const [input, setInput] = useState('');
  
  const addTodo = () => {
    if (input.trim()) {
      setTodos([...todos, { id: Date.now(), text: input, done: false }]);
      setInput('');
    }
  };
  
  const toggleTodo = (id) => {
    setTodos(todos.map(todo => 
      todo.id === id ? { ...todo, done: !todo.done } : todo
    ));
  };
  
  const deleteTodo = (id) => {
    setTodos(todos.filter(todo => todo.id !== id));
  };
  
  return (
    <div style={{ maxWidth: '500px', margin: '20px auto', padding: '20px' }}>
      <h2>My To-Do List</h2>
      <div>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && addTodo()}
          placeholder="Add a task..."
          style={{ padding: '8px', width: '70%' }}
        />
        <button onClick={addTodo} style={{ padding: '8px', marginLeft: '10px' }}>
          Add
        </button>
      </div>
      
      <ul style={{ listStyle: 'none', padding: 0, marginTop: '20px' }}>
        {todos.map(todo => (
          <li key={todo.id} style={{ 
            padding: '10px', 
            margin: '10px 0', 
            border: '1px solid #ccc',
            borderRadius: '4px'
          }}>
            <span
              onClick={() => toggleTodo(todo.id)}
              style={{
                textDecoration: todo.done ? 'line-through' : 'none',
                cursor: 'pointer',
                flex: 1
              }}
            >
              {todo.text}
            </span>
            <button 
              onClick={() => deleteTodo(todo.id)}
              style={{ float: 'right' }}
            >
              Delete
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default TodoList;
```

3. Update App.jsx to show both components

4. Commit your work:
```bash
git add .
git commit -m "Add Counter and TodoList components with useState"
git push
```

**SQL Practice: 60 minutes**
- Complete SQLBolt Lessons 7-12
- Practice JOINs, Aggregations, GROUP BY
- Create a tasks table and practice queries:

```sql
CREATE TABLE tasks (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    completed BOOLEAN DEFAULT FALSE,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO tasks (id, title, description) VALUES
    (1, 'Learn React', 'Complete React tutorial', FALSE),
    (2, 'Practice SQL', 'Finish SQLBolt lessons', FALSE),
    (3, 'Setup Git', 'Push code to GitHub', TRUE);

-- Practice queries
SELECT * FROM tasks WHERE completed = FALSE;
SELECT COUNT(*) as total_tasks FROM tasks;
SELECT completed, COUNT(*) FROM tasks GROUP BY completed;
```

### Day 3 Checklist
- [ ] Understand useState hook
- [ ] Built Counter component
- [ ] Built TodoList component
- [ ] SQLBolt Lessons 7-12 complete
- [ ] Created tasks table
- [ ] Git commit and push

---

## 📅 THURSDAY - Day 4: useEffect & API Calls

### Morning (1 hour) - 6:00-7:00 AM
**Reading: 60 minutes**
- "Python Crash Course" Chapter 3 (Lists)
- OR continue "The Phoenix Project"

### Evening (2 hours) - 7:00-9:00 PM
**React useEffect and API Calls: 120 minutes**

1. Learn useEffect basics (30 minutes)
- Read: react.dev/reference/react/useEffect
- Understand component lifecycle

2. Build User List component (60 minutes):
```jsx
// src/UserList.jsx
import { useState, useEffect } from 'react';

function UserList() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  useEffect(() => {
    // Fetch users from JSONPlaceholder API
    fetch('https://jsonplaceholder.typicode.com/users')
      .then(response => response.json())
      .then(data => {
        setUsers(data);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, []); // Empty array = run once on mount
  
  if (loading) return <div>Loading users...</div>;
  if (error) return <div>Error: {error}</div>;
  
  return (
    <div style={{ padding: '20px' }}>
      <h2>User Directory</h2>
      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
        gap: '20px' 
      }}>
        {users.map(user => (
          <div key={user.id} style={{ 
            border: '1px solid #ddd', 
            padding: '15px',
            borderRadius: '8px'
          }}>
            <h3>{user.name}</h3>
            <p><strong>Email:</strong> {user.email}</p>
            <p><strong>Company:</strong> {user.company.name}</p>
            <p><strong>City:</strong> {user.address.city}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

export default UserList;
```

3. Add search functionality (30 minutes):
```jsx
// Add to UserList component
const [searchTerm, setSearchTerm] = useState('');

const filteredUsers = users.filter(user =>
  user.name.toLowerCase().includes(searchTerm.toLowerCase())
);

// Add this above the user cards:
<input
  type="text"
  placeholder="Search by name..."
  value={searchTerm}
  onChange={(e) => setSearchTerm(e.target.value)}
  style={{ padding: '10px', width: '100%', marginBottom: '20px' }}
/>

// Use filteredUsers instead of users in map
```

4. Commit:
```bash
git add .
git commit -m "Add UserList with API fetch and search"
git push
```

### Day 4 Checklist
- [ ] Understand useEffect hook
- [ ] Fetched data from API
- [ ] Handled loading states
- [ ] Implemented search filter
- [ ] Git commit and push

---

## 📅 FRIDAY - Day 5: Azure Setup & FastAPI Intro

### Morning (1 hour) - 6:00-7:00 AM
**Reading: 60 minutes**
- "Python Crash Course" Chapter 4 (Working with lists)
- Take notes on list operations

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

1. Install Python and FastAPI (15 minutes):
```bash
# Verify Python installation
python --version  # Should be 3.11+

# Create project directory
mkdir week1-backend
cd week1-backend

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate
# OR Mac/Linux
source venv/bin/activate

# Install FastAPI
pip install fastapi uvicorn[standard]
```

2. Create your first API (30 minutes):
```python
# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI!"}

@app.get("/tasks")
def get_tasks():
    return [
        {"id": 1, "title": "Learn React", "completed": False},
        {"id": 2, "title": "Learn SQL", "completed": False},
        {"id": 3, "title": "Setup Azure", "completed": True}
    ]

@app.get("/tasks/{task_id}")
def get_task(task_id: int):
    return {"id": task_id, "title": "Sample task", "completed": False}
```

3. Run the API (5 minutes):
```bash
uvicorn main:app --reload
```
- Open browser to http://localhost:8000
- Go to http://localhost:8000/docs (Swagger UI)
- Test your endpoints!

4. Connect React to API (40 minutes):

Update your React TodoList to fetch from your API:
```jsx
// Update TodoList.jsx
useEffect(() => {
  fetch('http://localhost:8000/tasks')
    .then(response => response.json())
    .then(data => setTodos(data))
    .catch(err => console.error('Error:', err));
}, []);
```

5. Git setup for backend:
```bash
# In week1-backend directory
git init
echo "venv/" >> .gitignore
echo "__pycache__/" >> .gitignore
git add .
git commit -m "Initial FastAPI setup"

# Create GitHub repo and push
```

### Day 5 Checklist
- [ ] Azure account created
- [ ] FastAPI installed
- [ ] First API created
- [ ] Swagger docs working
- [ ] React connected to API
- [ ] Backend code in Git

---

## 📅 WEEKEND - Days 6-7: Build Task Manager App

### Saturday (6 hours)

**Morning (3 hours) - 9:00 AM - 12:00 PM**

**1. Setup PostgreSQL Database (30 minutes)**
```bash
# Install PostgreSQL (or use SQLite for simplicity)
# For SQLite (simpler):
pip install databases[sqlite]
```

**2. Create Database Schema (30 minutes)**
```sql
-- If using SQLite, create tasks.db
CREATE TABLE tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    completed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**3. Build Complete FastAPI Backend (2 hours)**
```python
# main.py - Complete CRUD API
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
from typing import Optional

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Task(BaseModel):
    title: str
    description: Optional[str] = ""
    completed: bool = False

def get_db():
    conn = sqlite3.connect('tasks.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.get("/tasks")
def get_tasks():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tasks ORDER BY created_at DESC")
    tasks = [dict(row) for row in cur.fetchall()]
    conn.close()
    return tasks

@app.post("/tasks")
def create_task(task: Task):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO tasks (title, description, completed) VALUES (?, ?, ?)",
        (task.title, task.description, task.completed)
    )
    task_id = cur.lastrowid
    conn.commit()
    conn.close()
    return {"id": task_id, **task.dict()}

@app.patch("/tasks/{task_id}")
def update_task(task_id: int, completed: bool):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE tasks SET completed = ? WHERE id = ?",
        (completed, task_id)
    )
    conn.commit()
    conn.close()
    return {"id": task_id, "completed": completed}

@app.delete("/tasks/{task_id}")
def delete_task(task_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()
    return {"message": "Task deleted"}
```

Test all endpoints in Swagger UI!

**Afternoon (3 hours) - 1:00 PM - 4:00 PM**

**4. Build Complete React Frontend (3 hours)**

Create a new React project for the task manager:
```bash
npm create vite@latest task-manager-app -- --template react
cd task-manager-app
npm install
```

Update src/App.jsx with complete task manager:
```jsx
import { useState, useEffect } from 'react';
import './App.css';

const API_URL = 'http://localhost:8000';

function App() {
  const [tasks, setTasks] = useState([]);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchTasks();
  }, []);

  const fetchTasks = async () => {
    try {
      const response = await fetch(`${API_URL}/tasks`);
      const data = await response.json();
      setTasks(data);
      setLoading(false);
    } catch (error) {
      console.error('Error fetching tasks:', error);
      setLoading(false);
    }
  };

  const addTask = async (e) => {
    e.preventDefault();
    if (!title.trim()) return;

    try {
      const response = await fetch(`${API_URL}/tasks`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, description, completed: false })
      });
      const newTask = await response.json();
      setTasks([newTask, ...tasks]);
      setTitle('');
      setDescription('');
    } catch (error) {
      console.error('Error adding task:', error);
    }
  };

  const toggleTask = async (taskId, currentStatus) => {
    try {
      await fetch(`${API_URL}/tasks/${taskId}?completed=${!currentStatus}`, {
        method: 'PATCH'
      });
      setTasks(tasks.map(task =>
        task.id === taskId ? { ...task, completed: !currentStatus } : task
      ));
    } catch (error) {
      console.error('Error updating task:', error);
    }
  };

  const deleteTask = async (taskId) => {
    try {
      await fetch(`${API_URL}/tasks/${taskId}`, { method: 'DELETE' });
      setTasks(tasks.filter(task => task.id !== taskId));
    } catch (error) {
      console.error('Error deleting task:', error);
    }
  };

  if (loading) return <div className="container">Loading...</div>;

  const completedCount = tasks.filter(t => t.completed).length;
  const totalCount = tasks.length;

  return (
    <div className="container">
      <div className="header">
        <h1>📋 Task Manager</h1>
        <p className="subtitle">Week 1 Full-Stack Project</p>
        <div className="stats">
          <span>{completedCount} / {totalCount} completed</span>
        </div>
      </div>

      <form onSubmit={addTask} className="add-form">
        <input
          type="text"
          placeholder="Task title..."
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className="input"
          required
        />
        <input
          type="text"
          placeholder="Description (optional)..."
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          className="input"
        />
        <button type="submit" className="btn-primary">
          Add Task
        </button>
      </form>

      <div className="task-list">
        {tasks.length === 0 ? (
          <p className="empty-state">No tasks yet. Add one above!</p>
        ) : (
          tasks.map(task => (
            <div key={task.id} className={`task-card ${task.completed ? 'completed' : ''}`}>
              <div className="task-content" onClick={() => toggleTask(task.id, task.completed)}>
                <div className="checkbox">
                  {task.completed ? '✅' : '⬜'}
                </div>
                <div className="task-details">
                  <h3>{task.title}</h3>
                  {task.description && <p>{task.description}</p>}
                </div>
              </div>
              <button
                onClick={() => deleteTask(task.id)}
                className="btn-delete"
              >
                🗑️
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

export default App;
```

Add styling (src/App.css):
```css
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  min-height: 100vh;
}

.container {
  max-width: 800px;
  margin: 0 auto;
  padding: 40px 20px;
}

.header {
  text-align: center;
  color: white;
  margin-bottom: 40px;
}

.header h1 {
  font-size: 3rem;
  margin-bottom: 10px;
}

.subtitle {
  font-size: 1.2rem;
  opacity: 0.9;
}

.stats {
  margin-top: 20px;
  font-size: 1.1rem;
  font-weight: 600;
}

.add-form {
  background: white;
  padding: 30px;
  border-radius: 12px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
  margin-bottom: 30px;
}

.input {
  width: 100%;
  padding: 12px 16px;
  margin-bottom: 15px;
  border: 2px solid #e0e0e0;
  border-radius: 8px;
  font-size: 1rem;
  transition: border-color 0.3s;
}

.input:focus {
  outline: none;
  border-color: #667eea;
}

.btn-primary {
  width: 100%;
  padding: 12px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.2s;
}

.btn-primary:hover {
  transform: translateY(-2px);
}

.task-list {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.task-card {
  background: white;
  padding: 20px;
  border-radius: 12px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  display: flex;
  justify-content: space-between;
  align-items: center;
  transition: all 0.3s;
}

.task-card:hover {
  box-shadow: 0 8px 15px rgba(0, 0, 0, 0.2);
  transform: translateY(-2px);
}

.task-card.completed {
  opacity: 0.7;
}

.task-content {
  display: flex;
  align-items: flex-start;
  gap: 15px;
  flex: 1;
  cursor: pointer;
}

.checkbox {
  font-size: 1.5rem;
}

.task-details h3 {
  font-size: 1.2rem;
  margin-bottom: 5px;
  text-decoration: none;
}

.completed .task-details h3 {
  text-decoration: line-through;
  color: #999;
}

.task-details p {
  color: #666;
  font-size: 0.9rem;
}

.btn-delete {
  padding: 8px 12px;
  background: #ff4757;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 1.2rem;
  transition: transform 0.2s;
}

.btn-delete:hover {
  transform: scale(1.1);
}

.empty-state {
  text-align: center;
  padding: 60px 20px;
  color: white;
  font-size: 1.2rem;
  opacity: 0.8;
}
```

Test your complete app!

**Commit everything:**
```bash
git add .
git commit -m "Complete task manager frontend"
git push
```

### Sunday (4 hours)

**Morning (2 hours) - 9:00 AM - 11:00 AM**

**5. Deploy Backend to Azure (2 hours)**

1. Create requirements.txt:
```
fastapi
uvicorn[standard]
python-multipart
```

2. Create Dockerfile (optional but recommended):
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

3. Deploy to Azure App Service:
```bash
# Install Azure CLI
# Then login
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
cd week1-backend
zip -r app.zip .
az webapp deployment source config-zip \
  --resource-group TaskManagerRG \
  --name task-manager-api-[yourname] \
  --src app.zip
```

Your API is now live at: https://task-manager-api-[yourname].azurewebsites.net

**Afternoon (2 hours) - 1:00 PM - 3:00 PM**

**6. Deploy Frontend to Azure Static Web Apps (1 hour)**

1. Build React app:
```bash
cd task-manager-app
npm run build
```

2. Update API URL in code to production URL

3. Deploy to Azure Static Web Apps:
- Go to portal.azure.com
- Create Static Web App
- Connect to GitHub
- Azure will auto-deploy!

OR use Azure CLI:
```bash
npm install -g @azure/static-web-apps-cli
swa deploy ./dist --env production
```

**7. Final Polish & Documentation (1 hour)**

Create README.md in both repos:
```markdown
# Task Manager - Week 1 Full-Stack Project

A full-stack task management application built with React, FastAPI, and SQL.

## 🚀 Tech Stack

**Frontend:** React, Vite, CSS3
**Backend:** Python, FastAPI, SQLite
**Deployment:** Azure App Service, Azure Static Web Apps

## ✨ Features

- ✅ Create, read, update, delete tasks
- ✅ Mark tasks as complete/incomplete
- ✅ Task descriptions
- ✅ Real-time statistics
- ✅ Responsive design
- ✅ Deployed to Azure

## 🔗 Live Demo

- **Frontend:** [URL]
- **Backend API:** [URL]
- **API Docs:** [URL/docs]

## 📸 Screenshots

[Add screenshots]

## 🛠️ Local Development

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
uvicorn main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## 📚 What I Learned

- React hooks (useState, useEffect)
- FastAPI CRUD operations
- SQL database design
- Azure deployment
- Git workflow

## 🎯 Next Steps

- Add user authentication
- Implement categories
- Add due dates
- Deploy to production

---

Built as part of my 14-week career transition to Full-Stack Cloud DevOps Engineer.
```

Commit and push both READMEs.

### Week 1 Complete! 🎉

**Evening (1 hour) - 7:00 PM - 8:00 PM**

**8. Weekly Review & Week 2 Prep**

Create a simple checklist file (checklist.md):

```markdown
# Week 1 Review - COMPLETE ✅

## Achievements
- [x] Task Manager app built and deployed
- [x] React fundamentals mastered
- [x] SQL basics learned (SQLBolt Lessons 1-12)
- [x] Git workflow established
- [x] Azure account created
- [x] FastAPI backend deployed
- [x] React frontend deployed
- [x] 30+ GitHub commits

## Books Progress
- [x] The Phoenix Project - Chapters 1-4 (20% done)
- [x] Python Crash Course - Chapters 1-4 (40% done)

## Code Stats
- GitHub commits: 30+
- Lines of code: ~500
- Projects: 1 complete full-stack app

## What I Learned
- React hooks completely changed my understanding of state
- SQL JOINs are powerful for multi-table queries
- Azure deployment is simpler than expected
- Git commits should be frequent and meaningful

## Challenges Faced
- CORS issues (solved with middleware)
- Async/await in React took practice
- Azure deployment initially confusing

## Week 2 Goals
- Learn React Router
- Complex SQL (advanced JOINs)
- Azure DevOps setup
- Start Project 1 planning
```

**Celebrate! 🎉**
- Share your deployed app with friends
- Post on LinkedIn (optional)
- Take screenshots for portfolio
- Feel proud of your progress!

---

## 📊 Week 1 Success Metrics

Check all that apply:
- [ ] Task Manager fully functional
- [ ] Frontend deployed to Azure
- [ ] Backend deployed to Azure
- [ ] GitHub repo with 20+ commits
- [ ] SQLBolt completed (Lessons 1-12)
- [ ] React basics understood (hooks, components, state)
- [ ] Read ~100 pages (Phoenix Project + Python Crash Course)
- [ ] Can explain to someone how your app works

**If you checked 6+, you CRUSHED Week 1!** 💪

---

## 🎯 Key Takeaways from Week 1

### React
- Components are the building blocks
- State changes trigger re-renders
- useEffect runs after render
- Props flow down, events flow up

### SQL
- SELECT retrieves data
- JOIN combines tables
- WHERE filters results
- GROUP BY aggregates data

### Git
- Commit frequently
- Write meaningful messages
- Push to GitHub daily
- Branches for features (coming Week 2)

### Azure
- App Service for backend APIs
- Static Web Apps for React
- Resource groups organize resources
- Free tier is generous for learning

### FastAPI
- Automatic API documentation (Swagger)
- Type hints with Pydantic
- CORS middleware for React
- Simple and fast

---

## 📚 Reading Summary

**Books Started:**
1. **"The Phoenix Project"** (~100 pages)
   - Key insight: IT challenges are universal
   - DevOps mindset: Continuous improvement
   - Next: Continue to Part 2

2. **"Python Crash Course"** (~80 pages)
   - Variables, data types, lists
   - Python fundamentals solid
   - Next: Dictionaries and functions

**Total Reading:** ~180 pages
**Time Invested:** ~7 hours (30-60 min/day)

---

## 🚀 Prepare for Week 2

### Order/Download (if you haven't):
- [ ] "Clean Code" by Robert C. Martin
- [ ] "Learning React" (or React Key Concepts)

### Technical Setup:
- [ ] PostgreSQL installed (if using it)
- [ ] Azure DevOps account created
- [ ] VS Code extensions updated

### Plan Week 2:
- [ ] Review Week 2 goals
- [ ] Schedule daily study time
- [ ] Block calendar for weekend project time

---

## 💡 Tips for Success Going Forward

### Daily Habits:
1. **Morning:** Read for 30-40 minutes
2. **Code:** At least 1 hour/day
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
- React Router (multi-page apps)
- Advanced SQL (complex JOINs)
- Azure SQL Database
- Azure DevOps basics

**Building:**
- Enhance task manager
- Multi-page structure
- Categories and filters
- Statistics dashboard

**Reading:**
- Continue Phoenix Project
- Start "Clean Code"
- Finish Python Crash Course Part 1

**Goals:**
- 15+ new commits
- Azure SQL connected
- Azure DevOps org setup
- Books: 150+ more pages

---

## ✅ Final Week 1 Checklist

Before starting Week 2:
- [ ] Task Manager deployed and working
- [ ] GitHub repos public and documented
- [ ] Weekly review completed
- [ ] Week 2 prep done
- [ ] Rest day taken (Sunday evening - relax!)
- [ ] Celebrated your wins! 🎉

**Congratulations on completing Week 1!**

You went from zero to deployed full-stack application in 7 days. That's incredible progress!

**Week 2 starts tomorrow. You're ready. Let's go! 🚀**