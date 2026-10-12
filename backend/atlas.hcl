data "external_schema" "sqlalchemy" {
  program = [
    "uv", "run", "atlas-provider-sqlalchemy",
    "--path", "./atlas_schema",
    "--dialect", "postgresql",
  ]
}

env "local" {
  src = data.external_schema.sqlalchemy.url
  dev = "docker://postgres/17/dev?search_path=public"
  migration {
    dir = "file://migrations"
  }
}
