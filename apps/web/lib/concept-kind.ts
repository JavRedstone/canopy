export function conceptKindIcon(kind: "conceptual" | "coding" | "assessment"): string {
  if (kind === "coding") return "science";
  return kind === "assessment" ? "assignment_turned_in" : "menu_book";
}

export function conceptKindLabel(kind: "conceptual" | "coding" | "assessment"): string {
  if (kind === "coding") return "Lab";
  return kind === "assessment" ? "Assessment" : "Lecture";
}
