import { useForm } from "react-hook-form";

import { Button } from "@/components/ui/button";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";

interface ChangePasswordFormValues {
  currentPassword: string;
  newPassword: string;
  confirmPassword: string;
}

export function ChangePasswordPage() {
  const form = useForm<ChangePasswordFormValues>({
    defaultValues: {
      currentPassword: "",
      newPassword: "",
      confirmPassword: "",
    },
  });

  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-6 py-12">
      <section className="w-full max-w-md rounded-lg border bg-card p-6 shadow-xs">
        <h1 className="text-[28px] font-semibold leading-[1.15]">
          Set a new password
        </h1>
        <p className="mt-4 text-muted-foreground">
          Your temporary password must be replaced before you can continue.
        </p>
        <Form {...form}>
          <form
            className="mt-8 grid gap-6"
            onSubmit={form.handleSubmit(() => undefined)}
          >
            <FormField
              control={form.control}
              name="currentPassword"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Current password</FormLabel>
                  <FormControl>
                    <Input
                      autoComplete="current-password"
                      type="password"
                      {...field}
                    />
                  </FormControl>
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="newPassword"
              rules={{
                validate: (value) =>
                  (value.length >= 12 && value.length <= 128) ||
                  "Password must contain 12 to 128 characters.",
              }}
              render={({ field }) => (
                <FormItem>
                  <FormLabel>New password</FormLabel>
                  <FormControl>
                    <Input
                      autoComplete="new-password"
                      type="password"
                      {...field}
                    />
                  </FormControl>
                  <FormDescription>
                    Use 12 to 128 characters. Spaces and Unicode characters are
                    allowed.
                  </FormDescription>
                  <FormMessage role="alert" />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="confirmPassword"
              rules={{
                validate: (value) =>
                  value === form.getValues("newPassword") ||
                  "Passwords do not match.",
              }}
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Confirm new password</FormLabel>
                  <FormControl>
                    <Input
                      autoComplete="new-password"
                      type="password"
                      {...field}
                    />
                  </FormControl>
                  <FormMessage role="alert" />
                </FormItem>
              )}
            />
            <Button className="w-full" type="submit">
              Set new password
            </Button>
          </form>
        </Form>
      </section>
    </main>
  );
}
