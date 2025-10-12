import axios from "axios";

export const api = axios.create(); // Vite proxy handles /api -> Flask

export interface CanvasAssignment {
  id: number;
  name: string;
  description?: string | null;
  due_at: string;
  due_at_display: string;
  html_url?: string | null;
  points_possible?: number | null;
  course_id: number;
  course_name: string;
}

export interface CanvasCourseAssignments {
  id: number;
  name: string;
  course_code?: string | null;
  assignments: CanvasAssignment[];
  assignments_in_window?: number;
  earliest_due_at?: string | null;
}

export interface CanvasAssignmentsResponse {
  fetched_at: string;
  courses: CanvasCourseAssignments[];
  window?: {
    start: string;
    end: string;
    lookback_days: number;
    lookahead_days: number;
  };
}

export interface AssistantMessage {
  role: "user" | "assistant";
  content: string;
}

export interface AssistantRequestPayload {
  keywords: string[];
  question: string;
  history?: AssistantMessage[];
}

export interface AssistantResponsePayload {
  reply: string;
  model: string;
  keywords: string[];
  usage: {
    prompt_tokens: number;
    candidates_tokens: number;
    total_tokens: number;
  };
  history: AssistantMessage[];
}

export const getHealth = () => api.get("/api/health").then((r) => r.data);
export const getHello = () => api.get("/api/hello").then((r) => r.data);
export const getCanvasAssignments = () =>
  api.get<CanvasAssignmentsResponse>("/api/assignments").then((r) => r.data);
export const getAssignmentHelp = (payload: AssistantRequestPayload) =>
  api.post<AssistantResponsePayload>("/api/assistant/help", payload).then((r) => r.data);
