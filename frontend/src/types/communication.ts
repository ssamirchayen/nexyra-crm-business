export type CommunicationChannel = "whatsapp" | "email" | "sms" | "phone";
export type ConsentStatus = "granted" | "denied" | "revoked" | "unknown";
export type LawfulBasis =
  | "consent"
  | "contract"
  | "legitimate_interest"
  | "customer_request"
  | "other";

export type CommunicationPolicy = {
  enforce_whatsapp_opt_in: boolean;
  enforce_email_opt_in: boolean;
  enforce_sms_opt_in: boolean;
  enforce_phone_opt_in: boolean;
  allow_legacy_lead_consent: boolean;
  stop_cadence_on_block: boolean;
  updated_at: string | null;
};

export type LeadConsent = {
  public_id: string | null;
  channel: CommunicationChannel;
  status: ConsentStatus;
  lawful_basis: LawfulBasis | null;
  source: string | null;
  evidence: string | null;
  note: string | null;
  granted_at: string | null;
  revoked_at: string | null;
  updated_at: string | null;
  explicit: boolean;
  allowed: boolean;
  effective_reason: string;
};

export type LeadCommunicationSummary = {
  lead_public_id: string;
  legacy_consent: boolean;
  global_opt_out: boolean;
  items: LeadConsent[];
};

export type LeadConsentPayload = {
  channel: CommunicationChannel | "all";
  status: ConsentStatus;
  lawful_basis?: LawfulBasis | null;
  source?: string | null;
  evidence?: string | null;
  note?: string | null;
};
