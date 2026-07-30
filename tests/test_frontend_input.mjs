import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(
  new URL("../frontend/src/input.js", import.meta.url),
  "utf8",
);
const moduleUrl = `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
const { Input } = await import(moduleUrl);

function makeInput() {
  const sent = [];
  const input = Object.create(Input.prototype);
  input.element = {
    value: "",
    selectionStart: 0,
    setSelectionRange(start) {
      this.selectionStart = start;
    },
  };
  input.bridge = { send: (message) => sent.push(message) };
  input.history = [];
  input.historyIndex = 0;
  input.words = [];
  input.completion = null;
  return { input, sent };
}

function keyEvent(key, modifiers = {}) {
  return {
    key,
    ctrlKey: false,
    altKey: false,
    shiftKey: false,
    metaKey: false,
    getModifierState: () => false,
    prevented: false,
    preventDefault() {
      this.prevented = true;
    },
    ...modifiers,
  };
}

test("Escape reaches the engine so the speech-flush binding works", () => {
  const { input, sent } = makeInput();
  const event = keyEvent("Escape");

  input._onKey(event);

  assert.equal(event.prevented, true);
  assert.deepEqual(sent, [{ type: "key", key: "escape" }]);
});

test("modified Enter reaches the engine", () => {
  const { input, sent } = makeInput();
  const event = keyEvent("Enter", { ctrlKey: true });

  input._onKey(event);

  assert.equal(event.prevented, true);
  assert.deepEqual(sent, [{ type: "key", key: "ctrl+enter" }]);
});

test("Ctrl+Space completes from recent output and cycles forward", () => {
  const { input, sent } = makeInput();
  input.addOutput("A goblin arrives");
  input.addOutput("A goblin-king arrives");
  input.element.value = "kill gob";
  input.element.selectionStart = input.element.value.length;
  const event = keyEvent(" ", { ctrlKey: true });

  input._onKey(event);

  assert.equal(event.prevented, true);
  assert.equal(input.element.value, "kill goblin-king");
  input._onKey(keyEvent(" ", { ctrlKey: true }));
  assert.equal(input.element.value, "kill goblin");
  assert.deepEqual(sent, []);
});

test("Ctrl+Shift+Space can start completion in reverse", () => {
  const { input } = makeInput();
  input.addOutput("goblin gnome goblin-king");
  input.element.value = "g";
  input.element.selectionStart = 1;

  input._onKey(keyEvent(" ", { ctrlKey: true, shiftKey: true }));

  assert.equal(input.element.value, "goblin");
});

test("browser editing shortcuts remain local", () => {
  const { input, sent } = makeInput();
  const event = keyEvent("v", { ctrlKey: true });

  input._onKey(event);

  assert.equal(event.prevented, false);
  assert.deepEqual(sent, []);
});

test("macOS Command shortcuts remain local", () => {
  const { input, sent } = makeInput();
  const event = keyEvent("v", { metaKey: true });

  input._onKey(event);

  assert.equal(event.prevented, false);
  assert.deepEqual(sent, []);
});

test("AltGraph text entry remains local", () => {
  const { input, sent } = makeInput();
  const event = keyEvent("@", {
    ctrlKey: true,
    altKey: true,
    getModifierState: (modifier) => modifier === "AltGraph",
  });

  input._onKey(event);

  assert.equal(event.prevented, false);
  assert.deepEqual(sent, []);
});

test("browser find shortcuts remain available", () => {
  const { input, sent } = makeInput();
  const ctrlF = keyEvent("f", { ctrlKey: true });
  const f3 = keyEvent("F3");

  input._onKey(ctrlF);
  input._onKey(f3);

  assert.equal(ctrlF.prevented, false);
  assert.equal(f3.prevented, false);
  assert.deepEqual(sent, []);
});
