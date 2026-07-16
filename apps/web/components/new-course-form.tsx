"use client";

import { Button } from "@base-ui/react/button";
import { Input } from "@base-ui/react/input";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const maxSourceBytes = 6 * 1024 * 1024;
const allowedSourceTypes = new Set(["application/pdf", "text/markdown", "text/plain"]);

function sourceMimeType(file: File): string {
  if (allowedSourceTypes.has(file.type)) return file.type;
  const filename = file.name.toLowerCase();
  if (filename.endsWith(".pdf")) return "application/pdf";
  if (filename.endsWith(".md")) return "text/markdown";
  if (filename.endsWith(".txt")) return "text/plain";
  throw new Error("Choose a PDF, Markdown, or text file.");
}

export function NewCourseForm() {
  const router = useRouter();
  const [file, setFile] = useState<File>();
  const [title, setTitle] = useState("");
  const [goal, setGoal] = useState("");
  const [error, setError] = useState<string>();
  const [progress, setProgress] = useState<string>();
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) { setError("Choose a source document first."); return; }
    if (file.size > maxSourceBytes) { setError("For now, source files must be 6 MB or smaller."); return; }
    setLoading(true); setError(undefined); setProgress(undefined);
    try {
      const mimeType = sourceMimeType(file);
      const supabase = createClient();
      const { data } = await supabase.auth.getSession();
      if (!data.session) throw new Error("Your session has expired. Please sign in again.");
      const headers = { "Content-Type": "application/json", Authorization: `Bearer ${data.session.access_token}` };
      setProgress("Preparing a secure upload…");
      const sourceResponse = await fetch(`${apiUrl}/api/v1/sources`, { method: "POST", headers, body: JSON.stringify({ filename: file.name, mime_type: mimeType, byte_size: file.size }) });
      if (!sourceResponse.ok) throw new Error("Unable to prepare the source upload.");
      const source: { id: string; storage_path: string; upload_token: string } = await sourceResponse.json();
      setProgress("Uploading your source securely…");
      const { error: uploadError } = await supabase.storage
        .from("sources")
        .uploadToSignedUrl(source.storage_path, source.upload_token, file, { contentType: mimeType });
      if (uploadError) throw new Error("Unable to securely upload the source file.");
      setProgress("Verifying the uploaded source…");
      const completeResponse = await fetch(`${apiUrl}/api/v1/sources/${source.id}/complete`, { method: "POST", headers });
      if (!completeResponse.ok) throw new Error("Unable to confirm the source upload.");
      setProgress("Creating your draft course…");
      const courseResponse = await fetch(`${apiUrl}/api/v1/courses`, { method: "POST", headers, body: JSON.stringify({ title, goal, source_ids: [source.id] }) });
      if (!courseResponse.ok) throw new Error("Unable to create your course.");
      router.push("/courses"); router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to create the course.");
    } finally { setLoading(false); setProgress(undefined); }
  }

  return (
    <form className="form" onSubmit={handleSubmit}>
      <label className="field" htmlFor="course-title">Course title<Input className="input" id="course-title" value={title} onChange={(event) => setTitle(event.target.value)} required /></label>
      <label className="field" htmlFor="course-goal">What do you want to learn?<textarea className="input" id="course-goal" rows={4} value={goal} onChange={(event) => setGoal(event.target.value)} required /></label>
      <label className="field" htmlFor="source-file">Source document<input className="input" id="source-file" type="file" accept=".pdf,.md,.txt,text/plain,application/pdf,text/markdown" onChange={(event) => setFile(event.target.files?.[0])} required /></label>
      <p className="notice">Files are uploaded directly to private storage through a one-time, path-bound upload token. PDF, Markdown, and text files up to 6 MB are supported in this first upload path.</p>
      {progress ? <p className="notice" role="status">{progress}</p> : null}
      {error ? <p className="error" role="alert">{error}</p> : null}
      <Button className="button" type="submit" disabled={loading} focusableWhenDisabled>{loading ? "Creating course…" : "Create course"}</Button>
    </form>
  );
}
