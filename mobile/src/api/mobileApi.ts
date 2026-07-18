import Constants from 'expo-constants';

const API_BASE_URL: string =
  (Constants.expoConfig?.extra?.apiBaseUrl as string | undefined) ??
  'https://www.my-way-solutions.com';

export interface EmployeeSummary {
  id: number;
  name: string;
  has_pin: boolean;
}

export type VisitState =
  | 'too_early'
  | 'already_done'
  | 'wrong_status'
  | 'success'
  | 'start_visit'
  | 'end_visit';

export interface TodayAppointment {
  appointment_id: number;
  start_time: string;
  client_name: string;
  service_name: string | null;
  status: string;
  state: VisitState;
  minutes_remaining?: number;
  seconds_remaining?: number;
  seconds_until_start?: number;
  unlock_at?: string;
  can_no_show?: boolean;
  /** Both client-computed at receipt time, from the *_seconds_* durations
   * above -- never parse unlock_at. The server runs in UTC but appointment
   * times are Polish local, so that naive ISO string reads as local time
   * on-device and lands ~2h off (CEST), making every too_early row look
   * already-expired and looping the "refetch on expiry" logic forever.
   * A plain duration is immune to that mismatch. */
  unlockAtLocalMs?: number;
  /** Time until the actual appointment start -- what the today-list badge
   * counts down to (in both too_early and start_visit), vs unlockAtLocalMs
   * which only gates the too_early -> start_visit transition. */
  startAtLocalMs?: number;
}

function anchorTimers<T extends { state?: VisitState; seconds_remaining?: number; seconds_until_start?: number }>(
  appt: T
): T {
  const patch: Partial<TodayAppointment> = {};
  if (appt.state === 'too_early' && typeof appt.seconds_remaining === 'number') {
    patch.unlockAtLocalMs = Date.now() + appt.seconds_remaining * 1000;
  }
  if (
    (appt.state === 'too_early' || appt.state === 'start_visit') &&
    typeof appt.seconds_until_start === 'number'
  ) {
    patch.startAtLocalMs = Date.now() + appt.seconds_until_start * 1000;
  }
  return { ...appt, ...patch };
}

async function parseJson(res: Response): Promise<any> {
  try {
    return await res.json();
  } catch {
    return { success: false, error: 'bad_response' };
  }
}

export async function fetchEmployees(): Promise<{
  success: boolean;
  employees: EmployeeSummary[];
  error?: string;
}> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/mobile/employees`);
    const body = await parseJson(res);
    return { employees: [], ...body };
  } catch {
    return { success: false, employees: [], error: 'network_error' };
  }
}

export interface PinResult {
  success: boolean;
  first_time?: boolean;
  session_token?: string;
  error?: string;
}

export async function submitPin(employeeId: number, pin: string): Promise<PinResult> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/mobile/employees/${employeeId}/pin`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pin }),
    });
    return await parseJson(res);
  } catch {
    return { success: false, error: 'network_error' };
  }
}

export interface TodayResult {
  success: boolean;
  appointments: TodayAppointment[];
  today?: string;
  error?: string;
}

export async function fetchToday(sessionToken: string): Promise<TodayResult> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/mobile/today`, {
      headers: { Authorization: `Bearer ${sessionToken}` },
    });
    if (res.status === 401) {
      return { success: false, appointments: [], error: 'unauthorized' };
    }
    const body = await parseJson(res);
    return {
      ...body,
      appointments: Array.isArray(body.appointments) ? body.appointments.map(anchorTimers) : [],
    };
  } catch {
    return { success: false, appointments: [], error: 'network_error' };
  }
}

export interface AppointmentStateResult {
  success: boolean;
  appointment_id?: number;
  start_time?: string;
  status?: string;
  state?: VisitState;
  minutes_remaining?: number;
  seconds_remaining?: number;
  seconds_until_start?: number;
  unlock_at?: string;
  unlockAtLocalMs?: number;
  startAtLocalMs?: number;
  can_no_show?: boolean;
  error?: string;
}

export async function fetchAppointmentState(
  sessionToken: string,
  appointmentId: number
): Promise<AppointmentStateResult> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/mobile/appointments/${appointmentId}`, {
      headers: { Authorization: `Bearer ${sessionToken}` },
    });
    if (res.status === 401) {
      return { success: false, error: 'unauthorized' };
    }
    const body = await parseJson(res);
    return anchorTimers(body);
  } catch {
    return { success: false, error: 'network_error' };
  }
}

export interface ActionResult {
  success: boolean;
  state?: VisitState;
  new_status?: string;
  error?: string;
  minutes_remaining?: number;
  seconds_remaining?: number;
  seconds_until_start?: number;
  unlock_at?: string;
  unlockAtLocalMs?: number;
  startAtLocalMs?: number;
  can_no_show?: boolean;
}

export async function submitAppointmentAction(
  sessionToken: string,
  appointmentId: number,
  action: 'start' | 'end' | 'no_show'
): Promise<ActionResult> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/mobile/appointments/${appointmentId}/action`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${sessionToken}` },
      body: JSON.stringify({ action }),
    });
    if (res.status === 401) {
      return { success: false, error: 'unauthorized' };
    }
    const body = await parseJson(res);
    return anchorTimers(body);
  } catch {
    return { success: false, error: 'network_error' };
  }
}
