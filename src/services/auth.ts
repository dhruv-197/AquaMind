import { FASTAPI_BASE as API_BASE } from '../config/api';

export interface AuthResponseData {
  access_token: string;
  token_type: string;
  role: string;
  username: string;
  email: string;
}

export interface AuthResponse {
  success: boolean;
  message: string;
  data: AuthResponseData;
}

async function parseApiError(response: Response): Promise<string> {
  try {
    const errorData = await response.json();
    const detail = errorData.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
      return detail.map((item: { msg?: string }) => item.msg || String(item)).join(', ');
    }
    return errorData.message || 'Request failed';
  } catch {
    return `Request failed (${response.status})`;
  }
}

async function authRequest<T>(path: string, body: Record<string, unknown>): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
  } catch {
    throw new Error('Unable to reach authentication server. Please ensure the backend is running.');
  }

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  return response.json();
}

export const authService = {
  async signup(username: string, email: string, role: string, password: string): Promise<AuthResponse> {
    return authRequest<AuthResponse>('/auth/signup', { username, email, role, password });
  },

  async login(email: string, password: string): Promise<AuthResponse> {
    return authRequest<AuthResponse>('/auth/login', { email, password });
  },

  /** Step 1 of reset: issues a one-time, 30-minute token (no email delivery in this pilot. See backend note). */
  async requestPasswordReset(email: string): Promise<{ success: boolean; message: string }> {
    return authRequest<{ success: boolean; message: string }>('/auth/request-password-reset', { email });
  },

  /** Step 2 of reset: completes the reset using the token from requestPasswordReset. */
  async forgotPassword(email: string, newPassword: string, resetToken: string): Promise<{ success: boolean; message: string }> {
    return authRequest<{ success: boolean; message: string }>('/auth/forgot-password', {
      email,
      new_password: newPassword,
      reset_token: resetToken
    });
  }
};
