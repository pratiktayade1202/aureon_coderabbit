// src/components/ErrorBoundary.jsx
import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

class ErrorBoundary extends React.Component {
    constructor(props) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error) {
        return { hasError: true, error };
    }

    componentDidCatch(error, errorInfo) {
        // Log error in development only
        if (import.meta.env.DEV) {
            console.error('ErrorBoundary caught:', error, errorInfo);
        }

        // In production, you could send to monitoring service here
        // e.g., Sentry.captureException(error, { extra: errorInfo });
    }

    render() {
        if (this.state.hasError) {
            return (
                <div className="min-h-screen flex items-center justify-center bg-slate-50 p-4">
                    <div className="max-w-md w-full bg-white border border-red-200 rounded-lg p-6 shadow-sm">
                        <div className="flex items-center gap-3 mb-4">
                            <div className="p-2 bg-red-100 rounded-full">
                                <AlertTriangle className="text-red-500" size={24} />
                            </div>
                            <h2 className="text-lg font-semibold text-slate-900">
                                Something went wrong
                            </h2>
                        </div>
                        <p className="text-sm text-slate-600 mb-4">
                            An unexpected error occurred. Please try refreshing the page.
                        </p>
                        {import.meta.env.DEV && this.state.error && (
                            <pre className="text-xs bg-slate-100 p-3 rounded overflow-auto mb-4 text-red-600">
                                {this.state.error.toString()}
                            </pre>
                        )}
                        <button
                            onClick={() => window.location.reload()}
                            className="w-full flex items-center justify-center gap-2 bg-slate-900 text-white py-2.5 px-4 rounded-md hover:bg-black transition-colors font-medium"
                        >
                            <RefreshCw size={16} />
                            Reload Application
                        </button>
                    </div>
                </div>
            );
        }

        return this.props.children;
    }
}

export default ErrorBoundary;
