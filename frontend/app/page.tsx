"use client";
import { useEffect, useState, type FormEvent } from "react";
import BusinessWorkspace from "./business-workspace";
import CRMWorkspace, { AssignmentForm } from "./crm-workspace";
type Me = {
  username: string;
  name: string;
  role: string;
  office_name: string;
  branding: { color?: string };
};
type Offering = {
  negotiable_price?: boolean;
  details?: Record<string, string | number | null>;
  can_edit: boolean;
  can_view_private: boolean;
  can_review: boolean;
  id: string;
  kind: string;
  district: string;
  area: string;
  transaction: string;
  price_toman: string;
  deposit_toman: string;
  rent_toman: string;
  status: string;
  version: number;
  review_reason: string;
  created_at: string;
};
type Advisor = { id: string; username: string; name: string; active: boolean };
type Private = {
  owner_version: number;
  owner_name: string;
  owner_phone: string;
  exact_address: string;
};
type Doc = { id: string; content_type: string; size: number };
const statuses: Record<string, string> = {
  draft: "پیش‌نویس",
  submitted: "در انتظار بررسی",
  revision: "نیازمند اصلاح",
  approved: "تأییدشده",
};
const kinds: Record<string, string> = {
  apartment: "آپارتمان",
  villa: "ویلا",
  land: "زمین",
  commercial: "تجاری",
  office: "اداری",
  other: "سایر",
};
const num = (v: string | number) =>
  new Intl.NumberFormat("fa-IR").format(
    String(v).includes(".") ? Number(v) : BigInt(v),
  );
const date = (v: string) =>
  new Intl.DateTimeFormat("fa-IR-u-ca-persian", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Asia/Tehran",
  }).format(new Date(v));
let csrf = "";
class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}
async function api(path: string, method = "GET", body?: unknown): Promise<any> {
  if (!csrf && method !== "GET") csrf = (await api("/auth/csrf")).csrfToken;
  const isFile = body instanceof FormData;
  const r = await fetch("/api/v1" + path, {
    method,
    credentials: "same-origin",
    cache: "no-store",
    headers: {
      ...(isFile ? {} : { "Content-Type": "application/json" }),
      ...(method === "GET" ? {} : { "X-CSRFToken": csrf }),
    },
    body: body === undefined ? undefined : isFile ? body : JSON.stringify(body),
  });
  if (!r.ok) {
    let d;
    try {
      d = await r.json();
    } catch {
      d = { detail: "پاسخ معتبر دریافت نشد." };
    }
    throw new ApiError(
      r.status,
      typeof d.detail === "string" ? d.detail : JSON.stringify(d),
    );
  }
  return r.json();
}
function Field({
  name,
  label,
  type = "text",
  required = true,
  defaultValue,
}: {
  name: string;
  label: string;
  type?: string;
  required?: boolean;
  defaultValue?: string;
}) {
  return (
    <label>
      {label}
      <input
        name={name}
        type={type}
        required={required}
        defaultValue={defaultValue}
        autoComplete={type === "password" ? "new-password" : "off"}
      />
    </label>
  );
}
export default function Home() {
  const [me, setMe] = useState<Me | null>(null),
    [loading, setLoading] = useState(true),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const [draftKind, setDraftKind] = useState("apartment");
  const [tab, setTab] = useState("bank"),
    [items, setItems] = useState<Offering[]>([]),
    [advisors, setAdvisors] = useState<Advisor[]>([]),
    [q, setQ] = useState("");
  const [selected, setSelected] = useState<Offering | null>(null),
    [privateData, setPrivateData] = useState<Private | null>(null),
    [docs, setDocs] = useState<Doc[]>([]),
    [audit, setAudit] = useState<any[]>([]);
  function clearPrivate() {
    setPrivateData(null);
    setDocs([]);
  }
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [pageOffset, setPageOffset] = useState(0),
    [total, setTotal] = useState(0),
    [more, setMore] = useState(false);
  async function load(offset = pageOffset, section = tab) {
    const params = new URLSearchParams({
      paginated: "1",
      offset: String(offset),
      limit: "30",
    });
    if (q) params.set("q", q);
    for (const [key, value] of Object.entries(filters))
      if (value) params.set(key, value);
    if (section === "bank") params.set("status", "approved");
    if (section === "review") params.set("status", "submitted");
    const result = await api("/offerings?" + params);
    setItems(result.results);
    setTotal(result.count);
    setMore(result.has_more);
    setPageOffset(offset);
  }
  async function run(fn: () => Promise<void>) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await fn();
    } catch (e) {
      const err = e as ApiError;
      setError(err.message);
      if (
        err.status === 403 &&
        /Authentication|احراز|اعتبارنامه/.test(err.message)
      ) {
        setMe(null);
        clearPrivate();
        setItems([]);
      }
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => {
    api("/me")
      .then(setMe)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);
  useEffect(() => {
    if (me) {
      run(() => load());
      if (me.branding.color && /^#[0-9a-f]{6}$/i.test(me.branding.color))
        document.documentElement.style.setProperty(
          "--brand",
          me.branding.color,
        );
    }
  }, [me]);
  async function login(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const d = Object.fromEntries(new FormData(e.currentTarget));
    await run(async () => {
      const res = await api("/auth/login", "POST", d);
      csrf = res.csrfToken;
      setMe(await api("/me"));
    });
  }
  async function create(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const raw = Object.fromEntries(new FormData(form));
    const details = Object.fromEntries(
      Object.entries(raw)
        .filter(([k, v]) => k.startsWith("feature_") && v !== "")
        .map(([k, v]) => [k.slice(8), v]),
    );
    const d = {
      negotiable_price: raw.negotiable_price === "on",
      ...Object.fromEntries(
        Object.entries(raw).filter(
          ([k]) => !k.startsWith("feature_") && k !== "negotiable_price",
        ),
      ),
      details,
    };
    await run(async () => {
      const o = await api("/offerings", "POST", d);
      setSelected(o);
      clearPrivate();
      await load();
      setTab("mine");
      form.reset();
      setNotice("ملک و عرضه به صورت پیش‌نویس ذخیره شدند.");
    });
  }
  async function action(name: string, extra: Record<string, unknown> = {}) {
    if (!selected) return;
    await run(async () => {
      const o = await api(
        "/offerings/" + selected.id + (name === "edit" ? "" : "/" + name),
        name === "edit" ? "PATCH" : "POST",
        { version: selected.version, ...extra },
      );
      setSelected(o);
      clearPrivate();
      await load();
      setNotice("تغییر ثبت شد.");
    });
  }
  async function advisorCreate(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const d = Object.fromEntries(new FormData(form));
    await run(async () => {
      await api("/advisors", "POST", d);
      setAdvisors(await api("/advisors"));
      form.reset();
      setNotice("حساب مشاور ایجاد شد.");
    });
  }
  const isReviewer = me?.role === "manager" || me?.role === "senior";
  if (loading)
    return (
      <main className="p-10" aria-busy="true">
        در حال بررسی نشست…
      </main>
    );
  if (!me)
    return (
      <main className="max-w-md mx-auto px-5 py-16">
        <p className="muted mb-3">سامانه تخصصی دفتر املاک</p>
        <h1 className="text-3xl font-bold mb-3">ورود به فضای کار</h1>
        <a className="secondary" href="/showcase">
          مرور ویترین عمومی
        </a>
        <p className="muted mb-8">
          اطلاعات داخلی دفتر فقط برای اعضای مجاز در دسترس است.
        </p>
        {error && (
          <p role="alert" className="error mb-5">
            {error}
          </p>
        )}
        <form onSubmit={login} className="card grid gap-5">
          <label>
            نام کاربری
            <input name="username" dir="ltr" autoComplete="username" required />
          </label>
          <label>
            رمز عبور
            <input
              name="password"
              dir="ltr"
              type="password"
              autoComplete="current-password"
              required
            />
          </label>
          <button className="primary" disabled={busy}>
            ورود امن
          </button>
        </form>
      </main>
    );
  const shown = items.filter((x) =>
    tab === "bank"
      ? x.status === "approved"
      : tab === "review"
        ? x.status === "submitted"
        : true,
  );
  return (
    <div className="min-h-screen">
      <header className="bg-white border-b border-slate-200 px-5 py-5">
        <div className="max-w-7xl mx-auto flex justify-between gap-3 items-center">
          <div>
            <p className="muted text-xs mb-1">فضای کار دفتر</p>
            <h1 className="text-xl font-bold">{me.office_name}</h1>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <span>{me.name || me.username}</span>
            <button
              className="secondary"
              onClick={() =>
                run(async () => {
                  await api("/auth/logout", "POST");
                  csrf = "";
                  setMe(null);
                  setItems([]);
                  setSelected(null);
                  clearPrivate();
                })
              }
            >
              خروج
            </button>
          </div>
        </div>
      </header>
      <main className="max-w-7xl mx-auto p-4 md:p-8">
        <div className="mb-7">
          <h2 className="text-2xl font-bold mb-2">پرونده‌های دفتر</h2>
          <p className="muted text-sm">
            ثبت سریع، بررسی روشن و دسترسی متناسب با مسئولیت
          </p>
        </div>
        <nav aria-label="بخش‌های پنل" className="flex flex-wrap gap-2 mb-6">
          {[
            ["bank", "بانک مشترک"],
            ["mine", "پرونده‌های در دسترس"],
            ["new", "ثبت ملک و عرضه"],
            ["crm", "مشتری و همکاری"],
            ["business", "دفتر، انتشار و مالی"],
            ...(isReviewer ? [["review", "صف بررسی"]] : []),
            ...(me.role === "manager"
              ? [
                  ["team", "مشاوران"],
                  ["audit", "رویدادها"],
                ]
              : []),
          ].map(([id, title]) => (
            <button
              key={id}
              className={tab === id ? "primary" : "secondary"}
              onClick={() =>
                run(async () => {
                  setTab(id);
                  setSelected(null);
                  clearPrivate();
                  if (id === "team") setAdvisors(await api("/advisors"));
                  else if (id === "audit") setAudit(await api("/audit"));
                  else if (!["crm", "business"].includes(id)) await load(0, id);
                })
              }
            >
              {title}
            </button>
          ))}
        </nav>
        {error && (
          <p role="alert" className="error mb-5">
            {error}
            {selected && (
              <button
                className="secondary mr-3"
                onClick={() =>
                  run(async () => {
                    setSelected(await api("/offerings/" + selected.id));
                    clearPrivate();
                    await load();
                  })
                }
              >
                بارگذاری نسخه جدید
              </button>
            )}
          </p>
        )}
        {notice && (
          <p role="status" className="success mb-5">
            {notice}
          </p>
        )}
        {tab === "business" ? (
          <BusinessWorkspace api={api} isManager={me.role === "manager"} />
        ) : tab === "crm" ? (
          <CRMWorkspace
            key={me.username}
            api={api}
            isManager={me.role === "manager"}
            onExpired={() => {
              setMe(null);
              setItems([]);
              setSelected(null);
              clearPrivate();
            }}
            onOffering={async (id) => {
              const o = await api("/offerings/" + id);
              setSelected(o);
              clearPrivate();
              setTab("mine");
              await load();
            }}
          />
        ) : tab === "new" ? (
          <form onSubmit={create} className="card grid gap-5">
            <h3 className="font-bold text-lg">ثبت پیش‌نویس جدید</h3>
            <div className="grid md:grid-cols-3 gap-5">
              <label>
                نوع ملک
                <select
                  name="kind"
                  value={draftKind}
                  onChange={(e) => setDraftKind(e.target.value)}
                >
                  {Object.entries(kinds).map(([k, v]) => (
                    <option key={k} value={k}>
                      {v}
                    </option>
                  ))}
                </select>
              </label>
              <Field name="district" label="محله (قابل مشاهده داخلی)" />
              <Field name="area" label="متراژ، متر مربع" />
              <label>
                نوع عرضه
                <select name="transaction">
                  <option value="sale">فروش</option>
                  <option value="rent">اجاره</option>
                </select>
              </label>
              <label>
                <input
                  type="checkbox"
                  className="w-auto"
                  name="negotiable_price"
                />{" "}
                قیمت فروش توافقی است؛ برای بودجه نیاز به استعلام دارد.
              </label>
              <Field
                name="price_toman"
                label="قیمت فروش، تومان"
                defaultValue="0"
              />
              <Field
                name="deposit_toman"
                label="ودیعه، تومان"
                defaultValue="0"
              />
              <Field
                name="rent_toman"
                label="اجاره ماهانه، تومان"
                defaultValue="0"
              />
            </div>
            <section className="grid md:grid-cols-3 gap-3">
              <h4 className="font-bold col-span-full">
                مشخصات اعلامی ملک؛ نیازمند بررسی
              </h4>
              {!["land"].includes(draftKind) &&
                [
                  ["rooms", "تعداد اتاق"],
                  ["floor", "طبقه"],
                  ["floors", "تعداد طبقات"],
                ].map(([k, l]) => (
                  <label key={k}>
                    {l}
                    <input
                      name={"feature_" + k}
                      placeholder="نامعلوم"
                      inputMode="numeric"
                    />
                  </label>
                ))}
              {[
                ["water", "آب"],
                ["gas", "گاز"],
                ["electricity", "برق"],
                ...(!["land"].includes(draftKind)
                  ? [
                      ["elevator", "آسانسور"],
                      ["parking", "پارکینگ"],
                    ]
                  : []),
              ].map(([k, l]) => (
                <label key={k}>
                  {l}
                  <select name={"feature_" + k}>
                    <option value="unknown">نامعلوم</option>
                    <option value="yes">دارد</option>
                    <option value="no">ندارد</option>
                  </select>
                </label>
              ))}
              {draftKind === "land" && (
                <>
                  <label>
                    کاربری اعلامی
                    <select name="feature_land_use">
                      <option value="unknown">نامعلوم</option>
                      <option value="residential">مسکونی</option>
                      <option value="agricultural">کشاورزی</option>
                      <option value="commercial">تجاری</option>
                    </select>
                  </label>
                  <label>
                    دسترسی
                    <select name="feature_access">
                      <option value="unknown">نامعلوم</option>
                      <option value="paved">آسفالت</option>
                      <option value="dirt">خاکی</option>
                    </select>
                  </label>
                </>
              )}
            </section>
            <div className="border-t border-slate-200 pt-5">
              <h4 className="font-bold mb-2">اطلاعات خصوصی مالک</h4>
              <p className="muted text-sm mb-4">
                فقط مدیر مجاز و معرف همین عرضه به این بخش دسترسی دارند.
              </p>
              <div className="grid md:grid-cols-3 gap-5">
                <Field name="owner_name" label="نام مالک" />
                <Field name="owner_phone" label="شماره همراه مالک" />
                <Field name="exact_address" label="نشانی دقیق" />
              </div>
            </div>
            <button className="primary justify-self-start" disabled={busy}>
              ذخیره پیش‌نویس
            </button>
          </form>
        ) : tab === "team" ? (
          <div className="grid lg:grid-cols-2 gap-5">
            <section className="card">
              <h3 className="font-bold mb-5">اعضای دفتر</h3>
              <div className="grid gap-4">
                {advisors.map((a) => (
                  <div
                    key={a.id}
                    className="flex justify-between gap-3 items-center border-b border-slate-100 pb-4"
                  >
                    <div>
                      <p>{a.name}</p>
                      <p className="muted text-xs">
                        {a.username} · {a.active ? "فعال" : "غیرفعال"}
                      </p>
                    </div>
                    <button
                      disabled={busy}
                      className="secondary"
                      onClick={() =>
                        run(async () => {
                          await api("/advisors/" + a.id, "PATCH", {
                            active: !a.active,
                          });
                          setAdvisors(await api("/advisors"));
                        })
                      }
                    >
                      {a.active ? "غیرفعال‌کردن" : "فعال‌کردن"}
                    </button>
                  </div>
                ))}
              </div>
            </section>
            <form onSubmit={advisorCreate} className="card grid gap-4">
              <h3 className="font-bold">ایجاد مشاور</h3>
              <Field name="first_name" label="نام نمایشی" />
              <Field name="username" label="نام کاربری لاتین" />
              <Field
                name="password"
                type="password"
                label="رمز عبور اولیه (حداقل ۱۲ نویسه)"
              />
              <button className="primary" disabled={busy}>
                ایجاد حساب مشاور
              </button>
            </form>
          </div>
        ) : tab === "audit" ? (
          <section className="card overflow-auto">
            <h3 className="font-bold mb-4">رویدادهای دفتر</h3>
            <table className="w-full text-sm text-right">
              <thead>
                <tr>
                  <th>عملیات</th>
                  <th>نتیجه</th>
                  <th>زمان تهران</th>
                </tr>
              </thead>
              <tbody>
                {audit.map((x) => (
                  <tr className="border-t border-slate-100" key={x.id}>
                    <td className="p-3" dir="ltr">
                      {x.action}
                    </td>
                    <td>{x.outcome === "allowed" ? "مجاز" : "ردشده"}</td>
                    <td>{date(x.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        ) : (
          <div className="grid lg:grid-cols-[1fr_1fr] gap-5">
            <section>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  run(() => load(0));
                }}
                className="grid grid-cols-2 gap-2 mb-4"
              >
                <input
                  aria-label="جستجوی محله"
                  placeholder="جستجو بر اساس محله…"
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                />
                <label>
                  نوع ملک
                  <select
                    aria-label="فیلتر نوع ملک"
                    value={filters.kind || ""}
                    onChange={(e) =>
                      setFilters({ ...filters, kind: e.target.value })
                    }
                  >
                    <option value="">همه انواع</option>
                    {Object.entries(kinds).map(([v, label]) => (
                      <option key={v} value={v}>
                        {label}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  نوع معامله
                  <select
                    aria-label="فیلتر معامله"
                    value={filters.transaction || ""}
                    onChange={(e) => {
                      setFilters({
                        area_min: filters.area_min || "",
                        area_max: filters.area_max || "",
                        kind: filters.kind || "",
                        transaction: e.target.value,
                      });
                    }}
                  >
                    <option value="">همه معاملات</option>
                    <option value="sale">فروش</option>
                    <option value="rent">اجاره</option>
                  </select>
                </label>
                {[
                  ["area_min", "حداقل متراژ"],
                  ["area_max", "حداکثر متراژ"],
                  ...(filters.transaction === "sale"
                    ? [
                        ["price_min", "حداقل قیمت فروش (تومان)"],
                        ["price_max", "حداکثر قیمت فروش (تومان)"],
                      ]
                    : filters.transaction === "rent"
                      ? [
                          ["deposit_min", "حداقل ودیعه (تومان)"],
                          ["deposit_max", "حداکثر ودیعه (تومان)"],
                          ["rent_min", "حداقل اجاره (تومان)"],
                          ["rent_max", "حداکثر اجاره (تومان)"],
                        ]
                      : []),
                ].map(([key, label]) => (
                  <label key={key}>
                    {label}
                    <input
                      inputMode="decimal"
                      value={filters[key] || ""}
                      onChange={(e) =>
                        setFilters({ ...filters, [key]: e.target.value })
                      }
                    />
                  </label>
                ))}
                <button className="secondary" disabled={busy}>
                  اعمال فیلترها
                </button>
              </form>
              <div
                className="flex flex-wrap items-center gap-3 mb-4"
                aria-label="صفحه‌بندی املاک"
              >
                <span>
                  {num(total)} پرونده · صفحه{" "}
                  {num(Math.floor(pageOffset / 30) + 1)}
                </span>
                <button
                  className="secondary"
                  disabled={busy || pageOffset === 0}
                  onClick={() => run(() => load(Math.max(0, pageOffset - 30)))}
                >
                  قبلی
                </button>
                <button
                  className="secondary"
                  disabled={busy || !more}
                  onClick={() => run(() => load(pageOffset + 30))}
                >
                  بعدی
                </button>
              </div>
              <div className="grid gap-3">
                {shown.length === 0 && (
                  <p className="card muted">پرونده‌ای در این بخش یافت نشد.</p>
                )}
                {shown.map((o) => (
                  <button
                    key={o.id}
                    className="card text-right w-full"
                    onClick={() => {
                      setSelected(o);
                      clearPrivate();
                      setError("");
                    }}
                  >
                    <div className="flex justify-between mb-3 gap-2">
                      <strong>
                        {kinds[o.kind]} · {o.district}
                      </strong>
                      <span className="badge">{statuses[o.status]}</span>
                    </div>
                    <div className="flex justify-between gap-3 text-sm muted">
                      <span>
                        {num(o.area)} متر ·{" "}
                        {o.transaction === "sale" ? "فروش" : "اجاره"}
                      </span>
                      <span>
                        {num(
                          o.transaction === "sale"
                            ? o.price_toman
                            : o.rent_toman,
                        )}{" "}
                        تومان
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            </section>
            <section className="card self-start" aria-label="جزئیات عرضه">
              {!selected ? (
                <p className="muted py-12 text-center">
                  یک پرونده را برای بررسی انتخاب کنید.
                </p>
              ) : (
                <div className="grid gap-5">
                  <div>
                    <span className="badge mb-3">
                      {statuses[selected.status]}
                    </span>
                    <h3 className="text-xl font-bold">
                      {kinds[selected.kind]} در {selected.district}
                    </h3>
                    <p className="muted text-sm mt-2">
                      {num(selected.area)} متر مربع · نسخه{" "}
                      {num(selected.version)}
                    </p>
                    <p className="text-xs muted mt-2">
                      {date(selected.created_at)}
                    </p>
                  </div>
                  <dl className="grid gap-2 text-sm">
                    <div>
                      قیمت:{" "}
                      {selected.negotiable_price
                        ? "توافقی"
                        : num(selected.price_toman) + " تومان"}
                    </div>
                    <div>ودیعه: {num(selected.deposit_toman)} تومان</div>
                    <div>اجاره: {num(selected.rent_toman)} تومان</div>
                  </dl>
                  {selected.details && (
                    <p className="muted text-sm">
                      مشخصات اعلامی:{" "}
                      {Object.entries(selected.details)
                        .map(
                          ([k, v]) =>
                            ((
                              ({
                                rooms: "اتاق",
                                floor: "طبقه",
                                floors: "طبقات",
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
                  {selected.review_reason && (
                    <p className="error">
                      دلیل اصلاح: {selected.review_reason}
                    </p>
                  )}
                  {selected.can_edit && (
                    <>
                      <form
                        onSubmit={(e) => {
                          e.preventDefault();
                          action(
                            "edit",
                            Object.fromEntries(new FormData(e.currentTarget)),
                          );
                        }}
                        className="grid gap-3"
                        key={selected.id + "-" + selected.version}
                      >
                        <Field
                          name="district"
                          label="محله"
                          defaultValue={selected.district}
                        />
                        <Field
                          name="area"
                          label="متراژ، متر مربع"
                          defaultValue={selected.area}
                        />
                        <label>
                          نوع ملک
                          <select name="kind" defaultValue={selected.kind}>
                            {Object.entries(kinds).map(([k, v]) => (
                              <option key={k} value={k}>
                                {v}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label>
                          نوع عرضه
                          <select
                            name="transaction"
                            defaultValue={selected.transaction}
                          >
                            <option value="sale">فروش</option>
                            <option value="rent">اجاره</option>
                          </select>
                        </label>
                        <Field
                          name="price_toman"
                          label="ویرایش قیمت فروش، تومان"
                          defaultValue={selected.price_toman}
                        />
                        <Field
                          name="deposit_toman"
                          label="ویرایش ودیعه، تومان"
                          defaultValue={selected.deposit_toman}
                        />
                        <Field
                          name="rent_toman"
                          label="ویرایش اجاره، تومان"
                          defaultValue={selected.rent_toman}
                        />
                        <button className="secondary" disabled={busy}>
                          ذخیره قیمت‌ها
                        </button>
                      </form>
                      <button
                        className="primary"
                        disabled={busy}
                        onClick={() => action("submit")}
                      >
                        ارسال برای بررسی
                      </button>
                    </>
                  )}
                  {selected.can_review && (
                    <div className="grid gap-3">
                      <button
                        className="primary"
                        disabled={busy}
                        onClick={() =>
                          action("review", { decision: "approved" })
                        }
                      >
                        تأیید داخلی
                      </button>
                      <form
                        className="grid gap-3"
                        onSubmit={(e) => {
                          e.preventDefault();
                          action("review", {
                            decision: "revision",
                            reason: new FormData(e.currentTarget).get("reason"),
                          });
                        }}
                      >
                        <label>
                          دلیل بازگشت برای اصلاح
                          <textarea required name="reason" maxLength={500} />
                        </label>
                        <button className="secondary" disabled={busy}>
                          بازگشت برای اصلاح
                        </button>
                      </form>
                      <p className="text-xs muted">
                        تأیید داخلی، انتشار عمومی ایجاد نمی‌کند.
                      </p>
                    </div>
                  )}
                  <div className="border-t border-slate-200 pt-5">
                    {me.role === "manager" && (
                      <AssignmentForm
                        key={selected.id + selected.version}
                        api={api}
                        path={"/offerings/" + selected.id}
                        version={selected.version}
                        onUpdated={async () => {
                          setSelected(await api("/offerings/" + selected.id));
                          clearPrivate();
                          await load();
                        }}
                      />
                    )}
                    <h4 className="font-bold mb-3">اطلاعات خصوصی</h4>
                    {!selected.can_view_private ? (
                      <p className="muted text-sm">
                        اطلاعات مالک و نشانی دقیق فقط در اختیار مدیر مجاز و معرف
                        عرضه است.
                      </p>
                    ) : !privateData ? (
                      <button
                        className="secondary"
                        disabled={busy}
                        onClick={() =>
                          run(async () => {
                            const d = await api(
                              "/offerings/" + selected.id + "/private",
                            );
                            setPrivateData(d);
                            setDocs(
                              await api(
                                "/offerings/" + selected.id + "/documents",
                              ),
                            );
                          })
                        }
                      >
                        دریافت با بررسی مجوز و ثبت رویداد
                      </button>
                    ) : (
                      <div className="grid gap-3 text-sm">
                        <p>مالک: {privateData.owner_name}</p>
                        <p>
                          تماس: <b dir="ltr">{privateData.owner_phone}</b>
                        </p>
                        <p>نشانی: {privateData.exact_address}</p>
                        {selected.can_edit && (
                          <form
                            className="grid gap-3"
                            onSubmit={(e) => {
                              e.preventDefault();
                              action(
                                "edit",
                                Object.fromEntries(
                                  new FormData(e.currentTarget),
                                ),
                              );
                            }}
                          >
                            <input
                              type="hidden"
                              name="owner_version"
                              value={privateData.owner_version}
                            />
                            <Field
                              name="owner_name"
                              label="اصلاح نام مالک"
                              defaultValue={privateData.owner_name}
                            />
                            <label>
                              شماره مالک (اصلاح هویت نیازمند بررسی جداست)
                              <input
                                value={privateData.owner_phone}
                                readOnly
                                dir="ltr"
                              />
                            </label>
                            <Field
                              name="exact_address"
                              label="اصلاح نشانی دقیق"
                              defaultValue={privateData.exact_address}
                            />
                            <button className="secondary" disabled={busy}>
                              ذخیره اصلاحات خصوصی
                            </button>
                          </form>
                        )}
                        <h5 className="font-bold mt-3">
                          مدرک خصوصی (تصویر JPEG یا PNG)
                        </h5>
                        {docs.map((d, i) => (
                          <button
                            key={d.id}
                            className="secondary"
                            onClick={() =>
                              run(async () => {
                                const r = await fetch(
                                  "/api/v1/offerings/" +
                                    selected.id +
                                    "/documents/" +
                                    d.id,
                                  {
                                    credentials: "same-origin",
                                    cache: "no-store",
                                  },
                                );
                                if (!r.ok)
                                  throw new Error(
                                    "دریافت مدرک مجاز نیست یا ذخیره‌ساز در دسترس نیست.",
                                  );
                                const url = URL.createObjectURL(await r.blob());
                                const a = document.createElement("a");
                                a.href = url;
                                a.download = "document.jpg";
                                a.click();
                                setTimeout(
                                  () => URL.revokeObjectURL(url),
                                  1000,
                                );
                              })
                            }
                          >
                            دریافت مدرک {num(i + 1)}
                          </button>
                        ))}
                        <form
                          className="grid gap-3"
                          onSubmit={(e) => {
                            e.preventDefault();
                            const f = new FormData(e.currentTarget);
                            run(async () => {
                              await api(
                                "/offerings/" + selected.id + "/documents",
                                "POST",
                                f,
                              );
                              setDocs(
                                await api(
                                  "/offerings/" + selected.id + "/documents",
                                ),
                              );
                              setNotice("مدرک در فضای خصوصی ذخیره شد.");
                            });
                          }}
                        >
                          <input
                            aria-label="تصویر مدرک خصوصی"
                            type="file"
                            name="file"
                            accept="image/jpeg,image/png"
                            required
                          />
                          <button className="secondary" disabled={busy}>
                            بارگذاری مدرک خصوصی
                          </button>
                        </form>
                        <button className="secondary" onClick={clearPrivate}>
                          بستن اطلاعات خصوصی
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </section>
          </div>
        )}
      </main>
    </div>
  );
}
