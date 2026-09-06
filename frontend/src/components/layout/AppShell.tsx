import type { CurrentUserResponse } from "../../api/client";
import {
  Boxes,
  Cloud,
  Languages,
  LayoutDashboard,
  LogOut,
  Menu,
  Users,
  type LucideIcon,
} from "lucide-react";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { Link, useInRouterContext, useLocation } from "react-router-dom";
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
import { WorkspaceOverviewPage } from "../../features/workspace/WorkspaceOverviewPage";

export interface AppShellProps {
  accessToken: string;
  children?: ReactNode;
  onLogout: () => Promise<void>;
  principal: CurrentUserResponse;
}

interface WorkspaceNavigationProps {
  administrationLabelId: string;
  onNavigate?: (destination: NavigationDestination) => void;
  showAdministration: boolean;
}

interface NavigationDestination {
  icon: LucideIcon;
  label: string;
  to: string;
}

const WORKSPACE_DESTINATION: NavigationDestination = {
  icon: LayoutDashboard,
  label: "Workspace",
  to: "/",
};

const TRANSLATIONS_DESTINATION: NavigationDestination = {
  icon: Languages,
  label: "Translations",
  to: "/translations",
};

const ADMINISTRATION_DESTINATIONS: NavigationDestination[] = [
  { icon: Boxes, label: "Products", to: "/admin/products" },
  { icon: Users, label: "Users", to: "/admin/users" },
  { icon: Cloud, label: "Bitbucket", to: "/admin/bitbucket" },
];

function destinationMatches(pathname: string, destination: string) {
  return destination === "/"
    ? pathname === "/"
    : pathname === destination || pathname.startsWith(`${destination}/`);
}

function MobileNavigationCommitObserver({
  destination,
  onCommit,
}: {
  destination: string | null;
  onCommit: () => void;
}) {
  const location = useLocation();

  useEffect(() => {
    if (
      destination !== null &&
      destinationMatches(location.pathname, destination)
    ) {
      onCommit();
    }
  }, [destination, location.pathname, onCommit]);

  return null;
}

function DestinationContent({
  icon: Icon,
  label,
}: Pick<NavigationDestination, "icon" | "label">) {
  return (
    <>
      <Icon aria-hidden="true" />
      <span className="min-w-0 break-words text-left [overflow-wrap:anywhere]">
        {label}
      </span>
    </>
  );
}

function RoutedDestination({
  destination,
  onNavigate,
}: {
  destination: NavigationDestination;
  onNavigate?: (destination: NavigationDestination) => void;
}) {
  const location = useLocation();
  const isCurrent =
    destination.to === "/"
      ? location.pathname === "/"
      : location.pathname === destination.to ||
        location.pathname.startsWith(`${destination.to}/`);

  return (
    <Button
      type="button"
      variant="ghost"
      className="h-auto min-h-[44px] w-full min-w-0 max-w-full justify-start whitespace-normal"
      asChild
    >
      <Link
        to={destination.to}
        onClick={() => onNavigate?.(destination)}
        aria-current={isCurrent ? "page" : undefined}
      >
        <DestinationContent {...destination} />
      </Link>
    </Button>
  );
}

function DestinationLink({
  destination,
  onNavigate,
}: {
  destination: NavigationDestination;
  onNavigate?: (destination: NavigationDestination) => void;
}) {
  const isWithinRouter = useInRouterContext();

  if (isWithinRouter) {
    return (
      <RoutedDestination destination={destination} onNavigate={onNavigate} />
    );
  }

  return (
    <Button
      type="button"
      variant="ghost"
      className="h-auto min-h-[44px] w-full min-w-0 max-w-full justify-start whitespace-normal"
      asChild
    >
      <a href={destination.to} onClick={() => onNavigate?.(destination)}>
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
    <nav
      aria-label="Primary navigation"
      className="grid w-full content-start gap-6"
    >
      <div>
        <DestinationLink
          destination={WORKSPACE_DESTINATION}
          onNavigate={onNavigate}
        />
        <DestinationLink
          destination={TRANSLATIONS_DESTINATION}
          onNavigate={onNavigate}
        />
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
            <DestinationLink
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

export function AppShell({
  accessToken,
  children,
  onLogout,
  principal,
}: AppShellProps) {
  const [navigationOpen, setNavigationOpen] = useState(false);
  const [pendingMobileDestination, setPendingMobileDestination] = useState<
    string | null
  >(null);
  const pendingWorkspaceFocus = useRef(false);
  const showAdministration = principal.roles.includes("admin");
  const isWithinRouter = useInRouterContext();
  const handleMobileNavigate = (destination: NavigationDestination) => {
    pendingWorkspaceFocus.current = destination.to === "/";
    setPendingMobileDestination(destination.to);
  };

  const commitMobileNavigation = useCallback(() => {
    setNavigationOpen(false);
    setPendingMobileDestination(null);
  }, []);

  function updateNavigationOpen(open: boolean) {
    setNavigationOpen(open);
    if (!open) {
      setPendingMobileDestination(null);
      pendingWorkspaceFocus.current = false;
    }
  }

  return (
    <div
      data-testid="app-shell"
      className="min-h-screen min-w-0 max-w-full overflow-x-clip bg-background text-foreground"
    >
      {isWithinRouter ? (
        <MobileNavigationCommitObserver
          destination={pendingMobileDestination}
          onCommit={commitMobileNavigation}
        />
      ) : null}
      <header className="flex items-center justify-between gap-4 border-b bg-secondary px-6 py-4 md:px-8">
        <div className="flex min-w-0 items-center gap-2">
          <Sheet open={navigationOpen} onOpenChange={updateNavigationOpen}>
            <TooltipProvider>
              <Tooltip>
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
              onCloseAutoFocus={(event) => {
                if (pendingWorkspaceFocus.current) {
                  event.preventDefault();
                  pendingWorkspaceFocus.current = false;
                  document.getElementById("workspace-title")?.focus();
                }
              }}
            >
              <SheetHeader>
                <SheetTitle>Navigation</SheetTitle>
              </SheetHeader>
              <div className="px-4">
                <WorkspaceNavigation
                  administrationLabelId="mobile-administration-nav-title"
                  showAdministration={showAdministration}
                  onNavigate={handleMobileNavigate}
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
            <WorkspaceOverviewPage
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
