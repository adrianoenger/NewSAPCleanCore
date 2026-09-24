// Desktop shell smoke test (SPRINT-00 primary flow).
// Launches the built Electron app with remote debugging, then over CDP verifies the three
// permanent shell regions and that the backend/database health is rendered as online.
// Requires the backend stack running (`docker compose up -d`). Screenshot: test-results/shell.png
import { spawn } from 'node:child_process'
import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import electronPath from 'electron'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const port = 9333
const timeoutMs = 30_000
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

const app = spawn(electronPath, ['.', `--remote-debugging-port=${port}`], {
  cwd: root,
  stdio: 'ignore',
  env: { ...process.env, ELECTRON_RENDERER_URL: '' }
})

async function waitFor(fn, label) {
  const deadline = Date.now() + timeoutMs
  let last
  while (Date.now() < deadline) {
    try {
      last = await fn()
      if (last) return last
    } catch (error) {
      last = error
    }
    await sleep(500)
  }
  throw new Error(`Timed out waiting for ${label} (last: ${JSON.stringify(last)})`)
}

function connect(wsUrl) {
  const ws = new WebSocket(wsUrl)
  let nextId = 1
  const pending = new Map()
  ws.addEventListener('message', (event) => {
    const message = JSON.parse(event.data)
    pending.get(message.id)?.(message)
    pending.delete(message.id)
  })
  const send = (method, params = {}) =>
    new Promise((resolve) => {
      const id = nextId++
      pending.set(id, resolve)
      ws.send(JSON.stringify({ id, method, params }))
    })
  return new Promise((resolve) => ws.addEventListener('open', () => resolve({ ws, send })))
}

const PROBE = `(() => {
  const region = (name) => document.querySelector('[data-region="' + name + '"]')
  const indicator = document.querySelector('[data-testid="connection-indicator"]')
  return JSON.stringify({
    sidebar: !!region('sidebar'),
    workspace: !!region('workspace'),
    copilot: !!region('copilot'),
    connectivity: indicator?.dataset.connectivity ?? null,
    health: document.querySelector('[data-testid="health-card"]')?.innerText ?? ''
  })
})()`

let exitCode = 1
try {
  const target = await waitFor(async () => {
    const targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json()
    return targets.find((t) => t.type === 'page')
  }, 'Electron window')
  const { ws, send } = await connect(target.webSocketDebuggerUrl)

  const state = await waitFor(async () => {
    const { result } = await send('Runtime.evaluate', { expression: PROBE })
    const probe = JSON.parse(result.result.value)
    return probe.connectivity === 'online' && probe ? probe : false
  }, 'connectivity=online')

  const checks = {
    'sidebar region rendered': state.sidebar,
    'workspace region rendered': state.workspace,
    'copilot region rendered': state.copilot,
    'backend online': state.connectivity === 'online',
    'pgvector reported': /pgvector\s+true/.test(state.health),
    'schema revision reported': /0001_foundation/.test(state.health)
  }

  const { result: shot } = await send('Page.captureScreenshot', { format: 'png' })
  const out = join(root, 'test-results', 'shell.png')
  mkdirSync(dirname(out), { recursive: true })
  writeFileSync(out, Buffer.from(shot.data, 'base64'))
  ws.close()

  for (const [name, ok] of Object.entries(checks)) console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}`)
  console.log(`screenshot: ${out}`)
  exitCode = Object.values(checks).every(Boolean) ? 0 : 1
} catch (error) {
  console.error(`FAIL  ${error.message}`)
} finally {
  app.kill()
  process.exit(exitCode)
}
