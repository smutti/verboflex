import type { CurrentUserResponse, RoleName } from "../../api/client";
import { Badge } from "../ui/badge";
import { Dashboard } from "../../pages/Dashboard";

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

export function AppShell({ principal }: AppShellProps) {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b bg-secondary px-6 py-4">
        <strong className="text-heading font-semibold">VerboFlex</strong>
      </header>
      <main className="grid gap-8 px-6 py-8">
        <section aria-labelledby="workspace-overview-title" className="grid gap-4">
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
        <Dashboard />
      </main>
    </div>
  );
}
