import { Link, Route, Routes } from "react-router-dom";
import PatentDetailPage from "./pages/PatentDetailPage";
import PatentListPage from "./pages/PatentListPage";

export default function App() {
  return (
    <div className="app-shell">
      <header className="app-header">
        <Link className="logo-link" to="/">
          Patent Summaries
        </Link>
        <p className="app-subtitle">Recent U.S. patents, summarized when you need them.</p>
      </header>

      <main className="app-main">
        <Routes>
          <Route path="/" element={<PatentListPage />} />
          <Route path="/patents/:publicationNumber" element={<PatentDetailPage />} />
        </Routes>
      </main>
    </div>
  );
}
