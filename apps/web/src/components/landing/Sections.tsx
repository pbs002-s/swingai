import { Icon } from "@/components/Icon";
import type { IconName } from "@/components/Icon";

const STEPS: { icon: IconName; title: string; text: string; detail: string }[] = [
  { icon: "pulse", title: "Sense", text: "A clamp-on sensor reads machine running time. Cameras on the edge box mark whether a station is working.", detail: "machine state · activity" },
  { icon: "check", title: "Review", text: "Phone use, needle breaks and anything the system is unsure of wait in a supervisor queue.", detail: "confirm · reject · reclassify" },
  { icon: "bars", title: "Measure", text: "Shift time, output against target and SMV efficiency, with the data coverage behind each number.", detail: "per worker · line · shift" },
  { icon: "alert", title: "Act", text: "Alerts for downtime and bad needle lots. Training suggestions only after other causes are ruled out.", detail: "alerts · investigations" },
];

const LOTS = [
  { lot: "B-104", supplier: "Supplier A", issued: 20, breaks: 8, rate: 72.4, pattern: "Batch pattern", tone: "down" },
  { lot: "GB-5598", supplier: "Supplier B", issued: 60, breaks: 4, rate: 30.5, pattern: "One machine", tone: "idle" },
  { lot: "B-109", supplier: "Supplier A", issued: 40, breaks: 3, rate: 9.4, pattern: "Normal", tone: "run" },
  { lot: "GB-5521", supplier: "Supplier B", issued: 100, breaks: 4, rate: 5.7, pattern: "Normal", tone: "run" },
  { lot: "C-077", supplier: "Supplier C", issued: 6, breaks: 1, rate: 47.6, pattern: "Too little use", tone: "off" },
] as const;

const TONE: Record<string, string> = {
  down: "bg-down-bg text-down",
  idle: "bg-idle-bg text-idle",
  run: "bg-run-bg text-run",
  off: "bg-off-bg text-ink-2",
};
const BAR: Record<string, string> = { down: "bg-down", idle: "bg-idle", run: "bg-brand", off: "bg-off" };

const FAIR = [
  { title: "No face recognition", text: "Workers are known by station assignment or their attendance card, never by their face." },
  { title: "No sound, no live watching", text: "Video becomes simple events on the edge box. Only a few still images are kept, for review." },
  { title: "Unsure means unsure", text: "Low-confidence events are shown as uncertain and never counted as fact." },
  { title: "Workers can dispute", text: "A wrong record goes back to review through the supervisor, and the correction is logged." },
];

const TIERS = [
  { where: "At each station", title: "Sensors and cameras", items: ["Clamp-on current sensor", "Optional card reader", "Camera over the work area"] },
  { where: "On the floor", title: "Edge box", items: ["Turns video into events", "72 hours of offline buffer", "Video stays here"] },
  { where: "Your server or cloud account", title: "StitchSense server", items: ["Database and dashboards", "Nightly backups", "Your data, your rules"] },
];

function SectionHead({ title, text }: { title: string; text: string }) {
  return (
    <div data-reveal className="grid grid-cols-1 items-end gap-6 lg:grid-cols-2 lg:gap-16">
      <h2 className="text-[34px] font-semibold leading-[1.06] tracking-[-0.03em] sm:text-[44px]">{title}</h2>
      <p className="max-w-[52ch] text-[17px] leading-[1.6] text-ink-2">{text}</p>
    </div>
  );
}

export function HowItWorks() {
  return (
    <section id="how" className="border-y border-line bg-surface">
      <div className="mx-auto flex max-w-[1240px] flex-col gap-14 px-6 py-24 lg:py-32">
        <SectionHead
          title="From the needle to the shift report"
          text="Sensors and cameras turn what happens at each station into events. Supervisors confirm what the system is unsure about. Only then does it count toward hours, output and rankings."
        />
        <ol data-reveal="stagger" className="grid grid-cols-1 gap-x-8 gap-y-10 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((s) => (
            <li key={s.title} className="group relative flex flex-col gap-3 border-t-2 border-ink pt-6">
              <span className="flex items-center gap-3">
                <span className="grid size-10 place-items-center rounded-xl bg-brand-bg text-brand transition-transform duration-300 ease-out group-hover:-translate-y-0.5 group-hover:rotate-[-4deg]">
                  <Icon name={s.icon} size={20} />
                </span>
                <span className="text-[22px] font-semibold tracking-[-0.02em]">{s.title}</span>
              </span>
              <p className="text-[15px] leading-[1.6] text-ink-2">{s.text}</p>
              <span className="font-mono text-[12px] text-ink-3">{s.detail}</span>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

export function NeedleTracing() {
  return (
    <section id="needles" className="mx-auto grid max-w-[1240px] grid-cols-1 items-center gap-14 px-6 py-24 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)] lg:py-32">
      <div data-reveal className="flex flex-col gap-5">
        <h2 className="text-[34px] font-semibold leading-[1.06] tracking-[-0.03em] sm:text-[44px]">Needle breaks, traced to the batch</h2>
        <p className="max-w-[46ch] text-[17px] leading-[1.6] text-ink-2">
          Every needle installed is logged against its supplier lot. When breaks cluster, StitchSense shows whether the pattern follows the batch, the machine or the operator, so a bad lot is not blamed on a worker.
        </p>
        <ul className="flex flex-col gap-2.5 text-[15px]">
          {["Breaks per needles issued, per 1,000 running hours", "No alert until a lot has enough use to judge", "Quarantine a lot and record what was found"].map((t) => (
            <li key={t} className="flex gap-3"><span className="mt-[9px] h-px w-4 shrink-0 bg-brand" />{t}</li>
          ))}
        </ul>
      </div>
      <div data-reveal className="panel overflow-hidden">
        <div className="flex items-center border-b border-line px-5 py-3.5 text-[14px]">
          <span className="font-medium">Breaks per 1,000 running hours</span>
          <span className="ml-auto text-[13px] text-ink-3">sample lots · alert at 25</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[520px] border-collapse text-[14px]">
            <thead>
              <tr className="text-left text-[12px] text-ink-3">
                <th className="px-5 py-2.5 font-medium">Lot</th>
                <th className="px-2 py-2.5 font-medium">Supplier</th>
                <th className="px-2 py-2.5 text-right font-medium">Issued</th>
                <th className="w-[38%] px-2 py-2.5 font-medium">Rate</th>
                <th className="px-5 py-2.5 font-medium">Pattern</th>
              </tr>
            </thead>
            <tbody>
              {LOTS.map((l) => (
                <tr key={l.lot} className="border-t border-line transition-colors hover:bg-bg">
                  <td className="px-5 py-3 font-mono font-medium">{l.lot}</td>
                  <td className="px-2 py-3 text-ink-2">{l.supplier}</td>
                  <td className="px-2 py-3 text-right font-mono tabular">{l.issued}</td>
                  <td className="px-2 py-3">
                    <span className="flex items-center gap-3">
                      <span className="relative h-2 flex-1 rounded-full bg-sunk">
                        <span data-bar={Math.min(100, (l.rate / 80) * 100).toFixed(0)} className={`absolute inset-y-0 left-0 rounded-full ${BAR[l.tone]} ${l.tone === "off" ? "opacity-60" : ""}`} style={{ width: `${Math.min(100, (l.rate / 80) * 100)}%` }} />
                        <span aria-hidden="true" className="absolute -inset-y-1 left-[31.25%] border-l border-dashed border-ink" />
                      </span>
                      <span className="w-10 text-right font-mono text-[13px] tabular">{l.rate}</span>
                    </span>
                  </td>
                  <td className="px-5 py-3"><span className={`rounded-md px-2 py-0.5 text-[12px] font-medium ${TONE[l.tone]}`}>{l.pattern}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

export function FairUse() {
  return (
    <section id="fair" className="bg-[#141619] text-[#eceae5]">
      <div className="mx-auto grid max-w-[1240px] grid-cols-1 gap-14 px-6 py-24 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)] lg:py-32">
        <div data-reveal className="flex flex-col gap-5">
          <h2 className="text-[34px] font-semibold leading-[1.06] tracking-[-0.03em] sm:text-[44px]">Numbers people can trust, checked by people</h2>
          <p className="max-w-[44ch] text-[17px] leading-[1.6] text-[#b4b2ab]">
            A camera can be wrong. StitchSense marks what it is unsure about, and a supervisor decides. No pay, bonus or training decision is ever made by the software alone.
          </p>
        </div>
        <div data-reveal="stagger" className="grid grid-cols-1 gap-px overflow-hidden rounded-2xl border border-[#2a2d32] bg-[#2a2d32] sm:grid-cols-2">
          {FAIR.map((f) => (
            <div key={f.title} className="flex flex-col gap-2 bg-[#17191c] p-7 transition-colors duration-300 hover:bg-[#1c1f23]">
              <span className="text-[19px] font-semibold tracking-[-0.02em]">{f.title}</span>
              <span className="text-[15px] leading-[1.6] text-[#b4b2ab]">{f.text}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

export function Install() {
  return (
    <section id="install" className="mx-auto flex max-w-[1240px] flex-col gap-14 px-6 py-24 lg:py-32">
      <SectionHead
        title="Installed in your factory, on your server"
        text="An edge box on the floor turns video and sensor signals into small events. Your server keeps the database and the dashboards. If the network drops, the edge box keeps 72 hours of events and sends them later."
      />
      <div data-reveal="stagger" className="flex flex-col items-stretch lg:flex-row">
        {TIERS.map((t, i) => (
          <div key={t.title} className="flex flex-1 flex-col items-stretch lg:flex-row">
            <div className="panel flex flex-1 flex-col gap-3 p-6 transition-[transform,box-shadow] duration-300 ease-out hover:-translate-y-0.5 hover:shadow-[0_18px_40px_-24px_rgb(20_22_25/0.35)]">
              <span className="text-[13px] text-ink-3">{t.where}</span>
              <span className="text-[22px] font-semibold tracking-[-0.02em]">{t.title}</span>
              <ul className="flex flex-col gap-1.5 text-[15px] text-ink-2">
                {t.items.map((it) => <li key={it}>{it}</li>)}
              </ul>
            </div>
            {i < TIERS.length - 1 && (
              <div aria-hidden="true" className="packet-track mx-auto h-10 w-px border-l border-dashed border-line-2 lg:mx-0 lg:my-auto lg:h-px lg:w-14 lg:border-l-0 lg:border-t" />
            )}
          </div>
        ))}
      </div>
      <p data-reveal className="text-[15px] text-ink-2">Interface in English and বাংলা. Hardware, network and what we ask of your team are listed in the deployment guide.</p>
    </section>
  );
}
