import { useState } from "react";
import {
  Box,
  Container,
  Typography,
  Stack,
} from "@mui/material";
import UrlInputBar from "./components/UrlInputBar";
import PlaylistHeader from "./components/PlaylistHeader";
import TrackList from "./components/TrackList";
import DownloadPanel from "./components/DownloadPanel";
import UnmatchedDialog from "./components/UnmatchedDialog";
import type { PreviewResponse } from "./api";

export default function App() {
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [services, setServices] = useState<string[]>(["tidal"]);
  const [unmatchedOpen, setUnmatchedOpen] = useState(false);
  const [inputUrl, setInputUrl] = useState("");

  return (
    <Box sx={{ minHeight: "100vh", bgcolor: "background.default", py: 4 }}>
      <Container maxWidth="sm">
        <Stack spacing={3} alignItems="center">
          {/* Logo / Title */}
          <Typography variant="h5" color="primary" sx={{ letterSpacing: -0.5 }}>
            SpotiFLAC
          </Typography>
          <Typography variant="body2" textAlign="center" sx={{ mt: -2 }}>
            Paste a Spotify or YouTube Music URL to preview and download
          </Typography>

          {/* URL Input */}
          <UrlInputBar
            onPreview={(data, url) => { setPreview(data); setInputUrl(url); }}
            loading={loading}
            setLoading={setLoading}
            services={services}
            setServices={setServices}
          />

          {/* Results */}
          {preview && (
            <>
              <PlaylistHeader
                name={preview.name}
                cover={preview.cover}
                count={preview.tracks.length}
                type={preview.type}
                unmatchedCount={preview.unmatched.length}
                onShowUnmatched={() => setUnmatchedOpen(true)}
              />
              <TrackList tracks={preview.tracks} />
              <DownloadPanel
                url={inputUrl}
                services={services}
                preview={preview}
              />
              <UnmatchedDialog
                open={unmatchedOpen}
                onClose={() => setUnmatchedOpen(false)}
                items={preview.unmatched}
              />
            </>
          )}
        </Stack>
      </Container>
    </Box>
  );
}
