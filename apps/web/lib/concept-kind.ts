export function conceptKindIcon(kind: "conceptual" | "coding"): string {
  return kind === "coding" ? "science" : "menu_book";
}

export function conceptKindLabel(kind: "conceptual" | "coding"): string {
  return kind === "coding" ? "Lab" : "Lecture";
}
