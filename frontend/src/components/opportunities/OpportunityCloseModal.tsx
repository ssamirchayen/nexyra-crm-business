import { useEffect, useState } from "react";

import type { OpportunityCard } from "../../types/opportunities";
import { Button } from "../ui/Button";
import { Modal } from "../ui/Modal";

type OpportunityCloseModalProps = {
  open: boolean;
  mode: "won" | "lost";
  opportunity: OpportunityCard | null;
  saving: boolean;
  error: string | null;
  onClose: () => void;
  onConfirm: (reason: string | null) => Promise<void>;
};

export function OpportunityCloseModal({
  open,
  mode,
  opportunity,
  saving,
  error,
  onClose,
  onConfirm,
}: OpportunityCloseModalProps) {
  const [reason, setReason] = useState("");

  useEffect(() => {
    if (open) {
      setReason("");
    }
  }, [open]);

  return (
    <Modal
      open={open}
      title={
        mode === "won"
          ? "Marcar oportunidade como ganha"
          : "Marcar oportunidade como perdida"
      }
      description={opportunity?.title}
      onClose={onClose}
      size="sm"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancelar
          </Button>
          <Button
            variant={mode === "lost" ? "danger" : "primary"}
            disabled={saving || (mode === "lost" && reason.trim().length < 2)}
            onClick={() => void onConfirm(mode === "lost" ? reason.trim() : null)}
          >
            {saving
              ? "Salvando..."
              : mode === "won"
                ? "Confirmar ganho"
                : "Confirmar perda"}
          </Button>
        </>
      }
    >
      <div className="confirmation-copy">
        {error && <div className="form-alert form-alert--error">{error}</div>}
        {mode === "won" ? (
          <>
            <strong>Essa negociação foi concluída com sucesso?</strong>
            <p>
              Ela deixará o pipeline aberto e passará a contar como oportunidade
              ganha nos indicadores de conversão.
            </p>
          </>
        ) : (
          <label className="field">
            <span>Motivo da perda *</span>
            <textarea
              rows={4}
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              placeholder="Ex.: preço, concorrência, sem retorno, desistência..."
            />
          </label>
        )}
      </div>
    </Modal>
  );
}
