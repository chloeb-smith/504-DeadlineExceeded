import { ref, computed } from "vue";
import {
  registerUser,
  loginUser,
  signOutUser,
  getSessionUser,
  usingMockAuth,
  type AuthResult
} from "../lib/auth";

const currentUser = ref<AuthResult | null>(getSessionUser());

const isAuthenticated = computed(() => currentUser.value !== null);

const signUp = async (name: string, email: string, password: string) => {
  const user = await registerUser(name, email, password);
  currentUser.value = user;
  return user;
};

const signIn = async (email: string, password: string) => {
  const user = await loginUser(email, password);
  currentUser.value = user;
  return user;
};

const signOut = async () => {
  await signOutUser();
  currentUser.value = null;
};

const getDisplayName = computed(() => {
  if (!currentUser.value) return "";
  return currentUser.value.displayName || currentUser.value.email;
});

const useAuth = () => ({
  currentUser,
  isAuthenticated,
  signUp,
  signIn,
  signOut,
  displayName: getDisplayName,
  usingMockAuth
});

export default useAuth;
