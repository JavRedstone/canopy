export type CourseStatus = "draft" | "ready" | "archived";
export type SourceStatus = "uploading" | "uploaded" | "ingesting" | "ready" | "failed";

export interface CreateCourseRequest {
  title: string;
  goal: string;
  sourceIds: string[];
}

export interface CourseSummary {
  id: string;
  title: string;
  goal: string;
  status: CourseStatus;
  activeVersion: number;
  updatedAt: string;
}

export interface CreateSourceRequest {
  filename: string;
  mimeType: string;
  byteSize: number;
}

export interface SourceUploadTarget {
  id: string;
  storagePath: string;
  uploadToken: string;
  status: SourceStatus;
}
