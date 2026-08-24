"use client";

import { useParams } from "next/navigation";

import { ProposalDetailPage } from "@/components/policy/proposal-detail-page";


export default function Page() {
  const params = useParams<{ proposalId: string }>();
  return <ProposalDetailPage proposalId={params.proposalId} />;
}
