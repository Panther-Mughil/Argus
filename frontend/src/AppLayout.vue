<template>
    <div class="flex min-h-screen bg-cocoa text-cream font-sans antialiased">
        <aside
            :class="collapsed ? 'w-16' : 'w-64'"
            class="shrink-0 border-r border-sand/30 bg-plum flex flex-col transition-all duration-200"
        >
            <!-- Header: the Argus logo is the collapse/expand button -->
            <div class="px-3 py-3">
                <button
                    @click="toggle"
                    class="flex items-center p-2 rounded-lg hover:bg-aubergine/40 transition group w-full"
                    :class="collapsed ? 'justify-center' : 'justify-start space-x-2'"
                    :title="collapsed ? 'Expand sidebar' : 'Collapse sidebar'"
                >
                    <img
                        src="/favicon.svg"
                        class="w-8 h-8 shrink-0 transition-transform group-hover:scale-105"
                    />
                    <span
                        v-if="!collapsed"
                        class="text-lg font-medium tracking-[0.02em] whitespace-nowrap"
                        >Argus</span
                    >
                </button>
            </div>

            <!-- Session switcher (expanded only) -->
            <div v-if="!collapsed" class="mb-6 px-3">
                <div
                    class="font-mono text-xs uppercase tracking-mono text-mint mb-1"
                >
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

            <!-- Collapsed session shortcut -->
            <button
                v-else
                @click="collapsed = false"
                class="mb-4 mx-auto p-2 rounded-lg text-stone hover:text-cream hover:bg-aubergine/60 transition"
                title="Sessions"
            >
                <svg
                    class="w-5 h-5"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2"
                    viewBox="0 0 24 24"
                >
                    <rect x="3" y="3" width="7" height="7"></rect>
                    <rect x="14" y="3" width="7" height="7"></rect>
                    <rect x="14" y="14" width="7" height="7"></rect>
                    <rect x="3" y="14" width="7" height="7"></rect>
                </svg>
            </button>

            <nav class="space-y-1 flex-1 px-3">
                <router-link
                    to="/"
                    class="flex items-center space-x-3 px-3 py-2 rounded-lg hover:bg-aubergine/60 transition"
                    active-class="bg-aubergine"
                    :title="collapsed ? 'Main Dashboard' : ''"
                >
                    <svg
                        class="w-5 h-5 shrink-0"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="2"
                        viewBox="0 0 24 24"
                    >
                        <path
                            d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"
                        ></path>
                        <polyline points="9 22 9 12 15 12 15 22"></polyline>
                    </svg>
                    <span v-if="!collapsed">Main Dashboard</span>
                </router-link>
                <router-link
                    to="/settings"
                    class="flex items-center space-x-3 px-3 py-2 rounded-lg hover:bg-aubergine/60 transition"
                    active-class="bg-aubergine"
                    :title="collapsed ? 'Settings' : ''"
                >
                    <svg
                        class="w-5 h-5 shrink-0"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="2"
                        viewBox="0 0 24 24"
                    >
                        <circle cx="12" cy="12" r="3"></circle>
                        <path
                            d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"
                        ></path>
                    </svg>
                    <span v-if="!collapsed">Settings</span>
                </router-link>
            </nav>

            <button
                @click="logout"
                class="flex items-center space-x-3 px-3 py-2 text-stone hover:text-danger transition"
                :title="collapsed ? 'Logout' : ''"
            >
                <svg
                    class="w-5 h-5 shrink-0"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2"
                    viewBox="0 0 24 24"
                >
                    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
                    <polyline points="16 17 21 12 16 7"></polyline>
                    <line x1="21" y1="12" x2="9" y2="12"></line>
                </svg>
                <span v-if="!collapsed">Logout</span>
            </button>
        </aside>
        <main class="flex-1 p-6 overflow-y-auto min-w-0">
            <router-view />
        </main>
    </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { sessionState, loadSessions, createSession } from "./store.js";

const collapsed = ref(localStorage.getItem("argus_sidebar_collapsed") === "1");

function toggle() {
    collapsed.value = !collapsed.value;
    localStorage.setItem("argus_sidebar_collapsed", collapsed.value ? "1" : "0");
}

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
