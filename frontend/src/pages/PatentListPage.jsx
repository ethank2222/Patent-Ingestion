import { useCallback, useEffect, useState } from "react";
import PatentFilters from "../components/PatentFilters";
import PatentTable from "../components/PatentTable";
import { listPatents } from "../api";

const DEFAULT_FILTERS = {
  q: "",
  assignee: "",
  from_date: "",
  to_date: "",
  sort: "publication_date_desc"
};

export default function PatentListPage() {
  const [filters, setFilters] = useState(DEFAULT_FILTERS);
  const [items, setItems] = useState([]);
  const [pagination, setPagination] = useState({ page: 1, pages: 1, total: 0, page_size: 20 });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const fetchPatents = useCallback(
    async (page = 1, currentFilters = filters) => {
      setLoading(true);
      setError("");
      try {
        const response = await listPatents({ ...currentFilters, page, page_size: pagination.page_size });
        setItems(response.items || []);
        setPagination(response.pagination || { page: 1, pages: 1, total: 0, page_size: 20 });
      } catch (err) {
        setError(err.message || "Failed to load patents");
      } finally {
        setLoading(false);
      }
    },
    [filters, pagination.page_size]
  );

  useEffect(() => {
    fetchPatents(1, filters);
  }, []);

  const handleApply = () => {
    fetchPatents(1, filters);
  };

  const handleReset = () => {
    setFilters(DEFAULT_FILTERS);
    fetchPatents(1, DEFAULT_FILTERS);
  };

  return (
    <section className="panel">
      <h1>Patent Summaries</h1>
      <p className="hint">Recent U.S. patent records with compact summaries generated on demand.</p>

      <PatentFilters
        filters={filters}
        onChange={setFilters}
        onSubmit={handleApply}
        onReset={handleReset}
        loading={loading}
      />

      {error && <div className="error">{error}</div>}
      <PatentTable items={items} />

      <div className="pagination">
        <button
          className="secondary"
          disabled={loading || pagination.page <= 1}
          onClick={() => fetchPatents(pagination.page - 1, filters)}
        >
          Previous
        </button>
        <span>
          Page {pagination.page} of {pagination.pages || 1} ({pagination.total} records)
        </span>
        <button
          className="secondary"
          disabled={loading || !pagination.has_next}
          onClick={() => fetchPatents(pagination.page + 1, filters)}
        >
          Next
        </button>
      </div>
    </section>
  );
}
