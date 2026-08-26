<template>
  <div class="max-w-[900px]">
    <h2 class="text-xl font-light mb-4">Settings</h2>

    <!-- Teams -->
    <div class="bg-plum rounded-lg border border-sand/30 p-6 mb-6">
      <h3 class="text-lg font-medium mb-4">Teams</h3>
      <div class="flex space-x-2 mb-5">
        <input
          v-model="newTeamName"
          type="text"
          placeholder="New team name"
          class="flex-1 bg-cocoa border border-sand/40 rounded p-2 text-cream"
        />
        <button
          @click="createTeam"
          class="bg-mint text-cocoa font-medium rounded-lg px-4 py-2 hover:bg-mint/90 transition"
        >
          Create Team
        </button>
      </div>
      <div
        v-for="team in teams"
        :key="team.id"
        class="bg-aubergine rounded-lg border border-sand/20 p-3 mb-3"
      >
        <div class="flex justify-between items-center">
          <h4 class="font-medium">{{ team.name }}</h4>
          <button @click="deleteTeam(team.id)" class="text-danger text-sm">
            Delete
          </button>
        </div>
        <div class="flex space-x-2 mt-2">
          <input
            v-model="memberEmail[team.id]"
            type="email"
            placeholder="add member by email"
            class="flex-1 bg-cocoa border border-sand/40 rounded p-2 text-cream text-sm"
          />
          <button
            @click="addMember(team.id)"
            class="border border-iris text-iris rounded-lg px-3 py-1.5 text-sm hover:bg-iris/10 transition"
          >
            Add
          </button>
        </div>
        <ul class="mt-3 space-y-1">
          <li
            v-for="u in membersByTeam[team.id] || []"
            :key="u.id"
            class="text-sm flex justify-between items-center"
          >
            <span>
              {{ u.username }}
              <span class="text-stone">({{ u.email }})</span>
            </span>
            <button
              @click="kickMember(team.id, u.id)"
              class="text-stone hover:text-danger transition"
            >
              kick
            </button>
          </li>
          <li
            v-if="
              !membersByTeam[team.id] || membersByTeam[team.id].length === 0
            "
            class="text-stone text-sm italic"
          >
            No members yet.
          </li>
        </ul>
      </div>
    </div>

    <!-- Account -->
    <div class="bg-plum rounded-lg border border-sand/30 p-6">
      <h3 class="text-lg font-medium mb-4">Account</h3>
      <div class="space-y-3 max-w-sm">
        <div>
          <label class="block text-sm text-cream mb-1">Current Password</label>
          <input
            v-model="oldPass"
            type="password"
            class="w-full bg-cocoa border border-sand/40 rounded p-2 text-cream"
          />
        </div>
        <div>
          <label class="block text-sm text-cream mb-1">New Password</label>
          <input
            v-model="newPass"
            type="password"
            class="w-full bg-cocoa border border-sand/40 rounded p-2 text-cream"
          />
        </div>
        <button
          @click="changePassword"
          class="bg-mint text-cocoa font-medium rounded-lg px-4 py-2 hover:bg-mint/90 transition"
        >
          Change Password
        </button>
        <div v-if="msg" class="text-mint text-sm">{{ msg }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";

const API = "http://localhost:8000/api";
const teams = ref([]);
const membersByTeam = ref({});
const memberEmail = ref({});
const newTeamName = ref("");
const oldPass = ref("");
const newPass = ref("");
const msg = ref("");

async function loadTeams() {
  const res = await fetch(`${API}/teams`);
  if (!res.ok) return;
  teams.value = await res.json();
  for (const t of teams.value) {
    await loadMembers(t.id);
  }
}

async function loadMembers(teamId) {
  const res = await fetch(`${API}/teams/${teamId}`);
  if (!res.ok) return;
  const team = await res.json();
  membersByTeam.value[teamId] = team.members || [];
}

async function createTeam() {
  if (!newTeamName.value.trim()) return;
  await fetch(`${API}/teams`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: newTeamName.value.trim() }),
  });
  newTeamName.value = "";
  await loadTeams();
}

async function addMember(teamId) {
  const email = (memberEmail.value[teamId] || "").trim();
  if (!email) return;
  await fetch(`${API}/teams/${teamId}/members`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
  memberEmail.value[teamId] = "";
  await loadMembers(teamId);
}

async function kickMember(teamId, userId) {
  await fetch(`${API}/teams/${teamId}/members/${userId}`, { method: "DELETE" });
  await loadMembers(teamId);
}

async function deleteTeam(teamId) {
  await fetch(`${API}/teams/${teamId}`, { method: "DELETE" });
  await loadTeams();
}

async function changePassword() {
  msg.value = "";
  const res = await fetch(`${API}/auth/change-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      old_password: oldPass.value,
      new_password: newPass.value,
    }),
  });
  if (res.ok) {
    msg.value = "Password updated.";
    oldPass.value = "";
    newPass.value = "";
  } else {
    const d = await res.json().catch(() => ({}));
    msg.value = d.detail || "Failed to change password.";
  }
}

onMounted(loadTeams);
</script>
