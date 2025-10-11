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
}

export interface CanvasAssignmentsResponse {
  fetched_at: string;
  courses: CanvasCourseAssignments[];
}

export const getHealth = () => api.get("/api/health").then((r) => r.data);
export const getHello = () => api.get("/api/hello").then((r) => r.data);
export const getCanvasAssignments = () =>
  api.get<CanvasAssignmentsResponse>("/api/assignments").then((r) => r.data);
