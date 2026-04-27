import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  List,
  ListItem,
  ListItemText,
  Typography,
} from "@mui/material";

interface Props {
  open: boolean;
  onClose: () => void;
  items: string[];
}

export default function UnmatchedDialog({ open, onClose, items }: Props) {
  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="xs"
      fullWidth
      PaperProps={{
        sx: { bgcolor: "background.paper", backgroundImage: "none" },
      }}
    >
      <DialogTitle sx={{ fontSize: "1rem", fontWeight: 600 }}>
        Unmatched Tracks
      </DialogTitle>
      <DialogContent dividers sx={{ p: 0 }}>
        {items.length === 0 ? (
          <Typography variant="body2" sx={{ p: 2 }}>
            All tracks were matched successfully.
          </Typography>
        ) : (
          <List dense disablePadding>
            {items.map((item, i) => (
              <ListItem
                key={i}
                sx={{
                  px: 2,
                  py: 0.8,
                  borderBottom: "1px solid rgba(255,255,255,0.04)",
                }}
              >
                <ListItemText
                  primary={item}
                  primaryTypographyProps={{ fontSize: "0.8rem", noWrap: true }}
                />
              </ListItem>
            ))}
          </List>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} size="small">
          Close
        </Button>
      </DialogActions>
    </Dialog>
  );
}
