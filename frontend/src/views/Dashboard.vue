<template>
  <div class="flex h-[85vh] gap-4">
    <!-- Center: clean agent investigation console -->
    <main
      class="flex-1 min-w-0 bg-plum rounded-lg border border-sand/30 p-6 flex flex-col"
    >
      <div class="font-mono text-xs uppercase tracking-mono text-mint mb-1">
        ACTIVE INVESTIGATION
      </div>
      <h2
        class="text-xl font-light text-cream mb-4 pb-2 border-b border-sand/20"
      >
        Active Investigation
        <span v-if="selectedChallenge" class="text-mint text-sm ml-1"
          >- {{ selectedChallenge.title }}</span
        >
      </h2>

      <div
        v-if="!selectedChallenge"
        class="flex-1 flex items-center justify-center text-stone"
      >
        Select a challenge from the sidebar to view or start an investigation.
      </div>

      <div v-else class="flex-1 flex flex-col space-y-4 overflow-hidden">
        <!-- Agent Info & Controls -->
        <div class="bg-aubergine rounded-lg border border-sand/20 p-3 mb-4">
          <div>
            <div
              class="font-mono text-xs uppercase tracking-mono text-stone mb-1"
            >
              AGENT
            </div>
            <div class="font-medium text-cream mb-2">Primary Solver</div>
            <div
              class="font-mono text-xs uppercase tracking-mono text-stone mb-1"
            >
              MODEL
            </div>
            <select
              v-model="modelChoice"
              @change="setChallengeModel(modelChoice)"
              class="font-mono text-sm text-cream bg-cocoa border border-sand/40 rounded-lg px-2 py-1.5 w-full"
            >
              <option v-for="m in models" :key="m.id" :value="m.id">
                {{ m.display_name }} ({{ m.provider }})
              </option>
            </select>
          </div>
          <div class="flex space-x-2 mt-4">
            <button
              @click="startAgent"
              v-if="selectedChallenge.status === 'QUEUED'"
              class="bg-mint text-cocoa font-medium rounded-lg py-2.5 px-6 hover:bg-mint/90 transition"
            >
              Start Agent
            </button>
            <button
              @click="stopAgent"
              v-if="selectedChallenge.status === 'IN_PROGRESS'"
              class="bg-danger text-cocoa font-medium rounded-lg py-2.5 px-6 hover:bg-danger/90 transition"
            >
              Stop
            </button>
            <button
              @click="restartAgent"
              v-if="
                ['FAILED', 'BLOCKED', 'SOLVED'].includes(
                  selectedChallenge.status,
                )
              "
              class="bg-mint text-cocoa font-medium rounded-lg py-2.5 px-6 hover:bg-mint/90 transition"
            >
              Restart Agent
            </button>
          </div>

          <!-- Flag verification (human-in-the-loop) -->
          <div
            v-if="selectedChallenge.status === 'FLAG_PROPOSED'"
            class="mt-4 bg-cocoa/60 border border-mint/40 rounded p-3"
          >
            <div
              class="font-mono text-xs uppercase tracking-mono text-mint mb-1"
            >
              PROPOSED FLAG — VERIFY
            </div>
            <div class="font-mono text-sm text-cream break-all mb-3">
              {{ selectedChallenge.proposed_flag || "(unknown)" }}
            </div>
            <div class="flex space-x-2">
              <button
                @click="markSolved"
                class="bg-mint text-cocoa font-medium rounded-lg py-2 px-4 hover:bg-mint/90 transition"
              >
                Mark Solved
              </button>
              <button
                @click="rejectFlag"
                class="border border-iris text-iris rounded-lg py-2 px-4 hover:bg-iris/10 transition"
              >
                Flag Wrong
              </button>
            </div>
          </div>
        </div>

        <!-- Challenge File Upload -->
        <div class="bg-aubergine rounded-lg border border-sand/20 p-3 mb-4">
          <div
            class="font-mono text-xs uppercase tracking-mono text-stone mb-2"
          >
            CHALLENGE FILES
          </div>
          <div
            v-if="selectedChallengeFiles.length === 0"
            class="text-stone italic text-sm mb-2"
          >
            No files uploaded.
          </div>
          <div v-else class="mb-2 space-y-1">
            <div
              v-for="f in selectedChallengeFiles"
              :key="f.filename"
              class="text-sm font-mono text-cream/80 flex justify-between"
            >
              <span>{{ f.filename }}</span>
              <span class="text-stone">{{ formatBytes(f.size) }}</span>
            </div>
          </div>
          <div class="flex space-x-2">
            <input
              ref="fileInput"
              type="file"
              class="flex-1 bg-cocoa border border-sand/40 rounded p-2 text-cream text-sm file:mr-3 file:bg-plum file:text-mint file:border-0 file:rounded file:px-3 file:py-1"
            />
            <button
              @click="uploadFile"
              class="bg-mint text-cocoa font-medium rounded-lg py-2 px-4 hover:bg-mint/90 transition"
            >
              Upload
            </button>
          </div>
        </div>

        <!-- Live Terminal/Event Stream -->
        <div
          class="flex-1 bg-cocoa border border-sand/30 rounded-lg font-mono text-[13px] leading-relaxed overflow-y-auto p-4"
          id="terminal"
        >
          <div v-if="logs.length === 0" class="text-stone italic">
            No agent logs yet. Click 'Start Agent'.
          </div>
          <div v-for="(log, idx) in logs" :key="idx" class="mb-1">
            <span class="text-stone text-xs mr-2">[{{ log.timestamp }}]</span>
            <span :class="log.color + ' font-bold mr-2'">[{{ log.type }}]</span>
            <span class="text-cream/80 whitespace-pre-wrap">{{
              log.content
            }}</span>
          </div>
        </div>

        <!-- Human Intervention Input -->
        <div class="mt-auto pt-4 flex">
          <input
            v-model="interventionText"
            @keyup.enter="sendIntervention"
            type="text"
            placeholder="Send manual command or hint (Intervene)..."
            class="flex-1 bg-cocoa border border-sand/40 rounded p-2 text-cream font-mono text-sm focus:border-mint focus:ring-1 focus:ring-mint"
          />
          <button
            @click="sendIntervention"
            class="border border-iris text-iris rounded-lg px-5 py-2.5 hover:bg-iris/10 transition"
          >
            Send
          </button>
        </div>
      </div>
    </main>

    <!-- Right sidebar: challenge history list (ChatGPT-style) -->
    <aside
      class="w-72 shrink-0 bg-plum rounded-lg border border-sand/30 p-4 flex flex-col overflow-hidden"
    >
      <div class="flex justify-between items-center mb-2">
        <h2 class="text-lg font-light text-cream">Challenges</h2>
        <button
          @click="showCreate = !showCreate"
          class="text-mint text-sm hover:text-mint/80 transition"
        >
          {{ showCreate ? "Close" : "+ New" }}
        </button>
      </div>
      <div v-if="currentSession()" class="text-xs font-mono text-stone mb-3">
        Session: {{ currentSession().name }}
      </div>

      <!-- Create form (toggle) -->
      <form
        v-if="showCreate"
        @submit.prevent="createChallenge"
        class="space-y-2 bg-aubergine rounded-lg border border-sand/20 p-3 mb-3"
      >
        <input
          v-model="newChallenge.title"
          type="text"
          placeholder="Title"
          required
          class="w-full bg-cocoa border border-sand/40 rounded p-2 text-cream text-sm focus:border-mint focus:ring-1 focus:ring-mint"
        />
        <select
          v-model="newChallenge.category"
          required
          class="w-full bg-cocoa border border-sand/40 rounded p-2 text-cream text-sm"
        >
          <option v-for="c in CHALLENGE_CATEGORIES" :key="c" :value="c">
            {{ c }}
          </option>
        </select>
        <textarea
          v-model="newChallenge.description"
          placeholder="Description & Hints"
          class="w-full bg-cocoa border border-sand/40 rounded p-2 text-cream text-sm resize-none h-16 focus:border-mint focus:ring-1 focus:ring-mint"
        ></textarea>
        <input
          ref="createFileInput"
          type="file"
          multiple
          class="w-full bg-cocoa border border-sand/40 rounded p-2 text-cream text-sm file:mr-2 file:bg-plum file:text-mint file:border-0 file:rounded file:px-2 file:py-1"
        />
        <select
          v-model="newChallenge.model"
          class="w-full bg-cocoa border border-sand/40 rounded p-2 text-cream text-sm"
        >
          <option v-for="m in models" :key="m.id" :value="m.id">
            {{ m.display_name }} ({{ m.provider }})
          </option>
        </select>
        <button
          type="submit"
          class="w-full bg-mint text-cocoa font-medium rounded-lg py-2 text-sm hover:bg-mint/90 transition"
        >
          Add Challenge
        </button>
      </form>

      <!-- Challenge list -->
      <div class="flex-1 overflow-y-auto -mx-1 px-1">
        <div v-if="challenges.length === 0" class="text-stone italic text-sm">
          No challenges in this session yet.
        </div>
        <div
          v-for="challenge in challenges"
          :key="challenge.id"
          class="bg-aubergine rounded-lg border p-3 mb-2 cursor-pointer hover:bg-aubergine/80 transition flex flex-col gap-1"
          :class="
            selectedChallenge && selectedChallenge.id === challenge.id
              ? 'border-mint/60'
              : 'border-sand/20'
          "
          @click="selectChallenge(challenge)"
        >
          <div class="flex justify-between items-center gap-2">
            <span class="font-medium text-cream text-sm truncate">{{
              challenge.title
            }}</span>
            <span
              class="text-xs px-2 py-0.5 rounded-pill font-mono tracking-mono shrink-0"
              :class="statusClasses[challenge.status]"
              >{{ challenge.status }}</span
            >
          </div>
          <span class="text-xs font-mono text-stone truncate">{{
            challenge.category
          }}</span>
          <button
            @click.stop="deleteChallenge(challenge.id)"
            class="text-stone hover:text-danger text-xs self-end transition"
            title="Delete"
          >
            ✖
          </button>
        </div>
      </div>
    </aside>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, watch } from "vue";
import { sessionState, loadSessions, currentSession } from "../store.js";

const challenges = ref([]);
const CHALLENGE_CATEGORIES = [
  "Web",
  "Pwn",
  "Reverse Engineering",
  "Cryptography",
  "Forensics",
  "OSINT",
  "Misc",
  "Steganography",
  "Programming",
  "Hardware",
  "Cloud",
  "Blockchain",
  "Mobile",
  "Network",
  "AI/ML",
];
const statusClasses = {
  QUEUED: "bg-plum text-stone border border-sand/30",
  IN_PROGRESS: "bg-mint/10 text-mint border border-mint/40",
  BLOCKED: "bg-lavender/10 text-lavender border border-lavender/40",
  SOLVED: "bg-mint text-cocoa border border-mint",
  FAILED: "bg-aubergine text-cream/60 border border-sand/30",
  FLAG_PROPOSED: "bg-lavender/10 text-lavender border border-lavender/40",
};
const newChallenge = ref({
  title: "",
  category: CHALLENGE_CATEGORIES[0],
  description: "",
  model: "",
});
const selectedChallenge = ref(null);
const showCreate = ref(false);

const logs = ref([]);
const interventionText = ref("");
const selectedChallengeFiles = ref([]);
const fileInput = ref(null);
const createFileInput = ref(null);
let ws = null;

const API_BASE = "http://localhost:8000/api";
const WS_BASE = "ws://localhost:8000/api/ws";

const models = ref([]);
const defaultModel = ref("");
const modelChoice = ref("");

const fetchChallenges = async () => {
  try {
    const sid = sessionState.currentId;
    const url = sid
      ? `${API_BASE}/challenges?session_id=${sid}`
      : `${API_BASE}/challenges`;
    const res = await fetch(url);
    challenges.value = await res.json();
    if (selectedChallenge.value) {
      const updated = challenges.value.find(
        (c) => c.id === selectedChallenge.value.id,
      );
      if (updated) selectedChallenge.value = updated;
    }
  } catch (e) {
    console.error("Failed to fetch challenges", e);
  }
};

const fetchModels = async () => {
  try {
    const res = await fetch(`${API_BASE}/models`);
    const data = await res.json();
    models.value = data.models || [];
    defaultModel.value = data.default_model || "";
    if (!newChallenge.value.model && defaultModel.value) {
      newChallenge.value.model = defaultModel.value;
    }
  } catch (e) {
    console.error("Failed to fetch models", e);
  }
};

const createChallenge = async () => {
  try {
    const fd = new FormData();
    fd.append("title", newChallenge.value.title);
    fd.append("category", newChallenge.value.category);
    fd.append("description", newChallenge.value.description || "");
    fd.append("assigned_model", newChallenge.value.model || "");
    if (sessionState.currentId) {
      fd.append("session_id", String(sessionState.currentId));
    }
    const createInput = createFileInput.value;
    if (createInput && createInput.files && createInput.files.length > 0) {
      for (const f of createInput.files) {
        fd.append("files", f);
      }
    }
    await fetch(`${API_BASE}/challenges`, {
      method: "POST",
      body: fd,
    });
    newChallenge.value = {
      title: "",
      category: CHALLENGE_CATEGORIES[0],
      description: "",
      model: defaultModel.value || "",
    };
    if (createFileInput.value) createFileInput.value.value = "";
    showCreate.value = false;
    await fetchChallenges();
  } catch (e) {
    console.error("Failed to create challenge", e);
  }
};

const setChallengeModel = async (modelId) => {
  if (!selectedChallenge.value || !modelId) return;
  try {
    const r = await fetch(
      `${API_BASE}/challenges/${selectedChallenge.value.id}/model`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model: modelId }),
      },
    );
    if (!r.ok) {
      console.error("Set model failed", r.status);
      return;
    }
    if (selectedChallenge.value)
      selectedChallenge.value.assigned_model = modelId;
    await fetchChallenges();
  } catch (e) {
    console.error("Failed to set model", e);
  }
};

const connectWebSocket = (challengeId) => {
  if (ws) {
    ws.close();
  }
  logs.value = []; // Clear logs on switch
  ws = new WebSocket(`${WS_BASE}/challenges/${challengeId}`);

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      logs.value.push(msg);
      scrollToBottom();
    } catch (e) {
      console.error("Invalid WS message", e);
    }
  };

  ws.onerror = (e) => console.error("WebSocket Error", e);
};

const selectChallenge = (challenge) => {
  selectedChallenge.value = challenge;
  connectWebSocket(challenge.id);
  fetchFiles(challenge.id);
  modelChoice.value = challenge.assigned_model || defaultModel.value;
};

const startAgent = async () => {
  try {
    await fetch(`${API_BASE}/challenges/${selectedChallenge.value.id}/start`, {
      method: "POST",
    });
    await fetchChallenges();
  } catch (e) {
    console.error("Failed to start agent", e);
  }
};

const stopAgent = async () => {
  if (!selectedChallenge.value) return;
  try {
    await fetch(`${API_BASE}/challenges/${selectedChallenge.value.id}/stop`, {
      method: "POST",
    });
    await fetchChallenges();
  } catch (e) {
    console.error("Failed to stop agent", e);
  }
};

const restartAgent = async () => {
  if (!selectedChallenge.value) return;
  try {
    const r = await fetch(
      `${API_BASE}/challenges/${selectedChallenge.value.id}/restart`,
      { method: "POST" },
    );
    if (!r.ok) {
      console.error("Restart agent failed", r.status);
      return;
    }
    await fetchChallenges();
  } catch (e) {
    console.error("Failed to restart agent", e);
  }
};

const deleteChallenge = async (id) => {
  if (!confirm("Are you sure you want to delete this challenge?")) return;
  try {
    await fetch(`${API_BASE}/challenges/${id}`, { method: "DELETE" });
    if (selectedChallenge.value && selectedChallenge.value.id === id) {
      selectedChallenge.value = null;
      selectedChallengeFiles.value = [];
      logs.value = [];
      if (ws) {
        ws.close();
        ws = null;
      }
    }
    await fetchChallenges();
  } catch (e) {
    console.error("Failed to delete challenge", e);
  }
};

const fetchFiles = async (challengeId) => {
  try {
    const res = await fetch(`${API_BASE}/challenges/${challengeId}/files`);
    if (!res.ok) return;
    const data = await res.json();
    selectedChallengeFiles.value = data.files || [];
  } catch (e) {
    console.error("Failed to fetch files", e);
  }
};

const uploadFile = async () => {
  if (!selectedChallenge.value) return;
  const input = fileInput.value;
  if (!input || !input.files || input.files.length === 0) return;
  const file = input.files[0];
  const fd = new FormData();
  fd.append("file", file);
  try {
    const res = await fetch(
      `${API_BASE}/challenges/${selectedChallenge.value.id}/files`,
      { method: "POST", body: fd },
    );
    if (!res.ok) {
      console.error("Upload failed", res.status);
      return;
    }
    await fetchFiles(selectedChallenge.value.id);
    input.value = "";
  } catch (e) {
    console.error("Failed to upload file", e);
  }
};

const formatBytes = (bytes) => {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return (bytes / Math.pow(k, i)).toFixed(1) + " " + sizes[i];
};

const sendIntervention = () => {
  if (!ws || !interventionText.value.trim()) return;
  ws.send(interventionText.value);
  interventionText.value = "";
};

const markSolved = async () => {
  if (!selectedChallenge.value) return;
  try {
    await fetch(`${API_BASE}/challenges/${selectedChallenge.value.id}/solved`, {
      method: "POST",
    });
    await fetchChallenges();
  } catch (e) {
    console.error("Failed to mark solved", e);
  }
};

const rejectFlag = () => {
  if (ws) ws.send("flag is wrong");
};

const scrollToBottom = () => {
  nextTick(() => {
    const terminal = document.querySelector("#terminal");
    if (terminal) terminal.scrollTop = terminal.scrollHeight;
  });
};

onMounted(async () => {
  await loadSessions();
  fetchChallenges();
  fetchModels();
  setInterval(fetchChallenges, 5000);
});

watch(
  () => sessionState.currentId,
  () => {
    selectedChallenge.value = null;
    selectedChallengeFiles.value = [];
    logs.value = [];
    fetchChallenges();
  },
);
</script>

<style>
#terminal::-webkit-scrollbar {
  width: 6px;
}
#terminal::-webkit-scrollbar-track {
  background: #200f0a;
}
#terminal::-webkit-scrollbar-thumb {
  background: #a69f9d;
  border-radius: 3px;
}
</style>
