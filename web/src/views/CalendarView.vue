<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import {
  addMonths,
  subMonths,
  startOfMonth,
  startOfWeek,
  endOfWeek,
  endOfMonth,
  eachDayOfInterval,
  isSameMonth,
  isToday,
  format,
  parseISO
} from "date-fns";
import { RouterLink } from "vue-router";
import useAssignments from "../stores/assignmentsStore";
import useAuth from "../stores/authStore";

const { loadAssignments, assignmentsByDate, coursesWithAssignments, loading, error, fetchedAt } =
  useAssignments();
const { isAuthenticated, displayName, signOut } = useAuth();

const currentMonth = ref(startOfMonth(new Date()));

onMounted(() => {
  loadAssignments();
});

const monthLabel = computed(() => format(currentMonth.value, "MMMM yyyy"));

const weeks = computed(() => {
  const firstDay = startOfWeek(startOfMonth(currentMonth.value), { weekStartsOn: 0 });
  const lastDay = endOfWeek(endOfMonth(currentMonth.value), { weekStartsOn: 0 });
  const days = eachDayOfInterval({ start: firstDay, end: lastDay });
  const chunked: Date[][] = [];
  for (let i = 0; i < days.length; i += 7) {
    chunked.push(days.slice(i, i + 7));
  }
  return chunked;
});

const dayNames = computed(() =>
  eachDayOfInterval({
    start: startOfWeek(new Date(), { weekStartsOn: 0 }),
    end: endOfWeek(new Date(), { weekStartsOn: 0 })
  }).map((date) => format(date, "EEE"))
);

const goToPreviousMonth = () => {
  currentMonth.value = subMonths(currentMonth.value, 1);
};

const goToNextMonth = () => {
  currentMonth.value = addMonths(currentMonth.value, 1);
};

const goToToday = () => {
  currentMonth.value = startOfMonth(new Date());
};

const assignmentsForDate = (date: Date) => {
  const key = format(date, "yyyy-MM-dd");
  return assignmentsByDate.value.get(key) ?? [];
};

const formattedFetchedAt = computed(() => {
  if (!fetchedAt.value) return null;
  try {
    const parsed = parseISO(fetchedAt.value);
    return format(parsed, "MMM d, yyyy - h:mm a");
  } catch {
    return fetchedAt.value;
  }
});

const courseColorPalette = [
  "border border-primary/40 bg-primary/15 text-foreground",
  "border border-secondary/40 bg-secondary/15 text-foreground",
  "border border-accent/40 bg-accent/15 text-foreground",
  "border border-muted text-foreground bg-muted/60"
];

const courseColorMap = computed<Record<number, string>>(() => {
  const map: Record<number, string> = {};
  coursesWithAssignments.value.forEach((course, index) => {
    map[course.id] = courseColorPalette[index % courseColorPalette.length];
  });
  return map;
});

const hasAssignments = computed(() => coursesWithAssignments.value.length > 0);
const welcomeLabel = computed(() => displayName.value || "");

const handleSignOut = async () => {
  await signOut();
};
</script>

<template>
  <div class="min-h-screen bg-background">
    <header
      class="border-b border-border/40 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60"
    >
      <div class="container mx-auto px-4 py-4 flex items-center justify-between">
        <RouterLink to="/" class="flex items-center gap-2 font-semibold text-lg text-foreground">
          <div class="w-8 h-8 bg-primary rounded-lg flex items-center justify-center">
            <span class="text-primary-foreground font-bold">5</span>
          </div>
          <span>504: Deadline Exceeded</span>
        </RouterLink>
        <nav class="flex items-center gap-4 text-sm">
          <RouterLink to="/dashboard" class="text-muted-foreground hover:text-foreground">
            Dashboard
          </RouterLink>
          <RouterLink to="/calendar" class="text-foreground font-medium">Calendar</RouterLink>
          <template v-if="!isAuthenticated">
            <RouterLink to="/signin" class="text-muted-foreground hover:text-foreground">
              Sign In
            </RouterLink>
            <RouterLink
              to="/signup"
              class="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors font-medium"
            >
              Get Started
            </RouterLink>
          </template>
          <template v-else>
            <span class="hidden sm:inline text-muted-foreground">
              Hi, <span class="text-foreground font-medium">{{ welcomeLabel }}</span>
            </span>
            <button
              type="button"
              class="px-4 py-2 bg-secondary text-secondary-foreground rounded-lg hover:bg-secondary/80 transition-colors font-medium"
              @click="handleSignOut"
            >
              Sign Out
            </button>
          </template>
        </nav>
      </div>
    </header>

    <main class="container mx-auto px-4 py-12 space-y-10">
      <section class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div class="space-y-1">
          <h1 class="text-4xl font-bold text-foreground">Planner Calendar</h1>
          <p class="text-muted-foreground max-w-2xl text-sm sm:text-base">
            View upcoming Canvas assignments across all of your courses. Use the navigation to scan
            month-by-month and hover for details.
          </p>
          <p v-if="formattedFetchedAt" class="text-xs text-muted-foreground">
            Last synced: {{ formattedFetchedAt }}
          </p>
        </div>
        <div class="flex items-center gap-3">
          <button
            type="button"
            class="px-3 py-2 rounded-lg border border-border text-sm text-muted-foreground hover:text-foreground transition-colors"
            @click="goToToday"
          >
            Today
          </button>
          <div class="flex items-center gap-2 bg-card border border-border rounded-lg px-3 py-2">
            <button
              type="button"
              class="p-1 rounded-md hover:bg-muted transition-colors"
              @click="goToPreviousMonth"
              aria-label="Previous month"
            >
              <
            </button>
            <span class="text-sm font-medium text-foreground">{{ monthLabel }}</span>
            <button
              type="button"
              class="p-1 rounded-md hover:bg-muted transition-colors"
              @click="goToNextMonth"
              aria-label="Next month"
            >
              >
            </button>
          </div>
          <button
            type="button"
            class="px-3 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors"
            :disabled="loading"
            @click="loadAssignments(true)"
          >
            {{ loading ? "Refreshing..." : "Sync Assignments" }}
          </button>
        </div>
      </section>

      <section class="space-y-4">
        <div
          v-if="error"
          class="border border-destructive/20 bg-destructive/10 text-destructive text-sm rounded-lg px-4 py-3 flex items-start justify-between gap-4"
        >
          <span>{{ error }}</span>
          <button
            type="button"
            class="text-sm font-medium underline underline-offset-4"
            @click="loadAssignments(true)"
          >
            Try again
          </button>
        </div>

        <div v-if="loading" class="border border-border bg-card rounded-xl p-6 text-center">
          <p class="text-muted-foreground">Syncing Canvas assignments...</p>
        </div>

        <div
          v-if="!loading && !error && !hasAssignments"
          class="border border-border bg-card rounded-xl p-6 text-center space-y-3"
        >
          <h2 class="text-lg font-semibold text-foreground">No assignments found</h2>
          <p class="text-sm text-muted-foreground max-w-md mx-auto">
            Connect your Canvas account or refresh the sync to pull in upcoming coursework.
          </p>
        </div>

        <div v-if="hasAssignments" class="bg-card border border-border rounded-xl overflow-hidden">
          <div class="grid grid-cols-7 gap-px bg-border">
            <div
              v-for="name in dayNames"
              :key="name"
              class="bg-background/80 text-xs font-medium text-muted-foreground uppercase tracking-wide px-3 py-2 text-center"
            >
              {{ name }}
            </div>
          </div>
          <div class="grid grid-cols-7 gap-px bg-border">
            <template v-for="(week, weekIndex) in weeks" :key="weekIndex">
              <div
                v-for="date in week"
                :key="date.toISOString()"
                class="relative min-h-[110px] bg-background px-2 py-2 flex flex-col gap-1"
                :class="{
                  'opacity-70': !isSameMonth(date, currentMonth),
                  'border border-primary/40 bg-primary/5': isToday(date)
                }"
              >
                <span
                  class="text-xs font-semibold"
                  :class="isToday(date) ? 'text-primary' : 'text-muted-foreground'"
                >
                  {{ format(date, 'd') }}
                </span>
                <div class="space-y-1 overflow-y-auto pr-1 max-h-28">
                  <div
                    v-for="assignment in assignmentsForDate(date)"
                    :key="assignment.id"
                    class="rounded-lg px-2 py-1 text-xs leading-tight shadow-sm"
                    :class="courseColorMap[assignment.course_id]"
                  >
                    <p class="font-semibold text-foreground break-words">
                      {{ assignment.name }}
                    </p>
                    <p class="text-[0.7rem] text-muted-foreground">
                      {{ assignment.course_name }}
                    </p>
                    <p class="text-[0.7rem] text-muted-foreground">
                      {{ assignment.due_at_display }}
                    </p>
                  </div>
                </div>
              </div>
            </template>
          </div>
        </div>
      </section>

      <section v-if="hasAssignments" class="grid gap-6 md:grid-cols-3">
        <div
          v-for="course in coursesWithAssignments"
          :key="course.id"
          class="bg-card border border-border rounded-xl p-5 space-y-3 shadow-sm"
        >
          <div>
            <h2 class="text-lg font-semibold text-foreground">{{ course.name }}</h2>
            <p v-if="course.course_code" class="text-xs text-muted-foreground uppercase tracking-wide">
              {{ course.course_code }}
            </p>
          </div>
          <ol class="space-y-2 text-sm text-muted-foreground">
            <li
              v-for="assignment in course.assignments"
              :key="assignment.id"
              class="border border-border/60 rounded-lg px-3 py-2 bg-background/60"
            >
              <p class="text-foreground font-medium">{{ assignment.name }}</p>
              <p class="text-xs">{{ assignment.due_at_display }}</p>
            </li>
          </ol>
        </div>
      </section>
    </main>
  </div>
</template>
