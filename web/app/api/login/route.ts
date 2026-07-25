import { NextResponse } from "next/server";
import { SESSION_COOKIE, makeToken } from "@/lib/auth";

export async function POST(req: Request) {
  const form = await req.formData();
  const password = String(form.get("password") || "");

  if (password && password === process.env.APP_PASSWORD) {
    const token = await makeToken(process.env.AUTH_SECRET || "");
    const res = NextResponse.redirect(new URL("/", req.url), { status: 303 });
    res.cookies.set(SESSION_COOKIE, token, {
      httpOnly: true,
      secure: true,
      sameSite: "lax",
      path: "/",
      maxAge: 60 * 60 * 24 * 30, // 30 days
    });
    return res;
  }

  return NextResponse.redirect(new URL("/login?error=1", req.url), {
    status: 303,
  });
}
