export const dynamic = "force-dynamic";

import { NextRequest, NextResponse } from "next/server";
import { AUTH_TOKEN_LOCAL_STORAGE_KEY, getSessionUser } from "@/lib/auth";

function normalizeToken(value: string): string {
  let token = value.trim();
  try {
    const parsed = JSON.parse(token) as unknown;
    if (typeof parsed === "string") token = parsed.trim();
  } catch {}
  return token;
}

// Reflex connects to the isolated Render origin, so Safari can hydrate the
// workspace before its LocalStorage state reaches that backend. This
// same-origin bootstrap lets the Reflex event loop recover the already-valid
// Vercel session. The response is private, never cached, and contains no
// provider credentials.
export async function GET(req: NextRequest) {
  const token = normalizeToken(
    req.cookies.get(AUTH_TOKEN_LOCAL_STORAGE_KEY)?.value ?? ""
  );
  if (!token || !(await getSessionUser(token))) {
    return NextResponse.json(
      { authenticated: false },
      { status: 401, headers: { "Cache-Control": "no-store" } }
    );
  }
  return NextResponse.json(
    { authenticated: true, token },
    { headers: { "Cache-Control": "no-store" } }
  );
}
