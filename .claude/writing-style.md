# Writing style for text read by humans (issues, PR descriptions, docs)

The user asked for this style on 2026-11-23. Use it for GitHub issues, PR descriptions and docs.

Based on ASD-STE100 (Simplified Technical English). Goal: text that is
unambiguous and easy to read, also for non-native English speakers.

- **Short sentences.** Max. 20 words for instructions and steps, max. 25
  for descriptions. Long sentences hide the main point.
- **One idea per sentence.** Split sentences joined with "and", "which",
  or "so that" when each part says something different.
- **Active voice.** "The parser drops the last line", not "The last line
  is dropped". Passive voice hides who or what does the action.
- **Imperative for instructions.** "Run `py .claude\sandbox\tools\setup_sandbox.py`",
  not "You should run" or "It is recommended to run".
- **One word, one meaning.** Use one term per concept and keep it. Don't
  switch between synonyms (e.g. "remove" / "delete" / "drop"), because
  readers assume different words mean different things.
- **Simple, common words.** "Use" instead of "utilize", "start" instead
  of "initiate", "help" instead of "facilitate".
- **Don't omit articles or verbs.** Write "Click the button", not "Click
  button". Telegram style is ambiguous for non-native readers.
- **No phrasal verbs where a simple verb exists.** "Find" instead of
  "figure out", "stop" instead of "shut down" (unless it is the technical
  term). Phrasal verbs are hard for non-native readers and translators.
- **No vague words.** Avoid "some", "a few", "quite", "basically",
  "should work". Give the number, the condition, or the fact.
- **Lists for sequences.** Put steps that occur in order in a numbered
  list, one action per step.
