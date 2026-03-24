'use client';

import { Component, type ReactNode } from 'react';

type Props = { children: ReactNode; fallback?: ReactNode };
type State = { error: Error | null };

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  render() {
    if (this.state.error) {
      if (this.props.fallback) return this.props.fallback;
      return (
        <div className="border border-red-500/30 bg-red-500/5 rounded-lg p-6 text-center">
          <p className="text-red-400 font-bold mb-2">Something went wrong</p>
          <p className="text-sm text-gray-400 mb-4">{this.state.error.message}</p>
          <button
            type="button"
            onClick={() => this.setState({ error: null })}
            className="px-4 py-2 text-sm bg-gray-800 hover:bg-gray-700 text-white rounded transition-colors"
          >
            Try again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
