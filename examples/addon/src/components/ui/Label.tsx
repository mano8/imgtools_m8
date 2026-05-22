import { cva, type VariantProps } from "class-variance-authority"
import { forwardRef } from "preact/compat"
import type { LabelHTMLAttributes } from "preact/compat"

const labelVariants = cva(
  "text-md font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 block pb-3 pt-2 pl-1"
)

export interface LabelProps
    extends LabelHTMLAttributes<HTMLLabelElement>,
    VariantProps<typeof labelVariants> { }

const Label = forwardRef<HTMLLabelElement, LabelProps>(({ className, ...props }, ref) => (
    // biome-ignore lint/a11y/noLabelWithoutControl: htmlFor is passed via props spread by callers
    <label
        ref={ref}
        className={`${labelVariants()} ${className ?? ''}`}
        {...props}/>

))
Label.displayName = "Label"

export { Label }