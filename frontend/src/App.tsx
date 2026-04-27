import { BrowserRouter as Router, Routes, Route, Link, NavLink, useLocation } from 'react-router-dom'
import AltaAcopio from './pages/AltaAcopio'
import ListaAcopios from './pages/ListaAcopios'
import DetalleAcopio from './pages/DetalleAcopio'
import Reportes from './pages/Reportes'
import ErrorBoundary from './components/ErrorBoundary'
import './App.css'

function AppLayout() {
    const location = useLocation()
    const isHome = location.pathname === '/'

    return (
        <div className="app">
            {!isHome && (
                <nav className="navbar">
                    <div className="container">
                        <h1>Acopios - Fontela Cristales</h1>
                        <ul className="nav-links">
                            <li>
                                <NavLink to="/" end>
                                    Inicio
                                </NavLink>
                            </li>
                            <li>
                                <NavLink
                                    to="/acopios"
                                    className={({ isActive }) => {
                                        const isDetalleAcopio = /^\/acopios\/[^/]+$/.test(location.pathname)
                                        return isActive || isDetalleAcopio ? 'active' : ''
                                    }}
                                >
                                    Acopios
                                </NavLink>
                            </li>
                            <li>
                                <NavLink to="/acopios/alta" end>
                                    Nuevo Acopio
                                </NavLink>
                            </li>
                            <li>
                                <NavLink to="/reportes" end>
                                    Reportes
                                </NavLink>
                            </li>
                        </ul>
                    </div>
                </nav>
            )}

            <main className="main-content">
                <div className="container">
                    <ErrorBoundary>
                        <Routes>
                            <Route path="/" element={<Home />} />
                            <Route path="/acopios" element={<ListaAcopios />} />
                            <Route path="/acopios/alta" element={<AltaAcopio />} />
                            <Route path="/acopios/:id" element={<DetalleAcopio />} />
                            <Route path="/reportes" element={<Reportes />} />
                        </Routes>
                    </ErrorBoundary>
                </div>
            </main>
        </div>
    )
}

function App() {
    return (
        <Router>
            <AppLayout />
        </Router>
    )
}

function Home() {
    return (
        <div className="home">
            <h1 className="home-title">Acopios - Fontela Cristales</h1>
            <div className="home-cards">
                 <Link to="/acopios/alta" className="card">
                    <h3>Nuevo Acopio</h3>
                    <p>Desde presupuesto PDF / SPF</p>
                </Link>
                <Link to="/acopios" className="card">
                    <h3>Ver Acopios</h3>
                    <p>Listado de saldos activos</p>
                </Link>
                <Link to="/reportes" className="card">
                    <h3>Reportes</h3>
                    <p>Consultas y estadísticas</p>
                </Link>
            </div>
        </div>
    )
}

export default App
