export type LeadCadenceStep = {
  position: number;
  delay_minutes: number;
  action_type: "call" | "whatsapp" | "email" | "follow_up" | "task";
  title: string;
  message_template: string | null;
};

export type LeadCadence = {
  public_id: string;
  name: string;
  description: string | null;
  active: boolean;
  stop_on_reply: boolean;
  steps: LeadCadenceStep[];
  active_enrollments: number;
  created_at: string;
  updated_at: string;
};

export type LeadCadenceEnrollment = {
  public_id: string;
  lead_public_id: string;
  lead_name: string;
  cadence_public_id: string;
  cadence_name: string;
  status: "active" | "completed" | "cancelled" | string;
  current_step: number;
  total_steps: number;
  next_run_at: string | null;
  started_at: string;
  completed_at: string | null;
  cancelled_at: string | null;
};

export type LeadCadenceProcessResult = {
  processed: number;
  activities_created: number;
  completed: number;
  cancelled: number;
};
