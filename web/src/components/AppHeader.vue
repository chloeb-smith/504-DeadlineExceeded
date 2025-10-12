<script setup lang="ts">
import { computed } from "vue";
import { useRoute, useRouter, RouterLink } from "vue-router";
import useAuth from "../stores/authStore";

const route = useRoute();
const router = useRouter();
const { isAuthenticated, displayName, signOut } = useAuth();

const welcomeLabel = computed(() => displayName.value || "");

const primaryLinks = computed(() => {
  const base = [
    { to: "/calendar", label: "Calendar" },
    { to: "/assistant", label: "Assistant" }
  ];
  return isAuthenticated.value
    ? [{ to: "/dashboard", label: "Dashboard" }, ...base]
    : base;
});

const showAuthButtons = computed(() => !isAuthenticated.value);

const isLinkActive = (target: string) => {
  if (target === "/") {
    return route.path === "/";
  }
  return route.path === target || route.path.startsWith(`${target}/`);
};

const linkClass = (target: string) =>
  [
    "text-sm transition-colors",
    isLinkActive(target) ? "text-foreground font-medium" : "text-muted-foreground hover:text-foreground"
  ].join(" ");

const handleSignOut = async () => {
  try {
    await signOut();
  } finally {
    router.push("/");
  }
};
</script>

<template>
  <header class="border-b border-border/40 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
    <div class="container mx-auto flex items-center justify-between gap-4 px-4 py-4">
      <RouterLink to="/" class="flex items-center gap-2 text-lg font-semibold text-foreground">
        <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
          <span class="font-bold text-primary-foreground">5</span>
        </div>
        <span>504: Deadline Exceeded</span>
      </RouterLink>
      <nav class="flex items-center gap-4">
        <RouterLink
          v-for="link in primaryLinks"
          :key="link.to"
          :to="link.to"
          :class="linkClass(link.to)"
        >
          {{ link.label }}
        </RouterLink>
      </nav>
      <div class="flex items-center gap-3">
        <template v-if="showAuthButtons">
          <RouterLink to="/signin" class="text-sm text-muted-foreground transition-colors hover:text-foreground">
            Sign In
          </RouterLink>
          <RouterLink
            to="/signup"
            class="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            Get Started
          </RouterLink>
        </template>
        <template v-else>
          <span class="hidden text-sm text-muted-foreground sm:inline">
            Hi, <span class="font-medium text-foreground">{{ welcomeLabel }}</span>
          </span>
          <button
            type="button"
            class="rounded-lg bg-secondary px-4 py-2 text-sm font-medium text-secondary-foreground transition-colors hover:bg-secondary/80"
            @click="handleSignOut"
          >
            Sign Out
          </button>
        </template>
      </div>
    </div>
  </header>
</template>
