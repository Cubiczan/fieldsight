import { NextResponse } from "next/server";

export const runtime = "nodejs";

export async function POST() {
  return NextResponse.json(
    {
      detail:
        "Hosted demo serves the four jobsite fixtures only. Run the Python API locally (scripts/dev.sh) to inspect uploads.",
    },
    { status: 501 },
  );
}
