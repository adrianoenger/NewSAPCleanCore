export {}

declare global {
  interface Window {
    desktop?: {
      platform: string
      versions: { electron: string; chrome: string }
      selectDirectory: () => Promise<string | null>
      getProjectRoot: () => Promise<string>
    }
  }
}
