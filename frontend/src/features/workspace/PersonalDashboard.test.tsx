import "@testing-library/jest-dom/vitest";
import {
  act,
  cleanup,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import {
  getPersonalDashboard,
  type CurrentUserResponse,
  type DashboardResponse,
  type DashboardReviewEvent,
  type NotificationItemResponse,
} from "../../api/client";
import {
  useNotificationShell,
  type NotificationShellValue,
} from "../notifications/NotificationShell";
import { ActivityEventList } from "./ActivityEventList";
import { PersonalDashboard } from "./PersonalDashboard";

vi.mock("../../api/client", async (original) => ({
  ...(await original<typeof import("../../api/client")>()),
  getPersonalDashboard: vi.fn(),
}));
vi.mock("../notifications/NotificationShell", () => ({
  useNotificationShell: vi.fn(),
}));
let notifications: NotificationShellValue;
const getDashboard = vi.mocked(getPersonalDashboard);
const principal: CurrentUserResponse = {
  id: "me",
  email: "me@example.test",
  display_name: "Mira",
  roles: ["translator"],
  must_change_password: false,
};
const empty: DashboardResponse = {
  my_activity: { items: [], has_more: false },
  project_updates: { items: [], has_more: false },
};
const saved: DashboardResponse = {
  ...empty,
  my_activity: {
    has_more: false,
    items: [
      {
        kind: "proposal_saved",
        event_id: "review:1",
        occurred_at: "2026-10-01T10:00:00Z",
        product: { id: "product", name: "Mobile" },
        actor: { id: "me", display_name: "Mira" },
        translation_group_id: "group",
        language: "it",
        key_excerpt: "welcome",
        from_state: null,
        to_state: null,
      },
    ],
  },
};
function view(person = principal, token = "token") {
  return (
    <MemoryRouter>
      <PersonalDashboard principal={person} accessToken={token} />
    </MemoryRouter>
  );
}
beforeEach(() => {
  getDashboard.mockReset();
  notifications = {
    announcement: "",
    status: "ready",
    stale: false,
    recent: [],
    unreadCount: 0,
    readingIds: new Set(),
    readErrorId: null,
    refresh: vi.fn().mockResolvedValue(undefined),
    markRead: vi.fn().mockResolvedValue(true),
  };
  vi.mocked(useNotificationShell).mockImplementation(() => notifications);
});
afterEach(cleanup);

it("loads saved operations through the generated client and resolves their translation destination", async () => {
  getDashboard.mockResolvedValue({ data: saved, error: undefined });
  render(view());
  expect(screen.getByRole("status")).toHaveTextContent("Loading activity");
  const link = await screen.findByRole("link", { name: /Saved a proposal/ });
  expect(link).toHaveAttribute("href", "/products/product/strings/group");
  expect(link).toHaveTextContent("welcome");
  expect(getDashboard).toHaveBeenCalledWith({
    auth: "token",
    signal: expect.any(AbortSignal),
  });
});

it("retries a safe failure, shows empty state and replaces the response on refresh", async () => {
  getDashboard
    .mockRejectedValueOnce(new Error("private payload"))
    .mockResolvedValueOnce({ data: saved, error: undefined })
    .mockResolvedValueOnce({ data: empty, error: undefined });
  render(view());
  expect(await screen.findByRole("alert")).not.toHaveTextContent(
    "private payload",
  );
  await userEvent.click(screen.getByRole("button", { name: "Retry activity" }));
  await screen.findByRole("link", { name: /Saved a proposal/ });
  await userEvent.click(
    screen.getByRole("button", { name: "Refresh activity" }),
  );
  expect(await screen.findByText("No recent activity yet")).toBeVisible();
  expect(screen.queryByText("welcome")).not.toBeInTheDocument();
});

it.each(["identity", "token", "roles"])(
  "clears data and rejects late success after %s replacement",
  async (change) => {
    let resolveOld!: (value: {
      data: DashboardResponse;
      error: undefined;
    }) => void;
    getDashboard
      .mockResolvedValueOnce({ data: saved, error: undefined })
      .mockImplementationOnce(
        () =>
          new Promise<{ data: DashboardResponse; error: undefined }>(
            (resolve) => {
              resolveOld = resolve;
            },
          ),
      )
      .mockResolvedValueOnce({ data: empty, error: undefined });
    const { rerender } = render(view());
    await screen.findByText("welcome");
    await userEvent.click(
      screen.getByRole("button", { name: "Refresh activity" }),
    );
    const signal = getDashboard.mock.calls[1][0]?.signal;
    rerender(
      view(
        change === "identity"
          ? { ...principal, id: "other" }
          : change === "roles"
            ? { ...principal, roles: ["viewer"] }
            : principal,
        change === "token" ? "rotated" : "token",
      ),
    );
    expect(screen.queryByText("welcome")).not.toBeInTheDocument();
    await screen.findByText("No recent activity yet");
    await act(async () => resolveOld({ data: saved, error: undefined }));
    expect(signal?.aborted).toBe(true);
    expect(screen.queryByText("welcome")).not.toBeInTheDocument();
  },
);

it("aborts unmounted work and ignores its failure", async () => {
  let rejectOld!: (reason: Error) => void;
  getDashboard.mockImplementationOnce(
    () =>
      new Promise<never>((_resolve, reject) => {
        rejectOld = reject;
      }),
  );
  const { unmount } = render(view());
  await waitFor(() => expect(getDashboard).toHaveBeenCalled());
  const signal = getDashboard.mock.calls[0][0]?.signal;
  unmount();
  await act(async () => rejectOld(new Error("late")));
  expect(signal?.aborted).toBe(true);
});

it.each(["identity", "token", "roles"])(
  "removes already rendered data immediately on %s change while the successor loads",
  async (change) => {
    getDashboard
      .mockResolvedValueOnce({ data: saved, error: undefined })
      .mockReturnValueOnce(new Promise<never>(() => undefined));
    const { rerender } = render(view());
    await screen.findByText("welcome");
    rerender(
      view(
        change === "identity"
          ? { ...principal, id: "next" }
          : change === "roles"
            ? { ...principal, roles: ["viewer"] }
            : principal,
        change === "token" ? "next" : "token",
      ),
    );
    expect(screen.queryByText("welcome")).toBeNull();
    expect(screen.getByText("Loading activity")).toBeVisible();
  },
);

it.each(["identity", "token", "roles"])(
  "ignores delayed failure after %s replacement",
  async (change) => {
    let rejectOld!: (reason: Error) => void;
    getDashboard
      .mockImplementationOnce(
        () =>
          new Promise<never>((_resolve, reject) => {
            rejectOld = reject;
          }),
      )
      .mockResolvedValue({ data: saved, error: undefined });
    const { rerender } = render(view());
    await waitFor(() => expect(getDashboard).toHaveBeenCalledOnce());
    rerender(
      view(
        change === "identity"
          ? { ...principal, id: "next" }
          : change === "roles"
            ? { ...principal, roles: ["viewer"] }
            : principal,
        change === "token" ? "next" : "token",
      ),
    );
    await screen.findByText("welcome");
    await act(async () => rejectOld(new Error("obsolete")));
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.getByText("welcome")).toBeVisible();
  },
);

it("renders every event with truthful labels, encoded destinations, times and bounded history guidance", async () => {
  const review = saved.my_activity.items[0] as DashboardReviewEvent;
  const common = {
    event_id: "event",
    product: { id: "a/b", name: "Mobile" },
    actor: review.actor,
    occurred_at: review.occurred_at,
  };
  const comment = {
    ...common,
    translation_group_id: "g/1",
    key_excerpt: "<script>key</script>",
    language: "it",
    comment_id: "c?2",
    comment_status: "available" as const,
  };
  const events: DashboardResponse = {
    my_activity: {
      has_more: true,
      items: [
        review,
        {
          ...review,
          event_id: "state",
          kind: "state_changed",
          from_state: "draft",
          to_state: "approved",
        },
        { ...comment, kind: "comment_created", event_id: "created" },
        { ...comment, kind: "comment_edited", event_id: "edited" },
        {
          ...comment,
          kind: "comment_removed",
          event_id: "removed",
          comment_id: null,
          comment_status: "removed",
        },
        {
          ...common,
          kind: "change_set_submitted",
          event_id: "submitted",
          change_set_id: "set/1",
          current_status: "needs_attention",
        },
      ],
    },
    project_updates: {
      has_more: false,
      items: [
        {
          ...common,
          kind: "current_import_completed",
          event_id: "import",
          actor: null,
        },
      ],
    },
  };
  const { container } = render(
    <MemoryRouter>
      <ActivityEventList
        items={[...events.my_activity.items, ...events.project_updates.items]}
      />
    </MemoryRouter>,
  );
  const region = screen.getByRole("list");
  expect(
    within(region).getByRole("link", {
      name: /Changed review state from draft to approved/,
    }),
  ).toHaveAttribute("href", "/products/product/strings/group");
  for (const label of ["Added a comment", "Edited a comment"])
    expect(
      within(region).getByRole("link", { name: new RegExp(label) }),
    ).toHaveAttribute("href", "/products/a%2Fb/strings/g%2F1?comment=c%3F2");
  expect(
    within(region).getByRole("link", { name: /Removed a comment/ }),
  ).toHaveAttribute("href", "/products/a%2Fb/strings/g%2F1");
  expect(
    within(region).getByRole("link", { name: "Submitted a change set" }),
  ).toHaveAttribute("href", "/products/a%2Fb/change-sets/set%2F1");
  expect(screen.getByText("Current status: needs attention")).toBeVisible();
  expect(
    screen.getByRole("link", { name: "Current import completed" }),
  ).toHaveAttribute("href", "/products/a%2Fb/strings");
  expect(container.querySelectorAll("time")).toHaveLength(7);
  expect(container.querySelector("script")).toBeNull();
});

const notification: NotificationItemResponse = {
  id: "n1",
  actor: { user_id: "author", display_name: "Alex" },
  comment_status: "available",
  created_at: "2026-10-01T10:00:00Z",
  is_read: false,
  key_excerpt: "welcome",
  language: "it",
  originating_comment_id: "c/1",
  product: { id: "p", name: "Mobile" },
  read_at: null,
  translation_group_id: "g/1",
};
it("uses the shell projection and explicit read/refresh actions, with removed targets kept unlinked", async () => {
  notifications.recent = [
    notification,
    { ...notification, id: "n2", comment_status: "removed" },
  ];
  notifications.unreadCount = 2;
  getDashboard.mockResolvedValue({ data: empty, error: undefined });
  const { rerender } = render(view());
  const region = screen.getByRole("region", { name: "Notifications" });
  expect(within(region).getByText("2 unread")).toBeVisible();
  expect(within(region).getAllByRole("link")).toHaveLength(2);
  expect(
    within(region).getByRole("link", { name: /Alex mentioned you/ }),
  ).toHaveAttribute("href", "/translations/g%2F1?comment=c%2F1");
  expect(notifications.markRead).not.toHaveBeenCalled();
  await userEvent.click(
    within(region).getByRole("button", { name: "Refresh notifications" }),
  );
  expect(notifications.refresh).toHaveBeenCalledOnce();
  expect(notifications.markRead).not.toHaveBeenCalled();
  await userEvent.click(
    within(region).getAllByRole("button", { name: "Mark as read" })[0],
  );
  expect(notifications.markRead).toHaveBeenCalledWith("n1");
  notifications.readingIds = new Set(["n1"]);
  rerender(view());
  expect(
    within(region).getByRole("button", { name: "Marking as read" }),
  ).toBeDisabled();
  notifications.readingIds = new Set();
  notifications.readErrorId = "n1";
  rerender(view());
  expect(within(region).getByRole("alert")).toHaveTextContent(
    "Notification was not marked as read",
  );
  await userEvent.click(
    within(region).getByRole("button", { name: "Retry marking as read" }),
  );
  notifications.readErrorId = null;
  notifications.unreadCount = 1;
  notifications.recent = [
    { ...notification, is_read: true },
    { ...notification, id: "n2", comment_status: "removed" },
  ];
  rerender(view());
  expect(within(region).getByText("1 unread")).toBeVisible();
  expect(within(region).getByText("Read")).toBeVisible();
});

it("keeps notification and activity loading/error/recovery independent", async () => {
  notifications.status = "loading";
  getDashboard.mockResolvedValue({ data: empty, error: undefined });
  const { rerender } = render(view());
  expect(screen.getByText("Loading notifications")).toBeVisible();
  await screen.findByText("No recent activity yet");
  notifications.status = "error";
  rerender(view());
  expect(screen.getByText("Notifications could not be loaded")).toBeVisible();
  expect(screen.getByText("No recent activity yet")).toBeVisible();
  notifications.status = "ready";
  notifications.stale = true;
  notifications.recent = [notification];
  rerender(view());
  expect(screen.getByText("May be out of date")).toBeVisible();
  getDashboard.mockRejectedValueOnce(new Error("private"));
  await userEvent.click(
    screen.getByRole("button", { name: "Refresh activity" }),
  );
  await screen.findByText(/Activity could not be loaded/);
  expect(
    screen.getByRole("link", { name: /Alex mentioned you/ }),
  ).toBeVisible();
  expect(notifications.markRead).not.toHaveBeenCalled();
});

it("limits project updates to three events and links to the full feed", async () => {
  getDashboard.mockResolvedValue({
    data: {
      ...empty,
      project_updates: {
        has_more: true,
        items: Array.from({ length: 10 }, (_, index) => ({
          kind: "current_import_completed" as const,
          event_id: `import:${index}`,
          occurred_at: "2026-10-03T12:00:00Z",
          product: { id: `product-${index}`, name: `Product ${index}` },
          actor: null,
        })),
      },
    },
    error: undefined,
  });
  render(view());
  const region = await screen.findByRole("region", { name: "Project updates" });
  expect(within(region).getAllByRole("listitem")).toHaveLength(3);
  expect(within(region).queryByText("Product 3")).toBeNull();
  expect(
    within(region).getByRole("link", { name: "View all project updates" }),
  ).toHaveAttribute("href", "/project-updates");
});

it("limits personal activity to three events and links to its full history", async () => {
  getDashboard.mockResolvedValue({
    data: {
      ...empty,
      my_activity: {
        has_more: true,
        items: Array.from({ length: 6 }, (_, index) => ({
          ...saved.my_activity.items[0],
          event_id: `review:${index}`,
          key_excerpt: `Key ${index}`,
        })),
      },
    },
    error: undefined,
  });
  render(view());
  const region = await screen.findByRole("region", {
    name: "My recent activity",
  });
  expect(within(region).getAllByRole("listitem")).toHaveLength(3);
  expect(within(region).queryByText("Key 3")).toBeNull();
  expect(
    within(region).getByRole("link", { name: "View all my activity" }),
  ).toHaveAttribute("href", "/my-activity");
});
