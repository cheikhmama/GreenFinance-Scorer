import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/shared/ui/cn"

/* Système « Registre » (tâche 5.15) : fond teinté et texte à 7:1 par statut, icône toujours
   doublée d'un titre. `default` reste neutre (carte), pour une information sans enjeu. */
const alertVariants = cva(
  "relative grid w-full grid-cols-[0_1fr] items-start gap-y-1 rounded-xl border px-[18px] py-4 text-sm has-[>svg]:grid-cols-[calc(var(--spacing)*5)_1fr] has-[>svg]:gap-x-3.5 [&>svg]:size-5 [&>svg]:translate-y-px [&>svg]:text-current",
  {
    variants: {
      variant: {
        default: "bg-card text-card-foreground",
        destructive:
          "border-danger-border bg-danger-soft text-danger *:data-[slot=alert-description]:text-danger",
        success:
          "border-success-border bg-success-soft text-success *:data-[slot=alert-description]:text-success",
        info: "border-info-border bg-info-soft text-info *:data-[slot=alert-description]:text-info",
        warning:
          "border-warning-border bg-warning-soft text-warning *:data-[slot=alert-description]:text-warning",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

function Alert({
  className,
  variant,
  ...props
}: React.ComponentProps<"div"> & VariantProps<typeof alertVariants>) {
  return (
    <div
      data-slot="alert"
      // Seule une erreur interrompt le lecteur d'écran ; le reste s'annonce poliment.
      role={variant === "destructive" ? "alert" : "status"}
      className={cn(alertVariants({ variant }), className)}
      {...props}
    />
  )
}

function AlertTitle({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="alert-title"
      className={cn(
        "col-start-2 min-h-4 text-[15px] font-semibold",
        className
      )}
      {...props}
    />
  )
}

function AlertDescription({
  className,
  ...props
}: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="alert-description"
      className={cn(
        "col-start-2 grid justify-items-start gap-1 text-sm text-muted-foreground [&_p]:leading-relaxed",
        className
      )}
      {...props}
    />
  )
}

export { Alert, AlertTitle, AlertDescription }
