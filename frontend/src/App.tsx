import { lazy, Suspense } from 'react'
import { createBrowserRouter, RouterProvider, Outlet, Link, NavLink, useLocation } from 'react-router-dom'
import AltaAcopio from './pages/AltaAcopio'
import ListaAcopios from './pages/ListaAcopios'
import DetalleAcopio from './pages/DetalleAcopio'
import ListaAcopioPaquetes from './pages/ListaAcopioPaquetes'
import AltaAcopioPaquete from './pages/AltaAcopioPaquete'
import DetalleAcopioPaquete from './pages/DetalleAcopioPaquete'
import ErrorBoundary from './components/ErrorBoundary'
import './App.css'

const Reportes = lazy(() => import('./pages/Reportes'))

function AppLayout() {
    const location = useLocation()
    const isHome = location.pathname === '/'
    const isListaAcopios = location.pathname === '/acopios'
    const isDetalleAcopio = /^\/acopios\/[^/]+$/.test(location.pathname) && location.pathname !== '/acopios/alta'
    const isPaquetes = /^\/paquetes(\/.*)?$/.test(location.pathname)
    const isDetallePaquete = /^\/paquetes\/[^/]+$/.test(location.pathname) && location.pathname !== '/paquetes/nuevo'
    const isInformes = location.pathname === '/reportes'
    const contentContainerClassName = [
        'container',
        isDetalleAcopio ? 'container-acopio' : '',
        isListaAcopios ? 'container-acopios-listado' : '',
        isPaquetes ? 'container-acopios-listado' : '',
        isInformes ? 'container-informes' : '',
    ].filter(Boolean).join(' ')

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
                                <NavLink
                                    to="/paquetes"
                                    className={({ isActive }) => {
                                        return isActive || isDetallePaquete ? 'active' : ''
                                    }}
                                >
                                    Paquetes de Obras
                                </NavLink>
                            </li>
                            <li>
                                <NavLink to="/paquetes/nuevo" end>
                                    Nuevo Paquete
                                </NavLink>
                            </li>
                            <li>
                                <NavLink to="/reportes" end>
                                    Informes
                                </NavLink>
                            </li>
                        </ul>
                    </div>
                </nav>
            )}

            <main className="main-content">
                <div className={contentContainerClassName}>
                    <ErrorBoundary>
                        <Outlet />
                    </ErrorBoundary>
                </div>
            </main>
        </div>
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
                <Link to="/paquetes" className="card">
                    <h3>Paquetes de Obras</h3>
                    <p>Consolidado por presupuestos</p>
                </Link>
                <Link to="/reportes" className="card">
                    <h3>Informes</h3>
                    <p>Panel ejecutivo y consultas</p>
                </Link>
            </div>
        </div>
    )
}

const router = createBrowserRouter([
    {
        path: "/",
        element: <AppLayout />,
        children: [
            { path: "", element: <Home /> },
            { path: "acopios", element: <ListaAcopios /> },
            { path: "acopios/alta", element: <AltaAcopio /> },
            { path: "acopios/:id", element: <DetalleAcopio /> },
            { path: "paquetes", element: <ListaAcopioPaquetes /> },
            { path: "paquetes/nuevo", element: <AltaAcopioPaquete /> },
            { path: "paquetes/:id", element: <DetalleAcopioPaquete /> },
            {
                path: "reportes",
                element: (
                    <Suspense fallback={<div className="loading">Cargando informes...</div>}>
                        <Reportes />
                    </Suspense>
                )
            }
        ]
    }
]);

function App() {
    return <RouterProvider router={router} />
}

export default App
