"use client";
import { useEffect, useState, useRef, type FormEvent } from "react";
type API = (path: string, method?: string, body?: unknown) => Promise<any>;
const money = (s: string) =>
  new Intl.NumberFormat("fa-IR").format(BigInt(s || "0"));
const fields = (e: FormEvent<HTMLFormElement>) => {
  e.preventDefault();
  return Object.fromEntries(new FormData(e.currentTarget));
};
function Input({
  name,
  label,
  type = "text",
  value,
}: {
  name: string;
  label: string;
  type?: string;
  value?: string;
}) {
  return (
    <label>
      {label}
      <input name={name} type={type} defaultValue={value} required />
    </label>
  );
}
function percent(s: string) {
  const x = s
    .replace(/[۰-۹]/g, (c) => String("۰۱۲۳۴۵۶۷۸۹".indexOf(c)))
    .replace(/[٠-٩]/g, (c) => String("٠١٢٣٤٥٦٧٨٩".indexOf(c)));
  if (!/^\d+(\.\d{1,2})?$/.test(x))
    throw Error("درصد باید حداکثر دو رقم اعشار داشته باشد.");
  const [a, b = ""] = x.split(".");
  return String(Number(a) * 100 + Number(b.padEnd(2, "0")));
}
export default function BusinessWorkspace({
  api,
  isManager,
}: {
  api: API;
  isManager: boolean;
}) {
  const [tab, setTab] = useState("publication"),
    [offerings, setOfferings] = useState<any[]>([]),
    [chosen, setChosen] = useState<any>(null),
    [publication, setPublication] = useState<any>(null),
    [revisions, setRevisions] = useState<any[]>([]),
    [deals, setDeals] = useState<any[]>([]),
    [deal, setDeal] = useState<any>(null),
    [members, setMembers] = useState<any[]>([]),
    [inbox, setInbox] = useState<any[]>([]),
    [settings, setSettings] = useState<any>(null),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false),
    [invitations, setInvitations] = useState<any[]>([]),
    [inviteLink, setInviteLink] = useState(""),
    [report, setReport] = useState<any>(null),
    [mode, setMode] = useState("percent"),
    [shares, setShares] = useState<
      { beneficiary: string; value: string; roles: string[] }[]
    >([{ beneficiary: "office", value: "0", roles: ["office"] }]);
  const operations = useRef<Record<string, string>>({});
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
  async function load() {
    const o = await api("/offerings?paginated=1&limit=100");
    setOfferings(o.results);
    setDeals(await api("/finance/deals"));
    setInbox(await api("/customer-inbox"));
    if (isManager) {
      setMembers(await api("/finance/members"));
      setSettings(await api("/settings/office"));
      setInvitations(await api("/invitations"));
      setReport(await api("/reports/office"));
    }
  }
  useEffect(() => {
    run(load);
  }, []);
  async function select(o: any) {
    setChosen(o);
    setPublication(await api("/offerings/" + o.id + "/publication"));
    setRevisions(await api("/offerings/" + o.id + "/revisions"));
  }
  async function act(action: string, d: any) {
    const result = await api(
      "/finance/deals/" + deal.id + "/" + action,
      "POST",
      { ...(action === "vote" ? {} : { version: deal.version }), ...d },
    );
    setDeal(result);
    setDeals(await api("/finance/deals"));
    setNotice("عملیات ثبت شد.");
  }
  async function cash(action: string, d: any) {
    operations.current[action] ||= crypto.randomUUID();
    await act(action, { ...d, operation: operations.current[action] });
    delete operations.current[action];
  }
  const name = (id: string) =>
    id === "office"
      ? "دفتر"
      : members.find((x) => x.id === id)?.name || "سهم شما";
  return (
    <section className="grid gap-5">
      <nav className="flex flex-wrap gap-2">
        {[
          ["publication", "انتشار و بازنگری"],
          ["finance", "معاملات و تسویه"],
          ["inbox", "درخواست‌های ویترین"],
          ...(isManager
            ? [
                ["settings", "تنظیمات دفتر"],
                ["invites", "دعوت همکار"],
                ["reports", "گزارش دفتر"],
              ]
            : []),
        ].map(([id, title]) => (
          <button
            key={id}
            disabled={busy}
            className={id === tab ? "primary" : "secondary"}
            onClick={() => setTab(id)}
          >
            {title}
          </button>
        ))}
        <a
          className="secondary"
          href="/showcase"
          target="_blank"
          rel="noreferrer"
        >
          مشاهده ویترین
        </a>
      </nav>
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
      {tab === "invites" && isManager && (
        <section className="card grid gap-3">
          <h3>دعوت یک‌بارمصرف مشاور · اعتبار ۲۴ ساعت</h3>
          <button
            disabled={busy}
            className="primary"
            onClick={() =>
              run(async () => {
                const d = await api("/invitations", "POST", {});
                setInviteLink(location.origin + "/join#token=" + d.token);
                await load();
              })
            }
          >
            ساخت لینک دعوت
          </button>
          {inviteLink && (
            <label>
              لینک خصوصی؛ فقط به همکار موردنظر بدهید
              <input
                readOnly
                value={inviteLink}
                onFocus={(e) => e.target.select()}
              />
            </label>
          )}
          {invitations.map((x) => (
            <div key={x.id} className="flex flex-wrap gap-2">
              <span>
                {x.used
                  ? "استفاده شده"
                  : x.revoked
                    ? "لغوشده"
                    : "مهلت " + new Date(x.expires_at).toLocaleString("fa-IR")}
              </span>
              {!x.used && !x.revoked && (
                <button
                  className="secondary"
                  disabled={busy}
                  onClick={() =>
                    run(async () => {
                      await api("/invitations/" + x.id, "DELETE");
                      await load();
                    })
                  }
                >
                  لغو دعوت
                </button>
              )}
            </div>
          ))}
        </section>
      )}
      {tab === "reports" && report && (
        <section className="card grid gap-3">
          <h3>گزارش عملیاتی و مالی دفتر</h3>
          {Object.entries(report).map(([k, v]) => (
            <p key={k}>
              {
                (
                  {
                    offerings: "عرضه‌ها",
                    demands: "تقاضاها",
                    cooperations: "همکاری‌ها",
                    visits: "بازدیدها",
                    deals: "معاملات",
                    approved: "عرضه تأییدشده",
                    published: "آگهی منتشرشده",
                    receipts: "دریافت خالص (تومان)",
                    payouts: "پرداخت خالص (تومان)",
                  } as any
                )[k]
              }
              : {money(String(v))}
            </p>
          ))}
          <button
            className="secondary"
            onClick={() => {
              const data =
                "\ufeff" +
                Object.entries(report)
                  .map(([k, v]) => k + "," + v)
                  .join("\n");
              const url = URL.createObjectURL(
                new Blob([data], { type: "text/csv;charset=utf-8" }),
              );
              const a = document.createElement("a");
              a.href = url;
              a.download = "office-report.csv";
              a.click();
              URL.revokeObjectURL(url);
            }}
          >
            دریافت گزارش CSV
          </button>
        </section>
      )}
      {tab === "settings" && settings && (
        <form
          key={settings.version}
          className="card grid gap-3"
          onSubmit={(e) => {
            const d = fields(e);
            run(async () => {
              await api("/settings/office", "PUT", {
                ...d,
                version: settings.version,
              });
              await load();
              setNotice(
                "تنظیمات ثبت شد؛ برای به‌روزرسانی سربرگ صفحه را تازه کنید.",
              );
            });
          }}
        >
          <h3>تنظیمات دفتر</h3>
          <Input name="name" label="نام دفتر" value={settings.name} />
          <Input name="city" label="شهر" value={settings.city} />
          <Input
            name="response_hours"
            label="ارجاع همکاری بی‌پاسخ پس از چند ساعت تقویمی؟ صفر یعنی غیرفعال"
            value={String(settings.response_hours)}
          />
          <Input
            name="color"
            label="رنگ اصلی"
            type="color"
            value={settings.color}
          />
          <button className="primary" disabled={busy}>
            ذخیره تنظیمات
          </button>
        </form>
      )}
      {tab === "inbox" && (
        <section className="grid gap-3">
          <h3>درخواست‌های مشتریان ویترین</h3>
          <p className="muted">
            متن درخواست خصوصی است و فقط مدیر و معرف عرضه می‌بینند.
          </p>
          {inbox.length === 0 && <p>درخواستی ثبت نشده است.</p>}
          {inbox.map((x) => (
            <article className="card grid gap-3" key={x.id}>
              <p>
                عرضه {x.offering.slice(0, 8)} ·{" "}
                {x.kind === "visit" ? "بازدید" : "اطلاعات بیشتر"}
              </p>
              <p className="whitespace-pre-wrap">{x.message}</p>
              <select
                aria-label="وضعیت درخواست"
                value={x.status}
                disabled={busy}
                onChange={(e) =>
                  run(async () => {
                    await api("/customer-inbox/" + x.id, "PATCH", {
                      version: x.version,
                      status: e.target.value,
                    });
                    await load();
                  })
                }
              >
                <option value="received">دریافت‌شده</option>
                <option value="contacted">تماس گرفته شد</option>
                <option value="closed">بسته‌شده</option>
              </select>
            </article>
          ))}
        </section>
      )}
      {tab === "publication" && (
        <div className="grid lg:grid-cols-2 gap-5">
          <section className="card grid gap-3">
            <h3>انتخاب عرضه برای بازنگری یا انتشار</h3>
            {offerings
              .filter((o) => o.status === "approved")
              .map((o) => (
                <button
                  className="secondary"
                  key={o.id}
                  disabled={busy}
                  onClick={() => run(() => select(o))}
                >
                  {o.district} · {o.area} متر · {o.id.slice(0, 8)}
                </button>
              ))}
          </section>
          {chosen && publication && (
            <section className="card grid gap-4">
              <h3>عرضه {chosen.id.slice(0, 8)}</h3>
              <p>
                رضایت انتشار: {publication.consent ? "ثبت شده" : "ثبت نشده"} ·
                وضعیت: {publication.published ? "منتشرشده" : "منتشرنشده"}
              </p>
              {chosen.can_view_private && (
                <>
                  <form
                    className="grid gap-3"
                    onSubmit={(e) => {
                      const d = fields(e);
                      run(async () => {
                        await api(
                          "/offerings/" + chosen.id + "/publication",
                          "POST",
                          {
                            version: publication.version || 1,
                            action: "consent",
                            reference: d.reference,
                          },
                        );
                        await select(chosen);
                        setNotice(
                          "رضایت ثبت شد؛ انتشار نیازمند بازبینی مدیر است.",
                        );
                      });
                    }}
                  >
                    <Input
                      name="reference"
                      label="مرجع مستند رضایت عرضه‌کننده"
                    />
                    <button className="secondary" disabled={busy}>
                      ثبت رضایت
                    </button>
                  </form>
                  <div className="flex flex-wrap gap-2">
                    {[
                      ["revoke", "لغو فوری رضایت"],
                      ["stop", "توقف نمایش"],
                    ].map(([action, title]) => (
                      <button
                        key={action}
                        className="secondary"
                        disabled={busy}
                        onClick={() =>
                          run(async () => {
                            await api(
                              "/offerings/" + chosen.id + "/publication",
                              "POST",
                              { action, version: publication.version || 1 },
                            );
                            await select(chosen);
                          })
                        }
                      >
                        {title}
                      </button>
                    ))}
                  </div>
                  {isManager && publication.consent && (
                    <form
                      className="grid gap-3 border-t pt-3"
                      onSubmit={(e) => {
                        e.preventDefault();
                        const body = new FormData(e.currentTarget);
                        run(async () => {
                          await api(
                            "/offerings/" + chosen.id + "/public-images",
                            "POST",
                            body,
                          );
                          await select(chosen);
                          setNotice("تصویر بازکدگذاری و برای ویترین ذخیره شد.");
                        });
                      }}
                    >
                      <h4>
                        تصاویر عمومی بازبینی‌شده ({publication.image_count || 0}
                        )
                      </h4>
                      <label>
                        تصویر JPEG یا PNG
                        <input
                          name="file"
                          type="file"
                          accept="image/jpeg,image/png"
                          required
                        />
                      </label>
                      <label>
                        <input
                          className="w-auto"
                          type="checkbox"
                          name="content_reviewed"
                          value="true"
                          required
                        />{" "}
                        تصویر را بررسی کردم؛ شماره تماس، مدرک یا نشانی دقیق روی
                        آن نیست.
                      </label>
                      <button disabled={busy} className="secondary">
                        بارگذاری تصویر عمومی
                      </button>
                    </form>
                  )}
                  {isManager && (
                    <form
                      className="grid gap-3"
                      onSubmit={(e) => {
                        e.preventDefault();
                        run(async () => {
                          await api(
                            "/offerings/" + chosen.id + "/publication",
                            "POST",
                            {
                              version: publication.version || 1,
                              action: "publish",
                              content_reviewed: true,
                            },
                          );
                          await select(chosen);
                          setNotice("آگهی پالایش‌شده در ویترین فعال شد.");
                        });
                      }}
                    >
                      <label>
                        <input className="w-auto" type="checkbox" required />{" "}
                        محله و اطلاعات عمومی را بررسی کردم؛ فاقد تماس و نشانی
                        دقیق‌اند.
                      </label>
                      <button className="primary" disabled={busy}>
                        انتشار در ویترین
                      </button>
                    </form>
                  )}
                  <form
                    className="grid gap-3 border-t pt-4"
                    onSubmit={(e) => {
                      const d = fields(e);
                      const changes = Object.fromEntries(
                        Object.entries(d).filter(([, v]) => v !== ""),
                      );
                      run(async () => {
                        await api(
                          "/offerings/" + chosen.id + "/revisions",
                          "POST",
                          {
                            base_version: chosen.version,
                            changes: { version: chosen.version, ...changes },
                          },
                        );
                        await select(chosen);
                        setNotice("نسخه اصلاحی برای بررسی ارسال شد.");
                      });
                    }}
                  >
                    <h4>بازنگری عرضه تأییدشده</h4>
                    <p className="muted">
                      فقط فیلدهای تغییرکرده را وارد کنید؛ نسخه فعلی تا تأیید
                      مستقل باقی می‌ماند.
                    </p>
                    {[
                      ["district", "محله"],
                      ["area", "متراژ"],
                      ["price_toman", "قیمت فروش (تومان)"],
                      ["deposit_toman", "ودیعه (تومان)"],
                      ["rent_toman", "اجاره (تومان)"],
                    ].map(([k, label]) => (
                      <label key={k}>
                        {label}
                        <input name={k} />
                      </label>
                    ))}
                    <button className="primary" disabled={busy}>
                      ارسال بازنگری
                    </button>
                  </form>
                </>
              )}
              {revisions.map((r) => (
                <article key={r.id} className="border-t pt-3 grid gap-2">
                  <strong>
                    بازنگری {r.id.slice(0, 8)} ·{" "}
                    {
                      (
                        {
                          submitted: "در انتظار",
                          approved: "تأییدشده",
                          rejected: "ردشده",
                        } as any
                      )[r.state]
                    }
                  </strong>
                  {Object.entries(r.changes).map(([k, v]) => (
                    <p key={k}>
                      {(
                        {
                          district: "محله",
                          area: "متراژ",
                          price_toman: "قیمت فروش",
                          deposit_toman: "ودیعه",
                          rent_toman: "اجاره",
                          kind: "نوع ملک",
                          transaction: "معامله",
                        } as any
                      )[k] || k}
                      : {String(v)}
                    </p>
                  ))}
                  <p>{r.reason}</p>
                  {r.can_review && (
                    <form
                      onSubmit={(e) => {
                        const d = fields(e);
                        run(async () => {
                          await api(
                            "/revisions/" + r.id + "/review",
                            "POST",
                            d,
                          );
                          await load();
                          const fresh = await api("/offerings/" + chosen.id);
                          await select(fresh);
                          setNotice("تصمیم بررسی ثبت شد.");
                        });
                      }}
                      className="grid gap-2"
                    >
                      <Input name="reason" label="دلیل تصمیم" />
                      <select name="decision">
                        <option value="approved">تأیید</option>
                        <option value="rejected">رد</option>
                      </select>
                      <button disabled={busy} className="primary">
                        ثبت تصمیم مستقل
                      </button>
                    </form>
                  )}
                </article>
              ))}
            </section>
          )}
        </div>
      )}
      {tab === "finance" && (
        <div className="grid lg:grid-cols-2 gap-5">
          <section className="grid gap-3 self-start">
            {isManager && (
              <form
                className="card grid gap-3"
                onSubmit={(e) => {
                  const d = fields(e);
                  run(async () => {
                    const obj = await api("/finance/deals", "POST", d);
                    setDeal(obj);
                    await load();
                  });
                }}
              >
                <h3>ثبت معامله</h3>
                <label>
                  عرضه تأییدشده
                  <select name="offering" required>
                    {offerings
                      .filter((o) => o.status === "approved")
                      .map((o) => (
                        <option key={o.id} value={o.id}>
                          {o.district} · {o.id.slice(0, 8)}
                        </option>
                      ))}
                  </select>
                </label>
                <Input name="amount" label="مبلغ معامله (تومان)" />
                <button className="primary" disabled={busy}>
                  ایجاد پرونده معامله
                </button>
              </form>
            )}
            <div className="card grid gap-2">
              <h3>{isManager ? "معاملات دفتر" : "سهم‌های شخصی شما"}</h3>
              {deals.length === 0 && <p>معامله‌ای برای نمایش وجود ندارد.</p>}
              {deals.map((x) => (
                <button
                  className="secondary"
                  disabled={busy}
                  key={x.id}
                  onClick={() => {
                    setDeal(x);
                    operations.current = {};
                  }}
                >
                  {x.id.slice(0, 8)} · {x.state === "open" ? "باز" : "لغوشده"} ·{" "}
                  {x.amount ? money(x.amount) + " تومان" : ""}
                </button>
              ))}
            </div>
          </section>
          {deal && (
            <section className="card grid gap-4 self-start">
              <h3>
                معامله {deal.id.slice(0, 8)} · نسخه {deal.version}
              </h3>
              {deal.shares && (
                <>
                  <p>توافق نسخه {deal.sequence}</p>
                  {isManager && (
                    <p>
                      مبنای تقسیم {money(deal.basis)} · وصول خالص{" "}
                      {money(deal.distributable)} · مازاد تعیین‌تکلیف{" "}
                      {money(deal.excess)} تومان
                    </p>
                  )}
                  {deal.shares.map((x: any) => (
                    <article className="border-t pt-3" key={x.beneficiary}>
                      <strong>{name(x.beneficiary)}</strong>
                      <p>
                        {x.roles
                          ?.map(
                            (r: string) =>
                              (
                                ({
                                  supplier: "معرف عرضه",
                                  customer: "معرف متقاضی",
                                  collaborator: "همکار",
                                  office: "دفتر",
                                }) as any
                              )[r],
                          )
                          .join(" · ")}
                      </p>
                      <p>
                        سهم مصوب {money(x.approved)} · قابل پرداخت فعلی{" "}
                        {money(x.payable)} · پرداخت‌شده {money(x.paid)} · مانده
                        کل {money(x.remaining)} · قابل بازپس‌گیری{" "}
                        {money(x.recoverable)} تومان
                      </p>
                      <p>
                        وضعیت سهم:{" "}
                        {
                          (
                            {
                              pending: "منتظر موافقت",
                              accepted: "موافق",
                              disputed: "مورد اختلاف",
                              resolved: "تعیین تکلیف مدیر",
                            } as any
                          )[x.decision]
                        }
                      </p>
                      {x.beneficiary !== "office" && (
                        <form
                          className="grid gap-2"
                          onSubmit={(e) => {
                            const d = fields(e);
                            run(() =>
                              act("vote", {
                                ...d,
                                agreement: deal.agreement,
                                ...(isManager
                                  ? { beneficiary: x.beneficiary }
                                  : {}),
                              }),
                            );
                          }}
                        >
                          <select name="decision">
                            {isManager ? (
                              <option value="resolved">
                                تعیین تکلیف اختلاف توسط مدیر
                              </option>
                            ) : (
                              <>
                                <option value="accepted">موافقت با سهم</option>
                                <option value="disputed">ثبت اعتراض</option>
                              </>
                            )}
                          </select>
                          <Input name="reason" label="توضیح موافقت یا اعتراض" />
                          <button className="secondary" disabled={busy}>
                            ثبت نظر
                          </button>
                        </form>
                      )}
                    </article>
                  ))}
                </>
              )}
              {isManager && deal.state === "open" && (
                <>
                  <form
                    className="grid gap-3 border-t pt-4"
                    onSubmit={(e) => {
                      const d = fields(e);
                      run(async () => {
                        const payload = {
                          fee: d.fee,
                          mode,
                          reason: d.reason,
                          deductions:
                            d.deduction_amount === "0"
                              ? []
                              : [
                                  {
                                    title: d.deduction_title,
                                    amount: d.deduction_amount,
                                  },
                                ],
                          shares: shares.map((x) => ({
                            ...x,
                            value:
                              mode === "percent" ? percent(x.value) : x.value,
                          })),
                        };
                        await act("agreement", payload);
                      });
                    }}
                  >
                    <h4>
                      {deal.agreement
                        ? "نسخه اصلاحی توافق"
                        : "توافق سهم مصوب مدیر"}
                    </h4>
                    <p className="muted">
                      هیچ تعرفه یا درصدی از قبل فعال نیست. اصلاح پس از پرداخت
                      نسخه جدید می‌سازد و پرداخت قبلی را حفظ می‌کند.
                    </p>
                    <Input name="fee" label="کارمزد مصوب (تومان)" />
                    <Input
                      name="deduction_title"
                      label="عنوان کسر مصوب (در صورت نبود: بدون کسر)"
                      value="بدون کسر"
                    />
                    <Input
                      name="deduction_amount"
                      label="مبلغ کسر مصوب (تومان)"
                      value="0"
                    />
                    <label>
                      روش سهم
                      <select
                        value={mode}
                        onChange={(e) => setMode(e.target.value)}
                      >
                        <option value="percent">درصدی</option>
                        <option value="fixed">مبلغ ثابت</option>
                      </select>
                    </label>
                    {shares.map((x, i) => (
                      <div className="flex flex-wrap gap-2" key={i}>
                        <label>
                          ذی‌نفع
                          <select
                            value={x.beneficiary}
                            onChange={(e) =>
                              setShares(
                                shares.map((v, j) =>
                                  i === j
                                    ? {
                                        ...v,
                                        beneficiary: e.target.value,
                                        roles:
                                          e.target.value === "office"
                                            ? ["office"]
                                            : ["collaborator"],
                                      }
                                    : v,
                                ),
                              )
                            }
                          >
                            <option value="office">دفتر</option>
                            {members.map((m) => (
                              <option key={m.id} value={m.id}>
                                {m.name}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label>
                          {mode === "percent" ? "درصد سهم" : "سهم به تومان"}
                          <input
                            required
                            value={x.value}
                            onChange={(e) =>
                              setShares(
                                shares.map((v, j) =>
                                  i === j ? { ...v, value: e.target.value } : v,
                                ),
                              )
                            }
                          />
                        </label>
                        {x.beneficiary !== "office" &&
                          [
                            ["supplier", "معرف عرضه"],
                            ["customer", "معرف متقاضی"],
                            ["collaborator", "همکار"],
                          ].map(([role, title]) => (
                            <label key={role}>
                              <input
                                className="w-auto"
                                type="checkbox"
                                checked={x.roles.includes(role)}
                                onChange={(e) =>
                                  setShares(
                                    shares.map((v, j) =>
                                      i === j
                                        ? {
                                            ...v,
                                            roles: e.target.checked
                                              ? [...v.roles, role]
                                              : v.roles.filter(
                                                  (r) => r !== role,
                                                ),
                                          }
                                        : v,
                                    ),
                                  )
                                }
                              />
                              {title}
                            </label>
                          ))}
                        {i > 0 && (
                          <button
                            type="button"
                            className="secondary"
                            onClick={() =>
                              setShares(shares.filter((_, j) => j !== i))
                            }
                          >
                            حذف ردیف
                          </button>
                        )}
                      </div>
                    ))}
                    <button
                      type="button"
                      className="secondary"
                      onClick={() =>
                        setShares([
                          ...shares,
                          {
                            beneficiary: members[0]?.id || "office",
                            value: "0",
                            roles: ["collaborator"],
                          },
                        ])
                      }
                    >
                      افزودن ذی‌نفع
                    </button>
                    <Input name="reason" label="دلیل و مرجع توافق یا اصلاح" />
                    <button className="primary" disabled={busy}>
                      تصویب نسخه توافق
                    </button>
                  </form>
                  {deal.agreement && (
                    <>
                      {["receipt", "payout"].map((action) => (
                        <form
                          key={action}
                          className="grid gap-3 border-t pt-4"
                          onSubmit={(e) => {
                            const d = fields(e);
                            run(() => cash(action, d));
                          }}
                        >
                          <h4>
                            {action === "receipt" ? "ثبت دریافت" : "ثبت پرداخت"}
                          </h4>
                          <Input name="amount" label="مبلغ (تومان)" />
                          {action === "receipt" ? (
                            <Input
                              name="distributable"
                              label="بخش قابل تقسیم از این دریافت (تومان)"
                            />
                          ) : (
                            <label>
                              ذی‌نفع
                              <select name="beneficiary">
                                {deal.shares.map((x: any) => (
                                  <option
                                    key={x.beneficiary}
                                    value={x.beneficiary}
                                  >
                                    {name(x.beneficiary)}
                                  </option>
                                ))}
                              </select>
                            </label>
                          )}
                          <Input
                            name="reference"
                            label="تاریخ، روش و مرجع ثبت دریافت یا پرداخت"
                          />
                          <button disabled={busy} className="primary">
                            {action === "receipt"
                              ? "ثبت دریافت"
                              : "پرداخت از مانده مجاز"}
                          </button>
                        </form>
                      ))}
                    </>
                  )}
                  <form
                    className="grid gap-2 border-t pt-4"
                    onSubmit={(e) => {
                      const d = fields(e);
                      if (confirm("معامله لغو شود؟ سوابق مالی حذف نمی‌شوند."))
                        run(() => act("cancel", d));
                    }}
                  >
                    <Input name="reason" label="دلیل لغو معامله" />
                    <button className="secondary" disabled={busy}>
                      لغو با حفظ سوابق
                    </button>
                  </form>
                </>
              )}
              {isManager &&
                deal.ledger?.map((x: any) => (
                  <article key={x.id} className="border-t pt-3 grid gap-2">
                    <p>
                      {
                        (
                          {
                            receipt: "دریافت",
                            payout: "پرداخت",
                            receipt_back: "برگشت دریافت",
                            payout_back: "برگشت پرداخت",
                          } as any
                        )[x.kind]
                      }{" "}
                      · {money(x.amount)} تومان ·{" "}
                      {new Date(x.created_at).toLocaleString("fa-IR", {
                        timeZone: "Asia/Tehran",
                      })}
                    </p>
                    {["receipt", "payout"].includes(x.kind) && (
                      <form
                        className="flex gap-2"
                        onSubmit={(e) => {
                          const d = fields(e);
                          run(() => cash("reverse", { entry: x.id, ...d }));
                        }}
                      >
                        <Input name="reason" label="دلیل ثبت سند معکوس" />
                        <button className="secondary" disabled={busy}>
                          ثبت سند معکوس
                        </button>
                      </form>
                    )}
                  </article>
                ))}
              {isManager &&
                deal.agreements?.map((x: any) => (
                  <p key={x.id} className="muted">
                    توافق تاریخی نسخه {x.sequence}: کارمزد {money(x.fee)} و مبنا{" "}
                    {money(x.basis)} تومان
                  </p>
                ))}
            </section>
          )}
        </div>
      )}
    </section>
  );
}
