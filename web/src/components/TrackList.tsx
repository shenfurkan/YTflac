import {
  List,
  ListItem,
  ListItemAvatar,
  ListItemText,
  Avatar,
  Typography,
  Paper,
  Box,
} from "@mui/material";
import type { PreviewTrack } from "../api";

function formatDuration(ms: number): string {
  if (ms <= 0) return "";
  const totalSec = Math.floor(ms / 1000);
  const min = Math.floor(totalSec / 60);
  const sec = totalSec % 60;
  return `${min}:${sec.toString().padStart(2, "0")}`;
}

interface Props {
  tracks: PreviewTrack[];
}

export default function TrackList({ tracks }: Props) {
  return (
    <Paper
      elevation={0}
      sx={{
        width: "100%",
        border: "1px solid rgba(255,255,255,0.06)",
        maxHeight: 420,
        overflow: "auto",
        "&::-webkit-scrollbar": { width: 4 },
        "&::-webkit-scrollbar-thumb": {
          bgcolor: "rgba(255,255,255,0.1)",
          borderRadius: 2,
        },
      }}
    >
      <List disablePadding>
        {tracks.map((track, idx) => (
          <ListItem
            key={track.id + idx}
            sx={{
              px: 2,
              py: 1,
              gap: 1.5,
              borderBottom: "1px solid rgba(255,255,255,0.04)",
              "&:last-child": { borderBottom: "none" },
              "&:hover": { bgcolor: "rgba(255,255,255,0.02)" },
            }}
          >
            <Typography
              variant="body2"
              sx={{
                width: 24,
                textAlign: "right",
                color: "rgba(255,255,255,0.3)",
                fontSize: "0.75rem",
                flexShrink: 0,
              }}
            >
              {idx + 1}
            </Typography>
            <ListItemAvatar sx={{ minWidth: 0 }}>
              <Avatar
                variant="rounded"
                src={track.cover}
                sx={{ width: 40, height: 40, borderRadius: 1.5 }}
              />
            </ListItemAvatar>
            <ListItemText
              primary={
                <Typography
                  variant="body1"
                  noWrap
                  sx={{ fontSize: "0.85rem", fontWeight: 500 }}
                >
                  {track.title}
                </Typography>
              }
              secondary={
                <Typography
                  variant="body2"
                  noWrap
                  sx={{ fontSize: "0.75rem" }}
                >
                  {track.artist}
                </Typography>
              }
              sx={{ minWidth: 0 }}
            />
            <Box sx={{ display: "flex", alignItems: "center", gap: 1, flexShrink: 0 }}>
              <Typography
                variant="body2"
                sx={{
                  fontSize: "0.75rem",
                  color: "rgba(255,255,255,0.35)",
                  fontVariantNumeric: "tabular-nums",
                }}
              >
                {formatDuration(track.duration_ms)}
              </Typography>
            </Box>
          </ListItem>
        ))}
      </List>
    </Paper>
  );
}
