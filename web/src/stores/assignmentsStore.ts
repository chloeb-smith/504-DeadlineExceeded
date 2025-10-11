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
const assignmentWindow = ref<CanvasAssignmentsResponse["window"] | null>(null);
const selectedCourseIds = ref<number[]>([]);
const loading = ref(false);
const error = ref<string | null>(null);

const sanitizeCourseIds = (ids: number[]) => {
  const availableIds = new Set(courses.value.map((course) => course.id));
  const uniqueIds = Array.from(new Set(ids));
  return uniqueIds.filter((id) => availableIds.has(id));
};

const setSelectedCourseIds = (ids: number[]) => {
  selectedCourseIds.value = sanitizeCourseIds(ids);
};

const selectAllCourses = () => {
  selectedCourseIds.value = courses.value.map((course) => course.id);
};

const clearCourseSelection = () => {
  selectedCourseIds.value = [];
};

const loadAssignments = async (force = false) => {
  if (loading.value || (!force && courses.value.length && error.value === null)) {
    return;
  }
  loading.value = true;
  error.value = null;
  try {
    const response: CanvasAssignmentsResponse = await getCanvasAssignments();
    const previousIds = new Set(courses.value.map((course) => course.id));
    courses.value = response.courses ?? [];
    fetchedAt.value = response.fetched_at ?? null;
    assignmentWindow.value = response.window ?? null;

    if (!courses.value.length) {
      selectedCourseIds.value = [];
    } else if (!selectedCourseIds.value.length) {
      selectAllCourses();
    } else {
      const validSelection = sanitizeCourseIds(selectedCourseIds.value);
      const newCourseIds = courses.value
        .map((course) => course.id)
        .filter((id) => !previousIds.has(id));
      selectedCourseIds.value = [...validSelection, ...newCourseIds.filter((id) => !validSelection.includes(id))];
    }
  } catch (err) {
    error.value =
      err instanceof Error ? err.message : "Failed to load assignments. Please try again.";
  } finally {
    loading.value = false;
  }
};

const selectedCourseIdSet = computed(() => new Set(selectedCourseIds.value));

const hasCourseSelection = computed(() => selectedCourseIds.value.length > 0);

const visibleCourses = computed(() => {
  if (!hasCourseSelection.value) {
    return [];
  }
  const courseSet = selectedCourseIdSet.value;
  return courses.value.filter((course) => courseSet.has(course.id));
});

const assignments = computed(() =>
  visibleCourses.value.flatMap((course) =>
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
  visibleCourses.value.map((course) => ({
    ...course,
    assignments: [...course.assignments].sort((a, b) => a.due_at.localeCompare(b.due_at))
  }))
);

const hasAssignments = computed(() => assignments.value.length > 0);

const useAssignments = () => ({
  courses,
  fetchedAt,
  assignmentWindow,
  selectedCourseIds,
  selectedCourseIdSet,
  hasCourseSelection,
  loading,
  error,
  assignments,
  assignmentsByDate,
  hasAssignments,
  coursesWithAssignments,
  loadAssignments,
  setSelectedCourseIds,
  selectAllCourses,
  clearCourseSelection
});

export default useAssignments;
