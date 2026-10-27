/** Real DeepSeek Harness MCP runtime, without a model or provider credential. */
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
const modules = process.env.AGENT_HOST_MODULES;
assert(modules, "set AGENT_HOST_MODULES to the isolated node_modules directory");
const load = (name) => import(pathToFileURL(resolve(modules, "@deepseek-ai", name, "lib/index.js")).href);
const { Context } = await load("cordis");
const { SystemPrompt } = await load("dsh-system-prompt");
const { ToolRuntime } = await load("dsh-tools");
const mcp = await load("dsh-mcp-client");
const { config, tool, args } = JSON.parse(await readFile(process.argv[2], "utf8"));
const ctx = new Context();
try {
  await ctx.plugin(SystemPrompt).await();
  await ctx.plugin(ToolRuntime).await();
  await ctx.plugin(mcp, { ...config, failOnStartupError: true, reconnect: { enabled: false } }).await();
  const names = ctx.tools.schemas().map(t => t.name);
  const name = `mcp__${config.serverName}__${tool}`;
  assert(names.includes(name), `missing MCP tool ${name}`);
  const result = await ctx.tools.execute({callId:"integration-1",name,arguments:args,signal:AbortSignal.timeout(15000)});
  assert.equal(result.isError, false, JSON.stringify(result));
  assert(result.content.length > 0, "empty tool result");
  console.log(`DeepSeek Harness: ${names.length} tools discovered; ${tool} passed`);
} finally {
  await ctx.fiber.dispose();
}
