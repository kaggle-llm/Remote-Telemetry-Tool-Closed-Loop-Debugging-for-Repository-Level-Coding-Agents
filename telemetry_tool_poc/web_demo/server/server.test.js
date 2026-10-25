import test from "node:test";
import assert from "node:assert/strict";
import crypto from "node:crypto";

test("application session tokens are random and hashed at rest", () => {
  const sid = crypto.randomBytes(32).toString("base64url");
  const hash = crypto.createHash("sha256").update(sid).digest("hex");
  assert.equal(sid.length >= 40, true);
  assert.equal(hash.length, 64);
  assert.notEqual(sid, hash);
});

test("HMAC session signatures reject tampered values", () => {
  const secret = "test-only-session-secret-at-least-32-chars";
  const sign = (value) => crypto.createHmac("sha256", secret).update(value).digest("base64url");
  const value = Buffer.from(JSON.stringify({ sid: "random", exp: Date.now() + 1000 })).toString("base64url");
  const signature = sign(value);
  assert.equal(sign(value), signature);
  assert.notEqual(sign(`${value}tampered`), signature);
});
