"use client";

import { ReviewList } from "@/components/app/ReviewList";
import { PageHeader } from "@/components/app/ui";
import { useI18n } from "@/lib/i18n";

export default function ReviewPage() {
  const { t } = useI18n();
  return (
    <>
      <PageHeader
        title={t("reviewQueue")}
        sub="Phone use, needle breaks and low-confidence events wait here. Nothing counts toward a person's numbers until it is reviewed."
      />
      <div className="max-w-[880px]">
        <ReviewList />
      </div>
    </>
  );
}
