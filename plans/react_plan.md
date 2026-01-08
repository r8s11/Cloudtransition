# React Learning Plan

> Complete React curriculum from fundamentals to production-ready applications

**Timeline:** Weeks 1-8 (parallel with other learning)  
**Time Commitment:** 6 hours/week  
**Goal:** Build modern, performant React applications

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Week 1-2: React Fundamentals](#week-1-2-react-fundamentals)
3. [Week 3-4: Advanced Patterns](#week-3-4-advanced-patterns)
4. [Week 5-6: State Management](#week-5-6-state-management)
5. [Week 7-8: Production Ready](#week-7-8-production-ready)
6. [Resources](#resources)
7. [Practice Projects](#practice-projects)

---

## 🎯 Overview

### What You'll Learn
- React fundamentals (JSX, components, props, state)
- Hooks (useState, useEffect, useContext, custom hooks)
- React Router for navigation
- State management (Context API, React Query)
- Performance optimization
- Testing and best practices

### Prerequisites
- Basic JavaScript (ES6+)
- HTML & CSS fundamentals
- Node.js installed
- Basic terminal/command line

---

## Week 1-2: React Fundamentals

### Topics

#### Day 1-2: Setup & JSX
- [ ] Create React app with Vite
- [ ] Understand JSX syntax
- [ ] JavaScript in JSX with `{}`
- [ ] Conditional rendering
- [ ] Lists and keys

**Resources:**
- react.dev/learn (Quick Start section)
- Vite documentation

**Practice:**
```jsx
function SkillList() {
  const skills = ["React", "Python", "SQL", "Azure"];
  return (
    <ul>
      {skills.map((skill, index) => (
        <li key={index}>{skill}</li>
      ))}
    </ul>
  );
}
```

#### Day 3-4: Components & Props
- [ ] Functional components
- [ ] Props (properties)
- [ ] Props destructuring
- [ ] Default props
- [ ] Children prop
- [ ] Component composition

**Practice:**
```jsx
function Card({ title, description, status = "active" }) {
  return (
    <div className="card">
      <h3>{title}</h3>
      <p>{description}</p>
      <span className={`badge ${status}`}>{status}</span>
    </div>
  );
}
```

#### Day 5-7: State with useState
- [ ] What is state?
- [ ] useState hook
- [ ] Updating state
- [ ] Multiple state variables
- [ ] State with objects
- [ ] State with arrays

**Practice:**
```jsx
function Counter() {
  const [count, setCount] = useState(0);
  const [history, setHistory] = useState([]);
  
  const increment = () => {
    setCount(count + 1);
    setHistory([...history, count + 1]);
  };
  
  return (
    <div>
      <h2>Count: {count}</h2>
      <button onClick={increment}>Increment</button>
      <p>History: {history.join(", ")}</p>
    </div>
  );
}
```

#### Day 8-10: Effects with useEffect
- [ ] Component lifecycle
- [ ] useEffect basics
- [ ] Dependency array
- [ ] Cleanup functions
- [ ] Fetching data
- [ ] Common patterns

**Practice:**
```jsx
function UserProfile({ userId }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    fetch(`/api/users/${userId}`)
      .then(res => res.json())
      .then(data => {
        setUser(data);
        setLoading(false);
      });
  }, [userId]);  // Re-fetch when userId changes
  
  if (loading) return <div>Loading...</div>;
  return <div>{user.name}</div>;
}
```

#### Day 11-14: Events & Forms
- [ ] Event handling
- [ ] Synthetic events
- [ ] Form inputs
- [ ] Controlled components
- [ ] Form submission
- [ ] Input validation

**Practice:**
```jsx
function LoginForm() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState({});
  
  const handleSubmit = (e) => {
    e.preventDefault();
    const newErrors = {};
    
    if (!email.includes('@')) {
      newErrors.email = 'Invalid email';
    }
    if (password.length < 8) {
      newErrors.password = 'Password too short';
    }
    
    if (Object.keys(newErrors).length === 0) {
      // Submit form
      console.log('Submitted:', { email, password });
    } else {
      setErrors(newErrors);
    }
  };
  
  return (
    <form onSubmit={handleSubmit}>
      <input
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="Email"
      />
      {errors.email && <span>{errors.email}</span>}
      
      <input
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        placeholder="Password"
      />
      {errors.password && <span>{errors.password}</span>}
      
      <button type="submit">Login</button>
    </form>
  );
}
```

### Week 1-2 Project: Task Manager
Build a complete CRUD application:
- Create, read, update, delete tasks
- Mark tasks as complete
- Filter and search
- Local state management
- Connect to FastAPI backend

---

## Week 3-4: Advanced Patterns

### Topics

#### React Router
- [ ] Installation and setup
- [ ] Route configuration
- [ ] Link and NavLink
- [ ] URL parameters
- [ ] Nested routes
- [ ] Programmatic navigation
- [ ] 404 pages

**Practice:**
```jsx
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';

function App() {
  return (
    <BrowserRouter>
      <nav>
        <Link to="/">Home</Link>
        <Link to="/about">About</Link>
        <Link to="/users">Users</Link>
      </nav>
      
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/about" element={<About />} />
        <Route path="/users" element={<Users />} />
        <Route path="/users/:id" element={<UserDetail />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </BrowserRouter>
  );
}
```

#### Component Patterns
- [ ] Compound components
- [ ] Higher-Order Components (HOCs)
- [ ] Render props
- [ ] Controlled vs Uncontrolled
- [ ] Prop drilling problem

#### Custom Hooks
- [ ] Creating custom hooks
- [ ] useLocalStorage example
- [ ] useFetch example
- [ ] useForm example
- [ ] Reusable logic

**Practice:**
```jsx
// Custom hook for API calls
function useFetch(url) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  useEffect(() => {
    fetch(url)
      .then(res => res.json())
      .then(data => {
        setData(data);
        setLoading(false);
      })
      .catch(err => {
        setError(err);
        setLoading(false);
      });
  }, [url]);
  
  return { data, loading, error };
}

// Usage
function UserList() {
  const { data: users, loading, error } = useFetch('/api/users');
  
  if (loading) return <div>Loading...</div>;
  if (error) return <div>Error: {error.message}</div>;
  
  return (
    <ul>
      {users.map(user => <li key={user.id}>{user.name}</li>)}
    </ul>
  );
}
```

#### UI Libraries
- [ ] Choose: Tailwind CSS or Material-UI
- [ ] Installation and configuration
- [ ] Building consistent UI
- [ ] Responsive design
- [ ] Theming

### Week 3-4 Project: IT Asset Management (Frontend)
Multi-page application with:
- Dashboard with statistics
- Asset list with search/filter
- Asset detail pages
- Assignment tracking
- Professional UI with component library

---

## Week 5-6: State Management

### Topics

#### Context API
- [ ] Creating context
- [ ] Context Provider
- [ ] useContext hook
- [ ] When to use Context
- [ ] Context best practices

**Practice:**
```jsx
// Create Auth Context
const AuthContext = createContext();

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    // Check if user is logged in
    fetch('/api/auth/me')
      .then(res => res.json())
      .then(user => {
        setUser(user);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);
  
  const login = async (email, password) => {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password })
    });
    const user = await res.json();
    setUser(user);
  };
  
  const logout = () => {
    fetch('/api/auth/logout', { method: 'POST' });
    setUser(null);
  };
  
  return (
    <AuthContext.Provider value={{ user, login, logout, loading }}>
      {children}
    </AuthContext.Provider>
  );
}

// Use in components
function Profile() {
  const { user, logout } = useContext(AuthContext);
  
  return (
    <div>
      <p>Welcome, {user.name}!</p>
      <button onClick={logout}>Logout</button>
    </div>
  );
}
```

#### useReducer
- [ ] When to use useReducer
- [ ] Reducer functions
- [ ] Actions and dispatch
- [ ] Complex state management

**Practice:**
```jsx
const initialState = {
  items: [],
  filter: 'all',
  searchTerm: ''
};

function reducer(state, action) {
  switch (action.type) {
    case 'ADD_ITEM':
      return { ...state, items: [...state.items, action.payload] };
    case 'REMOVE_ITEM':
      return { ...state, items: state.items.filter(item => item.id !== action.payload) };
    case 'SET_FILTER':
      return { ...state, filter: action.payload };
    case 'SET_SEARCH':
      return { ...state, searchTerm: action.payload };
    default:
      return state;
  }
}

function ItemManager() {
  const [state, dispatch] = useReducer(reducer, initialState);
  
  const addItem = (item) => {
    dispatch({ type: 'ADD_ITEM', payload: item });
  };
  
  // ... rest of component
}
```

#### React Query / TanStack Query
- [ ] Installation and setup
- [ ] Queries (GET requests)
- [ ] Mutations (POST/PUT/DELETE)
- [ ] Caching
- [ ] Background refetching
- [ ] Optimistic updates

**Practice:**
```jsx
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

function TaskList() {
  const queryClient = useQueryClient();
  
  // Fetch tasks
  const { data: tasks, isLoading } = useQuery({
    queryKey: ['tasks'],
    queryFn: () => fetch('/api/tasks').then(res => res.json())
  });
  
  // Create task mutation
  const createTask = useMutation({
    mutationFn: (newTask) => 
      fetch('/api/tasks', {
        method: 'POST',
        body: JSON.stringify(newTask)
      }).then(res => res.json()),
    onSuccess: () => {
      // Invalidate and refetch
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
    }
  });
  
  if (isLoading) return <div>Loading...</div>;
  
  return (
    <div>
      {tasks.map(task => (
        <div key={task.id}>{task.title}</div>
      ))}
      <button onClick={() => createTask.mutate({ title: 'New Task' })}>
        Add Task
      </button>
    </div>
  );
}
```

### Week 5-6 Project: Infrastructure Platform (Frontend)
Advanced state management with:
- React Query for server state
- Context API for authentication
- Real-time updates
- Complex forms
- Data caching

---

## Week 7-8: Production Ready

### Topics

#### Performance Optimization
- [ ] React.memo
- [ ] useMemo hook
- [ ] useCallback hook
- [ ] Code splitting
- [ ] Lazy loading
- [ ] Bundle size optimization

**Practice:**
```jsx
import { memo, useMemo, useCallback } from 'react';
import { lazy, Suspense } from 'react';

// Memoize expensive component
const ExpensiveComponent = memo(function ExpensiveComponent({ data }) {
  // This only re-renders if data changes
  return <div>{/* expensive render */}</div>;
});

function ParentComponent() {
  const [count, setCount] = useState(0);
  const [items, setItems] = useState([]);
  
  // Memoize expensive calculation
  const total = useMemo(() => {
    return items.reduce((sum, item) => sum + item.price, 0);
  }, [items]);  // Only recalculate when items change
  
  // Memoize callback
  const handleClick = useCallback(() => {
    console.log('Clicked with count:', count);
  }, [count]);  // Only recreate when count changes
  
  return (
    <div>
      <ExpensiveComponent data={items} />
      <button onClick={handleClick}>Click</button>
    </div>
  );
}

// Lazy load components
const Dashboard = lazy(() => import('./Dashboard'));

function App() {
  return (
    <Suspense fallback={<div>Loading...</div>}>
      <Dashboard />
    </Suspense>
  );
}
```

#### Error Handling
- [ ] Error boundaries
- [ ] Try-catch in async
- [ ] User-friendly errors
- [ ] Error logging

**Practice:**
```jsx
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }
  
  static getDerivedStateFromError(error) {
    return { hasError: true };
  }
  
  componentDidCatch(error, errorInfo) {
    console.error('Error:', error, errorInfo);
  }
  
  render() {
    if (this.state.hasError) {
      return <h1>Something went wrong.</h1>;
    }
    return this.props.children;
  }
}

// Usage
<ErrorBoundary>
  <App />
</ErrorBoundary>
```

#### Testing
- [ ] React Testing Library
- [ ] Unit tests
- [ ] Integration tests
- [ ] Mocking API calls
- [ ] Test coverage

#### Best Practices
- [ ] File structure
- [ ] Naming conventions
- [ ] Component organization
- [ ] Props validation
- [ ] Accessibility (a11y)

### Week 7-8 Project: Portfolio Website
Production-ready features:
- Optimized performance (Lighthouse 95+)
- Error boundaries
- Lazy loading
- Responsive design
- Accessibility
- SEO optimization

---

## 📚 Resources

### Official Documentation
- [React.dev](https://react.dev/) - Official docs (best resource)
- [React Router](https://reactrouter.com/)
- [TanStack Query](https://tanstack.com/query/)

### Books
- "Learning React" by Alex Banks & Eve Porcello
- "React Key Concepts" by Maximilian Schwarzmüller

### Online Courses (Optional)
- Scrimba - Learn React (FREE interactive)
- Jonas Schmedtmann - Ultimate React Course (Udemy, $15)

### YouTube Channels
- Web Dev Simplified
- Traversy Media
- Jack Herrington

### Practice Platforms
- Frontend Mentor (real-world projects)
- React Challenges (github.com/alexgurr/react-coding-challenges)

---

## 🏗️ Practice Projects

### Beginner Level (Week 1-2)
1. Counter app
2. Todo list
3. Weather app
4. Recipe finder
5. Portfolio page

### Intermediate Level (Week 3-4)
1. E-commerce product catalog
2. Blog with routing
3. Movie search app
4. Quiz application
5. Dashboard with charts

### Advanced Level (Week 5-8)
1. Full-stack task manager
2. Real-time chat app
3. Social media feed
4. Project management tool
5. Admin dashboard

---

## ✅ Progress Checklist

### Week 1-2: Fundamentals
- [ ] Created first React app
- [ ] Understand JSX
- [ ] Built components with props
- [ ] Used useState for state
- [ ] Fetched data with useEffect
- [ ] Built task manager app

### Week 3-4: Advanced
- [ ] Implemented React Router
- [ ] Created custom hooks
- [ ] Used UI component library
- [ ] Built multi-page application
- [ ] Professional styling

### Week 5-6: State Management
- [ ] Implemented Context API
- [ ] Used useReducer
- [ ] Set up React Query
- [ ] Managed complex state
- [ ] Handled authentication

### Week 7-8: Production
- [ ] Optimized performance
- [ ] Added error boundaries
- [ ] Wrote tests
- [ ] Implemented best practices
- [ ] Deployed to production

---

## 🎯 Next Steps

After completing this plan:
1. Build more projects (practice is key)
2. Contribute to open source React projects
3. Learn Next.js or Remix (React frameworks)
4. Explore React Native (mobile apps)
5. Stay updated with React releases

---

**Remember: React is just JavaScript + UI concepts. Master the fundamentals, practice daily, and build real projects. You've got this! 🚀**