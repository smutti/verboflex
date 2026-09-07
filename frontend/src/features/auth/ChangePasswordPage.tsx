import { useState } from "react";
import { useForm } from "react-hook-form";

import { Alert, AlertDescription } from "@/components/ui/alert";
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
import { useSession } from "./session";

interface ChangePasswordFormValues {
  currentPassword: string;
  newPassword: string;
  confirmPassword: string;
}

export function PasswordChangeForm({
  submitLabel = "Set new password",
}: {
  submitLabel?: string;
}) {
  const { changePassword } = useSession();
  const [actionError, setActionError] = useState(false);
  const form = useForm<ChangePasswordFormValues>({
    defaultValues: {
      currentPassword: "",
      newPassword: "",
      confirmPassword: "",
    },
  });

  return (
    <Form {...form}>
      <form
        className="grid gap-6"
        onSubmit={form.handleSubmit(async (values) => {
          setActionError(false);
          try {
            await changePassword({
              currentPassword: values.currentPassword,
              newPassword: values.newPassword,
            });
          } catch {
            setActionError(true);
          }
        })}
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
            validate: {
              length: (value) =>
                (value.length >= 12 && value.length <= 128) ||
                "Password must contain 12 to 128 characters.",
              differsFromCurrent: (value) =>
                value !== form.getValues("currentPassword") ||
                "New password must differ from current password.",
            },
          }}
          render={({ field }) => (
            <FormItem>
              <FormLabel>New password</FormLabel>
              <FormControl>
                <Input autoComplete="new-password" type="password" {...field} />
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
                <Input autoComplete="new-password" type="password" {...field} />
              </FormControl>
              <FormMessage role="alert" />
            </FormItem>
          )}
        />
        {actionError ? (
          <Alert variant="destructive">
            <AlertDescription>
              We could not change your password. Check the requirements and try
              again.
            </AlertDescription>
          </Alert>
        ) : null}
        <Button
          aria-busy={form.formState.isSubmitting}
          className="w-full"
          disabled={form.formState.isSubmitting}
          type="submit"
        >
          {submitLabel}
        </Button>
      </form>
    </Form>
  );
}

export function ChangePasswordPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-6 py-12">
      <section className="w-full max-w-md rounded-lg border bg-card p-6 shadow-xs">
        <h1 className="text-[28px] font-semibold leading-[1.15]">
          Set a new password
        </h1>
        <p className="mt-4 text-muted-foreground">
          Your temporary password must be replaced before you can continue.
        </p>
        <div className="mt-8">
          <PasswordChangeForm />
        </div>
      </section>
    </main>
  );
}
