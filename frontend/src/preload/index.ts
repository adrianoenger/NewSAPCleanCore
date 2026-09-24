import { contextBridge } from 'electron'

// Minimal, explicit bridge. Native capabilities (e.g. directory selection) are added per sprint.
contextBridge.exposeInMainWorld('desktop', {
  platform: process.platform,
  versions: {
    electron: process.versions.electron,
    chrome: process.versions.chrome
  }
})
