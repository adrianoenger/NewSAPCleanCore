import { cn } from '@/lib/utils'

interface ResizeHandleProps {
  onPointerDown: (e: React.PointerEvent) => void
  isDragging: boolean
  label: string
}

/** Thin drag divider between shell regions (CAP-001, SPRINT-17). */
export function ResizeHandle({ onPointerDown, isDragging, label }: ResizeHandleProps) {
  return (
    <div
      role="separator"
      aria-orientation="vertical"
      aria-label={label}
      onPointerDown={onPointerDown}
      className={cn(
        'group relative w-1 shrink-0 cursor-col-resize select-none',
        isDragging ? 'bg-brand' : 'bg-transparent hover:bg-brand/40',
      )}
    >
      <div className="absolute inset-y-0 -left-1 -right-1" />
    </div>
  )
}
