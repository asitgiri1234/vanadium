import Link from "next/link";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export default function NotFound() {
  return (
    <main className="mx-auto flex min-h-[60vh] max-w-lg flex-col items-center justify-center px-4 py-20 text-center">
      <p className="sci-fi-label mb-3">404</p>
      <h1 className="text-2xl font-bold">Page not found</h1>
      <p className="mt-3 text-sm text-muted-foreground">
        This route doesn&apos;t exist. Head back to the landing page or open the analyzer.
      </p>
      <div className="mt-8 flex flex-wrap justify-center gap-3">
        <Link href="/" className={cn(buttonVariants({ variant: "gradient" }))}>
          Home
        </Link>
        <Link href="/analyze" className={cn(buttonVariants({ variant: "outline" }))}>
          Analyze videos
        </Link>
      </div>
    </main>
  );
}
