import React from "react";

export default function PatentFilters({ filters, onChange, onSubmit, onReset, loading }) {
  return (
    <form
      className="filters"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit();
      }}
    >
      <label>
        Keyword
        <input
          type="text"
          value={filters.q}
          onChange={(event) => onChange({ ...filters, q: event.target.value })}
          placeholder="e.g., battery thermal"
        />
      </label>

      <label>
        Assignee
        <input
          type="text"
          value={filters.assignee}
          onChange={(event) => onChange({ ...filters, assignee: event.target.value })}
          placeholder="Company name"
        />
      </label>

      <label>
        From
        <input
          type="date"
          value={filters.from_date}
          onChange={(event) => onChange({ ...filters, from_date: event.target.value })}
        />
      </label>

      <label>
        To
        <input
          type="date"
          value={filters.to_date}
          onChange={(event) => onChange({ ...filters, to_date: event.target.value })}
        />
      </label>

      <label>
        Sort
        <select value={filters.sort} onChange={(event) => onChange({ ...filters, sort: event.target.value })}>
          <option value="publication_date_desc">Newest First</option>
          <option value="publication_date_asc">Oldest First</option>
          <option value="title_asc">Title A-Z</option>
        </select>
      </label>

      <div className="filter-actions" aria-label="Filter actions">
        <button type="submit" disabled={loading}>
          {loading ? "Applying" : "Apply"}
        </button>
        <button
          type="button"
          className="secondary"
          onClick={onReset}
          disabled={loading}
        >
          Reset
        </button>
      </div>
    </form>
  );
}
