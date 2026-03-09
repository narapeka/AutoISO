import { createRouter, createWebHistory } from "vue-router";

import DashboardPage from "../pages/DashboardPage.vue";
import HelpPage from "../pages/HelpPage.vue";
import SettingsPage from "../pages/SettingsPage.vue";
import TasksPage from "../pages/TasksPage.vue";

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", redirect: "/dashboard" },
    { path: "/dashboard", component: DashboardPage },
    { path: "/tasks", component: TasksPage },
    { path: "/settings", component: SettingsPage },
    { path: "/help", component: HelpPage },
  ],
});
