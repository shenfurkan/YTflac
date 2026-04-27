import { useState } from "react";
import {
  Box,
  TextField,
  Button,
  ToggleButtonGroup,
  ToggleButton,
  CircularProgress,
  Paper,
} from "@mui/material";
import SearchIcon from "@mui/icons-material/Search";
import { fetchPreview, type PreviewResponse } from "../api";

interface Props {
  onPreview: (data: PreviewResponse, url: string) => void;
  loading: boolean;
  setLoading: (v: boolean) => void;
  services: string[];
  setServices: (v: string[]) => void;
}

const SERVICE_OPTIONS = [
  { value: "tidal", label: "Tidal" },
  { value: "qobuz", label: "Qobuz" },
  { value: "amazon", label: "Amazon" },
  { value: "deezer", label: "Deezer" },
  { value: "youtube", label: "YouTube" },
];

export default function UrlInputBar({
  onPreview,
  loading,
  setLoading,
  services,
  setServices,
}: Props) {
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");

  const handlePreview = async () => {
    if (!url.trim()) return;
    setError("");
    setLoading(true);
    try {
      const trimmed = url.trim();
      const data = await fetchPreview(trimmed);
      onPreview(data, trimmed);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || "Preview failed");
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handlePreview();
  };

  const handleServiceChange = (
    _: React.MouseEvent<HTMLElement>,
    newServices: string[]
  ) => {
    if (newServices.length) setServices(newServices);
  };

  return (
    <Paper
      elevation={0}
      sx={{
        width: "100%",
        p: 2.5,
        display: "flex",
        flexDirection: "column",
        gap: 2,
        border: "1px solid rgba(255,255,255,0.06)",
      }}
    >
      <Box sx={{ display: "flex", gap: 1 }}>
        <TextField
          fullWidth
          size="small"
          placeholder="https://open.spotify.com/... or music.youtube.com/..."
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          onKeyDown={handleKeyDown}
          error={!!error}
          helperText={error}
          sx={{
            "& .MuiOutlinedInput-root": {
              bgcolor: "rgba(255,255,255,0.03)",
            },
          }}
        />
        <Button
          variant="contained"
          onClick={handlePreview}
          disabled={loading || !url.trim()}
          sx={{ minWidth: 100, height: 40 }}
        >
          {loading ? (
            <CircularProgress size={20} color="inherit" />
          ) : (
            <>
              <SearchIcon sx={{ mr: 0.5, fontSize: 18 }} />
              Preview
            </>
          )}
        </Button>
      </Box>

      <ToggleButtonGroup
        value={services}
        onChange={handleServiceChange}
        size="small"
        sx={{
          flexWrap: "wrap",
          gap: 0.5,
          "& .MuiToggleButton-root": {
            px: 1.5,
            py: 0.4,
            fontSize: "0.75rem",
            borderRadius: "8px !important",
            border: "1px solid rgba(255,255,255,0.08) !important",
            textTransform: "none",
            "&.Mui-selected": {
              bgcolor: "primary.main",
              color: "#fff",
              "&:hover": { bgcolor: "primary.dark" },
            },
          },
        }}
      >
        {SERVICE_OPTIONS.map((s) => (
          <ToggleButton key={s.value} value={s.value}>
            {s.label}
          </ToggleButton>
        ))}
      </ToggleButtonGroup>
    </Paper>
  );
}
