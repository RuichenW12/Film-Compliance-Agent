import { t } from "@/lib/i18n";
import type { PolicyVerificationStatus } from "@/lib/api";

export function PolicyVerificationBanner({
  status,
}: {
  status: PolicyVerificationStatus | null | undefined;
}) {
  if (status !== "mock_verified") return null;

  return (
    <p className="alert warning-alert" role="alert">
      {t("policy.verification.mock")}
    </p>
  );
}
