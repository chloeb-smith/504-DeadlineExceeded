import { api } from "../api";

type StoredUser = {
  name: string;
  email: string;
  password: string;
  normalizedEmail: string;
};

export type AuthTokens = {
  accessToken?: string;
  idToken?: string;
  refreshToken?: string;
  expiresIn?: number;
  tokenType?: string;
  scope?: string;
};

export type AuthResult = {
  email: string;
  displayName?: string | null;
  tokens?: AuthTokens;
};

const USERS_KEY = "deadline-exceeded-users";
const SESSION_KEY = "deadline-exceeded-session";

const isBrowser = typeof window !== "undefined";

const delay = (ms = 350) => new Promise((resolve) => setTimeout(resolve, ms));

const normalizeEmail = (value: string) => value.trim().toLowerCase();
const cleanPassword = (value: string) => value.trim();
const cleanName = (value: string) => value.trim();

const mockUserCache = new Map<string, StoredUser>();
let mockUsersHydrated = false;

const hydrateMockUsers = () => {
  if (!isBrowser || mockUsersHydrated) return;
  mockUsersHydrated = true;
  try {
    const raw = window.localStorage.getItem(USERS_KEY);
    if (!raw) return;
    const parsed = JSON.parse(raw) as Array<Partial<StoredUser>>;
    parsed.forEach((entry) => {
      if (!entry?.email || !entry?.password) return;
      const normalizedEmail = normalizeEmail(entry.email);
      mockUserCache.set(normalizedEmail, {
        name: cleanName(entry.name ?? ""),
        email: entry.email,
        password: cleanPassword(entry.password),
        normalizedEmail
      });
    });
  } catch (error) {
    console.warn("Failed to hydrate local auth users:", error);
    mockUserCache.clear();
  }
};

const persistMockUsers = () => {
  if (!isBrowser) return;
  const payload = JSON.stringify(Array.from(mockUserCache.values()));
  window.localStorage.setItem(USERS_KEY, payload);
};

export const getMockUsers = () => {
  hydrateMockUsers();
  return Array.from(mockUserCache.values());
};

const setSession = (user: AuthResult | null) => {
  if (!isBrowser) return;
  if (user) {
    window.localStorage.setItem(SESSION_KEY, JSON.stringify(user));
  } else {
    window.localStorage.removeItem(SESSION_KEY);
  }
};

export const getSessionUser = (): AuthResult | null => {
  if (!isBrowser) return null;
  try {
    const raw = window.localStorage.getItem(SESSION_KEY);
    return raw ? (JSON.parse(raw) as AuthResult) : null;
  } catch (error) {
    console.warn("Failed to read stored session:", error);
    return null;
  }
};

const decodeJwtPayload = (token?: string) => {
  if (!token) return null;
  const parts = token.split(".");
  if (parts.length !== 3) return null;
  try {
    const payload = parts[1];
    const normalized = payload.replace(/-/g, "+").replace(/_/g, "/");
    const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");
    const decoded = atob(padded);
    return JSON.parse(
      decodeURIComponent(
        decoded
          .split("")
          .map((c) => `%${c.charCodeAt(0).toString(16).padStart(2, "0")}`)
          .join("")
      )
    );
  } catch {
    return null;
  }
};

const normalizeTokens = (tokens: any): AuthTokens => ({
  accessToken: tokens?.access_token,
  idToken: tokens?.id_token,
  refreshToken: tokens?.refresh_token,
  expiresIn: typeof tokens?.expires_in === "number" ? tokens.expires_in : undefined,
  tokenType: tokens?.token_type,
  scope: tokens?.scope
});

const extractErrorMessage = (error: unknown, fallback: string) => {
  if (error && typeof error === "object" && "response" in error) {
    const resp = (error as { response?: { data?: any; status?: number } }).response;
    const message =
      resp?.data?.message || resp?.data?.error || resp?.data?.error_description || null;
    if (typeof message === "string" && message.trim()) {
      return message;
    }
  }
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
};

const auth0SignUp = async (name: string, email: string, password: string): Promise<AuthResult> => {
  let response;
  try {
    response = await api.post("/api/auth/register", {
      email,
      password,
      displayName: name
    });
  } catch (error) {
    throw new Error(
      extractErrorMessage(
        error,
        "We couldn't create your account. Double-check your details and try again."
      )
    );
  }
  const { profile, tokens } = response.data ?? {};
  const normalizedTokens = normalizeTokens(tokens);
  const claims = decodeJwtPayload(normalizedTokens.idToken);
  const result: AuthResult = {
    email: profile?.email ?? claims?.email ?? email,
    displayName: profile?.name ?? claims?.name ?? cleanName(name),
    tokens: normalizedTokens
  };
  setSession(result);
  return result;
};

const auth0SignIn = async (email: string, password: string): Promise<AuthResult> => {
  let response;
  try {
    response = await api.post("/api/auth/login", {
      email,
      password
    });
  } catch (error) {
    throw new Error(
      extractErrorMessage(
        error,
        "We couldn't sign you in with those credentials. Please try again."
      )
    );
  }
  const normalizedTokens = normalizeTokens(response.data?.tokens);
  const claims = decodeJwtPayload(normalizedTokens.idToken);
  const result: AuthResult = {
    email: claims?.email ?? email,
    displayName: claims?.name ?? claims?.nickname ?? claims?.email ?? email,
    tokens: normalizedTokens
  };
  setSession(result);
  return result;
};

const mockSignUp = async (name: string, email: string, password: string) => {
  await delay();
  const normalizedEmail = normalizeEmail(email);
  hydrateMockUsers();
  const alreadyExists = mockUserCache.has(normalizedEmail);

  if (alreadyExists) {
    throw new Error("An account with that email already exists. Try signing in instead.");
  }

  const entry: StoredUser = {
    name: cleanName(name),
    email: email.trim(),
    password: cleanPassword(password),
    normalizedEmail
  };
  mockUserCache.set(normalizedEmail, entry);
  persistMockUsers();
  const session: AuthResult = { email: entry.email, displayName: entry.name };
  setSession(session);
  return session;
};

const mockSignIn = async (email: string, password: string) => {
  await delay();
  const normalizedEmail = normalizeEmail(email);
  const cleanedPassword = cleanPassword(password);
  hydrateMockUsers();
  const match = mockUserCache.get(normalizedEmail);

  if (!match || match.password !== cleanedPassword) {
    throw new Error("We couldn't find that email and password combination. Please try again.");
  }

  const session: AuthResult = { email: match.email, displayName: match.name };
  setSession(session);
  return session;
};

const env = import.meta.env;
const isAuth0Configured = Boolean(env.VITE_AUTH0_DOMAIN && env.VITE_AUTH0_CLIENT_ID);

export const registerUser = async (
  name: string,
  email: string,
  password: string
): Promise<AuthResult> => {
  if (isAuth0Configured) {
    return auth0SignUp(name, email, password);
  }
  return mockSignUp(name, email, password);
};

export const loginUser = async (email: string, password: string): Promise<AuthResult> => {
  if (isAuth0Configured) {
    return auth0SignIn(email, password);
  }
  return mockSignIn(email, password);
};

export const signOutUser = async (): Promise<void> => {
  setSession(null);
};

export const usingMockAuth = !isAuth0Configured;
