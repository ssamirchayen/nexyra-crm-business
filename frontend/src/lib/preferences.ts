export const REPORT_PERIOD_OPTIONS = [7, 30, 90, 180, 365] as const;

export type ReportPeriod = (typeof REPORT_PERIOD_OPTIONS)[number];

function reportPeriodKey(workspacePublicId: string) {
  return `nexyra-report-period:${workspacePublicId}`;
}

export function getReportPeriodPreference(
  workspacePublicId: string,
): ReportPeriod {
  const raw = Number(localStorage.getItem(reportPeriodKey(workspacePublicId)));

  return REPORT_PERIOD_OPTIONS.includes(raw as ReportPeriod)
    ? (raw as ReportPeriod)
    : 30;
}

export function setReportPeriodPreference(
  workspacePublicId: string,
  value: ReportPeriod,
) {
  localStorage.setItem(reportPeriodKey(workspacePublicId), String(value));
}
