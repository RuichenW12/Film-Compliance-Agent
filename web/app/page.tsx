import { ReviewFlow } from "@/components/review-flow";


export default async function HomePage({
  searchParams,
}: {
  searchParams: Promise<{ review?: string | string[] }>;
}) {
  const params = await searchParams;
  const review = Array.isArray(params.review) ? params.review[0] : params.review;
  return <ReviewFlow initialReviewId={review} />;
}
