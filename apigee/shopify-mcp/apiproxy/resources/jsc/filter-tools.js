var method = context.getVariable("mcp.method") || "";
var allowed = context.getVariable("verifyapikey.VerifyAPIKey-1.apiproduct.allowed_tools") || "";
var content = context.getVariable("response.content") || "";
var permit, items, i, payload, tools, kept, name, updated;

if (method !== "tools/list" || allowed.replace(/^\s+|\s+$/g, "") === "*" || !content) {
  // Advanced clients and non-list calls keep the server response.
} else {
  permit = {};
  items = allowed.split(",");
  for (i = 0; i < items.length; i += 1) {
    permit[items[i].replace(/^\s+|\s+$/g, "")] = true;
  }
  try {
    payload = JSON.parse(content);
  } catch (error) {
    payload = null;
  }
  tools = payload && payload.result && payload.result.tools;
  if (tools && tools.length) {
    kept = [];
    for (i = 0; i < tools.length; i += 1) {
      name = tools[i] && tools[i].name;
      if (permit[name]) {
        kept.push(tools[i]);
      }
    }
    payload.result.tools = kept;
    updated = JSON.stringify(payload);
    context.setVariable("response.content", updated);
    context.setVariable("response.header.Content-Length", String(updated.length));
  }
}
