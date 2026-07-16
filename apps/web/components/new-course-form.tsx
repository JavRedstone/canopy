"use client";

import { Button } from "@base-ui/react/button";
import { Input } from "@base-ui/react/input";
import { Tabs } from "@base-ui/react/tabs";
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

type PendingSource =
  | { id: string; kind: "file"; file: File }
  | { id: string; kind: "text"; title: string; content: string };

function pendingSourceLabel(source: PendingSource): string {
  return source.kind === "file" ? source.file.name : `${source.title}.txt`;
}

function pendingSourceBlob(source: PendingSource): { blob: Blob; filename: string; mimeType: string } {
  if (source.kind === "file") {
    return { blob: source.file, filename: source.file.name, mimeType: sourceMimeType(source.file) };
  }
  return {
    blob: new Blob([source.content], { type: "text/plain" }),
    filename: `${source.title}.txt`,
    mimeType: "text/plain"
  };
}

function buildTextSource(content: string, existingSources: PendingSource[]): PendingSource {
  const noteNumber = existingSources.filter((source) => source.kind === "text").length + 1;
  return { id: crypto.randomUUID(), kind: "text", title: `pasted-note-${noteNumber}`, content };
}

export function NewCourseForm() {
  const router = useRouter();
  const [sources, setSources] = useState<PendingSource[]>([]);
  const [noteContent, setNoteContent] = useState("");
  const [title, setTitle] = useState("");
  const [goal, setGoal] = useState("");
  const [error, setError] = useState<string>();
  const [progress, setProgress] = useState<string>();
  const [loading, setLoading] = useState(false);

  function addFileSource(file: File | undefined) {
    if (!file) return;
    setError(undefined);
    setSources((current) => [...current, { id: crypto.randomUUID(), kind: "file", file }]);
  }

  function addTextSource() {
    if (!noteContent.trim()) { setError("Paste some text before adding it as a source."); return; }
    setError(undefined);
    setSources((current) => [...current, buildTextSource(noteContent, current)]);
    setNoteContent("");
  }

  function removeSource(id: string) {
    setSources((current) => current.filter((source) => source.id !== id));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    // Text left in the "paste text" box counts as an optional source too, even if
    // "Add as source" was never clicked.
    const allSources = noteContent.trim() ? [...sources, buildTextSource(noteContent, sources)] : sources;
    setLoading(true); setError(undefined); setProgress(undefined);
    try {
      const supabase = createClient();
      const { data } = await supabase.auth.getSession();
      if (!data.session) throw new Error("Your session has expired. Please sign in again.");
      const headers = { "Content-Type": "application/json", Authorization: `Bearer ${data.session.access_token}` };

      const sourceIds: string[] = [];
      for (const [index, pending] of allSources.entries()) {
        const { blob, filename, mimeType } = pendingSourceBlob(pending);
        if (blob.size > maxSourceBytes) throw new Error(`"${filename}" is larger than the 6 MB limit.`);

        setProgress(`Preparing source ${index + 1} of ${allSources.length}…`);
        const sourceResponse = await fetch(`${apiUrl}/api/v1/sources`, { method: "POST", headers, body: JSON.stringify({ filename, mime_type: mimeType, byte_size: blob.size }) });
        if (!sourceResponse.ok) throw new Error(`Unable to prepare the upload for "${filename}".`);
        const source: { id: string; storage_path: string; upload_token: string } = await sourceResponse.json();

        setProgress(`Uploading source ${index + 1} of ${allSources.length}…`);
        const { error: uploadError } = await supabase.storage
          .from("sources")
          .uploadToSignedUrl(source.storage_path, source.upload_token, blob, { contentType: mimeType });
        if (uploadError) throw new Error(`Unable to securely upload "${filename}".`);

        setProgress(`Verifying source ${index + 1} of ${allSources.length}…`);
        const completeResponse = await fetch(`${apiUrl}/api/v1/sources/${source.id}/complete`, { method: "POST", headers });
        if (!completeResponse.ok) throw new Error(`Unable to confirm "${filename}".`);

        sourceIds.push(source.id);
      }

      setProgress("Creating your draft course…");
      const courseResponse = await fetch(`${apiUrl}/api/v1/courses`, { method: "POST", headers, body: JSON.stringify({ title, goal, source_ids: sourceIds }) });
      if (!courseResponse.ok) throw new Error("Unable to create your course.");
      router.push("/courses"); router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to create the course.");
    } finally { setLoading(false); setProgress(undefined); }
  }

  return (
    <form className="form" onSubmit={handleSubmit}>
      <label className="field" htmlFor="course-title">Course title<Input className="input" id="course-title" value={title} onChange={(event) => setTitle(event.target.value)} autoComplete="off" required /></label>
      <label className="field" htmlFor="course-goal">What do you want to learn?<textarea className="input" id="course-goal" rows={4} value={goal} onChange={(event) => setGoal(event.target.value)} autoComplete="off" required /></label>

      {sources.length > 0 ? (
        <div className="field">
          <span>Sources added</span>
          <div className="source-list">
            {sources.map((source) => (
              <div className="source-row" key={source.id}>
                <span>{pendingSourceLabel(source)}</span>
                <Button className="button button-secondary button-small" type="button" onClick={() => removeSource(source.id)}>Remove</Button>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      <div className="field">
        <span>Add sources (optional)</span>
        <Tabs.Root className="tabs" defaultValue="file">
          <Tabs.List className="tabs-list">
            <Tabs.Tab className="tabs-tab" value="file">Upload file</Tabs.Tab>
            <Tabs.Tab className="tabs-tab" value="text">Paste text</Tabs.Tab>
          </Tabs.List>
          <Tabs.Panel className="tabs-panel" value="file">
            <div className="file-picker">
              <label className="button button-secondary" htmlFor="source-file">Choose file</label>
              <span className="file-picker-name">PDF, Markdown, or text, up to 6 MB</span>
            </div>
            <input
              className="visually-hidden"
              id="source-file"
              type="file"
              accept=".pdf,.md,.txt,text/plain,application/pdf,text/markdown"
              onChange={(event) => { addFileSource(event.target.files?.[0]); event.target.value = ""; }}
            />
          </Tabs.Panel>
          <Tabs.Panel className="tabs-panel" value="text">
            <textarea className="input" rows={4} placeholder="Paste notes, documentation, or any technical text here…" value={noteContent} onChange={(event) => setNoteContent(event.target.value)} autoComplete="off" />
            <Button className="button button-secondary" type="button" onClick={addTextSource}>Add as source</Button>
          </Tabs.Panel>
        </Tabs.Root>
      </div>

      {progress ? <p className="notice" role="status">{progress}</p> : null}
      {error ? <p className="error" role="alert">{error}</p> : null}
      <Button className="button" type="submit" disabled={loading} focusableWhenDisabled>{loading ? "Creating course…" : "Create course"}</Button>
    </form>
  );
}
