import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom'
import AltaAcopio from './pages/AltaAcopio'
import ListaAcopios from './pages/ListaAcopios'
import DetalleAcopio from './pages/DetalleAcopio'
import AltaPedido from './pages/AltaPedido'
import ListaPedidos from './pages/ListaPedidos'
import ImputacionConsumo from './pages/ImputacionConsumo'
import Reportes from './pages/Reportes'
import ErrorBoundary from './components/ErrorBoundary'
import './App.css'

function App() {
    return (
        <Router>
            <div className="app">
                <nav className="navbar">
                    <div className="container">
                        <h1>Acopios - Fontela Cristales</h1>
                        <ul className="nav-links">
                            <li><Link to="/">Inicio</Link></li>
                            <li><Link to="/acopios">Acopios</Link></li>
                            <li><Link to="/acopios/alta">Alta Acopio</Link></li>
                            <li><Link to="/pedidos">Pedidos</Link></li>
                            <li><Link to="/pedidos/alta">Alta Pedido</Link></li>
                            <li><Link to="/imputaciones">Imputar</Link></li>
                            <li><Link to="/reportes">Reportes</Link></li>
                        </ul>
                    </div>
                </nav>

                <main className="main-content">
                    <div className="container">
                        <ErrorBoundary>
                            <Routes>
                                <Route path="/" element={<Home />} />
                                <Route path="/acopios" element={<ListaAcopios />} />
                                <Route path="/acopios/alta" element={<AltaAcopio />} />
                                <Route path="/acopios/:id" element={<DetalleAcopio />} />
                                <Route path="/pedidos" element={<ListaPedidos />} />
                                <Route path="/pedidos/alta" element={<AltaPedido />} />
                                <Route path="/imputaciones" element={<ImputacionConsumo />} />
                                <Route path="/reportes" element={<Reportes />} />
                            </Routes>
                        </ErrorBoundary>
                    </div>
                </main>
            </div>
        </Router>
    )
}

function Home() {
    return (
        <div className="home">
            <h2>Sistema de Gestión de Acopios</h2>
            <p>Bienvenido al sistema de gestión de acopios de Fontela Cristales.</p>
            <div className="home-cards">
                <Link to="/acopios/alta" className="card">
                    <h3>Alta Acopio</h3>
                    <p>Cargar presupuesto PDF</p>
                </Link>
                <Link to="/acopios" className="card">
                    <h3>Ver Acopios</h3>
                    <p>Listado de acopios activos</p>
                </Link>
                <Link to="/pedidos/alta" className="card">
                    <h3>Alta Pedido</h3>
                    <p>Cargar pedido PDF</p>
                </Link>
                <Link to="/reportes" className="card">
                    <h3>Reportes</h3>
                    <p>Consultas y exportación</p>
                </Link>
            </div>
        </div>
    )
}

export default App
