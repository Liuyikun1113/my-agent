import React, { useState, useCallback, useEffect } from 'react'
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Box,
  Chip,
  Radio,
  RadioGroup,
  FormControlLabel,
  FormControl,
  TextField,
  LinearProgress,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Badge,
} from '@mui/material'
import WarningIcon from '@mui/icons-material/Warning'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import CancelIcon from '@mui/icons-material/Cancel'
import PendingIcon from '@mui/icons-material/Pending'
import useAgentStore from '@/stores/agentStore'
import { HumanInterventionResponse } from '@/types/agent'

const HumanIntervention: React.FC = () => {
  const {
    interventions,
    respondToIntervention,
    cancelIntervention,
    getActiveInterventions,
  } = useAgentStore()

  const activeInterventions = getActiveInterventions()
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [response, setResponse] = useState('')
  const [submitting, setSubmitting] = useState(false)

  // Auto-select first active intervention
  useEffect(() => {
    if (activeInterventions.length > 0 && !selectedId) {
      setSelectedId(activeInterventions[0].intervention_id)
    }
  }, [activeInterventions, selectedId])

  const selectedIntervention = selectedId ? interventions[selectedId] : null

  const handleApprove = useCallback(async () => {
    if (!selectedId) return
    setSubmitting(true)
    try {
      await respondToIntervention(selectedId, response || 'Approved')
      setResponse('')
      setSelectedId(null)
    } catch (err) {
      console.error('Failed to approve:', err)
    } finally {
      setSubmitting(false)
    }
  }, [selectedId, response, respondToIntervention])

  const handleReject = useCallback(async () => {
    if (!selectedId) return
    setSubmitting(true)
    try {
      await respondToIntervention(selectedId, response || 'Rejected')
      setResponse('')
      setSelectedId(null)
    } catch (err) {
      console.error('Failed to reject:', err)
    } finally {
      setSubmitting(false)
    }
  }, [selectedId, response, respondToIntervention])

  const handleCancel = useCallback(async () => {
    if (!selectedId) return
    try {
      await cancelIntervention(selectedId)
      setSelectedId(null)
    } catch (err) {
      console.error('Failed to cancel:', err)
    }
  }, [selectedId, cancelIntervention])

  if (activeInterventions.length === 0 && !selectedIntervention) {
    return null
  }

  return (
    <>
      {/* Floating badge for pending interventions */}
      {activeInterventions.length > 0 && !selectedId && (
        <Box
          sx={{
            position: 'fixed',
            bottom: 24,
            right: 24,
            zIndex: 2000,
          }}
        >
          <Button
            variant="contained"
            color="warning"
            startIcon={<WarningIcon />}
            onClick={() => setSelectedId(activeInterventions[0].intervention_id)}
            sx={{ borderRadius: 4, px: 3, py: 1.5 }}
          >
            <Badge badgeContent={activeInterventions.length} color="error" sx={{ mr: 1 }}>
              <PendingIcon />
            </Badge>
            {activeInterventions.length} Pending Intervention{activeInterventions.length !== 1 ? 's' : ''}
          </Button>
        </Box>
      )}

      {/* Intervention dialog */}
      <Dialog
        open={!!selectedId}
        onClose={() => setSelectedId(null)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle sx={{ bgcolor: 'warning.light', color: 'warning.contrastText' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <WarningIcon />
            <Typography variant="h6">Human Intervention Required</Typography>
          </Box>
        </DialogTitle>

        <DialogContent sx={{ mt: 2 }}>
          {selectedIntervention && (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              {/* Status and type */}
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Chip
                  label={selectedIntervention.status}
                  color={
                    selectedIntervention.status === 'pending'
                      ? 'warning'
                      : selectedIntervention.status === 'approved'
                      ? 'success'
                      : 'error'
                  }
                  size="small"
                />
                <Typography variant="body2" color="text.secondary">
                  ID: {selectedIntervention.intervention_id}
                </Typography>
              </Box>

              {/* Request message */}
              <Box sx={{ p: 2, bgcolor: 'grey.50', borderRadius: 1 }}>
                <Typography variant="body2" fontWeight="medium" sx={{ mb: 0.5 }}>
                  Request:
                </Typography>
                <Typography variant="body1">{selectedIntervention.request_message || 'No details'}</Typography>
              </Box>

              {/* User response */}
              <TextField
                label="Your response (optional)"
                placeholder="Provide context for your decision..."
                value={response}
                onChange={(e) => setResponse(e.target.value)}
                fullWidth
                multiline
                minRows={2}
                maxRows={4}
              />

              {/* Existing interventions list */}
              {activeInterventions.length > 1 && (
                <Box>
                  <Typography variant="body2" fontWeight="medium" sx={{ mb: 0.5 }}>
                    Other pending interventions ({activeInterventions.length - 1}):
                  </Typography>
                  <List dense>
                    {activeInterventions
                      .filter((i) => i.intervention_id !== selectedId)
                      .map((i) => (
                        <ListItem key={i.intervention_id}>
                          <ListItemIcon>
                            <PendingIcon fontSize="small" color="warning" />
                          </ListItemIcon>
                          <ListItemText
                            primary={i.intervention_type}
                            secondary={i.request_message?.slice(0, 60) + '...'}
                          />
                        </ListItem>
                      ))}
                  </List>
                </Box>
              )}
            </Box>
          )}
        </DialogContent>

        <DialogActions sx={{ px: 3, pb: 2, gap: 1 }}>
          <Button onClick={handleCancel} color="inherit" disabled={submitting}>
            Skip
          </Button>
          <Button
            onClick={handleReject}
            color="error"
            variant="outlined"
            startIcon={<CancelIcon />}
            disabled={submitting}
          >
            Reject
          </Button>
          <Button
            onClick={handleApprove}
            color="success"
            variant="contained"
            startIcon={<CheckCircleIcon />}
            disabled={submitting}
          >
            {submitting ? 'Processing...' : 'Approve'}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  )
}

export default HumanIntervention
