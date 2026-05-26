import { Link, Route, Routes } from "react-router-dom";
import PatentDetailPage from "./pages/PatentDetailPage";
import PatentListPage from "./pages/PatentListPage";

export default function App() {
  return (
    <div className="app-shell">
      <header className="app-header">
        <Link className="logo-link" to="/">
          US Patent Intelligence
        </Link>
        <p className="app-subtitle">Browse recent publications and generate summaries only when you request one.</p>
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
