<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRouter, RouterLink } from "vue-router";
import useAuth from "../stores/authStore";
import useAssignments from "../stores/assignmentsStore";

const router = useRouter();
const { currentUser, displayName, signOut } = useAuth();
const assignmentsStore = useAssignments();
const {
  loadAssignments,
  assignments,
  coursesWithAssignments,
  courses,
  selectedCourseIds,
  hasCourseSelection,
  selectAllCourses,
  clearCourseSelection,
  setSelectedCourseIds,
  loading: assignmentsLoading,
  error: assignmentsError
} = assignmentsStore;

onMounted(() => {
  loadAssignments();
});

const welcomeLabel = computed(() => {
  if (!currentUser.value) return "Guest";
  return displayName.value ?? currentUser.value.email;
});

const handleSignOut = async () => {
  await signOut();
  router.push("/");
};

const topAssignments = computed(() =>
  [...assignments.value]
    .sort((a, b) => a.due_at.localeCompare(b.due_at))
    .slice(0, 5)
);

const courseSummaries = computed(() =>
  coursesWithAssignments.value.map((course) => ({
    id: course.id,
    name: course.name,
    courseCode: course.course_code,
    total: course.assignments.length,
    nextDue: course.assignments[0]?.due_at_display ?? "No upcoming work"
  }))
);

const courseSelectionOptions = computed(() =>
  courses.value.map((course) => ({
    id: course.id,
    name: course.name ?? "Untitled course",
    courseCode: course.course_code,
    assignmentsInWindow: course.assignments_in_window ?? course.assignments.length,
    hasAssignments: (course.assignments_in_window ?? course.assignments.length) > 0
  }))
);

const selectedCourseIdsModel = computed<number[]>({
  get: () => selectedCourseIds.value,
  set: (value) => setSelectedCourseIds(value)
});

const totalCourses = computed(() => courses.value.length);
const selectedCourseCount = computed(() => selectedCourseIds.value.length);

const showCourseFilter = ref(false);

const toggleCourseFilter = () => {
  showCourseFilter.value = !showCourseFilter.value;
};

const handleSelectAllCourses = () => {
  selectAllCourses();
};

const handleClearCourseSelection = () => {
  clearCourseSelection();
};

watch(hasCourseSelection, (value) => {
  if (!value && totalCourses.value > 0) {
    showCourseFilter.value = true;
  }
});
</script>

<template>
  <div class="min-h-screen bg-background">
    <header
      class="border-b border-border/40 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60"
    >
      <div class="container mx-auto px-4 py-4 flex items-center justify-between gap-6">
        <RouterLink to="/" class="flex items-center gap-2 font-semibold text-lg text-foreground">
          <div class="w-8 h-8 bg-primary rounded-lg flex items-center justify-center">
            <span class="text-primary-foreground font-bold">5</span>
          </div>
          <span>504: Deadline Exceeded</span>
        </RouterLink>
        <nav class="flex items-center gap-4 text-sm text-muted-foreground">
          <RouterLink to="/dashboard" class="text-foreground font-medium">Dashboard</RouterLink>
          <RouterLink to="/calendar" class="hover:text-foreground">Calendar</RouterLink>
          <RouterLink to="/assistant" class="hover:text-foreground">Assistant</RouterLink>
        </nav>
        <div class="flex items-center gap-3">
          <span class="text-sm text-muted-foreground hidden sm:inline">
            Signed in as <span class="text-foreground font-medium">{{ welcomeLabel }}</span>
          </span>
          <button
            type="button"
            @click="handleSignOut"
            class="px-4 py-2 bg-secondary text-secondary-foreground rounded-lg hover:bg-secondary/80 transition-colors text-sm font-medium"
          >
            Sign Out
          </button>
        </div>
      </div>
    </header>

    <main class="container mx-auto px-4 py-16 space-y-10">
      <div class="space-y-2">
        <h1 class="text-4xl font-bold text-foreground">Welcome back, {{ welcomeLabel }}!</h1>
        <p class="text-muted-foreground">
          Stay ahead by reviewing your upcoming Canvas deadlines and exploring the planner calendar.
        </p>
      </div>

      <section class="grid gap-6 lg:grid-cols-[2fr,1fr]">
        <div class="bg-card border border-border rounded-xl p-6 shadow-sm space-y-4">
          <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div class="space-y-1">
              <h2 class="text-xl font-semibold text-foreground">Upcoming assignments</h2>
              <p class="text-sm text-muted-foreground">
                Ordered by due date. Keep an eye on what needs your attention next.
              </p>
            </div>
            <div class="flex items-center gap-2">
              <button
                type="button"
                class="px-3 py-2 rounded-lg border border-border text-xs sm:text-sm text-muted-foreground hover:text-foreground transition-colors"
                :disabled="assignmentsLoading"
                @click="loadAssignments(true)"
              >
                {{ assignmentsLoading ? "Refreshing..." : "Refresh" }}
              </button>
              <RouterLink
                to="/calendar"
                class="px-3 py-2 rounded-lg bg-primary text-primary-foreground text-xs sm:text-sm font-medium hover:bg-primary/90 transition-colors"
              >
                Open Calendar
              </RouterLink>
            </div>
          </div>

          <div
            v-if="courseSelectionOptions.length"
            class="border border-border/60 bg-background/50 rounded-lg px-4 py-3 space-y-3"
          >
            <button
              type="button"
              class="w-full flex items-center justify-between gap-3 text-left"
              @click="toggleCourseFilter"
            >
              <div class="flex flex-col">
                <span class="text-sm font-medium text-foreground">Filter classes</span>
                <span class="text-xs text-muted-foreground">
                  {{ selectedCourseCount }} of {{ totalCourses }} selected
                </span>
              </div>
              <span
                class="text-xs font-medium px-2 py-1 rounded-md border border-border text-muted-foreground"
              >
                {{ showCourseFilter ? "Hide" : "Show" }}
              </span>
            </button>
            <Transition name="fade">
              <div
                v-if="showCourseFilter"
                class="space-y-3 border-t border-border/60 pt-3"
              >
                <div class="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                  <p class="text-sm text-muted-foreground">
                    Select the classes you want included in the dashboard.
                  </p>
                  <div class="flex items-center gap-2">
                    <button
                      type="button"
                      class="px-3 py-1.5 rounded-md border border-border text-xs font-medium text-muted-foreground hover:text-foreground transition-colors disabled:opacity-50"
                      :disabled="assignmentsLoading"
                      @click="handleSelectAllCourses"
                    >
                      Select all
                    </button>
                    <button
                      type="button"
                      class="px-3 py-1.5 rounded-md border border-border text-xs font-medium text-muted-foreground hover:text-foreground transition-colors disabled:opacity-50"
                      :disabled="!hasCourseSelection || assignmentsLoading"
                      @click="handleClearCourseSelection"
                    >
                      Clear
                    </button>
                  </div>
                </div>
                <div class="flex flex-wrap gap-2">
                  <label
                    v-for="course in courseSelectionOptions"
                    :key="course.id"
                    class="cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      class="sr-only"
                      :value="course.id"
                      v-model="selectedCourseIdsModel"
                    />
                    <span
                      class="inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-xs sm:text-sm transition-colors"
                      :class="
                        selectedCourseIdsModel.includes(course.id)
                          ? 'bg-primary/10 border-primary/60 text-foreground font-medium'
                          : 'bg-background border-border text-muted-foreground hover:text-foreground'
                      "
                    >
                      <span class="truncate max-w-[11rem] sm:max-w-[14rem]">
                        {{ course.name }}
                        <template v-if="course.courseCode">
                          <span class="text-[0.65rem] text-muted-foreground uppercase">
                            ({{ course.courseCode }})
                          </span>
                        </template>
                      </span>
                      <span
                        v-if="course.assignmentsInWindow"
                        class="text-[0.65rem] px-2 py-0.5 rounded-full bg-primary/20 text-primary-foreground/90 font-semibold whitespace-nowrap"
                      >
                        {{ course.assignmentsInWindow }}
                      </span>
                    </span>
                  </label>
                </div>
              </div>
            </Transition>
          </div>

          <div
            v-if="assignmentsError"
            class="border border-destructive/20 bg-destructive/10 text-destructive text-sm rounded-lg px-4 py-3 flex items-start justify-between gap-3"
          >
            <span>{{ assignmentsError }}</span>
            <button
              type="button"
              class="text-sm font-medium underline underline-offset-4"
              @click="loadAssignments(true)"
            >
              Try again
            </button>
          </div>

          <div
            v-else-if="assignmentsLoading && !topAssignments.length"
            class="border border-border bg-background/60 rounded-lg px-4 py-6 text-center text-sm text-muted-foreground"
          >
            Syncing assignments from Canvas...
          </div>

          <div
            v-else-if="!hasCourseSelection"
            class="border border-border bg-background/60 rounded-lg px-4 py-6 text-center text-sm text-muted-foreground"
          >
            Choose at least one class above to see its upcoming assignments here.
          </div>

          <ul
            v-else-if="topAssignments.length"
            class="space-y-3"
          >
            <li
              v-for="assignment in topAssignments"
              :key="assignment.id"
              class="border border-border rounded-lg px-4 py-3 bg-background/60 space-y-2"
            >
              <div class="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <p class="text-foreground font-medium">{{ assignment.name }}</p>
                  <p class="text-xs text-muted-foreground">
                    {{ assignment.course_name }}
                  </p>
                </div>
                <span class="text-xs text-muted-foreground whitespace-nowrap">
                  {{ assignment.due_at_display }}
                </span>
              </div>
              <a
                v-if="assignment.html_url"
                :href="assignment.html_url"
                target="_blank"
                rel="noopener noreferrer"
                class="inline-flex items-center text-xs font-medium text-primary hover:underline underline-offset-4"
              >
                Open in Canvas
              </a>
            </li>
          </ul>

          <div
            v-else
            class="border border-border bg-background/60 rounded-lg px-4 py-6 text-center text-sm text-muted-foreground"
          >
            No upcoming assignments detected for the selected classes. Try syncing again or adjust
            your selection.
          </div>
        </div>

        <div class="bg-card border border-border rounded-xl p-6 shadow-sm space-y-4">
          <div class="space-y-1">
            <h2 class="text-xl font-semibold text-foreground">By class</h2>
            <p class="text-sm text-muted-foreground">
              Total number of upcoming assignments grouped by each course.
            </p>
          </div>

          <div
            v-if="!hasCourseSelection"
            class="border border-border bg-background/60 rounded-lg px-4 py-6 text-center text-sm text-muted-foreground"
          >
            Pick one or more classes to see their assignment summary.
          </div>

          <ul v-else-if="courseSummaries.length" class="space-y-3">
            <li
              v-for="course in courseSummaries"
              :key="course.id"
              class="border border-border/60 rounded-lg px-4 py-3 bg-background/60"
            >
              <div class="flex items-start justify-between gap-3">
                <div>
                  <p class="text-foreground font-medium">{{ course.name }}</p>
                  <p v-if="course.courseCode" class="text-xs text-muted-foreground uppercase">
                    {{ course.courseCode }}
                  </p>
                </div>
                <span class="text-xs font-semibold text-primary">
                  {{ course.total }} task{{ course.total === 1 ? "" : "s" }}
                </span>
              </div>
              <p class="text-xs text-muted-foreground">
                Next due: {{ course.nextDue }}
              </p>
            </li>
          </ul>

          <div
            v-else
            class="border border-border bg-background/60 rounded-lg px-4 py-6 text-center text-sm text-muted-foreground"
          >
            No assignments found for the selected classes in the current window. Try syncing again or
            adjust your selection.
          </div>
        </div>
      </section>
    </main>
  </div>
</template>
