import { cva, type VariantProps } from 'class-variance-authority'
import type { ButtonHTMLAttributes } from 'react'
import { cn } from '@/lib/utils'

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-1.5 rounded-control text-[12.5px] font-medium transition-colors disabled:pointer-events-none disabled:opacity-50',
  {
    variants: {
      variant: {
        primary: 'bg-brand text-text-primary hover:bg-brand-hover',
        secondary:
          'border border-border-default bg-transparent text-text-button hover:bg-surface-hover',
        ghost: 'text-text-secondary hover:bg-surface-hover hover:text-text-primary'
      },
      size: {
        sm: 'h-7 px-2.5',
        md: 'h-8 px-3',
        icon: 'h-7 w-7'
      }
    },
    defaultVariants: { variant: 'secondary', size: 'md' }
  }
)

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export function Button({ className, variant, size, ...props }: ButtonProps) {
  return <button className={cn(buttonVariants({ variant, size }), className)} {...props} />
}
