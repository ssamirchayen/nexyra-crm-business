import {
  AlertTriangle,
  CheckCircle2,
  Download,
  FileSpreadsheet,
  RefreshCw,
  UploadCloud,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { api } from "../../lib/api";
import type {
  CsvImportOptions,
  CsvImportPreview,
  CsvImportRequest,
  CsvImportResult,
  LeadImportJob,
} from "../../types/imports";
import type { WorkspaceSegmentConfig } from "../../types/leads";
import { Button } from "../ui/Button";
import { Modal } from "../ui/Modal";

type CsvImportModalProps = {
  open: boolean;
  workspacePublicId: string;
  segmentConfig: WorkspaceSegmentConfig | null;
  onClose: () => void;
  onImported: (result: CsvImportResult) => void;
};

const MAPPING_FIELDS = [
  ["name", "Nome *"],
  ["phone", "Telefone"],
  ["email", "E-mail"],
  ["external_id", "ID externo"],
  ["interest", "Interesse"],
  ["campaign", "Campanha"],
  ["message", "Mensagem"],
  ["status", "Status"],
  ["priority", "Prioridade"],
  ["consent", "Consentimento"],
] as const;

function formatDate(value: string) {
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}

export function CsvImportModal({
  open,
  workspacePublicId,
  segmentConfig,
  onClose,
  onImported,
}: CsvImportModalProps) {
  const [options, setOptions] = useState<CsvImportOptions | null>(null);
  const [jobs, setJobs] = useState<LeadImportJob[]>([]);
  const [filename, setFilename] = useState("");
  const [csvText, setCsvText] = useState("");
  const [delimiter, setDelimiter] = useState<CsvImportRequest["delimiter"]>("auto");
  const [sourceId, setSourceId] = useState("");
  const [duplicateMode, setDuplicateMode] =
    useState<CsvImportRequest["duplicate_mode"]>("update");
  const [campaign, setCampaign] = useState("");
  const [defaultStatus, setDefaultStatus] = useState("");
  const [defaultPriority, setDefaultPriority] = useState("media");
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [preview, setPreview] = useState<CsvImportPreview | null>(null);
  const [result, setResult] = useState<CsvImportResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedSource = useMemo(
    () => options?.sources.find((item) => item.public_id === sourceId) ?? null,
    [options, sourceId],
  );

  useEffect(() => {
    if (!open) return;
    setError(null);
    void Promise.all([
      api.get<CsvImportOptions>(
        `/workspaces/${workspacePublicId}/lead-imports/options`,
      ),
      api.get<LeadImportJob[]>(`/workspaces/${workspacePublicId}/lead-imports`),
    ])
      .then(([nextOptions, nextJobs]) => {
        setOptions(nextOptions);
        setJobs(nextJobs.slice(0, 5));
      })
      .catch((requestError) => {
        setError(
          requestError instanceof Error
            ? requestError.message
            : "Não foi possível carregar as opções de importação.",
        );
      });
  }, [open, workspacePublicId]);

  function resetFile() {
    setFilename("");
    setCsvText("");
    setMapping({});
    setPreview(null);
    setResult(null);
    setError(null);
  }

  function downloadTemplate() {
    const content = [
      "nome,telefone,email,interesse,campanha",
      "Lead Exemplo,92999999999,lead@example.com,Produto A,Campanha Setembro",
    ].join("\n");
    const blob = new Blob([content], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "nexyra_modelo_leads.csv";
    anchor.click();
    URL.revokeObjectURL(url);
  }

  async function handleFile(file: File | null) {
    if (!file) return;
    setError(null);
    setResult(null);
    setPreview(null);
    setMapping({});

    if (!file.name.toLowerCase().endsWith(".csv")) {
      setError("Selecione um arquivo com extensão .csv.");
      return;
    }

    const text = await file.text();
    if (options && text.length > options.max_file_chars) {
      setError("O arquivo ultrapassa o limite permitido para uma importação.");
      return;
    }
    setFilename(file.name);
    setCsvText(text);
  }

  function buildRequest(): CsvImportRequest {
    return {
      filename,
      csv_text: csvText,
      delimiter,
      integration_public_id: sourceId || null,
      duplicate_mode: duplicateMode,
      source: selectedSource?.source ?? "csv",
      channel: selectedSource?.channel ?? "import",
      campaign: campaign.trim() || null,
      default_status: defaultStatus || null,
      default_priority: defaultPriority,
      consent_default: true,
      field_mapping: mapping,
    };
  }

  async function analyze() {
    if (!filename || !csvText) {
      setError("Selecione um arquivo CSV antes de analisar.");
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const nextPreview = await api.post<CsvImportPreview>(
        `/workspaces/${workspacePublicId}/lead-imports/preview`,
        buildRequest(),
      );
      setPreview(nextPreview);
      setMapping(nextPreview.field_mapping);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível analisar o CSV.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function executeImport() {
    if (!preview) return;
    setLoading(true);
    setError(null);
    try {
      const importResult = await api.post<CsvImportResult>(
        `/workspaces/${workspacePublicId}/lead-imports/execute`,
        buildRequest(),
      );
      setResult(importResult);
      setJobs((current) => [importResult.job, ...current].slice(0, 5));
      onImported(importResult);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível executar a importação.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <Modal
      open={open}
      title="Importar leads por CSV"
      description="Analise, mapeie e importe listas em lote com deduplicação automática."
      onClose={() => !loading && onClose()}
      size="lg"
      footer={
        <>
          <Button variant="secondary" disabled={loading} onClick={onClose}>
            Fechar
          </Button>
          {preview && !result ? (
            <Button
              disabled={loading || preview.valid_rows === 0}
              onClick={() => void executeImport()}
            >
              {loading ? "Importando..." : `Importar ${preview.valid_rows} linha(s)`}
            </Button>
          ) : (
            <Button disabled={loading || !csvText} onClick={() => void analyze()}>
              {loading ? "Analisando..." : preview ? "Atualizar prévia" : "Analisar CSV"}
            </Button>
          )}
        </>
      }
    >
      <div className="csv-import-stack">
        {error && <div className="page-alert page-alert--error">{error}</div>}

        <div className="csv-import-grid csv-import-grid--setup">
          <label className="form-field csv-file-field">
            <span className="csv-file-label">
              <span>Arquivo CSV</span>
              <button
                type="button"
                onClick={(event) => {
                  event.preventDefault();
                  event.stopPropagation();
                  downloadTemplate();
                }}
              >
                <Download size={14} />
                Baixar modelo
              </button>
            </span>
            <div className="csv-file-picker">
              <UploadCloud size={20} />
              <div>
                <strong>{filename || "Selecionar arquivo .csv"}</strong>
                <span>
                  Até {options?.max_rows ?? 5000} linhas por importação
                </span>
              </div>
              <input
                key={filename || "empty"}
                type="file"
                accept=".csv,text/csv"
                disabled={loading}
                onChange={(event) => void handleFile(event.target.files?.[0] ?? null)}
              />
            </div>
          </label>

          <label className="form-field">
            <span>Fonte configurada</span>
            <select value={sourceId} onChange={(event) => setSourceId(event.target.value)}>
              <option value="">Padrão CSV / import</option>
              {options?.sources.map((source) => (
                <option key={source.public_id} value={source.public_id}>
                  {source.name} · {source.source}/{source.channel}
                </option>
              ))}
            </select>
          </label>

          <label className="form-field">
            <span>Separador</span>
            <select
              value={delimiter}
              onChange={(event) =>
                setDelimiter(event.target.value as CsvImportRequest["delimiter"])
              }
            >
              <option value="auto">Detectar automaticamente</option>
              <option value=",">Vírgula (,)</option>
              <option value=";">Ponto e vírgula (;)</option>
              <option value="\\t">Tabulação</option>
              <option value="|">Barra vertical (|)</option>
            </select>
          </label>

          <label className="form-field">
            <span>Duplicados</span>
            <select
              value={duplicateMode}
              onChange={(event) =>
                setDuplicateMode(event.target.value as CsvImportRequest["duplicate_mode"])
              }
            >
              <option value="update">Atualizar lead existente</option>
              <option value="skip">Ignorar lead existente</option>
            </select>
          </label>

          <label className="form-field">
            <span>Campanha padrão</span>
            <input
              value={campaign}
              placeholder={selectedSource?.default_campaign ?? "Opcional"}
              onChange={(event) => setCampaign(event.target.value)}
            />
          </label>

          <label className="form-field">
            <span>Status padrão</span>
            <select value={defaultStatus} onChange={(event) => setDefaultStatus(event.target.value)}>
              <option value="">Primeira etapa do pipeline</option>
              {segmentConfig?.pipeline.map((stage) => (
                <option key={stage} value={stage}>
                  {stage.replaceAll("_", " ")}
                </option>
              ))}
            </select>
          </label>

          <label className="form-field">
            <span>Prioridade padrão</span>
            <select value={defaultPriority} onChange={(event) => setDefaultPriority(event.target.value)}>
              <option value="baixa">Baixa</option>
              <option value="media">Média</option>
              <option value="alta">Alta</option>
              <option value="urgente">Urgente</option>
            </select>
          </label>
        </div>

        {preview && (
          <>
            <div className="csv-preview-summary">
              <div>
                <FileSpreadsheet size={18} />
                <span>Total</span>
                <strong>{preview.total_rows}</strong>
              </div>
              <div className="csv-preview-summary__ok">
                <CheckCircle2 size={18} />
                <span>Válidas</span>
                <strong>{preview.valid_rows}</strong>
              </div>
              <div className={preview.invalid_rows ? "csv-preview-summary__warning" : ""}>
                <AlertTriangle size={18} />
                <span>Com erro</span>
                <strong>{preview.invalid_rows}</strong>
              </div>
              <div>
                <span>Separador detectado</span>
                <strong>{preview.delimiter === "\\t" ? "Tab" : preview.delimiter}</strong>
              </div>
            </div>

            <section className="csv-mapping-section">
              <div className="csv-section-title">
                <div>
                  <strong>Mapeamento de colunas</strong>
                  <span>Confira onde cada coluna será salva no CRM.</span>
                </div>
                <Button variant="ghost" disabled={loading} onClick={() => void analyze()}>
                  <RefreshCw size={15} />
                  Revalidar
                </Button>
              </div>
              <div className="csv-mapping-grid">
                {MAPPING_FIELDS.map(([field, label]) => (
                  <label className="form-field" key={field}>
                    <span>{label}</span>
                    <select
                      value={mapping[field] ?? ""}
                      onChange={(event) => {
                        const header = event.target.value;
                        setMapping((current) => {
                          const next = { ...current };
                          if (header) next[field] = header;
                          else delete next[field];
                          return next;
                        });
                        setResult(null);
                      }}
                    >
                      <option value="">Não importar</option>
                      {preview.headers.map((header) => (
                        <option key={header} value={header}>
                          {header}
                        </option>
                      ))}
                    </select>
                  </label>
                ))}
              </div>
            </section>

            <section className="csv-sample-section">
              <div className="csv-section-title">
                <div>
                  <strong>Prévia</strong>
                  <span>Primeiras linhas analisadas pelo backend.</span>
                </div>
              </div>
              <div className="csv-sample-list">
                {preview.sample_rows.map((row) => (
                  <div
                    className={`csv-sample-row ${row.valid ? "" : "csv-sample-row--error"}`}
                    key={row.row_number}
                  >
                    <span>Linha {row.row_number}</span>
                    <strong>{String(row.values.name ?? "Sem nome")}</strong>
                    <small>
                      {row.valid
                        ? String(row.values.email ?? row.values.phone ?? "Pronta para importar")
                        : row.errors.join(" · ")}
                    </small>
                  </div>
                ))}
              </div>
              {preview.warnings.map((warning) => (
                <div className="csv-warning" key={warning}>
                  <AlertTriangle size={15} />
                  <span>{warning}</span>
                </div>
              ))}
            </section>
          </>
        )}

        {result && (
          <section className="csv-result-card">
            <CheckCircle2 size={28} />
            <div>
              <strong>Importação concluída</strong>
              <span>
                {result.created} criado(s), {result.duplicate_updated} atualizado(s), {result.duplicate_skipped} ignorado(s) e {result.failed} com erro.
              </span>
              <small>ID: {result.job.public_id}</small>
            </div>
            <Button variant="secondary" onClick={resetFile}>
              Nova importação
            </Button>
          </section>
        )}

        {jobs.length > 0 && (
          <section className="csv-history-section">
            <div className="csv-section-title">
              <div>
                <strong>Importações recentes</strong>
                <span>Últimos processamentos deste workspace.</span>
              </div>
            </div>
            <div className="csv-history-list">
              {jobs.map((job) => (
                <div key={job.public_id}>
                  <FileSpreadsheet size={16} />
                  <div>
                    <strong>{job.filename}</strong>
                    <span>{formatDate(job.created_at)}</span>
                  </div>
                  <small>
                    {job.created_count} novos · {job.updated_count} atualizados · {job.failed_count} erros
                  </small>
                </div>
              ))}
            </div>
          </section>
        )}
      </div>
    </Modal>
  );
}
