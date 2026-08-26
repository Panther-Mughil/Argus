<template>
    <div class="border border-sand/20 rounded-lg overflow-hidden">
        <div
            class="flex items-center justify-between px-3 py-1.5 bg-cocoa/60 border-b border-sand/20"
        >
            <span class="text-xs font-mono text-stone"
                >SSH → {{ hostName }}</span
            >
            <div class="flex space-x-3">
                <button
                    v-if="!connected"
                    @click="connect"
                    class="text-xs text-mint hover:text-mint/80 transition"
                >
                    Connect
                </button>
                <button
                    v-if="connected"
                    @click="disconnect"
                    class="text-xs text-danger hover:text-danger/80 transition"
                >
                    Disconnect
                </button>
            </div>
        </div>
        <div ref="terminalEl" class="h-80"></div>
    </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from "vue";
import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import "@xterm/xterm/css/xterm.css";

const props = defineProps({ hostName: { type: String, required: true } });
const terminalEl = ref(null);
const connected = ref(false);
let term = null;
let fit = null;
let ws = null;

function connect() {
    if (!term) return;
    if (ws && ws.readyState === WebSocket.OPEN) return;
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const url = `${proto}://${location.host}/api/ws/shell/${encodeURIComponent(
        props.hostName,
    )}`;
    ws = new WebSocket(url);
    ws.onopen = () => {
        connected.value = true;
        term.focus();
    };
    ws.onmessage = (e) => term.write(e.data);
    ws.onclose = () => {
        connected.value = false;
    };
    ws.onerror = () => {
        term.writeln("\r\n[ARGUS] WebSocket error.");
        connected.value = false;
    };
}

function disconnect() {
    if (ws) ws.close();
    connected.value = false;
}

onMounted(() => {
    term = new Terminal({
        cursorBlink: true,
        fontSize: 13,
        cols: 110,
        rows: 30,
        convertEol: true,
        theme: { background: "#200f0a", foreground: "#e3ccc0" },
    });
    fit = new FitAddon();
    term.loadAddon(fit);
    term.open(terminalEl.value);
    fit.fit();
    term.writeln("[ARGUS] Click Connect to open an SSH shell.");
    term.onData((data) => {
        if (ws && ws.readyState === WebSocket.OPEN) ws.send(data);
    });
});

onBeforeUnmount(() => {
    disconnect();
    if (term) term.dispose();
});
</script>
