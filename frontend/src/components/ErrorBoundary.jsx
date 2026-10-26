import React from "react";
import { AlertTriangle, RotateCcw, RefreshCw } from "lucide-react";

export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    this.setState({ errorInfo });
    console.error("ErrorBoundary caught an unhandled rendering error:", error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
  };

  handleReload = () => {
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="w-screen h-screen flex flex-col items-center justify-center bg-slate-950 text-slate-200 p-6 select-none font-mono">
          <div className="stellarium-glass-dark border border-rose-500/30 rounded-2xl p-8 max-w-xl w-full shadow-2xl space-y-4">
            <div className="flex items-center space-x-3 text-rose-400">
              <div className="w-12 h-12 rounded-xl bg-rose-950/60 border border-rose-500/40 flex items-center justify-center">
                <AlertTriangle className="w-6 h-6" />
              </div>
              <div>
                <h2 className="text-base font-bold text-white uppercase tracking-wider">
                  SkyTrace Interface Exception
                </h2>
                <p className="text-xs text-rose-300">
                  A rendering error was contained before taking down the application.
                </p>
              </div>
            </div>

            <div className="bg-black/50 p-3 rounded-lg border border-white/10 text-xs text-rose-200 font-mono overflow-auto max-h-40 whitespace-pre-wrap">
              {this.state.error?.toString() || "Unknown rendering error"}
            </div>

            {this.state.errorInfo?.componentStack && (
              <details className="text-[10px] text-slate-400 font-mono">
                <summary className="cursor-pointer hover:text-white mb-1">
                  View Component Stack Trace
                </summary>
                <div className="bg-black/40 p-2 rounded border border-white/5 overflow-auto max-h-32 whitespace-pre-wrap">
                  {this.state.errorInfo.componentStack}
                </div>
              </details>
            )}

            <div className="pt-2 flex items-center justify-end space-x-3 text-xs font-sans">
              <button
                onClick={this.handleReset}
                className="px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-slate-200 flex items-center space-x-1.5 transition-colors"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>Recover Interface</span>
              </button>
              <button
                onClick={this.handleReload}
                className="px-3 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white font-bold flex items-center space-x-1.5 transition-colors shadow-lg"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Reload Page</span>
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
