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
  unlock_at?: string;
  can_no_show?: boolean;
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
    return { appointments: [], ...body };
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
  unlock_at?: string;
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
    return await parseJson(res);
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
  unlock_at?: string;
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
    return await parseJson(res);
  } catch {
    return { success: false, error: 'network_error' };
  }
}
