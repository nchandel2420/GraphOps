
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  Bot,
  CircleCheck,
  GitBranch,
  Send,
  ShieldAlert,
  Workflow,
} from "lucide-react";
import "./App.css";

const examples = [
  "Payment Gateway S3 is down. What is impacted, who owns it, and what did we do last time?",
  // "Which projects directly contain S3?",
  "Which projects contain services that depend on S3?",
  "List all services in Mutual Fund Platform",
];

export default function App() {
  const [question, setQuestion] = useState("");
  const [report, setReport] = useState("");
  const [submittedQuestion, setSubmittedQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function investigate(text = question) {
    const value = text.trim();
    if (!value || loading) return;

    setQuestion(value);
    setSubmittedQuestion(value);
    setLoading(true);
    setError("");
    setReport("");

    try {
      const response = await fetch(
        "http://127.0.0.1:8000/api/investigate",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question: value }),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "The investigation request failed."
        );
      }

      setReport(data.answer);
    } catch (err) {
      setError(
        `${err.message}. Check that the GraphOps API is running on port 8000.`
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">
            <Workflow size={23} />
          </div>
          <div>
            <strong>GraphOps</strong>
            <span>Incident Intelligence</span>
          </div>
        </div>

        <div className="nav-label">WORKSPACE</div>
        <div className="nav-item active">
          <Activity size={18} /> Investigation
        </div>
        <div className="nav-item">
          <GitBranch size={18} /> Service dependencies
        </div>
        <div className="nav-item">
          <ShieldAlert size={18} /> Incident history
        </div>

        <div className="sidebar-bottom">
          <div className="connection-dot" />
          <div>
            <strong>GraphOps workspace</strong>
            <span>Local development</span>
          </div>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div>
            <span className="eyebrow">OPERATIONS CENTER</span>
            <h1>Incident investigation</h1>
          </div>
          <div className="api-status">
            <span className="status-dot" />
            Agent workspace
          </div>
        </header>

        <section className="welcome">
          <div className="welcome-icon">
            <Bot size={28} />
          </div>
          <div>
            <div className="eyebrow">GRAPH-POWERED INVESTIGATION</div>
            <h2>Understand the impact. Find the evidence.</h2>
            <p>
              Investigate service failures, trace dependencies, identify
              owners, and retrieve previous incidents and decisions.
            </p>
          </div>
        </section>

        <section className="metrics">
          <div className="metric-card">
            <span>GRAPH DATABASE</span>
            <div><GitBranch size={19} /> FalkorDB</div>
            <small>Knowledge graph</small>
          </div>
          <div className="metric-card">
            <span>INVESTIGATION ENGINE</span>
            <div><Bot size={19} /> LangGraph</div>
            <small>Tool-enabled agent</small>
          </div>
          <div className="metric-card">
            <span>INVESTIGATION MODE</span>
            <div><Activity size={19} /> Evidence-based</div>
            <small>Retrieved graph data</small>
          </div>
        </section>

        <section className="workspace">
          <div className="panel question-panel">
            <div className="panel-heading">
              <div>
                <h3>Ask GraphOps</h3>
                <p>Describe an outage or ask about your services.</p>
              </div>
              <Activity size={20} />
            </div>

            <div className="example-list">
              {examples.map((example) => (
                <button
                  key={example}
                  className="example-button"
                  disabled={loading}
                  onClick={() => {
                    setQuestion(example);
                    investigate(example);
                  }}
                >
                  <span>{example}</span>
                  <ArrowUpRight size={17} />
                </button>
              ))}
            </div>

            <form
              className="question-form"
              onSubmit={(event) => {
                event.preventDefault();
                investigate();
              }}
            >
              <textarea
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                placeholder="e.g. Payment Gateway S3 is down. Which services and projects could be affected?"
                rows={4}
                maxLength={2000}
                disabled={loading}
              />
              <div className="form-footer">
                <span>{question.length}/2000 characters</span>
                <button
                  className="primary-button"
                  type="submit"
                  disabled={loading || question.trim().length < 3}
                >
                  {loading ? "Investigating..." : "Investigate"}
                  <Send size={16} />
                </button>
              </div>
            </form>
          </div>

          <div className="panel report-panel">
            <div className="panel-heading">
              <div>
                <h3>Investigation report</h3>
                <p>Evidence returned by your GraphOps agent</p>
              </div>
              <div className="report-icon">
                {loading ? (
                  <Activity size={20} className="spin" />
                ) : (
                  <CircleCheck size={20} />
                )}
              </div>
            </div>

            {!report && !loading && !error && (
              <div className="empty-state">
                <div className="empty-icon">
                  <AlertTriangle size={26} />
                </div>
                <h3>No investigation yet</h3>
                <p>
                  Choose an example or submit a question to see the
                  incident report here.
                </p>
              </div>
            )}

            {loading && (
              <div className="loading-state">
                <div className="loading-bar" />
                <h3>Investigating your graph...</h3>
                <p>
                  The agent is querying service relationships and
                  collecting relevant evidence.
                </p>
              </div>
            )}

            {error && (
              <div className="error-state">
                <AlertTriangle size={23} />
                <h3>Investigation failed</h3>
                <p>{error}</p>
                <button
                  className="secondary-button"
                  onClick={() => investigate(submittedQuestion)}
                >
                  Retry investigation
                </button>
              </div>
            )}

            {report && !loading && (
              <div className="report-content">
                <div className="report-question">
                  <span>QUESTION</span>
                  <p>{submittedQuestion}</p>
                </div>
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                    components={{
                        table: ({ children }) => (
                          <div className="report-table-wrapper">
                            <table className="report-table">{children}</table>
                          </div>
                        ),
                        th: ({ children }) => <th>{children}</th>,
                        td: ({ children }) => <td>{children}</td>,
                      }}
                >{report}</ReactMarkdown>
              </div>
            )}
          </div>
        </section>

        <footer>
          <span><CircleCheck size={14} /> GraphOps development environment</span>
          <span>Recommendations require human verification</span>
        </footer>
      </main>
    </div>
  );
}
