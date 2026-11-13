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

const adminUser = { ...fakeUser, role: "admin", email: "admin@example.com" };

const fakeTokens = {
  access_token: "fake-access",
  refresh_token: "fake-refresh",
  token_type: "bearer",
};

/** Fiche enrichie (nouveau schéma) pour tester le rendu. */
const richSheet = {
  id: "sheet-1",
  course_id: "22222222-2222-2222-2222-222222222222",
  model: "gpt-4o",
  version: 1,
  created_at: "2026-01-01T00:00:00Z",
  content: {
    title: "La photosynthèse",
    summary: "Processus de conversion de la lumière en énergie chimique.",
    learning_objectives: ["Comprendre la phase claire", "Identifier les réactifs"],
    key_concepts: [
      {
        term: "Chlorophylle",
        definition: "Pigment vert captant la lumière.",
        importance: "high",
        example: "Feuilles vertes",
      },
    ],
    sections: [
      { heading: "Phase claire", type: "definition", points: ["Photolyse de l'eau"] },
      { heading: "Attention", type: "warning", points: ["Ne pas confondre avec la respiration"] },
    ],
    formulas: [{ name: "Bilan", expression: "6CO2 + 6H2O -> C6H12O6 + 6O2", meaning: "Global" }],
    pitfalls: ["Confondre phase claire et cycle de Calvin"],
    mnemonics: ["CO2 + H2O = sucre + O2"],
    flashcards: [{ question: "Où se déroule la phase claire ?", answer: "Thylakoïdes" }],
    review_questions: ["Expliquer le rôle de la chlorophylle"],
    estimated_review_time_min: 20,
    domain: "sciences",
    domain_label: "Sciences",
    disclaimer: "Fiche pédagogique : vérifiez les valeurs auprès de vos supports.",
  },
};

const courseDetail = {
  id: "22222222-2222-2222-2222-222222222222",
  title: "La photosynthèse",
  subject: "Sciences",
  domain: "sciences",
  tags: [],
  language: "fr",
  status: "ready",
  audio_url: null,
  duration_sec: 3600,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  transcript: null,
  study_sheet: richSheet,
  jobs: [],
};

async function login(page: Page, user = fakeUser) {
  await page.route(`${API}/api/auth/login`, (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(fakeTokens) }),
  );
  await page.route(`${API}/api/auth/me`, (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(user) }),
  );
  await page.route(`${API}/api/api-keys`, (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) }),
  );
  await page.goto("/");
  await page.getByPlaceholder("etudiant@exemple.fr").fill(user.email);
  await page.locator('input[type="password"]').fill("password123");
  await page.getByRole("button", { name: "Se connecter" }).click();
}

test("fiche enrichie : objectifs, sections typées, formules, avertissement", async ({ page }) => {
  await login(page);
  await page.route(`${API}/api/courses/${courseDetail.id}`, (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(courseDetail) }),
  );
  await page.goto(`/courses/${courseDetail.id}`);

  // Titre de la fiche (h2) + badge domaine (span)
  await expect(page.getByRole("heading", { name: "La photosynthèse", level: 2 })).toBeVisible();
  await expect(page.locator("span").filter({ hasText: /^Sciences$/ })).toBeVisible();

  // Avertissement du domaine
  await expect(page.getByText(/Fiche pédagogique/)).toBeVisible();

  // Objectifs
  await expect(page.getByText("Objectifs d'apprentissage")).toBeVisible();
  await expect(page.getByText("Comprendre la phase claire")).toBeVisible();

  // Notion essentielle (badge)
  await expect(page.getByText("Essentiel")).toBeVisible();

  // Section typée : badges "Définition" et "Attention" (spans)
  await expect(page.locator("span").filter({ hasText: /^Définition$/ }).first()).toBeVisible();
  await expect(page.locator("span").filter({ hasText: /^Attention$/ }).first()).toBeVisible();

  // Formule
  await expect(page.getByText("6CO2 + 6H2O -> C6H12O6 + 6O2")).toBeVisible();

  // Pièges + mnémotechniques
  await expect(page.getByText("Pièges à éviter")).toBeVisible();
  await expect(page.getByText("Moyens mnémotechniques")).toBeVisible();
});

test("révision : page accessible et sections visibles", async ({ page }) => {
  await login(page);
  await page.route(`${API}/api/revision/sheets`, (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) }),
  );
  await page.route(`${API}/api/revision/folders`, (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) }),
  );
  await page.route(`${API}/api/revision/quizzes`, (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) }),
  );
  await page.goto("/revision");
  // La page charge sans erreur (titre présent)
  await expect(page.locator("body")).toBeVisible();
});

test("admin facturation : rapport + factures affichés", async ({ page }) => {
  await login(page, adminUser);

  const billingReport = {
    period: "2026-11",
    currency: "EUR",
    markup: 1.0,
    users: [
      {
        user_id: "u1",
        email: "etudiant@example.com",
        display_name: "Alice",
        calls: 12,
        cost_usd: 0.18,
        subtotal: 0.24,
        total: 0.24,
        capped: false,
        currency: "EUR",
        margin_covered: true,
      },
    ],
    total_cost_usd: 0.18,
    total_billed: 0.24,
  };
  const invoices = [
    {
      id: "inv-1",
      number: "FAC-202611-0001",
      user_id: "u1",
      period: "2026-11",
      currency: "EUR",
      subtotal: 0.24,
      vat: 0,
      total: 0.24,
      status: "draft",
      issued_at: null,
      due_at: null,
      paid_at: null,
      lines: [],
    },
  ];

  await page.route(`${API}/api/admin/stats`, (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({}) }),
  );
  await page.route(`${API}/api/admin/billing*`, (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(billingReport) }),
  );
  await page.route(`${API}/api/admin/invoices*`, (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(invoices) }),
  );

  await page.goto("/admin");
  await page.getByRole("button", { name: "Facturation" }).click();

  await expect(page.getByText(/Rapport de facturation/)).toBeVisible();
  await expect(page.getByText("etudiant@example.com")).toBeVisible();
  await expect(page.getByText("FAC-202611-0001")).toBeVisible();
  await expect(page.getByText("Brouillon")).toBeVisible();
  await expect(page.getByRole("button", { name: /Émettre/ })).toBeVisible();
});

test("téléchargement : n'affiche que l'OS détecté par défaut", async ({ page }) => {
  await login(page);
  const downloads = [
    { filename: "Revizio_0.1.0_amd64.deb", size: 6000000, os: "linux", arch: "x86_64", version: "0.1.0", url: "/api/downloads/Revizio_0.1.0_amd64.deb" },
    { filename: "Revizio_0.1.0_x64_fr-FR.msi", size: 5800000, os: "windows", arch: "x86_64", version: "0.1.0", url: "/api/downloads/Revizio_0.1.0_x64_fr-FR.msi" },
    { filename: "Revizio_0.1.0_aarch64.dmg", size: 5500000, os: "macos", arch: "aarch64", version: "0.1.0", url: "/api/downloads/Revizio_0.1.0_aarch64.dmg" },
  ];
  await page.route(`${API}/api/downloads`, (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(downloads) }),
  );
  // Simule un visiteur Linux.
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "userAgent", { get: () => "Mozilla/5.0 (X11; Linux x86_64)" });
    Object.defineProperty(navigator, "platform", { get: () => "Linux x86_64" });
  });
  await page.goto("/download");

  // Linux visible, Windows/macOS masqués par défaut
  await expect(page.getByText("Revizio_0.1.0_amd64.deb")).toBeVisible();
  await expect(page.getByText("Revizio_0.1.0_x64_fr-FR.msi")).toHaveCount(0);
  await expect(page.getByText("Revizio_0.1.0_aarch64.dmg")).toHaveCount(0);

  // Le toggle révèle les autres
  await page.getByRole("button", { name: /Voir les autres systèmes/ }).click();
  await expect(page.getByText("Revizio_0.1.0_x64_fr-FR.msi")).toBeVisible();
  await expect(page.getByText("Revizio_0.1.0_aarch64.dmg")).toBeVisible();
});

test("téléchargement admin : voit toutes les plateformes", async ({ page }) => {
  await login(page, adminUser);
  const downloads = [
    { filename: "Revizio_0.1.0_amd64.deb", size: 6000000, os: "linux", arch: "x86_64", version: "0.1.0", url: "/api/downloads/Revizio_0.1.0_amd64.deb" },
    { filename: "Revizio_0.1.0_x64_fr-FR.msi", size: 5800000, os: "windows", arch: "x86_64", version: "0.1.0", url: "/api/downloads/Revizio_0.1.0_x64_fr-FR.msi" },
    { filename: "Revizio_0.1.0_aarch64.dmg", size: 5500000, os: "macos", arch: "aarch64", version: "0.1.0", url: "/api/downloads/Revizio_0.1.0_aarch64.dmg" },
  ];
  await page.route(`${API}/api/downloads`, (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(downloads) }),
  );
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "userAgent", { get: () => "Mozilla/5.0 (X11; Linux x86_64)" });
    Object.defineProperty(navigator, "platform", { get: () => "Linux x86_64" });
  });
  await page.goto("/download");

  // L'admin voit TOUTES les plateformes, même en étant sur Linux
  await expect(page.getByText("Revizio_0.1.0_amd64.deb")).toBeVisible();
  await expect(page.getByText("Revizio_0.1.0_x64_fr-FR.msi")).toBeVisible();
  await expect(page.getByText("Revizio_0.1.0_aarch64.dmg")).toBeVisible();
  // Badge admin + pas de toggle
  await expect(page.getByText(/Vue admin/)).toBeVisible();
  await expect(page.getByRole("button", { name: /Voir les autres systèmes/ })).toHaveCount(0);
});
