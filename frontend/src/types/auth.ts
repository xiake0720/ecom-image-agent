export interface UserProfile {
  id: string;
  email: string;
  nickname: string | null;
  avatar_url: string | null;
  status: string;
  email_verified: boolean;
  last_login_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface AuthTokenResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  user: UserProfile;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface RegisterPayload extends LoginPayload {
  nickname?: string;
}
