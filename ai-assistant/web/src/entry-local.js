// Offline build: open-source model on this computer via the local server.
// No Anthropic code is bundled here.
import { LocalKhabeer, TurnFailed } from "./local-agent.js";
import { start } from "./main.js";

start({
  needsKey: false,
  create: () => new LocalKhabeer(),
  isAuthError: () => false,
  describeError: (e) => (e instanceof TurnFailed ? e.message : null),
});
