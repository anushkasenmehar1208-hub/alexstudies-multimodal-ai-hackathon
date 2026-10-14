import type { Metadata } from "next";
import { TrackDDemo } from "@/components/track-d/TrackDDemo";

export const metadata: Metadata = {
  title: "Source-Grounded Learning Lab | Alex Studies",
  description: "Upload learning material, ask grounded questions, and practise with cited assessments.",
};

export default function TrackDPage() {
  return <TrackDDemo />;
}
