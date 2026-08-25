<template>
    <div class="max-w-[1200px] mx-auto px-6 py-8">
        <header
            class="flex justify-between items-center py-4 border-b border-sand/30 mb-6"
        >
            <div class="flex items-center space-x-3">
                <img
                    src="/favicon.svg"
                    alt="Argus Logo"
                    class="w-10 h-10"
                />
                <h1 class="text-2xl font-medium tracking-[0.02em] text-cream">
                    Argus
                </h1>
            </div>
        </header>

        <main class="grid grid-cols-1 md:grid-cols-3 gap-6">
            <!-- Challenge List Panel -->
            <div
                class="col-span-1 bg-plum rounded-lg border border-sand/30 p-6"
            >
                <h2
                    class="text-xl font-light text-cream mb-4 pb-2 border-b border-sand/20"
                >
                    Challenges
                </h2>

                <div
                    v-if="challenges.length === 0"
                    class="text-stone italic mb-4"
                >
                    No challenges found.
                </div>

                <div
                    v-for="challenge in challenges"
                    :key="challenge.id"
                    class="bg-aubergine rounded-lg border border-sand/20 p-3 mb-3 cursor-pointer hover:bg-aubergine/80 transition flex justify-between items-start"
                    @click="selectChallenge(challenge)"
                >
                    <div class="flex-1">
                        <div class="flex justify-between items-center pr-2">
                            <h3 class="font-medium text-cream">
                                {{ challenge.title }}
                            </h3>
                            <span
                                class="text-xs px-2 py-1 rounded-pill font-mono tracking-mono"
                                :class="statusClasses[challenge.status]"
                                >{{ challenge.status }}</span
                            >
                        </div>
                        <p
                            class="text-xs font-mono tracking-mono text-stone bg-cocoa/50 border border-sand/20 rounded-pill px-2 py-0.5 mt-1 truncate"
                        >
                            {{ challenge.category }}
                        </p>
                    </div>
                    <button
                        @click.stop="deleteChallenge(challenge.id)"
                        class="text-stone hover:text-danger transition px-2"
                        title="Delete Challenge"
                    >
                        ✖
                    </button>
                </div>

                <div class="mt-6 pt-4 border-t border-sand/20">
                    <div
                        class="font-mono text-xs uppercase tracking-mono text-mint mb-1"
                    >
                        NEW CHALLENGE
                    </div>
                    <h3 class="text-lg font-medium text-cream mb-2">
                        Create New Challenge
                    </h3>
                    <div class="border-t border-sand/20 mb-4"></div>
                    <form @submit.prevent="createChallenge" class="space-y-2">
                        <div class="mb-4">
                            <label
                                class="block text-sm font-medium text-cream mb-1.5"
                                >Title</label
                            >
                            <input
                                v-model="newChallenge.title"
                                type="text"
                                placeholder="Challenge Title"
                                required
                                class="w-full bg-cocoa border border-sand/40 rounded p-2 text-cream focus:border-mint focus:ring-1 focus:ring-mint"
                            />
                        </div>
                        <div class="mb-4">
                            <label
                                class="block text-sm font-medium text-cream mb-1.5"
                                >Category
                                <span class="text-mint">*</span></label
                            >
                            <div class="relative">
                                <select
                                    v-model="newChallenge.category"
                                    required
                                    class="w-full bg-cocoa border border-sand/40 rounded p-2 text-cream appearance-none focus:border-mint focus:ring-1 focus:ring-mint"
                                >
                                    <option
                                        v-for="category in CHALLENGE_CATEGORIES"
                                        :key="category"
                                        :value="category"
                                    >
                                        {{ category }}
                                    </option>
                                </select>
                                <div
                                    class="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2 text-mint"
                                >
                                    <svg
                                        class="fill-current h-4 w-4"
                                        xmlns="http://www.w3.org/2000/svg"
                                        viewBox="0 0 20 20"
                                    >
                                        <path
                                            d="M9.293 12.95l.707.707L15.657 8l-1.414-1.414L10 10.828 5.757 6.586 4.343 8z"
                                        />
                                    </svg>
                                </div>
                            </div>
                        </div>
                        <div class="mb-4">
                            <label
                                class="block text-sm font-medium text-cream mb-1.5"
                                >Description</label
                            >
                            <textarea
                                v-model="newChallenge.description"
                                placeholder="Description & Hints"
                                class="w-full bg-cocoa border border-sand/40 rounded p-2 text-cream text-sm resize-none h-24 focus:border-mint focus:ring-1 focus:ring-mint"
                            ></textarea>
                        </div>
                        <div class="mb-4">
                            <label
                                class="block text-sm font-medium text-cream mb-1.5"
                                >Files (optional)</label
                            >
                            <input
                                ref="createFileInput"
                                type="file"
                                multiple
                                class="w-full bg-cocoa border border-sand/40 rounded p-2 text-cream file:mr-3 file:bg-plum file:text-mint file:border-0 file:rounded file:px-3 file:py-1"
                            />
                        </div>
                        <div class="mb-4">
                            <label
                                class="block text-sm font-medium text-cream mb-1.5"
                                >Model</label
                            >
                            <select
                                v-model="newChallenge.model"
                                class="w-full bg-cocoa border border-sand/40 rounded p-2 text-cream appearance-none focus:border-mint focus:ring-1 focus:ring-mint"
                            >
                                <option
                                    v-for="m in models"
                                    :key="m.id"
                                    :value="m.id"
                                >
                                    {{ m.display_name }} ({{ m.provider }})
                                </option>
                            </select>
                        </div>
                        <button
                            type="submit"
                            class="w-full bg-mint text-cocoa font-medium rounded-lg py-2.5 px-4 hover:bg-mint/90 transition"
                        >
                            Add Challenge
                        </button>
                    </form>
                </div>
            </div>

            <!-- Agent Investigation Panel -->
            <div
                class="col-span-1 md:col-span-2 bg-plum rounded-lg border border-sand/30 p-6 flex flex-col h-[80vh]"
            >
                <div
                    class="font-mono text-xs uppercase tracking-mono text-mint mb-1"
                >
                    ACTIVE INVESTIGATION
                </div>
                <h2
                    class="text-xl font-light text-cream mb-4 pb-2 border-b border-sand/20"
                >
                    Active Investigation
                    <span
                        v-if="selectedChallenge"
                        class="text-mint text-sm ml-1"
                        >- {{ selectedChallenge.title }}</span
                    >
                </h2>

                <div
                    v-if="!selectedChallenge"
                    class="flex-1 flex items-center justify-center text-stone"
                >
                    Select a challenge to view or start an investigation.
                </div>

                <div
                    v-else
                    class="flex-1 flex flex-col space-y-4 overflow-hidden"
                >
                    <!-- Agent Info & Controls -->
                    <div
                        class="bg-aubergine rounded-lg border border-sand/20 p-3 mb-4"
                    >
                        <div>
                            <div
                                class="font-mono text-xs uppercase tracking-mono text-stone mb-1"
                            >
                                AGENT
                            </div>
                            <div class="font-medium text-cream mb-2">
                                Primary Solver
                            </div>
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
                                <option
                                    v-for="m in models"
                                    :key="m.id"
                                    :value="m.id"
                                >
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
                                v-if="['FAILED', 'BLOCKED', 'SOLVED'].includes(selectedChallenge.status)"
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
                            <div
                                class="font-mono text-sm text-cream break-all mb-3"
                            >
                                {{ selectedChallenge.proposed_flag || '(unknown)' }}
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
                    <div
                        class="bg-aubergine rounded-lg border border-sand/20 p-3 mb-4"
                    >
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
                                <span class="text-stone"
                                    >{{ formatBytes(f.size) }}</span
                                >
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
                        <div
                            v-if="logs.length === 0"
                            class="text-stone italic"
                        >
                            No agent logs yet. Click 'Start Agent'.
                        </div>
                        <div
                            v-for="(log, idx) in logs"
                            :key="idx"
                            class="mb-1"
                        >
                            <span class="text-stone text-xs mr-2"
                                >[{{ log.timestamp }}]</span
                            >
                            <span :class="log.color + ' font-bold mr-2'"
                                >[{{ log.type }}]</span
                            >
                            <span class="text-cream/80 whitespace-pre-wrap"
                                >{{ log.content }}</span
                            >
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
            </div>
        </main>
    </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'

const challenges = ref([])
const CHALLENGE_CATEGORIES = [
    'Web',
    'Pwn',
    'Reverse Engineering',
    'Cryptography',
    'Forensics',
    'OSINT',
    'Misc',
    'Steganography',
    'Programming',
    'Hardware',
    'Cloud',
    'Blockchain',
    'Mobile',
    'Network',
    'AI/ML',
]
const statusClasses = {
    QUEUED: 'bg-plum text-stone border border-sand/30',
    IN_PROGRESS: 'bg-mint/10 text-mint border border-mint/40',
    BLOCKED: 'bg-lavender/10 text-lavender border border-lavender/40',
    SOLVED: 'bg-mint text-cocoa border border-mint',
    FAILED: 'bg-aubergine text-cream/60 border border-sand/30',
    FLAG_PROPOSED: 'bg-lavender/10 text-lavender border border-lavender/40',
}
const newChallenge = ref({
    title: '',
    category: CHALLENGE_CATEGORIES[0],
    description: '',
    model: '',
})
const selectedChallenge = ref(null)

const logs = ref([])
const interventionText = ref('')
const selectedChallengeFiles = ref([])
const fileInput = ref(null)
const createFileInput = ref(null)
let ws = null

const API_BASE = 'http://localhost:8000/api'
const WS_BASE = 'ws://localhost:8000/api/ws'

const models = ref([])
const defaultModel = ref('')
const modelChoice = ref('')

const fetchChallenges = async () => {
    try {
        const res = await fetch(`${API_BASE}/challenges`)
        challenges.value = await res.json()
        // Update status of currently selected challenge if applicable
        if (selectedChallenge.value) {
            const updated = challenges.value.find(
                (c) => c.id === selectedChallenge.value.id,
            )
            if (updated) selectedChallenge.value = updated
        }
    } catch (e) {
        console.error('Failed to fetch challenges', e)
    }
}

const fetchModels = async () => {
    try {
        const res = await fetch(`${API_BASE}/models`)
        const data = await res.json()
        models.value = data.models || []
        defaultModel.value = data.default_model || ''
        if (!newChallenge.value.model && defaultModel.value) {
            newChallenge.value.model = defaultModel.value
        }
    } catch (e) {
        console.error('Failed to fetch models', e)
    }
}

const createChallenge = async () => {
    try {
        const fd = new FormData()
        fd.append('title', newChallenge.value.title)
        fd.append('category', newChallenge.value.category)
        fd.append('description', newChallenge.value.description || '')
        fd.append('assigned_model', newChallenge.value.model || '')
        const createInput = createFileInput.value
        if (createInput && createInput.files && createInput.files.length > 0) {
            for (const f of createInput.files) {
                fd.append('files', f)
            }
        }
        await fetch(`${API_BASE}/challenges`, {
            method: 'POST',
            body: fd,
        })
        newChallenge.value = {
            title: '',
            category: CHALLENGE_CATEGORIES[0],
            description: '',
            model: defaultModel.value || '',
        }
        if (createFileInput.value) createFileInput.value.value = ''
        await fetchChallenges()
    } catch (e) {
        console.error('Failed to create challenge', e)
    }
}

const setChallengeModel = async (modelId) => {
    if (!selectedChallenge.value || !modelId) return
    try {
        const r = await fetch(
            `${API_BASE}/challenges/${selectedChallenge.value.id}/model`,
            {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ model: modelId }),
            },
        )
        if (!r.ok) {
            console.error('Set model failed', r.status)
            return
        }
        if (selectedChallenge.value)
            selectedChallenge.value.assigned_model = modelId
        await fetchChallenges()
    } catch (e) {
        console.error('Failed to set model', e)
    }
}

const connectWebSocket = (challengeId) => {
    if (ws) {
        ws.close()
    }
    logs.value = [] // Clear logs on switch
    ws = new WebSocket(`${WS_BASE}/challenges/${challengeId}`)

    ws.onmessage = (event) => {
        try {
            const msg = JSON.parse(event.data)
            logs.value.push(msg)
            scrollToBottom()
        } catch (e) {
            console.error('Invalid WS message', e)
        }
    }

    ws.onerror = (e) => console.error('WebSocket Error', e)
}

const selectChallenge = (challenge) => {
    selectedChallenge.value = challenge
    connectWebSocket(challenge.id)
    fetchFiles(challenge.id)
    modelChoice.value = challenge.assigned_model || defaultModel.value
}

const startAgent = async () => {
    try {
        await fetch(
            `${API_BASE}/challenges/${selectedChallenge.value.id}/start`,
            { method: 'POST' },
        )
        await fetchChallenges() // Refresh status
    } catch (e) {
        console.error('Failed to start agent', e)
    }
}

const stopAgent = async () => {
    if (!selectedChallenge.value) return
    try {
        await fetch(
            `${API_BASE}/challenges/${selectedChallenge.value.id}/stop`,
            { method: 'POST' },
        )
        await fetchChallenges() // Refresh status
    } catch (e) {
        console.error('Failed to stop agent', e)
    }
}

const restartAgent = async () => {
    if (!selectedChallenge.value) return
    try {
        const r = await fetch(
            `${API_BASE}/challenges/${selectedChallenge.value.id}/restart`,
            { method: 'POST' },
        )
        if (!r.ok) {
            console.error('Restart agent failed', r.status)
            return
        }
        await fetchChallenges() // Refresh status
    } catch (e) {
        console.error('Failed to restart agent', e)
    }
}

const deleteChallenge = async (id) => {
    if (!confirm('Are you sure you want to delete this challenge?')) return
    try {
        await fetch(`${API_BASE}/challenges/${id}`, { method: 'DELETE' })
        if (selectedChallenge.value && selectedChallenge.value.id === id) {
            selectedChallenge.value = null
            selectedChallengeFiles.value = []
            logs.value = []
            if (ws) {
                ws.close()
                ws = null
            }
        }
        await fetchChallenges() // Refresh list
    } catch (e) {
        console.error('Failed to delete challenge', e)
    }
}

const fetchFiles = async (challengeId) => {
    try {
        const res = await fetch(`${API_BASE}/challenges/${challengeId}/files`)
        if (!res.ok) return
        const data = await res.json()
        selectedChallengeFiles.value = data.files || []
    } catch (e) {
        console.error('Failed to fetch files', e)
    }
}

const uploadFile = async () => {
    if (!selectedChallenge.value) return
    const input = fileInput.value
    if (!input || !input.files || input.files.length === 0) return
    const file = input.files[0]
    const fd = new FormData()
    fd.append('file', file)
    try {
        const res = await fetch(
            `${API_BASE}/challenges/${selectedChallenge.value.id}/files`,
            { method: 'POST', body: fd },
        )
        if (!res.ok) {
            console.error('Upload failed', res.status)
            return
        }
        await fetchFiles(selectedChallenge.value.id)
        input.value = ''
    } catch (e) {
        console.error('Failed to upload file', e)
    }
}

const formatBytes = (bytes) => {
    if (bytes === 0) return '0 B'
    const k = 1024
    const sizes = ['B', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return (bytes / Math.pow(k, i)).toFixed(1) + ' ' + sizes[i]
}

const sendIntervention = () => {
    if (!ws || !interventionText.value.trim()) return
    ws.send(interventionText.value)
    interventionText.value = ''
}

const markSolved = async () => {
    if (!selectedChallenge.value) return
    try {
        await fetch(
            `${API_BASE}/challenges/${selectedChallenge.value.id}/solved`,
            { method: 'POST' },
        )
        await fetchChallenges()
    } catch (e) {
        console.error('Failed to mark solved', e)
    }
}

const rejectFlag = () => {
    if (ws) ws.send('flag is wrong')
}

const scrollToBottom = () => {
    nextTick(() => {
        const terminal = document.querySelector('#terminal')
        if (terminal) terminal.scrollTop = terminal.scrollHeight
    })
}

onMounted(() => {
    fetchChallenges()
    fetchModels()
    // Poll challenges to update status (in real app, use SSE or WS for challenge list too)
    setInterval(fetchChallenges, 5000)
})
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
