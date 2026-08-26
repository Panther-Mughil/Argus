<template>
    <div class="flex min-h-screen bg-cocoa text-cream font-sans antialiased">
        <aside
            class="w-56 shrink-0 border-r border-sand/30 bg-plum p-4 flex flex-col"
        >
            <div class="flex items-center space-x-2 mb-6 px-2">
                <img src="/favicon.svg" class="w-8 h-8" />
                <span class="text-lg font-medium tracking-[0.02em]">Argus</span>
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
function logout() {
    localStorage.removeItem("argus_token");
    window.location.href = "/login";
}
</script>
