import { createRouter, createWebHistory } from "vue-router";
import useAuth from "../stores/authStore";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      name: "home",
      component: () => import("../views/HomeView.vue")
    },
    {
      path: "/signup",
      name: "signup",
      component: () => import("../views/SignUpView.vue")
    },
    {
      path: "/signin",
      name: "signin",
      component: () => import("../views/SignInView.vue")
    },
    {
      path: "/dashboard",
      name: "dashboard",
      component: () => import("../views/DashboardView.vue"),
      meta: { requiresAuth: true }
    },
    {
      path: "/calendar",
      name: "calendar",
      component: () => import("../views/CalendarView.vue")
    },
    {
      path: "/assistant",
      name: "assistant",
      component: () => import("../views/AssistantView.vue"),
      meta: { requiresAuth: true }
    }
  ]
});

router.beforeEach((to, from, next) => {
  const auth = useAuth();
  const requiresAuth = to.matched.some((record) => record.meta?.requiresAuth);
  const isAuthenticated = auth.isAuthenticated.value;

  if (requiresAuth && !isAuthenticated) {
    next({
      name: "signin",
      query: { redirect: to.fullPath }
    });
    return;
  }

  if (isAuthenticated && (to.name === "signin" || to.name === "signup")) {
    next({ name: "dashboard" });
    return;
  }

  next();
});

export default router;
