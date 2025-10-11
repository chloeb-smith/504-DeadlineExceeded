import { initializeApp, getApps, getApp, FirebaseOptions, FirebaseApp } from "firebase/app";
import { getAuth, Auth } from "firebase/auth";

const env = import.meta.env;

const rawConfig: Partial<FirebaseOptions> = {
  apiKey: env.VITE_FIREBASE_API_KEY,
  authDomain: env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: env.VITE_FIREBASE_APP_ID,
  measurementId: env.VITE_FIREBASE_MEASUREMENT_ID
};

const missingKeys = Object.entries(rawConfig)
  .filter(([, value]) => !value)
  .map(([key]) => key);

export const isFirebaseConfigured = missingKeys.length === 0;

if (!isFirebaseConfigured) {
  console.warn(
    `Missing Firebase environment variables: ${missingKeys.join(
      ", "
    )}. Falling back to local auth storage until they are provided.`
  );
}

let app: FirebaseApp | undefined;
let auth: Auth | null = null;

if (isFirebaseConfigured) {
  const config = rawConfig as FirebaseOptions;
  app = getApps().length ? getApp() : initializeApp(config);
  auth = getAuth(app);
}

export { auth };
export default app;
