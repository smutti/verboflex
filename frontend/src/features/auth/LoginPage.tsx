import { t, useUiLanguage } from "@/i18n";
import { LanguagePicker } from "@/i18n/LanguagePicker";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Languages } from "lucide-react";

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
import "./LoginPage.css";

interface LoginFormValues {
  email: string;
  password: string;
}

export function LoginPage() {
  useUiLanguage();
  const { login } = useSession();
  const [authError, setAuthError] = useState(false);
  const form = useForm<LoginFormValues>({
    defaultValues: { email: "", password: "" },
  });

  return (
    <main className="login-page">
      <div className="login-backdrop" aria-hidden="true">
        <svg
          className="login-globe"
          viewBox="0 0 1200 900"
          fill="none"
          focusable="false"
        >
          <g stroke="currentColor" strokeWidth="1">
            <circle cx="600" cy="450" r="350" />
            <ellipse cx="600" cy="450" rx="240" ry="350" />
            <ellipse cx="600" cy="450" rx="100" ry="350" />
            <ellipse cx="600" cy="450" rx="350" ry="245" />
            <ellipse cx="600" cy="450" rx="350" ry="100" />
            <path d="M250 450h700M600 100v700" />
          </g>
          <path
            d="M120 620C260 120 900 80 1080 390M180 260c140 470 680 560 930 210"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeDasharray="4 8"
          />
          <g fill="currentColor">
            <circle cx="285" cy="298" r="5" />
            <circle cx="842" cy="195" r="5" />
            <circle cx="910" cy="650" r="5" />
            <circle cx="350" cy="705" r="5" />
          </g>
        </svg>
        <span className="login-language login-language-hello" lang="en">
          Hello
        </span>
        <span className="login-language login-language-ciao" lang="it">
          Ciao
        </span>
        <span className="login-language login-language-bonjour" lang="fr">
          Bonjour
        </span>
        <span className="login-language login-language-japanese" lang="ja">
          こんにちは
        </span>
        <span
          className="login-language login-language-arabic"
          lang="ar"
          dir="rtl"
        >
          مرحبا
        </span>
        <span className="login-language login-language-vietnamese" lang="vi">
          Xin chào
        </span>
      </div>
      <section className="login-card w-full max-w-md rounded-2xl border bg-card p-6 sm:p-8">
        <div className="flex items-center gap-3">
          <span className="flex size-12 shrink-0 items-center justify-center rounded-xl bg-teal-50 text-primary">
            <Languages aria-hidden="true" className="size-6" />
          </span>
          <h1 className="text-[28px] font-semibold leading-[1.15] tracking-tight">
            VerboFlex
          </h1>
        </div>
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
                  <FormLabel>{t("Email")}</FormLabel>
                  <FormControl>
                    <Input
                      className="min-h-[44px]"
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
                  <FormLabel>{t("Password")}</FormLabel>
                  <FormControl>
                    <Input
                      className="min-h-[44px]"
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
                  {t(
                    "We could not sign you in. Check your email and password, then try again.",
                  )}
                </AlertDescription>
              </Alert>
            ) : null}
            <Button
              aria-busy={form.formState.isSubmitting}
              className="min-h-[44px] w-full"
              disabled={form.formState.isSubmitting}
              type="submit"
            >
              {t("Sign in to VerboFlex")}
            </Button>
          </form>
        </Form>
      </section>
      <div className="absolute right-4 top-4 z-10">
        <LanguagePicker />
      </div>
    </main>
  );
}
