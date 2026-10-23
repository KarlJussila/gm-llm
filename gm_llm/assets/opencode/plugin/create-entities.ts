import { promises as fs } from "node:fs"
import * as path from "node:path"
import { parseTemplate, render, templateName, TYPES, validate, type EntitySpec, type Template } from "./entities/scaffold"

/**
 * `create_entities` — write new campaign entity files in one call (design/luna.md § Campaign
 * layout). Each entity gets its file from its canon-conventions template, with the frontmatter and
 * sections the model gives and nothing else, plus its state file when the model gives state. So
 * populating a town is one call, not a template read and a hand-typed skeleton per person.
 *
 * All or nothing: every spec is checked first, and one bad spec writes no files. It never
 * overwrites — an existing entity is edited, not re-created. The canon lint still runs after.
 * The pure half (template parsing, checks, rendering) is `entities/scaffold.ts`, one directory down
 * because opencode loads every direct child of `plugin/` as a plugin.
 */
export default {
  id: "gm-create-entities",
  async setup(ctx) {
    const root = ctx.location.directory
    const templates = path.join(root, ".opencode", "skills", "canon-conventions", "templates")

    async function template(file: string): Promise<Template | undefined> {
      try {
        return parseTemplate(await fs.readFile(path.join(templates, file), "utf-8"))
      } catch {
        return undefined
      }
    }

    async function exists(p: string): Promise<boolean> {
      return fs.access(p).then(() => true, () => false)
    }

    await ctx.tool.transform((tools) => {
      tools.add({
        name: "create_entities",
        description:
          "Create new campaign entities in one call: NPCs, factions, locations, regions, items, " +
          "concepts, bestiary creatures. Each gets its file from its template with the frontmatter " +
          "and sections you give, and its state file when you give state. For new entities only; " +
          "edit existing files directly.",
        input: {
          type: "object",
          properties: {
            entities: {
              type: "array",
              items: {
                type: "object",
                properties: {
                  type: { type: "string", enum: TYPES },
                  slug: { type: "string", description: "kebab-case; becomes the file name" },
                  frontmatter: {
                    type: "object",
                    description: "Every key the type's template has (name, status, summary and its vitals); slug and type are filled in.",
                    additionalProperties: { type: ["string", "number"] },
                  },
                  sections: {
                    type: "object",
                    description: 'Body sections by heading, e.g. {"Identity / Public role": "…"}. Give the ones you have; template order is kept.',
                    additionalProperties: { type: "string" },
                  },
                  state: {
                    type: "object",
                    description: 'The state file\'s sections by heading ("Location", "Disposition", "Condition", "Doing now"), for a type that has one.',
                    additionalProperties: { type: "string" },
                  },
                },
                required: ["type", "slug", "frontmatter", "sections"],
                additionalProperties: false,
              },
            },
            as_of: { type: "string", description: 'The state files\' as-of stamp, e.g. "S0" at setup.' },
          },
          required: ["entities"],
          additionalProperties: false,
        },
        options: { codemode: false },
        async execute(args: { entities: EntitySpec[]; as_of?: string }) {
          const stateTpl = await template("entity-state.template.md")
          const errors: string[] = []
          const files: [string, string][] = []
          const seen = new Set<string>()
          for (const spec of args.entities ?? []) {
            const tpl = TYPES.includes(spec.type) ? await template(templateName(spec.type)) : undefined
            const problems = validate(spec, tpl, args.as_of)
            if (seen.has(spec.slug)) problems.push(`${spec.slug}: given twice`)
            seen.add(spec.slug)
            if (problems.length || !tpl) {
              errors.push(...problems)
              continue
            }
            const out = render(spec, tpl, stateTpl, args.as_of)
            for (const [rel, text] of [[out.path, out.text], [out.statePath, out.stateText]]) {
              if (!rel || text === undefined) continue
              if (await exists(path.join(root, "campaign", rel)))
                errors.push(`${spec.slug}: campaign/${rel} already exists — edit it instead`)
              else files.push([rel, text])
            }
          }
          if (errors.length) return { content: "Nothing written. Fix these and call again:\n- " + errors.join("\n- ") }
          for (const [rel, text] of files) {
            const p = path.join(root, "campaign", rel)
            await fs.mkdir(path.dirname(p), { recursive: true })
            await fs.writeFile(p, text, "utf-8")
          }
          return { content: "Written:\n" + files.map(([rel]) => `- campaign/${rel}`).join("\n") }
        },
      })
    })
  },
}
