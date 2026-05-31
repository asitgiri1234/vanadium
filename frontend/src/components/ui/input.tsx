import * as React from "react";
import { cn } from "@/lib/utils";

const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, type, ...props }, ref) => (
    <input
      type={type}
      ref={ref}
      className={cn(
        "glow-ring flex h-10 w-full rounded-lg border border-border/70 bg-background/60 px-3 py-2 text-sm backdrop-blur-md ring-offset-background transition-all duration-300 placeholder:text-muted-foreground/70 focus-visible:border-primary/50 focus-visible:bg-background/80 disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    />
  ),
);
Input.displayName = "Input";

export { Input };
