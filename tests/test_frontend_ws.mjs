import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(
  new URL("../frontend/src/ws.js", import.meta.url),
  "utf8",
);
const moduleUrl = `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
const { Bridge } = await import(moduleUrl);

class FakeWebSocket {
  static OPEN = 1;

  constructor(url) {
    this.url = url;
    this.readyState = 0;
    this.sent = [];
  }

  send(message) {
    this.sent.push(JSON.parse(message));
  }

  close() {}
}

globalThis.WebSocket = FakeWebSocket;
globalThis.location = { search: "?token=secret" };

test("messages entered before the socket opens are sent after authentication", () => {
  const bridge = new Bridge("45678", {});
  bridge.send({ type: "input", text: "look" });

  bridge.ws.readyState = FakeWebSocket.OPEN;
  bridge.ws.onopen();

  assert.equal(bridge.ws.url, "ws://127.0.0.1:45678");
  assert.deepEqual(bridge.ws.sent, [
    { type: "hello", token: "secret" },
    { type: "input", text: "look" },
  ]);
  assert.deepEqual(bridge.pending, []);
});
