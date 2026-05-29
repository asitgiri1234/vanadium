import * as React from "react";
import { cn } from "@/lib/utils";

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "muted" | "success" | "outline";
}

export function Badge({ className, variant = "default", ...props }: BadgeProps) {
  const styles: Record<string, string> = {
    default: "bg-primary/15 text-primary",
    muted: "bg-muted text-muted-foreground",
    success: "bg-[hsl(var(--success))]/15 text-[hsl(var(--success))]",
    outline: "border border-border text-foreground",
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
