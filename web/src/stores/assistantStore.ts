import { computed, ref } from "vue";
import {
  getAssignmentHelp,
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

const historyForRequest = computed<AssistantMessage[]>(() =>
  messages.value.map((message) => ({
    role: message.role,
    content: message.content
  }))
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
};

const sendMessage = async (question: string) => {
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

  messages.value = [...messages.value, userMessage];
  error.value = null;
  loading.value = true;

  try {
    const payload: AssistantRequestPayload = {
      keywords,
      question: trimmedQuestion,
      history: historyForRequest.value
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
