import '@testing-library/jest-dom'

// Mock browser APIs not available in jsdom
beforeAll(() => {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }),
  })

  // Mock clipboard API
  Object.defineProperty(navigator, 'clipboard', {
    writable: true,
    value: { writeText: () => Promise.resolve() },
  })

  // Mock scrollTo
  window.scrollTo = () => {}
})

afterAll(() => {
  vi.clearAllMocks()
})
