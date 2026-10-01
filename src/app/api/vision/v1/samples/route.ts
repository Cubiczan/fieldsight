import { NextResponse } from "next/server";
import { samplesPayload } from "@/lib/vision-fixtures";

export const runtime = "nodejs";

export function GET() {
  return NextResponse.json(samplesPayload());
}
