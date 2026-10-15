export const dynamic = "force-dynamic";

import { NextRequest, NextResponse } from "next/server";
import {
  AUTH_TOKEN_LOCAL_STORAGE_KEY,
  getSessionUser,
} from "@/lib/auth";

function requestToken(req: NextRequest): string {
  const direct = req.headers.get("x-auth-token")?.trim();
  if (direct) return direct;
  const authorization = req.headers.get("authorization")?.trim() ?? "";
  if (authorization.toLowerCase().startsWith("bearer ")) {
    return authorization.slice(7).trim();
  }
  return req.cookies.get(AUTH_TOKEN_LOCAL_STORAGE_KEY)?.value?.trim() ?? "";
}

export async function GET(req: NextRequest) {
  try {
    const token = requestToken(req);
    if (!token) {
      return NextResponse.json({ authenticated: false }, { status: 401 });
    }
    const user = await getSessionUser(token);
    if (!user) {
      return NextResponse.json({ authenticated: false }, { status: 401 });
    }
    return NextResponse.json({
      authenticated: true,
      user: { username: user.username },
    });
  } catch (error) {
    console.error("[auth-session] lookup failed", error);
    return NextResponse.json(
      { authenticated: false, error: "Session validation is temporarily unavailable." },
      { status: 503 },
    );
  }
}
