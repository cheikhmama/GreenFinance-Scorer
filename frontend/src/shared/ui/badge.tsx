import { cva, type VariantProps } from "class-variance-authority";
import type * as React from "react";

import { cn } from "@/shared/ui/cn";

const badgeVariants = cva(
  "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium w-fit whitespace-nowrap shrink-0 gap-1",
  {
    variants: {
      variant: {
        default: "border-transparent bg-primary text-primary-foreground",
        secondary: "border-transparent bg-secondary text-secondary-foreground",
        destructive: "border-transparent bg-destructive text-white",
        outline: "text-foreground",
        // Validé / Actif — contour émeraude, lisible dans les deux thèmes.
        success:
          "border-emerald-200 bg-emerald-50/50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/30 dark:text-emerald-400",
        // En cours / En revue — contour ambre, même construction que `success`.
        warning:
          "border-amber-200 bg-amber-50/50 text-amber-700 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-400",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

function Badge({
  className,
  variant,
  ...props
}: React.ComponentProps<"span"> & VariantProps<typeof badgeVariants>) {
  return <span data-slot="badge" className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge };
