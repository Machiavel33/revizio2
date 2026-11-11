import { test, expect, type Page } from "@playwright/test";

const API = "http://localhost:8000";

const fakeUser = {
  id: "11111111-1111-1111-1111-111111111111",
  email: "etudiant@example.com",
  display_name: "Alice",
  role: "student",
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
};

const fakeTokens = {
  access_token: "fake-access",
  refresh_token: "fake-refresh",
  token_type: "bearer",
};

/** Mocke les endpoints API utilisés par le front. */
async function mockApi(page: Page, opts: { courses?: unknown[] } = {}) {
  await page.route(`${API}/api/auth/login`, (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(fakeTokens) }),
  );
  await page.route(`${API}/api/auth/register`, (route) =>
    route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify(fakeTokens) }),
  );
  await page.route(`${API}/api/auth/me`, (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(fakeUser) }),
  );
  await page.route(`${API}/api/courses`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(opts.courses ?? []),
    }),
  );
  await page.route(`${API}/api/api-keys`, (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) }),
  );
}

test("affiche la page de connexion", async ({ page }) => {
  await mockApi(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Revizio" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Se connecter" })).toBeVisible();
});

test("connexion puis dashboard vide", async ({ page }) => {
  await mockApi(page);
  await page.goto("/");
  await page.getByPlaceholder("etudiant@exemple.fr").fill("etudiant@example.com");
  await page.locator('input[type="password"]').fill("password123");
  await page.getByRole("button", { name: "Se connecter" }).click();

  await expect(page.getByRole("heading", { name: "Mes cours" })).toBeVisible();
  await expect(page.getByText("Aucun cours pour l'instant.")).toBeVisible();
});

test("dashboard avec un cours", async ({ page }) => {
  await mockApi(page, {
    courses: [
      {
        id: "22222222-2222-2222-2222-222222222222",
        title: "Droit constitutionnel",
        subject: "Droit",
        language: "fr",
        status: "ready",
        audio_url: null,
        duration_sec: 3600,
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      },
    ],
  });
  await page.goto("/");
  await page.getByPlaceholder("etudiant@exemple.fr").fill("etudiant@example.com");
  await page.locator('input[type="password"]').fill("password123");
  await page.getByRole("button", { name: "Se connecter" }).click();

  await expect(page.getByText("Droit constitutionnel")).toBeVisible();
  await expect(page.getByText("Prêt")).toBeVisible();
});

test("navigation vers les réglages", async ({ page }) => {
  await mockApi(page);
  await page.goto("/");
  await page.getByPlaceholder("etudiant@exemple.fr").fill("etudiant@example.com");
  await page.locator('input[type="password"]').fill("password123");
  await page.getByRole("button", { name: "Se connecter" }).click();

  await page.getByRole("link", { name: "Réglages" }).click();
  await expect(page.getByRole("heading", { name: "Réglages" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Clés API" })).toBeVisible();
});
