import { cleanup } from "@testing-library/react";
import { afterAll, afterEach } from "vitest";
import { server } from "./test-server.ts";

server.listen({ onUnhandledRequest: "error" });

afterEach(() => {
  cleanup();
  server.resetHandlers();
});

afterAll(() => {
  server.close();
});
