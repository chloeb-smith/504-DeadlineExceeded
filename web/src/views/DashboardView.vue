<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRouter, RouterLink } from "vue-router";
import type { CanvasAssignment } from "../api";
import useAuth from "../stores/authStore";
import useAssignments from "../stores/assignmentsStore";
import useAssistant from "../stores/assistantStore";
import AppHeader from "../components/AppHeader.vue";
const router = useRouter();
const { currentUser, displayName } = useAuth();
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
  error: assignmentsError,
  analysisGeneratedAt,
  analysisError
} = assignmentsStore;
const assistantStore = useAssistant();
const assistantBusy = computed(() => assistantStore.loading.value);
onMounted(() => {
  loadAssignments();
});
const welcomeLabel = computed(() => {
  if (!currentUser.value) return "Guest";
  return displayName.value ?? currentUser.value.email;
});
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
const analysisStatus = computed(() =>
  analysisError.value ? "Unavailable" : analysisGeneratedAt.value ? "Updated" : "Pending"
);
const analysisTimestamp = computed(() => {
  if (!analysisGeneratedAt.value) return null;
  const timestamp = new Date(analysisGeneratedAt.value);
  if (Number.isNaN(timestamp.getTime())) return null;
  return timestamp.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
});
const priorityLabelDisplay = (assignment: CanvasAssignment) => {
  if (assignment.priority_label) return assignment.priority_label;
  if (typeof assignment.priority_score === "number") {
    if (assignment.priority_score >= 80) return "High";
    if (assignment.priority_score >= 50) return "Medium";
    return "Low";
  }
  return null;
};
const priorityBadgeClass = (assignment: CanvasAssignment) => {
  const label = (priorityLabelDisplay(assignment) || "").toLowerCase();
  if (label === "critical" || label === "high") {
    return "bg-red-500/10 text-red-600 border border-red-500/30";
  }
  if (label === "medium") {
    return "bg-amber-500/10 text-amber-600 border border-amber-500/30";
  }
  return "bg-emerald-500/10 text-emerald-600 border border-emerald-500/30";
};
const hasMilestones = (assignment: CanvasAssignment) =>
  Array.isArray(assignment.suggested_milestones) && assignment.suggested_milestones.length > 0;
const formatMilestoneDate = (value: string | null | undefined) => {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
};
const expandedAssignments = ref<Set<number>>(new Set());
const MAX_ASSIGNMENT_DESCRIPTION = 800;
const plainTextDescription = (raw: string | null | undefined): string =>
  (raw ?? "")
    .replace(/<[^>]*>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
const describeAssignment = (assignment: CanvasAssignment): string => {
  const description = plainTextDescription(assignment.description);
  if (!description) return "";
  if (description.length <= MAX_ASSIGNMENT_DESCRIPTION) {
    return description;
  }
  return `${description.slice(0, MAX_ASSIGNMENT_DESCRIPTION).trim()}...`;
};
const hasAssignmentDescription = (assignment: CanvasAssignment) =>
  describeAssignment(assignment).length > 0;
const isAssignmentExpanded = (assignmentId: number) =>
  expandedAssignments.value.has(assignmentId);
const toggleAssignmentDetails = (assignmentId: number) => {
  const updated = new Set(expandedAssignments.value);
  if (updated.has(assignmentId)) {
    updated.delete(assignmentId);
  } else {
    updated.add(assignmentId);
  }
  expandedAssignments.value = updated;
};
watch(assignments, () => {
  expandedAssignments.value = new Set();
});
const buildAssignmentContext = (assignment: CanvasAssignment) => {
  const milestones = Array.isArray(assignment.suggested_milestones)
    ? assignment.suggested_milestones
        .filter((milestone) => milestone && typeof milestone === "object")
        .slice(0, 4)
        .map((milestone) => ({
          name: String(milestone.name ?? "").trim(),
          due_by:
            typeof milestone.due_by === "string" && milestone.due_by.trim().length
              ? milestone.due_by.trim()
              : null,
          notes:
            typeof milestone.notes === "string" && milestone.notes.trim().length
              ? milestone.notes.trim()
              : null
        }))
        .filter((milestone) => milestone.name.length)
    : [];
  return {
    courses: [
      {
        id: assignment.course_id,
        name: assignment.course_name ?? "Course",
        course_code: assignment.course_code ?? null,
        assignments: [
          {
            id: assignment.id,
            name: assignment.name ?? "",
            due_at: assignment.due_at ?? null,
            due_at_display: assignment.due_at_display ?? null,
            course_name: assignment.course_name ?? null,
            course_code: assignment.course_code ?? null,
            points_possible: assignment.points_possible ?? null,
            description: plainTextDescription(assignment.description),
            priority_score:
              typeof assignment.priority_score === "number" ? assignment.priority_score : null,
            priority_label: assignment.priority_label ?? null,
            priority_rationale: assignment.priority_rationale ?? null,
            suggested_milestones: milestones
          }
        ]
      }
    ]
  };
};
const requestAssistantHelp = async (assignment: CanvasAssignment) => {
  if (assistantStore.loading.value) {
    return;
  }
  const description = plainTextDescription(assignment.description);
  const keywords = [
    assignment.course_name ?? "",
    assignment.course_code ?? "",
    assignment.name ?? ""
  ].filter(Boolean);
  assistantStore.resetConversation();
  if (keywords.length) {
    assistantStore.setSelectedKeywords(keywords);
  } else {
    assistantStore.clearKeywords();
  }
  const milestoneLines = Array.isArray(assignment.suggested_milestones)
    ? assignment.suggested_milestones
        .filter((milestone) => milestone && typeof milestone === "object")
        .map((milestone) => {
          const name = String(milestone.name ?? "").trim();
          if (!name.length) return null;
          const due = milestone.due_by ? ` (due by ${milestone.due_by})` : "";
          const notes = milestone.notes ? ` - ${milestone.notes}` : "";
          return `- ${name}${due}${notes}`;
        })
        .filter((line): line is string => Boolean(line))
        .join("\n")
    : "";
  const questionSections = [
    `Please help me plan the assignment "${assignment.name ?? "Unnamed Assignment"}".`,
    assignment.due_at_display ? `Due date: ${assignment.due_at_display}.` : null,
    description
      ? `Full assignment description:\n${description}`
      : "No additional assignment description was provided.",
    assignment.priority_label || typeof assignment.priority_score === "number"
      ? `Priority data: ${assignment.priority_label ?? ""}${
          typeof assignment.priority_score === "number" ? ` (score ${assignment.priority_score})` : ""
        }.`
      : null,
    assignment.priority_rationale ? `Priority rationale: ${assignment.priority_rationale}` : null,
    milestoneLines ? `Suggested milestones:\n${milestoneLines}` : null,
    "Provide a comprehensive response with sections for Summary, Step-by-step Plan, Recommended Resources, Risks & Reminders, and Next Actions tailored to this assignment."
  ].filter(Boolean);
  const question = questionSections.join("\n\n");
  const context = buildAssignmentContext(assignment);
  await router.push("/assistant");
  try {
    await assistantStore.sendMessage(question, context);
  } catch (error) {
    console.error("Failed to request assistant help", error);
  }
};
</script>
<template>
  <div class="min-h-screen bg-background">
    <AppHeader />
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
                <div class="flex-1">
                  <p class="text-foreground font-medium">{{ assignment.name }}</p>
                  <p class="text-xs text-muted-foreground">
                    {{ assignment.course_name }}
                  </p>
                </div>
                <div class="flex items-center gap-2">
                  <span class="text-xs text-muted-foreground whitespace-nowrap">
                    {{ assignment.due_at_display }}
                  </span>
                  <button
                    v-if="hasAssignmentDescription(assignment)"
                    type="button"
                    class="text-xs font-medium text-primary hover:underline underline-offset-4"
                    @click="toggleAssignmentDetails(assignment.id)"
                  >
                    {{ isAssignmentExpanded(assignment.id) ? "Hide details" : "Show details" }}
                  </button>
                </div>
              </div>
              <div
                v-if="assignment.priority_label || typeof assignment.priority_score === 'number'"
                class="flex flex-col gap-1 text-xs text-muted-foreground mt-1"
              >
                <div class="flex items-center gap-2">
                  <span class="font-semibold text-foreground/80">Priority</span>
                  <span
                    class="inline-flex items-center px-2 py-0.5 rounded-full border text-[11px]"
                    :class="priorityBadgeClass(assignment)"
                  >
                    {{ priorityLabelDisplay(assignment) }}
                  </span>
                  <span v-if="typeof assignment.priority_score === 'number'" class="text-muted-foreground">
                    {{ assignment.priority_score }}
                  </span>
                </div>
                <p v-if="assignment.priority_rationale" class="text-muted-foreground">
                  {{ assignment.priority_rationale }}
                </p>
              </div>
              <Transition name="fade">
                <div
                  v-if="isAssignmentExpanded(assignment.id) && hasAssignmentDescription(assignment)"
                  class="text-xs text-muted-foreground bg-secondary/20 border border-border/60 rounded-lg px-3 py-2 leading-relaxed"
                >
                  {{ describeAssignment(assignment) }}
                </div>
              </Transition>
              <div v-if="hasMilestones(assignment)" class="text-xs text-muted-foreground space-y-1 mt-2">
                <p class="font-semibold text-foreground/80">Suggested milestones</p>
                <ul class="space-y-1">
                  <li
                    v-for="milestone in assignment.suggested_milestones"
                    :key="`${assignment.id}-${milestone.name}-${milestone.due_by ?? ''}`"
                    class="flex flex-col sm:flex-row sm:items-baseline sm:gap-2"
                  >
                    <span class="font-medium text-foreground">{{ milestone.name }}</span>
                    <span v-if="milestone.due_by" class="text-muted-foreground">
                      due by {{ formatMilestoneDate(milestone.due_by) ?? milestone.due_by }}
                    </span>
                    <span v-if="milestone.notes" class="text-muted-foreground">
                      - {{ milestone.notes }}
                    </span>
                  </li>
                </ul>
              </div>
              <div class="flex flex-wrap items-center gap-2">
                <a
                  v-if="assignment.html_url"
                  :href="assignment.html_url"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="inline-flex items-center text-xs font-medium text-primary hover:underline underline-offset-4"
                >
                  Open in Canvas
                </a>
                <button
                  type="button"
                  class="inline-flex items-center gap-2 text-xs font-medium px-3 py-1.5 rounded-full border border-primary/60 text-primary hover:bg-primary/10 transition disabled:opacity-60"
                  :disabled="assistantBusy"
                  @click="requestAssistantHelp(assignment)"
                >
                  {{ assistantBusy ? "Assistant busy..." : "Ask AI for help" }}
                </button>
              </div>
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
        <div class="space-y-4">
          <div class="bg-card border border-border rounded-xl shadow-sm p-6 space-y-3 text-sm">
            <h3 class="text-sm font-semibold text-foreground">Status</h3>
            <div class="flex items-center justify-between">
              <span class="text-muted-foreground">AI Priority</span>
              <span class="font-medium text-foreground">{{ analysisStatus }}</span>
            </div>
            <p v-if="analysisTimestamp && !analysisError" class="text-[11px] text-muted-foreground">
              Updated {{ analysisTimestamp }}
            </p>
            <p v-if="analysisError" class="text-[11px] text-amber-600">
              {{ analysisError }}
            </p>
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
      </div>
      </section>
    </main>
  </div>
</template>
