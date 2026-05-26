import { Link } from "react-router-dom";

export default function PatentTable({ items }) {
  if (!items.length) {
    return <div className="empty">No patents match your filters.</div>;
  }

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Publication</th>
            <th>Title</th>
            <th>Type</th>
            <th>Publication Date</th>
            <th>Filing Date</th>
            <th>Assignee</th>
            <th>CPC</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.publication_number}>
              <td>
                <Link to={`/patents/${item.publication_number}`}>{item.publication_number}</Link>
              </td>
              <td>{item.title || "Untitled"}</td>
              <td>{item.doc_type}</td>
              <td>{item.publication_date || "-"}</td>
              <td>{item.filing_date || "-"}</td>
              <td>{item.assignee || "-"}</td>
              <td>{item.cpc_primary || "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
