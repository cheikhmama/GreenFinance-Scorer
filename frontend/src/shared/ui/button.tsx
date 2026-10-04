import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { Loader2 } from "lucide-react"
import { Slot } from "radix-ui"

import { cn } from "@/shared/ui/cn"

/* Système « Registre » (tâche 5.15) : 44 px par défaut (cible tactile), anneau de focus double
   (2 px fond + 2 px couleur, visible sur toute surface), état appuyé (descend d'1 px), état
   désactivé lisible plutôt que transparent. Une seule action pleine par vue : `default`. */
const buttonVariants = cva(
  "inline-flex shrink-0 items-center justify-center gap-2 rounded-lg text-[15px] font-semibold whitespace-nowrap transition-[background-color,border-color,color,box-shadow,transform] duration-[120ms] ease-(--ease-registre) outline-none select-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background active:translate-y-px disabled:pointer-events-none disabled:bg-muted disabled:text-muted-foreground disabled:shadow-none aria-busy:cursor-progress aria-invalid:border-destructive [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-[18px]",
  {
    variants: {
      variant: {
        default:
          "bg-primary text-primary-foreground hover:bg-[color-mix(in_oklab,var(--primary),black_22%)] hover:shadow-(--shadow-e2) active:bg-[color-mix(in_oklab,var(--primary),black_38%)] dark:hover:bg-[color-mix(in_oklab,var(--primary),white_12%)]",
        destructive:
          "bg-destructive text-destructive-foreground hover:bg-[color-mix(in_oklab,var(--destructive),black_18%)] focus-visible:ring-destructive dark:hover:bg-[color-mix(in_oklab,var(--destructive),white_12%)]",
        "destructive-outline":
          "border border-danger-border bg-card text-danger hover:border-danger hover:bg-danger-soft focus-visible:ring-destructive",
        outline:
          "border border-input bg-card text-foreground hover:border-foreground hover:bg-muted disabled:border-dashed disabled:bg-card",
        secondary: "bg-secondary text-success hover:bg-[color-mix(in_oklab,var(--secondary),var(--primary)_12%)]",
        subtle: "bg-secondary text-success hover:bg-[color-mix(in_oklab,var(--secondary),var(--primary)_12%)]",
        ghost: "text-foreground hover:bg-muted disabled:bg-transparent",
        link: "text-primary underline-offset-4 hover:underline disabled:bg-transparent",
      },
      size: {
        default: "h-11 px-[18px] has-[>svg]:px-4",
        xs: "h-7 gap-1 rounded-md px-2 text-xs has-[>svg]:px-1.5 [&_svg:not([class*='size-'])]:size-3",
        sm: "h-9 gap-1.5 rounded-lg px-3.5 text-sm has-[>svg]:px-3",
        lg: "h-13 rounded-[10px] px-6 text-base has-[>svg]:px-5",
        icon: "size-11",
        "icon-xs": "size-7 rounded-md [&_svg:not([class*='size-'])]:size-3",
        "icon-sm": "size-9",
        "icon-lg": "size-13",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

function Button({
  className,
  variant = "default",
  size = "default",
  asChild = false,
  loading = false,
  disabled,
  children,
  ...props
}: React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean
    /** Action en cours : roue à la place de l'icône, bouton inactif, `aria-busy`. Le libellé
     * reste celui de l'appelant (« Validation… »). */
    loading?: boolean
  }) {
  const Comp = asChild ? Slot.Root : "button"

  return (
    <Comp
      data-slot="button"
      data-variant={variant}
      data-size={size}
      className={cn(buttonVariants({ variant, size, className }))}
      disabled={asChild ? undefined : disabled || loading}
      aria-busy={loading || undefined}
      {...props}
    >
      {loading && !asChild ? (
        <>
          <Loader2 className="animate-spin" aria-hidden="true" />
          {children}
        </>
      ) : (
        children
      )}
    </Comp>
  )
}

export { Button, buttonVariants }
