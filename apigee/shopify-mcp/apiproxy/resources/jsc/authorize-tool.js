var body = context.getVariable("request.content") || "";
var allowed = context.getVariable("verifyapikey.VerifyAPIKey-1.apiproduct.allowed_tools") || "";
var payload = {};
try {
  payload = JSON.parse(body);
} catch (error) {
  payload = {};
}
var method = payload.method || "";
var tool = "";
if (payload.params && payload.params.name) {
  tool = String(payload.params.name);
}
context.setVariable("mcp.method", method);
context.setVariable("mcp.tool", tool);

function permitted(name) {
  var items, i;
  if (!allowed) {
    return false;
  }
  if (allowed.replace(/^\s+|\s+$/g, "") === "*") {
    return true;
  }
  items = allowed.split(",");
  for (i = 0; i < items.length; i += 1) {
    if (items[i].replace(/^\s+|\s+$/g, "") === name) {
      return true;
    }
  }
  return false;
}

if (method === "tools/call" && !permitted(tool)) {
  context.setVariable("mcp.deny", "true");
  context.setVariable(
    "mcp.deny.message",
    "Access denied: tool '" + tool + "' is not entitled on this API product"
  );
}
