import { createRouter, createWebHistory } from "vue-router";

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
      component: () => import("../views/DashboardView.vue")
    }
  ]
});

export default router;
