"use client";
import { useEffect, useState, type FormEvent } from "react";

type Api = (path: string, method?: string, body?: unknown) => Promise<any>;
type Page<T> = {
  results: T[];
  count: number;
  has_more: boolean;
  offset: number;
  limit: number;
};
type Person = { id: string; label: string; relations: string[] };
type Demand = {
  id: string;
  kind: string;
  transaction: string;
  districts: string[];
  area_min: string;
  area_max: string;
  budget_min_toman: string;
  budget_max_toman: string;
  deposit_max_toman: string;
  rent_max_toman: string;
  status: string;
  version: number;
  can_edit: boolean;
  can_operate: boolean;
  can_view_private: boolean;
  introducer_id: string;
  assignee_id: string;
};
type Coop = {
  id: string;
  demand_id: string;
  offering_id: string;
  status: string;
  reason_code: string;
  version: number;
  can_decide: boolean;
  can_schedule: boolean;
  can_close: boolean;
  can_reopen: boolean;
};
type Visit = {
  id: string;
  cooperation_id: string;
  scheduled_at: string;
  status: string;
  outcome_code: string;
  version: number;
  can_change: boolean;
};
type FollowUp = {
  id: string;
  cooperation_id: string;
  kind: string;
  due_at: string | null;
  completed_at: string | null;
  overdue: boolean;
  version: number;
};
type Notification = {
  id: string;
  label: string;
  record_id: string;
  record_type: string;
  read_at: string | null;
  created_at: string;
};
type Match = {
  offering: {
    id: string;
    district: string;
    area: string;
    price_toman: string;
    rent_toman: string;
    transaction: string;
  };
  eligible: boolean;
  score: number;
  reasons: {
    criterion: string;
    label: string;
    matched: boolean;
    required: boolean;
  }[];
};
const kinds: Record<string, string> = {
  apartment: "آپارتمان",
  villa: "ویلا",
  land: "زمین",
  commercial: "تجاری",
  office: "اداری",
  other: "سایر",
};
const statuses: Record<string, string> = {
  open: "باز",
  closed: "بسته",
  requested: "در انتظار پاسخ",
  accepted: "پذیرفته",
  rejected: "ردشده",
  scheduled: "برنامه‌ریزی‌شده",
  completed: "انجام‌شده",
  cancelled: "لغوشده",
};
const reasons: Record<string, string> = {
  not_available: "عدم موجودی",
  needs_update: "نیاز به بررسی مجدد",
  schedule_conflict: "تداخل زمان",
  customer_cancelled: "انصراف مشتری",
  completed: "پایان پیگیری",
  other: "سایر",
};
const outcomes: Record<string, string> = {
  interested: "مشتری علاقه‌مند بود",
  not_suitable: "مناسب مشتری نبود",
  no_show: "بازدید انجام نشد؛ عدم حضور",
};
const code = (id: string) => id.slice(0, 8);
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
function Field({
  name,
  label,
  value,
  required = true,
  type = "text",
}: {
  name: string;
  label: string;
  value?: string;
  required?: boolean;
  type?: string;
}) {
  return (
    <label>
      {label}
      <input name={name} defaultValue={value} required={required} type={type} />
    </label>
  );
}
function Options({ values }: { values: Record<string, string> }) {
  return (
    <>
      {Object.entries(values).map(([k, v]) => (
        <option key={k} value={k}>
          {v}
        </option>
      ))}
    </>
  );
}
export function AssignmentForm({
  api,
  path,
  version,
  onUpdated,
}: {
  api: Api;
  path: string;
  version: number;
  onUpdated: () => Promise<void>;
}) {
  const [advisors, setAdvisors] = useState<
      { id: string; name: string; active: boolean }[]
    >([]),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [history, setHistory] = useState<any[] | null>(null);
  useEffect(() => {
    api("/advisors")
      .then(setAdvisors)
      .catch((e) => setError(e.message));
  }, [api]);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api(path + "/assign", "POST", {
        version,
        ...Object.fromEntries(new FormData(e.currentTarget)),
      });
      setHistory(null);
      await onUpdated();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="border-t border-slate-200 pt-4 grid gap-3">
      <h4 className="font-bold">ارجاع مسئول اجرایی</h4>
      <p className="muted text-xs">
        معرف تاریخی و مجوز تماس با این کار تغییر نمی‌کند.
      </p>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <form onSubmit={submit} className="grid gap-3">
        <label>
          مشاور فعال
          <select name="assignee_id" required defaultValue="">
            <option value="" disabled>
              انتخاب کنید
            </option>
            {advisors
              .filter((a) => a.active)
              .map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
          </select>
        </label>
        <Field name="reason" label="دلیل ارجاع (فقط مدیر)" />
        <button className="secondary" disabled={busy}>
          ثبت ارجاع
        </button>
      </form>
      <button
        className="secondary"
        onClick={async () => {
          try {
            setHistory(await api(path + "/assignments"));
          } catch (e) {
            setError((e as Error).message);
          }
        }}
      >
        مشاهده تاریخچه ارجاع
      </button>
      {history?.map((h) => (
        <div className="text-xs border-t pt-2" key={h.id}>
          <p>{date(h.created_at)}</p>
          <p>
            از {code(h.previous_id)} به {code(h.assignee_id)}
          </p>
          <p>{h.reason}</p>
        </div>
      ))}
    </section>
  );
}
function DemandForm({
  initial,
  people,
  onSave,
  busy,
}: {
  initial?: Demand;
  people: Person[];
  onSave: (d: Record<string, unknown>) => Promise<void>;
  busy: boolean;
}) {
  const [transaction, setTransaction] = useState(
      initial?.transaction || "sale",
    ),
    [person, setPerson] = useState("");
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const d: Record<string, unknown> = Object.fromEntries(
      new FormData(e.currentTarget),
    );
    d.districts = String(d.districts || "")
      .split(/[,،\n]/)
      .map((s) => s.trim())
      .filter(Boolean);
    if (initial) {
      d.version = initial.version;
    } else if (person) {
      d.person_id = person;
      delete d.name;
      delete d.phone;
    }
    await onSave(d);
  }
  return (
    <form onSubmit={submit} className="card grid gap-4">
      <h3 className="font-bold">
        {initial ? "اصلاح تقاضا" : "ثبت تقاضای مشتری"}
      </h3>
      {!initial && (
        <>
          <label>
            متقاضی
            <select value={person} onChange={(e) => setPerson(e.target.value)}>
              <option value="">شخص جدید</option>
              {people.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label}
                </option>
              ))}
            </select>
          </label>
          {!person && (
            <div className="grid sm:grid-cols-2 gap-3">
              <Field name="name" label="نام متقاضی (خصوصی)" />
              <Field name="phone" label="همراه متقاضی (خصوصی)" />
            </div>
          )}
          <p className="muted text-xs">
            شخص موجود فقط از فهرست مجاز شما انتخاب می‌شود. هشدار تکرار، مشخصات
            دیگران را نمایش نمی‌دهد.
          </p>
        </>
      )}
      <div className="grid sm:grid-cols-2 gap-3">
        <label>
          نوع ملک
          <select name="kind" defaultValue={initial?.kind || "apartment"}>
            <Options values={kinds} />
          </select>
        </label>
        <label>
          نوع تقاضا
          <select
            name="transaction"
            value={transaction}
            onChange={(e) => setTransaction(e.target.value)}
          >
            <option value="sale">خرید</option>
            <option value="rent">اجاره</option>
          </select>
        </label>
        <Field name="area_min" label="حداقل متراژ" value={initial?.area_min} />
        <Field name="area_max" label="حداکثر متراژ" value={initial?.area_max} />
        <Field
          name="districts"
          label="محله‌های ترجیحی، جدا با ویرگول"
          required={false}
          value={initial?.districts.join("، ")}
        />
        {transaction === "sale" ? (
          <>
            <Field
              name="budget_min_toman"
              label="حداقل بودجه خرید، تومان"
              value={initial?.budget_min_toman || "0"}
            />
            <Field
              name="budget_max_toman"
              label="حداکثر بودجه خرید، تومان"
              value={initial?.budget_max_toman || "0"}
            />
          </>
        ) : (
          <>
            <Field
              name="deposit_max_toman"
              label="حداکثر ودیعه، تومان"
              value={initial?.deposit_max_toman || "0"}
            />
            <Field
              name="rent_max_toman"
              label="حداکثر اجاره ماهانه، تومان"
              value={initial?.rent_max_toman || "0"}
            />
          </>
        )}
        {initial && (
          <label>
            وضعیت
            <select name="status" defaultValue={initial.status}>
              <option value="open">باز</option>
              <option value="closed">بسته</option>
            </select>
          </label>
        )}
      </div>
      <button className="primary" disabled={busy}>
        ذخیره تقاضا
      </button>
    </form>
  );
}
export default function CRMWorkspace({
  api,
  isManager,
  onExpired,
  onOffering,
}: {
  api: Api;
  isManager: boolean;
  onExpired: () => void;
  onOffering: (id: string) => Promise<void>;
}) {
  const [tab, setTab] = useState("demands"),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [offset, setOffset] = useState(0),
    [count, setCount] = useState(0),
    [more, setMore] = useState(false);
  const [people, setPeople] = useState<Person[]>([]),
    [demands, setDemands] = useState<Demand[]>([]),
    [coops, setCoops] = useState<Coop[]>([]),
    [visits, setVisits] = useState<Visit[]>([]),
    [followups, setFollowups] = useState<FollowUp[]>([]),
    [notifications, setNotifications] = useState<Notification[]>([]);
  const [focusVisit, setFocusVisit] = useState<Visit | null>(null),
    [focusFollowUp, setFocusFollowUp] = useState<FollowUp | null>(null);
  const [selected, setSelected] = useState<Demand | null>(null),
    [coop, setCoop] = useState<Coop | null>(null),
    [privateData, setPrivateData] = useState<{
      name: string;
      phone: string;
    } | null>(null),
    [matchPage, setMatchPage] = useState<Page<Match> | null>(null),
    [reason, setReason] = useState(""),
    [dueOnly, setDueOnly] = useState(false),
    [note, setNote] = useState<{ id: string; body: string } | null>(null);
  async function load(current = tab, start = offset) {
    const response: Page<any> = await api(
      "/" +
        current +
        "?offset=" +
        start +
        (current === "followups" && dueOnly ? "&due=1" : ""),
    );
    setCount(response.count);
    setMore(response.has_more);
    (
      ({
        people: setPeople,
        demands: setDemands,
        cooperations: setCoops,
        visits: setVisits,
        followups: setFollowups,
        notifications: setNotifications,
      }) as Record<string, (v: any[]) => void>
    )[current](response.results);
  }
  async function run(fn: () => Promise<void>) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await fn();
    } catch (e) {
      setError((e as Error).message);
      if ((e as { status?: number }).status === 403) {
        try {
          await api("/me");
        } catch {
          onExpired();
        }
      }
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => {
    run(async () => {
      await load(tab, offset);
      if (tab === "demands")
        setPeople((await api("/people?limit=100")).results);
    });
  }, [tab, offset, dueOnly]);
  function switchTab(t: string) {
    setFocusVisit(null);
    setFocusFollowUp(null);
    setSelected(null);
    setCoop(null);
    setPrivateData(null);
    setMatchPage(null);
    setNote(null);
    setReason("");
    setOffset(0);
    setTab(t);
  }
  async function refreshDemand() {
    if (selected) setSelected(await api("/demands/" + selected.id));
    setPrivateData(null);
    setMatchPage(null);
    await load("demands");
  }
  async function decide(decision: string) {
    if (!coop) return;
    await run(async () => {
      setCoop(
        await api("/cooperations/" + coop.id, "PATCH", {
          version: coop.version,
          decision,
          ...(decision === "accepted" ? {} : { reason_code: reason }),
        }),
      );
      setReason("");
      await load("cooperations");
    });
  }
  async function openNotification(n: Notification) {
    await run(async () => {
      if (n.record_type === "demand") {
        switchTab("demands");
        setSelected(await api("/demands/" + n.record_id));
      } else if (n.record_type === "cooperation") {
        switchTab("cooperations");
        setCoop(await api("/cooperations/" + n.record_id));
      } else if (n.record_type === "offering") {
        await onOffering(n.record_id);
      } else if (n.record_type === "visit") {
        switchTab("visits");
        const v: Visit = await api("/visits/" + n.record_id);
        setFocusVisit(v);
        setCount(1);
        setMore(false);
      } else {
        switchTab("followups");
        const f: FollowUp = await api("/followups/" + n.record_id);
        setFocusFollowUp(f);
        setCount(1);
        setMore(false);
      }
    });
  }
  return (
    <section className="grid gap-5">
      <nav aria-label="مشتری و همکاری" className="flex flex-wrap gap-2">
        {[
          ["demands", "تقاضاها و تطبیق"],
          ["people", "اشخاص مجاز"],
          ["cooperations", "همکاری‌ها"],
          ["visits", "بازدیدها"],
          ["followups", "پیگیری‌ها"],
          ["notifications", "اعلان‌ها"],
        ].map(([id, label]) => (
          <button
            key={id}
            className={tab === id ? "primary" : "secondary"}
            disabled={busy}
            onClick={() => switchTab(id)}
          >
            {label}
          </button>
        ))}
      </nav>
      <p className="muted text-sm">
        تماس مالک از مسیر معرف هماهنگ می‌شود. ارجاع و همکاری، شماره طرف دیگر را
        در اختیار شما نمی‌گذارد.
      </p>
      {error && (
        <p className="error" role="alert">
          {error}
          <button
            className="secondary mr-3"
            disabled={busy}
            onClick={() =>
              run(async () => {
                if (selected) await refreshDemand();
                else if (coop) {
                  setCoop(await api("/cooperations/" + coop.id));
                  await load();
                } else await load();
              })
            }
          >
            بارگذاری نسخه جدید
          </button>
        </p>
      )}
      {notice && (
        <p className="success" role="status">
          {notice}
        </p>
      )}
      {tab === "people" && (
        <div className="grid lg:grid-cols-2 gap-5">
          <section className="card grid gap-3">
            <h3 className="font-bold">اشخاص قابل دسترس شما</h3>
            {people.length === 0 && <p className="muted">شخصی ثبت نشده است.</p>}
            {people.map((p) => (
              <div
                key={p.id}
                className="border-t border-slate-100 pt-3 flex justify-between gap-3"
              >
                <div>
                  {p.label}
                  <p className="muted text-xs">
                    {p.relations
                      .map((x) => (x === "owner" ? "مالک" : "متقاضی"))
                      .join("، ")}
                  </p>
                </div>
                <button
                  className="secondary"
                  disabled={busy}
                  onClick={() =>
                    run(async () =>
                      setPrivateData(await api("/people/" + p.id + "/private")),
                    )
                  }
                >
                  نمایش تماس با ثبت رویداد
                </button>
              </div>
            ))}
            {privateData && (
              <div className="success">
                <p>{privateData.name}</p>
                <p dir="ltr">{privateData.phone}</p>
                <button
                  className="secondary mt-2"
                  onClick={() => setPrivateData(null)}
                >
                  بستن
                </button>
              </div>
            )}
          </section>
          <form
            className="card grid gap-4 self-start"
            onSubmit={(e) => {
              e.preventDefault();
              const form = e.currentTarget;
              const d = Object.fromEntries(new FormData(form));
              run(async () => {
                await api("/people", "POST", d);
                form.reset();
                await load();
                setNotice("شخص با رابطه متقاضی ثبت شد.");
              });
            }}
          >
            <h3 className="font-bold">ثبت شخص متقاضی</h3>
            <Field name="name" label="نام خصوصی" />
            <Field name="phone" label="شماره همراه خصوصی" />
            <button className="primary" disabled={busy}>
              ذخیره شخص
            </button>
          </form>
        </div>
      )}
      {tab === "demands" && (
        <div className="grid xl:grid-cols-2 gap-5">
          <div className="grid gap-3 self-start">
            <div className="card">
              <h3 className="font-bold mb-3">بانک تقاضاهای دفتر</h3>
              {demands.length === 0 && (
                <p className="muted">تقاضایی ثبت نشده است.</p>
              )}
              <div className="grid gap-3">
                {demands.map((d) => (
                  <button
                    key={d.id}
                    className="secondary text-right"
                    disabled={busy}
                    onClick={() => {
                      setSelected(d);
                      setPrivateData(null);
                      setMatchPage(null);
                    }}
                  >
                    <div className="flex justify-between gap-2">
                      <strong>
                        {kinds[d.kind]} ·{" "}
                        {d.transaction === "sale" ? "خرید" : "اجاره"}
                      </strong>
                      <span className="badge">{statuses[d.status]}</span>
                    </div>
                    <p className="muted text-sm mt-2">
                      {num(d.area_min)} تا {num(d.area_max)} متر ·{" "}
                      {d.districts.join("، ") || "تمام محله‌ها"}
                    </p>
                    <p className="text-xs muted mt-2">کد {code(d.id)}</p>
                  </button>
                ))}
              </div>
            </div>
            <DemandForm
              people={people}
              busy={busy}
              onSave={async (d) => {
                await run(async () => {
                  const created = await api("/demands", "POST", d);
                  setSelected(created);
                  setPrivateData(null);
                  await load();
                  setNotice("تقاضا ثبت شد.");
                });
              }}
            />
          </div>
          <div className="grid gap-4 self-start">
            {!selected ? (
              <p className="card muted">
                یک تقاضا را برای مشاهده، تطبیق و همکاری انتخاب کنید.
              </p>
            ) : (
              <>
                <section className="card grid gap-4">
                  <h3 className="font-bold">
                    تقاضا {code(selected.id)} · نسخه {num(selected.version)}
                  </h3>
                  <p>
                    {kinds[selected.kind]} ·{" "}
                    {selected.transaction === "sale" ? "خرید" : "اجاره"} ·{" "}
                    {statuses[selected.status]}
                  </p>
                  <p className="muted text-sm">
                    {selected.transaction === "sale"
                      ? `بودجه ${num(selected.budget_min_toman)} تا ${num(selected.budget_max_toman)} تومان`
                      : `حداکثر ودیعه ${num(selected.deposit_max_toman)} و اجاره ${num(selected.rent_max_toman)} تومان`}
                  </p>
                  {selected.can_view_private ? (
                    <>
                      <button
                        className="secondary"
                        disabled={busy}
                        onClick={() =>
                          run(async () =>
                            setPrivateData(
                              await api("/demands/" + selected.id + "/private"),
                            ),
                          )
                        }
                      >
                        مشاهده تماس متقاضی با ثبت رویداد
                      </button>
                      {privateData && (
                        <div className="success">
                          <p>{privateData.name}</p>
                          <p dir="ltr">{privateData.phone}</p>
                          <button
                            className="secondary mt-2"
                            onClick={() => setPrivateData(null)}
                          >
                            بستن تماس
                          </button>
                        </div>
                      )}
                    </>
                  ) : (
                    <p className="muted text-xs">
                      تماس متقاضی فقط برای مدیر و معرف تقاضا مجاز است.
                    </p>
                  )}
                  <button
                    className="primary"
                    disabled={busy || selected.status !== "open"}
                    onClick={() =>
                      run(async () =>
                        setMatchPage(
                          await api("/demands/" + selected.id + "/matches"),
                        ),
                      )
                    }
                  >
                    بررسی تطبیق با عرضه‌های تأییدشده
                  </button>
                  {isManager && (
                    <AssignmentForm
                      key={selected.id + selected.version}
                      api={api}
                      path={"/demands/" + selected.id}
                      version={selected.version}
                      onUpdated={refreshDemand}
                    />
                  )}
                </section>
                {selected.can_edit && (
                  <DemandForm
                    key={selected.id + "-" + selected.version}
                    initial={selected}
                    people={people}
                    busy={busy}
                    onSave={async (d) =>
                      run(async () => {
                        setSelected(
                          await api("/demands/" + selected.id, "PATCH", d),
                        );
                        setMatchPage(null);
                        setPrivateData(null);
                        await load();
                        setNotice("تقاضا اصلاح شد.");
                      })
                    }
                  />
                )}
                {matchPage && (
                  <section className="card grid gap-4">
                    <h4 className="font-bold">تطبیق قواعدی و دلایل</h4>
                    <p className="text-xs muted">
                      نوع معامله، نوع ملک، متراژ و بودجه الزامی‌اند؛ محله معیار
                      ترجیحی است. هیچ تبدیل خودکار ودیعه و اجاره یا تلورانس
                      پنهانی اعمال نمی‌شود.
                    </p>
                    {matchPage.results.length === 0 && (
                      <p>عرضه تأییدشده‌ای وجود ندارد.</p>
                    )}
                    {matchPage.results.map((match) => (
                      <article
                        className="border-t border-slate-200 pt-4 grid gap-3"
                        key={match.offering.id}
                      >
                        <div className="flex justify-between">
                          <strong>
                            {match.offering.district} ·{" "}
                            {num(match.offering.area)} متر
                          </strong>
                          <span className="badge">
                            {match.eligible
                              ? `${num(match.score)}٪`
                              : "ناسازگار"}
                          </span>
                        </div>
                        <ul className="text-sm space-y-1">
                          {match.reasons.map((r) => (
                            <li key={r.criterion}>
                              {r.matched ? "مطابق" : "نامطابق"} · {r.label}
                              {r.required ? " (الزامی)" : ""}
                            </li>
                          ))}
                        </ul>
                        <button
                          className="secondary"
                          onClick={() =>
                            run(async () => onOffering(match.offering.id))
                          }
                        >
                          مشاهده عرضه
                        </button>
                        {selected.can_operate && (
                          <button
                            className="primary"
                            disabled={busy}
                            onClick={() =>
                              run(async () => {
                                const created = await api(
                                  "/cooperations",
                                  "POST",
                                  {
                                    demand_id: selected.id,
                                    offering_id: match.offering.id,
                                  },
                                );
                                switchTab("cooperations");
                                setCoop(created);
                                setNotice(
                                  "درخواست همکاری ثبت یا درخواست قبلی بازیابی شد.",
                                );
                              })
                            }
                          >
                            درخواست هماهنگی از معرف
                            {!match.eligible ? " با آگاهی از ناسازگاری" : ""}
                          </button>
                        )}
                      </article>
                    ))}
                    <div className="flex gap-2">
                      <button
                        className="secondary"
                        disabled={busy || matchPage.offset === 0}
                        onClick={() =>
                          run(async () =>
                            setMatchPage(
                              await api(
                                `/demands/${selected.id}/matches?offset=${Math.max(0, matchPage.offset - 30)}`,
                              ),
                            ),
                          )
                        }
                      >
                        قبلی
                      </button>
                      <button
                        className="secondary"
                        disabled={busy || !matchPage.has_more}
                        onClick={() =>
                          run(async () =>
                            setMatchPage(
                              await api(
                                `/demands/${selected.id}/matches?offset=${matchPage.offset + 30}`,
                              ),
                            ),
                          )
                        }
                      >
                        بعدی
                      </button>
                    </div>
                  </section>
                )}
              </>
            )}
          </div>
        </div>
      )}
      {tab === "cooperations" && (
        <div className="grid lg:grid-cols-2 gap-5">
          <section className="card grid gap-3 self-start">
            <h3 className="font-bold">همکاری‌های مجاز شما</h3>
            {coops.length === 0 && (
              <p className="muted">درخواستی وجود ندارد.</p>
            )}
            {coops.map((c) => (
              <button
                className="secondary text-right"
                key={c.id}
                disabled={busy}
                onClick={() => {
                  setCoop(c);
                  setReason("");
                }}
              >
                <div className="flex justify-between">
                  <strong>همکاری {code(c.id)}</strong>
                  <span className="badge">{statuses[c.status]}</span>
                </div>
                <p className="text-xs muted mt-2">
                  تقاضا {code(c.demand_id)} · عرضه {code(c.offering_id)}
                </p>
              </button>
            ))}
          </section>
          <section className="card grid gap-4 self-start">
            {!coop ? (
              <p className="muted">یک همکاری را انتخاب کنید.</p>
            ) : (
              <>
                <h3 className="font-bold">
                  همکاری {code(coop.id)} · نسخه {num(coop.version)}
                </h3>
                <p>
                  {statuses[coop.status]}
                  {coop.reason_code
                    ? " · " + (reasons[coop.reason_code] || coop.reason_code)
                    : ""}
                </p>
                <button
                  className="secondary"
                  onClick={() => run(async () => onOffering(coop.offering_id))}
                >
                  مشاهده عرضه
                </button>
                {(coop.can_decide || coop.can_close || coop.can_reopen) && (
                  <label>
                    علت رد، بستن یا ارسال دوباره
                    <select
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                    >
                      <option value="">انتخاب علت</option>
                      <Options values={reasons} />
                    </select>
                  </label>
                )}
                {coop.can_decide && (
                  <div className="flex flex-wrap gap-2">
                    <button
                      className="primary"
                      disabled={busy}
                      onClick={() => decide("accepted")}
                    >
                      پذیرش همکاری
                    </button>
                    <button
                      className="secondary"
                      disabled={busy || !reason}
                      onClick={() => decide("rejected")}
                    >
                      رد با علت
                    </button>
                  </div>
                )}
                {coop.can_close && (
                  <button
                    className="secondary"
                    disabled={busy || !reason}
                    onClick={() => decide("closed")}
                  >
                    بستن همکاری با علت
                  </button>
                )}
                {coop.can_reopen && (
                  <button
                    className="secondary"
                    disabled={busy || !reason}
                    onClick={() => decide("reopen")}
                  >
                    ارسال دوباره با علت
                  </button>
                )}
                <WorkflowHistory
                  key={coop.id + coop.version}
                  api={api}
                  path={"/cooperations/" + coop.id + "/history"}
                />
                {coop.can_schedule && (
                  <form
                    className="grid gap-3 border-t pt-4"
                    onSubmit={(e) => {
                      e.preventDefault();
                      const d = Object.fromEntries(
                        new FormData(e.currentTarget),
                      );
                      run(async () => {
                        await api("/visits", "POST", {
                          ...d,
                          cooperation_id: coop.id,
                          cooperation_version: coop.version,
                        });
                        setCoop(await api("/cooperations/" + coop.id));
                        setNotice("بازدید ثبت شد و به طرفین اعلان داخلی رسید.");
                      });
                    }}
                  >
                    <h4 className="font-bold">برنامه‌ریزی بازدید</h4>
                    <Field
                      name="scheduled_at"
                      label="تاریخ میلادی و ساعت ورودی، به وقت تهران"
                      type="datetime-local"
                    />
                    <p className="text-xs muted">
                      زمان پس از ذخیره به تقویم شمسی نمایش داده می‌شود. نشانی از
                      مسیر مدیر و معرف هماهنگ شود.
                    </p>
                    <button className="primary" disabled={busy}>
                      ثبت زمان بازدید
                    </button>
                  </form>
                )}
                <form
                  className="grid gap-3 border-t pt-4"
                  onSubmit={(e) => {
                    e.preventDefault();
                    const form = e.currentTarget;
                    const d = Object.fromEntries(new FormData(form));
                    if (!d.due_at) delete d.due_at;
                    run(async () => {
                      await api("/followups", "POST", {
                        cooperation_id: coop.id,
                        ...d,
                      });
                      form.reset();
                      setNotice("پیگیری خصوصی شما ثبت شد.");
                    });
                  }}
                >
                  <h4 className="font-bold">ثبت پیگیری و وظیفه</h4>
                  <label>
                    نوع
                    <select name="kind">
                      <option value="note">یادداشت</option>
                      <option value="call">تماس انجام‌شده</option>
                      <option value="task">وظیفه دارای سررسید</option>
                    </select>
                  </label>
                  <label>
                    متن خصوصی شما
                    <textarea name="body" maxLength={2000} required />
                  </label>
                  <Field
                    name="due_at"
                    label="سررسید اختیاری، تاریخ میلادی و ساعت تهران"
                    type="datetime-local"
                    required={false}
                  />
                  <p className="muted text-xs">
                    متن فقط برای نویسنده و مدیر قابل دریافت است و در اعلان‌ها
                    نمایش داده نمی‌شود.
                  </p>
                  <button className="secondary" disabled={busy}>
                    ذخیره پیگیری
                  </button>
                </form>
              </>
            )}
          </section>
        </div>
      )}
      {tab === "visits" && (
        <section className="grid gap-3">
          <h3 className="font-bold">
            بازدیدها · نمایش به وقت تهران و تقویم شمسی
          </h3>
          {visits.length === 0 && (
            <p className="card muted">بازدیدی وجود ندارد.</p>
          )}
          {(focusVisit ? [focusVisit] : visits).map((v) => (
            <article key={v.id + "-" + v.version} className="card grid gap-3">
              <div className="flex flex-wrap justify-between gap-3">
                <strong>{date(v.scheduled_at)}</strong>
                <span className="badge">{statuses[v.status]}</span>
              </div>
              <p className="text-xs muted">
                بازدید {code(v.id)} · همکاری {code(v.cooperation_id)} ·{" "}
                {outcomes[v.outcome_code] || reasons[v.outcome_code] || ""}
              </p>
              <WorkflowHistory
                api={api}
                path={"/visits/" + v.id + "/history"}
              />
              {v.can_change && (
                <VisitActions
                  visit={v}
                  busy={busy}
                  onSave={async (d) =>
                    run(async () => {
                      const updated = await api("/visits/" + v.id, "PATCH", {
                        version: v.version,
                        ...d,
                      });
                      await load();
                      if (focusVisit) setFocusVisit(updated);
                      setNotice("تغییر بازدید ثبت شد.");
                    })
                  }
                />
              )}
            </article>
          ))}
        </section>
      )}
      {tab === "followups" && (
        <section className="grid gap-3">
          <div className="flex justify-between gap-3">
            <h3 className="font-bold">پیگیری‌های خصوصی مجاز</h3>
            <label className="flex items-center gap-2">
              <input
                className="w-auto"
                type="checkbox"
                checked={dueOnly}
                onChange={(e) => {
                  setDueOnly(e.target.checked);
                  setOffset(0);
                }}
              />
              فقط سررسیدگذشته
            </label>
          </div>
          {followups.length === 0 && (
            <p className="card muted">پیگیری‌ای یافت نشد.</p>
          )}
          {(focusFollowUp ? [focusFollowUp] : followups).map((f) => (
            <article className="card grid gap-3" key={f.id}>
              <div className="flex justify-between">
                <strong>
                  {f.kind === "call"
                    ? "تماس"
                    : f.kind === "task"
                      ? "وظیفه"
                      : "یادداشت"}{" "}
                  · {code(f.id)}
                </strong>
                <span className="badge">
                  {f.completed_at
                    ? "انجام‌شده"
                    : f.overdue
                      ? "سررسیدگذشته"
                      : "باز"}
                </span>
              </div>
              <p className="muted text-sm">
                {f.due_at ? "سررسید " + date(f.due_at) : "بدون سررسید"}
              </p>
              <div className="flex gap-2">
                <button
                  className="secondary"
                  disabled={busy}
                  onClick={() =>
                    run(async () =>
                      setNote({
                        id: f.id,
                        ...(await api("/followups/" + f.id + "/private")),
                      }),
                    )
                  }
                >
                  دریافت متن با ثبت رویداد
                </button>
                {!f.completed_at && (
                  <button
                    className="primary"
                    disabled={busy}
                    onClick={() =>
                      run(async () => {
                        const updated = await api(
                          "/followups/" + f.id,
                          "PATCH",
                          {
                            version: f.version,
                          },
                        );
                        if (focusFollowUp) setFocusFollowUp(updated);
                        await load();
                      })
                    }
                  >
                    انجام شد
                  </button>
                )}
              </div>
              {note?.id === f.id && (
                <div className="success whitespace-pre-wrap">
                  <p>{note.body}</p>
                  <button
                    className="secondary mt-2"
                    onClick={() => setNote(null)}
                  >
                    بستن متن
                  </button>
                </div>
              )}
            </article>
          ))}
        </section>
      )}
      {tab === "notifications" && (
        <section className="card grid gap-3">
          <h3 className="font-bold">صندوق اعلان‌های شما</h3>
          <p className="text-xs muted">
            اعلان‌ها فقط عنوان کنترل‌شده و شناسه پرونده دارند؛ اطلاعات تماس و
            متن خصوصی در آن‌ها قرار نمی‌گیرد.
          </p>
          {notifications.length === 0 && (
            <p className="muted">اعلانی وجود ندارد.</p>
          )}
          {notifications.map((n) => (
            <article
              className="border-t border-slate-100 pt-3 grid gap-2"
              key={n.id}
            >
              <div className="flex justify-between">
                <strong>{n.label}</strong>
                <span className="badge">
                  {n.read_at ? "خوانده‌شده" : "جدید"}
                </span>
              </div>
              <p className="text-xs muted">{date(n.created_at)}</p>
              <div className="flex gap-2">
                <button
                  className="secondary"
                  disabled={busy}
                  onClick={() => openNotification(n)}
                >
                  باز کردن پرونده
                </button>
                {!n.read_at && (
                  <button
                    className="secondary"
                    disabled={busy}
                    onClick={() =>
                      run(async () => {
                        await api("/notifications/" + n.id, "PATCH", {});
                        await load();
                      })
                    }
                  >
                    خواندم
                  </button>
                )}
              </div>
            </article>
          ))}
        </section>
      )}
      {(focusVisit || focusFollowUp) && (
        <button
          className="secondary"
          onClick={() => {
            setFocusVisit(null);
            setFocusFollowUp(null);
          }}
        >
          نمایش همه موارد
        </button>
      )}
      <div className="flex flex-wrap items-center gap-3">
        <button
          className="secondary"
          disabled={busy || offset === 0}
          onClick={() => setOffset(Math.max(0, offset - 30))}
        >
          صفحه قبل
        </button>
        <span className="muted text-sm">{num(count)} مورد</span>
        <button
          className="secondary"
          disabled={busy || !more}
          onClick={() => setOffset(offset + 30)}
        >
          صفحه بعد
        </button>
        <button
          className="secondary"
          disabled={busy}
          onClick={() => run(async () => load())}
        >
          تازه‌سازی
        </button>
      </div>
    </section>
  );
}
function VisitActions({
  visit,
  busy,
  onSave,
}: {
  visit: Visit;
  busy: boolean;
  onSave: (d: Record<string, unknown>) => Promise<void>;
}) {
  const [action, setAction] = useState("complete");
  return (
    <form
      className="grid sm:grid-cols-2 gap-3"
      onSubmit={(e) => {
        e.preventDefault();
        onSave(Object.fromEntries(new FormData(e.currentTarget)));
      }}
    >
      <label>
        عملیات
        <select
          name="action"
          value={action}
          onChange={(e) => setAction(e.target.value)}
        >
          <option value="complete">ثبت نتیجه</option>
          <option value="reschedule">تغییر زمان</option>
          <option value="cancel">لغو بازدید</option>
        </select>
      </label>
      <label>
        نتیجه یا علت
        <select name="outcome_code" required key={action} defaultValue="">
          <option value="" disabled>
            انتخاب کنید
          </option>
          <Options values={action === "complete" ? outcomes : reasons} />
        </select>
      </label>
      {action === "reschedule" && (
        <Field
          name="scheduled_at"
          label="تاریخ میلادی و ساعت تازه، به وقت تهران"
          type="datetime-local"
        />
      )}
      <button className="primary self-end" disabled={busy}>
        ثبت تغییر بازدید
      </button>
    </form>
  );
}

function WorkflowHistory({ api, path }: { api: Api; path: string }) {
  const [rows, setRows] = useState<any[] | null>(null),
    [error, setError] = useState("");
  return (
    <section className="grid gap-2">
      <button
        className="secondary"
        onClick={async () => {
          try {
            setRows(await api(path));
            setError("");
          } catch (e) {
            setError((e as Error).message);
          }
        }}
      >
        تاریخچه تغییرات
      </button>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {rows?.map((row) => (
        <div key={row.id} className="border-t border-slate-100 pt-2 text-xs">
          <p>
            نسخه {num(row.version)} · {statuses[row.status]} · ثبت{" "}
            {date(row.created_at)}
          </p>
          {row.scheduled_at && (
            <p>زمان بازدید در این نسخه: {date(row.scheduled_at)}</p>
          )}
          {(row.reason_code || row.outcome_code) && (
            <p>
              {reasons[row.reason_code] ||
                reasons[row.outcome_code] ||
                outcomes[row.outcome_code] ||
                ""}
            </p>
          )}
        </div>
      ))}
    </section>
  );
}
