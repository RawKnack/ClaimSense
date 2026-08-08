const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000/api/v1";

export type ClaimSubmitResponse = {
  claim_id: string;
  claim_number: string;
  status: string;
  message: string;
};

export type Decision = {
  decision: string;
  approved_amount?: number;
  rejection_reasons?: string[];
  notes?: string;
  confidence_score?: number;
  deductions?: Record<string, number>;
};

export type ClaimStatus = {
  claim_id: string;
  claim_number: string;
  status: string;
  member_id: string;
  member_name: string;
  treatment_date: string;
  claim_amount: number;
  decision?: Decision | null;
  error_message?: string | null;
};

export async function submitClaim(form: FormData): Promise<ClaimSubmitResponse> {
  const res = await fetch(`${API_BASE}/claims`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const detail = err.detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((d: { msg?: string }) => d.msg).join(", ")
          : res.statusText;
    throw new Error(message || "Submit failed");
  }
  return res.json();
}

export async function getClaim(claimId: string): Promise<ClaimStatus> {
  const res = await fetch(`${API_BASE}/claims/${claimId}`, {
    cache: "no-store",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? res.statusText);
  }
  return res.json();
}
