import React from "react";
import { Link } from "react-router-dom";

export default function PatentTable({ items, loading }) {
  if (loading && !items.length) {
    return <div className="loading">Loading patent records...</div>;
  }

  if (!items.length) {
    return (
      <div className="empty">
        <strong>No patent records available.</strong>
        <span>The production database is ready, but no USPTO records have been ingested yet.</span>
      </div>
    );
  }

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Publication</th>
            <th>Title</th>
            <th>Publication Date</th>
            <th>Assignee</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.publication_number}>
              <td>
                <Link to={`/patents/${item.publication_number}`}>{item.publication_number}</Link>
              </td>
              <td>{item.title || "Untitled"}</td>
              <td>{item.publication_date || "-"}</td>
              <td>{item.assignee || "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
