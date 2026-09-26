import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * Persisted, drag-resizable panel width (CAP-001, SPRINT-17). `direction: 'left'` grows the
 * panel when the pointer moves right (e.g. the sidebar, dragging its own right edge);
 * `direction: 'right'` grows it when the pointer moves left (e.g. the Copilot, dragging its
 * own left edge).
 */
export function useResizableWidth(opts: {
  storageKey: string
  defaultWidth: number
  min: number
  max: number
  direction: 'left' | 'right'
}) {
  const { storageKey, defaultWidth, min, max, direction } = opts

  const [width, setWidth] = useState<number>(() => {
    const stored = Number(window.localStorage.getItem(storageKey))
    return Number.isFinite(stored) && stored > 0 ? clamp(stored, min, max) : defaultWidth
  })
  const [isDragging, setIsDragging] = useState(false)
  const startX = useRef(0)
  const startWidth = useRef(width)

  const onPointerDown = useCallback(
    (e: React.PointerEvent) => {
      startX.current = e.clientX
      startWidth.current = width
      setIsDragging(true)
    },
    [width],
  )

  useEffect(() => {
    if (!isDragging) return

    const onMove = (e: PointerEvent) => {
      const delta = e.clientX - startX.current
      const signed = direction === 'left' ? delta : -delta
      setWidth(clamp(startWidth.current + signed, min, max))
    }
    const onUp = () => setIsDragging(false)

    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
    return () => {
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
    }
  }, [isDragging, direction, min, max])

  useEffect(() => {
    if (!isDragging) window.localStorage.setItem(storageKey, String(width))
  }, [isDragging, storageKey, width])

  return { width, isDragging, onPointerDown }
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}
