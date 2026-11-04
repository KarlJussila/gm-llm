/**
 * `gm-llm.yaml`'s `temperature` and `top-p`, sent with every request to the campaign's model.
 *
 * opencode (2.2.4) accepts an agent's `temperature` / `top_p` and a model's `options` in its
 * config, but drops both before a request to a built-in provider; only a `context` hook's
 * options reach it. The orchestrator hands the settings over as `GM_LLM_SAMPLING`
 * (`{"model": "provider/model", "temperature": …, "top_p": …}`); without it, this does nothing
 * and the provider picks its own.
 */
export default {
  id: "gm-sampling",
  async setup(ctx) {
    const raw = process.env.GM_LLM_SAMPLING
    if (!raw) return
    const { model, temperature, top_p } = JSON.parse(raw)
    const hook = (event) => {
      if (`${event.model.providerID}/${event.model.id}` !== model) return
      if (temperature !== undefined) event.options.temperature = temperature
      if (top_p !== undefined) event.options.topP = top_p
    }
    for (const name of ["context", "compaction", "generate"]) await ctx.session.hook(name, hook)
  },
}
