import { cva, type VariantProps } from "class-variance-authority"
import { forwardRef, HTMLAttributes } from "preact/compat"
import { Separator } from "./Separator"

const InputDescriptionVariants = cva(
  "text-md font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 block py-3 pl-1"
)

export interface InputDescriptionProps
    extends HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof InputDescriptionVariants> { 
      separators?: boolean
    }

const InputDescription = forwardRef<HTMLDivElement, InputDescriptionProps>((
  { 
    separators=false,
    className,
    ...props
  }, ref) => {
    
    const obj = (
      <div
          ref={ref}
          className={`${InputDescriptionVariants()} ${className ?? ''}`}
          {...props}/>
  
    )

    if(separators === true){
      return [
        <Separator className="mt-4" />,
        obj,
        <Separator className="mb-4" />
      ]
    }

    return obj;
})
InputDescription.displayName = "InputDescription"

export { InputDescription }