import { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
    children: ReactNode;
}

interface State {
    hasError: boolean;
    error: Error | null;
}

class ErrorBoundary extends Component<Props, State> {
    public state: State = {
        hasError: false,
        error: null,
    };

    public static getDerivedStateFromError(error: Error): State {
        return { hasError: true, error };
    }

    public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
        console.error('Uncaught error:', error, errorInfo);
    }

    public render() {
        if (this.state.hasError) {
            return (
                <div style={{ padding: '2rem', textAlign: 'center', backgroundColor: '#fff3cd', border: '1px solid #ffeeba', color: '#856404', margin: '2rem', borderRadius: '4px' }}>
                    <h2>Algo salió mal.</h2>
                    <p>Se ha producido un error inesperado en la aplicación.</p>
                    {this.state.error && (
                        <div style={{ marginTop: '1rem', textAlign: 'left', overflow: 'auto', maxHeight: '200px', backgroundColor: '#f8f9fa', padding: '1rem', border: '1px solid #e9ecef' }}>
                            <code style={{ fontFamily: 'monospace' }}>{this.state.error.toString()}</code>
                        </div>
                    )}
                    <button
                        onClick={() => window.location.reload()}
                        style={{ marginTop: '1rem', padding: '0.5rem 1rem', cursor: 'pointer' }}
                    >
                        Recargar Página
                    </button>
                </div>
            );
        }

        return this.props.children;
    }
}

export default ErrorBoundary;
