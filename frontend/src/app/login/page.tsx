'use client';

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { getSession, login } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [password, setPassword] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  useEffect(() => {
    const checkSession = async () => {
      try {
        await getSession();
        router.replace("/");
      } catch {
        // Not authenticated; stay on login page
      }
    };
    void checkSession();
  }, [router]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);

    const trimmedPassword = password.trim();
    if (!trimmedPassword) {
      setError("Password is required.");
      return;
    }

    setIsSubmitting(true);
    try {
      await login(trimmedPassword);
      router.push("/");
    } catch (loginError) {
      setError(
        loginError instanceof Error
          ? loginError.message
          : "Unable to sign in. Please try again."
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-b from-slate-50 to-slate-100 px-4 dark:from-black dark:to-zinc-900">
      <Card className="w-full max-w-md border-slate-200 shadow-lg dark:border-zinc-800">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl font-semibold">Welcome back</CardTitle>
          <CardDescription>
            Enter the demo password to continue.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div className="space-y-2">
              <label
                htmlFor="password"
                className="text-sm font-medium text-foreground"
              >
                Password
              </label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Enter password"
                autoComplete="current-password"
                aria-invalid={Boolean(error)}
                aria-describedby={error ? "password-error" : undefined}
                required
              />
              {error ? (
                <p id="password-error" className="text-sm text-destructive">
                  {error}
                </p>
              ) : null}
            </div>
            <Button
              type="submit"
              className="w-full"
              disabled={isSubmitting}
            >
              {isSubmitting ? "Signing in..." : "Sign in"}
            </Button>
          </form>
        </CardContent>
        <CardFooter className="justify-center">
          <p className="text-xs text-muted-foreground">
            Access is protected for demo purposes only.
          </p>
        </CardFooter>
      </Card>
    </div>
  );
}
