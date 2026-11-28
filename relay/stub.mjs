// What test.mjs, restore-test.mjs and load.mjs all need the same way: the hash the worker keeps invites under, one
// request that passes its checks, the answer a working Google gives, and a stand-in Durable Object
import { Counter } from "./worker.js";

export const hash = async (t) => [...new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(t)))]
  .map((b) => b.toString(16).padStart(2, "0")).join("");

export const good = { messages: [{ role: "user", content: "Fix row 7" }], response_format: { type: "json_schema", json_schema: { name: "fix", schema: {} } } };

export const googleOk = () => new Response(JSON.stringify({ choices: [{ message: { content: '{"explanation":"x","changes":[]}' } }] }), { status: 200 });

// one Counter, requests handled one at a time (as Cloudflare does)
export function namespace() {
  const store = new Map(), obj = new Counter({ storage: { get: async (k) => store.get(k), put: async (k, v) => store.set(k, v) } });
  let queue = Promise.resolve();
  return { idFromName: () => "caps", get: () => ({ fetch: (u, init) => (queue = queue.then(() => obj.fetch(new Request(u, init)))) }) };
}
