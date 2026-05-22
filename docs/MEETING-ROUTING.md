# Meeting Routing — How it Works

When the client opens a Plaud recording with a spoken phrase like "Kingsway Pharma meeting with John Smith," the skill uses that phrase to route the meeting to the right folder (Windows) or tag the action items with the right Context (Mac), and to decide whether the meeting is included in the Friday rollup.

## The contract

**Every Plaud recording opens with a known keyword.** The skill reads the first 30 seconds of the transcript and looks for the keyword. First match wins.

Defaults for the launch client:

| Keyword (matched case-insensitive) | Output folder / Notion Context | Included in Friday rollup? |
|---|---|---|
| `Kingsway Pharma` | `Kingsway Pharma` | ✅ yes |
| `Church` | `Church` | ❌ no |
| `Personal` | `Personal` | ❌ no |
| _(none of the above)_ | `Uncategorized` | ❌ no |

## How the matching works

Pseudocode:

```python
opening = transcript[:scan_first_seconds_of_speech]  # default 30 sec
for entry in config["meeting_routing"]["types"]:
    if entry["keyword"].lower() in opening.lower():
        meeting_type = entry["folder"]
        include_in_rollup = entry["include_in_weekly_rollup"]
        break
else:
    meeting_type = config["meeting_routing"]["fallback_folder"]  # "Uncategorized"
    include_in_rollup = False
```

**Order matters.** If "Kingsway Pharma" is listed before "Personal" and a recording says "Kingsway Pharma — a quick personal note," the recording goes to Kingsway Pharma because that's the first match. Put more specific keywords first.

## Adding a new meeting type

Edit `~/.claude/skills/meetings-digest/config.json` and add an entry under `meeting_routing.types`:

```json
{
  "keyword": "Family",
  "folder": "Family",
  "include_in_weekly_rollup": false
}
```

Save the file. No reinstall needed — the skill reads the config at every run.

To rebuild past meetings with the new routing: clear the dedup state file (`~/.claude/skills/meetings-digest/state/processed-file-ids.json`) and run `/meetings-digest --days 30 --force`. The skill re-processes everything and routes by the updated config.

## Changing whether a type is included in the rollup

Edit `meeting_routing.types[i].include_in_weekly_rollup` in the config. Affects only future rollups.

## Troubleshooting

### "Why did my recording go to Uncategorized?"

Three possibilities, in order of likelihood:

1. **Client forgot to state the keyword.** The transcript opens with something else. Listen to the first 30 seconds in Plaud — does the keyword appear? If not, this is operator-error on the recording side, not the skill.
2. **Keyword wasn't transcribed accurately.** Plaud sometimes mis-transcribes proper nouns. If `Kingsway Pharma` comes out as `King's Way Pharma` or `Kings Way Farma` in the transcript, the substring match fails. Fix: add the misspelling as an additional keyword pointing to the same folder. Example:
   ```json
   {"keyword": "Kingsway", "folder": "Kingsway Pharma", "include_in_weekly_rollup": true},
   {"keyword": "Kings Way", "folder": "Kingsway Pharma", "include_in_weekly_rollup": true}
   ```
3. **Client said the keyword too late.** If the meeting opens with 90 seconds of small talk before the keyword, it might fall outside the `scan_first_seconds` window. Increase `meeting_routing.scan_first_seconds` to 60 or 90 in the config. Or coach the client to say the keyword FIRST.

### "My Friday rollup is missing meetings I expected"

Check whether those meetings routed to the right meeting type AND that type has `include_in_weekly_rollup: true`. The Friday rollup is strictly scoped — Church, Personal, and Uncategorized are excluded by default and won't appear no matter how many meetings they contain.

### "I want to recover a meeting from Uncategorized"

Three options:

1. **Manually move it** in OneDrive (Windows) or update the Notion Context property (Mac). Easy if it's one or two recordings.
2. **Re-route by adjusting keywords + re-running.** Add the actual opening phrase as a keyword in the config (point to the right folder), clear the recording's entry from the dedup state, run `/meetings-digest --since <date>`. The skill re-processes and routes correctly.
3. **Just accept it.** Uncategorized recordings still get the same extraction treatment — they just sit in their own folder/Context. Nothing's lost.

## Best practices for the client

Train them on these:

- **Lead with the keyword.** First sentence of the recording, no preamble. Plaud's transcription accuracy is higher on the first words of any session.
- **Keep keywords short + distinct.** `Kingsway Pharma` is good. `My quarterly business review meeting with the Kingsway Pharma team` is too long and unreliable.
- **Don't mix meeting types in one recording.** If a Kingsway call shifts into a personal aside, end the Plaud recording and start a new one with the new keyword. Mid-recording switches won't re-route.

## Privacy implications

The first 30 seconds of every recording's transcript is scanned for routing. Nothing else about that scan is stored or logged — just the routing decision. The full transcript continues into the normal extraction pipeline.
