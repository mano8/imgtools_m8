import { cva, type VariantProps } from "class-variance-authority"
import { forwardRef, HTMLAttributes } from "preact/compat"

const SeparatorVariants = cva(
  "shrink-0 bg-border h-[1px] w-full"
)

export interface SeparatorProps
    extends HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof SeparatorVariants> { }

const Separator = forwardRef<HTMLDivElement, SeparatorProps>(({ className, ...props }, ref) => (
    <div
        ref={ref}
        className={`${SeparatorVariants()} ${className ?? ''}`}
        {...props}/>
  )
)
Separator.displayName = "Separator"

export { Separator }