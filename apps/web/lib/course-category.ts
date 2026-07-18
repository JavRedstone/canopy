export interface CourseCategory {
  key: string;
  icon: string;
  color: string;
  keywords: string[];
}

const categories: CourseCategory[] = [
  {
    key: "security",
    icon: "shield",
    color: "#fbe0e2",
    keywords: ["security", "auth", "jwt", "oauth", "encryption", "vulnerability", "penetration"]
  },
  {
    key: "ml",
    icon: "psychology",
    color: "#e8defa",
    keywords: ["machine learning", " ml ", "neural", "deep learning", "supervised", "unsupervised", "llm", "artificial intelligence", " ai "]
  },
  {
    key: "data",
    icon: "database",
    color: "#fcedc7",
    keywords: ["sql", "database", "data engineering", "postgres", "etl", "pipeline", "warehouse"]
  },
  {
    key: "web",
    icon: "language",
    color: "#d6e9fb",
    keywords: ["web", "react", "frontend", "html", "css", "next.js", "javascript", "typescript", "dom"]
  },
  {
    key: "backend",
    icon: "dns",
    color: "#d1f0dd",
    keywords: ["api", "backend", "server", "fastapi", "django", "microservice", "rest"]
  },
  {
    key: "cloud",
    icon: "cloud",
    color: "#cef2ef",
    keywords: ["cloud", "docker", "kubernetes", "aws", "azure", "devops", "deployment", "infrastructure"]
  },
  {
    key: "code",
    icon: "code",
    // Shifted further toward yellow-green than "backend" so the two greens are
    // actually distinguishable at a glance -- they were nearly identical before.
    color: "#e9f2c4",
    keywords: ["python", "programming", "algorithm", "code", "software", "language"]
  }
];

const defaultCategory: CourseCategory = { key: "default", icon: "school", color: "#ececec", keywords: [] };

export function getCourseCategory(title: string, goal: string): CourseCategory {
  const haystack = ` ${title.toLowerCase()} ${goal.toLowerCase()} `;
  for (const category of categories) {
    if (category.keywords.some((keyword) => haystack.includes(keyword))) return category;
  }
  return defaultCategory;
}
