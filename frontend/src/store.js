import { reactive } from "vue";

const API = "http://localhost:8000/api";

// Shared session state across the sidebar (switcher) and dashboard (scoped list).
export const sessionState = reactive({
  sessions: [],
  currentId: null,
});

export async function loadSessions() {
  try {
    const res = await fetch(`${API}/sessions`);
    if (!res.ok) return;
    const data = await res.json();
    sessionState.sessions = data;
    if (!sessionState.currentId && data.length > 0) {
      sessionState.currentId = data[0].id;
    }
  } catch (e) {
    console.error("Failed to load sessions", e);
  }
}

export async function createSession(name) {
  const res = await fetch(`${API}/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) return null;
  const session = await res.json();
  await loadSessions();
  sessionState.currentId = session.id;
  return session;
}

export function currentSession() {
  return (
    sessionState.sessions.find((s) => s.id === sessionState.currentId) || null
  );
}
