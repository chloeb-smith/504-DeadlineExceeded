<script setup lang="ts">
import { RouterLink } from "vue-router";
</script>

<template>
  <div class="min-h-screen bg-background">
    <header
      class="border-b border-border/40 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60"
    >
      <div class="container mx-auto px-4 py-4 flex items-center justify-between">
        <div class="flex items-center gap-2">
          <div class="w-8 h-8 bg-primary rounded-lg flex items-center justify-center">
            <span class="text-primary-foreground font-bold">5</span>
          </div>
          <span class="font-semibold text-lg text-foreground">504: Deadline Exceeded</span>
        </div>
        <nav class="flex items-center gap-4">
          <RouterLink
            to="/signin"
            class="text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            Sign In
          </RouterLink>
          <RouterLink
            to="/signup"
            class="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors text-sm font-medium"
          >
            Get Started
          </RouterLink>
        </nav>
      </div>
    </header>

    <main class="container mx-auto px-4 py-20 md:py-32">
      <div class="max-w-3xl mx-auto text-center space-y-8">
        <h1 class="text-4xl md:text-6xl font-bold text-foreground text-balance">
          Never Miss a Deadline Again
        </h1>
        <p class="text-xl text-muted-foreground text-pretty max-w-2xl mx-auto">
          AI-powered study planning that syncs with Canvas and adapts to your schedule.
          Stay organized, focused, and ahead of your coursework.
        </p>
        <div class="flex flex-col sm:flex-row gap-4 justify-center pt-4">
          <RouterLink
            to="/signup"
            class="px-8 py-4 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors text-lg font-medium"
          >
            Start Planning
          </RouterLink>
          <a
            href="#learn-more"
            class="px-8 py-4 bg-secondary text-secondary-foreground rounded-lg hover:bg-secondary/80 transition-colors text-lg font-medium"
          >
            Learn More
          </a>
        </div>
      </div>
      <section
        id="learn-more"
        class="mt-20 grid gap-8 md:grid-cols-3 text-left"
      >
        <div class="bg-card border border-border rounded-xl p-6 shadow-sm space-y-3">
          <h3 class="text-lg font-semibold text-foreground">Canvas Sync</h3>
          <p class="text-muted-foreground text-sm">
            Import assignments automatically so every due date and rubric detail lives in one place.
          </p>
        </div>
        <div class="bg-card border border-border rounded-xl p-6 shadow-sm space-y-3">
          <h3 class="text-lg font-semibold text-foreground">Adaptive Planning</h3>
          <p class="text-muted-foreground text-sm">
            Our AI reorganizes your schedule when life happens, highlighting the tasks that need attention.
          </p>
        </div>
        <div class="bg-card border border-border rounded-xl p-6 shadow-sm space-y-3">
          <h3 class="text-lg font-semibold text-foreground">Focus Support</h3>
          <p class="text-muted-foreground text-sm">
            Receive focused study blocks and reminders so you tackle big projects without the last-minute rush.
          </p>
        </div>
      </section>
    </main>
  </div>
</template>
