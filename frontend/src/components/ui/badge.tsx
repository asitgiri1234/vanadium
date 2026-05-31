import * as React from "react";
import { cn } from "@/lib/utils";

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "muted" | "success" | "outline";
}

export function Badge({ className, variant = "default", ...props }: BadgeProps) {
  const styles: Record<string, string> = {
    default:
      "border border-primary/25 bg-primary/10 text-primary shadow-[0_0_16px_-4px_hsl(276_91%_66%/0.4)]",
    muted: "border border-border/60 bg-muted/40 text-muted-foreground backdrop-blur-sm",
    success:
      "border border-[hsl(var(--success))]/30 bg-[hsl(var(--success))]/10 text-[hsl(var(--success))]",
    outline: "border border-border/80 bg-background/40 text-foreground backdrop-blur-sm",
  };
  return (
    <div
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
        styles[variant],
        className,
      )}
      {...props}
    />
  );
}
