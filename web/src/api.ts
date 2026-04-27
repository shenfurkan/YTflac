import axios from "axios";

const client = axios.create({ baseURL: "/api" });

export interface PreviewTrack {
  id: string;
  title: string;
  artist: string;
  album: string;
  cover: string;
  duration_ms: number;
  source: string;
}

export interface PreviewResponse {
  type: string;
  name: string;
  cover: string;
  tracks: PreviewTrack[];
  unmatched: string[];
}

export interface JobStatus {
  id: string;
  state: "pending" | "running" | "completed" | "failed";
  current: number;
  total: number;
  succeeded: number;
  failed: number;
  errors: { title: string; artist: string; error: string }[];
}

export async function fetchPreview(url: string): Promise<PreviewResponse> {
  const { data } = await client.post<PreviewResponse>("/preview", { url });
  return data;
}

export async function startDownload(
  url: string,
  services: string[] = ["tidal"],
  outputDir = "./downloads"
): Promise<string> {
  const { data } = await client.post<{ job_id: string }>("/download", {
    url,
    services,
    output_dir: outputDir,
  });
  return data.job_id;
}

export async function getJobStatus(jobId: string): Promise<JobStatus> {
  const { data } = await client.get<JobStatus>(`/jobs/${jobId}`);
  return data;
}
