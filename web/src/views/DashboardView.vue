<script setup lang="ts">
import { RouterLink } from "vue-router";
</script>

<template>
  <div class="min-h-screen bg-background">
    <div class="container mx-auto px-4 py-16 space-y-8">
      <header class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 class="text-3xl font-semibold text-foreground">Dashboard</h1>
          <p class="text-muted-foreground mt-1">
            Welcome back! This is a placeholder dashboard. Replace it with real data when ready.
          </p>
        </div>
        <RouterLink
          to="/"
          class="inline-flex items-center justify-center px-5 py-2 rounded-lg bg-secondary text-secondary-foreground hover:bg-secondary/80 transition-colors"
        >
          Return Home
        </RouterLink>
      </header>

      <section class="grid gap-6 md:grid-cols-2">
        <div class="bg-card border border-border rounded-xl p-6 shadow-sm space-y-3">
          <h2 class="text-xl font-semibold text-foreground">Upcoming Deadlines</h2>
          <p class="text-muted-foreground">
            Connect your coursework to see a snapshot of what's due next.
          </p>
        </div>
        <div class="bg-card border border-border rounded-xl p-6 shadow-sm space-y-3">
          <h2 class="text-xl font-semibold text-foreground">Focus Plan</h2>
          <p class="text-muted-foreground">
            Personalized study blocks will appear here once the planner is configured.
          </p>
        </div>
      </section>
    </div>
  </div>
</template>
