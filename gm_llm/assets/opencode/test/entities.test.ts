import { describe, expect, it } from "bun:test"
import { readFileSync } from "node:fs"
import * as path from "node:path"
import { parseTemplate, render, templateName, TYPES, validate, yamlValue } from "../plugin/entities/scaffold"

const TEMPLATES = path.join(import.meta.dir, "..", "skills", "canon-conventions", "templates")
const tpl = (file: string) => parseTemplate(readFileSync(path.join(TEMPLATES, file), "utf-8"))

const npc = {
  type: "npc",
  slug: "orla-venn",
  frontmatter: {
    name: "Orla Venn", status: "active", summary: "the Survey's Ternbridge clerk",
    "full-name": "Orla Venn", race: "human", pronouns: "she/her", age: "40s",
    role: "field-office clerk", affiliation: "[[meridian-survey]]",
  },
  sections: { Agenda: "Keep the office's record clean.", "Identity / Public role": "Precise, ink-stained." },
  state: { "Doing now": "Filing reports.", Location: "[[ternbridge]]" },
}

describe("templates", () => {
  it("every creatable type has a template with a directory", () => {
    for (const type of TYPES) {
      const t = tpl(templateName(type))
      expect(t.dir).not.toBe("")
      expect(t.keys).toContain("name")
    }
  })

  it("reads keys, directory and section order from the NPC template", () => {
    const t = tpl("entity-npc.template.md")
    expect(t.dir).toBe("world/npcs")
    expect(t.keys.slice(0, 3)).toEqual(["slug", "name", "type"])
    expect(t.headings.indexOf("Identity / Public role")).toBeLessThan(t.headings.indexOf("Agenda"))
  })
})

describe("validate", () => {
  it("passes a complete shim", () => {
    expect(validate(npc, tpl("entity-npc.template.md"), "S0")).toEqual([])
  })

  it("names missing vitals, a bad slug, an empty body and state without as_of", () => {
    const bad = { ...npc, slug: "Orla Venn", frontmatter: { name: "Orla" }, sections: { Agenda: " " } }
    const errors = validate(bad, tpl("entity-npc.template.md"))
    expect(errors.join("\n")).toContain("kebab-case")
    expect(errors.join("\n")).toContain("full-name")
    expect(errors.join("\n")).toContain("at least one section")
    expect(errors.join("\n")).toContain("as_of")
  })

  it("rejects a type it doesn't create", () => {
    expect(validate({ ...npc, type: "pc" }, undefined)[0]).toContain("type must be one of")
  })
})

describe("render", () => {
  const out = render(npc, tpl("entity-npc.template.md"), tpl("entity-state.template.md"), "S0")

  it("writes the file under the template's directory, sections in template order", () => {
    expect(out.path).toBe("world/npcs/orla-venn.md")
    expect(out.text.startsWith("---\nslug: orla-venn\nname: Orla Venn\ntype: npc\n")).toBe(true)
    expect(out.text.indexOf("## Identity / Public role")).toBeLessThan(out.text.indexOf("## Agenda"))
    expect(out.text).not.toContain("## Stats") // sections not given are left out
  })

  it("quotes values YAML would misread", () => {
    expect(out.text).toContain('affiliation: "[[meridian-survey]]"')
    expect(yamlValue("she/her")).toBe("she/her")
    expect(yamlValue("yes")).toBe('"yes"')
    expect(yamlValue("a: b")).toBe('"a: b"')
  })

  it("writes the state file stamped and in the state template's order", () => {
    expect(out.statePath).toBe("world/npcs/orla-venn.state.md")
    expect(out.stateText).toContain("as-of: S0")
    expect(out.stateText!.indexOf("## Location")).toBeLessThan(out.stateText!.indexOf("## Doing now"))
  })
})
