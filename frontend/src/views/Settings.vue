<template>
    <div class="max-w-[1000px]">
        <h2 class="text-xl font-light mb-4">Settings</h2>

        <!-- Teams (per-session) -->
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
                    <button
                        @click="deleteTeam(team.id)"
                        class="text-danger text-sm"
                    >
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
                        v-if="!membersByTeam[team.id] || membersByTeam[team.id].length === 0"
                        class="text-stone text-sm italic"
                    >
                        No members yet.
                    </li>
                </ul>
            </div>
        </div>

        <!-- Podman Hosts -->
        <div class="bg-plum rounded-lg border border-sand/30 p-6 mb-6">
            <div class="flex justify-between items-center mb-4">
                <h3 class="text-lg font-medium">Podman Hosts</h3>
                <button
                    @click="openHostForm()"
                    class="bg-mint text-cocoa font-medium rounded-lg px-3 py-1.5 text-sm hover:bg-mint/90 transition"
                >
                    + Add Host
                </button>
            </div>

            <div
                v-if="showHostForm"
                class="bg-aubergine rounded-lg border border-sand/20 p-4 mb-4 grid grid-cols-2 gap-3"
            >
                <label class="block">
                    <span class="text-xs text-stone">Name</span>
                    <input
                        v-model="hostForm.name"
                        :disabled="!showHostForm || false"
                        class="w-full bg-cocoa border border-sand/40 rounded p-2 text-cream text-sm"
                    />
                </label>
                <label class="block">
                    <span class="text-xs text-stone">Host</span>
                    <input
                        v-model="hostForm.host"
                        class="w-full bg-cocoa border border-sand/40 rounded p-2 text-cream text-sm"
                    />
                </label>
                <label class="block">
                    <span class="text-xs text-stone">Port</span>
                    <input
                        v-model.number="hostForm.port"
                        type="number"
                        class="w-full bg-cocoa border border-sand/40 rounded p-2 text-cream text-sm"
                    />
                </label>
                <label class="block">
                    <span class="text-xs text-stone">User</span>
                    <input
                        v-model="hostForm.user"
                        class="w-full bg-cocoa border border-sand/40 rounded p-2 text-cream text-sm"
                    />
                </label>
                <label class="block">
                    <span class="text-xs text-stone">SSH Key</span>
                    <input
                        v-model="hostForm.ssh_key"
                        class="w-full bg-cocoa border border-sand/40 rounded p-2 text-cream text-sm"
                    />
                </label>
                <label class="block">
                    <span class="text-xs text-stone">Concurrency</span>
                    <input
                        v-model.number="hostForm.concurrency"
                        type="number"
                        class="w-full bg-cocoa border border-sand/40 rounded p-2 text-cream text-sm"
                    />
                </label>
                <label class="block">
                    <span class="text-xs text-stone">Max Challenges</span>
                    <input
                        v-model.number="hostForm.max_challenges"
                        type="number"
                        class="w-full bg-cocoa border border-sand/40 rounded p-2 text-cream text-sm"
                    />
                </label>
                <label class="flex items-center space-x-2 text-sm">
                    <input v-model="hostForm.healthy" type="checkbox" />
                    <span>Healthy</span>
                </label>
                <label class="block col-span-2">
                    <span class="text-xs text-stone">Notes</span>
                    <input
                        v-model="hostForm.notes"
                        class="w-full bg-cocoa border border-sand/40 rounded p-2 text-cream text-sm"
                    />
                </label>
                <div class="col-span-2 flex space-x-2">
                    <button
                        @click="saveHost"
                        class="bg-mint text-cocoa font-medium rounded-lg px-4 py-2 text-sm hover:bg-mint/90 transition"
                    >
                        {{ editingHost ? "Save Host" : "Add Host" }}
                    </button>
                    <button
                        @click="showHostForm = false"
                        class="border border-sand/40 text-stone rounded-lg px-4 py-2 text-sm"
                    >
                        Cancel
                    </button>
                </div>
            </div>

            <div
                v-for="host in hosts"
                :key="host.name"
                class="bg-aubergine rounded-lg border border-sand/20 p-3 mb-3"
            >
                <div class="flex justify-between items-center">
                    <div>
                        <div class="font-medium">
                            {{ host.name }}
                            <span
                                class="text-xs px-1.5 py-0.5 rounded-pill font-mono"
                                :class="host.healthy ? 'bg-mint/10 text-mint' : 'bg-danger/10 text-danger'"
                                >{{ host.healthy ? "healthy" : "unhealthy" }}</span
                            >
                        </div>
                        <div class="text-xs font-mono text-stone">
                            {{ host.user }}@{{ host.host }}:{{ host.port }} ·
                            conc {{ host.concurrency }} · max
                            {{ host.max_challenges }}
                        </div>
                    </div>
                    <div class="flex space-x-3 text-sm">
                        <button
                            @click="openHostForm(host)"
                            class="text-iris hover:text-iris/80 transition"
                        >
                            Edit
                        </button>
                        <button
                            @click="connectTerminal(host.name)"
                            class="text-mint hover:text-mint/80 transition"
                        >
                            Terminal
                        </button>
                        <button
                            @click="deleteHost(host.name)"
                            class="text-danger hover:text-danger/80 transition"
                        >
                            Delete
                        </button>
                    </div>
                </div>
                <div v-if="terminalHost === host.name" class="mt-3">
                    <ShellTerminal :host-name="host.name" />
                </div>
            </div>
            <div
                v-if="hosts.length === 0"
                class="text-stone italic text-sm"
            >
                No container hosts configured.
            </div>
        </div>

        <!-- Models -->
        <div class="bg-plum rounded-lg border border-sand/30 p-6 mb-6">
            <div class="flex justify-between items-center mb-4">
                <h3 class="text-lg font-medium">Models</h3>
                <button
                    @click="openProviderForm()"
                    class="bg-mint text-cocoa font-medium rounded-lg px-3 py-1.5 text-sm hover:bg-mint/90 transition"
                >
                    + Add Provider
                </button>
            </div>

            <div
                v-if="showProviderForm"
                class="bg-aubergine rounded-lg border border-sand/20 p-4 mb-4 grid grid-cols-2 gap-3"
            >
                <label class="block">
                    <span class="text-xs text-stone">Name</span>
                    <input
                        v-model="providerForm.name"
                        class="w-full bg-cocoa border border-sand/40 rounded p-2 text-cream text-sm"
                    />
                </label>
                <label class="block">
                    <span class="text-xs text-stone">API type</span>
                    <input
                        v-model="providerForm.api_type"
                        class="w-full bg-cocoa border border-sand/40 rounded p-2 text-cream text-sm"
                    />
                </label>
                <label class="block col-span-2">
                    <span class="text-xs text-stone">Base URL</span>
                    <input
                        v-model="providerForm.base_url"
                        class="w-full bg-cocoa border border-sand/40 rounded p-2 text-cream text-sm"
                    />
                </label>
                <label class="block">
                    <span class="text-xs text-stone">API key</span>
                    <input
                        v-model="providerForm.api_key"
                        class="w-full bg-cocoa border border-sand/40 rounded p-2 text-cream text-sm"
                    />
                </label>
                <label class="block">
                    <span class="text-xs text-stone">API key env</span>
                    <input
                        v-model="providerForm.api_key_env"
                        class="w-full bg-cocoa border border-sand/40 rounded p-2 text-cream text-sm"
                    />
                </label>
                <label class="block">
                    <span class="text-xs text-stone">Concurrency</span>
                    <input
                        v-model.number="providerForm.concurrency"
                        type="number"
                        class="w-full bg-cocoa border border-sand/40 rounded p-2 text-cream text-sm"
                    />
                </label>
                <div class="col-span-2 flex space-x-2">
                    <button
                        @click="saveProvider"
                        class="bg-mint text-cocoa font-medium rounded-lg px-4 py-2 text-sm hover:bg-mint/90 transition"
                    >
                        {{ editingProvider ? "Save Provider" : "Add Provider" }}
                    </button>
                    <button
                        @click="showProviderForm = false"
                        class="border border-sand/40 text-stone rounded-lg px-4 py-2 text-sm"
                    >
                        Cancel
                    </button>
                </div>
            </div>

            <div
                v-for="provider in providers"
                :key="provider.name"
                class="bg-aubergine rounded-lg border border-sand/20 p-4 mb-4"
            >
                <div class="flex justify-between items-center">
                    <div>
                        <div class="font-medium">{{ provider.name }}</div>
                        <div class="text-xs font-mono text-stone">
                            {{ provider.api_type }} · {{ provider.base_url }}
                        </div>
                    </div>
                    <div class="flex space-x-3 text-sm">
                        <button
                            @click="openProviderForm(provider)"
                            class="text-iris hover:text-iris/80 transition"
                        >
                            Edit
                        </button>
                        <button
                            @click="deleteProvider(provider.name)"
                            class="text-danger hover:text-danger/80 transition"
                        >
                            Delete
                        </button>
                    </div>
                </div>

                <div
                    v-if="modelFormFor[provider.name]"
                    class="mt-3 bg-cocoa/40 rounded-lg border border-sand/20 p-3 grid grid-cols-2 gap-3"
                >
                    <label class="block">
                        <span class="text-xs text-stone">Model id</span>
                        <input
                            v-model="modelForms[provider.name].id"
                            class="w-full bg-cocoa border border-sand/40 rounded p-2 text-cream text-sm"
                        />
                    </label>
                    <label class="block">
                        <span class="text-xs text-stone">Display name</span>
                        <input
                            v-model="modelForms[provider.name].display_name"
                            class="w-full bg-cocoa border border-sand/40 rounded p-2 text-cream text-sm"
                        />
                    </label>
                    <label class="block">
                        <span class="text-xs text-stone">Context (ctx)</span>
                        <input
                            v-model.number="modelForms[provider.name].ctx"
                            type="number"
                            class="w-full bg-cocoa border border-sand/40 rounded p-2 text-cream text-sm"
                        />
                    </label>
                    <label class="flex items-center space-x-2 text-sm">
                        <input
                            v-model="modelForms[provider.name].free"
                            type="checkbox"
                        />
                        <span>Free</span>
                    </label>
                    <label class="block col-span-2">
                        <span class="text-xs text-stone">Notes</span>
                        <input
                            v-model="modelForms[provider.name].notes"
                            class="w-full bg-cocoa border border-sand/40 rounded p-2 text-cream text-sm"
                        />
                    </label>
                    <div class="col-span-2 flex space-x-2">
                        <button
                            @click="saveModel(provider.name)"
                            class="bg-mint text-cocoa font-medium rounded-lg px-3 py-1.5 text-sm hover:bg-mint/90 transition"
                        >
                            Save Model
                        </button>
                        <button
                            @click="modelFormFor[provider.name] = null"
                            class="border border-sand/40 text-stone rounded-lg px-3 py-1.5 text-sm"
                        >
                            Cancel
                        </button>
                    </div>
                </div>

                <ul class="mt-3 space-y-1">
                    <li
                        v-for="m in provider.models || []"
                        :key="m.id"
                        class="text-sm flex justify-between items-center"
                    >
                        <span>
                            {{ m.display_name || m.id }}
                            <span class="text-stone font-mono text-xs"
                                >({{ m.id }})</span
                            >
                            <span
                                v-if="m.free"
                                class="text-xs px-1.5 py-0.5 rounded-pill bg-mint/10 text-mint ml-1"
                                >free</span
                            >
                        </span>
                        <span class="flex space-x-3">
                            <button
                                @click="openModelForm(provider.name, m)"
                                class="text-iris hover:text-iris/80 text-xs"
                            >
                                Edit
                            </button>
                            <button
                                @click="deleteModel(provider.name, m.id)"
                                class="text-danger hover:text-danger/80 text-xs"
                            >
                                Delete
                            </button>
                        </span>
                    </li>
                </ul>
                <button
                    @click="openModelForm(provider.name)"
                    class="mt-2 text-sm text-mint hover:text-mint/80 transition"
                >
                    + Add Model
                </button>
            </div>
            <div
                v-if="providers.length === 0"
                class="text-stone italic text-sm"
            >
                No model providers configured.
            </div>
        </div>

        <!-- Account -->
        <div class="bg-plum rounded-lg border border-sand/30 p-6">
            <h3 class="text-lg font-medium mb-4">Account</h3>
            <div class="space-y-3 max-w-sm">
                <div>
                    <label class="block text-sm text-cream mb-1"
                        >Current Password</label
                    >
                    <input
                        v-model="oldPass"
                        type="password"
                        class="w-full bg-cocoa border border-sand/40 rounded p-2 text-cream"
                    />
                </div>
                <div>
                    <label class="block text-sm text-cream mb-1"
                        >New Password</label
                    >
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
import { ref, reactive, onMounted } from "vue";
import ShellTerminal from "./ShellTerminal.vue";

const API = "http://localhost:8000/api";

// ---- Teams ----
const teams = ref([]);
const membersByTeam = ref({});
const memberEmail = ref({});
const newTeamName = ref("");

// ---- Hosts ----
const hosts = ref([]);
const showHostForm = ref(false);
const editingHost = ref(null);
const hostForm = reactive({
    name: "",
    host: "",
    port: 2222,
    user: "root",
    ssh_key: "",
    concurrency: 2,
    max_challenges: 8,
    healthy: true,
    notes: "",
});
const terminalHost = ref(null);

// ---- Models ----
const providers = ref([]);
const showProviderForm = ref(false);
const editingProvider = ref(null);
const providerForm = reactive({
    name: "",
    api_type: "openai-completions",
    base_url: "",
    api_key: "",
    api_key_env: "",
    concurrency: 1,
});
const modelFormFor = ref({});
const modelForms = reactive({});

// ---- Account ----
const oldPass = ref("");
const newPass = ref("");
const msg = ref("");

async function loadTeams() {
    const res = await fetch(`${API}/teams`);
    if (!res.ok) return;
    teams.value = await res.json();
    for (const t of teams.value) await loadMembers(t.id);
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

// ---- Hosts ----
async function loadHosts() {
    const res = await fetch(`${API}/admin/hosts`);
    if (!res.ok) return;
    const data = await res.json();
    hosts.value = data.hosts || [];
}
function openHostForm(host) {
    if (host) {
        editingHost.value = host.name;
        Object.assign(hostForm, host);
    } else {
        editingHost.value = null;
        Object.assign(hostForm, {
            name: "",
            host: "",
            port: 2222,
            user: "root",
            ssh_key: "",
            concurrency: 2,
            max_challenges: 8,
            healthy: true,
            notes: "",
        });
    }
    showHostForm.value = true;
}
async function saveHost() {
    const method = editingHost.value ? "PUT" : "POST";
    const url = editingHost.value
        ? `${API}/admin/hosts/${editingHost.value}`
        : `${API}/admin/hosts`;
    const r = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(hostForm),
    });
    if (r.ok) {
        showHostForm.value = false;
        editingHost.value = null;
        await loadHosts();
    }
}
async function deleteHost(name) {
    if (!window.confirm(`Delete host ${name}?`)) return;
    await fetch(`${API}/admin/hosts/${name}`, { method: "DELETE" });
    if (terminalHost.value === name) terminalHost.value = null;
    await loadHosts();
}
function connectTerminal(name) {
    terminalHost.value = terminalHost.value === name ? null : name;
}

// ---- Models ----
async function loadProviders() {
    const res = await fetch(`${API}/admin/models`);
    if (!res.ok) return;
    const data = await res.json();
    providers.value = data.providers || [];
}
function openProviderForm(provider) {
    if (provider) {
        editingProvider.value = provider.name;
        Object.assign(providerForm, {
            name: provider.name,
            api_type: provider.api_type,
            base_url: provider.base_url,
            api_key: provider.api_key || "",
            api_key_env: provider.api_key_env || "",
            concurrency: provider.concurrency || 1,
        });
    } else {
        editingProvider.value = null;
        Object.assign(providerForm, {
            name: "",
            api_type: "openai-completions",
            base_url: "",
            api_key: "",
            api_key_env: "",
            concurrency: 1,
        });
    }
    showProviderForm.value = true;
}
async function saveProvider() {
    const method = editingProvider.value ? "PUT" : "POST";
    const url = editingProvider.value
        ? `${API}/admin/models/providers/${editingProvider.value}`
        : `${API}/admin/models/providers`;
    const r = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(providerForm),
    });
    if (r.ok) {
        showProviderForm.value = false;
        editingProvider.value = null;
        await loadProviders();
    }
}
async function deleteProvider(name) {
    if (!window.confirm(`Delete provider ${name}?`)) return;
    await fetch(`${API}/admin/models/providers/${name}`, { method: "DELETE" });
    await loadProviders();
}
function openModelForm(providerName, model) {
    const base = {
        id: "",
        display_name: "",
        ctx: 131072,
        free: false,
        notes: "",
    };
    if (model) Object.assign(base, model);
    modelForms[providerName] = base;
    modelFormFor.value = { ...modelFormFor.value, [providerName]: true };
}
async function saveModel(providerName) {
    const form = modelForms[providerName];
    if (!form) return;
    // Determine add vs edit by whether the id already exists on this provider.
    const provider = providers.value.find((p) => p.name === providerName);
    const exists = (provider?.models || []).some((m) => m.id === form.id);
    const url = `${API}/admin/models/providers/${providerName}/models${
        exists ? `/${encodeURIComponent(form.id)}` : ""
    }`;
    const r = await fetch(url, {
        method: exists ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
    });
    if (r.ok) {
        modelFormFor.value = { ...modelFormFor.value, [providerName]: false };
        await loadProviders();
    }
}
async function deleteModel(providerName, modelId) {
    if (!window.confirm(`Delete model ${modelId}?`)) return;
    await fetch(
        `${API}/admin/models/providers/${providerName}/models/${encodeURIComponent(modelId)}`,
        { method: "DELETE" },
    );
    await loadProviders();
}

async function changePassword() {
    msg.value = "";
    const res = await fetch(`${API}/auth/change-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ old_password: oldPass.value, new_password: newPass.value }),
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

onMounted(() => {
    loadTeams();
    loadHosts();
    loadProviders();
});
</script>
