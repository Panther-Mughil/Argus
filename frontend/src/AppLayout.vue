<template>
  <div class="flex min-h-screen bg-cocoa text-cream font-sans antialiased">
    <aside
      class="w-56 shrink-0 border-r border-sand/30 bg-plum p-4 flex flex-col"
    >
      <div class="flex items-center space-x-2 mb-6 px-2">
        <img src="/favicon.svg" class="w-8 h-8" />
        <span class="text-lg font-medium tracking-[0.02em]">Argus</span>
      </div>

      <div class="mb-6 px-2">
        <div class="font-mono text-xs uppercase tracking-mono text-mint mb-1">
          Session
        </div>
        <div class="flex space-x-2">
          <select
            v-model="sessionState.currentId"
            class="flex-1 bg-cocoa border border-sand/40 rounded p-2 text-cream text-sm min-w-0"
          >
            <option
              v-for="s in sessionState.sessions"
              :key="s.id"
              :value="s.id"
            >
              {{ s.name }}
            </option>
          </select>
          <button
            @click="newSession"
            class="border border-iris text-iris rounded-lg px-2 hover:bg-iris/10 transition"
            title="New Session"
          >
            +
          </button>
        </div>
      </div>

      <nav class="space-y-1 flex-1">
        <router-link
          to="/"
          class="block px-3 py-2 rounded-lg hover:bg-aubergine/60 transition"
          active-class="bg-aubergine"
        >
          Main Dashboard
        </router-link>
        <router-link
          to="/settings"
          class="block px-3 py-2 rounded-lg hover:bg-aubergine/60 transition"
          active-class="bg-aubergine"
        >
          Settings
        </router-link>
      </nav>
      <button
        @click="logout"
        class="mt-8 w-full text-left px-3 py-2 text-stone hover:text-danger transition"
      >
        Logout
      </button>
    </aside>
    <main class="flex-1 p-6 overflow-y-auto min-w-0">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { onMounted } from "vue";
import { sessionState, loadSessions, createSession } from "./store.js";

async function newSession() {
  const name = window.prompt("Session name (e.g. a CTF event):");
  if (!name || !name.trim()) return;
  await createSession(name.trim());
}

function logout() {
  localStorage.removeItem("argus_token");
  window.location.replace("/login");
}

onMounted(loadSessions);
</script>
