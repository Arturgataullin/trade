import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";
import ts from "typescript";

// Compile the pure display helpers without needing a browser or a test framework.
const source = await readFile(new URL("../src/simulationDisplay.ts", import.meta.url), "utf8");
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
const { decimalLabel, newerRun } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`);

test("large Decimal values retain all integer digits", () => {
  assert.equal(decimalLabel("1234567890123456.12345678"), "1\u00a0234\u00a0567\u00a0890\u00a0123\u00a0456,12345678");
});
test("Pydantic scientific notation and zero are readable", () => {
  assert.equal(decimalLabel("0E-16"), "0");
  assert.equal(decimalLabel("1E-8"), "0,00000001");
  assert.equal(decimalLabel("-2.50E+3"), "-2\u00a0500");
  assert.equal(decimalLabel("0.0000000001"), "≈0");
  assert.equal(decimalLabel(null), "—");
});
test("delayed poll cannot overwrite a new run or completed status", () => {
  const completed = { id: 7, status: "completed", current_step: 10 };
  assert.equal(newerRun(completed, { id: 6, status: "running", current_step: 20 }), completed);
  assert.equal(newerRun(completed, { id: 7, status: "running", current_step: 10 }), completed);
  const started = { id: 8, status: "running", current_step: 0 };
  assert.equal(newerRun(completed, started), started);
});
