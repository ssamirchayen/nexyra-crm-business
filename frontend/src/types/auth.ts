export type AuthUser = {
  public_id: string;
  name: string;
  email: string;
  must_change_password: boolean;
};

export type AuthWorkspace = {
  public_id: string;
  name: string;
  slug: string;
  segment: string;
  role: string;
  permissions: string[];
};

export type AuthContextPayload = {
  user: AuthUser;
  workspaces: AuthWorkspace[];
};

export type AuthLoginResponse = AuthContextPayload & {
  access_token: string;
  token_type: "bearer" | string;
  expires_at: string;
};

export type AuthMessageResponse = {
  ok: boolean;
  message: string;
};

export type AuthSession = {
  public_id: string;
  current: boolean;
  ip_address: string | null;
  user_agent: string | null;
  expires_at: string;
  revoked_at: string | null;
  revoked_reason: string | null;
  last_seen_at: string;
  created_at: string;
};

export type AuthSessionsRevokedResponse = {
  ok: boolean;
  revoked: number;
  message: string;
};

export type AuthPasswordRecoveryRequestedResponse = {
  ok: boolean;
  message: string;
  expires_in_minutes: number;
};
