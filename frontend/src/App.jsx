import { Navigate, NavLink, Route, Routes, useLocation } from 'react-router-dom'
import { Home, Leaf, MessageCircle, ScanLine, Sprout, Store, Landmark, Users, UserRound } from 'lucide-react'
import { useAuth } from './auth.jsx'
import { Loading } from './components/ui.jsx'
import AuthPage from './pages/Auth.jsx'
import FarmSetup from './pages/FarmSetup.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Recommend from './pages/Recommend.jsx'
import Crops from './pages/Crops.jsx'
import CycleDetail from './pages/CycleDetail.jsx'
import Scan from './pages/Scan.jsx'
import Markets from './pages/Markets.jsx'
import Schemes from './pages/Schemes.jsx'
import Assistant from './pages/Assistant.jsx'
import Community, { PostDetail } from './pages/Community.jsx'
import Profile from './pages/Profile.jsx'

const NAV = [
  { to: '/', label: 'Home', icon: Home, end: true },
  { to: '/recommend', label: 'What to grow', icon: Sprout },
  { to: '/crops', label: 'My crops', icon: Leaf },
  { to: '/scan', label: 'Check a leaf', icon: ScanLine },
  { to: '/markets', label: 'Prices & mandis', icon: Store },
  { to: '/schemes', label: 'Schemes', icon: Landmark },
  { to: '/assistant', label: 'Ask Krishi Mitra', icon: MessageCircle },
  { to: '/community', label: 'Community', icon: Users },
  { to: '/profile', label: 'Profile', icon: UserRound },
]
const TABS = [
  { to: '/', label: 'Home', icon: Home, end: true },
  { to: '/crops', label: 'Crops', icon: Leaf },
  { to: '/scan', label: 'Scan', icon: ScanLine, scan: true },
  { to: '/markets', label: 'Prices', icon: Store },
  { to: '/assistant', label: 'Ask', icon: MessageCircle },
]

export function Logo({ size = 30 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <rect width="32" height="32" rx="9" fill="#2E3A70" />
      <path d="M16 26V13" stroke="#E3A21A" strokeWidth="2.6" strokeLinecap="round" />
      <path d="M16 17c-5 0-7-3-7-7 4 0 7 2 7 7zM16 15c4.5 0 6.5-2.6 6.5-6.2-3.7 0-6.5 1.8-6.5 6.2z" fill="#E3A21A" />
    </svg>
  )
}

function Shell({ children }) {
  const { user, farm } = useAuth()
  return (
    <div className="shell">
      <nav className="rail" aria-label="Main">
        <NavLink to="/" className="brand"><Logo /><strong>AgriExpert</strong></NavLink>
        {NAV.map(({ to, label, icon: Icon, end }) => (
          <NavLink key={to} to={to} end={end} className="nav"><Icon size={20} />{label}</NavLink>
        ))}
        <div className="spacer" />
        <div className="who"><b>{user?.name}</b>{farm ? `${farm.district}, ${farm.state}` : 'No farm added yet'}</div>
      </nav>
      <main className="main">
        <div className="topbar">
          <NavLink to="/" className="brand"><Logo size={26} /><strong>AgriExpert</strong></NavLink>
          <div className="row" style={{ gap: 16 }}>
            <NavLink to="/community" aria-label="Community"><Users size={22} /></NavLink>
            <NavLink to="/profile" aria-label="Profile and more"><UserRound size={22} /></NavLink>
          </div>
        </div>
        <div className="page">{children}</div>
      </main>
      <nav className="tabbar" aria-label="Main">
        {TABS.map(({ to, label, icon: Icon, end, scan }) => (
          <NavLink key={to} to={to} end={end} className={scan ? 'scan' : ''}>
            {scan ? <span className="dot"><Icon size={22} /></span> : <Icon size={22} />}
            {!scan && label}
          </NavLink>
        ))}
      </nav>
    </div>
  )
}

export default function App() {
  const { user, farm, ready } = useAuth()
  const location = useLocation()
  if (!ready) return <div style={{ padding: 40 }}><Loading /></div>
  if (!user) {
    return (
      <Routes>
        <Route path="/login" element={<AuthPage />} />
        <Route path="*" element={<Navigate to="/login" replace state={{ from: location.pathname }} />} />
      </Routes>
    )
  }
  if (!farm && location.pathname !== '/farm') return <Navigate to="/farm" replace />
  return (
    <Shell>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/farm" element={<FarmSetup />} />
        <Route path="/recommend" element={<Recommend />} />
        <Route path="/crops" element={<Crops />} />
        <Route path="/crops/:id" element={<CycleDetail />} />
        <Route path="/scan" element={<Scan />} />
        <Route path="/markets" element={<Markets />} />
        <Route path="/schemes" element={<Schemes />} />
        <Route path="/assistant" element={<Assistant />} />
        <Route path="/community" element={<Community />} />
        <Route path="/community/:id" element={<PostDetail />} />
        <Route path="/profile" element={<Profile />} />
        <Route path="/login" element={<Navigate to="/" replace />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Shell>
  )
}
