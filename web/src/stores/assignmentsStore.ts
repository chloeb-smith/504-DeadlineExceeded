import { computed, ref } from "vue";
import {
  getCanvasAssignments,
  type CanvasAssignmentsResponse,
  type CanvasCourseAssignments,
  type CanvasAssignment,
  type AssignmentPriorityInsight
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
const analysisGeneratedAt = ref<string | null>(null);
const analysisError = ref<string | null>(null);
const assignmentInsights = ref<Record<number, AssignmentPriorityInsight>>({});

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
  analysisError.value = null;
  try {
    const response: CanvasAssignmentsResponse = await getCanvasAssignments(force);
    const previousIds = new Set(courses.value.map((course) => course.id));
    courses.value = response.courses ?? [];
    fetchedAt.value = response.fetched_at ?? null;
    assignmentWindow.value = response.window ?? null;

    const insightsRecord: Record<number, AssignmentPriorityInsight> = {};
    for (const insight of response.analysis?.assignments ?? []) {
      if (!insight || typeof insight !== "object") {
        continue;
      }
      const assignmentId = (insight as AssignmentPriorityInsight).id;
      if (typeof assignmentId !== "number") {
        continue;
      }
      insightsRecord[assignmentId] = {
        id: assignmentId,
        priority_score:
          insight.priority_score === null || insight.priority_score === undefined
            ? null
            : Number.isNaN(Number(insight.priority_score))
            ? null
            : Number(insight.priority_score),
        priority_label: insight.priority_label ?? null,
        rationale: insight.rationale ?? null,
        suggested_milestones: Array.isArray(insight.suggested_milestones)
          ? insight.suggested_milestones
              .filter((milestone) => milestone && typeof milestone === "object")
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
          : []
      };
    }
    assignmentInsights.value = insightsRecord;
    analysisGeneratedAt.value = response.analysis?.generated_at ?? null;
    analysisError.value = response.analysis_error ?? null;

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
    assignmentInsights.value = {};
    analysisGeneratedAt.value = null;
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
    course.assignments.map((assignment) => {
      const insight = assignmentInsights.value[assignment.id];
      return {
        ...assignment,
        course_code: course.course_code ?? assignment.course_code ?? null,
        priority_score: insight?.priority_score ?? null,
        priority_label: insight?.priority_label ?? null,
        priority_rationale: insight?.rationale ?? null,
        suggested_milestones: insight?.suggested_milestones ?? []
      };
    })
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
    assignments: [...course.assignments]
      .map((assignment) => {
        const insight = assignmentInsights.value[assignment.id];
        return {
          ...assignment,
          course_code: course.course_code ?? assignment.course_code ?? null,
          priority_score: insight?.priority_score ?? null,
          priority_label: insight?.priority_label ?? null,
          priority_rationale: insight?.rationale ?? null,
          suggested_milestones: insight?.suggested_milestones ?? []
        };
      })
      .sort((a, b) => a.due_at.localeCompare(b.due_at))
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
  analysisGeneratedAt,
  analysisError,
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
