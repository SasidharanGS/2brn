import { Component, type ReactNode } from 'react'

interface Props { children: ReactNode }
interface State { hasError: boolean; message: string }

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, message: '' }
  }

  static getDerivedStateFromError(error: unknown): State {
    const message = error instanceof Error ? error.message : String(error)
    return { hasError: true, message }
  }

  handleReload = () => {
    this.setState({ hasError: false, message: '' })
    window.location.reload()
  }

  render() {
    if (this.state.hasError) {
      return (
        <div
          className="flex flex-col items-center justify-center h-full gap-4 p-8 text-center"
          style={{ background: 'var(--bg-base)', color: 'var(--text)' }}
        >
          <div className="text-4xl opacity-30">⚠</div>
          <div className="text-[15px] font-medium">Something went wrong</div>
          <div
            className="text-[12px] font-mono px-3 py-2 rounded-[8px] max-w-md break-words"
            style={{ background: 'var(--bg-surface)', color: 'var(--text-dim)' }}
          >
            {this.state.message}
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => this.setState({ hasError: false, message: '' })}
              className="px-4 py-2 rounded-[8px] text-[13px] font-medium"
              style={{ background: 'var(--bg-surface-2)', color: 'var(--text)', border: '1px solid var(--border)' }}
            >
              Try again
            </button>
            <button
              type="button"
              onClick={this.handleReload}
              className="px-4 py-2 rounded-[8px] text-[13px] font-medium"
              style={{ background: 'var(--accent)', color: '#fff' }}
            >
              Reload
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
