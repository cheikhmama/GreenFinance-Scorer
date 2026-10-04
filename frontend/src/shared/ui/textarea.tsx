import * as React from "react";

import { cn } from "@/shared/ui/cn";

function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "flex min-h-24 w-full rounded-lg border border-input bg-card px-3 py-2.5 text-[15px] leading-6 text-foreground transition-[border-color,box-shadow] duration-[120ms] outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed disabled:border-dashed disabled:bg-muted disabled:text-muted-foreground",
        "focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/25",
        "aria-invalid:border-2 aria-invalid:border-destructive aria-invalid:ring-destructive/20",
        className,
      )}
      {...props}
    />
  );
}

export { Textarea };
