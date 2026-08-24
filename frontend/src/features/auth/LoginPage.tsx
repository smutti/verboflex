import { useState } from "react";
import { useForm } from "react-hook-form";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { useSession } from "./session";

interface LoginFormValues {
  email: string;
  password: string;
}

export function LoginPage() {
  const { login } = useSession();
  const [authError, setAuthError] = useState(false);
  const form = useForm<LoginFormValues>({
    defaultValues: { email: "", password: "" },
  });

  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-6 py-12">
      <section className="w-full max-w-md rounded-lg border bg-card p-6 shadow-xs">
        <h1 className="text-[28px] font-semibold leading-[1.15]">VerboFlex</h1>
        <Form {...form}>
          <form
            className="mt-8 grid gap-6"
            onSubmit={form.handleSubmit(async (values) => {
              setAuthError(false);
              try {
                await login(values);
              } catch {
                setAuthError(true);
              }
            })}
          >
            <FormField
              control={form.control}
              name="email"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Email</FormLabel>
                  <FormControl>
                    <Input
                      autoComplete="username"
                      inputMode="email"
                      type="email"
                      {...field}
                    />
                  </FormControl>
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="password"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Password</FormLabel>
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
            {authError ? (
              <Alert variant="destructive">
                <AlertDescription>
                  We could not sign you in. Check your email and password,
                  then try again.
                </AlertDescription>
              </Alert>
            ) : null}
            <Button
              aria-busy={form.formState.isSubmitting}
              className="w-full"
              disabled={form.formState.isSubmitting}
              type="submit"
            >
              Sign in to VerboFlex
            </Button>
          </form>
        </Form>
      </section>
    </main>
  );
}
