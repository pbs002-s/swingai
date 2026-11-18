"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { hasRole, useMe } from "@/components/app/Shell";
import { Empty, PageHeader } from "@/components/app/ui";
import { StepAssign, StepSettings, StepVerify } from "@/components/cameras/FinishSteps";
import { StepEdgeBox, StepFind, StepTest } from "@/components/cameras/SetupSteps";
import { ZoneEditor } from "@/components/cameras/ZoneEditor";
import { STEPS, StepIndicator, connectionProblem } from "@/components/cameras/parts";
import type { WizardDraft } from "@/lib/types-cameras";

const INITIAL: WizardDraft = {
  edgeBoxId: null,
  name: "",
  connection: { host: "", port: 554, rtsp_path: "/", username: "", password: "" },
  test: null,
  lineId: null,
  stations: [],
  zones: [],
  purpose: "activity",
  fps: 5,
  faceBlur: true,
};

/** Why the user cannot go on from `step` yet, or null when they can. */
function blocker(step: number, d: WizardDraft): string | null {
  if (step === 0 && d.edgeBoxId == null) return "Choose an online edge box.";
  if (step === 1) return d.connection.host ? connectionProblem(d.connection) : "Scan and pick a camera, or enter its address.";
  if (step === 2 && !d.test) return "Run a successful connection test first.";
  if (step === 3 && d.stations.length === 0) return "Pick at least one station.";
  return null;
}

export default function NewCameraPage() {
  const me = useMe();
  const [step, setStep] = useState(0);
  const [draft, setDraft] = useState<WizardDraft>(INITIAL);
  const update = useCallback((patch: Partial<WizardDraft>) => setDraft((d) => ({ ...d, ...patch })), []);
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => heading.current?.focus(), [step]);

  if (!hasRole(me, "factory_admin")) {
    return (
      <>
        <PageHeader title="Add camera" />
        <Empty title="Only a factory admin can add cameras" text="Ask your factory admin to connect the camera." />
      </>
    );
  }

  const block = blocker(step, draft);
  const body = [
    <StepEdgeBox key="0" draft={draft} update={update} />,
    <StepFind key="1" draft={draft} update={update} />,
    <StepTest key="2" draft={draft} update={update} />,
    <StepAssign key="3" draft={draft} update={update} />,
    <ZoneEditor key="4" snapshot={draft.test?.snapshot} stations={draft.stations} zones={draft.zones} onChange={(zones) => update({ zones })} />,
    <StepSettings key="5" draft={draft} update={update} />,
    <StepVerify key="6" draft={draft} />,
  ][step];

  return (
    <>
      <PageHeader
        title="Add camera"
        sub="The edge box does the camera work; video never leaves the factory."
        actions={<Link href="/app/cameras" className="btn btn-ghost">Cancel</Link>}
      />
      <StepIndicator current={step} />
      <section aria-labelledby="step-h" className="panel flex max-w-[1100px] flex-col gap-5 p-5">
        <h2 id="step-h" ref={heading} tabIndex={-1} className="text-[18px] font-semibold outline-none">
          Step {step + 1} of {STEPS.length}: {STEPS[step]}
        </h2>
        {body}
        {step < STEPS.length - 1 && (
          <div className="flex flex-wrap items-center gap-3 border-t border-line pt-4">
            <button type="button" className="btn btn-ghost" disabled={step === 0} onClick={() => setStep(step - 1)}>Back</button>
            <button type="button" className="btn btn-primary" disabled={block != null} onClick={() => setStep(step + 1)}>Next</button>
            {block && <span className="text-[13px] text-ink-3">{block}</span>}
          </div>
        )}
      </section>
    </>
  );
}
