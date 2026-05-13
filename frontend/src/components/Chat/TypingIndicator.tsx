import React from 'react'
import { Box, Typography } from '@mui/material'
import { keyframes } from '@mui/system'

const blink = keyframes`
  0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
  40% { opacity: 1; transform: scale(1); }
`

interface TypingIndicatorProps {
  text?: string
}

const TypingIndicator: React.FC<TypingIndicatorProps> = ({ text = 'AI is thinking' }) => {
  return (
    <Box
      sx={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 0.5,
        px: 2,
        py: 1,
        borderRadius: 2,
        bgcolor: 'grey.100',
        border: '1px solid',
        borderColor: 'divider',
      }}
    >
      <Typography variant="body2" color="text.secondary" sx={{ mr: 0.5 }}>
        {text}
      </Typography>
      {[0, 1, 2].map((i) => (
        <Box
          key={i}
          sx={{
            width: 6,
            height: 6,
            borderRadius: '50%',
            bgcolor: 'primary.main',
            animation: `${blink} 1.4s infinite`,
            animationDelay: `${i * 0.2}s`,
          }}
        />
      ))}
    </Box>
  )
}

export default TypingIndicator
