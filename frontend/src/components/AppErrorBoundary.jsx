import React from "react";

export default class AppErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <main className="app-main">
          <section className="panel">
            <h1>Patent Summaries</h1>
            <div className="error" role="alert">
              The app could not render. Refresh the page, then check that the latest production bundle is deployed.
            </div>
          </section>
        </main>
      );
    }

    return this.props.children;
  }
}
