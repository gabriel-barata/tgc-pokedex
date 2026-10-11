import { execFileSync } from "node:child_process";
import { readdirSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const composeFile = fileURLToPath(new URL("../../compose.e2e.yml", import.meta.url));
const fixturesDir = new URL("fixtures/", import.meta.url);

function loadFixture(name: string) {
  execFileSync(
    "docker",
    [
      "compose",
      "-f",
      composeFile,
      "exec",
      "-T",
      "postgres",
      "sh",
      "-c",
      'psql -v ON_ERROR_STOP=1 --single-transaction -U "$POSTGRES_USER" -d "$POSTGRES_DB"',
    ],
    { input: readFileSync(new URL(name, fixturesDir)), stdio: ["pipe", "ignore", "inherit"] },
  );
}

export default function loadFixtures() {
  const names = readdirSync(fixturesDir)
    .filter((name) => name.endsWith(".sql"))
    .sort();
  names.forEach(loadFixture);
}
