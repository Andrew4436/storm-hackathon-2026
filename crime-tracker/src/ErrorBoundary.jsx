import { Component } from 'react'

/** Last line of defence: if anything throws while rendering, show a way out instead of a blank page. */
export default class ErrorBoundary extends Component {
  state = { failed: false }

  static getDerivedStateFromError() {
    return { failed: true }
  }

  render() {
    if (!this.state.failed) return this.props.children
    return (
      <div className="status-page">
        <div className="status surface" role="alert">
          <p className="status__title">Something went wrong loading the map. Reload the page.</p>
          <button type="button" className="btn btn--primary" onClick={() => window.location.reload()}>
            Reload
          </button>
        </div>
      </div>
    )
  }
}
