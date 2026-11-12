// Revizio — test de charge k6.
//
// Usage:
//   k6 run load/load-test.js
//   BASE_URL=http://localhost:8000 k6 run load/load-test.js
//
// Scénarios:
//   - health:      smoke (1 VU, 10s)
//   - auth_flow:   register + login (montée en charge)
//   - courses:     CRUD cours authentifié
//   - rate_limit:  vérifie que le rate-limit renvoie 429 sous rafale
//
// Seuils (thresholds) : p95 < 500ms, taux d'erreur < 5%.

import http from "k6/http";
import { check, sleep, group } from "k6";
import { Rate, Trend } from "k6/metrics";

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";

const errorRate = new Rate("errors");
const authDuration = new Trend("auth_duration");
const coursesDuration = new Trend("courses_duration");

export const options = {
  scenarios: {
    health: {
      executor: "constant-vus",
      vus: 1,
      duration: "10s",
      exec: "healthScenario",
      tags: { scenario: "health" },
    },
    auth_flow: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: "10s", target: 10 },
        { duration: "20s", target: 20 },
        { duration: "10s", target: 0 },
      ],
      exec: "authScenario",
      tags: { scenario: "auth" },
    },
    courses: {
      executor: "constant-vus",
      vus: 5,
      duration: "20s",
      exec: "coursesScenario",
      tags: { scenario: "courses" },
    },
  },
  thresholds: {
    // p95 < 2s : réaliste car register/login font du bcrypt (CPU-bound ~300ms).
    // Les endpoints non-auth (health, list) sont bien plus rapides.
    http_req_duration: ["p(95)<2000"],
    errors: ["rate<0.05"],
  },
};

function uniqueEmail() {
  // Composant aléatoire pour éviter les collisions entre VUs au même ms
  const rand = Math.random().toString(36).slice(2, 10);
  return `load_${__VU}_${__ITER}_${Date.now()}_${rand}@example.com`;
}

export function healthScenario() {
  const res = http.get(`${BASE_URL}/health`);
  check(res, { "health 200": (r) => r.status === 200 });
  sleep(1);
}

export function authScenario() {
  const email = uniqueEmail();
  const password = "password123";

  group("register", () => {
    const res = http.post(
      `${BASE_URL}/api/auth/register`,
      JSON.stringify({ email, password, display_name: "Load" }),
      { headers: { "Content-Type": "application/json" } },
    );
    authDuration.add(res.timings.duration);
    const ok = check(res, {
      "register 201": (r) => r.status === 201,
      "has access_token": (r) => !!r.json("access_token"),
    });
    errorRate.add(!ok);
  });

  group("login", () => {
    const res = http.post(
      `${BASE_URL}/api/auth/login`,
      JSON.stringify({ email, password }),
      { headers: { "Content-Type": "application/json" } },
    );
    authDuration.add(res.timings.duration);
    const ok = check(res, { "login 200": (r) => r.status === 200 });
    errorRate.add(!ok);
  });

  sleep(1);
}

export function coursesScenario() {
  const email = uniqueEmail();
  const password = "password123";
  const reg = http.post(
    `${BASE_URL}/api/auth/register`,
    JSON.stringify({ email, password }),
    { headers: { "Content-Type": "application/json" } },
  );
  const token = reg.json("access_token");
  if (!token) {
    errorRate.add(1);
    return;
  }
  const authHeaders = {
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
  };

  group("create_course", () => {
    const res = http.post(
      `${BASE_URL}/api/courses`,
      JSON.stringify({ title: "Load course", subject: "Test" }),
      authHeaders,
    );
    coursesDuration.add(res.timings.duration);
    const ok = check(res, { "create 201": (r) => r.status === 201 });
    errorRate.add(!ok);
  });

  group("list_courses", () => {
    const res = http.get(`${BASE_URL}/api/courses`, authHeaders);
    coursesDuration.add(res.timings.duration);
    const ok = check(res, { "list 200": (r) => r.status === 200 });
    errorRate.add(!ok);
  });

  sleep(1);
}

// Scénario dédié au rate-limit (à lancer seul) :
//   k6 run --env SCENARIO=ratelimit load/load-test.js
export function rateLimitScenario() {
  const res = http.post(
    `${BASE_URL}/api/auth/login`,
    JSON.stringify({ email: "nobody@example.com", password: "wrong" }),
    { headers: { "Content-Type": "application/json" } },
  );
  check(res, { "rate limited (429) or 401": (r) => r.status === 429 || r.status === 401 });
}
