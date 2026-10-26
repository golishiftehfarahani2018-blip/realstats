"use client";
import { useEffect, useState } from "react";
export default function Join() {
  const [token, setToken] = useState(""),
    [done, setDone] = useState(false),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    setToken(new URLSearchParams(location.hash.slice(1)).get("token") || "");
    history.replaceState(null, "", "/join");
  }, []);
  return (
    <main className="max-w-lg mx-auto p-6 grid gap-4">
      <h1 className="text-2xl font-bold">پذیرش دعوت همکاری دفتر</h1>
      <p>دعوت یک‌بارمصرف است و فقط حساب مشاور ایجاد می‌کند.</p>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {done ? (
        <>
          <p className="success">
            حساب مشاور ساخته شد. اکنون با نام کاربری و رمز خود وارد شوید.
          </p>
          <a href="/" className="primary">
            ورود به دفتر
          </a>
        </>
      ) : (
        <form
          className="card grid gap-3"
          onSubmit={async (e) => {
            e.preventDefault();
            const data = Object.fromEntries(new FormData(e.currentTarget));
            setBusy(true);
            setError("");
            try {
              const c = await (
                await fetch("/api/v1/auth/csrf", { cache: "no-store" })
              ).json();
              const r = await fetch("/api/v1/public/accept-invitation", {
                method: "POST",
                headers: {
                  "Content-Type": "application/json",
                  "X-CSRFToken": c.csrfToken,
                },
                credentials: "same-origin",
                body: JSON.stringify({ ...data, token }),
              });
              const d = await r.json();
              if (!r.ok) throw Error(d.detail || JSON.stringify(d));
              setDone(true);
              setToken("");
            } catch (e) {
              setError((e as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          {!token && (
            <p className="error">
              لینک دعوت کامل را باز کنید؛ کد دعوت در این صفحه دریافت نشده است.
            </p>
          )}
          <label>
            نام نمایشی
            <input name="name" required maxLength={100} />
          </label>
          <label>
            نام کاربری لاتین
            <input name="username" required autoComplete="username" />
          </label>
          <label>
            رمز عبور (حداقل ۱۲ نویسه)
            <input
              type="password"
              name="password"
              minLength={12}
              autoComplete="new-password"
              required
            />
          </label>
          <button className="primary" disabled={busy || !token}>
            ایجاد حساب مشاور
          </button>
        </form>
      )}
    </main>
  );
}
