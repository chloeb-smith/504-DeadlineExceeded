import {
  createUserWithEmailAndPassword,
  signInWithEmailAndPassword,
  updateProfile,
  onAuthStateChanged,
  UserCredential
} from "firebase/auth";
import { auth, isFirebaseConfigured } from "./firebase";

type StoredUser = {
  name: string;
  email: string;
  password: string;
  normalizedEmail: string;
};

export type AuthResult = {
  email: string;
  displayName?: string | null;
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

const firebaseSignUp = async (name: string, email: string, password: string) => {
  if (!auth) {
    throw new Error("Firebase authentication is not initialized.");
  }

  const cleanedName = cleanName(name);
  const cleanedEmail = email.trim();
  const cleanedPassword = cleanPassword(password);

  const credentials: UserCredential = await createUserWithEmailAndPassword(
    auth,
    cleanedEmail,
    cleanedPassword
  );
  if (cleanedName) {
    await updateProfile(credentials.user, { displayName: cleanedName });
  }
  const result: AuthResult = {
    email: credentials.user.email ?? cleanedEmail,
    displayName: credentials.user.displayName ?? cleanedName
  };
  setSession(result);
  return result;
};

const firebaseSignIn = async (email: string, password: string) => {
  if (!auth) {
    throw new Error("Firebase authentication is not initialized.");
  }

  const cleanedEmail = email.trim();
  const cleanedPassword = cleanPassword(password);

  const credentials = await signInWithEmailAndPassword(auth, cleanedEmail, cleanedPassword);
  const result: AuthResult = {
    email: credentials.user.email ?? cleanedEmail,
    displayName: credentials.user.displayName
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

export const registerUser = async (
  name: string,
  email: string,
  password: string
): Promise<AuthResult> => {
  if (isFirebaseConfigured) {
    return firebaseSignUp(name, email, password);
  }
  return mockSignUp(name, email, password);
};

export const loginUser = async (email: string, password: string): Promise<AuthResult> => {
  if (isFirebaseConfigured) {
    return firebaseSignIn(email, password);
  }
  return mockSignIn(email, password);
};

export const signOutUser = async (): Promise<void> => {
  setSession(null);
  if (auth && isFirebaseConfigured) {
    try {
      await auth.signOut();
    } catch (error) {
      console.warn("Failed to sign out from Firebase:", error);
    }
  }
};

export const usingMockAuth = !isFirebaseConfigured;

if (auth && isFirebaseConfigured) {
  onAuthStateChanged(auth, (user) => {
    if (user) {
      setSession({
        email: user.email ?? "",
        displayName: user.displayName ?? undefined
      });
    } else {
      setSession(null);
    }
  });
}
