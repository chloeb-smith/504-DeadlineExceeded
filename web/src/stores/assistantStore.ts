import { computed, ref } from "vue";
import {
  getAssignmentHelp,
  type AssistantContext,
  type AssistantMessage,
  type AssistantRequestPayload,
  type AssistantResponsePayload
} from "../api";

export type ChatMessageRole = "user" | "assistant";

export interface ChatMessage {
  id: string;
  role: ChatMessageRole;
  content: string;
  keywords: string[];
  createdAt: string;
  usage?: AssistantResponsePayload["usage"];
}

const messages = ref<ChatMessage[]>([]);
const selectedKeywords = ref<string[]>([]);
const loading = ref(false);
const error = ref<string | null>(null);
const lastModel = ref<string | null>(null);
const usage = ref<AssistantResponsePayload["usage"] | null>(null);

const makeId = () =>
  typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : Math.random().toString(36).slice(2);

const normalizeKeywords = (keywords: string[]) =>
  Array.from(
    new Set(
      keywords
        .map((keyword) => keyword.trim())
        .filter((keyword) => keyword.length && keyword.length < 120)
    )
  ).slice(0, 25);

const mapMessagesToHistory = (items: ChatMessage[]): AssistantMessage[] =>
  items.map((message) => ({
    role: message.role,
    content: message.content
  }));

const historyForRequest = computed<AssistantMessage[]>(() =>
  mapMessagesToHistory(messages.value)
);

const setSelectedKeywords = (keywords: string[]) => {
  selectedKeywords.value = normalizeKeywords(keywords);
};

const addKeyword = (keyword: string) => {
  const normalized = normalizeKeywords([keyword]);
  if (!normalized.length) return;
  const existing = new Set(selectedKeywords.value);
  normalized.forEach((item) => existing.add(item));
  selectedKeywords.value = Array.from(existing);
};

const toggleKeyword = (keyword: string) => {
  const trimmed = keyword.trim();
  if (!trimmed) return;
  if (selectedKeywords.value.includes(trimmed)) {
    selectedKeywords.value = selectedKeywords.value.filter((item) => item !== trimmed);
  } else {
    selectedKeywords.value = normalizeKeywords([...selectedKeywords.value, trimmed]);
  }
};

const clearKeywords = () => {
  selectedKeywords.value = [];
};

const resetConversation = () => {
  messages.value = [];
  usage.value = null;
  error.value = null;
  lastModel.value = null;
  loading.value = false;
};

const sanitizeContext = (context?: AssistantContext | null): AssistantRequestPayload["context"] => {
  if (!context?.courses?.length) {
    return undefined;
  }

  const clampDescription = (value: unknown): string | null => {
    if (typeof value !== "string") return null;
    const normalized = value.trim();
    if (!normalized) return null;
    return normalized.length > 360 ? `${normalized.slice(0, 360).trim()}...` : normalized;
  };

  const sanitizeMilestones = (milestones: unknown) => {
    if (!Array.isArray(milestones)) {
      return [];
    }
    return milestones
      .filter((item) => item && typeof item === "object")
      .slice(0, 4)
      .map((milestone) => ({
        name: String((milestone as Record<string, unknown>).name ?? "").trim(),
        due_by:
          typeof (milestone as Record<string, unknown>).due_by === "string" &&
          ((milestone as Record<string, unknown>).due_by as string).trim().length
            ? ((milestone as Record<string, unknown>).due_by as string).trim()
            : null,
        notes:
          typeof (milestone as Record<string, unknown>).notes === "string" &&
          ((milestone as Record<string, unknown>).notes as string).trim().length
            ? ((milestone as Record<string, unknown>).notes as string).trim()
            : null
      }))
      .filter((milestone) => milestone.name.length);
  };

  const courses = context.courses
    .filter((course) => course && typeof course === "object")
    .slice(0, 5)
    .map((course) => ({
      id: course.id,
      name: course.name,
      course_code: course.course_code ?? null,
      assignments: (course.assignments ?? [])
        .filter((assignment) => assignment && typeof assignment === "object")
        .slice(0, 6)
        .map((assignment) => ({
          id: assignment.id,
          name: assignment.name,
          due_at: assignment.due_at ?? null,
          due_at_display: assignment.due_at_display ?? null,
          course_name: assignment.course_name ?? null,
          course_code: assignment.course_code ?? null,
          points_possible: assignment.points_possible ?? null,
          description: clampDescription(assignment.description ?? null),
          priority_score:
            typeof assignment.priority_score === "number" ? assignment.priority_score : null,
          priority_label: assignment.priority_label ?? null,
          priority_rationale: assignment.priority_rationale ?? null,
          suggested_milestones: sanitizeMilestones(assignment.suggested_milestones)
        }))
    }))
    .filter((course) => course.assignments.length || course.name?.trim());
  if (!courses.length) {
    return undefined;
  }

  return { courses };
};

const sendMessage = async (question: string, context?: AssistantContext | null) => {
  const trimmedQuestion = question.trim();
  if (!trimmedQuestion) {
    error.value = "Please enter a question.";
    return;
  }

  const keywords = normalizeKeywords(selectedKeywords.value);
  const now = new Date().toISOString();
  const userMessage: ChatMessage = {
    id: makeId(),
    role: "user",
    content: trimmedQuestion,
    keywords,
    createdAt: now
  };

  const history = mapMessagesToHistory(messages.value);
  messages.value = [...messages.value, userMessage];
  error.value = null;
  loading.value = true;

  try {
    const payload: AssistantRequestPayload = {
      keywords,
      question: trimmedQuestion,
      history,
      context: sanitizeContext(context)
    };
    const response = await getAssignmentHelp(payload);
    const assistantMessage: ChatMessage = {
      id: makeId(),
      role: "assistant",
      content: response.reply,
      keywords: response.keywords,
      createdAt: new Date().toISOString(),
      usage: response.usage
    };
    messages.value = [...messages.value, assistantMessage];
    usage.value = response.usage;
    lastModel.value = response.model;
  } catch (err) {
    error.value =
      err instanceof Error ? err.message : "Unable to contact the assignment assistant right now.";
    // Remove the user's latest message so they can retry with edits.
    messages.value = messages.value.slice(0, -1);
  } finally {
    loading.value = false;
  }
};

const hasConversation = computed(() => messages.value.length > 0);

const useAssistant = () => ({
  messages,
  selectedKeywords,
  loading,
  error,
  usage,
  lastModel,
  hasConversation,
  historyForRequest,
  setSelectedKeywords,
  addKeyword,
  toggleKeyword,
  clearKeywords,
  resetConversation,
  sendMessage
});

export default useAssistant;
