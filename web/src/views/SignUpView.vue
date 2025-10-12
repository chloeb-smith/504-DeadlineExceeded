<script setup lang="ts">
import { ref } from "vue";
import { useRouter, useRoute, RouterLink } from "vue-router";
import useAuth from "../stores/authStore";
import AppHeader from "../components/AppHeader.vue";

const router = useRouter();
const route = useRoute();
const { signUp, usingMockAuth: isMockAuth } = useAuth();

const name = ref("");
const email = ref("");
const password = ref("");
const error = ref("");
const loading = ref(false);

const handleSignUp = async () => {
  error.value = "";
  loading.value = true;

  try {
    await signUp(name.value, email.value, password.value);
    const redirectTo =
      typeof route.query.redirect === "string" && route.query.redirect
        ? route.query.redirect
        : "/dashboard";
    router.push(redirectTo);
  } catch (err) {
    error.value =
      err instanceof Error ? err.message : "Failed to create account. Please try again.";
  } finally {
    loading.value = false;
  }
};
</script>

<template>
  <div class="flex min-h-screen flex-col bg-background">
    <AppHeader />
    <main class="flex flex-1 items-center justify-center p-4">
      <div class="w-full max-w-md space-y-8">
        <div class="text-center">
          <h1 class="text-3xl font-bold text-foreground">Create your account</h1>
          <p class="mt-2 text-muted-foreground">Start organizing your studies today</p>
        </div>

        <div class="rounded-lg border border-border bg-card p-8 shadow-sm">
          <form @submit.prevent="handleSignUp" class="space-y-6">
            <div class="space-y-2">
              <label for="name" class="text-sm font-medium text-foreground">Full Name</label>
              <input
                id="name"
                v-model="name"
                type="text"
                required
                placeholder="John Doe"
                class="w-full rounded-lg border border-input bg-background px-4 py-2 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>

            <div class="space-y-2">
              <label for="email" class="text-sm font-medium text-foreground">Email</label>
              <input
                id="email"
                v-model="email"
                type="email"
                required
                placeholder="you@example.com"
                class="w-full rounded-lg border border-input bg-background px-4 py-2 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>

            <div class="space-y-2">
              <label for="password" class="text-sm font-medium text-foreground">Password</label>
              <input
                id="password"
                v-model="password"
                type="password"
                required
                placeholder="********"
                class="w-full rounded-lg border border-input bg-background px-4 py-2 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>

            <div v-if="error" class="rounded-lg border border-destructive/20 bg-destructive/10 p-3">
              <p class="text-sm text-destructive">{{ error }}</p>
            </div>

            <button
              type="submit"
              :disabled="loading"
              class="w-full rounded-lg bg-primary px-4 py-3 font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {{ loading ? "Creating account..." : "Create Account" }}
            </button>
          </form>

          <div class="mt-6 text-center">
            <p v-if="isMockAuth" class="mb-3 text-xs text-muted-foreground">
              You're using mock authentication. Data is stored locally for development only.
            </p>
            <p class="text-sm text-muted-foreground">
              Already have an account?
              <RouterLink to="/signin" class="font-medium text-primary hover:underline">
                Sign in
              </RouterLink>
            </p>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>
