import { create } from 'zustand'
import { devtools, persist } from 'zustand/middleware'

interface UIStore {
  // Sidebar state
  sidebarOpen: boolean
  sidebarWidth: number

  // Theme
  themeMode: 'light' | 'dark'
  primaryColor: string

  // Layout preferences
  chatLayout: 'split' | 'single' | 'focus'
  messageDensity: 'compact' | 'comfortable' | 'spacious'

  // Notification preferences
  showNotifications: boolean
  notificationSound: boolean
  desktopNotifications: boolean

  // Chat preferences
  autoScroll: boolean
  showTimestamps: boolean
  showAvatars: boolean
  markdownRendering: boolean

  // Agent preferences
  defaultAgentId: string | null
  autoSelectAgent: boolean
  showAgentStatus: boolean

  // Actions
  toggleSidebar: () => void
  setSidebarOpen: (open: boolean) => void
  setSidebarWidth: (width: number) => void

  toggleTheme: () => void
  setThemeMode: (mode: 'light' | 'dark') => void
  setPrimaryColor: (color: string) => void

  setChatLayout: (layout: 'split' | 'single' | 'focus') => void
  setMessageDensity: (density: 'compact' | 'comfortable' | 'spacious') => void

  setShowNotifications: (show: boolean) => void
  setNotificationSound: (sound: boolean) => void
  setDesktopNotifications: (notifications: boolean) => void

  setAutoScroll: (auto: boolean) => void
  setShowTimestamps: (show: boolean) => void
  setShowAvatars: (show: boolean) => void
  setMarkdownRendering: (rendering: boolean) => void

  setDefaultAgentId: (agentId: string | null) => void
  setAutoSelectAgent: (auto: boolean) => void
  setShowAgentStatus: (show: boolean) => void

  // Reset
  resetPreferences: () => void
}

const defaultState = {
  sidebarOpen: true,
  sidebarWidth: 280,

  themeMode: 'light' as const,
  primaryColor: '#1976d2',

  chatLayout: 'split' as const,
  messageDensity: 'comfortable' as const,

  showNotifications: true,
  notificationSound: true,
  desktopNotifications: false,

  autoScroll: true,
  showTimestamps: true,
  showAvatars: true,
  markdownRendering: true,

  defaultAgentId: null,
  autoSelectAgent: true,
  showAgentStatus: true,
}

const useUIStore = create<UIStore>()(
  devtools(
    persist(
      (set) => ({
        ...defaultState,

        // Sidebar actions
        toggleSidebar: () =>
          set((state) => ({ sidebarOpen: !state.sidebarOpen })),
        setSidebarOpen: (open) => set({ sidebarOpen: open }),
        setSidebarWidth: (width) => set({ sidebarWidth: width }),

        // Theme actions
        toggleTheme: () =>
          set((state) => ({
            themeMode: state.themeMode === 'light' ? 'dark' : 'light',
          })),
        setThemeMode: (mode) => set({ themeMode: mode }),
        setPrimaryColor: (color) => set({ primaryColor: color }),

        // Layout actions
        setChatLayout: (layout) => set({ chatLayout: layout }),
        setMessageDensity: (density) => set({ messageDensity: density }),

        // Notification actions
        setShowNotifications: (show) => set({ showNotifications: show }),
        setNotificationSound: (sound) => set({ notificationSound: sound }),
        setDesktopNotifications: (notifications) =>
          set({ desktopNotifications: notifications }),

        // Chat actions
        setAutoScroll: (auto) => set({ autoScroll: auto }),
        setShowTimestamps: (show) => set({ showTimestamps: show }),
        setShowAvatars: (show) => set({ showAvatars: show }),
        setMarkdownRendering: (rendering) => set({ markdownRendering: rendering }),

        // Agent actions
        setDefaultAgentId: (agentId) => set({ defaultAgentId: agentId }),
        setAutoSelectAgent: (auto) => set({ autoSelectAgent: auto }),
        setShowAgentStatus: (show) => set({ showAgentStatus: show }),

        // Reset
        resetPreferences: () => set(defaultState),
      }),
      {
        name: 'ui-preferences',
        partialize: (state) => ({
          themeMode: state.themeMode,
          primaryColor: state.primaryColor,
          chatLayout: state.chatLayout,
          messageDensity: state.messageDensity,
          showNotifications: state.showNotifications,
          notificationSound: state.notificationSound,
          desktopNotifications: state.desktopNotifications,
          autoScroll: state.autoScroll,
          showTimestamps: state.showTimestamps,
          showAvatars: state.showAvatars,
          markdownRendering: state.markdownRendering,
          defaultAgentId: state.defaultAgentId,
          autoSelectAgent: state.autoSelectAgent,
          showAgentStatus: state.showAgentStatus,
        }),
      }
    ),
    {
      name: 'UIStore',
    }
  )
)

export default useUIStore