import { loader } from '@monaco-editor/react'
import * as monaco from 'monaco-editor'

/**
 * Bundle Monaco locally (CAP-002, SPRINT-17) instead of `@monaco-editor/react`'s default
 * jsdelivr CDN loader — this is an offline Electron desktop app (ADR-002), so the editor must
 * never depend on network access at runtime. `monaco-editor` already ships a built-in `abap`
 * Monarch language (esm/vs/languages/definitions/abap), registered automatically by this import
 * — no custom tokenizer needed.
 *
 * No web worker is wired up: neither the documented `?worker` suffix import nor
 * `new URL(..., import.meta.url)` resolves through electron-vite's Rollup build for a module
 * this deep inside node_modules (tried both — see git history). Monaco falls back to running
 * its editor services on the main thread, logging one harmless console error per opened file;
 * functionally unaffected since this is a read-only viewer (readOnly+domReadOnly, no lint/format
 * language services) — acceptable for a lean PoC (ADR-011), not worth a heavier plugin dependency
 * to silence a console-only warning. See BACKLOG.md.
 */
loader.config({ monaco })
