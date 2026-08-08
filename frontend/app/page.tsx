"use client";

import { useRouter } from "next/navigation";
import { DragEvent, FormEvent, useCallback, useState } from "react";
import { submitClaim } from "@/lib/api";

const SAMPLE_APPROVED = `{
  "prescription": {
    "doctor_name": "Dr. Sharma",
    "doctor_reg": "KA/45678/2015",
    "diagnosis": "Viral fever",
    "medicines_prescribed": ["Paracetamol 650mg"]
  },
  "bill": {
    "consultation_fee": 1000,
    "diagnostic_tests": 500
  }
}`;

const SAMPLE_REJECTED = `{
  "bill": {
    "consultation_fee": 1500,
    "medicines": 500
  }
}`;

type FileSlot = "prescription" | "bill";

export default function SubmitClaimPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [jsonText, setJsonText] = useState(SAMPLE_APPROVED);
  const [files, setFiles] = useState<Record<FileSlot, File | null>>({
    prescription: null,
    bill: null,
  });
  const [dragOver, setDragOver] = useState<FileSlot | null>(null);

  const onDrop = useCallback((slot: FileSlot, e: DragEvent) => {
    e.preventDefault();
    setDragOver(null);
    const file = e.dataTransfer.files[0];
    if (file) setFiles((f) => ({ ...f, [slot]: file }));
  }, []);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    const form = e.currentTarget;
    const data = new FormData(form);

    const json = jsonText.trim();
    if (json) {
      data.set("structured_documents", json);
    } else {
      data.delete("structured_documents");
    }

    if (files.prescription) {
      data.set("prescription", files.prescription);
    } else {
      data.delete("prescription");
    }
    if (files.bill) {
      data.set("bill", files.bill);
    } else {
      data.delete("bill");
    }

    try {
      const res = await submitClaim(data);
      router.push(`/claims/${res.claim_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Submit failed");
    } finally {
      setLoading(false);
    }
  }

  function FileDropZone({
    slot,
    label,
  }: {
    slot: FileSlot;
    label: string;
  }) {
    const file = files[slot];
    return (
      <div
        className={`dropzone ${dragOver === slot ? "dropzone-active" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(slot);
        }}
        onDragLeave={() => setDragOver(null)}
        onDrop={(e) => onDrop(slot, e)}
      >
        <p className="dropzone-title">{label}</p>
        {file ? (
          <p className="dropzone-file">{file.name}</p>
        ) : (
          <p className="muted">Drag & drop or click to browse</p>
        )}
        <input
          type="file"
          accept="image/*,.pdf"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) setFiles((prev) => ({ ...prev, [slot]: f }));
          }}
        />
        {file && (
          <button
            type="button"
            className="link-btn"
            onClick={() => setFiles((prev) => ({ ...prev, [slot]: null }))}
          >
            Remove
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="card">
      <h1>Submit OPD claim</h1>
      <p className="muted">
        Provide structured JSON and/or upload prescription and bill. The API
        adjudicates automatically; the status page polls until a decision is
        ready.
      </p>

      <div className="samples">
        <button
          type="button"
          className="secondary"
          onClick={() => setJsonText(SAMPLE_APPROVED)}
        >
          Load approved example
        </button>
        <button
          type="button"
          className="secondary"
          onClick={() => setJsonText(SAMPLE_REJECTED)}
        >
          Load bill-only (reject) example
        </button>
        <button type="button" className="secondary" onClick={() => setJsonText("")}>
          Clear JSON
        </button>
      </div>

      <form onSubmit={onSubmit}>
        <div className="grid2">
          <div>
            <label htmlFor="member_id">Member ID</label>
            <input id="member_id" name="member_id" defaultValue="EMP001" required />
          </div>
          <div>
            <label htmlFor="member_name">Member name</label>
            <input
              id="member_name"
              name="member_name"
              defaultValue="Rajesh Kumar"
              required
            />
          </div>
        </div>
        <div className="grid2">
          <div>
            <label htmlFor="treatment_date">Treatment date</label>
            <input
              id="treatment_date"
              name="treatment_date"
              type="date"
              defaultValue="2024-11-01"
              required
            />
          </div>
          <div>
            <label htmlFor="claim_amount">Claim amount (₹)</label>
            <input
              id="claim_amount"
              name="claim_amount"
              type="number"
              step="0.01"
              defaultValue={1500}
              required
            />
          </div>
        </div>
        <div className="grid2">
          <div>
            <label htmlFor="member_join_date">Member joining date (optional)</label>
            <input
              id="member_join_date"
              name="member_join_date"
              type="date"
            />
          </div>
          <div>
            <label htmlFor="hospital">Hospital (optional, network cashless)</label>
            <input id="hospital" name="hospital" placeholder="Apollo Hospitals" />
          </div>
        </div>
        <div className="checkbox-row" style={{ marginBottom: "1rem" }}>
          <label>
            <input name="cashless_request" type="checkbox" value="true" />
            Cashless request
          </label>
        </div>

        <label htmlFor="structured_documents">Structured documents (JSON)</label>
        <textarea
          id="structured_documents"
          rows={12}
          value={jsonText}
          onChange={(e) => setJsonText(e.target.value)}
          placeholder='{"prescription": {...}, "bill": {...}}'
        />

        <p className="section-label">Document uploads (optional — uses OCR)</p>
        <div className="grid2">
          <FileDropZone slot="prescription" label="Prescription" />
          <FileDropZone slot="bill" label="Bill / receipt" />
        </div>

        {error && <p className="error">{error}</p>}
        <button type="submit" className="primary" disabled={loading}>
          {loading ? "Submitting…" : "Submit claim"}
        </button>
      </form>
    </div>
  );
}
