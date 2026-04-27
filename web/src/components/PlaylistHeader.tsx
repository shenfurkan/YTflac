import {
  Box,
  Typography,
  Chip,
  Avatar,
  Button,
} from "@mui/material";
import WarningAmberIcon from "@mui/icons-material/WarningAmber";

interface Props {
  name: string;
  cover: string;
  count: number;
  type: string;
  unmatchedCount: number;
  onShowUnmatched: () => void;
}

export default function PlaylistHeader({
  name,
  cover,
  count,
  type,
  unmatchedCount,
  onShowUnmatched,
}: Props) {
  return (
    <Box
      sx={{
        width: "100%",
        display: "flex",
        alignItems: "center",
        gap: 2,
        p: 2,
        borderRadius: 3,
        bgcolor: "background.paper",
        border: "1px solid rgba(255,255,255,0.06)",
      }}
    >
      <Avatar
        variant="rounded"
        src={cover}
        sx={{ width: 72, height: 72, borderRadius: 2 }}
      />
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Typography
          variant="h6"
          noWrap
          sx={{ fontSize: "1rem", lineHeight: 1.3 }}
        >
          {name}
        </Typography>
        <Box sx={{ display: "flex", gap: 1, mt: 0.5, alignItems: "center" }}>
          <Chip
            label={type === "playlist" ? "Playlist" : "Track"}
            size="small"
            sx={{
              height: 22,
              fontSize: "0.7rem",
              bgcolor: "rgba(123,151,237,0.15)",
              color: "primary.main",
            }}
          />
          <Typography variant="body2" sx={{ fontSize: "0.8rem" }}>
            {count} track{count !== 1 && "s"}
          </Typography>
          {unmatchedCount > 0 && (
            <Button
              size="small"
              startIcon={<WarningAmberIcon sx={{ fontSize: 14 }} />}
              onClick={onShowUnmatched}
              sx={{
                fontSize: "0.7rem",
                color: "warning.main",
                textTransform: "none",
                p: 0,
                minWidth: 0,
              }}
            >
              {unmatchedCount} unmatched
            </Button>
          )}
        </Box>
      </Box>
    </Box>
  );
}
