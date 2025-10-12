<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import useAssignments from "../stores/assignmentsStore";
import useAssistant from "../stores/assistantStore";

const assignmentsStore = useAssignments();
const assistantStore = useAssistant();

const {
  loadAssignments,
  assignments,
  assignmentsByDate,
  loading: assignmentsLoading,
  error: assignmentsError,
  coursesWithAssignments
} = assignmentsStore;

const {
  messages,
  selectedKeywords,
  loading: assistantLoading,
  error: assistantError,
  usage,
  lastModel,
  hasConversation,
  addKeyword,
  toggleKeyword,
  clearKeywords,
  resetConversation,
  sendMessage
} = assistantStore;

const question = ref("");
const keywordInput = ref("");

onMounted(() => {
  loadAssignments();
});

const stopWords = new Set([
  "the",
  "and",
  "for",
  "with",
  "from",
  "that",
  "this",
  "your",
  "about",
  "into",
  "using",
  "into",
  "project",
  "assignment",
  "homework",
  "task",
  "work",
  "exam",
  "quiz"
]);

const tokenize = (text: string) =>
  text
    .toLowerCase()
    .split(/[^a-z0-9+#]+/g)
    .map((token) => token.trim())
    .filter((token) => token.length > 2 && token.length < 24 && !stopWords.has(token));

const suggestedKeywords = computed(() => {
  const counts = new Map<string, number>();

  assignments.value.forEach((assignment) => {
    tokenize(assignment.name || "").forEach((token) => {
      counts.set(token, (counts.get(token) || 0) + 3);
    });
    tokenize(assignment.course_name || "").forEach((token) => {
      counts.set(token, (counts.get(token) || 0) + 1);
    });
    if (assignment.course_code) {
      tokenize(assignment.course_code).forEach((token) => {
        counts.set(token, (counts.get(token) || 0) + 2);
      });
    }
  });

  assignmentsByDate.value.forEach((dayAssignments) => {
    dayAssignments.forEach((assignment) => {
      tokenize(assignment.description || "").forEach((token) => {
        counts.set(token, (counts.get(token) || 0) + 1);
      });
    });
  });

  return Array.from(counts.entries())
    .sort((a, b) => {
      if (b[1] === a[1]) return a[0].localeCompare(b[0]);
      return b[1] - a[1];
    })
    .slice(0, 40)
    .map(([token]) => token);
});

const MAX_CONTEXT_COURSES = 4;
const MAX_CONTEXT_ASSIGNMENTS = 6;
const MAX_CONTEXT_DESCRIPTION = 360;

const stripHtml = (value: string | null | undefined) =>
  (value ?? "")
    .replace(/<[^>]*>/g, " ")
    .replace(/\s+/g, " ")
    .trim();

const summarizeText = (value: string, limit = MAX_CONTEXT_DESCRIPTION) => {
  if (!value) return "";
  return value.length > limit ? `${value.slice(0, limit).trim()}…` : value;
};

const assistantContext = computed(() => {
  const courses = coursesWithAssignments.value
    .slice(0, MAX_CONTEXT_COURSES)
    .map((course) => {
      const assignmentsList = (course.assignments ?? [])
        .slice(0, MAX_CONTEXT_ASSIGNMENTS)
        .map((assignment) => {
          const summary = summarizeText(stripHtml(assignment.description));
          return {
            id: assignment.id,
            name: assignment.name ?? "",
            due_at: assignment.due_at ?? null,
            due_at_display: assignment.due_at_display ?? null,
            course_name: assignment.course_name ?? course.name ?? "",
            course_code: assignment.course_code ?? course.course_code ?? null,
            points_possible: assignment.points_possible ?? null,
            description: summary || null
          };
        })
        .filter((assignment) => assignment.name.trim().length);

      return {
        id: course.id,
        name: course.name ?? "",
        course_code: course.course_code ?? null,
        assignments: assignmentsList
      };
    })
    .filter((course) => course.assignments.length);

  return courses.length ? { courses } : null;
});

const sortedMessages = computed(() =>
  [...messages.value].sort((a, b) => a.createdAt.localeCompare(b.createdAt))
);

const handleAddKeyword = () => {
  if (!keywordInput.value.trim()) return;
  keywordInput.value
    .split(/[,;]+/)
    .map((token) => token.trim())
    .filter(Boolean)
    .forEach((token) => addKeyword(token));
  keywordInput.value = "";
};

const handleSubmit = async () => {
  if (!question.value.trim() || assistantLoading.value) return;
  await sendMessage(question.value, assistantContext.value);
  if (!assistantError.value) {
    question.value = "";
  }
};

const handleNewChat = () => {
  resetConversation();
  question.value = "";
};

const totalTokens = computed(() => usage.value?.total_tokens ?? 0);
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
          <RouterLink to="/dashboard" class="hover:text-foreground">Dashboard</RouterLink>
          <RouterLink to="/calendar" class="hover:text-foreground">Calendar</RouterLink>
          <RouterLink to="/assistant" class="text-foreground font-medium">Assistant</RouterLink>
        </nav>
      </div>
    </header>

    <main class="container mx-auto px-4 py-10 space-y-8">
      <section class="space-y-2">
        <h1 class="text-3xl md:text-4xl font-bold text-foreground">Assignment Assistant</h1>
        <p class="text-muted-foreground max-w-2xl">
          Select the keywords that describe your current tasks, ask a question, and the Gemini powered
          assistant will suggest the next steps.
        </p>
      </section>

      <section class="grid gap-6 lg:grid-cols-[2fr,1fr]">
        <div class="bg-card border border-border rounded-xl shadow-sm flex flex-col">
          <div class="border-b border-border/60 px-6 py-4 flex items-center justify-between">
            <h2 class="text-lg font-semibold text-foreground">Conversation</h2>
            <div class="flex items-center gap-2 text-xs text-muted-foreground">
              <span v-if="lastModel">Model: {{ lastModel }}</span>
              <span v-if="totalTokens">Tokens: {{ totalTokens }}</span>
              <button
                v-if="hasConversation"
                type="button"
                class="ml-2 text-xs font-medium underline underline-offset-4"
                @click="handleNewChat"
              >
                New chat
              </button>
            </div>
          </div>
          <div class="flex-1 px-6 py-4 space-y-4 max-h-[520px] overflow-y-auto">
            <div
              v-if="assistantError"
              class="border border-destructive/20 bg-destructive/10 text-destructive text-sm rounded-lg px-4 py-3"
            >
              {{ assistantError }}
            </div>
            <div
              v-if="assignmentsError"
              class="border border-amber-500/30 bg-amber-500/10 text-amber-900 text-sm rounded-lg px-4 py-3"
            >
              {{ assignmentsError }}
            </div>
            <div v-if="!sortedMessages.length" class="text-sm text-muted-foreground pt-4">
              Select keywords on the right to give the assistant context, then ask for help planning your
              work.
            </div>
            <div
              v-for="message in sortedMessages"
              :key="message.id"
              class="flex flex-col gap-2"
              :class="message.role === 'assistant' ? 'items-start' : 'items-end'"
            >
              <div
                class="max-w-[90%] rounded-lg px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap"
                :class="
                  message.role === 'assistant'
                    ? 'bg-muted text-foreground border border-border/60'
                    : 'bg-primary text-primary-foreground'
                "
              >
                <p class="font-semibold text-xs uppercase tracking-wide mb-1">
                  {{ message.role === "assistant" ? "Assistant" : "You" }}
                </p>
                <p>{{ message.content }}</p>
                <div
                  v-if="message.keywords.length"
                  class="flex flex-wrap gap-1 mt-3"
                >
                  <span
                    v-for="keyword in message.keywords"
                    :key="keyword"
                    class="inline-flex items-center text-[0.65rem] px-2 py-0.5 rounded-full bg-background/80 border border-border/60"
                  >
                    {{ keyword }}
                  </span>
                </div>
              </div>
              <span class="text-xs text-muted-foreground">
                {{ new Date(message.createdAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) }}
              </span>
            </div>
          </div>
          <form
            class="border-t border-border/60 px-6 py-4 flex flex-col gap-3 bg-background/80"
            @submit.prevent="handleSubmit"
          >
            <label class="text-xs font-medium text-muted-foreground">
              Question or request
            </label>
            <textarea
              v-model="question"
              class="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/40 transition shadow-sm resize-none"
              rows="3"
              placeholder="Example: Help me plan the database schema assignment this week."
              :disabled="assistantLoading"
            />
            <div class="flex items-center justify-between gap-3">
              <span class="text-xs text-muted-foreground">
                {{ question.length }}/500
              </span>
              <button
                type="submit"
                class="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition disabled:opacity-60"
                :disabled="assistantLoading || !question.trim()"
              >
                {{ assistantLoading ? "Thinking..." : "Ask assistant" }}
              </button>
            </div>
          </form>
        </div>

        <aside class="space-y-6">
          <div class="bg-card border border-border rounded-xl shadow-sm p-6 space-y-4">
            <div class="flex items-center justify-between gap-3">
              <div>
                <h2 class="text-lg font-semibold text-foreground">Keywords</h2>
                <p class="text-xs text-muted-foreground">
                  Provide up to 25 keywords for the assistant to reference.
                </p>
              </div>
              <button
                type="button"
                class="text-xs font-medium text-muted-foreground underline underline-offset-4"
                @click="clearKeywords"
              >
                Clear
              </button>
            </div>

            <div class="flex flex-wrap gap-2">
              <span
                v-if="!selectedKeywords.length"
                class="text-xs text-muted-foreground"
              >
                No keywords selected yet.
              </span>
              <span
                v-for="keyword in selectedKeywords"
                :key="keyword"
                class="inline-flex items-center gap-1 text-xs px-2 py-1 bg-primary/10 text-foreground border border-primary/40 rounded-full"
              >
                {{ keyword }}
                <button
                  type="button"
                  class="h-4 w-4 flex items-center justify-center rounded-full bg-primary/20 hover:bg-primary/40 transition"
                  @click="toggleKeyword(keyword)"
                  aria-label="Remove keyword"
                >
                  ×
                </button>
              </span>
            </div>

            <div class="space-y-2">
              <label class="text-xs font-medium text-muted-foreground">
                Add custom keyword
              </label>
              <div class="flex gap-2">
                <input
                  v-model="keywordInput"
                  type="text"
                  class="flex-1 rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/40 transition shadow-sm"
                  placeholder="e.g. normalization, recursive functions"
                  @keydown.enter.prevent="handleAddKeyword"
                />
                <button
                  type="button"
                  class="px-3 py-2 rounded-lg border border-border text-sm text-muted-foreground hover:text-foreground transition"
                  @click="handleAddKeyword"
                >
                  Add
                </button>
              </div>
            </div>

            <div class="space-y-2">
              <p class="text-xs font-medium text-muted-foreground">Suggested keywords</p>
              <div class="flex flex-wrap gap-2 max-h-48 overflow-y-auto pr-1">
                <button
                  v-for="keyword in suggestedKeywords"
                  :key="keyword"
                  type="button"
                  class="px-3 py-1.5 rounded-full border text-xs transition"
                  :class="
                    selectedKeywords.includes(keyword)
                      ? 'border-primary bg-primary/10 text-foreground font-medium'
                      : 'border-border text-muted-foreground hover:text-foreground'
                  "
                  @click="toggleKeyword(keyword)"
                >
                  {{ keyword }}
                </button>
                <span v-if="!suggestedKeywords.length" class="text-xs text-muted-foreground">
                  Load assignments to get keyword suggestions.
                </span>
              </div>
            </div>
          </div>

          <div class="bg-card border border-border rounded-xl shadow-sm p-6 space-y-3 text-sm">
            <h3 class="text-sm font-semibold text-foreground">Status</h3>
            <div class="flex items-center justify-between">
              <span class="text-muted-foreground">Assignments</span>
              <span class="font-medium text-foreground">
                {{ assignmentsLoading ? "Syncing..." : `${assignments.length} loaded` }}
              </span>
            </div>
            <div class="flex items-center justify-between">
              <span class="text-muted-foreground">Assistant</span>
              <span class="font-medium text-foreground">
                {{ assistantLoading ? "Thinking..." : hasConversation ? "Ready" : "Waiting" }}
              </span>
            </div>
            <div v-if="usage" class="flex items-center justify-between">
              <span class="text-muted-foreground">Last tokens</span>
              <span class="font-medium text-foreground">{{ usage.total_tokens }}</span>
            </div>
          </div>
        </aside>
      </section>
    </main>
  </div>
</template>
