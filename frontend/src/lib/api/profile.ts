import { api } from './client';
import type { ChangePasswordPayload, ProfileResponse } from '../../types/profile';

/** `/auth/profile` + `/auth/change-password` (routes/auth/routes.py) — both
 * branch on the `X-Requested-With` header the shared `api` wrapper sends. */
export const profileApi = {
  get: () => api.get<ProfileResponse>('/auth/profile'),

  changePassword: (payload: ChangePasswordPayload) => api.post<{ success: true }>('/auth/change-password', payload),
};
