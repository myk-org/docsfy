import { mergeProps } from "@base-ui/react/merge-props"
import { useRender } from "@base-ui/react/use-render"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "group/badge inline-flex h-5 w-fit shrink-0 items-center justify-center gap-1 overflow-hidden rounded-4xl border border-transparent px-2 py-0.5 text-xs font-medium whitespace-nowrap transition-all focus-visible:border-border-accent focus-visible:ring-[3px] focus-visible:ring-border-accent/50 has-data-[icon=inline-end]:pr-1.5 has-data-[icon=inline-start]:pl-1.5 aria-invalid:border-signal-red aria-invalid:ring-signal-red/20 [&>svg]:pointer-events-none [&>svg]:size-3!",
  {
    variants: {
      variant: {
        default: "bg-signal-blue/15 text-signal-blue [a]:hover:bg-signal-blue/25",
        secondary:
          "bg-surface-elevated text-text-primary [a]:hover:bg-surface-hover",
        destructive:
          "bg-signal-red/15 text-signal-red focus-visible:ring-signal-red/20 [a]:hover:bg-signal-red/25",
        outline:
          "border-border-default text-text-secondary [a]:hover:bg-surface-hover [a]:hover:text-text-secondary",
        ghost:
          "hover:bg-surface-hover hover:text-text-secondary",
        link: "text-text-link underline-offset-4 hover:underline",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

function Badge({
  className,
  variant = "default",
  render,
  ...props
}: useRender.ComponentProps<"span"> & VariantProps<typeof badgeVariants>) {
  return useRender({
    defaultTagName: "span",
    props: mergeProps<"span">(
      {
        className: cn(badgeVariants({ variant }), className),
      },
      props
    ),
    render,
    state: {
      slot: "badge",
      variant,
    },
  })
}

export { Badge, badgeVariants }
