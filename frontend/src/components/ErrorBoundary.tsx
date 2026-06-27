import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
  onReset?: () => void;
}

interface State {
  hasError: boolean;
  message: string;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = {
    hasError: false,
    message: '',
  };

  static getDerivedStateFromError(error: Error): State {
    return {
      hasError: true,
      message: error.message || 'Something went wrong.',
    };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('UI error boundary caught:', error, info.componentStack);
  }

  private handleReset = () => {
    this.props.onReset?.();
    this.setState({ hasError: false, message: '' });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="classic-font flex min-h-dvh items-center justify-center bg-[var(--ui-bg)] px-6 text-[var(--phosphor)]">
          <div className="elevated-panel w-full max-w-lg rounded-3xl border border-[var(--ui-border)] p-8 text-center">
            <div className="type-eyebrow !tracking-[0.35em]">Application Error</div>
            <h1 className="mt-3 text-xl font-semibold text-[var(--phosphor-bright)]">The chat UI hit an unexpected error</h1>
            <p className="mt-3 text-sm leading-relaxed text-[var(--phosphor-dim)]">{this.state.message}</p>
            <button
              type="button"
              onClick={this.handleReset}
              className="mt-6 rounded-xl border border-[var(--ui-border)] bg-[var(--ui-bg-elevated)] px-4 py-2.5 text-sm font-medium text-[var(--phosphor)] transition hover:border-[var(--ui-border-strong)] hover:bg-[var(--ui-panel)]"
            >
              Try again
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
