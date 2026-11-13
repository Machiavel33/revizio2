import { useCallback, useEffect, useState } from "react";
import { Download, FileText, Send, CheckCircle, CreditCard, RefreshCw } from "lucide-react";
import { api } from "../../lib/api";
import type { BillingReport, Invoice } from "../../lib/types";

const STATUS_STYLE: Record<string, string> = {
  draft: "bg-[color:var(--bg-elevated)] text-[color:var(--text-muted)]",
  sent: "bg-[color:var(--accent-primary)]/15 text-[color:var(--accent-primary)]",
  paid: "bg-[color:var(--accent-success)]/15 text-[color:var(--accent-success)]",
  overdue: "bg-[color:var(--accent-danger)]/15 text-[color:var(--accent-danger)]",
  cancelled: "bg-[color:var(--bg-elevated)] text-[color:var(--text-muted)]",
};

const STATUS_LABEL: Record<string, string> = {
  draft: "Brouillon",
  sent: "Émise",
  paid: "Payée",
  overdue: "En retard",
  cancelled: "Annulée",
};

function currentPeriod(): { year: number; month: number } {
  const now = new Date();
  return { year: now.getFullYear(), month: now.getMonth() + 1 };
}

export default function BillingTab() {
  const [{ year, month }, setPeriod] = useState(currentPeriod());
  const [report, setReport] = useState<BillingReport | null>(null);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [r, inv] = await Promise.all([
        api.adminBilling(year, month),
        api.adminInvoices(undefined, `${year}-${String(month).padStart(2, "0")}`),
      ]);
      setReport(r);
      setInvoices(inv);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [year, month]);

  useEffect(() => {
    void load();
  }, [load]);

  async function generate(userId: string) {
    setBusy(userId);
    try {
      await api.adminGenerateInvoice(userId, year, month);
      await load();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(null);
    }
  }

  async function issue(id: string) {
    setBusy(id);
    try {
      await api.adminIssueInvoice(id);
      await load();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(null);
    }
  }

  async function markPaid(id: string) {
    setBusy(id);
    try {
      await api.adminMarkInvoicePaid(id);
      await load();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(null);
    }
  }

  async function checkout(id: string) {
    setBusy(id);
    try {
      const { checkout_url } = await api.adminInvoiceCheckout(id);
      window.open(checkout_url, "_blank", "noopener");
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(null);
    }
  }

  function downloadPdf(id: string) {
    window.open(api.adminInvoicePdfUrl(id), "_blank", "noopener");
  }

  function downloadCsv() {
    window.open(api.adminBillingCsvUrl(year, month), "_blank", "noopener");
  }

  const periodLabel = `${String(month).padStart(2, "0")}/${year}`;

  return (
    <div className="space-y-6">
      {/* Sélecteur de période + actions */}
      <div className="flex flex-wrap items-center gap-3">
        <label className="text-sm text-[color:var(--text-secondary)]">Période</label>
        <input
          type="month"
          className="input w-auto"
          value={`${year}-${String(month).padStart(2, "0")}`}
          onChange={(e) => {
            const [y, m] = e.target.value.split("-").map(Number);
            if (y && m) setPeriod({ year: y, month: m });
          }}
        />
        <button onClick={() => void load()} className="btn-secondary" disabled={loading}>
          <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
          Actualiser
        </button>
        <button onClick={downloadCsv} className="btn-secondary">
          <Download size={16} />
          Export CSV
        </button>
      </div>

      {error && (
        <div className="rounded-md border border-[color:var(--accent-danger)]/40 bg-[color:var(--accent-danger)]/10 p-3 text-sm text-[color:var(--accent-danger)]">
          {error}
        </div>
      )}

      {/* Rapport de facturation */}
      {report && (
        <div className="card">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="font-display text-lg font-semibold">
              Rapport de facturation — {periodLabel}
            </h3>
            <div className="text-right text-sm">
              <p className="text-[color:var(--text-muted)]">
                Coût réel : ${report.total_cost_usd.toFixed(4)}
              </p>
              <p className="font-semibold text-[color:var(--accent-primary)]">
                Facturé : {report.total_billed.toFixed(2)} {report.currency}
              </p>
            </div>
          </div>
          {report.users.length === 0 ? (
            <p className="text-sm text-[color:var(--text-muted)]">
              Aucun usage de la clé plateforme sur cette période.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[color:var(--border-subtle)] text-left text-xs uppercase tracking-wider text-[color:var(--text-muted)]">
                    <th className="px-3 py-2">Utilisateur</th>
                    <th className="px-3 py-2">Appels</th>
                    <th className="px-3 py-2">Coût réel</th>
                    <th className="px-3 py-2">Facturé</th>
                    <th className="px-3 py-2">Marge</th>
                    <th className="px-3 py-2">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {report.users.map((u) => (
                    <tr key={u.user_id} className="border-b border-[color:var(--border-subtle)]/50">
                      <td className="px-3 py-2 font-mono text-xs">{u.email}</td>
                      <td className="px-3 py-2">{u.calls}</td>
                      <td className="px-3 py-2 font-mono text-xs">${u.cost_usd.toFixed(4)}</td>
                      <td className="px-3 py-2 font-mono text-xs">
                        {u.total.toFixed(2)} {u.currency}
                        {u.capped && (
                          <span className="ml-1 rounded bg-[color:var(--accent-warning)]/15 px-1 text-[10px] text-[color:var(--accent-warning)]">
                            plafonné
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-2">
                        {u.margin_covered ? (
                          <span className="text-[color:var(--accent-success)]">OK</span>
                        ) : (
                          <span className="text-[color:var(--accent-danger)]">négative</span>
                        )}
                      </td>
                      <td className="px-3 py-2">
                        <button
                          onClick={() => void generate(u.user_id)}
                          disabled={busy === u.user_id}
                          className="btn-secondary text-xs"
                        >
                          <FileText size={14} />
                          Générer facture
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Liste des factures */}
      <div className="card">
        <h3 className="mb-4 font-display text-lg font-semibold">
          Factures — {periodLabel} ({invoices.length})
        </h3>
        {invoices.length === 0 ? (
          <p className="text-sm text-[color:var(--text-muted)]">
            Aucune facture pour cette période. Générez-en depuis le rapport ci-dessus.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[color:var(--border-subtle)] text-left text-xs uppercase tracking-wider text-[color:var(--text-muted)]">
                  <th className="px-3 py-2">Numéro</th>
                  <th className="px-3 py-2">Total</th>
                  <th className="px-3 py-2">Statut</th>
                  <th className="px-3 py-2">Actions</th>
                </tr>
              </thead>
              <tbody>
                {invoices.map((inv) => (
                  <tr key={inv.id} className="border-b border-[color:var(--border-subtle)]/50">
                    <td className="px-3 py-2 font-mono text-xs">{inv.number}</td>
                    <td className="px-3 py-2 font-mono text-xs">
                      {inv.total.toFixed(2)} {inv.currency}
                    </td>
                    <td className="px-3 py-2">
                      <span
                        className={`rounded px-2 py-0.5 text-xs font-semibold ${STATUS_STYLE[inv.status] ?? ""}`}
                      >
                        {STATUS_LABEL[inv.status] ?? inv.status}
                      </span>
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex flex-wrap gap-1">
                        {inv.status === "draft" && (
                          <button
                            onClick={() => void issue(inv.id)}
                            disabled={busy === inv.id}
                            className="btn-secondary text-xs"
                          >
                            <Send size={14} />
                            Émettre
                          </button>
                        )}
                        {(inv.status === "sent" || inv.status === "overdue") && (
                          <>
                            <button
                              onClick={() => void markPaid(inv.id)}
                              disabled={busy === inv.id}
                              className="btn-secondary text-xs"
                            >
                              <CheckCircle size={14} />
                              Payée
                            </button>
                            <button
                              onClick={() => void checkout(inv.id)}
                              disabled={busy === inv.id}
                              className="btn-secondary text-xs"
                            >
                              <CreditCard size={14} />
                              Payer en ligne
                            </button>
                          </>
                        )}
                        <button
                          onClick={() => downloadPdf(inv.id)}
                          className="btn-secondary text-xs"
                        >
                          <Download size={14} />
                          PDF
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
