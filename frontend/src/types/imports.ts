export type CsvImportSourceOption = {
  public_id: string;
  name: string;
  source: string;
  channel: string;
  default_campaign: string | null;
};

export type CsvImportOptions = {
  sources: CsvImportSourceOption[];
  max_rows: number;
  max_file_chars: number;
  supported_fields: string[];
};

export type CsvImportPreviewRow = {
  row_number: number;
  valid: boolean;
  values: Record<string, unknown>;
  errors: string[];
};

export type CsvImportPreview = {
  filename: string;
  delimiter: string;
  headers: string[];
  field_mapping: Record<string, string>;
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  sample_rows: CsvImportPreviewRow[];
  warnings: string[];
};

export type LeadImportJob = {
  public_id: string;
  filename: string;
  delimiter: string;
  duplicate_mode: string;
  source: string;
  channel: string;
  campaign: string | null;
  status: string;
  total_rows: number;
  created_count: number;
  updated_count: number;
  skipped_count: number;
  failed_count: number;
  field_mapping: Record<string, unknown>;
  error_samples: Array<Record<string, unknown>>;
  created_at: string;
  completed_at: string | null;
};

export type CsvImportResult = {
  job: LeadImportJob;
  created: number;
  duplicate_updated: number;
  duplicate_skipped: number;
  failed: number;
  error_samples: Array<Record<string, unknown>>;
};

export type CsvImportRequest = {
  filename: string;
  csv_text: string;
  delimiter: "auto" | "," | ";" | "\\t" | "|";
  integration_public_id: string | null;
  duplicate_mode: "update" | "skip";
  source: string;
  channel: string;
  campaign: string | null;
  default_status: string | null;
  default_priority: string;
  consent_default: boolean;
  field_mapping: Record<string, string>;
};
