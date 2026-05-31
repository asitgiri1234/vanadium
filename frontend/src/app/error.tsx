"use client";

import { useEffect } from "react";
import Link from "next/link";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <main className="mx-auto flex min-h-[60vh] max-w-lg flex-col items-center justify-center px-4 py-20 text-center">
      <p className="sci-fi-label mb-3 text-red-400">System Error</p>
      <h1 className="text-2xl font-bold">Something went wrong</h1>
      <p className="mt-3 text-sm text-muted-foreground">
        The page failed to load. Try refreshing — if the error persists, restart the
        dev server and clear the <code className="text-accent">.next</code> cache.
      </p>
      <div className="mt-8 flex flex-wrap justify-center gap-3">
        <button
          type="button"
          onClick={reset}
          className={cn(buttonVariants({ variant: "gradient" }))}
        >
          Try again
        </button>
        <Link href="/" className={cn(buttonVariants({ variant: "outline" }))}>
          Go home
        </Link>
      </div>
    </main>
  );
}
