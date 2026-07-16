export interface CourseSummary {
  id: string;
  title: string;
  goal: string;
  status: "draft" | "ready" | "archived";
  active_version: number;
  updated_at: string;
}

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function getCourses(accessToken: string): Promise<CourseSummary[]> {
  const response = await fetch(`${apiUrl}/api/v1/courses`, {
    headers: { Authorization: `Bearer ${accessToken}` },
    cache: "no-store"
  });
  if (!response.ok) throw new Error("Unable to load courses.");
  return response.json();
}
