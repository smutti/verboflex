import type { CurrentUserResponse, RoleName } from "../../api/client";
import {
  Boxes,
  Cloud,
  LayoutDashboard,
  LogOut,
  Menu,
  Users,
  type LucideIcon,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import { Link, useInRouterContext, useLocation } from "react-router-dom";
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
  children?: ReactNode;
  onLogout: () => Promise<void>;
  principal: CurrentUserResponse;
}

const ROLE_LABELS: Record<RoleName, string> = {
  admin: "Administrator",
  product_manager_reviewer: "Product manager / reviewer",
  translator: "Translator",
  viewer: "Viewer",
};

interface WorkspaceNavigationProps {
  administrationLabelId: string;
  onNavigate?: () => void;
  showAdministration: boolean;
}

interface AdministrationDestination {
  icon: LucideIcon;
  label: string;
  to: string;
}

const ADMINISTRATION_DESTINATIONS: AdministrationDestination[] = [
  { icon: Boxes, label: "Products", to: "/admin/products" },
  { icon: Users, label: "Users", to: "/admin/users" },
  { icon: Cloud, label: "Bitbucket", to: "/admin/bitbucket" },
];

function DestinationContent({
  icon: Icon,
  label,
}: Pick<AdministrationDestination, "icon" | "label">) {
  return (
    <>
      <Icon aria-hidden="true" />
      <span className="min-w-0 break-words text-left [overflow-wrap:anywhere]">
        {label}
      </span>
    </>
  );
}

function RoutedAdministrationDestination({
  destination,
  onNavigate,
}: {
  destination: AdministrationDestination;
  onNavigate?: () => void;
}) {
  const location = useLocation();
  const isCurrent =
    location.pathname === destination.to ||
    location.pathname.startsWith(`${destination.to}/`);

  return (
    <Button
      type="button"
      variant="ghost"
      className="h-auto min-h-9 w-full min-w-0 max-w-full justify-start whitespace-normal"
      asChild
    >
      <Link
        to={destination.to}
        onClick={onNavigate}
        aria-current={isCurrent ? "page" : undefined}
      >
        <DestinationContent {...destination} />
      </Link>
    </Button>
  );
}

function AdministrationDestinationLink({
  destination,
  onNavigate,
}: {
  destination: AdministrationDestination;
  onNavigate?: () => void;
}) {
  const isWithinRouter = useInRouterContext();

  if (isWithinRouter) {
    return (
      <RoutedAdministrationDestination
        destination={destination}
        onNavigate={onNavigate}
      />
    );
  }

  return (
    <Button
      type="button"
      variant="ghost"
      className="h-auto min-h-9 w-full min-w-0 max-w-full justify-start whitespace-normal"
      asChild
    >
      <a href={destination.to} onClick={onNavigate}>
        <DestinationContent {...destination} />
      </a>
    </Button>
  );
}

function WorkspaceNavigation({
  administrationLabelId,
  onNavigate,
  showAdministration,
}: WorkspaceNavigationProps) {
  return (
    <nav aria-label="Primary navigation" className="grid w-full gap-6">
      <div>
        <Button
          type="button"
          variant="ghost"
          className="w-full justify-start"
          aria-current="page"
        >
          <LayoutDashboard aria-hidden="true" />
          Workspace overview
        </Button>
      </div>
      {showAdministration ? (
        <section className="grid gap-2" aria-labelledby={administrationLabelId}>
          <h2
            id={administrationLabelId}
            className="px-3 text-label font-semibold text-muted-foreground"
          >
            Administration
          </h2>
          {ADMINISTRATION_DESTINATIONS.map((destination) => (
            <AdministrationDestinationLink
              key={destination.to}
              destination={destination}
              onNavigate={onNavigate}
            />
          ))}
        </section>
      ) : null}
    </nav>
  );
}

function WorkspaceOverviewContent({
  accessToken,
  principal,
}: Pick<AppShellProps, "accessToken" | "principal">) {
  return (
    <>
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
    </>
  );
}

export function AppShell({
  accessToken,
  children,
  onLogout,
  principal,
}: AppShellProps) {
  const [navigationOpen, setNavigationOpen] = useState(false);
  const [navigationTooltipOpen, setNavigationTooltipOpen] = useState(false);
  const showAdministration = principal.roles.includes("admin");

  return (
    <div
      data-testid="app-shell"
      className="min-h-screen min-w-0 max-w-full overflow-x-clip bg-background text-foreground"
    >
      <header className="flex items-center justify-between gap-4 border-b bg-secondary px-6 py-4 md:px-8">
        <div className="flex min-w-0 items-center gap-2">
          <Sheet open={navigationOpen} onOpenChange={setNavigationOpen}>
            <TooltipProvider>
              <Tooltip
                open={!navigationOpen && navigationTooltipOpen}
                onOpenChange={setNavigationTooltipOpen}
              >
                <TooltipTrigger asChild>
                  <SheetTrigger asChild>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="lg:hidden"
                      aria-label="Open navigation"
                    >
                      <Menu aria-hidden="true" />
                    </Button>
                  </SheetTrigger>
                </TooltipTrigger>
                {!navigationOpen && (
                  <TooltipContent>Open navigation</TooltipContent>
                )}
              </Tooltip>
            </TooltipProvider>
            <SheetContent
              side="left"
              className="w-72 max-w-[calc(100vw-32px)] motion-reduce:animate-none motion-reduce:transition-none"
            >
              <SheetHeader>
                <SheetTitle>Navigation</SheetTitle>
              </SheetHeader>
              <div className="px-4">
                <WorkspaceNavigation
                  administrationLabelId="mobile-administration-nav-title"
                  showAdministration={showAdministration}
                  onNavigate={() => setNavigationOpen(false)}
                />
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
      <div className="min-w-0 max-w-full lg:grid lg:grid-cols-[16rem_minmax(0,1fr)]">
        <aside
          data-testid="desktop-navigation"
          className="hidden min-h-[calc(100vh-65px)] border-r bg-secondary p-4 lg:flex"
        >
          <WorkspaceNavigation
            administrationLabelId="desktop-administration-nav-title"
            showAdministration={showAdministration}
          />
        </aside>
        <main
          data-testid="app-shell-content"
          className="grid min-w-0 max-w-full content-start gap-8 px-6 py-8 md:px-8"
        >
          {children === undefined ? (
            <WorkspaceOverviewContent
              accessToken={accessToken}
              principal={principal}
            />
          ) : (
            children
          )}
        </main>
      </div>
    </div>
  );
}
