import { computed, ref } from "vue";
import {
  getCanvasAssignments,
  type CanvasAssignmentsResponse,
  type CanvasCourseAssignments,
  type CanvasAssignment
} from "../api";

export type CourseAssignmentsMap = Map<
  string,
  Array<CanvasAssignment & { course_code?: string | null }>
>;

const courses = ref<CanvasCourseAssignments[]>([]);
const fetchedAt = ref<string | null>(null);
const loading = ref(false);
const error = ref<string | null>(null);

const loadAssignments = async (force = false) => {
  if (loading.value || (!force && courses.value.length && error.value === null)) {
    return;
  }
  loading.value = true;
  error.value = null;
  try {
    const response: CanvasAssignmentsResponse = await getCanvasAssignments();
    courses.value = response.courses ?? [];
    fetchedAt.value = response.fetched_at ?? null;
  } catch (err) {
    error.value =
      err instanceof Error ? err.message : "Failed to load assignments. Please try again.";
  } finally {
    loading.value = false;
  }
};

const assignments = computed(() =>
  courses.value.flatMap((course) =>
    course.assignments.map((assignment) => ({
      ...assignment,
      course_code: course.course_code
    }))
  )
);

const assignmentsByDate = computed<CourseAssignmentsMap>(() => {
  const map: CourseAssignmentsMap = new Map();
  assignments.value.forEach((assignment) => {
    const dateKey = assignment.due_at ? assignment.due_at.split("T")[0] : "undated";
    const existing = map.get(dateKey) ?? [];
    existing.push(assignment);
    map.set(dateKey, existing);
  });

  // Sort assignments within each date by course then by due time
  map.forEach((items) => {
    items.sort((a, b) => {
      if (a.course_name === b.course_name) {
        return a.due_at.localeCompare(b.due_at);
      }
      return a.course_name.localeCompare(b.course_name);
    });
  });

  return map;
});

const coursesWithAssignments = computed(() =>
  courses.value.map((course) => ({
    ...course,
    assignments: [...course.assignments].sort((a, b) => a.due_at.localeCompare(b.due_at))
  }))
);

const hasAssignments = computed(() => assignments.value.length > 0);

const useAssignments = () => ({
  courses,
  fetchedAt,
  loading,
  error,
  assignments,
  assignmentsByDate,
  hasAssignments,
  coursesWithAssignments,
  loadAssignments
});

export default useAssignments;
