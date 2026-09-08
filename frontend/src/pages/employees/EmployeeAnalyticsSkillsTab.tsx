import { useApiData } from '../../lib/useApiData';
import { employeeServicesApi } from '../../lib/api/employeeServices';
import { ApiError } from '../../lib/api/client';
import { useToast } from '../../components/feedback/ToastProvider';
import { CHART_BASE_OPTIONS, CHART_COLORS, useChartCanvas } from '../../lib/useChartCanvas';
import type { EmployeeServiceRating } from '../../types/employeeAnalytics';

/** "Umiejętności" tab — ported from analytics.js's `loadUmiejetnosci()` +
 * `renderSkillsTable()`: a dual-rating table (manager's manual 1-5 stars vs.
 * clients' average post-visit rating) per assigned service, with an
 * editable-in-place manual rating and a radar chart once ≥3 services carry
 * one. */
export function EmployeeAnalyticsSkillsTab({ employeeId }: { employeeId: number }) {
  const servicesState = useApiData(() => employeeServicesApi.withRatings(employeeId), [employeeId]);
  const toast = useToast();
  const services = servicesState.data ?? [];
  const rated = services.filter((s) => s.skill_rating !== null);

  const radarRef = useChartCanvas(() => {
    if (rated.length < 3) return null;
    return {
      type: 'radar',
      data: {
        labels: rated.map((s) => s.service_name),
        datasets: [
          {
            label: 'Ocena manualna',
            data: rated.map((s) => s.skill_rating),
            backgroundColor: CHART_COLORS.blueFill,
            borderColor: CHART_COLORS.blue,
            pointBackgroundColor: CHART_COLORS.blue,
            borderWidth: 2,
            pointRadius: 4,
          },
          {
            label: 'Ocena klientów',
            data: rated.map((s) => s.avg_client_rating),
            fill: false,
            borderColor: CHART_COLORS.green,
            pointBackgroundColor: CHART_COLORS.green,
            borderWidth: 2,
            pointRadius: 4,
            spanGaps: false,
          },
        ],
      },
      options: {
        ...CHART_BASE_OPTIONS,
        plugins: { legend: { display: true, position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } } },
        scales: { r: { min: 0, max: 5, ticks: { stepSize: 1, font: { size: 11 } }, pointLabels: { font: { size: 12 } }, grid: { color: 'rgba(0,0,0,0.06)' } } },
      },
    };
  }, [rated]);

  async function saveSkillRating(esId: number, score: number) {
    try {
      await employeeServicesApi.update(employeeId, esId, { skill_rating: score });
      servicesState.reload();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Nie udało się zapisać oceny');
    }
  }

  if (servicesState.loading) return <p className="analytics-loading">Ładowanie…</p>;
  if (servicesState.error) return <p className="analytics-error">Błąd: {servicesState.error.message}</p>;

  return (
    <div>
      <div className="analytics-chart-label">Usługi pracownika — ocena manualna vs. ocena klientów</div>
      {services.length === 0 ? (
        <p className="analytics-empty">Brak przypisanych usług</p>
      ) : (
        <div className="table-container">
          <table className="refined-table stack-cards">
            <thead>
              <tr>
                <th>Usługa</th>
                <th>Kategoria</th>
                <th title="Ocena ustawiana ręcznie przez menedżera">Ocena manualna</th>
                <th title="Średnia z ocen klientów na ukończonych wizytach">Ocena klientów</th>
                <th>Wizyt z oceną</th>
              </tr>
            </thead>
            <tbody>
              {services.map((svc) => (
                <SkillRow key={svc.es_id} svc={svc} onRate={saveSkillRating} />
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="analytics-skills-hint">
        Kliknij gwiazdki w kolumnie <strong>Ocena manualna</strong>, aby ustawić lub zmienić ocenę pracownika dla danej usługi.
      </p>

      {rated.length >= 3 && (
        <div className="analytics-radar-wrap">
          <div className="analytics-chart-label">Wykres ocen manualnych</div>
          <div className="analytics-chart-box" style={{ height: 300 }}>
            <canvas ref={radarRef} role="img" aria-label="Wykres radarowy ocen manualnych umiejętności" />
          </div>
        </div>
      )}
    </div>
  );
}

function SkillRow({ svc, onRate }: { svc: EmployeeServiceRating; onRate: (esId: number, score: number) => void }) {
  const category = svc.service_category || (svc.service_type === 'addon' ? 'Mikrousługa' : '—');
  return (
    <tr>
      <td className="cell-name" data-label="Usługa">
        {svc.service_name}
      </td>
      <td data-label="Kategoria" style={{ color: 'var(--color-ink-subtle)', fontSize: '0.75rem' }}>
        {category}
      </td>
      <td data-label="Ocena manualna" style={{ textAlign: 'center' }}>
        <EditableStars esId={svc.es_id} rating={svc.skill_rating} onRate={onRate} />
      </td>
      <td data-label="Ocena klientów" style={{ textAlign: 'center' }}>
        {svc.avg_client_rating !== null ? (
          <>
            <span style={{ fontWeight: 600, color: 'var(--color-ink)' }}>{svc.avg_client_rating.toFixed(1)}</span>{' '}
            <span style={{ color: 'var(--color-star-filled)', fontSize: '0.875rem' }}>
              {'★'.repeat(Math.round(svc.avg_client_rating))}
              {'☆'.repeat(5 - Math.round(svc.avg_client_rating))}
            </span>
          </>
        ) : (
          <span style={{ color: 'var(--color-ink-subtle)' }}>—</span>
        )}
      </td>
      <td data-label="Wizyt z oceną" style={{ textAlign: 'right', color: 'var(--color-ink-subtle)', fontSize: '0.75rem' }}>
        {svc.scored_visits}
      </td>
    </tr>
  );
}

function EditableStars({ esId, rating, onRate }: { esId: number; rating: number | null; onRate: (esId: number, score: number) => void }) {
  return (
    <span>
      {[1, 2, 3, 4, 5].map((n) => {
        const filled = rating !== null && n <= rating;
        return (
          <button
            key={n}
            type="button"
            className="skill-star-btn"
            style={{ color: filled ? 'var(--color-star-filled)' : 'var(--color-star-empty)' }}
            title={`Ustaw ocenę ${n}/5`}
            onClick={() => onRate(esId, n)}
          >
            {filled ? '★' : '☆'}
          </button>
        );
      })}
    </span>
  );
}
