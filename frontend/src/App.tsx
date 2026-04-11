import React from 'react'
import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom'
import IntakePage from './pages/IntakePage'
import CheckerPage from './pages/CheckerPage'
import DashboardPage from './pages/DashboardPage'

function App() {
  return (
    <BrowserRouter>
      <div className="app">
        <nav className="navbar">
          <Link to="/" className="navbar-brand">
            <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2a4 4 0 0 1 4 4c0 1.1-.45 2.1-1.17 2.83L12 12l-2.83-3.17A4 4 0 0 1 12 2z"/>
              <path d="M12 12v10"/>
              <path d="M8 22h8"/>
              <circle cx="12" cy="6" r="1"/>
            </svg>
            IASW
          </Link>
          <div className="navbar-links">
            <NavLink to="/">Dashboard</NavLink>
            <NavLink to="/intake">New Request</NavLink>
            <NavLink to="/checker">Checker Review</NavLink>
          </div>
        </nav>
        <main className="main-content">
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/intake" element={<IntakePage />} />
            <Route path="/checker" element={<CheckerPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}

function NavLink({ to, children }: { to: string; children: React.ReactNode }) {
  const location = useLocation()
  const isActive = location.pathname === to
  return (
    <Link to={to} className={`nav-link ${isActive ? 'active' : ''}`}>
      {children}
    </Link>
  )
}

export default App
