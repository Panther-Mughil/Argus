<template>
  <div
    class="min-h-screen bg-cocoa text-cream font-sans antialiased flex items-center justify-center"
  >
    <div class="bg-plum border border-sand/30 rounded-lg p-8 w-full max-w-sm">
      <div class="flex items-center space-x-2 mb-6 justify-center">
        <img src="/favicon.svg" class="w-8 h-8" />
        <h1 class="text-xl font-medium tracking-[0.02em]">Argus Login</h1>
      </div>
      <form @submit.prevent="login" class="space-y-3">
        <div>
          <label class="block text-sm text-cream mb-1">Username</label>
          <input
            v-model="username"
            type="text"
            required
            class="w-full bg-cocoa border border-sand/40 rounded p-2 text-cream focus:border-mint focus:ring-1 focus:ring-mint"
          />
        </div>
        <div>
          <label class="block text-sm text-cream mb-1">Password</label>
          <input
            v-model="password"
            type="password"
            required
            class="w-full bg-cocoa border border-sand/40 rounded p-2 text-cream focus:border-mint focus:ring-1 focus:ring-mint"
          />
        </div>
        <div v-if="error" class="text-danger text-sm">{{ error }}</div>
        <button
          type="submit"
          class="w-full bg-mint text-cocoa font-medium rounded-lg py-2.5 hover:bg-mint/90 transition"
        >
          Log In
        </button>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";

const router = useRouter();
const username = ref("");
const password = ref("");
const error = ref("");

async function login() {
  error.value = "";
  try {
    const res = await fetch("http://localhost:8000/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: username.value,
        password: password.value,
      }),
    });
    const data = await res.json();
    if (!res.ok) {
      error.value = data.detail || "Login failed";
      return;
    }
    localStorage.setItem("argus_token", data.token);
    router.push("/");
  } catch (e) {
    error.value = "Login failed: " + e;
  }
}
</script>
