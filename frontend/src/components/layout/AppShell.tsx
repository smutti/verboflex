import type { CurrentUserResponse, RoleName } from "../../api/client";
import { LayoutDashboard, LogOut, Menu } from "lucide-react";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "../ui/sheet";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "../ui/tooltip";
import { Dashboard } from "../../pages/Dashboard";
import { ServiceStatus } from "./ServiceStatus";

export interface AppShellProps {
  accessToken: string;
  onLogout: () => Promise<void>;
  principal: CurrentUserResponse;
}

const ROLE_LABELS: Record<RoleName, string> = {
  admin: "Administrator",
  product_manager_reviewer: "Product manager / reviewer",
  translator: "Translator",
  viewer: "Viewer",
};

function WorkspaceNavigation() {
  return (
    <nav aria-label="Primary navigation" className="w-full">
      <Button
        type="button"
        variant="ghost"
        className="w-full justify-start"
        aria-current="page"
      >
        <LayoutDashboard aria-hidden="true" />
        Workspace overview
      </Button>
    </nav>
  );
}

export function AppShell({ accessToken, onLogout, principal }: AppShellProps) {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="flex items-center justify-between gap-4 border-b bg-secondary px-6 py-4">
        <div className="flex min-w-0 items-center gap-2">
          <Sheet>
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <SheetTrigger asChild>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="md:hidden"
                      aria-label="Open navigation"
                    >
                      <Menu aria-hidden="true" />
                    </Button>
                  </SheetTrigger>
                </TooltipTrigger>
                <TooltipContent>Open navigation</TooltipContent>
              </Tooltip>
            </TooltipProvider>
            <SheetContent side="left" className="w-72 max-w-[calc(100vw-32px)]">
              <SheetHeader>
                <SheetTitle>Navigation</SheetTitle>
              </SheetHeader>
              <div className="px-4">
                <WorkspaceNavigation />
              </div>
            </SheetContent>
          </Sheet>
          <strong className="truncate text-heading font-semibold">
            VerboFlex
          </strong>
        </div>
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                aria-label="Sign out of VerboFlex"
                onClick={() => void onLogout()}
              >
                <LogOut aria-hidden="true" />
                <span className="hidden sm:inline">Sign out of VerboFlex</span>
              </Button>
            </TooltipTrigger>
            <TooltipContent>Sign out of VerboFlex</TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </header>
      <div className="md:grid md:grid-cols-[16rem_minmax(0,1fr)]">
        <aside className="hidden min-h-[calc(100vh-65px)] border-r bg-secondary p-4 md:flex">
          <WorkspaceNavigation />
        </aside>
        <main className="grid min-w-0 content-start gap-8 px-6 py-8">
          <section
            aria-labelledby="workspace-overview-title"
            className="grid gap-4"
          >
            <div className="grid gap-2">
              <h1
                id="workspace-overview-title"
                className="text-display font-semibold"
              >
                Workspace overview
              </h1>
              <p className="text-muted-foreground">
                Your review workspace will appear here as products and repositories
                are configured.
              </p>
            </div>
            <div className="grid gap-2">
              <p className="font-semibold">{principal.display_name}</p>
              <p className="text-muted-foreground">{principal.email}</p>
              <div className="flex flex-wrap gap-2" aria-label="Assigned roles">
                {principal.roles.map((role) => (
                  <Badge key={role} variant="outline" className="rounded-md">
                    {ROLE_LABELS[role]}
                  </Badge>
                ))}
              </div>
            </div>
          </section>
          <ServiceStatus accessToken={accessToken} />
          <Dashboard />
        </main>
      </div>
    </div>
  );
}
