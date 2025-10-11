<script setup lang="ts">
import { ref } from "vue";
import { useRouter, RouterLink } from "vue-router";
import { registerUser, usingMockAuth } from "../lib/auth";

const router = useRouter();
const name = ref("");
const email = ref("");
const password = ref("");
const error = ref("");
const loading = ref(false);
const isMockAuth = usingMockAuth;

const handleSignUp = async () => {
  error.value = "";
  loading.value = true;

  try {
    await registerUser(name.value, email.value, password.value);
    router.push("/dashboard");
  } catch (err) {
    error.value =
      err instanceof Error ? err.message : "Failed to create account. Please try again.";
  } finally {
    loading.value = false;
  }
};
</script>

<template>
  <div class="min-h-screen bg-background flex items-center justify-center p-4">
    <div class="w-full max-w-md space-y-8">
      <div class="text-center">
        <RouterLink to="/" class="inline-flex items-center gap-2 mb-8">
          <div class="w-10 h-10 bg-primary rounded-lg flex items-center justify-center">
            <span class="text-primary-foreground font-bold text-lg">5</span>
          </div>
          <span class="font-semibold text-xl text-foreground">504: Deadline Exceeded</span>
        </RouterLink>
        <h1 class="text-3xl font-bold text-foreground">Create your account</h1>
        <p class="text-muted-foreground mt-2">Start organizing your studies today</p>
      </div>

      <div class="bg-card border border-border rounded-lg p-8 shadow-sm">
        <form @submit.prevent="handleSignUp" class="space-y-6">
          <div class="space-y-2">
            <label for="name" class="text-sm font-medium text-foreground">Full Name</label>
            <input
              id="name"
              v-model="name"
              type="text"
              required
              placeholder="John Doe"
              class="w-full px-4 py-2 bg-background border border-input rounded-lg focus:outline-none focus:ring-2 focus:ring-ring text-foreground placeholder:text-muted-foreground"
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
              class="w-full px-4 py-2 bg-background border border-input rounded-lg focus:outline-none focus:ring-2 focus:ring-ring text-foreground placeholder:text-muted-foreground"
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
              class="w-full px-4 py-2 bg-background border border-input rounded-lg focus:outline-none focus:ring-2 focus:ring-ring text-foreground placeholder:text-muted-foreground"
            />
          </div>

          <div v-if="error" class="p-3 bg-destructive/10 border border-destructive/20 rounded-lg">
            <p class="text-sm text-destructive">{{ error }}</p>
          </div>

          <button
            type="submit"
            :disabled="loading"
            class="w-full px-4 py-3 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors font-medium disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {{ loading ? "Creating account..." : "Create Account" }}
          </button>
        </form>

        <div class="mt-6 text-center">
          <p v-if="isMockAuth" class="text-xs text-muted-foreground mb-3">
            You're using mock authentication. Data is stored locally for development only.
          </p>
          <p class="text-sm text-muted-foreground">
            Already have an account?
            <RouterLink to="/signin" class="text-primary hover:underline font-medium">
              Sign in
            </RouterLink>
          </p>
        </div>
      </div>
    </div>
  </div>
</template>
