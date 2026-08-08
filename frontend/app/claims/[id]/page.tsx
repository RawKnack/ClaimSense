"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { getClaim } from "@/lib/api";

export default function ClaimStatusPage() {
  const params = useParams();
  const claimId = params.id as string;

  const { data, error, isLoading, isFetching } = useQuery({
    queryKey: ["claim", claimId],
    queryFn: () => getClaim(claimId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "PENDING" || status === "PROCESSING") return 1500;
      return false;
    },
  });

  if (isLoading) {
    return (
      <div className="card">
        <p className="muted">
          <span className="spinner" />
          Loading claim…
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="card">
        <p className="error">{String(error)}</p>
        <Link href="/" className="back">
          ← Submit another claim
        </Link>
      </div>
    );
  }

  if (!data) return null;

  const renderNotes = (notes: string | null | undefined) => {
    if (!notes) return null;
    const parts = notes.split(/\[System Info:\s*/i);
    const standardNotes = parts[0].trim();
    let systemInfo = parts[1] ? parts[1].replace(/\]$/, "").trim() : null;

    if (systemInfo) {
      if (
        systemInfo.includes("exceeded your current quota") ||
        systemInfo.includes("Quota exceeded") ||
        systemInfo.includes("429")
      ) {
        systemInfo = "Gemini API Quota Exceeded (429 Rate Limit). The system successfully fell back to the local deterministic rule engine.";
      }
    }

    return (
      <div className="notes-container">
        {standardNotes && <p className="notes-text">{standardNotes}</p>}
        {systemInfo && (
          <div className="system-warning-alert">
            <span className="warning-icon">⚠️</span>
            <div className="warning-content">
              <strong>System Notice</strong>
              <p>{systemInfo}</p>
            </div>
          </div>
        )}
      </div>
    );
  };
  const decision = data.decision?.decision;
  const isProcessing =
    data.status === "PENDING" || data.status === "PROCESSING";

  return (
    <div className="card">
      <p>
        <Link href="/" className="back">
          ← New claim
        </Link>
      </p>
      <h1>{data.claim_number}</h1>
      <p className="muted">Claim ID: {data.claim_id}</p>

      <p>
        Workflow status:{" "}
        <span className={`badge badge-${data.status}`}>{data.status}</span>
        {isFetching && isProcessing && (
          <span className="muted"> (refreshing…)</span>
        )}
      </p>

      <p>
        {data.member_name} · {data.member_id} · {data.treatment_date} · ₹
        {data.claim_amount}
      </p>

      {isProcessing && (
        <p className="muted">
          <span className="spinner" />
          Adjudication in progress… this page updates automatically.
        </p>
      )}

      {data.decision && (
        <>
          <h2>
            Outcome{" "}
            <span className={`badge badge-${decision}`}>{decision}</span>
          </h2>

          <div className="stat-grid">
            {data.decision.approved_amount != null && (
              <div className="stat">
                <p className="stat-value">₹{data.decision.approved_amount}</p>
                <p className="stat-label">Approved amount</p>
              </div>
            )}
            {data.decision.confidence_score != null && (
              <div className="stat">
                <p className="stat-value">
                  {(data.decision.confidence_score * 100).toFixed(0)}%
                </p>
                <p className="stat-label">Confidence</p>
              </div>
            )}
            {data.decision.deductions &&
              Object.entries(data.decision.deductions).map(([k, v]) => (
                <div className="stat" key={k}>
                  <p className="stat-value">₹{v}</p>
                  <p className="stat-label">{k}</p>
                </div>
              ))}
          </div>

          {data.decision.rejection_reasons &&
            data.decision.rejection_reasons.length > 0 && (
              <p>
                <strong>Rejection codes:</strong>{" "}
                {data.decision.rejection_reasons.join(", ")}
              </p>
            )}

          {renderNotes(data.decision.notes)}

          <h3>Full decision JSON</h3>
          <pre>{JSON.stringify(data.decision, null, 2)}</pre>
        </>
      )}

      {data.error_message && (
        <p className="error">Processing error: {data.error_message}</p>
      )}
    </div>
  );
}
