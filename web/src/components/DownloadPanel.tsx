import { useState, useEffect, useCallback } from "react";
import {
  Box,
  Button,
  LinearProgress,
  Typography,
  Paper,
  Collapse,
} from "@mui/material";
import DownloadIcon from "@mui/icons-material/Download";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import ErrorOutlineIcon from "@mui/icons-material/ErrorOutline";
import { startDownload, getJobStatus, type PreviewResponse, type JobStatus } from "../api";

interface Props {
  url: string;
  services: string[];
  preview: PreviewResponse;
}

export default function DownloadPanel({ url, services, preview }: Props) {
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<JobStatus | null>(null);
  const [starting, setStarting] = useState(false);

  const handleStart = async () => {
    if (!preview.tracks.length) return;
    setStarting(true);
    try {
      const id = await startDownload(url, services);
      setJobId(id);
    } catch {
      // error handled below
    } finally {
      setStarting(false);
    }
  };

  const poll = useCallback(async () => {
    if (!jobId) return;
    try {
      const s = await getJobStatus(jobId);
      setStatus(s);
    } catch {
      // ignore
    }
  }, [jobId]);

  useEffect(() => {
    if (!jobId) return;
    const interval = setInterval(poll, 1500);
    poll();
    return () => clearInterval(interval);
  }, [jobId, poll]);

  const isDone = status?.state === "completed" || status?.state === "failed";
  const progress =
    status && status.total > 0
      ? Math.round((status.current / status.total) * 100)
      : 0;

  return (
    <Paper
      elevation={0}
      sx={{
        width: "100%",
        p: 2,
        border: "1px solid rgba(255,255,255,0.06)",
      }}
    >
      {!jobId ? (
        <Button
          fullWidth
          variant="contained"
          size="large"
          startIcon={<DownloadIcon />}
          onClick={handleStart}
          disabled={starting || !preview.tracks.length}
          sx={{ py: 1.2 }}
        >
          {starting
            ? "Starting..."
            : `Download ${preview.tracks.length} track${preview.tracks.length !== 1 ? "s" : ""}`}
        </Button>
      ) : (
        <Box>
          <Box sx={{ display: "flex", justifyContent: "space-between", mb: 1 }}>
            <Typography variant="body2" sx={{ fontSize: "0.8rem" }}>
              {isDone ? (
                status?.state === "completed" ? (
                  <Box component="span" sx={{ display: "flex", alignItems: "center", gap: 0.5, color: "success.main" }}>
                    <CheckCircleIcon sx={{ fontSize: 16 }} /> Completed
                  </Box>
                ) : (
                  <Box component="span" sx={{ display: "flex", alignItems: "center", gap: 0.5, color: "error.main" }}>
                    <ErrorOutlineIcon sx={{ fontSize: 16 }} /> Failed
                  </Box>
                )
              ) : (
                "Downloading..."
              )}
            </Typography>
            <Typography variant="body2" sx={{ fontSize: "0.8rem", color: "rgba(255,255,255,0.5)" }}>
              {status ? `${status.succeeded}/${status.total}` : "..."}
            </Typography>
          </Box>
          <LinearProgress
            variant="determinate"
            value={progress}
            sx={{
              height: 6,
              borderRadius: 3,
              bgcolor: "rgba(255,255,255,0.05)",
              "& .MuiLinearProgress-bar": { borderRadius: 3 },
            }}
          />
          <Collapse in={!!status?.errors.length}>
            <Box sx={{ mt: 1.5 }}>
              {status?.errors.slice(0, 5).map((e, i) => (
                <Typography
                  key={i}
                  variant="body2"
                  sx={{ fontSize: "0.7rem", color: "error.light", mb: 0.3 }}
                >
                  {e.title} — {e.error}
                </Typography>
              ))}
            </Box>
          </Collapse>
        </Box>
      )}
    </Paper>
  );
}
