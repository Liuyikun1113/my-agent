import React, { useState } from 'react'
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Button,
  Typography,
  Box,
  Chip,
} from '@mui/material'
import AddIcon from '@mui/icons-material/Add'

interface NewSessionModalProps {
  open: boolean
  onClose: () => void
  onCreate: (title?: string, description?: string) => Promise<void>
}

const suggestedTitles = [
  'Code Review Session',
  'Research & Analysis',
  'Task Planning',
  'Debug Help',
  'General Chat',
]

const NewSessionModal: React.FC<NewSessionModalProps> = ({ open, onClose, onCreate }) => {
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [creating, setCreating] = useState(false)

  const handleCreate = async () => {
    setCreating(true)
    try {
      await onCreate(title || undefined, description || undefined)
      setTitle('')
      setDescription('')
      onClose()
    } catch (err) {
      console.error('Failed to create session:', err)
    } finally {
      setCreating(false)
    }
  }

  const handleSuggestedTitle = (suggested: string) => {
    setTitle(suggested)
  }

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <AddIcon />
          <Typography variant="h6">New Session</Typography>
        </Box>
      </DialogTitle>

      <DialogContent>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1 }}>
          <TextField
            label="Session Title"
            placeholder="Enter a descriptive title..."
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            fullWidth
            autoFocus
            onKeyDown={(e) => {
              if (e.key === 'Enter' && title.trim()) handleCreate()
            }}
          />

          <TextField
            label="Description (optional)"
            placeholder="What is this session about?"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            fullWidth
            multiline
            minRows={2}
            maxRows={4}
          />

          {/* Suggested titles */}
          <Box>
            <Typography variant="caption" color="text.secondary" sx={{ mb: 0.5, display: 'block' }}>
              Quick start:
            </Typography>
            <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
              {suggestedTitles.map((suggested) => (
                <Chip
                  key={suggested}
                  label={suggested}
                  size="small"
                  variant="outlined"
                  onClick={() => handleSuggestedTitle(suggested)}
                  sx={{ cursor: 'pointer' }}
                />
              ))}
            </Box>
          </Box>
        </Box>
      </DialogContent>

      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose} disabled={creating}>
          Cancel
        </Button>
        <Button
          onClick={handleCreate}
          variant="contained"
          disabled={!title.trim() || creating}
          startIcon={<AddIcon />}
        >
          {creating ? 'Creating...' : 'Create Session'}
        </Button>
      </DialogActions>
    </Dialog>
  )
}

export default NewSessionModal
