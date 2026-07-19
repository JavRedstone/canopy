"use client";

import { FormEvent, SyntheticEvent, useState } from "react";
import { useRouter } from "next/navigation";
import Stack from "@mui/material/Stack";
import Box from "@mui/material/Box";
import TextField from "@mui/material/TextField";
import Button from "@mui/material/Button";
import Typography from "@mui/material/Typography";
import Slider from "@mui/material/Slider";
import Tabs from "@mui/material/Tabs";
import Tab from "@mui/material/Tab";
import Alert from "@mui/material/Alert";
import List from "@mui/material/List";
import ListItem from "@mui/material/ListItem";
import ListItemText from "@mui/material/ListItemText";
import IconButton from "@mui/material/IconButton";
import { Icon } from "@/components/icon";
import { createClient } from "@/lib/supabase/client";
import { APPLY_COLOR, UNDERSTAND_COLOR } from "@/lib/palette";

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
  const [lessonMin, setLessonMin] = useState(12);
  const [lessonMax, setLessonMax] = useState(20);
  const [quizMaxAttempts, setQuizMaxAttempts] = useState(3);
  const [sourceTab, setSourceTab] = useState<"file" | "text">("file");
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

  function handleLessonRangeChange(_event: Event, value: number | number[]) {
    if (!Array.isArray(value)) return;
    const [min, max] = value;
    // Base UI's Slider had `minStepsBetweenValues={1}` to keep the two thumbs from
    // colliding; MUI's Slider has no direct equivalent, so clamp here instead.
    setLessonMin(Math.min(min, max - 1));
    setLessonMax(Math.max(max, min + 1));
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
      const courseResponse = await fetch(`${apiUrl}/api/v1/courses`, { method: "POST", headers, body: JSON.stringify({ title, goal, source_ids: sourceIds, lesson_min: lessonMin, lesson_max: lessonMax, quiz_max_attempts: quizMaxAttempts }) });
      if (!courseResponse.ok) throw new Error("Unable to create your course.");
      router.push("/courses"); router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to create the course.");
    } finally { setLoading(false); setProgress(undefined); }
  }

  return (
    <Stack component="form" sx={{ gap: 3, maxWidth: 560, mt: 3 }} onSubmit={handleSubmit}>
      <TextField label="Course title" id="course-title" value={title} onChange={(event) => setTitle(event.target.value)} autoComplete="off" required fullWidth />
      <TextField
        label="What do you want to learn?"
        id="course-goal"
        multiline
        rows={4}
        value={goal}
        onChange={(event) => setGoal(event.target.value)}
        autoComplete="off"
        required
        fullWidth
      />

      <Box>
        <Typography gutterBottom>
          Activity range <Typography component="span" sx={{ fontWeight: 700 }}>{lessonMin}–{lessonMax} activities</Typography>
        </Typography>
        <Slider
          value={[lessonMin, lessonMax]}
          onChange={handleLessonRangeChange}
          min={6}
          max={24}
          step={1}
          disableSwap
          getAriaLabel={(index) => (index === 0 ? "Minimum lessons" : "Maximum lessons")}
          sx={{ mt: 2 }}
        />
        <Stack direction="row" sx={{ justifyContent: "space-between", color: "text.secondary", fontSize: "0.75rem" }}>
          <span>One topic<br />6 activities</span>
          <span>Deep dive<br />24 lessons</span>
        </Stack>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>Each topic includes several short lectures, focused labs, and a final assessment.</Typography>
      </Box>

      <TextField
        label="Quiz attempts per question"
        id="quiz-max-attempts"
        type="number"
        slotProps={{ htmlInput: { min: 1, max: 10 } }}
        value={quizMaxAttempts}
        onChange={(event) => setQuizMaxAttempts(Math.max(1, Math.min(10, Number(event.target.value) || 1)))}
        helperText="How many tries a learner gets on each mastery-check question before it locks. Default 3."
        fullWidth
      />

      {sources.length > 0 ? (
        <Box>
          <Typography gutterBottom>Sources added</Typography>
          <List disablePadding sx={{ display: "grid", gap: 1 }}>
            {sources.map((source) => (
              <ListItem
                key={source.id}
                sx={{ border: 1, borderColor: "divider", borderRadius: 1.5 }}
                secondaryAction={
                  <IconButton edge="end" aria-label="Remove source" onClick={() => removeSource(source.id)}>
                    <Icon name="close" />
                  </IconButton>
                }
              >
                <ListItemText primary={pendingSourceLabel(source)} />
              </ListItem>
            ))}
          </List>
        </Box>
      ) : null}

      <Box>
        <Typography gutterBottom>Add sources (optional)</Typography>
        <Tabs value={sourceTab} onChange={(_event: SyntheticEvent, value: "file" | "text") => setSourceTab(value)}>
          <Tab value="file" icon={<Icon name="upload_file" />} iconPosition="start" label="Upload file" sx={{ color: sourceTab === "file" ? UNDERSTAND_COLOR : undefined }} />
          <Tab value="text" icon={<Icon name="article" />} iconPosition="start" label="Paste text" sx={{ color: sourceTab === "text" ? APPLY_COLOR : undefined }} />
        </Tabs>
        {sourceTab === "file" ? (
          <Stack direction="row" sx={{ alignItems: "center", gap: 1.5, mt: 2 }}>
            <Button variant="outlined" component="label">
              Choose file
              <input
                hidden
                id="source-file"
                type="file"
                accept=".pdf,.md,.txt,text/plain,application/pdf,text/markdown"
                onChange={(event) => { addFileSource(event.target.files?.[0]); event.target.value = ""; }}
              />
            </Button>
            <Typography variant="body2" color="text.secondary">PDF, Markdown, or text, up to 6 MB</Typography>
          </Stack>
        ) : (
          <Stack sx={{ gap: 1.5, mt: 2 }}>
            <TextField
              multiline
              rows={4}
              placeholder="Paste notes, documentation, or any technical text here…"
              value={noteContent}
              onChange={(event) => setNoteContent(event.target.value)}
              autoComplete="off"
              fullWidth
            />
            <Button variant="outlined" type="button" onClick={addTextSource} sx={{ alignSelf: "flex-start" }}>Add as source</Button>
          </Stack>
        )}
      </Box>

      {progress ? <Alert severity="info" role="status">{progress}</Alert> : null}
      {error ? <Alert severity="error" role="alert">{error}</Alert> : null}
      <Button variant="contained" type="submit" disabled={loading} size="large">{loading ? "Creating course…" : "Create course"}</Button>
    </Stack>
  );
}
