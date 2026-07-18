import { APPLY_COLOR, ASSESSMENT_COLOR, UNDERSTAND_COLOR } from "@/lib/palette";

export function conceptKindIcon(kind: "conceptual" | "coding" | "assessment"): string {
  if (kind === "coding") return "science";
  return kind === "assessment" ? "assignment_turned_in" : "menu_book";
}

export function conceptKindLabel(kind: "conceptual" | "coding" | "assessment"): string {
  if (kind === "coding") return "Lab";
  return kind === "assessment" ? "Assessment" : "Lecture";
}

// Reuses the mastery-track colors: conceptual lessons build understanding (indigo), coding
// labs build applied skill (teal) -- the same distinction the mastery meter measures.
export function conceptKindColor(kind: "conceptual" | "coding" | "assessment"): string {
  if (kind === "coding") return APPLY_COLOR;
  return kind === "assessment" ? ASSESSMENT_COLOR : UNDERSTAND_COLOR;
}
