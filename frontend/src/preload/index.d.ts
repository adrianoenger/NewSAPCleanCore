export {}

declare global {
  interface Window {
    desktop?: {
      platform: string
      versions: { electron: string; chrome: string }
    }
  }
}
