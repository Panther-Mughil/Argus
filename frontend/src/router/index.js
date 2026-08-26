import { createRouter, createWebHistory } from "vue-router";
import Dashboard from "../views/Dashboard.vue";
import Login from "../views/Login.vue";
import Settings from "../views/Settings.vue";
import AppLayout from "../AppLayout.vue";

const routes = [
  { path: "/login", name: "Login", component: Login },
  {
    path: "/",
    component: AppLayout,
    meta: { requiresAuth: true },
    children: [
      { path: "", name: "MainDashboard", component: Dashboard },
      { path: "settings", name: "Settings", component: Settings },
    ],
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach((to) => {
  const token = localStorage.getItem("argus_token");
  if (to.meta.requiresAuth && !token) {
    return { name: "Login" };
  }
  if (to.name === "Login" && token) {
    return { name: "MainDashboard" };
  }
  return true;
});

export default router;
