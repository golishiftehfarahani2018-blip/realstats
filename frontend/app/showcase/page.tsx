"use client";
import { useEffect, useState, type FormEvent } from "react";
let csrf = "";
async function api(path: string, method = "GET", data?: any) {
  if (method !== "GET" && !csrf) csrf = (await api("/auth/csrf")).csrfToken;
  const r = await fetch("/api/v1" + path, {
    method,
    credentials: "same-origin",
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...(method === "GET" ? {} : { "X-CSRFToken": csrf }),
    },
    body: data === undefined ? undefined : JSON.stringify(data),
  });
  const d = await r.json();
  if (!r.ok)
    throw Error(typeof d.detail === "string" ? d.detail : JSON.stringify(d));
  if (d.csrfToken) csrf = d.csrfToken;
  return d;
}
const num = (s: string) => new Intl.NumberFormat("fa-IR").format(BigInt(s));
export default function Showcase() {
  const [rows, setRows] = useState<any[]>([]),
    [offset, setOffset] = useState(0),
    [more, setMore] = useState(false),
    [count, setCount] = useState(0),
    [q, setQ] = useState(""),
    [kind, setKind] = useState(""),
    [tx, setTx] = useState(""),
    [me, setMe] = useState<any>(null),
    [office, setOffice] = useState(""),
    [offices, setOffices] = useState<any[]>([]),
    [requests, setRequests] = useState<any[]>([]),
    [favorites, setFavorites] = useState<any[]>([]),
    [tab, setTab] = useState("list"),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false),
    [register, setRegister] = useState(false);
  async function run(fn: () => Promise<void>) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await fn();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function load(start = 0) {
    const params = new URLSearchParams({ offset: String(start), limit: "12" });
    if (q) params.set("q", q);
    if (kind) params.set("kind", kind);
    if (tx) params.set("transaction", tx);
    const d = await api("/public/listings?" + params);
    setRows(d.results);
    setMore(d.has_more);
    setCount(d.count);
    setOffset(start);
    if (!office && d.results.length) setOffice(d.results[0].office);
  }
  useEffect(() => {
    run(async () => {
      const directory = await api("/public/offices");
      setOffices(directory);
      if (directory.length) setOffice(directory[0].id);
      const selected = new URLSearchParams(location.search).get("listing");
      if (selected) {
        const listing = await api(
          "/public/listings/" + encodeURIComponent(selected),
        );
        setRows([listing]);
        setCount(1);
        setMore(false);
        setOffice(listing.office);
      } else await load();
      try {
        setMe(await api("/customer/me"));
      } catch {}
    });
  }, []);
  async function personal(t: string) {
    setTab(t);
    if (t === "requests") setRequests(await api("/customer/requests"));
    if (t === "favorites") setFavorites(await api("/customer/favorites"));
  }
  const form = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    return Object.fromEntries(new FormData(e.currentTarget));
  };
  return (
    <main className="max-w-7xl mx-auto px-5 py-8 grid gap-5">
      <header className="flex flex-wrap justify-between gap-3">
        <h1 className="text-2xl font-bold">ویترین املاک</h1>
        <a className="secondary" href="/">
          ورود کارکنان
        </a>
      </header>
      <p className="muted">
        فقط آگهی‌های دارای رضایت و بازبینی دفتر نمایش داده می‌شوند. تماس
        عرضه‌کننده و نشانی دقیق عمومی نیستند.
      </p>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {notice && (
        <p role="status" className="success">
          {notice}
        </p>
      )}
      <nav className="flex flex-wrap gap-2">
        <button className="secondary" onClick={() => setTab("list")}>
          آگهی‌ها
        </button>
        {me && (
          <>
            <button
              disabled={busy}
              className="secondary"
              onClick={() => run(() => personal("requests"))}
            >
              درخواست‌های من
            </button>
            <button
              disabled={busy}
              className="secondary"
              onClick={() => run(() => personal("favorites"))}
            >
              علاقه‌مندی‌ها
            </button>
            <button
              className="secondary"
              onClick={() =>
                run(async () => {
                  await api("/customer/auth/logout", "POST", {});
                  setMe(null);
                  setRequests([]);
                  setFavorites([]);
                  setTab("list");
                })
              }
            >
              خروج {me.username}
            </button>
          </>
        )}
      </nav>
      {!me && (
        <details className="card">
          <summary>ورود یا ساخت حساب مشتری برای ثبت و پیگیری درخواست</summary>
          <form
            className="grid md:grid-cols-2 gap-3 mt-4"
            onSubmit={(e) => {
              const d = form(e);
              run(async () => {
                await api(
                  "/customer/auth/" + (register ? "register" : "login"),
                  "POST",
                  { ...d, office },
                );
                setMe(await api("/customer/me"));
                setNotice("وارد حساب مشتری شدید.");
              });
            }}
          >
            <label>
              دفتر
              <select
                value={office}
                onChange={(e) => setOffice(e.target.value)}
                required
              >
                <option value="">انتخاب دفتر</option>
                {offices.map(({ id, name }) => (
                  <option key={id} value={id}>
                    {name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              نام کاربری
              <input name="username" autoComplete="username" required />
            </label>
            <label>
              رمز عبور (حداقل ۱۲ نویسه)
              <input
                name="password"
                type="password"
                autoComplete={register ? "new-password" : "current-password"}
                minLength={12}
                required
              />
            </label>
            <label>
              <input
                className="w-auto"
                type="checkbox"
                checked={register}
                onChange={(e) => setRegister(e.target.checked)}
              />{" "}
              ساخت حساب تازه
            </label>
            <button disabled={busy} className="primary">
              {register ? "ساخت حساب" : "ورود"}
            </button>
          </form>
          <p className="muted mt-3">
            این ورود با رمز عبور است؛ تأیید شماره تلفن و پیامک در این نسخه فعال
            نیست.
          </p>
        </details>
      )}
      {tab === "requests" ? (
        <section className="grid gap-3">
          <h2>درخواست‌های من</h2>
          {requests.length === 0 && <p>درخواستی ثبت نکرده‌اید.</p>}
          {requests.map((x) => (
            <article className="card" key={x.id}>
              <p>
                کد {x.id.slice(0, 8)} ·{" "}
                {
                  (
                    {
                      received: "دریافت‌شده",
                      contacted: "تماس گرفته شد",
                      closed: "بسته‌شده",
                    } as any
                  )[x.status]
                }
              </p>
              <p className="whitespace-pre-wrap">{x.message}</p>
            </article>
          ))}
        </section>
      ) : (
        <>
          <form
            className="card flex flex-wrap gap-3"
            onSubmit={(e) => {
              e.preventDefault();
              run(() => load(0));
            }}
          >
            <label>
              محله
              <input value={q} onChange={(e) => setQ(e.target.value)} />
            </label>
            <label>
              نوع ملک
              <select value={kind} onChange={(e) => setKind(e.target.value)}>
                <option value="">همه</option>
                {[
                  ["apartment", "آپارتمان"],
                  ["villa", "ویلا"],
                  ["land", "زمین"],
                  ["commercial", "تجاری"],
                  ["office", "اداری"],
                  ["other", "سایر"],
                ].map(([v, n]) => (
                  <option key={v} value={v}>
                    {n}
                  </option>
                ))}
              </select>
            </label>
            <label>
              معامله
              <select value={tx} onChange={(e) => setTx(e.target.value)}>
                <option value="">همه</option>
                <option value="sale">فروش</option>
                <option value="rent">اجاره</option>
              </select>
            </label>
            <button disabled={busy} className="primary">
              جستجو
            </button>
          </form>
          <p>
            {tab === "favorites" ? "علاقه‌مندی‌های فعال شما" : count + " آگهی"}
          </p>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
            {(tab === "favorites" ? favorites : rows).map((x) => (
              <article className="card grid gap-3" key={x.id}>
                {x.images?.length > 0 && (
                  <img
                    src={"/api/v1/public/images/" + x.images[0]}
                    alt={"ملک در " + x.district}
                    className="w-full rounded-lg object-cover"
                    style={{ maxHeight: 240 }}
                  />
                )}
                <a href={"/showcase?listing=" + x.id} className="secondary">
                  جزئیات و لینک این آگهی
                </a>
                {x.images?.length > 1 && (
                  <details>
                    <summary>سایر تصاویر بازبینی‌شده</summary>
                    {x.images.slice(1).map((id: string) => (
                      <img
                        key={id}
                        src={"/api/v1/public/images/" + id}
                        alt={"تصویر ملک در " + x.district}
                        className="w-full rounded-lg"
                      />
                    ))}
                  </details>
                )}
                <h2 className="font-bold">
                  {x.district} · {x.area} متر
                </h2>
                {x.details && (
                  <p className="muted">
                    مشخصات اعلامی:{" "}
                    {Object.entries(x.details)
                      .map(
                        ([k, v]) =>
                          ((
                            ({
                              rooms: "اتاق",
                              floor: "طبقه",
                              floors: "تعداد طبقات",
                              elevator: "آسانسور",
                              parking: "پارکینگ",
                              water: "آب",
                              gas: "گاز",
                              electricity: "برق",
                              land_use: "کاربری",
                              access: "دسترسی",
                            }) as any
                          )[k] || k) +
                          " " +
                          ((
                            {
                              yes: "دارد",
                              no: "ندارد",
                              unknown: "نامعلوم",
                              residential: "مسکونی",
                              agricultural: "کشاورزی",
                              commercial: "تجاری",
                              paved: "آسفالت",
                              dirt: "خاکی",
                            } as any
                          )[String(v)] || String(v ?? "نامعلوم")),
                      )
                      .join(" · ")}
                  </p>
                )}
                <p>
                  {x.office_name} ·{" "}
                  {x.transaction === "sale" ? "فروش" : "اجاره"}
                </p>
                <p>
                  {x.transaction === "sale"
                    ? x.negotiable_price
                      ? "قیمت توافقی"
                      : "قیمت " + num(x.price_toman)
                    : "ودیعه " +
                      num(x.deposit_toman) +
                      " · اجاره " +
                      num(x.rent_toman)}{" "}
                  تومان
                </p>
                {me && me.office === x.office && (
                  <>
                    <button
                      disabled={busy}
                      className="secondary"
                      onClick={() =>
                        run(async () => {
                          if (tab === "favorites") {
                            await api("/customer/favorites/" + x.id, "DELETE");
                            await personal("favorites");
                          } else {
                            await api(
                              "/customer/favorites/" + x.id,
                              "POST",
                              {},
                            );
                            setNotice("به علاقه‌مندی‌ها افزوده شد.");
                          }
                        })
                      }
                    >
                      {tab === "favorites"
                        ? "حذف علاقه‌مندی"
                        : "ذخیره علاقه‌مندی"}
                    </button>
                    <form
                      className="grid gap-2"
                      onSubmit={(e) => {
                        const d = form(e);
                        run(async () => {
                          await api("/customer/requests", "POST", {
                            ...d,
                            publication: x.id,
                          });
                          setNotice(
                            "درخواست ثبت شد؛ وضعیت را در درخواست‌های من ببینید.",
                          );
                        });
                      }}
                    >
                      <label>
                        درخواست
                        <select name="kind">
                          <option value="visit">بازدید</option>
                          <option value="information">اطلاعات بیشتر</option>
                        </select>
                      </label>
                      <label>
                        توضیح و روش تماس خودتان
                        <textarea name="message" maxLength={1000} required />
                      </label>
                      <button disabled={busy} className="primary">
                        ارسال درخواست به دفتر
                      </button>
                    </form>
                  </>
                )}
              </article>
            ))}
          </div>
          {rows.length === 0 && (
            <p>آگهی منتشرشده‌ای برای این فیلتر وجود ندارد.</p>
          )}
          {tab === "list" && (
            <div className="flex gap-3">
              <button
                disabled={busy || offset === 0}
                className="secondary"
                onClick={() => run(() => load(Math.max(0, offset - 12)))}
              >
                قبلی
              </button>
              <button
                disabled={busy || !more}
                className="secondary"
                onClick={() => run(() => load(offset + 12))}
              >
                بعدی
              </button>
            </div>
          )}
        </>
      )}
    </main>
  );
}
