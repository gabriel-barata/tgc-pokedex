import createClient from "openapi-fetch";
import type { paths } from "@/api/schema.gen.ts";

export const api = createClient<paths>({ baseUrl: window.location.origin });
