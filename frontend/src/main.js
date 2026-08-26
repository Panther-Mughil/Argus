import { createApp } from "vue";
import App from "./App.vue";
import router from "./router";

// Attach the JWT to every /api request so the backend auth dependency is satisfied.
const API_ORIGIN = "http://localhost:8000";
const origFetch = window.fetch.bind(window);
window.fetch = (input, init = {}) => {
    const url = typeof input === "string" ? input : (input && input.url) || "";
    const headers = new Headers(init.headers || {});
    if (url.startsWith(API_ORIGIN + "/api/")) {
        const token = localStorage.getItem("argus_token");
        if (token) headers.set("Authorization", "Bearer " + token);
        if (
            init.body &&
            typeof init.body === "string" &&
            !headers.has("Content-Type")
        ) {
            headers.set("Content-Type", "application/json");
        }
    }
    init.headers = headers;
    return origFetch(input, init);
};

createApp(App).use(router).mount("#app");
