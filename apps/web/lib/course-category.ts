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
    color: "#fbe4e6",
    keywords: ["security", "auth", "jwt", "oauth", "encryption", "vulnerability", "penetration"]
  },
  {
    key: "ml",
    icon: "psychology",
    color: "#ece3fb",
    keywords: ["machine learning", " ml ", "neural", "deep learning", "supervised", "unsupervised", "llm", "artificial intelligence", " ai "]
  },
  {
    key: "data",
    icon: "database",
    color: "#fdf1d6",
    keywords: ["sql", "database", "data engineering", "postgres", "etl", "pipeline", "warehouse"]
  },
  {
    key: "web",
    icon: "language",
    color: "#dcedfb",
    keywords: ["web", "react", "frontend", "html", "css", "next.js", "javascript", "typescript", "dom"]
  },
  {
    key: "backend",
    icon: "dns",
    color: "#ddf3e4",
    keywords: ["api", "backend", "server", "fastapi", "django", "microservice", "rest"]
  },
  {
    key: "cloud",
    icon: "cloud",
    color: "#dbf3f1",
    keywords: ["cloud", "docker", "kubernetes", "aws", "azure", "devops", "deployment", "infrastructure"]
  },
  {
    key: "code",
    icon: "code",
    color: "#e5f1da",
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
