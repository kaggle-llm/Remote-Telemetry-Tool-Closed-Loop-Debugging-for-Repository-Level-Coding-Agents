import "dotenv/config";
import crypto from "node:crypto";
import express from "express";
import cookieParser from "cookie-parser";
import { OAuth2Client } from "google-auth-library";
import { createClient } from "@supabase/supabase-js";

const required = ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_CALLBACK_URL", "APP_SESSION_SECRET", "SUPABASE_URL", "SUPABASE_SECRET_KEY", "APP_ORIGIN"];
for (const name of required) if (!process.env[name]) throw new Error(`Missing environment variable: ${name}`);
if (process.env.APP_SESSION_SECRET.length < 32) throw new Error("APP_SESSION_SECRET must be at least 32 characters.");

const app = express();
const google = new OAuth2Client(process.env.GOOGLE_CLIENT_ID, process.env.GOOGLE_CLIENT_SECRET, process.env.GOOGLE_CALLBACK_URL);
const db = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_SECRET_KEY, { auth: { persistSession: false, autoRefreshToken: false } });
const digest = (text) => crypto.createHash("sha256").update(text).digest("hex");
const randomKey = (prefix) => `${prefix}_${crypto.randomBytes(32).toString("base64url")}`;
const sign = (value) => crypto.createHmac("sha256", process.env.APP_SESSION_SECRET).update(value).digest("base64url");
const validSignedValue = (value, signature) => {
  const expected = Buffer.from(sign(value));
  const received = Buffer.from(signature || "");
  return expected.length === received.length && crypto.timingSafeEqual(expected, received);
};

app.use(express.json({ limit: "16kb" }));
app.use(cookieParser());
app.use((req, res, next) => {
  res.set("Cache-Control", "no-store");
  next();
});
app.use((req, res, next) => {
  if (req.path.startsWith("/api/") && req.method !== "GET" && req.method !== "HEAD" && !req.get("origin")) {
    return res.status(403).json({ error: "Origin header required." });
  }
  next();
});

function setSessionCookie(res, raw) {
  const encoded = Buffer.from(raw).toString("base64url");
  res.cookie("tl_session", `${encoded}.${sign(encoded)}`, {
    httpOnly: true, secure: process.env.NODE_ENV === "production", sameSite: "lax", path: "/", maxAge: 7 * 86400000,
  });
}

async function requireUser(req, res, next) {
  try {
    const [encoded, signature, extra] = (req.cookies.tl_session || "").split(".");
    if (!encoded || !signature || extra || !validSignedValue(encoded, signature)) return res.status(401).json({ error: "Sign in required." });
    const session = JSON.parse(Buffer.from(encoded, "base64url").toString("utf8"));
    if (session.exp < Date.now()) return res.status(401).json({ error: "Session expired." });
    const { data, error } = await db.from("app_sessions").select("user_id,expires_at").eq("token_hash", digest(session.sid)).maybeSingle();
    if (error || !data || Date.parse(data.expires_at) < Date.now()) return res.status(401).json({ error: "Session expired." });
    const { data: user, error: userError } = await db.from("users").select("id,email,display_name,avatar_url").eq("id", data.user_id).single();
    if (userError) return res.status(401).json({ error: "User not found." });
    req.user = user;
    next();
  } catch {
    return res.status(401).json({ error: "Invalid session." });
  }
}

function sameOrigin(req, res, next) {
  const origin = req.get("origin");
  if (origin && origin !== process.env.APP_ORIGIN) return res.status(403).json({ error: "Invalid origin." });
  next();
}

app.get("/api/auth/google", async (_req, res) => {
  const state = crypto.randomBytes(24).toString("base64url");
  const stateToken = `${state}.${sign(state)}`;
  const nonce = crypto.randomBytes(24).toString("base64url");
  res.cookie("oauth_nonce", nonce, { httpOnly: true, secure: process.env.NODE_ENV === "production", sameSite: "lax", maxAge: 600000, path: "/" });
  const url = await google.generateAuthUrl({ scope: ["openid", "email", "profile"], state: stateToken, nonce, prompt: "select_account" });
  res.redirect(url);
});

app.get("/api/auth/google/callback", async (req, res) => {
  try {
    if (req.query.error) return res.status(401).send("Google sign-in was cancelled or denied.");
    const [state, stateSignature, extra] = String(req.query.state || "").split(".");
    if (!state || !stateSignature || extra || !validSignedValue(state, stateSignature)) return res.status(400).send("OAuth state validation failed. Start a new Google sign-in from the app.");
    const expectedNonce = req.cookies.oauth_nonce;
    res.clearCookie("oauth_nonce", { path: "/" });
    if (!expectedNonce) return res.status(400).send("OAuth nonce missing. Start a new Google sign-in from the app.");
    const { tokens } = await google.getToken(String(req.query.code || ""));
    if (!tokens.id_token) return res.status(401).send("Google ID token missing.");
    const ticket = await google.verifyIdToken({ idToken: tokens.id_token, audience: process.env.GOOGLE_CLIENT_ID });
    const identity = ticket.getPayload();
    if (!identity?.sub || !identity.email || identity.email_verified !== true || identity.nonce !== expectedNonce) return res.status(401).send("Verified Google account required.");
    const { data: user, error: userError } = await db.from("users").upsert({
      google_sub: identity.sub,
      email: identity.email,
      display_name: identity.name || null,
      avatar_url: identity.picture || null,
      updated_at: new Date().toISOString(),
    }, { onConflict: "google_sub" }).select("id").single();
    if (userError) throw userError;
    const sid = crypto.randomBytes(32).toString("base64url");
    const expiresAt = new Date(Date.now() + 7 * 86400000).toISOString();
    const { error: sessionError } = await db.from("app_sessions").insert({ user_id: user.id, token_hash: digest(sid), expires_at: expiresAt });
    if (sessionError) throw sessionError;
    setSessionCookie(res, JSON.stringify({ sid, exp: Date.parse(expiresAt) }));
    return res.redirect(process.env.APP_ORIGIN);
  } catch (error) {
    console.error("Google OAuth callback failed:", error.message);
    return res.status(401).send("Google sign-in failed. Return to the app and try again.");
  }
});

app.post("/api/auth/logout", sameOrigin, requireUser, async (req, res) => {
  const [encoded] = (req.cookies.tl_session || "").split(".");
  const session = JSON.parse(Buffer.from(encoded, "base64url").toString("utf8"));
  await db.from("app_sessions").delete().eq("token_hash", digest(session.sid));
  res.clearCookie("tl_session", { path: "/" });
  res.status(204).end();
});

app.get("/api/auth/logout", async (req, res) => {
  const [encoded] = (req.cookies.tl_session || "").split(".");
  if (encoded) {
    try {
      const session = JSON.parse(Buffer.from(encoded, "base64url").toString("utf8"));
      await db.from("app_sessions").delete().eq("token_hash", digest(session.sid));
    } catch {}
  }
  res.clearCookie("tl_session", { path: "/" });
  res.redirect(process.env.APP_ORIGIN);
});

app.get("/api/me", requireUser, (req, res) => res.json({ user: req.user }));
app.get("/api/health", (_req, res) => res.json({ status: "ok" }));

app.get("/api/keys", requireUser, async (req, res) => {
  const { data, error } = await db.from("tool_api_keys").select("id,name,key_prefix,revoked_at,created_at").eq("user_id", req.user.id).order("created_at", { ascending: false });
  if (error) return res.status(500).json({ error: "Could not load tool keys." });
  res.json(data);
});

app.post("/api/keys", sameOrigin, requireUser, async (req, res) => {
  const secret = randomKey("tlk");
  const name = String(req.body.name || "AI tool key").slice(0, 80);
  const { data, error } = await db.from("tool_api_keys").insert({ user_id: req.user.id, name, key_hash: digest(secret), key_prefix: secret.slice(0, 12) }).select("id,name,key_prefix,revoked_at,created_at").single();
  if (error) return res.status(500).json({ error: "Could not create tool key." });
  res.json({ ...data, secret });
});

app.post("/api/keys/:id/revoke", sameOrigin, requireUser, async (req, res) => {
  const { error } = await db.from("tool_api_keys").update({ revoked_at: new Date().toISOString() }).eq("id", req.params.id).eq("user_id", req.user.id);
  if (error) return res.status(500).json({ error: "Could not revoke tool key." });
  res.status(204).end();
});

app.get("/api/sessions", requireUser, async (req, res) => {
  const { data, error } = await db.from("ai_sessions").select("id,name,session_prefix,revoked_at,created_at").eq("user_id", req.user.id).order("created_at", { ascending: false });
  if (error) return res.status(500).json({ error: "Could not load AI sessions." });
  res.json(data);
});

app.post("/api/sessions", sameOrigin, requireUser, async (req, res) => {
  const secret = randomKey("tls");
  const name = String(req.body.name || "AI session").slice(0, 80);
  const { data, error } = await db.from("ai_sessions").insert({ user_id: req.user.id, name, session_hash: digest(secret), session_prefix: secret.slice(0, 12) }).select("id,name,session_prefix,revoked_at,created_at").single();
  if (error) return res.status(500).json({ error: "Could not create AI session." });
  res.json({ ...data, secret });
});

app.post("/api/sessions/:id/revoke", sameOrigin, requireUser, async (req, res) => {
  const { error } = await db.from("ai_sessions").update({ revoked_at: new Date().toISOString() }).eq("id", req.params.id).eq("user_id", req.user.id);
  if (error) return res.status(500).json({ error: "Could not revoke AI session." });
  res.status(204).end();
});

app.post("/api/demo/log", sameOrigin, requireUser, async (req, res) => {
  const { tool_key: toolKey, session_key: sessionKey } = req.body;
  const { data, error } = await db.rpc("write_session_log", {
    p_tool_key: toolKey, p_session_key: sessionKey, p_level: "error",
    p_event: "highlight_palette_presentation_failed",
    p_detail: { view: "HighlightPaletteView", action: "open_palette", failure_code: "missing_presentation_context", source: "web-prototype" },
  });
  if (error) return res.status(403).json({ error: "Keys invalid, revoked, or not paired." });
  res.json(data);
});

app.post("/api/demo/logs", sameOrigin, requireUser, async (req, res) => {
  const { data, error } = await db.rpc("read_session_logs", { p_tool_key: req.body.tool_key, p_session_key: req.body.session_key, p_limit: 50 });
  if (error) return res.status(403).json({ error: "Keys invalid, revoked, or not paired." });
  res.json(data);
});

app.use(express.static(new URL("../dist", import.meta.url).pathname));
app.listen(Number(process.env.PORT || 5175), "0.0.0.0", () => console.log(`Telemetry API listening on ${process.env.PORT || 5175}`));
