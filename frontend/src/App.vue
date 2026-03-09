<script setup lang="ts">
import { ref } from "vue";

const navItems = [
  { to: "/dashboard", label: "仪表盘" },
  { to: "/tasks", label: "任务" },
  { to: "/settings", label: "设置" },
  { to: "/help", label: "帮助" },
];

const sidebarOpen = ref(false);

function closeSidebar() {
  sidebarOpen.value = false;
}
</script>

<template>
  <div class="app-shell">
    <button
      type="button"
      class="menu-toggle"
      aria-label="打开菜单"
      :aria-expanded="sidebarOpen"
      @click="sidebarOpen = true"
    >
      <span class="menu-toggle-icon" aria-hidden="true"></span>
    </button>

    <div
      v-if="sidebarOpen"
      class="sidebar-overlay"
      aria-hidden="true"
      @click="closeSidebar"
    />

    <aside class="sidebar" :class="{ 'sidebar--open': sidebarOpen }">
      <div class="brand">
        <h1>AutoISO</h1>
      </div>
      <nav class="sidebar-nav">
        <RouterLink
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="nav-link"
          active-class="active"
          @click="closeSidebar"
        >
          {{ item.label }}
        </RouterLink>
      </nav>
    </aside>

    <main class="shell-content">
      <RouterView />
    </main>
  </div>
</template>
