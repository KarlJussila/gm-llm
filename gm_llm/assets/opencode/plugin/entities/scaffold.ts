/**
 * The pure half of `create_entities` (plugin/create-entities.ts): read an entity template, check a
 * spec against it, and render the entity's file and its state file. No filesystem here — the
 * adapter reads the templates and writes the results.
 *
 * The templates in skills/canon-conventions/templates are the one home of each type's shape: the
 * frontmatter keys, the section order, and the directory (from the `Path: <dir>/{slug}.md` line in
 * the template's comment). Nothing about a type is restated here.
 */

export type EntitySpec = {
  type: string
  slug: string
  frontmatter: Record<string, string | number>
  sections?: Record<string, string>
  state?: Record<string, string>
}

export type Template = {
  dir: string // e.g. "world/npcs"
  keys: string[] // frontmatter keys, in order
  headings: string[] // `## ` section headings, in order
}

export type Rendered = { path: string; text: string; statePath?: string; stateText?: string }

// The types this tool creates. The PC and arcs have flows of their own.
export const TYPES = ["npc", "faction", "location", "region", "item", "concept", "creature"]

export function templateName(type: string): string {
  return type === "creature" ? "bestiary.template.md" : `entity-${type}.template.md`
}

const FRONTMATTER = /^---\n([\s\S]*?)\n---/
const COMMENT = /<!--[\s\S]*?-->/g

export function parseTemplate(text: string): Template {
  const fm = FRONTMATTER.exec(text)?.[1] ?? ""
  const keys = fm
    .split("\n")
    .map((l) => /^([A-Za-z][\w-]*):/.exec(l)?.[1])
    .filter((k): k is string => !!k)
  const dir = /Path: ([\w./-]+)\/\{slug\}\.md/.exec(text)?.[1] ?? ""
  const body = text.slice(fm ? text.indexOf("---", 3) + 3 : 0).replace(COMMENT, "")
  const headings = [...body.matchAll(/^## (.+?)\s*$/gm)].map((m) => m[1])
  return { dir, keys, headings }
}

const SLUG = /^[a-z0-9]+(-[a-z0-9]+)*$/

/** Every problem with `spec`, as text the model can act on; empty when it can be written. */
export function validate(spec: EntitySpec, tpl: Template | undefined, asOf?: string): string[] {
  const who = spec.slug || "(no slug)"
  if (!TYPES.includes(spec.type)) return [`${who}: type must be one of ${TYPES.join(", ")}`]
  if (!tpl || !tpl.dir) return [`${who}: no template found for type ${spec.type}`]
  const errors: string[] = []
  if (!SLUG.test(spec.slug ?? "")) errors.push(`${who}: slug must be kebab-case`)
  const fm = spec.frontmatter ?? {}
  const missing = tpl.keys.filter((k) => k !== "slug" && k !== "type" && blank(fm[k]))
  if (missing.length) errors.push(`${who}: frontmatter needs ${missing.join(", ")}`)
  if (!Object.values(spec.sections ?? {}).some((v) => !blank(v)))
    errors.push(`${who}: give at least one section of body prose`)
  if (spec.state && !/^S\d+$/.test(asOf ?? "")) errors.push(`${who}: state needs as_of, e.g. "S0"`)
  return errors
}

function blank(v: unknown): boolean {
  return v === undefined || v === null || String(v).trim() === ""
}

/** A frontmatter value as YAML: plain when it's safe to leave bare, otherwise a quoted string. */
export function yamlValue(v: string | number): string {
  if (typeof v === "number") return String(v)
  const s = v.replace(/\s*\n\s*/g, " ").trim()
  const bare = /^[A-Za-z0-9][\w .,'()/-]*$/.test(s) && !/^(true|false|yes|no|null|on|off|~)$/i.test(s)
  return bare ? s : JSON.stringify(s)
}

function sections(given: Record<string, string>, order: string[]): string[] {
  const names = [...order.filter((h) => h in given), ...Object.keys(given).filter((h) => !order.includes(h))]
  return names.filter((h) => !blank(given[h])).map((h) => `## ${h}\n${given[h].trim()}\n`)
}

export function render(spec: EntitySpec, tpl: Template, stateTpl?: Template, asOf?: string): Rendered {
  const fm: Record<string, string | number> = { ...spec.frontmatter, slug: spec.slug, type: spec.type }
  const keys = [...tpl.keys, ...Object.keys(fm).filter((k) => !tpl.keys.includes(k))]
  const head = keys.filter((k) => !blank(fm[k])).map((k) => `${k}: ${yamlValue(fm[k])}`)
  const name = String(fm.name ?? spec.slug)
  const text = ["---", ...head, "---", "", `# ${name}`, "", ...sections(spec.sections ?? {}, tpl.headings)].join("\n")
  const out: Rendered = { path: `${tpl.dir}/${spec.slug}.md`, text }
  if (spec.state) {
    const stateHead = ["---", `slug: ${spec.slug}`, "layer: state", `as-of: ${asOf}`, "---", ""]
    out.statePath = `${tpl.dir}/${spec.slug}.state.md`
    out.stateText = [...stateHead, ...sections(spec.state, stateTpl?.headings ?? [])].join("\n")
  }
  return out
}
