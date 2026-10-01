import { NextResponse } from "next/server";
import { healthPayload } from "@/lib/vision-fixtures";

export const runtime = "nodejs";

export function GET() {
  return NextResponse.json(healthPayload());
}
