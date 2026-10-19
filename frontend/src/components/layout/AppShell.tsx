import { t, useUiLanguage } from "@/i18n";
import { LanguagePicker } from "@/i18n/LanguagePicker";
import type { CurrentUserResponse } from "../../api/client";
import {
  Boxes,
  ChevronDown,
  Cloud,
  Languages,
  LayoutDashboard,
  LogOut,
  Menu,
  PackageSearch,
  UserRound,
  Users,
  type LucideIcon,
} from "lucide-react";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";
import { Link, useInRouterContext, useLocation } from "react-router-dom";
import { Button } from "../ui/button";
import { Badge } from "../ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "../ui/dropdown-menu";
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
import { productIdentity } from "../../features/products/productIdentity";
import { ROLE_LABELS } from "../../features/auth/roleLabels";
import { NotificationPanel } from "../../features/notifications/NotificationPanel";
import { NotificationShell } from "../../features/notifications/NotificationShell";

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
  productFocus?: boolean;
  to: string;
}

const WORKSPACE_DESTINATION: NavigationDestination = {
  icon: LayoutDashboard,
  get label() {
    return t("Home");
  },
  to: "/",
};

const PRODUCTS_DESTINATION: NavigationDestination = {
  icon: PackageSearch,
  get label() {
    return t("Product workspace");
  },
  productFocus: true,
  to: "/products",
};

const TRANSLATIONS_DESTINATION: NavigationDestination = {
  icon: Languages,
  get label() {
    return t("All translations");
  },
  to: "/translations",
};

const ADMINISTRATION_DESTINATIONS: NavigationDestination[] = [
  {
    icon: Boxes,
    get label() {
      return t("Product configuration");
    },
    to: "/admin/products",
  },
  {
    icon: Users,
    get label() {
      return t("Users");
    },
    to: "/admin/users",
  },
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
  useUiLanguage();
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
  useUiLanguage();
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
  useUiLanguage();
  const location = useLocation();
  const isCurrent =
    destination.to === "/"
      ? location.pathname === "/"
      : location.pathname === destination.to ||
        location.pathname.startsWith(`${destination.to}/`);
  const productIdMatch = destination.productFocus
    ? location.pathname.match(/^\/products\/([^/]+)/)
    : null;
  let productStyle: CSSProperties | undefined;
  if (isCurrent && productIdMatch) {
    let productId = productIdMatch[1];
    try {
      productId = decodeURIComponent(productId);
    } catch {
      // Keep the raw route segment; the workspace will render it unavailable.
    }
    const identity = productIdentity(productId, t("Product"));
    productStyle = {
      backgroundColor: identity.soft,
      borderLeftColor: identity.accent,
      color: identity.ink,
    };
  }

  return (
    <Button
      type="button"
      variant="ghost"
      className={`h-auto min-h-[44px] w-full min-w-0 max-w-full justify-start whitespace-normal ${isCurrent ? "bg-muted font-semibold text-foreground border-l-4 border-l-primary" : "text-foreground"}`}
      style={productStyle}
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
  useUiLanguage();
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
  useUiLanguage();
  return (
    <nav
      aria-label={t("Primary navigation")}
      className="grid w-full content-start gap-6"
    >
      <div>
        <DestinationLink
          destination={WORKSPACE_DESTINATION}
          onNavigate={onNavigate}
        />
        <DestinationLink
          destination={PRODUCTS_DESTINATION}
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
            {t("Administration")}
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
  useUiLanguage();
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
    <NotificationShell accessToken={accessToken} principalId={principal.id}>
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
                        aria-label={t("Open navigation")}
                      >
                        <Menu aria-hidden="true" />
                      </Button>
                    </SheetTrigger>
                  </TooltipTrigger>
                  {!navigationOpen && (
                    <TooltipContent>{t("Open navigation")}</TooltipContent>
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
                  <SheetTitle>{t("Navigation")}</SheetTitle>
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
          <div className="flex items-center gap-1 sm:gap-2">
            <NotificationPanel />
            <LanguagePicker />
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  type="button"
                  variant="ghost"
                  aria-label={t("Open user menu for {{v0}}", {
                    v0: principal.display_name,
                  })}
                  className="max-w-[14rem]"
                >
                  <UserRound aria-hidden="true" />
                  <span className="hidden truncate sm:inline">
                    {principal.display_name}
                  </span>
                  <ChevronDown aria-hidden="true" className="hidden sm:block" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent
                align="end"
                className="w-72 max-w-[calc(100vw-2rem)]"
              >
                <DropdownMenuLabel className="grid gap-2 py-2">
                  <span className="truncate font-semibold">
                    {principal.display_name}
                  </span>
                  <span className="break-words font-normal text-muted-foreground [overflow-wrap:anywhere]">
                    {principal.email}
                  </span>
                  <span
                    className="flex flex-wrap gap-1.5"
                    aria-label={t("Assigned roles")}
                  >
                    {principal.roles.map((role) => (
                      <Badge
                        key={role}
                        variant="outline"
                        className="rounded-md"
                      >
                        {ROLE_LABELS[role]}
                      </Badge>
                    ))}
                  </span>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem asChild>
                  {isWithinRouter ? (
                    <Link to="/profile">
                      <UserRound aria-hidden="true" />
                      {t("Profile")}
                    </Link>
                  ) : (
                    <a href="/profile">
                      <UserRound aria-hidden="true" />
                      {t("Profile")}
                    </a>
                  )}
                </DropdownMenuItem>
                <DropdownMenuItem asChild>
                  {isWithinRouter ? (
                    <Link to="/mcp/connections">{t("Connected apps")}</Link>
                  ) : (
                    <a href="/mcp/connections">{t("Connected apps")}</a>
                  )}
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem asChild>
                  <a
                    href="https://github.com/smutti/verboflex/issues/new/choose"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {t("Report a problem on GitHub")}
                  </a>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    type="button"
                    variant="ghost"
                    aria-label={t("Sign out of VerboFlex")}
                    onClick={() => void onLogout()}
                  >
                    <LogOut aria-hidden="true" />
                    <span className="hidden sm:inline">
                      {t("Sign out of VerboFlex")}
                    </span>
                  </Button>
                </TooltipTrigger>
                <TooltipContent>{t("Sign out of VerboFlex")}</TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
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
            className="grid min-w-0 max-w-full content-start gap-(--space-xl) px-(--space-lg) py-(--space-xl) md:px-(--space-xl)"
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
    </NotificationShell>
  );
}
