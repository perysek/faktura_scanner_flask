import { api } from './client';

export interface EmployeeOption {
  id: number;
  first_name: string;
  last_name: string;
}

export interface ServiceOption {
  id: number;
  name: string;
}

export interface ServiceForEmployee {
  service_id: number;
  service_name: string;
}

export interface EmployeeForService {
  employee_id: number;
  first_name: string;
  last_name: string;
}

/** Small cross-module lookups consumed by the client-preferences form
 * (view.html §"Dodaj preferencję") — routes/api_routes.py +
 * routes/employee_service_routes.py. Each of these four calls requires its
 * OWN module ('employees'/'services'), independent of 'clients' — a role
 * without that access gets a 403 here exactly like it does in the Jinja page
 * this replaces (not a regression introduced by the port). */
export const lookupsApi = {
  employees: () => api.get<{ success: true; employees: EmployeeOption[] }>('/api/employees', { active_only: true }).then((r) => r.employees),
  services: () => api.get<{ success: true; services: ServiceOption[] }>('/api/services', { active_only: true }).then((r) => r.services),
  servicesForEmployee: (employeeId: number) =>
    api
      .get<{ success: true; services: ServiceForEmployee[] }>(`/api/employees/${employeeId}/services`, { active_only: true })
      .then((r) => r.services),
  employeesForService: (serviceId: number) =>
    api
      .get<{ success: true; employees: EmployeeForService[] }>(`/api/services/${serviceId}/employees`, { active_only: true })
      .then((r) => r.employees),
};
