import {
  createUserWithEmailAndPassword,
  signInWithEmailAndPassword,
  updateProfile,
  UserCredential
} from "firebase/auth";
import { auth, isFirebaseConfigured } from "./firebase";

type StoredUser = {
  name: string;
  email: string;
  password: string;
};

type AuthResult = {
  email: string;
  displayName?: string | null;
};

const USERS_KEY = "deadline-exceeded-users";
const SESSION_KEY = "deadline-exceeded-session";

const isBrowser = typeof window !== "undefined";

const delay = (ms = 350) => new Promise((resolve) => setTimeout(resolve, ms));

const readUsers = (): StoredUser[] => {
  if (!isBrowser) return [];
  try {
    const raw = window.localStorage.getItem(USERS_KEY);
    return raw ? (JSON.parse(raw) as StoredUser[]) : [];
  } catch (error) {
    console.warn("Failed to read local auth users:", error);
    return [];
  }
};

const writeUsers = (users: StoredUser[]) => {
  if (!isBrowser) return;
  window.localStorage.setItem(USERS_KEY, JSON.stringify(users));
};

const setSession = (user: AuthResult) => {
  if (!isBrowser) return;
  window.localStorage.setItem(SESSION_KEY, JSON.stringify(user));
};

const firebaseSignUp = async (name: string, email: string, password: string) => {
  if (!auth) {
    throw new Error("Firebase authentication is not initialized.");
  }

  const credentials: UserCredential = await createUserWithEmailAndPassword(auth, email, password);
  if (name) {
    await updateProfile(credentials.user, { displayName: name });
  }
  return { email: credentials.user.email ?? email, displayName: credentials.user.displayName ?? name };
};

const firebaseSignIn = async (email: string, password: string) => {
  if (!auth) {
    throw new Error("Firebase authentication is not initialized.");
  }

  const credentials = await signInWithEmailAndPassword(auth, email, password);
  return { email: credentials.user.email ?? email, displayName: credentials.user.displayName };
};

const mockSignUp = async (name: string, email: string, password: string) => {
  await delay();
  const users = readUsers();
  const alreadyExists = users.some((user) => user.email.toLowerCase() === email.toLowerCase());

  if (alreadyExists) {
    throw new Error("An account with that email already exists. Try signing in instead.");
  }

  const entry: StoredUser = { name, email, password };
  users.push(entry);
  writeUsers(users);
  setSession({ email, displayName: name });

  return { email, displayName: name };
};

const mockSignIn = async (email: string, password: string) => {
  await delay();
  const users = readUsers();
  const match = users.find(
    (user) => user.email.toLowerCase() === email.toLowerCase() && user.password === password
  );

  if (!match) {
    throw new Error("We couldn't find that email and password combination. Please try again.");
  }

  setSession({ email: match.email, displayName: match.name });
  return { email: match.email, displayName: match.name };
};

export const registerUser = async (name: string, email: string, password: string): Promise<AuthResult> => {
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

export const signOutUser = () => {
  if (isBrowser) {
    window.localStorage.removeItem(SESSION_KEY);
  }
  if (auth && isFirebaseConfigured) {
    auth.signOut().catch((error) => console.warn("Failed to sign out from Firebase:", error));
  }
};

export const usingMockAuth = !isFirebaseConfigured;
