import { NextResponse } from "next/server";
import { loadInspection } from "@/lib/vision-fixtures";

export const runtime = "nodejs";

type Ctx = { params: Promise<{ sampleId: string }> };

export async function POST(request: Request, context: Ctx) {
  const { sampleId } = await context.params;
  const trade = new URL(request.url).searchParams.get("trade") ?? "electrical";
  const body = loadInspection(sampleId, trade);
  if (!body) {
    return NextResponse.json(
      { detail: `Unknown sample '${sampleId}' or trade '${trade}'.` },
      { status: 404 },
    );
  }
  return NextResponse.json(body);
}
