// Edge-compatible session cookie signing (Web Crypto HMAC).
// The cookie holds an HMAC of a constant, so only someone with AUTH_SECRET can
// forge it. Simple and sufficient for a single-user private dashboard.

const CLAIM = "amm-authed-v1";
const enc = new TextEncoder();

async function hmacHex(secret: string, msg: string): Promise<string> {
  const key = await crypto.subtle.importKey(
    "raw",
    enc.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const sig = await crypto.subtle.sign("HMAC", key, enc.encode(msg));
  return Array.from(new Uint8Array(sig))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

export async function makeToken(secret: string): Promise<string> {
  return hmacHex(secret, CLAIM);
}

function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

export async function verifyToken(
  token: string | undefined,
  secret: string,
): Promise<boolean> {
  if (!token || !secret) return false;
  const expected = await hmacHex(secret, CLAIM);
  return timingSafeEqual(token, expected);
}

export const SESSION_COOKIE = "amm_session";
