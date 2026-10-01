import { Inspector } from "@/components/inspector";

export default function Home() {
  return (
    <>
      <header className="border-b border-foreground/10 bg-card">
        <div className="mx-auto flex w-full max-w-6xl items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <div className="flex items-baseline gap-3">
            <span className="font-[family-name:var(--font-display)] text-2xl font-semibold tracking-wide">
              FIELDSIGHT
            </span>
            <span className="hidden text-sm text-muted-foreground sm:inline">Jobsite inspection</span>
          </div>
          <p className="text-xs text-muted-foreground sm:text-sm">Cubiczan · Sam Desigan</p>
        </div>
        <div className="h-1 bg-[#e85d04]" />
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:px-6 sm:py-8">
        <Inspector />
      </main>
      <footer className="border-t border-foreground/10 px-4 py-4 text-xs leading-5 text-muted-foreground sm:px-6">
        <p className="mx-auto max-w-6xl">
          FieldSight is a photo heuristic for the crew on site. It is not a qualified-person inspection
          and it does not decide that equipment is safe to touch.
        </p>
      </footer>
    </>
  );
}
