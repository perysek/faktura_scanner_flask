import { Link } from 'react-router-dom';
import './DashboardPage.css';
import { useApiData } from '../../lib/useApiData';
import { invoicesApi } from '../../lib/api/invoices';
import { dashboardApi } from '../../lib/api/dashboard';
import { Button } from '../../components/ui/Button';
import { formatCurrency, formatDate, formatPLN, parseLocalDate } from '../../lib/format';
import { MonthlyChart } from './MonthlyChart';
import type { DashboardInvoice, TopSeller } from '../../types/dashboard';

// Darker variants (not the --color-chart-* tokens — those are lighter, tuned
// for chart series, not text-on-chip contrast) so white initials meet WCAG AA
// (4.5:1) on every avatar chip — ported 1:1 from the original's own comment.
const SELLER_COLORS = ['#1d4ed8', '#047857', '#4338ca', '#b45309', '#475569'];

/**
 * Pulpit (Dashboard) — Faza 2, pierwszy moduł po pilocie Klientów.
 * Ported 1:1 from templates/dashboard/index.html: same 6 stat cards, same 5
 * panels (chart + 4 lists), same empty/error copy. `main.dashboard` has NO
 * module decorator on the backend (@login_required only, D14 pt. 5) — the
 * PAGE is reachable by any authenticated user, but every widget's API call
 * requires 'invoices' (the pre-existing pattern `get_statistics` already had,
 * now extended to the other 5 endpoints — see implementation-log.md, they
 * had NO auth decorator at all before this port). A user without 'invoices'
 * access sees the page shell with every panel in its error/empty state —
 * exactly what happens today, not a new regression introduced by React.
 */
export function DashboardPage() {
  const statsState = useApiData(() => invoicesApi.statistics(), []);
  const recentState = useApiData(() => dashboardApi.recentInvoices(5), []);
  const overdueState = useApiData(() => dashboardApi.overduePayments(5), []);
  const upcomingState = useApiData(() => dashboardApi.upcomingPayments(5), []);
  const topSellersState = useApiData(() => dashboardApi.topSellers(5), []);
  const monthlyState = useApiData(() => dashboardApi.monthlyTotals(), []);

  const isRefreshing = statsState.loading || recentState.loading || overdueState.loading || upcomingState.loading || topSellersState.loading || monthlyState.loading;

  function refreshAll() {
    statsState.reload();
    recentState.reload();
    overdueState.reload();
    upcomingState.reload();
    topSellersState.reload();
    monthlyState.reload();
  }

  const stats = statsState.data;
  const totalGross = stats?.totals?.total_amount ?? 0;
  const totalNet = totalGross / 1.23;
  const totalVat = totalGross * (23 / 123);

  const overdueTotal = (overdueState.data ?? []).reduce((sum, inv) => sum + (inv.amount ?? 0), 0);
  const upcomingTotal = (upcomingState.data ?? []).reduce((sum, inv) => sum + (inv.amount ?? 0), 0);

  return (
    <div className="refined-page dashboard-page animate-fade-up">
      <header className="page-header">
        <h1 className="page-title">Pulpit</h1>
        <div className="header-actions">
          <Button variant="ghost" small icon="refresh" isLoading={isRefreshing} loadingText="Ładowanie…" onClick={refreshAll}>
            Odśwież
          </Button>
        </div>
      </header>

      <div className="dash-stats-grid">
        <div className="dash-stat-card dash-stat-card--hero">
          <span className="dash-stat-value">{stats ? formatPLN(totalGross) : '—'}</span>
          <span className="dash-stat-label">Brutto</span>
        </div>
        <div className="dash-stat-card">
          <span className="dash-stat-value">{stats?.total_invoices ?? '—'}</span>
          <span className="dash-stat-label">Wszystkie</span>
        </div>
        <div className="dash-stat-card">
          <span className="dash-stat-value">{stats?.paid_invoices ?? '—'}</span>
          <span className="dash-stat-label">Opłacone</span>
        </div>
        <div className="dash-stat-card">
          <span className="dash-stat-value">{stats?.unpaid_invoices ?? '—'}</span>
          <span className="dash-stat-label">Nieopłacone</span>
        </div>
        <div className="dash-stat-card dash-stat-card--amount">
          <span className="dash-stat-value">{stats ? formatPLN(totalNet) : '—'}</span>
          <span className="dash-stat-label">Netto</span>
        </div>
        <div className="dash-stat-card dash-stat-card--amount">
          <span className="dash-stat-value">{stats ? formatPLN(totalVat) : '—'}</span>
          <span className="dash-stat-label">VAT</span>
        </div>
      </div>

      <div className="dash-panels-grid">
        <div className="dash-panel dash-chart-panel">
          <div className="dash-panel-header">
            <div className="dash-panel-title">
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
              Kwoty faktur - ostatnie 12 miesięcy
            </div>
          </div>
          <div className="dash-chart-container">
            {monthlyState.data && <MonthlyChart labels={monthlyState.data.labels} data={monthlyState.data.data} months={monthlyState.data.months} />}
          </div>
        </div>

        <div className="dash-panel">
          <div className="dash-panel-header">
            <div className="dash-panel-title">
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              Ostatnie faktury
            </div>
            <Link to="/faktury" className="dash-panel-link">
              Zobacz wszystkie →
            </Link>
          </div>
          <div className="dash-panel-content">
            <RecentInvoicesList state={recentState} />
          </div>
        </div>

        <div className="dash-panel">
          <div className="dash-panel-header">
            <div className="dash-panel-title">
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                />
              </svg>
              Przeterminowane
            </div>
            <span className="dash-panel-link" style={{ fontWeight: 600 }}>
              {overdueState.data ? formatPLN(overdueTotal) : '—'}
            </span>
          </div>
          <div className="dash-panel-content" tabIndex={0} role="region" aria-label="Przeterminowane płatności">
            <OverdueList state={overdueState} />
          </div>
        </div>

        <div className="dash-panel">
          <div className="dash-panel-header">
            <div className="dash-panel-title">
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
              Nadchodzące płatności
            </div>
            <span className="dash-panel-link" style={{ fontWeight: 600 }}>
              {upcomingState.data ? formatPLN(upcomingTotal) : '—'}
            </span>
          </div>
          <div className="dash-panel-content" tabIndex={0} role="region" aria-label="Nadchodzące płatności">
            <UpcomingList state={upcomingState} />
          </div>
        </div>

        <div className="dash-panel">
          <div className="dash-panel-header">
            <div className="dash-panel-title">
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
              </svg>
              Najczęstsi dostawcy
            </div>
          </div>
          <div className="dash-panel-content" tabIndex={0} role="region" aria-label="Najczęstsi dostawcy">
            <TopSellersList sellers={topSellersState.data} loading={topSellersState.loading} error={topSellersState.error} />
          </div>
        </div>
      </div>
    </div>
  );
}

interface ListState {
  data: DashboardInvoice[] | null;
  loading: boolean;
  error: Error | null;
}

function EmptyPanel({ title, text }: { title: string; text?: string }) {
  return (
    <div className="dash-empty-panel">
      <div className="dash-empty-title">{title}</div>
      {text && <div className="dash-empty-text">{text}</div>}
    </div>
  );
}

function RecentInvoicesList({ state }: { state: ListState }) {
  if (state.loading) return <div className="dash-empty-panel">Ładowanie...</div>;
  if (state.error) return <EmptyPanel title="Błąd ładowania" />;
  if (!state.data || state.data.length === 0) return <EmptyPanel title="Brak faktur" />;
  return (
    <>
      {state.data.map((invoice) => (
        <a key={invoice.id} href={`/invoice/${invoice.id}/edit`} className="dash-list-item">
          <div className="dash-list-item-main">
            <div className="dash-list-item-title">{invoice.seller_name || 'Nieznany'}</div>
            <div className="dash-list-item-subtitle">{invoice.invoice_number || '—'}</div>
          </div>
          <div className="dash-list-item-side">
            <div className="dash-list-item-amount">{formatCurrency(invoice.amount ?? 0, invoice.currency || 'PLN')}</div>
            <div className="dash-list-item-meta">
              <span className={`status-badge ${invoice.status === 'Opłacona' ? 'status-paid' : 'status-unpaid'}`}>{invoice.status || 'Nieopłacona'}</span>
            </div>
          </div>
        </a>
      ))}
    </>
  );
}

function OverdueList({ state }: { state: ListState }) {
  if (state.loading) return <div className="dash-empty-panel">Ładowanie...</div>;
  if (state.error) return <EmptyPanel title="Błąd ładowania" />;
  if (!state.data || state.data.length === 0) return <EmptyPanel title="Brak zaległości" text="Wszystko opłacone na czas!" />;
  return (
    <>
      {state.data.map((invoice) => {
        const dueDate = invoice.payment_due_date ? parseLocalDate(invoice.payment_due_date) : null;
        const daysOverdue = dueDate ? Math.ceil((Date.now() - dueDate.getTime()) / (1000 * 60 * 60 * 24)) : 0;
        return (
          <a key={invoice.id} href={`/invoice/${invoice.id}/edit`} className="dash-list-item">
            <div className="dash-list-item-main">
              <div className="dash-list-item-title">{invoice.seller_name || 'Nieznany'}</div>
              <div className="dash-list-item-subtitle dash-urgency-high">{daysOverdue} dni po terminie</div>
            </div>
            <div className="dash-list-item-side">
              <div className="dash-list-item-amount dash-urgency-high">{formatCurrency(invoice.amount ?? 0, invoice.currency || 'PLN')}</div>
              <div className="dash-list-item-meta">{formatDate(invoice.payment_due_date)}</div>
            </div>
          </a>
        );
      })}
    </>
  );
}

function UpcomingList({ state }: { state: ListState }) {
  if (state.loading) return <div className="dash-empty-panel">Ładowanie...</div>;
  if (state.error) return <EmptyPanel title="Błąd ładowania" />;
  if (!state.data || state.data.length === 0) return <EmptyPanel title="Brak nadchodzących płatności" />;
  return (
    <>
      {state.data.map((invoice) => {
        const dueDate = invoice.payment_due_date ? parseLocalDate(invoice.payment_due_date) : null;
        const daysUntil = dueDate ? Math.ceil((dueDate.getTime() - Date.now()) / (1000 * 60 * 60 * 24)) : null;
        let urgencyClass = 'dash-urgency-low';
        if (daysUntil !== null) {
          if (daysUntil <= 3) urgencyClass = 'dash-urgency-high';
          else if (daysUntil <= 7) urgencyClass = 'dash-urgency-medium';
        }
        const daysText = daysUntil === 0 ? 'Dziś' : daysUntil === 1 ? 'Jutro' : `Za ${daysUntil} dni`;
        return (
          <a key={invoice.id} href={`/invoice/${invoice.id}/edit`} className="dash-list-item">
            <div className="dash-list-item-main">
              <div className="dash-list-item-title">{invoice.seller_name || 'Nieznany'}</div>
              <div className="dash-list-item-subtitle">{invoice.invoice_number || '—'}</div>
            </div>
            <div className="dash-list-item-side">
              <div className="dash-list-item-amount">{formatCurrency(invoice.amount ?? 0, invoice.currency || 'PLN')}</div>
              <div className={`dash-list-item-meta ${urgencyClass}`}>{daysText}</div>
            </div>
          </a>
        );
      })}
    </>
  );
}

function TopSellersList({ sellers, loading, error }: { sellers: TopSeller[] | null; loading: boolean; error: Error | null }) {
  if (loading) return <div className="dash-empty-panel">Ładowanie...</div>;
  if (error) return <EmptyPanel title="Błąd ładowania" />;
  if (!sellers || sellers.length === 0) return <EmptyPanel title="Brak danych o dostawcach" />;
  return (
    <>
      {sellers.map((seller, index) => {
        const bgColor = SELLER_COLORS[index] ?? SELLER_COLORS[4];
        const initials = (seller.seller_name || '??').substring(0, 2).toUpperCase();
        return (
          <div key={seller.id} className="dash-list-item">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flex: 1, minWidth: 0 }}>
              <span className="dash-seller-initial" style={{ background: bgColor }}>
                {initials}
              </span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="dash-list-item-title">{seller.seller_name || 'Nieznany'}</div>
                <div className="dash-list-item-subtitle">NIP: {seller.seller_nip || '—'}</div>
              </div>
            </div>
            <div className="dash-list-item-side">
              <div className="dash-list-item-amount">{seller.invoice_count || 0} faktur</div>
              <div className="dash-list-item-meta">{formatPLN(seller.total_amount || 0)}</div>
            </div>
          </div>
        );
      })}
    </>
  );
}
