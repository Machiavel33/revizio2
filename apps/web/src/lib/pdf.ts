/** Export PDF d'une fiche de révision (jsPDF). */

import { jsPDF } from "jspdf";
import type { StudySheet } from "./types";

const MARGIN = 18;
const PAGE_W = 210;
const PAGE_H = 297;
const CONTENT_W = PAGE_W - MARGIN * 2;

export async function exportSheetToPdf(sheet: StudySheet): Promise<void> {
  const c = sheet.content;
  const doc = new jsPDF({ unit: "mm", format: "a4" });
  let y = MARGIN;

  const ensureSpace = (needed: number) => {
    if (y + needed > PAGE_H - MARGIN) {
      doc.addPage();
      y = MARGIN;
    }
  };
  const heading = (text: string, size = 14) => {
    ensureSpace(12);
    doc.setFont("helvetica", "bold");
    doc.setFontSize(size);
    doc.setTextColor(20, 20, 30);
    doc.text(text, MARGIN, y);
    y += size * 0.5 + 3;
  };
  const paragraph = (text: string, size = 10) => {
    doc.setFont("helvetica", "normal");
    doc.setFontSize(size);
    doc.setTextColor(60, 60, 70);
    for (const line of doc.splitTextToSize(text, CONTENT_W)) {
      ensureSpace(6);
      doc.text(line, MARGIN, y);
      y += 5;
    }
    y += 2;
  };

  doc.setFont("helvetica", "bold");
  doc.setFontSize(20);
  doc.setTextColor(0, 120, 160);
  doc.text(c.title || "Fiche de révision", MARGIN, y);
  y += 10;

  if (c.learning_objectives && c.learning_objectives.length) {
    heading("Objectifs d'apprentissage");
    for (const o of c.learning_objectives) paragraph(`• ${o}`, 10);
  }

  heading("Résumé");
  paragraph(c.summary);
  paragraph(`Temps de révision estimé : ${c.estimated_review_time_min} min`, 9);

  if (c.key_concepts.length) {
    heading("Notions clés");
    for (const k of c.key_concepts) {
      ensureSpace(10);
      doc.setFont("helvetica", "bold");
      doc.setFontSize(10);
      doc.setTextColor(20, 20, 30);
      const star = k.importance === "high" ? "★ " : "• ";
      doc.text(`${star}${k.term}`, MARGIN, y);
      y += 5;
      paragraph(k.definition, 9);
      if (k.example) paragraph(`Ex. : ${k.example}`, 8);
    }
  }

  if (c.formulas && c.formulas.length) {
    heading("Formules");
    for (const f of c.formulas) {
      ensureSpace(8);
      doc.setFont("courier", "bold");
      doc.setFontSize(10);
      doc.setTextColor(120, 40, 160);
      doc.text(f.expression, MARGIN, y);
      y += 5;
      if (f.name) paragraph(f.name, 9);
      if (f.meaning) paragraph(f.meaning, 8);
    }
  }

  const SECTION_LABEL: Record<string, string> = {
    definition: " [Définition]",
    formula: " [Formule]",
    example: " [Exemple]",
    warning: " [Attention]",
    tip: " [Astuce]",
  };
  for (const s of c.sections) {
    const label = s.type ? SECTION_LABEL[s.type] ?? "" : "";
    heading(`${s.heading}${label}`, 12);
    for (const p of s.points) paragraph(`– ${p}`, 10);
  }

  if (c.pitfalls && c.pitfalls.length) {
    heading("Pièges à éviter");
    for (const p of c.pitfalls) paragraph(`⚠ ${p}`, 10);
  }

  if (c.mnemonics && c.mnemonics.length) {
    heading("Moyens mnémotechniques");
    for (const m of c.mnemonics) paragraph(`✦ ${m}`, 10);
  }

  if (c.flashcards.length) {
    heading("Flashcards");
    for (const f of c.flashcards) {
      ensureSpace(12);
      doc.setFont("helvetica", "bold");
      doc.setFontSize(10);
      doc.setTextColor(20, 20, 30);
      for (const line of doc.splitTextToSize(`Q: ${f.question}`, CONTENT_W)) {
        ensureSpace(6);
        doc.text(line, MARGIN, y);
        y += 5;
      }
      paragraph(`R: ${f.answer}`, 9);
    }
  }

  if (c.review_questions.length) {
    heading("Questions de révision");
    c.review_questions.forEach((q, i) => paragraph(`${i + 1}. ${q}`, 10));
  }

  const safe = (c.title || "fiche-revision").replace(/[^\w\-]+/g, "_").slice(0, 60);
  doc.save(`${safe}.pdf`);
}
