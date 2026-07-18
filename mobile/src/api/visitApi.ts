import Constants from 'expo-constants';

const API_BASE_URL: string =
  (Constants.expoConfig?.extra?.apiBaseUrl as string | undefined) ??
  'https://www.my-way-solutions.com';

export type VisitState =
  | 'too_early'
  | 'already_done'
  | 'wrong_status'
  | 'success'
  | 'start_visit'
  | 'end_visit';

export interface VisitAppointment {
  first_name: string;
  last_name: string;
  appointment_date: string;
  start_time: string;
  status: string;
}

export interface VisitStatusResponse {
  success: boolean;
  state?: VisitState;
  appointment?: VisitAppointment;
  minutes_remaining?: number;
  new_status?: 'in_progress' | 'completed';
  error?: string;
}

async function parseResponse(res: Response): Promise<VisitStatusResponse> {
  let body: VisitStatusResponse;
  try {
    body = (await res.json()) as VisitStatusResponse;
  } catch {
    return { success: false, error: 'bad_response' };
  }
  if (!res.ok && body.error === undefined) {
    return { success: false, error: `http_${res.status}` };
  }
  return body;
}

export async function fetchVisitStatus(token: string): Promise<VisitStatusResponse> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/visit/${encodeURIComponent(token)}`);
    return await parseResponse(res);
  } catch {
    return { success: false, error: 'network_error' };
  }
}

export async function submitVisitAction(
  token: string,
  action: 'start' | 'end'
): Promise<VisitStatusResponse> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/visit/${encodeURIComponent(token)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action }),
    });
    return await parseResponse(res);
  } catch {
    return { success: false, error: 'network_error' };
  }
}

/**
 * Employees paste the SMS link itself just as often as the bare token —
 * accept either. Falls back to treating the whole input as the token.
 */
export function extractToken(input: string): string {
  const trimmed = input.trim();
  const match = trimmed.match(/\/visit\/([^/?#]+)/);
  return match ? match[1] : trimmed;
}
