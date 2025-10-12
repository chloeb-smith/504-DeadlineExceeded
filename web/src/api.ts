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

export interface AssistantContextCourseAssignment {
  id: number;
  name: string;
  due_at?: string | null;
  due_at_display?: string | null;
  course_name?: string | null;
  course_code?: string | null;
  points_possible?: number | null;
  description?: string | null;
}

export interface AssistantContextCourse {
  id: number;
  name: string;
  course_code?: string | null;
  assignments: AssistantContextCourseAssignment[];
}

export interface AssistantContext {
  courses: AssistantContextCourse[];
}

export interface AssistantRequestPayload {
  keywords: string[];
  question: string;
  history?: AssistantMessage[];
  context?: AssistantContext;
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
export const getCanvasAssignments = (force = false) =>
  api
    .get<CanvasAssignmentsResponse>("/api/assignments", {
      params: force ? { force: "1" } : undefined
    })
    .then((r) => r.data);
export const getAssignmentHelp = (payload: AssistantRequestPayload) =>
  api.post<AssistantResponsePayload>("/api/assistant/help", payload).then((r) => r.data);
