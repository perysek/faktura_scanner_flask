import { useRef, useState } from 'react';
import type { TouchEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { Icon } from '../../lib/icons/Icon';
import { formatPhone } from '../../lib/format';
import { Modal } from '../../components/ui/Modal';
import type { BalanceSummaryEntry, EmployeeListRow } from '../../types/employee';

/** Same mechanics as MobileWizytyCalendarView's card swipe (TASK5/TASK3 there)
 * — hand-rolled, no gesture library in this project's deps. Ported thresholds
 * 1:1; only the two actions differ (both navigate here, confirmed with the
 * principal: left→Zobacz, right→Edytuj, not the visit-card's action+nav
 * split). Horizontal drag must dominate vertical by 1.5x before it's treated
 * as a swipe at all, so an ordinary list scroll starting on a card is never
 * hijacked. */
const SWIPE_TRIGGER_PX = -84;
const SWIPE_MAX_PX = -120;
const SWIPE_TRIGGER_PX_RIGHT = 84;
const SWIPE_MAX_PX_RIGHT = 120;

function telHref(phone: string): string {
  const digits = phone.replace(/\D/g, '');
  if (digits.length === 9) return `tel:+48${digits}`;
  if (digits.length === 11 && digits.startsWith('48')) return `tel:+${digits}`;
  return `tel:${digits}`;
}

function statusBadge(emp: EmployeeListRow) {
  if (!emp.is_active) return { cls: 'inactive', label: 'Nieaktywny' };
  if (emp.employment_status === 'on_leave') return { cls: 'on-leave', label: 'Na urlopie' };
  if (emp.employment_status === 'terminated') return { cls: 'terminated', label: 'Zwolniony' };
  return { cls: 'active', label: 'Aktywny' };
}

function ratingClass(avg: number): string {
  if (avg >= 4.5) return 'rating-excellent';
  if (avg >= 3.5) return 'rating-good';
  if (avg >= 2.5) return 'rating-fair';
  return 'rating-poor';
}

export interface MobileEmployeesListViewProps {
  employees: EmployeeListRow[];
  loading: boolean;
  error: string | null;
  balances: Record<string, BalanceSummaryEntry>;
  /** Gates the swipe-RIGHT→Edytuj affordance — a read-only viewer gets no
   * edit action to swipe into, same as the desktop table's own Edytuj icon
   * being hidden for them (EmployeesListPage.tsx). */
  canWrite: boolean;
}

export function MobileEmployeesListView({ employees, loading, error, balances, canWrite }: MobileEmployeesListViewProps) {
  const navigate = useNavigate();
  const [swipeState, setSwipeState] = useState<{ id: number; dx: number } | null>(null);
  const [sheetTarget, setSheetTarget] = useState<EmployeeListRow | null>(null);
  const touchStartRef = useRef<{ x: number; y: number; id: number } | null>(null);
  const suppressClickRef = useRef<number | null>(null);

  function handleCardTouchStart(empId: number, e: TouchEvent<HTMLDivElement>) {
    const t = e.touches[0];
    touchStartRef.current = { x: t.clientX, y: t.clientY, id: empId };
  }
  function handleCardTouchMove(empId: number, e: TouchEvent<HTMLDivElement>) {
    const start = touchStartRef.current;
    if (!start || start.id !== empId) return;
    const t = e.touches[0];
    const dx = t.clientX - start.x;
    const dy = t.clientY - start.y;
    if (Math.abs(dx) <= Math.abs(dy) * 1.5) return;
    if (dx < 0) {
      setSwipeState({ id: empId, dx: Math.max(dx, SWIPE_MAX_PX) });
    } else if (dx > 0 && canWrite) {
      setSwipeState({ id: empId, dx: Math.min(dx, SWIPE_MAX_PX_RIGHT) });
    }
  }
  function handleCardTouchEnd(emp: EmployeeListRow) {
    touchStartRef.current = null;
    const dx = swipeState?.id === emp.id ? swipeState.dx : 0;
    const triggeredLeft = dx <= SWIPE_TRIGGER_PX;
    const triggeredRight = canWrite && dx >= SWIPE_TRIGGER_PX_RIGHT;
    setSwipeState(null);
    if (triggeredLeft) {
      suppressClickRef.current = emp.id;
      navigate(`/pracownicy/${emp.id}`);
    } else if (triggeredRight) {
      suppressClickRef.current = emp.id;
      navigate(`/pracownicy/${emp.id}/edytuj`);
    }
  }
  function handleCardClick(emp: EmployeeListRow) {
    if (suppressClickRef.current === emp.id) {
      suppressClickRef.current = null;
      return;
    }
    navigate(`/pracownicy/${emp.id}`);
  }

  if (loading) {
    return (
      <div className="mob-emp-list">
        <p className="empty-text">Ładowanie pracowników...</p>
      </div>
    );
  }
  if (error) {
    return (
      <div className="mob-emp-list">
        <p className="empty-text" style={{ color: 'var(--color-error)' }}>
          Błąd ładowania: {error}
        </p>
      </div>
    );
  }
  if (employees.length === 0) {
    return (
      <div className="mob-emp-list">
        <div className="empty-state">
          <Icon name="search_off" className="empty-icon" />
          <p className="empty-text">Nie znaleziono pracowników</p>
        </div>
      </div>
    );
  }

  return (
    <div className="mob-emp-list">
      {employees.map((emp) => {
        const badge = statusBadge(emp);
        const initials = (emp.first_name.charAt(0) + emp.last_name.charAt(0)).toUpperCase();
        const swipeDx = swipeState?.id === emp.id ? swipeState.dx : 0;
        const balance = balances[String(emp.id)];
        return (
          <div key={emp.id} className="mob-emp-card-wrap">
            {swipeDx < 0 && (
              <div className={['mob-emp-swipe-reveal', 'mob-emp-swipe-reveal--left', swipeDx <= SWIPE_TRIGGER_PX ? 'mob-emp-swipe-reveal--armed' : ''].filter(Boolean).join(' ')} aria-hidden="true">
                <div className="mob-emp-swipe-content mob-emp-swipe-content--left" style={{ transform: `translateX(${swipeDx}px)` }}>
                  <Icon name="badge" />
                  <span className="mob-emp-swipe-label">Zobacz</span>
                </div>
              </div>
            )}
            {canWrite && swipeDx > 0 && (
              <div className={['mob-emp-swipe-reveal', 'mob-emp-swipe-reveal--right', swipeDx >= SWIPE_TRIGGER_PX_RIGHT ? 'mob-emp-swipe-reveal--armed' : ''].filter(Boolean).join(' ')} aria-hidden="true">
                <div className="mob-emp-swipe-content mob-emp-swipe-content--right" style={{ transform: `translateX(${swipeDx}px)` }}>
                  <span className="mob-emp-swipe-label">Edytuj</span>
                  <Icon name="edit" />
                </div>
              </div>
            )}
            <div
              className={[
                'mob-emp-card',
                !emp.is_active ? 'mob-emp-card--muted' : '',
                swipeState?.id === emp.id && swipeState.dx <= SWIPE_TRIGGER_PX ? 'mob-emp-card--swipe-armed' : '',
                swipeState?.id === emp.id && swipeState.dx >= SWIPE_TRIGGER_PX_RIGHT ? 'mob-emp-card--swipe-armed-right' : '',
              ]
                .filter(Boolean)
                .join(' ')}
              style={swipeState?.id === emp.id ? { transform: `translateX(${swipeState.dx}px)`, transition: 'none' } : undefined}
              onClick={() => handleCardClick(emp)}
              onTouchStart={(e) => handleCardTouchStart(emp.id, e)}
              onTouchMove={(e) => handleCardTouchMove(emp.id, e)}
              onTouchEnd={() => handleCardTouchEnd(emp)}
            >
              <div className="mob-emp-identity">
                <div className="employee-avatar mob-emp-avatar">{initials}</div>
                <div className="mob-emp-name-wrap">
                  <span className="mob-emp-name">{emp.full_name}</span>
                  <span className="mob-emp-position">{emp.position || '—'}</span>
                  <div className="mob-emp-meta">
                    <span className={`status-badge ${badge.cls}`}>{badge.label}</span>
                    {emp.avg_satisfaction != null ? (
                      <span className={ratingClass(emp.avg_satisfaction)}>
                        ★ {emp.avg_satisfaction.toFixed(1)} <span className="rating-count">({emp.rated_count})</span>
                      </span>
                    ) : (
                      <span className="dim">Brak ocen</span>
                    )}
                    {balance && balance.status !== 'unlimited' && (
                      <span className={balance.status === 'exceeded' ? 'balance-exceeded' : balance.status === 'warning' ? 'balance-warning' : 'balance-ok'}>
                        {Math.round(balance.used)}/{balance.limit}
                        {balance.unit === 'hours' ? 'h' : 'd'} urlopu
                      </span>
                    )}
                  </div>
                </div>
              </div>

              <div className="mob-emp-actions">
                {canWrite && (
                  <button
                    type="button"
                    className="mob-emp-more"
                    aria-label={`Akcje: ${emp.full_name}`}
                    onClick={(e) => {
                      e.stopPropagation();
                      setSheetTarget(emp);
                    }}
                  >
                    <Icon name="more_horiz" />
                  </button>
                )}
                {emp.phone && (
                  <a className="mob-emp-phone-btn" href={telHref(emp.phone)} title={formatPhone(emp.phone)} aria-label={`Zadzwoń: ${formatPhone(emp.phone)}`} onClick={(e) => e.stopPropagation()}>
                    <Icon name="call" />
                  </a>
                )}
              </div>
            </div>
          </div>
        );
      })}

      <Modal isOpen={sheetTarget !== null} onClose={() => setSheetTarget(null)} title={sheetTarget?.full_name ?? ''} variant="sheet">
        {sheetTarget && (
          <ul className="action-sheet">
            <li>
              <button
                type="button"
                className="action-sheet-item"
                onClick={() => {
                  const id = sheetTarget.id;
                  setSheetTarget(null);
                  navigate(`/pracownicy/${id}`);
                }}
              >
                <Icon name="badge" /> Zobacz szczegóły
              </button>
            </li>
            {canWrite && (
              <li>
                <button
                  type="button"
                  className="action-sheet-item"
                  onClick={() => {
                    const id = sheetTarget.id;
                    setSheetTarget(null);
                    navigate(`/pracownicy/${id}/edytuj`);
                  }}
                >
                  <Icon name="edit" /> Edytuj pracownika
                </button>
              </li>
            )}
          </ul>
        )}
      </Modal>
    </div>
  );
}
