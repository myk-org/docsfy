import * as React from "react"
import { Input as InputPrimitive } from "@base-ui/react/input"

import { cn } from "@/lib/utils"

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <InputPrimitive
      type={type}
      data-slot="input"
      className={cn(
        "h-8 w-full min-w-0 rounded-lg border border-border-default bg-surface-elevated px-2.5 py-1 text-base transition-colors outline-none file:inline-flex file:h-6 file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-text-primary placeholder:text-text-tertiary hover:bg-surface-hover focus-visible:border-border-accent focus-visible:ring-3 focus-visible:ring-border-accent/50 disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50 aria-invalid:border-signal-red aria-invalid:ring-3 aria-invalid:ring-signal-red/20 md:text-sm",
        className
      )}
      {...props}
    />
  )
}

export { Input }
